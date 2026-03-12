"""KPI and SLA tracking metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.storage.sqlite_db import get_connection, init_database


@dataclass
class SLAConfig:
    """SLA configuration for response time targets."""

    target_response_hours: float = 48.0
    warning_threshold_hours: float = 24.0
    critical_threshold_hours: float = 4.0


@dataclass
class TicketMetric:
    """Metric record for a single ticket."""

    ticket_id: str
    created_at: datetime
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    category: str = ""
    queue: str = ""
    was_auto_resolved: bool = False

    @property
    def response_time_hours(self) -> Optional[float]:
        """Time from creation to first response in hours."""
        if self.first_response_at and self.created_at:
            delta = self.first_response_at - self.created_at
            return delta.total_seconds() / 3600
        return None

    @property
    def resolution_time_hours(self) -> Optional[float]:
        """Time from creation to resolution in hours."""
        if self.resolved_at and self.created_at:
            delta = self.resolved_at - self.created_at
            return delta.total_seconds() / 3600
        return None

    def is_within_sla(self, sla: Optional[SLAConfig] = None) -> bool:
        """Check if ticket met SLA for first response."""
        sla = sla or SLAConfig()
        rt = self.response_time_hours
        return rt is not None and rt <= sla.target_response_hours


def _to_iso(value: Optional[datetime]) -> str | None:
    return value.isoformat() if value else None


def _row_to_metric(row) -> TicketMetric:
    return TicketMetric(
        ticket_id=row["ticket_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        first_response_at=datetime.fromisoformat(row["first_response_at"])
        if row["first_response_at"]
        else None,
        resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        category=row["category"],
        queue=row["queue"],
        was_auto_resolved=bool(row["was_auto_resolved"]),
    )


def record_metric(metric: TicketMetric) -> None:
    """Record a ticket metric."""
    init_database()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO metrics (
                ticket_id, created_at, first_response_at, resolved_at,
                category, queue, was_auto_resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metric.ticket_id,
                metric.created_at.isoformat(),
                _to_iso(metric.first_response_at),
                _to_iso(metric.resolved_at),
                metric.category,
                metric.queue,
                int(metric.was_auto_resolved),
            ),
        )


def mark_ticket_resolved(ticket_id: str, *, was_auto_resolved: bool) -> bool:
    """Mark an existing ticket metric as resolved."""
    init_database()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE metrics
            SET resolved_at = ?, was_auto_resolved = ?
            WHERE ticket_id = ?
            """,
            (
                datetime.now().isoformat(),
                int(was_auto_resolved),
                ticket_id,
            ),
        )
    return cursor.rowcount > 0


def get_all_metrics() -> list[TicketMetric]:
    """Get all recorded metrics."""
    init_database()
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM metrics ORDER BY created_at DESC").fetchall()
    return [_row_to_metric(row) for row in rows]


def get_sla_compliance(sla: Optional[SLAConfig] = None) -> dict:
    """Get SLA compliance statistics."""
    sla = sla or SLAConfig()
    metrics = get_all_metrics()
    if not metrics:
        return {"total": 0, "within_sla": 0, "compliance_rate": 0.0}
    within = sum(1 for m in metrics if m.is_within_sla(sla))
    return {
        "total": len(metrics),
        "within_sla": within,
        "compliance_rate": within / len(metrics),
        "target_hours": sla.target_response_hours,
    }


def get_avg_response_time() -> float:
    """Get average first response time in hours."""
    times = [m.response_time_hours for m in get_all_metrics() if m.response_time_hours is not None]
    return sum(times) / len(times) if times else 0.0
