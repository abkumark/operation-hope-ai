"""Tests for the configurable Dynamics 365 Dataverse client."""

from src.integration.dynamics365 import Dynamics365Client, DynamicsCase


class TestDynamicsClient:
    def test_case_payload_uses_configured_fields(self):
        client = Dynamics365Client()
        case = DynamicsCase(
            ticket_number="HOPE-00001",
            title="Password reset",
            description="Please reset my password",
            origin="portal",
            customer_name="Client Name",
            customer_email="client@example.com",
            status="active",
            queue="IT Support",
            ai_category="password_reset",
            ai_confidence=0.91,
            ai_response="Draft response",
            ai_action="suggest_review",
        )

        payload = client._case_payload(case)
        assert payload[client.settings.dynamics_title_field] == "Password reset"
        assert payload[client.settings.dynamics_description_field] == "Please reset my password"
        assert payload[client.settings.dynamics_ticket_number_field] == "HOPE-00001"

    def test_from_dataverse_maps_core_fields(self):
        client = Dynamics365Client()
        raw = {
            client.settings.dynamics_case_id_field: "abc-123",
            client.settings.dynamics_ticket_number_field: "HOPE-00001",
            client.settings.dynamics_title_field: "Password reset",
            client.settings.dynamics_description_field: "Please reset my password",
            client.settings.dynamics_status_field: "active",
        }
        mapped = client._from_dataverse(raw)
        assert mapped["id"] == "abc-123"
        assert mapped["ticket_number"] == "HOPE-00001"
        assert mapped["title"] == "Password reset"
        assert mapped["status"] == "active"
