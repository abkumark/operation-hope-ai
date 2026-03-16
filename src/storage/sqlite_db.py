"""SQLite persistence for tickets, approvals, metrics, and demo cases."""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from config.settings import get_settings

logger = logging.getLogger(__name__)

# ── Thread-safe connection pool (one connection per thread) ──────────────
_local = threading.local()


def _db_path() -> Path:
    settings = get_settings()
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_connection() -> sqlite3.Connection:
    """Return a thread-local SQLite connection with WAL mode enabled."""
    conn = getattr(_local, "connection", None)
    db = _db_path()
    # Re-use connection if same DB path and still open
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            if getattr(_local, "db_path", None) == str(db):
                return conn
        except Exception:
            pass  # stale connection, recreate
    connection = sqlite3.connect(str(db), check_same_thread=False, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    _local.connection = connection
    _local.db_path = str(db)
    return connection


def close_connection() -> None:
    """Explicitly close the thread-local connection (call at shutdown)."""
    conn = getattr(_local, "connection", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _local.connection = None


def _migrate_tickets_table(connection: sqlite3.Connection) -> None:
    """Add columns that may be missing in databases created before the migration."""
    cursor = connection.execute("PRAGMA table_info(tickets)")
    existing_columns = {row["name"] for row in cursor.fetchall()}
    migrations = {
        "submitter_email": "ALTER TABLE tickets ADD COLUMN submitter_email TEXT NOT NULL DEFAULT ''",
        "status": "ALTER TABLE tickets ADD COLUMN status TEXT NOT NULL DEFAULT 'Open'",
        "ai_resolution": "ALTER TABLE tickets ADD COLUMN ai_resolution TEXT NOT NULL DEFAULT ''",
        "similar_ticket_ids": "ALTER TABLE tickets ADD COLUMN similar_ticket_ids TEXT NOT NULL DEFAULT '[]'",
        "assigned_to": "ALTER TABLE tickets ADD COLUMN assigned_to TEXT NOT NULL DEFAULT ''",
        "phone_number": "ALTER TABLE tickets ADD COLUMN phone_number TEXT NOT NULL DEFAULT ''",
        "created_at": "ALTER TABLE tickets ADD COLUMN created_at TEXT NOT NULL DEFAULT ''",
        "updated_at": "ALTER TABLE tickets ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''",
    }
    for col, sql in migrations.items():
        if col not in existing_columns:
            connection.execute(sql)


def init_database() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS ticket_sequence (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                next_value INTEGER NOT NULL
            );

            INSERT OR IGNORE INTO ticket_sequence (id, next_value) VALUES (1, 1);

            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                submitter TEXT NOT NULL,
                submitter_email TEXT NOT NULL DEFAULT '',
                phone_number TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Open',
                ai_resolution TEXT NOT NULL DEFAULT '',
                similar_ticket_ids TEXT NOT NULL DEFAULT '[]',
                assigned_to TEXT NOT NULL DEFAULT '',
                classification_json TEXT NOT NULL,
                routing_json TEXT NOT NULL,
                response_json TEXT,
                processed_at TEXT NOT NULL,
                processing_time_ms REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS approvals (
                ticket_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                ai_category TEXT NOT NULL,
                ai_confidence REAL NOT NULL,
                ai_response TEXT NOT NULL,
                assigned_queue TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                reviewed_by TEXT NOT NULL,
                reviewer_notes TEXT NOT NULL,
                final_response TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS approval_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS metrics (
                ticket_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                first_response_at TEXT,
                resolved_at TEXT,
                category TEXT NOT NULL,
                queue TEXT NOT NULL,
                was_auto_resolved INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mock_cases (
                case_id TEXT PRIMARY KEY,
                ticket_number TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                origin TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                status TEXT NOT NULL,
                queue TEXT NOT NULL,
                ai_category TEXT NOT NULL,
                ai_confidence REAL NOT NULL,
                ai_response TEXT NOT NULL,
                ai_action TEXT NOT NULL,
                created_on TEXT NOT NULL,
                modified_on TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                body_preview TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                sent_at TEXT,
                error_message TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS engineer_expertise (
                engineer_username TEXT NOT NULL,
                category_id TEXT NOT NULL,
                PRIMARY KEY (engineer_username, category_id)
            );

            CREATE TABLE IF NOT EXISTS kb_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                created_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                published_at TEXT
            );

            CREATE TABLE IF NOT EXISTS resolution_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                submitter_email TEXT NOT NULL DEFAULT '',
                helpful INTEGER NOT NULL,
                comment TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            -- Performance indexes
            CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
            CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to ON tickets(assigned_to);
            CREATE INDEX IF NOT EXISTS idx_tickets_processed_at ON tickets(processed_at);
            CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
            CREATE INDEX IF NOT EXISTS idx_email_notifications_ticket ON email_notifications(ticket_id);
            CREATE INDEX IF NOT EXISTS idx_approval_events_ticket ON approval_events(ticket_id);
            CREATE INDEX IF NOT EXISTS idx_metrics_category ON metrics(category);
            CREATE INDEX IF NOT EXISTS idx_resolution_feedback_ticket ON resolution_feedback(ticket_id);
            """
        )
        # Run migrations BEFORE creating indexes on migrated columns
        _migrate_tickets_table(connection)
        # Now safe to create indexes on columns added by migration
        connection.executescript("""
            CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);
            CREATE INDEX IF NOT EXISTS idx_tickets_updated_at ON tickets(updated_at);
        """)


def next_ticket_id() -> str:
    init_database()
    with get_connection() as connection:
        cursor = connection.execute("SELECT next_value FROM ticket_sequence WHERE id = 1")
        row = cursor.fetchone()
        next_value = 1 if row is None else int(row["next_value"])
        connection.execute(
            "UPDATE ticket_sequence SET next_value = ? WHERE id = 1",
            (next_value + 1,),
        )
    return f"HOPE-{next_value:05d}"


def create_placeholder_ticket(
    ticket_id: str,
    subject: str,
    description: str,
    submitter: str,
    submitter_email: str = "",
    phone_number: str = "",
) -> None:
    """Insert a minimal ticket row so the ID is reserved and visible immediately.

    The AI pipeline will overwrite this row via INSERT OR REPLACE once complete.
    """
    from datetime import datetime

    init_database()
    placeholder_classification = '{"category_id":"pending","category_name":"Processing…","confidence":0,"language":"en","sentiment":"neutral","urgency":"medium","is_hr":false,"summary":"","raw_text":""}'
    placeholder_routing = '{"action":"pending","queue":"","reason":"AI processing in progress","requires_approval":false}'
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO tickets (
                ticket_id, subject, description, submitter, submitter_email, phone_number,
                status, ai_resolution, similar_ticket_ids, assigned_to,
                classification_json, routing_json, response_json,
                processed_at, processing_time_ms, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'Processing', '', '[]', '', ?, ?, NULL, ?, 0, ?, ?)
            """,
            (
                ticket_id,
                subject,
                description,
                submitter,
                submitter_email,
                phone_number,
                placeholder_classification,
                placeholder_routing,
                now,
                now,
                now,
            ),
        )


def delete_ticket(ticket_id: str) -> bool:
    """Delete a ticket and all associated records. Returns True if the ticket existed."""
    init_database()
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM tickets WHERE ticket_id = ?", (ticket_id,))
        conn.execute("DELETE FROM approvals WHERE ticket_id = ?", (ticket_id,))
        conn.execute("DELETE FROM approval_events WHERE ticket_id = ?", (ticket_id,))
        conn.execute("DELETE FROM metrics WHERE ticket_id = ?", (ticket_id,))
        conn.execute("DELETE FROM email_notifications WHERE ticket_id = ?", (ticket_id,))
    return cursor.rowcount > 0


def update_ticket_fields(ticket_id: str, **fields: str) -> bool:
    """Update arbitrary text fields on a ticket row. Returns True if the ticket existed.

    Only whitelisted column names are allowed to prevent SQL injection.
    Automatically sets updated_at to the current timestamp on every call.
    """
    from datetime import datetime

    _ALLOWED_COLUMNS = {
        "subject", "description", "submitter", "submitter_email", "phone_number",
        "status", "ai_resolution", "similar_ticket_ids", "assigned_to",
        "classification_json", "routing_json", "response_json",
        "created_at", "updated_at",
    }
    if not fields:
        return False
    # Validate column names against whitelist
    invalid_cols = set(fields.keys()) - _ALLOWED_COLUMNS
    if invalid_cols:
        raise ValueError(f"Invalid column names: {invalid_cols}. Allowed: {_ALLOWED_COLUMNS}")

    # Always update the updated_at timestamp on any field change
    fields["updated_at"] = datetime.now().isoformat()

    init_database()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [ticket_id]
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE tickets SET {set_clause} WHERE ticket_id = ?",  # noqa: S608
            values,
        )
    return cursor.rowcount > 0


def get_ticket_by_id(ticket_id: str) -> sqlite3.Row | None:
    """Fetch a single ticket row by ID using an indexed lookup (O(1) vs O(n))."""
    init_database()
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()


def get_tickets_by_status(statuses: list[str]) -> list[sqlite3.Row]:
    """Fetch tickets matching any of the given statuses."""
    init_database()
    if not statuses:
        return []
    placeholders = ", ".join("?" for _ in statuses)
    with get_connection() as conn:
        return conn.execute(
            f"SELECT * FROM tickets WHERE status IN ({placeholders}) ORDER BY processed_at ASC",
            statuses,
        ).fetchall()


def get_tickets_paginated(
    offset: int = 0,
    limit: int = 50,
    status: str | None = None,
    assigned_to: str | None = None,
) -> tuple[list[sqlite3.Row], int]:
    """Return paginated tickets with optional filters. Returns (rows, total_count)."""
    init_database()
    conditions = []
    params: list = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if assigned_to:
        conditions.append("assigned_to = ?")
        params.append(assigned_to)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with get_connection() as conn:
        count_row = conn.execute(f"SELECT COUNT(*) AS cnt FROM tickets {where}", params).fetchone()
        total = count_row["cnt"] if count_row else 0
        rows = conn.execute(
            f"SELECT * FROM tickets {where} ORDER BY processed_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    return rows, total


def cleanup_stuck_tickets(max_age_minutes: int = 30) -> int:
    """Reset tickets stuck in 'Processing' state for longer than max_age_minutes.

    Returns the number of tickets cleaned up. Called at startup.
    """
    from datetime import datetime, timedelta

    init_database()
    cutoff = (datetime.now() - timedelta(minutes=max_age_minutes)).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE tickets SET status = 'Open' WHERE status = 'Processing' AND processed_at < ?",
            (cutoff,),
        )
    count = cursor.rowcount
    if count > 0:
        logger.warning("Cleaned up %d stuck 'Processing' tickets (older than %d min)", count, max_age_minutes)
    return count


def get_engineer_expertise() -> dict[str, list[str]]:
    """Return {engineer_username: [category_id, ...]} mapping."""
    init_database()
    with get_connection() as conn:
        rows = conn.execute("SELECT engineer_username, category_id FROM engineer_expertise").fetchall()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["engineer_username"], []).append(row["category_id"])
    return result


