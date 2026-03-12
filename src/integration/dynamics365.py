"""Dynamics 365 Dataverse REST API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from config.settings import get_settings


@dataclass
class DynamicsCase:
    """Case payload for Dynamics 365."""

    ticket_number: str
    title: str
    description: str
    origin: str
    customer_name: str
    customer_email: str
    status: str
    queue: str
    ai_category: str = ""
    ai_confidence: float = 0.0
    ai_response: str = ""
    ai_action: str = ""


class Dynamics365Client:
    """
    Dynamics 365 Dataverse REST API client.
    Uses client credentials OAuth2 against Azure AD.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        instance_url: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.settings = settings
        self.tenant_id = tenant_id or settings.dynamics_tenant_id
        self.client_id = client_id or settings.dynamics_client_id
        self.client_secret = client_secret or settings.dynamics_client_secret
        self.instance_url = (instance_url or settings.dynamics_instance_url or "").rstrip(
            "/"
        )
        self._access_token: Optional[str] = None
        self.case_entity = settings.dynamics_case_entity
        self.case_id_field = settings.dynamics_case_id_field

    async def _authenticate(self) -> str:
        """Obtain OAuth2 access token via client credentials flow."""
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError(
                "Dynamics 365 credentials not configured. "
                "Set DYNAMICS_TENANT_ID, DYNAMICS_CLIENT_ID, DYNAMICS_CLIENT_SECRET."
            )

        token_url = (
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        )
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": f"{self.instance_url}/.default",
                    "grant_type": "client_credentials",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data["access_token"]
            return self._access_token

    async def authenticate(self) -> str:
        """Authenticate if necessary and return a valid token."""
        if self._access_token:
            return self._access_token
        return await self._authenticate()

    def _headers(self) -> dict[str, str]:
        """Get auth headers for API requests."""
        if not self._access_token:
            raise RuntimeError("Not authenticated. Call _authenticate first.")
        return {
            "Authorization": f"Bearer {self._access_token}",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _entity_url(self, entity: str | None = None) -> str:
        entity_name = entity or self.case_entity
        return f"{self.instance_url}/api/data/v9.2/{entity_name}"

    def _record_url(self, record_id: str, entity: str | None = None) -> str:
        return f"{self._entity_url(entity)}({record_id})"

    def _case_payload(self, case: DynamicsCase, include_ticket_number: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        field_map = {
            self.settings.dynamics_title_field: case.title,
            self.settings.dynamics_description_field: case.description,
            self.settings.dynamics_status_field: case.status,
            self.settings.dynamics_customer_name_field: case.customer_name,
            self.settings.dynamics_customer_email_field: case.customer_email,
            self.settings.dynamics_origin_field: case.origin,
            self.settings.dynamics_queue_field: case.queue,
            self.settings.dynamics_ai_category_field: case.ai_category,
            self.settings.dynamics_ai_confidence_field: case.ai_confidence,
            self.settings.dynamics_ai_response_field: case.ai_response,
            self.settings.dynamics_ai_action_field: case.ai_action,
        }
        if include_ticket_number and self.settings.dynamics_ticket_number_field:
            payload[self.settings.dynamics_ticket_number_field] = case.ticket_number

        for field_name, value in field_map.items():
            if field_name:
                payload[field_name] = value
        return payload

    def _from_dataverse(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self.settings
        return {
            "id": payload.get(settings.dynamics_case_id_field),
            "ticket_number": payload.get(settings.dynamics_ticket_number_field, ""),
            "title": payload.get(settings.dynamics_title_field, ""),
            "description": payload.get(settings.dynamics_description_field, ""),
            "status": payload.get(settings.dynamics_status_field, ""),
            "customer_name": payload.get(settings.dynamics_customer_name_field, "") if settings.dynamics_customer_name_field else "",
            "customer_email": payload.get(settings.dynamics_customer_email_field, "") if settings.dynamics_customer_email_field else "",
            "origin": payload.get(settings.dynamics_origin_field, "") if settings.dynamics_origin_field else "",
            "queue": payload.get(settings.dynamics_queue_field, "") if settings.dynamics_queue_field else "",
            "ai_category": payload.get(settings.dynamics_ai_category_field, "") if settings.dynamics_ai_category_field else "",
            "ai_confidence": payload.get(settings.dynamics_ai_confidence_field, 0) if settings.dynamics_ai_confidence_field else 0,
            "ai_response": payload.get(settings.dynamics_ai_response_field, "") if settings.dynamics_ai_response_field else "",
            "ai_action": payload.get(settings.dynamics_ai_action_field, "") if settings.dynamics_ai_action_field else "",
            "raw": payload,
        }

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        prefer_return: bool = True,
    ) -> httpx.Response:
        await self.authenticate()
        headers = self._headers()
        if prefer_return:
            headers["Prefer"] = "return=representation"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method,
                url,
                json=json_payload,
                params=params,
                headers=headers,
            )
        response.raise_for_status()
        return response

    async def create_case(self, case: DynamicsCase) -> dict[str, Any]:
        """Create a case in Dynamics 365 Dataverse."""
        payload = self._case_payload(case)
        response = await self._request("POST", self._entity_url(), json_payload=payload)
        if response.content:
            data = response.json()
            return self._from_dataverse(data)
        entity_id = response.headers.get("OData-EntityId", "").rsplit("(", 1)[-1].rstrip(")")
        return {"id": entity_id, **payload}

    async def update_case(
        self,
        case_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a case in Dynamics 365 Dataverse."""
        response = await self._request(
            "PATCH",
            self._record_url(case_id),
            json_payload=updates,
        )
        if response.content:
            return self._from_dataverse(response.json())
        refreshed = await self.get_case(case_id)
        return refreshed

    async def get_case(self, case_id: str) -> dict[str, Any]:
        """Get a case from Dynamics 365 Dataverse."""
        response = await self._request(
            "GET",
            self._record_url(case_id),
            prefer_return=False,
        )
        return self._from_dataverse(response.json())

    async def list_cases(
        self,
        *,
        top: int = 25,
        select_fields: list[str] | None = None,
        filter_query: str | None = None,
    ) -> list[dict[str, Any]]:
        """List cases from Dynamics 365 Dataverse."""
        params: dict[str, Any] = {"$top": top}
        if select_fields:
            params["$select"] = ",".join(select_fields)
        if filter_query:
            params["$filter"] = filter_query
        response = await self._request(
            "GET",
            self._entity_url(),
            params=params,
            prefer_return=False,
        )
        payload = response.json()
        return [self._from_dataverse(item) for item in payload.get("value", [])]

    async def sync_ai_result(
        self,
        *,
        case_id: str,
        category: str,
        confidence: float,
        response_text: str,
        action: str,
        queue: str,
    ) -> dict[str, Any]:
        """Push AI processing results into configured Dataverse fields."""
        updates = {}
        if self.settings.dynamics_ai_category_field:
            updates[self.settings.dynamics_ai_category_field] = category
        if self.settings.dynamics_ai_confidence_field:
            updates[self.settings.dynamics_ai_confidence_field] = confidence
        if self.settings.dynamics_ai_response_field:
            updates[self.settings.dynamics_ai_response_field] = response_text
        if self.settings.dynamics_ai_action_field:
            updates[self.settings.dynamics_ai_action_field] = action
        if self.settings.dynamics_queue_field:
            updates[self.settings.dynamics_queue_field] = queue
        if not updates:
            return {"id": case_id, "status": "no-op", "reason": "No Dynamics AI field mappings configured."}
        return await self.update_case(case_id, updates)
