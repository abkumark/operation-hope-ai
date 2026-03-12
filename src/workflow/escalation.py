"""Escalation rules engine for ticket routing."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from src.core.router import RoutingAction


class EscalationReason(str, Enum):
    """Reason for escalating a ticket."""

    URGENCY_HIGH = "urgency_high"
    URGENCY_CRITICAL = "urgency_critical"
    CATEGORY_REQUIRED = "category_required"
    TIME_THRESHOLD = "time_threshold"
    LOW_CONFIDENCE = "low_confidence"


@dataclass
class EscalationRule:
    """Rule defining when to escalate."""

    reason: EscalationReason
    urgency_threshold: Optional[str] = None
    category_ids: Optional[list[str]] = None
    max_hours_unassigned: Optional[float] = None
    min_confidence: Optional[float] = None


# Default escalation rules
DEFAULT_ESCALATION_RULES: list[EscalationRule] = [
    EscalationRule(
        reason=EscalationReason.URGENCY_CRITICAL,
        urgency_threshold="critical",
    ),
    EscalationRule(
        reason=EscalationReason.URGENCY_HIGH,
        urgency_threshold="high",
    ),
    EscalationRule(
        reason=EscalationReason.LOW_CONFIDENCE,
        min_confidence=0.5,
    ),
    EscalationRule(
        reason=EscalationReason.TIME_THRESHOLD,
        max_hours_unassigned=4.0,
    ),
]


def should_escalate(
    urgency: str = "normal",
    category_id: str = "",
    confidence: float = 1.0,
    created_at: Optional[datetime] = None,
    rules: Optional[list[EscalationRule]] = None,
) -> tuple[bool, Optional[EscalationReason]]:
    """
    Determine if a ticket should be escalated based on rules.
    Returns (should_escalate, reason).
    """
    rules = rules or DEFAULT_ESCALATION_RULES
    urgency_levels = {"low": 0, "medium": 1, "normal": 1, "high": 2, "critical": 3}

    for rule in rules:
        if rule.urgency_threshold:
            if urgency_levels.get(urgency, 0) >= urgency_levels.get(
                rule.urgency_threshold, 0
            ):
                return True, rule.reason

        if rule.min_confidence is not None and confidence < rule.min_confidence:
            return True, rule.reason

        if rule.max_hours_unassigned and created_at:
            elapsed = (datetime.now() - created_at).total_seconds() / 3600
            if elapsed >= rule.max_hours_unassigned:
                return True, rule.reason

        if rule.category_ids and category_id in rule.category_ids:
            return True, rule.reason

    return False, None


def get_escalation_action(
    urgency: str = "normal",
    category_id: str = "",
    confidence: float = 1.0,
    created_at: Optional[datetime] = None,
) -> RoutingAction:
    """
    Get the routing action based on escalation rules.
    """
    escalate, _ = should_escalate(
        urgency=urgency,
        category_id=category_id,
        confidence=confidence,
        created_at=created_at,
    )
    return RoutingAction.ESCALATE if escalate else RoutingAction.ROUTE_TO_HUMAN