def set_engineer_expertise(engineer_username: str, category_ids: list[str]) -> None:
    """Replace the expertise list for a given engineer."""
    init_database()
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM engineer_expertise WHERE engineer_username = ?",
            (engineer_username,),
        )
        for cid in category_ids:
            conn.execute(
                "INSERT INTO engineer_expertise (engineer_username, category_id) VALUES (?, ?)",
                (engineer_username, cid),
            )


def get_expertise_for_category(category_id: str) -> list[str]:
    """Return list of engineer usernames tagged as experts for a category."""
    init_database()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT engineer_username FROM engineer_expertise WHERE category_id = ?",
            (category_id,),
        ).fetchall()
    return [row["engineer_username"] for row in rows]


def create_kb_draft(
    ticket_id: str, title: str, category: str, content: str, created_by: str = ""
) -> int:
    """Create a KB draft from a resolved ticket. Returns the draft ID."""
    from datetime import datetime

    init_database()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO kb_drafts (ticket_id, title, category, content, status, created_by, created_at) "
            "VALUES (?, ?, ?, ?, 'draft', ?, ?)",
            (ticket_id, title, category, content, created_by, datetime.now().isoformat()),
        )
    return cursor.lastrowid


def list_kb_drafts(status: str | None = None) -> list[dict]:
    """Return all KB drafts, optionally filtered by status."""
    init_database()
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM kb_drafts WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM kb_drafts ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def get_kb_draft(draft_id: int) -> dict | None:
    """Return a single KB draft by ID."""
    init_database()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM kb_drafts WHERE id = ?", (draft_id,)).fetchone()
    return dict(row) if row else None


