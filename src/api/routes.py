"""FastAPI routes for Operation HOPE AI."""

from __future__ import annotations

import csv
import io
import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config.settings import get_settings
from src.analytics.metrics import mark_ticket_resolved
from src.analytics.reports import generate_summary_report
from src.analytics.trend_engine import generate_trend_report
from src.core.router import RoutingAction
from src.auth import ENGINEER_LIST, authenticate
from src.integration.dynamics365 import Dynamics365Client, DynamicsCase
from src.integration.power_automate import handle_power_automate_webhook
from src.knowledge.kb_ingester import load_all_kb_articles
from src.knowledge.vectorstore import get_kb_status, ingest_kb_articles, search_kb
from src.notifications.email_service import (
    _is_smtp_configured,
    get_submitter_email,
    send_status_update,
    send_ticket_confirmation,
)
from src.workflow.approval import (
    approve_approval,
    get_all_approvals,
    get_approval,
    get_approval_history,
    get_pending_approvals,
    reject_approval,
    reroute_approval,
)
from src.core.resolution_engine import find_similar_tickets
from src.storage.sqlite_db import (
    create_kb_draft,
    create_placeholder_ticket,
    delete_kb_draft,
    delete_ticket,
    get_engineer_expertise,
    get_expertise_for_category,
    get_feedback_by_category,
    get_feedback_for_ticket,
    get_feedback_summary,
    get_kb_draft,
    init_database,
    list_kb_drafts,
    next_ticket_id,
    publish_kb_draft,
    set_engineer_expertise,
    submit_resolution_feedback,
    update_ticket_fields,
)
from src.workflow.pipeline import get_processed_tickets, process_ticket

_logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

router = APIRouter()


def _get_ticket_result(ticket_id: str):
    return next((ticket for ticket in get_processed_tickets() if ticket.ticket_id == ticket_id), None)


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


@router.post("/auth/login")
async def login(request: LoginRequest) -> dict[str, Any]:
    """Authenticate user and return profile info."""
    user = authenticate(request.username, request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role.value,
        "email": user.email,
    }


class PublicTicketRequest(BaseModel):
    subject: str = Field(..., description="Ticket subject/title", min_length=3, max_length=300)
    description: str = Field(..., description="Ticket description/body", min_length=10, max_length=5000)
    submitter_name: str = Field(..., description="Submitter full name", min_length=1, max_length=200)
    submitter_email: str = Field(..., description="Submitter email address", max_length=320)


def _process_ticket_background(
    ticket_id: str,
    subject: str,
    description: str,
    submitter_name: str,
    submitter_email: str,
) -> None:
    """Run the full AI pipeline in a background thread.

    The placeholder ticket row already exists so the user has a ticket ID.
    This function overwrites it with the real AI results.
    """
    try:
        process_ticket(
            subject=subject,
            description=description,
            submitter=submitter_name,
            submitter_email=submitter_email,
            ticket_id=ticket_id,
        )
    except Exception:
        _logger.exception("Background AI pipeline failed for %s", ticket_id)
        update_ticket_fields(ticket_id, status="Open")

    try:
        send_ticket_confirmation(
            ticket_id=ticket_id,
            recipient_email=submitter_email,
            recipient_name=submitter_name,
            subject=subject,
        )
    except Exception:
        _logger.warning("Failed to send confirmation email for %s", ticket_id)


