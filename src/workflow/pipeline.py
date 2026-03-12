"""End-to-end ticket processing pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

import logging

from src.analytics.metrics import TicketMetric, record_metric
from src.core.classifier import ClassificationResult, classify_ticket
from src.core.resolution_engine import find_similar_tickets, generate_resolution
from src.core.responder import TicketResponse, generate_ticket_response
from src.core.router import RoutingAction, RoutingDecision, route_ticket
from src.storage.sqlite_db import (
    get_connection,
    get_expertise_for_category,
    init_database,
    next_ticket_id,
    update_ticket_fields,
)
from src.workflow.approval import ApprovalRecord, create_approval, get_approval
from src.workflow.escalation import should_escalate, EscalationReason

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    ticket_id: str
    subject: str
    description: str
    submitter: str
    classification: ClassificationResult
    routing: RoutingDecision
    response: TicketResponse | None
    approval: ApprovalRecord | None
    submitter_email: str = ""
    status: str = "Open"
    ai_resolution: str = ""
    similar_ticket_ids: list[str] = field(default_factory=list)
    assigned_to: str = ""
    processed_at: datetime = field(default_factory=datetime.now)
    processing_time_ms: float = 0.0

    @property
    def action_summary(self) -> str:
        action = self.routing.action
        if action == RoutingAction.INSTANT_RESOLVE:
            return (
                f"High-confidence AI draft prepared ({self.classification.confidence:.0%} confidence) "
                f"-> {self.routing.queue} [Admin Resolve Required]"
            )
        elif action == RoutingAction.AUTO_RESOLVE:
            return (
                f"AI draft prepared ({self.classification.confidence:.0%} confidence) "
                f"-> {self.routing.queue} [Admin Resolve Required]"
            )
        elif action == RoutingAction.SUGGEST_REVIEW:
            return f"AI suggestion generated -> {self.routing.queue} [Needs Review]"
        elif action == RoutingAction.ROUTE_TO_HUMAN:
            return f"Routed to {self.routing.queue} [Manual Handling]"
        elif action == RoutingAction.HR_EXCLUDED:
            return "HR ticket - excluded from AI processing"
        elif action == RoutingAction.ESCALATE:
            return f"ESCALATED to {self.routing.queue} [Critical]"
        return f"{action.value} -> {self.routing.queue}"


def _serialize_classification(classification: ClassificationResult) -> str:
    return json.dumps(asdict(classification))


def _serialize_routing(routing: RoutingDecision) -> str:
    payload = {
        "action": routing.action.value,
        "queue": routing.queue,
        "reason": routing.reason,
        "requires_approval": routing.requires_approval,
    }
    return json.dumps(payload)


def _serialize_response(response: TicketResponse | None) -> str | None:
    if response is None:
        return None
    return json.dumps(asdict(response))


def _deserialize_classification(payload: str) -> ClassificationResult:
    data = json.loads(payload)
    return ClassificationResult(**data)


def _deserialize_routing(payload: str, classification: ClassificationResult) -> RoutingDecision:
    data = json.loads(payload)
    try:
        action = RoutingAction(data["action"])
    except ValueError:
        action = RoutingAction.ROUTE_TO_HUMAN
    return RoutingDecision(
        action=action,
        queue=data["queue"],
        reason=data["reason"],
        classification=classification,
        requires_approval=bool(data["requires_approval"]),
    )


def _deserialize_response(payload: str | None) -> TicketResponse | None:
    if not payload:
        return None
    return TicketResponse(**json.loads(payload))


def _save_pipeline_result(result: PipelineResult) -> None:
    init_database()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO tickets (
                ticket_id, subject, description, submitter, submitter_email,
                status, ai_resolution, similar_ticket_ids, assigned_to,
                classification_json, routing_json, response_json,
                processed_at, processing_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.ticket_id,
                result.subject,
                result.description,
                result.submitter,
                result.submitter_email,
                result.status,
                result.ai_resolution,
                json.dumps(result.similar_ticket_ids),
                result.assigned_to,
                _serialize_classification(result.classification),
                _serialize_routing(result.routing),
                _serialize_response(result.response),
                result.processed_at.isoformat(),
                result.processing_time_ms,
            ),
        )


def _load_pipeline_result(row) -> PipelineResult:
    classification = _deserialize_classification(row["classification_json"])
    routing = _deserialize_routing(row["routing_json"], classification)
    response = _deserialize_response(row["response_json"])
    approval = get_approval(row["ticket_id"])
    cols = row.keys()
    similar_ids_raw = row["similar_ticket_ids"] if "similar_ticket_ids" in cols else "[]"
    try:
        similar_ids = json.loads(similar_ids_raw) if similar_ids_raw else []
    except (json.JSONDecodeError, TypeError):
        similar_ids = []
    return PipelineResult(
        ticket_id=row["ticket_id"],
        subject=row["subject"],
        description=row["description"],
        submitter=row["submitter"],
        classification=classification,
        routing=routing,
        response=response,
        approval=approval,
        submitter_email=row["submitter_email"] if "submitter_email" in cols else "",
        status=row["status"] if "status" in cols else "Open",
        ai_resolution=row["ai_resolution"] if "ai_resolution" in cols else "",
        similar_ticket_ids=similar_ids,
        assigned_to=row["assigned_to"] if "assigned_to" in cols else "",
        processed_at=datetime.fromisoformat(row["processed_at"]),
        processing_time_ms=float(row["processing_time_ms"]),
    )


def _auto_assign_engineer(ticket_id: str, category_id: str) -> str:
    """Pick the best engineer by expertise match + lowest workload. Returns username or ''."""
    from src.auth import ENGINEER_LIST

    experts = get_expertise_for_category(category_id)
    all_eng = [e["username"] for e in ENGINEER_LIST]
    if not all_eng:
        return ""

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT assigned_to, COUNT(*) AS cnt FROM tickets "
            "WHERE assigned_to != '' AND status IN ('Open','Assigned','PendingApproval') "
            "GROUP BY assigned_to"
        ).fetchall()
    load = {r["assigned_to"]: r["cnt"] for r in rows}

    candidates = []
    for eng in all_eng:
        candidates.append((eng, eng in experts, load.get(eng, 0)))
    candidates.sort(key=lambda c: (-int(c[1]), c[2]))

    best = candidates[0][0]
    try:
        update_ticket_fields(ticket_id, assigned_to=best, status="Assigned")
        logger.info("Auto-assigned ticket %s to %s (expert=%s, load=%d)",
                     ticket_id, best, best in experts, load.get(best, 0))
    except Exception:
        logger.exception("Failed to auto-assign ticket %s", ticket_id)
        return ""
    return best


def process_ticket(
    subject: str,
    description: str,
    submitter: str = "Unknown",
    submitter_email: str = "",
    ticket_id: str | None = None,
) -> PipelineResult:
    """Process a single ticket through the full AI pipeline."""
    init_database()
    start_time = datetime.now()

    if not ticket_id:
        ticket_id = next_ticket_id()

    classification = classify_ticket(subject, description, submitter)
    routing = route_ticket(classification)

    # Check escalation rules for low-confidence or high-urgency tickets that the
    # router didn't already escalate (router only handles urgency=="critical").
    if routing.action not in (RoutingAction.HR_EXCLUDED, RoutingAction.ESCALATE):
        needs_escalation, esc_reason = should_escalate(
            urgency=classification.urgency,
            category_id=classification.category_id,
            confidence=classification.confidence,
        )
        if needs_escalation and esc_reason in (
            EscalationReason.LOW_CONFIDENCE,
            EscalationReason.URGENCY_HIGH,
        ):
            from config.routing_rules import get_queue_for_category
            queue = get_queue_for_category(classification.category_id)
            routing = RoutingDecision(
                action=RoutingAction.ESCALATE,
                queue=queue,
                reason=f"Escalated by rule: {esc_reason.value}",
                classification=classification,
                requires_approval=False,
            )
            logger.info("Ticket %s escalated: %s", ticket_id, esc_reason.value)

    response = None
    if routing.action not in (RoutingAction.HR_EXCLUDED, RoutingAction.ESCALATE):
        response = generate_ticket_response(classification, routing, subject, description)

    approval = None
    if response and (response.requires_approval or routing.action == RoutingAction.INSTANT_RESOLVE):
        approval = create_approval(
            ticket_id=ticket_id,
            category=classification.category_id,
            confidence=classification.confidence,
            response=response.response_text,
            queue=routing.queue,
        )

    similar = find_similar_tickets(subject, description, exclude_ticket_id=ticket_id, top_k=3)
    resolution = generate_resolution(
        subject=subject,
        description=description,
        category=classification.category_id,
        similar_tickets=similar,
    )

    processing_time = (datetime.now() - start_time).total_seconds() * 1000

    initial_status = (
        "PendingApproval"
        if response and (response.requires_approval or routing.action == RoutingAction.INSTANT_RESOLVE)
        else "Open"
    )

    result = PipelineResult(
        ticket_id=ticket_id,
        subject=subject,
        description=description,
        submitter=submitter,
        classification=classification,
        routing=routing,
        response=response,
        approval=approval,
        submitter_email=submitter_email,
        status=initial_status,
        ai_resolution=resolution.proposed_resolution,
        similar_ticket_ids=resolution.similar_ticket_ids,
        processing_time_ms=processing_time,
    )

    _save_pipeline_result(result)

    if routing.action in (RoutingAction.ROUTE_TO_HUMAN, RoutingAction.SUGGEST_REVIEW):
        assigned = _auto_assign_engineer(ticket_id, classification.category_id)
        if assigned:
            result.assigned_to = assigned
            result.status = "Assigned"

    record_metric(
        TicketMetric(
            ticket_id=ticket_id,
            created_at=start_time,
            first_response_at=datetime.now() if response else None,
            resolved_at=None,
            category=classification.category_id,
            queue=routing.queue,
            was_auto_resolved=False,
        )
    )
    return result


def get_processed_tickets() -> list[PipelineResult]:
    init_database()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM tickets ORDER BY processed_at ASC"
        ).fetchall()
    return [_load_pipeline_result(row) for row in rows]


def get_pipeline_stats() -> dict:
    """Get summary statistics for all processed tickets."""
    tickets = get_processed_tickets()
    total = len(tickets)
    if total == 0:
        return {"total": 0}

    auto_resolved = sum(
        1 for t in tickets if t.routing.action in (RoutingAction.AUTO_RESOLVE, RoutingAction.INSTANT_RESOLVE)
    )
    suggested = sum(1 for t in tickets if t.routing.action == RoutingAction.SUGGEST_REVIEW)
    routed = sum(1 for t in tickets if t.routing.action == RoutingAction.ROUTE_TO_HUMAN)
    hr_excluded = sum(1 for t in tickets if t.routing.action == RoutingAction.HR_EXCLUDED)
    escalated = sum(1 for t in tickets if t.routing.action == RoutingAction.ESCALATE)
    pending_approval = sum(
        1 for t in tickets if t.approval is not None and str(t.approval.status.value) == "pending_approval"
    )
    ai_drafted = auto_resolved + suggested

    avg_confidence = sum(t.classification.confidence for t in tickets) / total
    avg_processing_ms = sum(t.processing_time_ms for t in tickets) / total

    categories = {}
    for t in tickets:
        cat = t.classification.category_id
        categories[cat] = categories.get(cat, 0) + 1

    languages = {}
    for t in tickets:
        lang = t.classification.language
        languages[lang] = languages.get(lang, 0) + 1

    queues = {}
    for t in tickets:
        q = t.routing.queue
        queues[q] = queues.get(q, 0) + 1

    return {
        "total": total,
        "auto_resolved": auto_resolved,
        "auto_resolve_rate": auto_resolved / total if total > 0 else 0,
        "ai_drafted": ai_drafted,
        "ai_draft_rate": ai_drafted / total if total > 0 else 0,
        "suggested_review": suggested,
        "pending_approval": pending_approval,
        "routed_to_human": routed,
        "hr_excluded": hr_excluded,
        "escalated": escalated,
        "avg_confidence": avg_confidence,
        "avg_processing_ms": avg_processing_ms,
        "categories": categories,
        "languages": languages,
        "queues": queues,
    }