def publish_kb_draft(draft_id: int) -> bool:
    """Mark a draft as published. Returns True if the draft existed."""
    from datetime import datetime

    init_database()
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE kb_drafts SET status = 'published', published_at = ? WHERE id = ? AND status = 'draft'",
            (datetime.now().isoformat(), draft_id),
        )
    return cursor.rowcount > 0


def delete_kb_draft(draft_id: int) -> bool:
    """Delete a KB draft. Returns True if the draft existed."""
    init_database()
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM kb_drafts WHERE id = ?", (draft_id,))
    return cursor.rowcount > 0


def submit_resolution_feedback(
    ticket_id: str,
    helpful: bool,
    comment: str = "",
    submitter_email: str = "",
) -> int:
    """Record resolution feedback from a submitter. Returns the feedback ID."""
    from datetime import datetime

    init_database()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO resolution_feedback (ticket_id, submitter_email, helpful, comment, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (ticket_id, submitter_email, int(helpful), comment, datetime.now().isoformat()),
        )
    return cursor.lastrowid


def get_feedback_for_ticket(ticket_id: str) -> list[dict]:
    """Return all feedback entries for a given ticket."""
    init_database()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM resolution_feedback WHERE ticket_id = ? ORDER BY created_at DESC",
            (ticket_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_feedback_summary() -> dict:
    """Return aggregate feedback stats for analytics."""
    init_database()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN helpful = 1 THEN 1 ELSE 0 END) AS helpful_count, "
            "SUM(CASE WHEN helpful = 0 THEN 1 ELSE 0 END) AS unhelpful_count "
            "FROM resolution_feedback"
        ).fetchone()
    total = row["total"] or 0
    helpful_count = row["helpful_count"] or 0
    return {
        "total": total,
        "helpful": helpful_count,
        "unhelpful": row["unhelpful_count"] or 0,
        "satisfaction_rate": round(helpful_count / total, 2) if total else 0.0,
    }