@router.post("/tickets/submit")
async def submit_public_ticket(
    request: PublicTicketRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Public (unauthenticated) ticket submission for website visitors.

    Returns the ticket ID immediately; the AI pipeline runs in the background.
    """
    if not _EMAIL_RE.match(request.submitter_email):
        raise HTTPException(status_code=422, detail="Invalid email address format")

    init_database()
    ticket_id = next_ticket_id()

    create_placeholder_ticket(
        ticket_id=ticket_id,
        subject=request.subject,
        description=request.description,
        submitter=request.submitter_name,
        submitter_email=request.submitter_email,
    )

    background_tasks.add_task(
        _process_ticket_background,
        ticket_id=ticket_id,
        subject=request.subject,
        description=request.description,
        submitter_name=request.submitter_name,
        submitter_email=request.submitter_email,
    )

    return {
        "ticket_id": ticket_id,
        "email_sent": False,
        "message": (
            f"Your request has been submitted as {ticket_id}. "
            "Our AI is analyzing your request — you will receive updates shortly."
        ),
        "auto_resolved": False,
        "instant_resolved": False,
        "category": "Processing…",
        "confidence": 0,
        "ai_resolution": None,
        "kb_articles_used": [],
    }


@router.get("/tickets/status/{ticket_id}")
async def public_ticket_status(ticket_id: str, email: str = "") -> dict[str, Any]:
    """Public (unauthenticated) ticket status lookup. Requires matching email."""
    tickets = get_processed_tickets()
    target = next((t for t in tickets if t.ticket_id == ticket_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if email and target.submitter_email.lower() != email.lower():
        raise HTTPException(status_code=403, detail="Email does not match this ticket")
    existing_feedback = get_feedback_for_ticket(ticket_id)
    return {
        "ticket_id": target.ticket_id,
        "subject": target.subject,
        "status": target.status,
        "category": target.classification.category_name,
        "submitted_at": target.processed_at.isoformat(),
        "ai_resolution": target.ai_resolution if target.status == "Approved" else None,
        "assigned_to": target.assigned_to or None,
        "has_feedback": len(existing_feedback) > 0,
    }


class ProcessTicketRequest(BaseModel):
    subject: str = Field(..., description="Ticket subject/title")
    description: str = Field(..., description="Ticket description/body")
    submitter: str = Field(default="Unknown", description="Submitter name or email")


class ProcessTicketResponse(BaseModel):
    ticket_id: str
    category_id: str
    category_name: str
    confidence: float
    routing_action: str
    queue: str
    response_text: str
    processing_time_ms: float


class KBSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    category: Optional[str] = Field(default=None, description="Filter by category")
    limit: int = Field(default=5, ge=1, le=20, description="Max results")


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


class DynamicsCaseRequest(BaseModel):
    ticket_number: str
    title: str
    description: str
    origin: str = "portal"
    customer_name: str = ""
    customer_email: str = ""
    status: str = "active"
    queue: str = "IT Support"
    ai_category: str = ""
    ai_confidence: float = 0.0
    ai_response: str = ""
    ai_action: str = ""


class DynamicsUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)


@router.post("/tickets/process", response_model=ProcessTicketResponse)
async def process_ticket_endpoint(request: ProcessTicketRequest) -> dict[str, Any]:
    """Process a single ticket through the AI pipeline."""
    result = process_ticket(
        subject=request.subject,
        description=request.description,
        submitter=request.submitter,
    )
    response_text = ""
    if result.response:
        response_text = result.response.response_text

    return {
        "ticket_id": result.ticket_id,
        "category_id": result.classification.category_id,
        "category_name": result.classification.category_name,
        "confidence": result.classification.confidence,
        "routing_action": result.routing.action.value,
        "queue": result.routing.queue,
        "response_text": response_text,
        "processing_time_ms": result.processing_time_ms,
    }


@router.get("/tickets")
async def list_tickets() -> dict[str, Any]:
    """List all processed tickets."""
    tickets = get_processed_tickets()
    return {
        "total": len(tickets),
        "tickets": [
            {
                "ticket_id": t.ticket_id,
                "subject": t.subject,
                "submitter": t.submitter,
                "description": t.description[:200],
                "status": t.status,
                "assigned_to": t.assigned_to,
                "ai_resolution": t.ai_resolution[:200] if t.ai_resolution else "",
                "similar_ticket_ids": t.similar_ticket_ids,
                "category_id": t.classification.category_id,
                "category_name": t.classification.category_name,
                "confidence": t.classification.confidence,
                "routing_action": t.routing.action.value,
                "queue": t.routing.queue,
                "approval_status": t.approval.status.value if t.approval else None,
                "processing_time_ms": t.processing_time_ms,
                "processed_at": t.processed_at.isoformat(),
            }
            for t in tickets
        ],
    }


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str) -> dict[str, Any]:
    """Get a single ticket by ID."""
    tickets = get_processed_tickets()
    for t in tickets:
        if t.ticket_id == ticket_id:
            response_text = ""
            kb_articles = []
            if t.response:
                response_text = t.response.response_text
                kb_articles = t.response.kb_articles_used
            return {
                "ticket_id": t.ticket_id,
                "subject": t.subject,
                "description": t.description,
                "submitter": t.submitter,
                "status": t.status,
                "assigned_to": t.assigned_to,
                "ai_resolution": t.ai_resolution,
                "similar_ticket_ids": t.similar_ticket_ids,
                "classification": {
                    "category_id": t.classification.category_id,
                    "category_name": t.classification.category_name,
                    "confidence": t.classification.confidence,
                    "language": t.classification.language,
                    "sentiment": t.classification.sentiment,
                    "urgency": t.classification.urgency,
                    "is_hr": t.classification.is_hr,
                    "summary": t.classification.summary,
                },
                "routing": {
                    "action": t.routing.action.value,
                    "queue": t.routing.queue,
                    "reason": t.routing.reason,
                    "requires_approval": t.routing.requires_approval,
                },
                "response_text": response_text,
                "kb_articles_used": kb_articles,
                "processing_time_ms": t.processing_time_ms,
                "processed_at": t.processed_at.isoformat(),
                "action_summary": t.action_summary,
            }
    raise HTTPException(status_code=404, detail="Ticket not found")


@router.post("/kb/ingest")
async def kb_ingest(force: bool = False) -> dict[str, Any]:
    """Trigger KB ingestion."""
    settings = get_settings()
    count = ingest_kb_articles(kb_dir=str(settings.knowledge_base_dir), force_reingest=force)
    return {"documents_added": count, "status": "success"}


@router.get("/kb/status")
async def kb_status() -> dict[str, Any]:
    """Return KB article and vector store status."""
    status = get_kb_status()
    return {"status": "success", **status}


@router.get("/kb/articles")
async def kb_articles() -> dict[str, Any]:
    """Return KB article metadata."""
    settings = get_settings()
    articles = load_all_kb_articles(settings.knowledge_base_dir)
    return {
        "count": len(articles),
        "articles": [
            {
                "filename": article.filename,
                "title": article.title,
                "category": article.category,
                "ticket_type": article.ticket_type,
                "auto_resolvable": article.auto_resolvable,
                "queue": article.queue,
                "last_updated": article.last_updated,
            }
            for article in articles
        ],
    }


@router.get("/kb/articles/{filename}")
async def kb_article_detail(filename: str) -> dict[str, Any]:
    """Return full content for a single KB article by filename."""
    settings = get_settings()
    articles = load_all_kb_articles(settings.knowledge_base_dir)
    for article in articles:
        if article.filename == filename:
            return {
                "filename": article.filename,
                "title": article.title,
                "category": article.category,
                "ticket_type": article.ticket_type,
                "auto_resolvable": article.auto_resolvable,
                "queue": article.queue,
                "last_updated": article.last_updated,
                "content": article.content,
                "resolution_steps": article.resolution_steps,
                "response_template": article.response_template,
                "internal_notes": article.internal_notes,
            }
    raise HTTPException(status_code=404, detail="KB article not found")


@router.get("/kb/search")
async def kb_search(
    query: str,
    category: Optional[str] = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search the knowledge base."""
    results = search_kb(query=query, n_results=limit, category_filter=category)
    return {
        "query": query,
        "count": len(results),
        "results": [
            {
                "content": r["content"][:500],
                "title": r["metadata"].get("title", ""),
                "category": r["metadata"].get("category", ""),
                "similarity": r.get("similarity", 0),
            }
            for r in results
        ],
    }


@router.get("/kb/self-service")
async def kb_self_service(query: str, limit: int = 5) -> dict[str, Any]:
    """Public (unauthenticated) self-service KB search for end-users.

    Returns simplified, user-friendly results without internal metadata.
    """
    if len(query.strip()) < 3:
        raise HTTPException(status_code=422, detail="Query must be at least 3 characters")
    results = search_kb(query=query, n_results=limit)
    return {
        "query": query,
        "count": len(results),
        "results": [
            {
                "title": r["metadata"].get("title", "Untitled"),
                "summary": r["content"][:300],
                "category": r["metadata"].get("category", ""),
            }
            for r in results
        ],
    }


@router.get("/analytics/summary")
async def analytics_summary() -> dict[str, Any]:
    """Get analytics summary report."""
    return generate_summary_report()


@router.get("/analytics/trends")
async def analytics_trends() -> dict[str, Any]:
    """Strategic trend analysis: clusters, training alerts, engineer performance, AI vs Human."""
    return generate_trend_report()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "operation-hope-ai"}


