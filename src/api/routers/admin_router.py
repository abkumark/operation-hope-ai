"""Admin & system routes — analytics, queues, config, escalations, health, feedback, dynamics."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config.routing_rules import QUEUES, get_all_queue_members, get_queue_members
from config.settings import get_settings
from src.auth import ENGINEER_LIST, User, get_engineer_emails
from src.api.deps import require_admin, require_auth
from src.analytics.reports import generate_summary_report
from src.analytics.trend_engine import generate_trend_report
from src.core.router import RoutingAction
from src.integration.dynamics365 import Dynamics365Client, DynamicsCase
from src.integration.power_automate import handle_power_automate_webhook
from src.knowledge.vectorstore import get_kb_status
from src.notifications.email_service import (
    get_notifications_for_ticket,
    send_escalation_notification,
)
from src.storage.sqlite_db import (
    get_engineer_expertise,
    get_feedback_by_category,
    get_feedback_for_ticket,
    get_feedback_summary,
    get_ticket_by_id,
    init_database,
    set_engineer_expertise,
    submit_resolution_feedback,
    update_ticket_fields,
)
from src.workflow.pipeline import get_processed_tickets, _load_pipeline_result

_logger = logging.getLogger(__name__)
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

router = APIRouter(tags=["admin"])


# ── Health & System ──────────────────────────────────────────────────────

@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check — verifies DB connectivity and reports LLM/SMTP status."""
    settings = get_settings()
    checks: dict[str, str] = {"service": "operation-hope-ai"}

    # DB check
    try:
        from src.storage.sqlite_db import get_connection
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        checks["database"] = "healthy"
    except Exception as exc:
        checks["database"] = f"unhealthy: {exc}"

    # LLM check
    checks["llm_provider"] = settings.active_provider
    checks["llm_configured"] = settings.active_provider != "fallback"

    # SMTP check
    checks["smtp_configured"] = bool(settings.smtp_username)

    # KB check
    try:
        kb_status = get_kb_status()
        checks["kb_chunks"] = kb_status.get("chunk_count", 0)
    except Exception:
        checks["kb_chunks"] = "unavailable"

    overall = "healthy" if checks.get("database") == "healthy" else "degraded"
    checks["status"] = overall
    return checks


@router.get("/llm/status")
async def llm_status(user: User = Depends(require_admin)) -> dict[str, Any]:
    """Return LLM provider status, token usage summary, and recent call history."""
    from src.llm.provider import get_llm_provider, get_token_tracker

    settings = get_settings()
    tracker = get_token_tracker()

    provider_info = {"provider": "not_initialized", "model": "none"}
    try:
        llm = get_llm_provider()
        provider_info = {
            "provider": llm.provider_name,
            "model": llm.model_name,
        }
    except Exception:
        pass

    return {
        **provider_info,
        "configured_provider": settings.llm_provider,
        "active_provider": settings.active_provider,
        "usage_summary": tracker.get_summary(),
        "recent_calls": tracker.get_recent(20),
    }


# ── Analytics ────────────────────────────────────────────────────────────

@router.get("/analytics/summary")
async def analytics_summary(user: User = Depends(require_auth)) -> dict[str, Any]:
    """Get analytics summary report."""
    return generate_summary_report()


@router.get("/analytics/trends")
async def analytics_trends(user: User = Depends(require_auth)) -> dict[str, Any]:
    """Strategic trend analysis."""
    return generate_trend_report()


# ── Escalations ──────────────────────────────────────────────────────────

@router.post("/tickets/check-escalations")
async def check_stale_escalations(user: User = Depends(require_admin)) -> dict[str, Any]:
    """Check for tickets with no edits for 24+ hours and escalate them.

    Uses the `updated_at` column to detect stale tickets — any ticket in an
    active status that hasn't been edited within `settings.escalation_hours`
    (default 24) hours gets escalated and an alert email is sent.
    """
    from src.storage.sqlite_db import get_stale_tickets

    settings = get_settings()
    escalation_hours = settings.escalation_hours

    stale_rows = get_stale_tickets(max_hours_since_update=escalation_hours)
    escalated = []

    for row in stale_rows:
        ticket_id = row["ticket_id"]
        subject = row["subject"]
        last_touch = row["updated_at"] or row["created_at"] or row["processed_at"]

        try:
            hours_open = (datetime.now() - datetime.fromisoformat(last_touch)).total_seconds() / 3600
        except Exception:
            hours_open = escalation_hours

        update_ticket_fields(ticket_id, status="Escalated")
        escalated.append(ticket_id)

        try:
            import json as _json
            rte = _json.loads(row["routing_json"])
            queue_name = rte.get("queue", "IT Support")
        except Exception:
            queue_name = "IT Support"

        try:
            members = get_queue_members(queue_name) if queue_name else []
            recipients = get_engineer_emails(members) if members else []
            # Always include the configured escalation mailbox for visibility
            escalation_email = settings.escalation_email or settings.smtp_sender
            if escalation_email and not any(r[1] == escalation_email for r in recipients):
                recipients.append(("Escalation Alerts", escalation_email))
            # Also notify the original submitter
            sub_email = row.get("submitter_email", "")
            sub_name = row.get("submitter", "")
            if sub_email and not any(r[1] == sub_email for r in recipients):
                recipients.append((sub_name or "Submitter", sub_email))
            send_escalation_notification(
                ticket_id=ticket_id, subject=subject,
                queue_name=queue_name, hours_open=hours_open, recipients=recipients,
            )
        except Exception:
            _logger.exception("Failed to send escalation email for %s", ticket_id)

    return {
        "status": "success",
        "escalation_rule": f"No edits for {escalation_hours}h",
        "escalation_threshold_hours": escalation_hours,
        "escalated_count": len(escalated),
        "escalated_tickets": escalated,
    }


