"""Power Automate webhook handler for case creation triggers."""
from typing import Any

from config.settings import get_settings
from src.integration.dynamics365 import Dynamics365Client
from src.integration.mock_dynamics import create_case, get_case, update_case
from src.workflow.pipeline import process_ticket


async def handle_power_automate_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Process webhook payload from Power Automate flow (case creation trigger).
    Returns classification and response results for the flow to use.
    """
    title = payload.get("title", payload.get("subject", ""))
    description = payload.get("description", payload.get("body", ""))
    submitter = payload.get("customer_email", payload.get("submitter", ""))
    customer_name = payload.get("customer_name", "")
    case_id = payload.get("case_id", "")

    if not title and not description:
        return {
            "success": False,
            "error": "Missing required fields: title/subject and description/body",
            "classification": None,
            "response": None,
        }

    settings = get_settings()
    live_case_id = case_id or payload.get("dynamics_case_id", "")
    case = None
    if settings.use_mock_dynamics:
        case = get_case(case_id) if case_id else None
        if case is None:
            case = create_case(
                title=title,
                description=description,
                origin=payload.get("origin", "power_automate"),
                customer_name=customer_name,
                customer_email=submitter,
            )

    result = process_ticket(
        subject=title,
        description=description,
        submitter=submitter,
        ticket_id=case.ticket_number if case is not None else payload.get("ticket_number"),
    )

    if settings.use_mock_dynamics and case is not None:
        update_case(
            case.case_id,
            queue=result.routing.queue,
            ai_category=result.classification.category_id,
            ai_confidence=result.classification.confidence,
            ai_response=result.response.response_text if result.response else "",
            ai_action=result.routing.action.value,
        )
    elif live_case_id:
        client = Dynamics365Client()
        await client.sync_ai_result(
            case_id=live_case_id,
            category=result.classification.category_id,
            confidence=result.classification.confidence,
            response_text=result.response.response_text if result.response else "",
            action=result.routing.action.value,
            queue=result.routing.queue,
        )

    return {
        "success": True,
        "ticket_id": result.ticket_id,
        "case_id": case.case_id if case is not None else live_case_id,
        "classification": {
            "category_id": result.classification.category_id,
            "confidence": result.classification.confidence,
            "language": result.classification.language,
            "urgency": result.classification.urgency,
            "sentiment": result.classification.sentiment,
        },
        "routing": {
            "action": result.routing.action.value,
            "queue": result.routing.queue,
        },
        "response": result.response.response_text if result.response else "",
        "processing_time_ms": result.processing_time_ms,
    }


def power_automate_webhook_schema() -> dict[str, Any]:
    """Return expected webhook payload schema for documentation."""
    return {
        "title": "Power Automate Case Creation Webhook",
        "description": "Payload from Power Automate when a new case is created",
        "properties": {
            "title": {"type": "string", "description": "Case title/subject"},
            "subject": {"type": "string", "description": "Alias for title"},
            "description": {"type": "string", "description": "Case description/body"},
            "body": {"type": "string", "description": "Alias for description"},
            "customer_email": {"type": "string", "description": "Submitter email"},
            "customer_name": {"type": "string", "description": "Submitter name"},
            "submitter": {"type": "string", "description": "Alias for customer_email"},
        },
        "required": [],
    }