@router.post("/tickets/check-escalations")
async def check_stale_escalations() -> dict[str, Any]:
    """Check for tickets that have been unassigned too long and escalate them.

    This endpoint can be called periodically (e.g. by a cron job or scheduler)
    to catch tickets that slipped through.
    """
    from datetime import datetime
    from src.workflow.escalation import should_escalate, EscalationReason

    tickets = get_processed_tickets()
    escalated = []
    for t in tickets:
        if t.status not in ("Open", "Assigned") or t.routing.action in (
            RoutingAction.HR_EXCLUDED,
            RoutingAction.ESCALATE,
        ):
            continue
        needs, reason = should_escalate(
            urgency=t.classification.urgency,
            category_id=t.classification.category_id,
            confidence=t.classification.confidence,
            created_at=t.processed_at,
        )
        if needs and reason == EscalationReason.TIME_THRESHOLD:
            update_ticket_fields(t.ticket_id, status="Escalated")
            escalated.append(t.ticket_id)

    return {
        "status": "success",
        "escalated_count": len(escalated),
        "escalated_tickets": escalated,
    }


@router.get("/integration/status")
async def integration_status() -> dict[str, Any]:
    """Return integration mode and configured Dynamics settings."""
    settings = get_settings()
    return {
        "use_mock_dynamics": settings.use_mock_dynamics,
        "instance_url": settings.dynamics_instance_url,
        "case_entity": settings.dynamics_case_entity,
        "configured": bool(
            settings.dynamics_tenant_id
            and settings.dynamics_client_id
            and settings.dynamics_client_secret
        ),
    }


