"""Tests for approval persistence, history, and transitions."""

from unittest.mock import patch

from src.workflow.approval import (
    approve_approval,
    get_approval_history,
    get_pending_approvals,
    reject_approval,
)
from src.workflow.pipeline import process_ticket


class TestApprovalWorkflow:
    @patch("src.core.classifier.get_llm_provider")
    def test_pending_approval_created_for_reviewable_ticket(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")

        process_ticket(
            subject="Password reset",
            description="I need help resetting my password",
            submitter="test@example.com",
        )

        pending = get_pending_approvals()
        assert len(pending) == 1
        assert pending[0].status.value == "pending_approval"

    @patch("src.core.classifier.get_llm_provider")
    def test_approval_can_be_sent(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")

        result = process_ticket(
            subject="Password reset",
            description="I need help resetting my password",
            submitter="test@example.com",
        )

        approval = approve_approval(
            ticket_id=result.ticket_id,
            reviewer="Reviewer",
            final_response="Approved response",
            mark_sent=True,
        )

        assert approval is not None
        assert approval.status.value == "sent"
        assert approval.final_response == "Approved response"
        history = get_approval_history(result.ticket_id)
        assert [event.event_type for event in history] == ["created", "approved", "sent"]

    @patch("src.core.classifier.get_llm_provider")
    def test_approval_can_be_rejected(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")

        result = process_ticket(
            subject="Password reset",
            description="I need help resetting my password",
            submitter="test@example.com",
        )

        approval = reject_approval(
            ticket_id=result.ticket_id,
            reviewer="Reviewer",
            notes="Needs manual handling",
        )

        assert approval is not None
        assert approval.status.value == "rejected"
        assert approval.reviewer_notes == "Needs manual handling"
        history = get_approval_history(result.ticket_id)
        assert history[-1].event_type == "rejected"
