"""
Secure Scheduler Service

This module provides secure background task scheduling with proper
error handling, monitoring, and audit logging.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from config.settings import Settings
from src.database.repository import TicketRepository
from src.database.models import TicketStatus

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Secure background scheduler for ticket escalation and maintenance tasks.
    """

    def __init__(self, settings: Settings):
        """
        Initialize scheduler service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.scheduler = None
        self.ticket_repo = TicketRepository()
        self._running = False

    async def start(self) -> None:
        """Start the scheduler service."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler

            self.scheduler = BackgroundScheduler(
                daemon=True,
                job_defaults={
                    'coalesce': True,
                    'max_instances': 1,
                    'misfire_grace_time': 300  # 5 minutes
                }
            )

            # Add escalation check job
            self.scheduler.add_job(
                self._escalation_check,
                trigger='interval',
                hours=1,  # Run every hour
                id='escalation_check',
                name='Ticket Escalation Check'
            )

            # Add maintenance job
            self.scheduler.add_job(
                self._maintenance_tasks,
                trigger='cron',
                hour=2,  # Run at 2 AM daily
                id='maintenance_tasks',
                name='Database Maintenance'
            )

            self.scheduler.start()
            self._running = True

            logger.info("Scheduler service started successfully")

        except Exception as e:
            logger.error(f"Failed to start scheduler service: {e}")
            raise

    async def stop(self) -> None:
        """Stop the scheduler service."""
        try:
            if self.scheduler and self._running:
                self.scheduler.shutdown(wait=True)
                self._running = False
                logger.info("Scheduler service stopped")

        except Exception as e:
            logger.error(f"Error stopping scheduler service: {e}")

    def _escalation_check(self) -> None:
        """
        Check for stale tickets and escalate them.

        This runs every hour to find tickets that haven't been updated
        within the escalation timeframe.
        """
        try:
            escalation_hours = getattr(self.settings, 'escalation_hours', 24.0)
            logger.debug(f"Starting escalation check (threshold: {escalation_hours}h)")

            # Get stale tickets
            stale_tickets = self.ticket_repo.get_stale_tickets(escalation_hours)

            if not stale_tickets:
                logger.debug("No tickets require escalation")
                return

            escalated_count = 0

            for ticket in stale_tickets:
                try:
                    # Calculate how long the ticket has been stale
                    last_update = ticket.updated_at or ticket.created_at
                    hours_stale = (datetime.now() - last_update).total_seconds() / 3600

                    # Update ticket status to Escalated
                    updated = self.ticket_repo.update_ticket(
                        ticket_id=ticket.ticket_id,
                        updates={'status': TicketStatus.ESCALATED},
                        user_id='system_escalation'
                    )

                    if updated:
                        escalated_count += 1

                        # Send escalation notification
                        self._send_escalation_notification(ticket, hours_stale)

                        logger.info(
                            f"Escalated ticket {ticket.ticket_id} "
                            f"(stale for {hours_stale:.1f} hours)"
                        )

                except Exception as e:
                    logger.error(f"Failed to escalate ticket {ticket.ticket_id}: {e}")
                    continue

            if escalated_count > 0:
                logger.info(
                    f"Escalation check completed: {escalated_count} tickets escalated "
                    f"out of {len(stale_tickets)} candidates"
                )

        except Exception as e:
            logger.error(f"Escalation check failed: {e}")

    def _send_escalation_notification(self, ticket, hours_stale: float) -> None:
        """
        Send escalation notification email.

        Args:
            ticket: Ticket model that was escalated
            hours_stale: Hours since last update
        """
        try:
            # Import here to avoid circular imports
            from src.notifications.email_service import send_escalation_notification
            from config.routing_rules import get_queue_members
            from src.security.auth import get_engineer_emails

            # Parse routing information
            queue_name = "IT Support"  # Default
            if ticket.routing_json and isinstance(ticket.routing_json, dict):
                queue_name = ticket.routing_json.get('queue', 'IT Support')

            # Get queue members
            members = get_queue_members(queue_name) if hasattr(queue_name, '__iter__') else []
            recipients = get_engineer_emails(members) if members else []

            # Add escalation mailbox
            escalation_email = getattr(self.settings, 'escalation_email', None)
            if escalation_email:
                recipients.append(("Escalation Team", escalation_email))

            # Add submitter
            if ticket.submitter_email:
                recipients.append((ticket.submitter, ticket.submitter_email))

            # Send notification
            if recipients:
                send_escalation_notification(
                    ticket_id=ticket.ticket_id,
                    subject=ticket.subject,
                    queue_name=queue_name,
                    hours_open=hours_stale,
                    recipients=recipients
                )

                logger.debug(
                    f"Sent escalation notification for {ticket.ticket_id} "
                    f"to {len(recipients)} recipients"
                )

        except Exception as e:
            logger.error(f"Failed to send escalation notification for {ticket.ticket_id}: {e}")

    def _maintenance_tasks(self) -> None:
        """
        Perform daily maintenance tasks.

        This runs daily at 2 AM to perform database cleanup and optimization.
        """
        try:
            logger.info("Starting daily maintenance tasks")

            # Clean up old audit logs (keep 90 days)
            self._cleanup_audit_logs(days=90)

            # Clean up old email notifications (keep 30 days)
            self._cleanup_email_notifications(days=30)

            # Optimize database (SQLite VACUUM)
            self._optimize_database()

            logger.info("Daily maintenance tasks completed")

        except Exception as e:
            logger.error(f"Maintenance tasks failed: {e}")

    def _cleanup_audit_logs(self, days: int) -> None:
        """Clean up old audit log entries."""
        try:
            from src.database.connection import get_connection

            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            with get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM audit_log WHERE created_at < ?",
                    (cutoff,)
                )

                if cursor.rowcount > 0:
                    logger.info(f"Cleaned up {cursor.rowcount} old audit log entries")

        except Exception as e:
            logger.error(f"Failed to cleanup audit logs: {e}")

    def _cleanup_email_notifications(self, days: int) -> None:
        """Clean up old email notification records."""
        try:
            from src.database.connection import get_connection

            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            with get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM email_notifications WHERE created_at < ? AND status = 'sent'",
                    (cutoff,)
                )

                if cursor.rowcount > 0:
                    logger.info(f"Cleaned up {cursor.rowcount} old email notification records")

        except Exception as e:
            logger.error(f"Failed to cleanup email notifications: {e}")

    def _optimize_database(self) -> None:
        """Optimize database performance."""
        try:
            from src.database.connection import get_connection

            with get_connection() as conn:
                # SQLite optimization commands
                conn.execute("PRAGMA optimize")
                conn.execute("VACUUM")

                logger.info("Database optimization completed")

        except Exception as e:
            logger.error(f"Database optimization failed: {e}")

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running and self.scheduler and self.scheduler.running

    def get_job_status(self) -> dict:
        """Get status of scheduled jobs."""
        if not self.scheduler:
            return {"status": "stopped", "jobs": []}

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })

        return {
            "status": "running" if self._running else "stopped",
            "jobs": jobs
        }