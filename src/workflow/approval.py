"""Approval workflow state machine for AI-generated responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.storage.sqlite_db import get_connection, init_database


class ApprovalStatus(str, Enum):
    NEW = "new"
    AI_CLASSIFIED = "ai_classified"
    RESPONSE_GENERATED = "ai_response_generated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    REROUTED = "rerouted"


@dataclass
class ApprovalEvent:
    id: int
    ticket_id: str
    event_type: str
    actor: str
    details: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ApprovalRecord:
    ticket_id: str
    status: ApprovalStatus
    ai_category: str
    ai_confidence: float
    ai_response: str
    assigned_queue: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    reviewed_by: str = ""
    reviewer_notes: str = ""
    final_response: str = ""

    def approve(self, reviewer: str, final_response: str | None = None):
        self.status = ApprovalStatus.APPROVED
        self.reviewed_by = reviewer
        self.final_response = final_response or self.ai_response
        self.updated_at = datetime.now()

    def reject(self, reviewer: str, notes: str = ""):
        self.status = ApprovalStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewer_notes = notes
        self.updated_at = datetime.now()

    def mark_sent(self):
        self.status = ApprovalStatus.SENT
        self.updated_at = datetime.now()

    def reroute(self, new_queue: str, reviewer: str, notes: str = ""):
        self.status = ApprovalStatus.REROUTED
        self.assigned_queue = new_queue
        self.reviewed_by = reviewer
        self.reviewer_notes = notes
        self.updated_at = datetime.now()


def _save_approval(record: ApprovalRecord) -> None:
    init_database()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO approvals (
                ticket_id, status, ai_category, ai_confidence, ai_response,
                assigned_queue, created_at, updated_at, reviewed_by,
                reviewer_notes, final_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.ticket_id,
                record.status.value,
                record.ai_category,
                record.ai_confidence,
                record.ai_response,
                record.assigned_queue,
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
                record.reviewed_by,
                record.reviewer_notes,
                record.final_response,
            ),
        )


def _save_approval_event(ticket_id: str, event_type: str, actor: str, details: str) -> None:
    init_database()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO approval_events (ticket_id, event_type, actor, details, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ticket_id, event_type, actor, details, datetime.now().isoformat()),
        )


def _row_to_approval(row) -> ApprovalRecord:
    return ApprovalRecord(
        ticket_id=row["ticket_id"],
        status=ApprovalStatus(row["status"]),
        ai_category=row["ai_category"],
        ai_confidence=float(row["ai_confidence"]),
        ai_response=row["ai_response"],
        assigned_queue=row["assigned_queue"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        reviewed_by=row["reviewed_by"],
        reviewer_notes=row["reviewer_notes"],
        final_response=row["final_response"],
    )


def _row_to_event(row) -> ApprovalEvent:
    return ApprovalEvent(
        id=int(row["id"]),
        ticket_id=row["ticket_id"],
        event_type=row["event_type"],
        actor=row["actor"],
        details=row["details"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def create_approval(
    ticket_id: str,
    category: str,
    confidence: float,
    response: str,
    queue: str,
) -> ApprovalRecord:
    init_database()
    record = ApprovalRecord(
        ticket_id=ticket_id,
        status=ApprovalStatus.PENDING_APPROVAL,
        ai_category=category,
        ai_confidence=confidence,
        ai_response=response,
        assigned_queue=queue,
    )
    _save_approval(record)
    _save_approval_event(
        ticket_id=ticket_id,
        event_type="created",
        actor="system",
        details=f"AI draft created for queue {queue} with confidence {confidence:.0%}.",
    )
    return record


def get_approval(ticket_id: str) -> ApprovalRecord | None:
    init_database()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM approvals WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
    return _row_to_approval(row) if row else None


def get_pending_approvals() -> list[ApprovalRecord]:
    init_database()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM approvals WHERE status = ? ORDER BY created_at DESC",
            (ApprovalStatus.PENDING_APPROVAL.value,),
        ).fetchall()
    return [_row_to_approval(row) for row in rows]


def get_all_approvals() -> list[ApprovalRecord]:
    init_database()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM approvals ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_approval(row) for row in rows]


def get_approval_history(ticket_id: str) -> list[ApprovalEvent]:
    init_database()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM approval_events WHERE ticket_id = ? ORDER BY created_at ASC, id ASC",
            (ticket_id,),
        ).fetchall()
    return [_row_to_event(row) for row in rows]


def approve_approval(
    ticket_id: str,
    reviewer: str,
    final_response: str | None = None,
    mark_sent: bool = True,
) -> ApprovalRecord | None:
    record = get_approval(ticket_id)
    if record is None:
        return None
    record.approve(reviewer=reviewer, final_response=final_response)
    _save_approval_event(
        ticket_id=ticket_id,
        event_type="approved",
        actor=reviewer,
        details="Draft approved by reviewer.",
    )
    if mark_sent:
        record.mark_sent()
        _save_approval_event(
            ticket_id=ticket_id,
            event_type="sent",
            actor=reviewer,
            details="Approved response marked as sent.",
        )
    _save_approval(record)
    return record


def reject_approval(ticket_id: str, reviewer: str, notes: str = "") -> ApprovalRecord | None:
    record = get_approval(ticket_id)
    if record is None:
        return None
    record.reject(reviewer=reviewer, notes=notes)
    _save_approval(record)
    _save_approval_event(
        ticket_id=ticket_id,
        event_type="rejected",
        actor=reviewer,
        details=notes or "Draft rejected by reviewer.",
    )
    return record


def reroute_approval(
    ticket_id: str,
    reviewer: str,
    new_queue: str,
    notes: str = "",
) -> ApprovalRecord | None:
    record = get_approval(ticket_id)
    if record is None:
        return None
    record.reroute(new_queue=new_queue, reviewer=reviewer, notes=notes)
    _save_approval(record)
    _save_approval_event(
        ticket_id=ticket_id,
        event_type="rerouted",
        actor=reviewer,
        details=notes or f"Draft rerouted to {new_queue}.",
    )
    return record
