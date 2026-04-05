"""
Repository Pattern for Secure Database Operations

This module provides secure, type-safe database operations using the
repository pattern to prevent SQL injection and ensure data integrity.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from abc import ABC, abstractmethod

from .connection import get_connection, transaction, execute_query
from .models import (
    TicketModel,
    ApprovalModel,
    ApprovalEventModel,
    MetricsModel,
    EmailNotificationModel,
    AuditLogModel,
    TicketStatus,
    ApprovalStatus,
    NotificationStatus
)
from security.validation import validate_sql_identifier, ValidationError

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Repository operation error."""
    pass


class BaseRepository(ABC):
    """Base repository with common operations."""

    def __init__(self):
        """Initialize repository."""
        pass

    def _validate_id(self, entity_id: str, field_name: str = "id") -> str:
        """Validate entity ID format."""
        if not entity_id or not entity_id.strip():
            raise ValidationError(f"{field_name} cannot be empty")

        # Basic validation for ticket IDs
        if field_name == "ticket_id" and not entity_id.startswith("HOPE-"):
            raise ValidationError("Invalid ticket ID format")

        return entity_id.strip()

    def _log_audit(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: str = "",
        ip_address: str = "",
        user_agent: str = ""
    ) -> None:
        """Log audit trail for security."""
        try:
            audit_log = AuditLogModel(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                created_at=datetime.now()
            )

            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_log
                    (user_id, action, resource_type, resource_id, details, ip_address, user_agent, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(audit_log.to_db_dict().values())
                )

        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")