# ── Notifications ────────────────────────────────────────────────────────

@router.get("/notifications/{ticket_id}")
async def ticket_notifications(
    ticket_id: str, user: User = Depends(require_auth),
) -> dict[str, Any]:
    """Return email notification history for a ticket."""
    notifications = get_notifications_for_ticket(ticket_id)
    return {"ticket_id": ticket_id, "count": len(notifications), "notifications": notifications}


# ── Queues ───────────────────────────────────────────────────────────────

@router.get("/queues")
async def list_queues(user: User = Depends(require_auth)) -> dict[str, Any]:
    """Return all queues with their member engineers."""
    eng_map = {e["username"]: e["display_name"] for e in ENGINEER_LIST}
    result = {}
    for name, cfg in QUEUES.items():
        result[name] = {
            "name": cfg.name,
            "description": cfg.description,
            "members": [
                {"username": u, "display_name": eng_map.get(u, u)}
                for u in cfg.members
            ],
        }
    return {"queues": result}


@router.get("/queues/{queue_name}/members")
async def queue_members(
    queue_name: str, user: User = Depends(require_auth),
) -> dict[str, Any]:
    """Return engineers assigned to a specific queue."""
    members = get_queue_members(queue_name)
    if not members:
        raise HTTPException(status_code=404, detail="Queue not found or has no members")
    eng_map = {e["username"]: e["display_name"] for e in ENGINEER_LIST}
    return {
        "queue": queue_name,
        "members": [{"username": u, "display_name": eng_map.get(u, u)} for u in members],
    }


# ── Config / Expertise ───────────────────────────────────────────────────

@router.get("/config/expertise")
async def get_expertise(user: User = Depends(require_admin)) -> dict[str, Any]:
    """Return the engineer-to-category expertise mapping."""
    return {"expertise": get_engineer_expertise()}


class SetExpertiseRequest(BaseModel):
    engineer_username: str = Field(..., description="Engineer username")
    category_ids: list[str] = Field(..., description="Category IDs the engineer is expert in")


@router.post("/config/expertise")
async def save_expertise(
    request: SetExpertiseRequest, user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Save expertise tags for an engineer."""
    valid_usernames = {e["username"] for e in ENGINEER_LIST}
    if request.engineer_username not in valid_usernames:
        raise HTTPException(status_code=422, detail="Invalid engineer username")
    set_engineer_expertise(request.engineer_username, request.category_ids)
    return {"status": "success", "engineer": request.engineer_username, "categories": request.category_ids}


# ── Integration Status ───────────────────────────────────────────────────

@router.get("/integration/status")
async def integration_status(user: User = Depends(require_admin)) -> dict[str, Any]:
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


# ── Dynamics 365 ─────────────────────────────────────────────────────────

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


@router.post("/dynamics/cases")
async def dynamics_create_case(
    request: DynamicsCaseRequest, user: User = Depends(require_admin),
) -> dict[str, Any]:
    client = Dynamics365Client()
    payload = DynamicsCase(**request.model_dump())
    return await client.create_case(payload)


@router.get("/dynamics/cases/{case_id}")
async def dynamics_get_case(
    case_id: str, user: User = Depends(require_admin),
) -> dict[str, Any]:
    client = Dynamics365Client()
    return await client.get_case(case_id)


@router.patch("/dynamics/cases/{case_id}")
async def dynamics_update_case(
    case_id: str,
    request: DynamicsUpdateRequest,
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    client = Dynamics365Client()
    return await client.update_case(case_id, request.updates)


@router.get("/dynamics/cases")
async def dynamics_list_cases(
    top: int = 25,
    filter_query: Optional[str] = None,
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    client = Dynamics365Client()
    cases = await client.list_cases(top=top, filter_query=filter_query)
    return {"count": len(cases), "cases": cases}


# ── Power Automate Webhook ───────────────────────────────────────────────

@router.post("/webhook/power-automate")
async def power_automate_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Power Automate webhook endpoint for case creation triggers."""
    return await handle_power_automate_webhook(payload)


# ── Resolution Feedback ─────────────────────────────────────────────────


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
    row = get_ticket_by_id(request.ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    target = _load_pipeline_result(row)
    if target.submitter_email.lower() != request.email.lower():
        raise HTTPException(status_code=403, detail="Email does not match this ticket")

    fb_id = submit_resolution_feedback(
        ticket_id=request.ticket_id, helpful=request.helpful,
        comment=request.comment, submitter_email=request.email,
    )
    return {"status": "success", "feedback_id": fb_id}


@router.get("/feedback/summary")
async def feedback_summary(user: User = Depends(require_admin)) -> dict[str, Any]:
    """Aggregate resolution feedback stats (admin)."""
    return {"overall": get_feedback_summary(), "by_category": get_feedback_by_category()}


@router.get("/feedback/{ticket_id}")
async def ticket_feedback(
    ticket_id: str, user: User = Depends(require_auth),
) -> dict[str, Any]:
    """Get feedback entries for a specific ticket."""
    return {"ticket_id": ticket_id, "feedback": get_feedback_for_ticket(ticket_id)}
