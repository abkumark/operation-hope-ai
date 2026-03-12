"""Mock Dynamics 365 API backed by SQLite for demo mode."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.storage.sqlite_db import get_connection, init_database


@dataclass
class Case:
    """Dynamics 365 case representation."""

    case_id: str
    ticket_number: str
    title: str
    description: str
    origin: str  # email, portal, phone
    customer_name: str
    customer_email: str
    status: str  # active, resolved, cancelled
    queue: str
    ai_category: str = ""
    ai_confidence: float = 0.0
    ai_response: str = ""
    ai_action: str = ""
    created_on: datetime = field(default_factory=datetime.now)
    modified_on: datetime = field(default_factory=datetime.now)


def _row_to_case(row) -> Case:
    return Case(
        case_id=row["case_id"],
        ticket_number=row["ticket_number"],
        title=row["title"],
        description=row["description"],
        origin=row["origin"],
        customer_name=row["customer_name"],
        customer_email=row["customer_email"],
        status=row["status"],
        queue=row["queue"],
        ai_category=row["ai_category"],
        ai_confidence=float(row["ai_confidence"]),
        ai_response=row["ai_response"],
        ai_action=row["ai_action"],
        created_on=datetime.fromisoformat(row["created_on"]),
        modified_on=datetime.fromisoformat(row["modified_on"]),
    )


def _next_ticket_number() -> str:
    """Generate next ticket number."""
    init_database()
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM mock_cases").fetchone()
    count = 0 if row is None else int(row["count"])
    return f"CASE-{datetime.now().strftime('%Y%m%d')}-{count + 1:04d}"


def create_case(
    title: str,
    description: str,
    origin: str = "email",
    customer_name: str = "",
    customer_email: str = "",
    queue: str = "IT Support",
) -> Case:
    """Create a new case in mock storage."""
    init_database()
    case_id = str(uuid.uuid4())
    ticket_number = _next_ticket_number()
    case = Case(
        case_id=case_id,
        ticket_number=ticket_number,
        title=title,
        description=description,
        origin=origin,
        customer_name=customer_name,
        customer_email=customer_email,
        status="active",
        queue=queue,
        created_on=datetime.now(),
        modified_on=datetime.now(),
    )
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO mock_cases (
                case_id, ticket_number, title, description, origin,
                customer_name, customer_email, status, queue,
                ai_category, ai_confidence, ai_response, ai_action,
                created_on, modified_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case.case_id,
                case.ticket_number,
                case.title,
                case.description,
                case.origin,
                case.customer_name,
                case.customer_email,
                case.status,
                case.queue,
                case.ai_category,
                case.ai_confidence,
                case.ai_response,
                case.ai_action,
                case.created_on.isoformat(),
                case.modified_on.isoformat(),
            ),
        )
    return case


def update_case(
    case_id: str,
    *,
    status: Optional[str] = None,
    queue: Optional[str] = None,
    ai_category: Optional[str] = None,
    ai_confidence: Optional[float] = None,
    ai_response: Optional[str] = None,
    ai_action: Optional[str] = None,
) -> Optional[Case]:
    """Update an existing case."""
    case = get_case(case_id)
    if not case:
        return None

    if status is not None:
        case.status = status
    if queue is not None:
        case.queue = queue
    if ai_category is not None:
        case.ai_category = ai_category
    if ai_confidence is not None:
        case.ai_confidence = ai_confidence
    if ai_response is not None:
        case.ai_response = ai_response
    if ai_action is not None:
        case.ai_action = ai_action

    case.modified_on = datetime.now()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE mock_cases
            SET status = ?, queue = ?, ai_category = ?, ai_confidence = ?,
                ai_response = ?, ai_action = ?, modified_on = ?
            WHERE case_id = ?
            """,
            (
                case.status,
                case.queue,
                case.ai_category,
                case.ai_confidence,
                case.ai_response,
                case.ai_action,
                case.modified_on.isoformat(),
                case_id,
            ),
        )
    return case


def get_case(case_id: str) -> Optional[Case]:
    """Get a case by ID."""
    init_database()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM mock_cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()
    return _row_to_case(row) if row else None


def list_cases(
    status: Optional[str] = None,
    queue: Optional[str] = None,
    limit: int = 100,
) -> list[Case]:
    """List cases with optional filters."""
    init_database()
    query = "SELECT * FROM mock_cases WHERE 1 = 1"
    params: list[object] = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if queue:
        query += " AND queue = ?"
        params.append(queue)
    query += " ORDER BY created_on DESC LIMIT ?"
    params.append(limit)
    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_row_to_case(row) for row in rows]


def get_case_by_ticket_id(ticket_number: str) -> Optional[Case]:
    """Get a case by ticket number."""
    init_database()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM mock_cases WHERE ticket_number = ?",
            (ticket_number,),
        ).fetchone()
    return _row_to_case(row) if row else None


def clear_mock_store() -> None:
    """Clear persisted mock cases (for testing)."""
    init_database()
    with get_connection() as connection:
        connection.execute("DELETE FROM mock_cases")
