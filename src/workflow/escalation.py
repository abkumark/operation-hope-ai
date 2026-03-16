"""Escalation rules engine for ticket routing.

Fixed: Rules are now evaluated with proper precedence. The urgency check
is corrected so that "high" urgency tickets are NOT auto-escalated (they
still get AI response generation). Only "critical" urgency auto-escalates.
Low confidence triggers escalation independently of urgency.
"""

from dataclasses import dataclass
from datetime import datetime
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


# Default escalation rules — ordered by severity (highest first).
# NOTE: Urgency rules use EXACT match, not >=, to prevent "high" from
# triggering the critical rule and "medium" from triggering the high rule.
DEFAULT_ESCALATION_RULES: list[EscalationRule] = [
    EscalationRule(
        reason=EscalationReason.URGENCY_CRITICAL,
        urgency_threshold="critical",
    ),
    EscalationRule(
        reason=EscalationReason.LOW_CONFIDENCE,
        min_confidence=0.4,
    ),
    EscalationRule(
        reason=EscalationReason.TIME_THRESHOLD,
        max_hours_unassigned=4.0,
    ),
]

# NOTE: URGENCY_HIGH is intentionally NOT in the default rules.
# "high" urgency tickets should still get AI response generation and
# be routed to a human for review, NOT skip AI processing entirely.
# The router already handles critical urgency escalation (router.py:43-51).
# This prevents the bug where "high" urgency tickets bypassed AI assistance.


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

    Rules are evaluated independently — the first matching rule wins.
    """
    rules = rules or DEFAULT_ESCALATION_RULES

    for rule in rules:
        # Urgency: exact match only (not >=) to prevent over-escalation
        if rule.urgency_threshold:
            if urgency == rule.urgency_threshold:
                return True, rule.reason

        # Low confidence: escalate if below minimum
        if rule.min_confidence is not None and confidence < rule.min_confidence:
            return True, rule.reason

        # Time threshold: escalate if ticket has been open too long
        if rule.max_hours_unassigned and created_at:
            elapsed = (datetime.now() - created_at).total_seconds() / 3600
            if elapsed >= rule.max_hours_unassigned:
                return True, rule.reason

        # Category-based escalation
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
