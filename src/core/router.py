"""Intelligent ticket routing engine with confidence-based decision making."""

from dataclasses import dataclass
from enum import Enum

from config.categories import TICKET_CATEGORIES, get_auto_resolvable_categories
from config.routing_rules import get_queue_for_category
from config.settings import get_settings
from src.core.classifier import ClassificationResult


class RoutingAction(str, Enum):
    INSTANT_RESOLVE = "instant_resolve"
    AUTO_RESOLVE = "auto_resolve"
    SUGGEST_REVIEW = "suggest_review"
    ROUTE_TO_HUMAN = "route_to_human"
    HR_EXCLUDED = "hr_excluded"
    ESCALATE = "escalate"


@dataclass
class RoutingDecision:
    action: RoutingAction
    queue: str
    reason: str
    classification: ClassificationResult
    requires_approval: bool


def route_ticket(classification: ClassificationResult) -> RoutingDecision:
    """Determine routing action based on classification results."""
    settings = get_settings()

    if classification.is_hr:
        return RoutingDecision(
            action=RoutingAction.HR_EXCLUDED,
            queue="HR",
            reason="HR ticket - excluded from AI processing per business rules",
            classification=classification,
            requires_approval=False,
        )

    if classification.urgency == "critical":
        queue = get_queue_for_category(classification.category_id)
        return RoutingDecision(
            action=RoutingAction.ESCALATE,
            queue=queue,
            reason=f"Critical urgency detected - immediate escalation to {queue}",
            classification=classification,
            requires_approval=False,
        )

    queue = get_queue_for_category(classification.category_id)
    auto_resolvable_categories = get_auto_resolvable_categories()
    is_auto_resolvable = classification.category_id in auto_resolvable_categories

    if (
        settings.instant_resolve_enabled
        and is_auto_resolvable
        and classification.confidence >= settings.instant_resolve_threshold
    ):
        return RoutingDecision(
            action=RoutingAction.AUTO_RESOLVE,
            queue=queue,
            reason=f"Very high confidence ({classification.confidence:.0%}) auto-resolvable ticket. "
                   f"AI draft generated and queued for admin resolution.",
            classification=classification,
            requires_approval=True,
        )

    if classification.confidence >= settings.auto_resolve_threshold and is_auto_resolvable:
        return RoutingDecision(
            action=RoutingAction.AUTO_RESOLVE,
            queue=queue,
            reason=f"High confidence ({classification.confidence:.0%}) auto-resolvable ticket. "
                   f"AI draft generated and queued for admin resolution.",
            classification=classification,
            requires_approval=True,
        )

    if classification.confidence >= settings.review_threshold:
        return RoutingDecision(
            action=RoutingAction.SUGGEST_REVIEW,
            queue=queue,
            reason=f"Medium confidence ({classification.confidence:.0%}). "
                   f"AI suggestion generated, routing to {queue} for human review.",
            classification=classification,
            requires_approval=True,
        )

    return RoutingDecision(
        action=RoutingAction.ROUTE_TO_HUMAN,
        queue=queue,
        reason=f"Low confidence ({classification.confidence:.0%}). "
               f"Routing to {queue} for manual classification and handling.",
        classification=classification,
        requires_approval=False,
    )
