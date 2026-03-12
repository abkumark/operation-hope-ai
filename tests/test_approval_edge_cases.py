"""Tests for approval workflow edge cases."""

from unittest.mock import patch

from src.workflow.approval import (
    approve_approval,
    get_approval,
    get_pending_approvals,
    reject_approval,
)
from src.workflow.pipeline import process_ticket


def _create_pending_ticket():
    """Helper to create a ticket that generates a pending approval."""
    with patch("src.core.classifier.get_llm_provider") as mock:
        mock.side_effect = Exception("No LLM")
        return process_ticket(
            subject="Password reset",
            description="I need help resetting my password",
            submitter="test@example.com",
        )


class TestDoubleApprove:
    def test_double_approve_is_idempotent(self):
        result = _create_pending_ticket()
        ticket_id = result.ticket_id

        first = approve_approval(ticket_id=ticket_id, reviewer="A", mark_sent=True)
        assert first is not None
        assert first.status.value == "sent"

        second = approve_approval(ticket_id=ticket_id, reviewer="B", mark_sent=True)
        # Second approve should still return the approval (already approved/sent)
        approval = get_approval(ticket_id)
        assert approval is not None
        # Status should remain sent from the first approval
        assert approval.status.value == "sent"


class TestApproveAfterReject:
    def test_approve_after_reject(self):
        result = _create_pending_ticket()
        ticket_id = result.ticket_id

        rejected = reject_approval(ticket_id=ticket_id, reviewer="R1", notes="Bad")
        assert rejected is not None
        assert rejected.status.value == "rejected"

        # Attempting to approve a rejected ticket
        approved = approve_approval(ticket_id=ticket_id, reviewer="R2", mark_sent=True)
        approval = get_approval(ticket_id)
        assert approval is not None


class TestRejectAfterApprove:
    def test_reject_after_approve(self):
        result = _create_pending_ticket()
        ticket_id = result.ticket_id

        approved = approve_approval(ticket_id=ticket_id, reviewer="A", mark_sent=True)
        assert approved is not None

        # Attempting to reject an already approved/sent ticket
        rejected = reject_approval(ticket_id=ticket_id, reviewer="R", notes="Too late")
        approval = get_approval(ticket_id)
        assert approval is not None


class TestNoApprovalForLowConfidence:
    def test_low_confidence_no_approval(self):
        """Low confidence tickets route to human without creating an approval."""
        with patch("src.core.classifier.get_llm_provider") as mock:
            mock.side_effect = Exception("No LLM")
            result = process_ticket(
                subject="Something random",
                description="Not sure what this is about",
                submitter="test@example.com",
            )

        # If routed to human (low confidence), no approval should be created
        if result.routing.action.value == "route_to_human":
            assert result.approval is None


class TestPendingApprovalsFiltering:
    def test_approved_ticket_not_in_pending(self):
        result = _create_pending_ticket()
        ticket_id = result.ticket_id

        pending_before = get_pending_approvals()
        pending_ids_before = [p.ticket_id for p in pending_before]
        assert ticket_id in pending_ids_before

        approve_approval(ticket_id=ticket_id, reviewer="Admin", mark_sent=True)

        pending_after = get_pending_approvals()
        pending_ids_after = [p.ticket_id for p in pending_after]
        assert ticket_id not in pending_ids_after
