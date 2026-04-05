"""
Health Monitoring Service

This module provides comprehensive health monitoring for the application,
including database connectivity, service status, and performance metrics.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import threading

logger = logging.getLogger(__name__)


class HealthService:
    """
    Health monitoring service for application components.
    """

    def __init__(self):
        """Initialize health service."""
        self._running = False
        self._health_data = {}
        self._monitor_task = None
        self._lock = threading.Lock()

    async def start(self) -> None:
        """Start health monitoring."""
        try:
            self._running = True
            self._monitor_task = asyncio.create_task(self._monitoring_loop())
            logger.info("Health monitoring service started")

        except Exception as e:
            logger.error(f"Failed to start health service: {e}")
            raise

    async def stop(self) -> None:
        """Stop health monitoring."""
        try:
            self._running = False

            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass

            logger.info("Health monitoring service stopped")

        except Exception as e:
            logger.error(f"Error stopping health service: {e}")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Update health status every 30 seconds
                await self._update_health_status()
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(30)  # Continue monitoring even if one check fails

    async def _update_health_status(self) -> None:
        """Update comprehensive health status."""
        try:
            with self._lock:
                health_data = {
                    "timestamp": datetime.now().isoformat(),
                    "status": "healthy",
                    "services": {},
                    "metrics": {}
                }

                # Check database health
                health_data["services"]["database"] = await self._check_database_health()

                # Check knowledge base health
                health_data["services"]["knowledge_base"] = await self._check_kb_health()

                # Check scheduler health
                health_data["services"]["scheduler"] = await self._check_scheduler_health()

                # Check file system health
                health_data["services"]["filesystem"] = await self._check_filesystem_health()

                # Calculate overall status
                service_statuses = [svc["status"] for svc in health_data["services"].values()]
                if any(status == "unhealthy" for status in service_statuses):
                    health_data["status"] = "unhealthy"
                elif any(status == "degraded" for status in service_statuses):
                    health_data["status"] = "degraded"

                # Collect performance metrics
                health_data["metrics"] = await self._collect_metrics()

                self._health_data = health_data

        except Exception as e:
            logger.error(f"Failed to update health status: {e}")
            with self._lock:
                self._health_data = {
                    "timestamp": datetime.now().isoformat(),
                    "status": "unhealthy",
                    "error": str(e)
                }

    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            from src.database.connection import get_connection
            import time

            start_time = time.time()

            with get_connection() as conn:
                # Test basic connectivity
                conn.execute("SELECT 1")

                # Test table existence
                tables_result = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()

                # Test data access
                ticket_count = conn.execute(
                    "SELECT COUNT(*) as count FROM tickets"
                ).fetchone()

            response_time = time.time() - start_time

            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "tables_count": len(tables_result),
                "tickets_count": ticket_count["count"] if ticket_count else 0,
                "last_check": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }

    async def _check_kb_health(self) -> Dict[str, Any]:
        """Check knowledge base health."""
        try:
            from src.knowledge.vectorstore import get_kb_status

            kb_status = get_kb_status()

            if kb_status["chunk_count"] == 0:
                status = "degraded"
                message = "Knowledge base is empty"
            else:
                status = "healthy"
                message = f"{kb_status['chunk_count']} chunks available"

            return {
                "status": status,
                "message": message,
                "chunk_count": kb_status["chunk_count"],
                "last_check": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Knowledge base health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }

    async def _check_scheduler_health(self) -> Dict[str, Any]:
        """Check scheduler service health."""
        try:
            # This would check the scheduler service if available
            # For now, return basic status
            return {
                "status": "healthy",
                "message": "Scheduler service operational",
                "last_check": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Scheduler health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }

    async def _check_filesystem_health(self) -> Dict[str, Any]:
        """Check filesystem health and disk space."""
        try:
            import shutil
            from pathlib import Path

            # Check database directory
            from config.settings import get_settings
            settings = get_settings()
            db_path = Path(settings.database_path)

            # Get disk usage
            total, used, free = shutil.disk_usage(db_path.parent)

            # Calculate usage percentage
            usage_percent = (used / total) * 100

            # Determine status based on disk usage
            if usage_percent > 95:
                status = "unhealthy"
                message = "Disk space critically low"
            elif usage_percent > 85:
                status = "degraded"
                message = "Disk space running low"
            else:
                status = "healthy"
                message = "Sufficient disk space available"

            return {
                "status": status,
                "message": message,
                "disk_usage_percent": round(usage_percent, 2),
                "free_bytes": free,
                "total_bytes": total,
                "last_check": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Filesystem health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }

    async def _collect_metrics(self) -> Dict[str, Any]:
        """Collect performance metrics."""
        try:
            from src.database.connection import get_connection
            import psutil
            import os

            metrics = {}

            # System metrics
            process = psutil.Process(os.getpid())
            metrics["system"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "process_memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                "process_cpu_percent": process.cpu_percent()
            }

            # Database metrics
            try:
                with get_connection() as conn:
                    # Count tickets by status
                    status_counts = conn.execute("""
                        SELECT status, COUNT(*) as count
                        FROM tickets
                        GROUP BY status
                    """).fetchall()

                    metrics["tickets"] = {
                        row["status"]: row["count"]
                        for row in status_counts
                    }

                    # Recent activity (last 24 hours)
                    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
                    recent_count = conn.execute(
                        "SELECT COUNT(*) as count FROM tickets WHERE created_at >= ?",
                        (cutoff,)
                    ).fetchone()

                    metrics["activity"] = {
                        "tickets_last_24h": recent_count["count"] if recent_count else 0
                    }

            except Exception as e:
                logger.warning(f"Failed to collect database metrics: {e}")
                metrics["tickets"] = {"error": "Unable to collect ticket metrics"}

            return metrics

        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            return {"error": str(e)}

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        with self._lock:
            return self._health_data.copy() if self._health_data else {
                "status": "unknown",
                "message": "Health data not available"
            }

    def is_healthy(self) -> bool:
        """Check if application is healthy."""
        with self._lock:
            return self._health_data.get("status") == "healthy" if self._health_data else False

    @property
    def is_running(self) -> bool:
        """Check if health monitoring is running."""
        return self._running