class TicketRepository(BaseRepository):
    """Repository for ticket operations with security and validation."""

    def generate_ticket_id(self) -> str:
        """Generate next ticket ID atomically."""
        try:
            with transaction() as conn:
                # Atomic increment
                cursor = conn.execute(
                    "UPDATE ticket_sequence SET next_value = next_value + 1 WHERE id = 1"
                )

                if cursor.rowcount == 0:
                    # Initialize if missing
                    conn.execute(
                        "INSERT OR IGNORE INTO ticket_sequence (id, next_value) VALUES (1, 2)"
                    )
                    next_value = 1
                else:
                    row = conn.execute(
                        "SELECT next_value FROM ticket_sequence WHERE id = 1"
                    ).fetchone()
                    next_value = int(row["next_value"]) - 1

                ticket_id = f"HOPE-{next_value:05d}"
                logger.debug(f"Generated ticket ID: {ticket_id}")
                return ticket_id

        except Exception as e:
            logger.error(f"Failed to generate ticket ID: {e}")
            raise RepositoryError("Failed to generate ticket ID")

    def create_ticket(self, ticket: TicketModel, user_id: str = "system") -> TicketModel:
        """
        Create a new ticket with validation.

        Args:
            ticket: Ticket model to create
            user_id: User creating the ticket for audit

        Returns:
            Created ticket model

        Raises:
            RepositoryError: If creation fails
            ValidationError: If ticket data is invalid
        """
        try:
            # Validate ticket data
            ticket_data = ticket.to_db_dict()

            with transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO tickets (
                        ticket_id, subject, description, submitter, submitter_email, phone_number,
                        status, ai_resolution, similar_ticket_ids, assigned_to,
                        classification_json, routing_json, response_json,
                        processed_at, processing_time_ms, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ticket_data['ticket_id'], ticket_data['subject'], ticket_data['description'],
                        ticket_data['submitter'], ticket_data['submitter_email'], ticket_data['phone_number'],
                        ticket_data['status'], ticket_data['ai_resolution'], ticket_data['similar_ticket_ids'],
                        ticket_data['assigned_to'], ticket_data['classification_json'], ticket_data['routing_json'],
                        ticket_data.get('response_json'), ticket_data['processed_at'], ticket_data['processing_time_ms'],
                        ticket_data['created_at'], ticket_data['updated_at']
                    )
                )

                # Log audit trail
                self._log_audit(
                    user_id=user_id,
                    action="create",
                    resource_type="ticket",
                    resource_id=ticket.ticket_id,
                    details=f"Created ticket: {ticket.subject}"
                )

                logger.info(f"Created ticket {ticket.ticket_id} by user {user_id}")
                return ticket

        except Exception as e:
            logger.error(f"Failed to create ticket {ticket.ticket_id}: {e}")
            raise RepositoryError(f"Failed to create ticket: {e}")

    def get_ticket_by_id(self, ticket_id: str) -> Optional[TicketModel]:
        """
        Get ticket by ID with validation.

        Args:
            ticket_id: Ticket ID to retrieve

        Returns:
            Ticket model if found, None otherwise

        Raises:
            ValidationError: If ticket ID is invalid
        """
        ticket_id = self._validate_id(ticket_id, "ticket_id")

        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM tickets WHERE ticket_id = ?",
                    (ticket_id,)
                ).fetchone()

                if row:
                    return TicketModel.from_db_row(row)
                return None

        except Exception as e:
            logger.error(f"Failed to get ticket {ticket_id}: {e}")
            raise RepositoryError(f"Failed to get ticket: {e}")

    def update_ticket(
        self,
        ticket_id: str,
        updates: Dict[str, Any],
        user_id: str = "system"
    ) -> bool:
        """
        Update ticket with validated fields.

        Args:
            ticket_id: Ticket ID to update
            updates: Dictionary of field updates
            user_id: User making the update for audit

        Returns:
            True if ticket was updated, False if not found

        Raises:
            RepositoryError: If update fails
            ValidationError: If field names or values are invalid
        """
        ticket_id = self._validate_id(ticket_id, "ticket_id")

        # Whitelist of allowed update fields
        allowed_fields = {
            'subject', 'description', 'submitter', 'submitter_email', 'phone_number',
            'status', 'ai_resolution', 'similar_ticket_ids', 'assigned_to',
            'classification_json', 'routing_json', 'response_json'
        }

        if not updates:
            raise ValidationError("No updates provided")

        # Validate field names
        invalid_fields = set(updates.keys()) - allowed_fields
        if invalid_fields:
            raise ValidationError(f"Invalid fields: {invalid_fields}")

        try:
            with transaction() as conn:
                # Prepare update data
                update_data = dict(updates)

                # Convert lists/dicts to JSON for storage
                for field in ['similar_ticket_ids', 'classification_json', 'routing_json', 'response_json']:
                    if field in update_data and isinstance(update_data[field], (list, dict)):
                        update_data[field] = json.dumps(update_data[field])

                # Always update timestamp
                update_data['updated_at'] = datetime.now().isoformat()

                # Build dynamic query with validated fields
                set_clauses = []
                values = []

                for field, value in update_data.items():
                    # Validate field name (redundant but belt-and-suspenders)
                    validate_sql_identifier(field)
                    set_clauses.append(f"{field} = ?")
                    values.append(value)

                values.append(ticket_id)

                query = f"UPDATE tickets SET {', '.join(set_clauses)} WHERE ticket_id = ?"

                cursor = conn.execute(query, values)
                updated = cursor.rowcount > 0

                if updated:
                    # Log audit trail
                    details = f"Updated fields: {', '.join(updates.keys())}"
                    self._log_audit(
                        user_id=user_id,
                        action="update",
                        resource_type="ticket",
                        resource_id=ticket_id,
                        details=details
                    )

                    logger.info(f"Updated ticket {ticket_id} by user {user_id}")

                return updated

        except Exception as e:
            logger.error(f"Failed to update ticket {ticket_id}: {e}")
            raise RepositoryError(f"Failed to update ticket: {e}")

    def delete_ticket(self, ticket_id: str, user_id: str = "system") -> bool:
        """
        Delete ticket and all associated records.

        Args:
            ticket_id: Ticket ID to delete
            user_id: User performing deletion for audit

        Returns:
            True if ticket was deleted, False if not found

        Raises:
            RepositoryError: If deletion fails
        """
        ticket_id = self._validate_id(ticket_id, "ticket_id")

        try:
            with transaction() as conn:
                # Delete associated records first (foreign key constraints)
                conn.execute("DELETE FROM approvals WHERE ticket_id = ?", (ticket_id,))
                conn.execute("DELETE FROM approval_events WHERE ticket_id = ?", (ticket_id,))
                conn.execute("DELETE FROM metrics WHERE ticket_id = ?", (ticket_id,))
                conn.execute("DELETE FROM email_notifications WHERE ticket_id = ?", (ticket_id,))
                conn.execute("DELETE FROM kb_drafts WHERE ticket_id = ?", (ticket_id,))
                conn.execute("DELETE FROM resolution_feedback WHERE ticket_id = ?", (ticket_id,))

                # Delete main ticket record
                cursor = conn.execute("DELETE FROM tickets WHERE ticket_id = ?", (ticket_id,))
                deleted = cursor.rowcount > 0

                if deleted:
                    # Log audit trail
                    self._log_audit(
                        user_id=user_id,
                        action="delete",
                        resource_type="ticket",
                        resource_id=ticket_id,
                        details="Deleted ticket and all associated records"
                    )

                    logger.info(f"Deleted ticket {ticket_id} by user {user_id}")

                return deleted

        except Exception as e:
            logger.error(f"Failed to delete ticket {ticket_id}: {e}")
            raise RepositoryError(f"Failed to delete ticket: {e}")

    def get_tickets_paginated(
        self,
        offset: int = 0,
        limit: int = 50,
        status: Optional[TicketStatus] = None,
        assigned_to: Optional[str] = None,
        order_by: str = "processed_at",
        order_dir: str = "DESC"
    ) -> Tuple[List[TicketModel], int]:
        """
        Get paginated tickets with filters.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            status: Filter by ticket status
            assigned_to: Filter by assigned engineer
            order_by: Field to order by
            order_dir: Order direction (ASC/DESC)

        Returns:
            Tuple of (ticket list, total count)

        Raises:
            ValidationError: If parameters are invalid
            RepositoryError: If query fails
        """
        # Validate parameters
        if offset < 0 or limit <= 0 or limit > 1000:
            raise ValidationError("Invalid offset or limit")

        if order_dir.upper() not in ['ASC', 'DESC']:
            raise ValidationError("Invalid order direction")

        # Validate order field
        allowed_order_fields = {
            'ticket_id', 'subject', 'status', 'assigned_to',
            'created_at', 'updated_at', 'processed_at'
        }
        if order_by not in allowed_order_fields:
            raise ValidationError("Invalid order field")

        try:
            conditions = []
            params = []

            # Build WHERE clause with validated conditions
            if status:
                conditions.append("status = ?")
                params.append(status.value)

            if assigned_to:
                conditions.append("assigned_to = ?")
                params.append(assigned_to)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM tickets {where_clause}"
            with get_connection() as conn:
                total_row = conn.execute(count_query, params).fetchone()
                total = total_row['total'] if total_row else 0

                # Get paginated results
                query = f"""
                    SELECT * FROM tickets {where_clause}
                    ORDER BY {order_by} {order_dir}
                    LIMIT ? OFFSET ?
                """
                rows = conn.execute(query, params + [limit, offset]).fetchall()

                tickets = [TicketModel.from_db_row(row) for row in rows]
                return tickets, total

        except Exception as e:
            logger.error(f"Failed to get paginated tickets: {e}")
            raise RepositoryError(f"Failed to get tickets: {e}")

    def get_tickets_by_status(self, statuses: List[TicketStatus]) -> List[TicketModel]:
        """
        Get tickets by status list.

        Args:
            statuses: List of ticket statuses to filter by

        Returns:
            List of ticket models

        Raises:
            ValidationError: If statuses are invalid
            RepositoryError: If query fails
        """
        if not statuses:
            return []

        try:
            # Build IN clause with placeholders
            placeholders = ', '.join('?' for _ in statuses)
            status_values = [status.value for status in statuses]

            with get_connection() as conn:
                query = f"""
                    SELECT * FROM tickets
                    WHERE status IN ({placeholders})
                    ORDER BY processed_at ASC
                """
                rows = conn.execute(query, status_values).fetchall()
                return [TicketModel.from_db_row(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get tickets by status: {e}")
            raise RepositoryError(f"Failed to get tickets by status: {e}")

    def get_stale_tickets(self, max_hours: float = 24.0) -> List[TicketModel]:
        """
        Get tickets that haven't been updated within the specified timeframe.

        Args:
            max_hours: Maximum hours since last update

        Returns:
            List of stale ticket models

        Raises:
            RepositoryError: If query fails
        """
        try:
            cutoff = (datetime.now() - timedelta(hours=max_hours)).isoformat()
            active_statuses = ['Open', 'Assigned', 'WorkInProgress', 'Processing']

            placeholders = ', '.join('?' for _ in active_statuses)

            with get_connection() as conn:
                query = f"""
                    SELECT * FROM tickets
                    WHERE status IN ({placeholders})
                      AND COALESCE(NULLIF(updated_at, ''), NULLIF(created_at, ''), processed_at) < ?
                    ORDER BY processed_at ASC
                """
                params = active_statuses + [cutoff]
                rows = conn.execute(query, params).fetchall()
                return [TicketModel.from_db_row(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get stale tickets: {e}")
            raise RepositoryError(f"Failed to get stale tickets: {e}")


class ApprovalRepository(BaseRepository):
    """Repository for approval operations."""

    def create_approval(self, approval: ApprovalModel, user_id: str = "system") -> ApprovalModel:
        """Create new approval record."""
        try:
            approval_data = approval.to_db_dict()

            with transaction() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO approvals (
                        ticket_id, status, ai_category, ai_confidence, ai_response,
                        assigned_queue, created_at, updated_at, reviewed_by, reviewer_notes, final_response
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(approval_data.values())
                )

                # Log audit trail
                self._log_audit(
                    user_id=user_id,
                    action="create",
                    resource_type="approval",
                    resource_id=approval.ticket_id,
                    details=f"Created approval for ticket {approval.ticket_id}"
                )

                return approval

        except Exception as e:
            logger.error(f"Failed to create approval for {approval.ticket_id}: {e}")
            raise RepositoryError(f"Failed to create approval: {e}")

    def get_approval_by_ticket(self, ticket_id: str) -> Optional[ApprovalModel]:
        """Get approval by ticket ID."""
        ticket_id = self._validate_id(ticket_id, "ticket_id")

        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM approvals WHERE ticket_id = ?",
                    (ticket_id,)
                ).fetchone()

                if row:
                    return ApprovalModel.from_db_row(row)
                return None

        except Exception as e:
            logger.error(f"Failed to get approval for ticket {ticket_id}: {e}")
            raise RepositoryError(f"Failed to get approval: {e}")


class MetricsRepository(BaseRepository):
    """Repository for metrics and analytics operations."""

    def create_metrics(self, metrics: MetricsModel, user_id: str = "system") -> MetricsModel:
        """Create metrics record."""
        try:
            metrics_data = metrics.to_db_dict()

            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO metrics (
                        ticket_id, created_at, first_response_at, resolved_at,
                        category, queue, was_auto_resolved
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(metrics_data.values())
                )

                logger.debug(f"Created metrics for ticket {metrics.ticket_id}")
                return metrics

        except Exception as e:
            logger.error(f"Failed to create metrics for {metrics.ticket_id}: {e}")
            raise RepositoryError(f"Failed to create metrics: {e}")

    def get_category_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get ticket statistics by category."""
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        category,
                        COUNT(*) as total_tickets,
                        SUM(was_auto_resolved) as auto_resolved,
                        AVG(CASE
                            WHEN resolved_at IS NOT NULL AND first_response_at IS NOT NULL
                            THEN (julianday(resolved_at) - julianday(first_response_at)) * 24 * 3600
                            ELSE NULL
                        END) as avg_resolution_time_seconds
                    FROM metrics
                    WHERE created_at >= ?
                    GROUP BY category
                    ORDER BY total_tickets DESC
                    """,
                    (cutoff,)
                ).fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get category stats: {e}")
            raise RepositoryError(f"Failed to get category stats: {e}")