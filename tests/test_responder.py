"""Tests for response generation (mocked LLM)."""
import pytest
from unittest.mock import patch

from src.core.classifier import ClassificationResult
from src.core.router import RoutingAction, RoutingDecision, route_ticket
from src.core.responder import generate_ticket_response, TicketResponse


def _make_classification(category_id="password_reset", confidence=0.9):
    return ClassificationResult(
        category_id=category_id,
        category_name="Password Reset",
        confidence=confidence,
        language="en",
        sentiment="neutral",
        urgency="medium",
        is_hr=False,
        summary="Password reset request",
        raw_text="I need to reset my password",
    )


class TestResponder:
    @patch("src.knowledge.rag_pipeline.search_kb")
    @patch("src.knowledge.rag_pipeline.get_llm_provider")
    def test_generates_response_for_auto_resolve(self, mock_provider, mock_search):
        mock_search.return_value = [
            {"content": "Reset steps...", "metadata": {"title": "Password Reset", "chunk_type": "resolution"}, "similarity": 0.9}
        ]
        mock_llm = mock_provider.return_value
        mock_llm.chat.return_value = "Thank you for contacting us. Here are the reset steps..."

        c = _make_classification()
        r = route_ticket(c)
        response = generate_ticket_response(c, r, "Password reset", "I need to reset my password")

        assert response is not None
        assert isinstance(response, TicketResponse)
        assert len(response.response_text) > 0

    def test_no_response_for_hr_ticket(self):
        c = _make_classification()
        c.is_hr = True
        r = RoutingDecision(
            action=RoutingAction.HR_EXCLUDED,
            queue="HR",
            reason="HR",
            classification=c,
            requires_approval=False,
        )
        response = generate_ticket_response(c, r, "HR complaint", "harassment")
        assert response is None

    def test_no_response_for_escalation(self):
        c = _make_classification()
        r = RoutingDecision(
            action=RoutingAction.ESCALATE,
            queue="IT Support",
            reason="Critical",
            classification=c,
            requires_approval=False,
        )
        response = generate_ticket_response(c, r, "System down", "Everything is broken")
        assert response is None
