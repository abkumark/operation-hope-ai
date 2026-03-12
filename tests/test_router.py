"""Tests for ticket routing logic."""
import pytest

from src.core.classifier import ClassificationResult
from src.core.router import route_ticket, RoutingAction, RoutingDecision


def _make_classification(category_id="password_reset", confidence=0.9, urgency="medium", is_hr=False):
    return ClassificationResult(
        category_id=category_id,
        category_name="Test",
        confidence=confidence,
        language="en",
        sentiment="neutral",
        urgency=urgency,
        is_hr=is_hr,
        summary="Test ticket",
        raw_text="test",
    )


class TestRouting:
    def test_high_confidence_auto_resolvable(self):
        """High confidence + auto-resolvable category -> AUTO_RESOLVE."""
        c = _make_classification(category_id="password_reset", confidence=0.92)
        decision = route_ticket(c)
        assert decision.action == RoutingAction.AUTO_RESOLVE
        assert decision.requires_approval is True
        assert decision.queue == "IT Support"

    def test_medium_confidence_suggest_review(self):
        """Medium confidence -> SUGGEST_REVIEW."""
        c = _make_classification(category_id="password_reset", confidence=0.72)
        decision = route_ticket(c)
        assert decision.action == RoutingAction.SUGGEST_REVIEW
        assert decision.requires_approval is True

    def test_low_confidence_route_to_human(self):
        """Low confidence -> ROUTE_TO_HUMAN."""
        c = _make_classification(category_id="password_reset", confidence=0.4)
        decision = route_ticket(c)
        assert decision.action == RoutingAction.ROUTE_TO_HUMAN
        assert decision.requires_approval is False

    def test_hr_excluded(self):
        """HR ticket -> HR_EXCLUDED."""
        c = _make_classification(is_hr=True)
        decision = route_ticket(c)
        assert decision.action == RoutingAction.HR_EXCLUDED
        assert decision.queue == "HR"

    def test_critical_urgency_escalated(self):
        """Critical urgency -> ESCALATE."""
        c = _make_classification(urgency="critical")
        decision = route_ticket(c)
        assert decision.action == RoutingAction.ESCALATE

    def test_non_auto_resolvable_high_confidence(self):
        """High confidence but not auto-resolvable -> SUGGEST_REVIEW."""
        c = _make_classification(category_id="coach_assignment", confidence=0.95)
        decision = route_ticket(c)
        assert decision.action == RoutingAction.SUGGEST_REVIEW

    def test_routing_queue_ld(self):
        """L&D category routes to L&D queue."""
        c = _make_classification(category_id="course_video_issue", confidence=0.92)
        decision = route_ticket(c)
        assert decision.queue == "L&D"

    def test_routing_queue_marketing(self):
        """Marketing category routes to Marketing queue."""
        c = _make_classification(category_id="marketing_request", confidence=0.72)
        decision = route_ticket(c)
        assert decision.queue == "Marketing"

    def test_routing_queue_leadership(self):
        """Partnership routes to Leadership."""
        c = _make_classification(category_id="partnership_request", confidence=0.72)
        decision = route_ticket(c)
        assert decision.queue == "Leadership"

    def test_decision_is_dataclass(self):
        c = _make_classification()
        decision = route_ticket(c)
        assert isinstance(decision, RoutingDecision)
        assert isinstance(decision.action, RoutingAction)
        assert isinstance(decision.reason, str)