def get_feedback_by_category() -> list[dict]:
    """Return feedback stats grouped by ticket category."""
    init_database()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT t.classification_json, "
            "COUNT(*) AS total, "
            "SUM(CASE WHEN rf.helpful = 1 THEN 1 ELSE 0 END) AS helpful "
            "FROM resolution_feedback rf "
            "JOIN tickets t ON rf.ticket_id = t.ticket_id "
            "GROUP BY json_extract(t.classification_json, '$.category_id')"
        ).fetchall()
    import json
    results = []
    for r in rows:
        try:
            cls = json.loads(r["classification_json"])
        except (json.JSONDecodeError, TypeError):
            cls = {}
        total = r["total"] or 0
        helpful = r["helpful"] or 0
        results.append({
            "category_id": cls.get("category_id", "unknown"),
            "category_name": cls.get("category_name", cls.get("category_id", "unknown")),
            "total_feedback": total,
            "helpful": helpful,
            "unhelpful": total - helpful,
            "satisfaction_rate": round(helpful / total, 2) if total else 0.0,
        })
    return sorted(results, key=lambda x: x["total_feedback"], reverse=True)


def get_stale_tickets(max_hours_since_update: float = 24.0) -> list[sqlite3.Row]:
    """Return tickets that have had NO edits for `max_hours_since_update` hours.

    Only considers tickets in active statuses (not already Completed/Escalated/HR).
    Uses the `updated_at` column — if it's empty, falls back to `created_at` or `processed_at`.
    """
    from datetime import datetime, timedelta

    init_database()
    cutoff = (datetime.now() - timedelta(hours=max_hours_since_update)).isoformat()
    active_statuses = ("Open", "Assigned", "WorkInProgress", "Processing")
    placeholders = ", ".join("?" for _ in active_statuses)

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM tickets
            WHERE status IN ({placeholders})
              AND COALESCE(NULLIF(updated_at, ''), NULLIF(created_at, ''), processed_at) < ?
            ORDER BY processed_at ASC
            """,
            list(active_statuses) + [cutoff],
        ).fetchall()
    return rows


def backfill_timestamps() -> int:
    """Backfill created_at and updated_at for tickets that don't have them.

    Uses processed_at as the fallback. Called once at startup.
    Returns the number of tickets backfilled.
    """
    init_database()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE tickets
            SET created_at = processed_at,
                updated_at = processed_at
            WHERE (created_at IS NULL OR created_at = '')
               AND processed_at IS NOT NULL AND processed_at != ''
            """
        )
    count = cursor.rowcount
    if count > 0:
        logger.info("Backfilled created_at/updated_at for %d existing tickets", count)
    return count


def clear_all_data() -> None:
    init_database()
    with get_connection() as connection:
        connection.execute("DELETE FROM tickets")
        connection.execute("DELETE FROM approvals")
        connection.execute("DELETE FROM approval_events")
        connection.execute("DELETE FROM metrics")
        connection.execute("DELETE FROM mock_cases")
        connection.execute("DELETE FROM resolution_feedback")
        connection.execute("UPDATE ticket_sequence SET next_value = 1 WHERE id = 1")
