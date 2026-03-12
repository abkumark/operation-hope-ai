"""High-level response generation orchestrator."""

from dataclasses import dataclass

from src.core.classifier import ClassificationResult
from src.core.router import RoutingDecision, RoutingAction
from src.knowledge.rag_pipeline import generate_response


@dataclass
class TicketResponse:
    response_text: str
    kb_articles_used: list[str]
    language: str
    should_send: bool
    requires_approval: bool


def generate_ticket_response(
    classification: ClassificationResult,
    routing: RoutingDecision,
    subject: str,
    description: str,
) -> TicketResponse | None:
    """Generate a response for a ticket based on classification and routing.

    Returns None if no response should be generated (e.g., HR tickets, escalations).
    """
    if routing.action in (RoutingAction.HR_EXCLUDED, RoutingAction.ESCALATE):
        return None

    rag_result = generate_response(classification, subject, description)

    should_send = False
    requires_approval = routing.action in (
        RoutingAction.AUTO_RESOLVE,
        RoutingAction.INSTANT_RESOLVE,
        RoutingAction.SUGGEST_REVIEW,
    )

    return TicketResponse(
        response_text=rag_result["response"],
        kb_articles_used=rag_result["kb_articles_used"],
        language=rag_result["language"],
        should_send=should_send,
        requires_approval=requires_approval,
    )