@router.post("/dynamics/cases")
async def dynamics_create_case(request: DynamicsCaseRequest) -> dict[str, Any]:
    """Create a case in live Dynamics 365 Dataverse."""
    client = Dynamics365Client()
    payload = DynamicsCase(**request.model_dump())
    return await client.create_case(payload)


@router.get("/dynamics/cases/{case_id}")
async def dynamics_get_case(case_id: str) -> dict[str, Any]:
    """Fetch a case from live Dynamics 365 Dataverse."""
    client = Dynamics365Client()
    return await client.get_case(case_id)


@router.patch("/dynamics/cases/{case_id}")
async def dynamics_update_case(case_id: str, request: DynamicsUpdateRequest) -> dict[str, Any]:
    """Update a case in live Dynamics 365 Dataverse."""
    client = Dynamics365Client()
    return await client.update_case(case_id, request.updates)


@router.get("/dynamics/cases")
async def dynamics_list_cases(top: int = 25, filter_query: Optional[str] = None) -> dict[str, Any]:
    """List cases from live Dynamics 365 Dataverse."""
    client = Dynamics365Client()
    cases = await client.list_cases(top=top, filter_query=filter_query)
    return {"count": len(cases), "cases": cases}


@router.get("/approvals")
async def list_approvals(status: Optional[str] = None) -> dict[str, Any]:
    """List approvals, optionally filtered by status."""
    approvals = get_pending_approvals() if status == "pending" else get_all_approvals()
    return {
        "count": len(approvals),
        "approvals": [
            {
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
            for approval in approvals
        ],
    }


@router.get("/approvals/{ticket_id}")
async def approval_detail(ticket_id: str) -> dict[str, Any]:
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
async def approval_history(ticket_id: str) -> dict[str, Any]:
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
async def approval_approve(ticket_id: str, request: ApprovalDecisionRequest) -> dict[str, Any]:
    """Approve and optionally mark a drafted response as sent."""
    approval = approve_approval(
        ticket_id=ticket_id,
        reviewer=request.reviewer,
        final_response=request.final_response,
        mark_sent=request.send,
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    ticket = _get_ticket_result(ticket_id)
    final_resolution = approval.final_response or approval.ai_response
    update_ticket_fields(ticket_id, status="Approved", ai_resolution=final_resolution)
    mark_ticket_resolved(ticket_id, was_auto_resolved=bool(ticket and not ticket.assigned_to))

    name, email = get_submitter_email(ticket_id)
    if email:
        try:
            send_status_update(
                ticket_id=ticket_id,
                recipient_email=email,
                recipient_name=name,
                new_status=approval.status.value,
                details=final_resolution,
            )
        except Exception:
            pass

    return {"status": "success", "approval_status": approval.status.value}


@router.post("/approvals/{ticket_id}/reject")
async def approval_reject(ticket_id: str, request: ApprovalRejectRequest) -> dict[str, Any]:
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
        except Exception:
            pass

    return {"status": "success", "approval_status": approval.status.value}


@router.post("/approvals/{ticket_id}/reroute")
async def approval_reroute(ticket_id: str, request: ApprovalRerouteRequest) -> dict[str, Any]:
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
        except Exception:
            pass

    return {"status": "success", "approval_status": approval.status.value, "queue": approval.assigned_queue}


@router.get("/notifications/{ticket_id}")
async def ticket_notifications(ticket_id: str) -> dict[str, Any]:
    """Return email notification history for a ticket (admin)."""
    from src.notifications.email_service import get_notifications_for_ticket

    notifications = get_notifications_for_ticket(ticket_id)
    return {"ticket_id": ticket_id, "count": len(notifications), "notifications": notifications}


class EditResolutionRequest(BaseModel):
    ai_resolution: str = Field(..., description="Edited AI resolution text")


class ApproveCloseRequest(BaseModel):
    reviewer: str = Field(..., description="Reviewer performing the approval")
    ai_resolution: str | None = Field(default=None, description="Optional edited resolution")


@router.delete("/tickets/{ticket_id}")
async def delete_ticket_endpoint(ticket_id: str) -> dict[str, Any]:
    """Delete a ticket and all associated records (admin)."""
    found = delete_ticket(ticket_id)
    if not found:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"status": "success", "message": f"Ticket {ticket_id} deleted"}


@router.patch("/tickets/{ticket_id}/resolution")
async def edit_ticket_resolution(ticket_id: str, request: EditResolutionRequest) -> dict[str, Any]:
    """Edit the AI-generated resolution for a ticket (admin)."""
    updated = update_ticket_fields(ticket_id, ai_resolution=request.ai_resolution)
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"status": "success", "ticket_id": ticket_id}


