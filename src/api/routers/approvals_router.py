"""Approval workflow routes."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.analytics.metrics import mark_ticket_resolved
from src.auth import User
from src.api.deps import require_admin, require_auth
from src.api.routers.tickets_router import _get_ticket_or_404
from src.notifications.email_service import get_submitter_email, send_status_update
from src.storage.sqlite_db import update_ticket_fields
from src.workflow.approval import (
    approve_approval,
    get_all_approvals,
    get_approval,
    get_approval_history,
    get_pending_approvals,
    reject_approval,
    reroute_approval,
)

_logger = logging.getLogger(__name__)

router = APIRouter(tags=["approvals"])


class ApprovalDecisionRequest(BaseModel):
    reviewer: str = Field(..., description="Reviewer/technician name")
    final_response: str | None = Field(default=None, description="Optional edited response text")
    send: bool = Field(default=True, description="Mark response as sent after approval")


class ApprovalRejectRequest(BaseModel):
    reviewer: str = Field(..., description="Reviewer/technician name")
    notes: str = Field(default="", description="Reason for rejection")


class ApprovalRerouteRequest(BaseModel):
    reviewer: str = Field(..., description="Reviewer/technician name")
    new_queue: str = Field(..., description="Queue to reroute the ticket to")
    notes: str = Field(default="", description="Reason for rerouting")


@router.get("/approvals")
async def list_approvals(
    status: Optional[str] = None,
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """List approvals, optionally filtered by status."""
    approvals = get_pending_approvals() if status == "pending" else get_all_approvals()
    return {
        "count": len(approvals),
        "approvals": [
            {
                "ticket_id": a.ticket_id,
                "status": a.status.value,
                "ai_category": a.ai_category,
                "ai_confidence": a.ai_confidence,
                "ai_response": a.ai_response,
                "assigned_queue": a.assigned_queue,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
                "reviewed_by": a.reviewed_by,
                "reviewer_notes": a.reviewer_notes,
                "final_response": a.final_response,
            }
            for a in approvals
        ],
    }


@router.get("/approvals/{ticket_id}")
async def approval_detail(
    ticket_id: str, user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Fetch a single approval record."""
    approval = get_approval(ticket_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {
        "ticket_id": approval.ticket_id,
        "status": approval.status.value,
        "ai_category": approval.ai_category,
        "ai_confidence": approval.ai_confidence,
        "ai_response": approval.ai_response,
        "assigned_queue": approval.assigned_queue,
        "created_at": approval.created_at.isoformat(),
        "updated_at": approval.updated_at.isoformat(),
        "reviewed_by": approval.reviewed_by,
        "reviewer_notes": approval.reviewer_notes,
        "final_response": approval.final_response,
    }


@router.get("/approvals/{ticket_id}/history")
async def approval_history(
    ticket_id: str, user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Fetch review/audit history for a single approval record."""
    approval = get_approval(ticket_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    events = get_approval_history(ticket_id)
    return {
        "ticket_id": ticket_id,
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "actor": event.actor,
                "details": event.details,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
    }


@router.post("/approvals/{ticket_id}/approve")
async def approval_approve(
    ticket_id: str,
    request: ApprovalDecisionRequest,
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Approve and optionally mark a drafted response as sent."""
    approval = approve_approval(
        ticket_id=ticket_id,
        reviewer=request.reviewer,
        final_response=request.final_response,
        mark_sent=request.send,
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    ticket = _get_ticket_or_404(ticket_id)
    final_resolution = approval.final_response or approval.ai_response
    update_ticket_fields(ticket_id, status="Completed", ai_resolution=final_resolution)
    mark_ticket_resolved(ticket_id, was_auto_resolved=bool(ticket and not ticket.assigned_to))

    name, email = get_submitter_email(ticket_id)
    if email:
        try:
            send_status_update(
                ticket_id=ticket_id,
                recipient_email=email,
                recipient_name=name,
                new_status="completed",
                details=final_resolution,
            )
        except Exception as exc:
            _logger.exception("Failed to send approval email for %s: %s", ticket_id, exc)

    return {"status": "success", "approval_status": approval.status.value}


@router.post("/approvals/{ticket_id}/reject")
async def approval_reject(
    ticket_id: str,
    request: ApprovalRejectRequest,
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Reject an AI-drafted response."""
    approval = reject_approval(ticket_id=ticket_id, reviewer=request.reviewer, notes=request.notes)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    update_ticket_fields(ticket_id, status="Open")

    name, email = get_submitter_email(ticket_id)
    if email:
        try:
            send_status_update(
                ticket_id=ticket_id,
                recipient_email=email,
                recipient_name=name,
                new_status="rejected",
                details=request.notes or "Your request needs additional information.",
            )
        except Exception as exc:
            _logger.exception("Failed to send rejection email for %s: %s", ticket_id, exc)

    return {"status": "success", "approval_status": approval.status.value}


@router.post("/approvals/{ticket_id}/reroute")
async def approval_reroute(
    ticket_id: str,
    request: ApprovalRerouteRequest,
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Reroute a pending approval to a different queue."""
    approval = reroute_approval(
        ticket_id=ticket_id,
        reviewer=request.reviewer,
        new_queue=request.new_queue,
        notes=request.notes,
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    update_ticket_fields(ticket_id, status="Open")

    name, email = get_submitter_email(ticket_id)
    if email:
        try:
            send_status_update(
                ticket_id=ticket_id,
                recipient_email=email,
                recipient_name=name,
                new_status="rerouted",
                details=f"Your request has been transferred to the {request.new_queue} team.",
            )
        except Exception as exc:
            _logger.exception("Failed to send reroute email for %s: %s", ticket_id, exc)

    return {"status": "success", "approval_status": approval.status.value, "queue": approval.assigned_queue}