@router.post("/tickets/{ticket_id}/resolve")
@router.post("/tickets/{ticket_id}/approve-close")
async def resolve_ticket(ticket_id: str, request: ApproveCloseRequest) -> dict[str, Any]:
    """Resolve the ticket after admin review."""
    ticket = _get_ticket_result(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    fields: dict[str, str] = {"status": "Approved"}
    if request.ai_resolution is not None:
        fields["ai_resolution"] = request.ai_resolution
    updated = update_ticket_fields(ticket_id, **fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")

    mark_ticket_resolved(ticket_id, was_auto_resolved=not ticket.assigned_to)

    name, email = get_submitter_email(ticket_id)
    resolution_text = request.ai_resolution or ticket.ai_resolution or "Your request has been resolved."
    if email:
        try:
            send_status_update(
                ticket_id=ticket_id,
                recipient_email=email,
                recipient_name=name,
                new_status="closed",
                details=resolution_text,
            )
        except Exception:
            pass

    return {"status": "success", "ticket_id": ticket_id, "ticket_status": "Approved"}


@router.get("/tickets/{ticket_id}/similar")
async def similar_tickets_endpoint(ticket_id: str) -> dict[str, Any]:
    """Find tickets similar to the given ticket (used for resolution context)."""
    tickets = get_processed_tickets()
    target = None
    for t in tickets:
        if t.ticket_id == ticket_id:
            target = t
            break
    if target is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    all_tickets = {t.ticket_id: t for t in tickets}
    similar = find_similar_tickets(target.subject, target.description, exclude_ticket_id=ticket_id)
    enriched = []
    for s in similar:
        pipeline_t = all_tickets.get(s.ticket_id)
        cat_name = pipeline_t.classification.category_name if pipeline_t else ""
        enriched.append(
            {
                "ticket_id": s.ticket_id,
                "subject": s.subject,
                "description": s.description[:300],
                "similarity": s.similarity,
                "status": s.status,
                "category_name": cat_name,
                "ai_resolution": s.ai_resolution[:300] if s.ai_resolution else "",
            }
        )
    return {
        "ticket_id": ticket_id,
        "count": len(enriched),
        "similar": enriched,
    }


@router.get("/users/engineers")
async def list_engineers() -> dict[str, Any]:
    """Return the list of available engineers for ticket assignment."""
    return {"engineers": ENGINEER_LIST}


@router.get("/config/expertise")
async def get_expertise() -> dict[str, Any]:
    """Return the engineer-to-category expertise mapping."""
    return {"expertise": get_engineer_expertise()}


class SetExpertiseRequest(BaseModel):
    engineer_username: str = Field(..., description="Engineer username")
    category_ids: list[str] = Field(..., description="List of category IDs the engineer is expert in")


@router.post("/config/expertise")
async def save_expertise(request: SetExpertiseRequest) -> dict[str, Any]:
    """Save expertise tags for an engineer (replaces existing)."""
    valid_usernames = {e["username"] for e in ENGINEER_LIST}
    if request.engineer_username not in valid_usernames:
        raise HTTPException(status_code=422, detail="Invalid engineer username")
    set_engineer_expertise(request.engineer_username, request.category_ids)
    return {"status": "success", "engineer": request.engineer_username, "categories": request.category_ids}


@router.get("/tickets/{ticket_id}/recommend-engineer")
async def recommend_engineer(ticket_id: str) -> dict[str, Any]:
    """Recommend the best engineer based on expertise match and current workload."""
    tickets = get_processed_tickets()
    target = None
    for t in tickets:
        if t.ticket_id == ticket_id:
            target = t
            break
    if target is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    category_id = target.classification.category_id
    experts = get_expertise_for_category(category_id)

    assigned_counts: dict[str, int] = {}
    for t in tickets:
        if t.assigned_to and t.status in ("Open", "Assigned", "PendingApproval"):
            assigned_counts[t.assigned_to] = assigned_counts.get(t.assigned_to, 0) + 1

    all_engineers = [e["username"] for e in ENGINEER_LIST]
    ranked = []
    for eng in all_engineers:
        is_expert = eng in experts
        load = assigned_counts.get(eng, 0)
        ranked.append({
            "username": eng,
            "display_name": next((e["display_name"] for e in ENGINEER_LIST if e["username"] == eng), eng),
            "is_expert": is_expert,
            "open_tickets": load,
        })
    ranked.sort(key=lambda e: (-int(e["is_expert"]), e["open_tickets"]))

    return {
        "ticket_id": ticket_id,
        "category_id": category_id,
        "category_name": target.classification.category_name,
        "recommendations": ranked,
        "top_pick": ranked[0] if ranked else None,
    }


class AssignTicketRequest(BaseModel):
    assigned_to: str = Field(..., description="Engineer username to assign the ticket to")
    notes: str = Field(default="", description="Optional routing notes")


@router.post("/tickets/{ticket_id}/assign")
async def assign_ticket(ticket_id: str, request: AssignTicketRequest) -> dict[str, Any]:
    """Assign (route) a ticket to a specific engineer and set status to Assigned."""
    valid_usernames = {e["username"] for e in ENGINEER_LIST}
    if request.assigned_to not in valid_usernames:
        raise HTTPException(status_code=422, detail="Invalid engineer username")

    updated = update_ticket_fields(
        ticket_id, status="Assigned", assigned_to=request.assigned_to
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "status": "success",
        "ticket_id": ticket_id,
        "assigned_to": request.assigned_to,
        "ticket_status": "Assigned",
    }


@router.get("/tickets/my-queue/{username}")
async def my_queue(username: str) -> dict[str, Any]:
    """Return tickets assigned to the given engineer."""
    tickets = get_processed_tickets()
    mine = [t for t in tickets if t.assigned_to == username]
    return {
        "total": len(mine),
        "tickets": [
            {
                "ticket_id": t.ticket_id,
                "subject": t.subject,
                "submitter": t.submitter,
                "description": t.description[:200],
                "status": t.status,
                "assigned_to": t.assigned_to,
                "ai_resolution": t.ai_resolution[:300] if t.ai_resolution else "",
                "category_id": t.classification.category_id,
                "category_name": t.classification.category_name,
                "confidence": t.classification.confidence,
                "queue": t.routing.queue,
            }
            for t in mine
        ],
    }


class EngineerResolveRequest(BaseModel):
    engineer: str = Field(..., description="Engineer username submitting the resolution")
    resolution: str = Field(..., description="Manual resolution text from the engineer")


@router.post("/tickets/{ticket_id}/engineer-resolve")
async def engineer_resolve(ticket_id: str, request: EngineerResolveRequest) -> dict[str, Any]:
    """Engineer provides a manual resolution; ticket moves to PendingApproval for admin."""
    updated = update_ticket_fields(
        ticket_id,
        ai_resolution=request.resolution,
        status="PendingApproval",
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {
        "status": "success",
        "ticket_id": ticket_id,
        "ticket_status": "PendingApproval",
        "message": "Resolution submitted. Ticket returned to admin for final approval.",
    }


@router.post("/webhook/power-automate")
async def power_automate_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Power Automate webhook endpoint for case creation triggers."""
    return await handle_power_automate_webhook(payload)


# ─── KB Drafts (Resolution-to-KB Pipeline) ───


class KBDraftCreateRequest(BaseModel):
    ticket_id: str = Field(..., description="Source ticket ID")
    title: str = Field(..., description="Draft article title", min_length=3, max_length=300)
    category: str = Field(default="", description="Category ID for the KB article")
    content: str = Field(..., description="Article content (resolution text)", min_length=10)
    created_by: str = Field(default="", description="Admin who created the draft")


@router.post("/kb/drafts")
async def create_kb_draft_endpoint(request: KBDraftCreateRequest) -> dict[str, Any]:
    """Create a KB article draft from a resolved ticket."""
    draft_id = create_kb_draft(
        ticket_id=request.ticket_id,
        title=request.title,
        category=request.category,
        content=request.content,
        created_by=request.created_by,
    )
    return {"status": "success", "draft_id": draft_id}


@router.get("/kb/drafts")
async def list_kb_drafts_endpoint(status: Optional[str] = None) -> dict[str, Any]:
    """List KB article drafts, optionally filtered by status (draft/published)."""
    drafts = list_kb_drafts(status=status)
    return {"count": len(drafts), "drafts": drafts}


@router.get("/kb/drafts/{draft_id}")
async def get_kb_draft_endpoint(draft_id: int) -> dict[str, Any]:
    """Get a single KB draft by ID."""
    draft = get_kb_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="KB draft not found")
    return draft


@router.post("/kb/drafts/{draft_id}/publish")
async def publish_kb_draft_endpoint(draft_id: int) -> dict[str, Any]:
    """Publish a KB draft (writes it as a new KB article and ingests into vector store)."""
    draft = get_kb_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="KB draft not found")
    if draft["status"] != "draft":
        raise HTTPException(status_code=400, detail="Draft is already published")

    settings = get_settings()
    kb_dir = settings.knowledge_base_dir
    safe_title = re.sub(r"[^a-z0-9_]+", "_", draft["title"].lower()).strip("_")
    filename = f"{safe_title}.md"
    filepath = kb_dir / filename

    md_content = (
        f"---\n"
        f"title: \"{draft['title']}\"\n"
        f"category: \"{draft['category']}\"\n"
        f"ticket_type: \"any\"\n"
        f"auto_resolvable: false\n"
        f"queue: \"IT Support\"\n"
        f"last_updated: \"{draft['created_at'][:10]}\"\n"
        f"---\n\n"
        f"# {draft['title']}\n\n"
        f"{draft['content']}\n"
    )
    filepath.write_text(md_content, encoding="utf-8")

    published = publish_kb_draft(draft_id)
    if not published:
        raise HTTPException(status_code=500, detail="Failed to mark draft as published")

    added = ingest_kb_articles(kb_dir=str(kb_dir), force_reingest=True)

    return {
        "status": "success",
        "draft_id": draft_id,
        "filename": filename,
        "documents_ingested": added,
    }


@router.delete("/kb/drafts/{draft_id}")
async def delete_kb_draft_endpoint(draft_id: int) -> dict[str, Any]:
    """Delete a KB draft."""
    found = delete_kb_draft(draft_id)
    if not found:
        raise HTTPException(status_code=404, detail="KB draft not found")
    return {"status": "success", "draft_id": draft_id}


# ─── Resolution Feedback ───


class FeedbackRequest(BaseModel):
    ticket_id: str = Field(..., description="Ticket ID the feedback is for")
    email: str = Field(..., description="Submitter email for verification", max_length=320)
    helpful: bool = Field(..., description="Whether the resolution was helpful")
    comment: str = Field(default="", description="Optional comment", max_length=1000)


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest) -> dict[str, Any]:
    """Public endpoint: submitter rates an AI resolution."""
    if not _EMAIL_RE.match(request.email):
        raise HTTPException(status_code=422, detail="Invalid email address format")
    tickets = get_processed_tickets()
    target = next((t for t in tickets if t.ticket_id == request.ticket_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if target.submitter_email.lower() != request.email.lower():
        raise HTTPException(status_code=403, detail="Email does not match this ticket")

    fb_id = submit_resolution_feedback(
        ticket_id=request.ticket_id,
        helpful=request.helpful,
        comment=request.comment,
        submitter_email=request.email,
    )
    return {"status": "success", "feedback_id": fb_id}


@router.get("/feedback/summary")
async def feedback_summary() -> dict[str, Any]:
    """Aggregate resolution feedback stats (admin)."""
    return {
        "overall": get_feedback_summary(),
        "by_category": get_feedback_by_category(),
    }


@router.get("/feedback/{ticket_id}")
async def ticket_feedback(ticket_id: str) -> dict[str, Any]:
    """Get feedback entries for a specific ticket."""
    return {"ticket_id": ticket_id, "feedback": get_feedback_for_ticket(ticket_id)}


# ─── Export Reports (CSV) ───


@router.get("/analytics/export")
async def export_analytics_csv() -> StreamingResponse:
    """Export analytics data as a downloadable CSV file."""
    tickets = get_processed_tickets()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Ticket ID", "Subject", "Submitter", "Status", "Category", "Confidence",
        "Routing Action", "Queue", "Assigned To", "AI Resolution (first 200 chars)",
        "Processing Time (ms)", "Processed At",
    ])
    for t in tickets:
        writer.writerow([
            t.ticket_id,
            t.subject,
            t.submitter,
            t.status,
            t.classification.category_name,
            round(t.classification.confidence, 2),
            t.routing.action.value,
            t.routing.queue,
            t.assigned_to or "",
            (t.ai_resolution or "")[:200],
            round(t.processing_time_ms, 1),
            t.processed_at.isoformat(),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=hope_ai_report.csv"},
    )
