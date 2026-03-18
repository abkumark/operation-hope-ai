"""FastAPI application with HTML UI and API routes."""
try:
    __import__("pysqlite3")
    import sys
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config.settings import get_settings
from config.categories import get_all_categories
from src.api.routes import router
from src.knowledge.vectorstore import get_kb_status, ingest_kb_articles
from src.storage.sqlite_db import backfill_timestamps, cleanup_stuck_tickets, init_database

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Rate limiter (keyed by client IP)
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# APScheduler for periodic escalation checks
_scheduler = None


def _start_escalation_scheduler() -> None:
    """Start background scheduler that checks for stale tickets periodically.

    Escalation rule: any ticket with no edits (no updated_at change) for
    24 hours after creation gets escalated and an email alert is sent
    to the configured escalation address and queue members.
    """
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        settings = get_settings()

        def _run_escalation_check():
            """Check for tickets with no activity for 24+ hours and escalate."""
            from datetime import datetime
            from config.routing_rules import get_queue_members
            from src.auth import get_engineer_emails
            from src.notifications.email_service import send_escalation_notification
            from src.storage.sqlite_db import get_stale_tickets, update_ticket_fields
            from src.workflow.pipeline import _load_pipeline_result

            escalation_hours = settings.escalation_hours  # default 24.0
            stale_rows = get_stale_tickets(max_hours_since_update=escalation_hours)
            escalated = []

            for row in stale_rows:
                ticket_id = row["ticket_id"]
                subject = row["subject"]

                # Parse routing to get queue name
                try:
                    import json as _json
                    rte = _json.loads(row["routing_json"])
                    queue_name = rte.get("queue", "IT Support")
                except Exception:
                    queue_name = "IT Support"

                # Calculate hours since last update
                last_touch = row["updated_at"] or row["created_at"] or row["processed_at"]
                try:
                    hours_open = (datetime.now() - datetime.fromisoformat(last_touch)).total_seconds() / 3600
                except Exception:
                    hours_open = escalation_hours

                # Mark as escalated
                update_ticket_fields(ticket_id, status="Escalated")
                escalated.append(ticket_id)

                # Send escalation email to queue members + escalation address + submitter
                try:
                    members = get_queue_members(queue_name) if queue_name else []
                    recipients = get_engineer_emails(members) if members else []
                    # Always include the configured escalation mailbox
                    escalation_email = settings.escalation_email or settings.smtp_sender
                    if escalation_email and not any(r[1] == escalation_email for r in recipients):
                        recipients.append(("Escalation Alerts", escalation_email))
                    # Also notify the original submitter so they know
                    sub_email = row.get("submitter_email", "")
                    sub_name = row.get("submitter", "")
                    if sub_email and not any(r[1] == sub_email for r in recipients):
                        recipients.append((sub_name or "Submitter", sub_email))
                    send_escalation_notification(
                        ticket_id=ticket_id, subject=subject,
                        queue_name=queue_name, hours_open=hours_open,
                        recipients=recipients,
                    )
                except Exception:
                    logger.exception("Scheduled escalation email failed for %s", ticket_id)

            if escalated:
                logger.info(
                    "Escalation check: %d tickets escalated (no edits for %.0fh): %s",
                    len(escalated), escalation_hours, escalated,
                )

        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            _run_escalation_check, "interval",
            hours=1, id="escalation_check",
            misfire_grace_time=300,
        )
        _scheduler.start()
        logger.info(
            "Escalation scheduler started (checks every 1 hour, "
            "escalates tickets with no edits for %.0fh)",
            settings.escalation_hours,
        )
    except Exception as exc:
        logger.warning("Failed to start escalation scheduler: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_database()

    # Backfill created_at/updated_at for existing tickets that don't have them
    backfill_timestamps()

    # Clean up stuck tickets from previous crashes
    cleaned = cleanup_stuck_tickets(max_age_minutes=30)
    if cleaned:
        logger.info("Cleaned up %d stuck 'Processing' tickets on startup", cleaned)

    if settings.auto_ingest_kb_on_startup:
        kb_status = get_kb_status()
        if kb_status["chunk_count"] == 0:
            ingest_kb_articles(kb_dir=str(settings.knowledge_base_dir), force_reingest=False)

    # Start escalation scheduler
    _start_escalation_scheduler()

    yield

    # Shutdown scheduler
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Operation HOPE AI",
        description="AI-powered support ticket system for Operation HOPE",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router, prefix="/api/v1")

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        categories = get_all_categories()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "provider": settings.active_provider.upper(),
            "model": settings.azure_openai_deployment or settings.openai_model or "fallback",
            "auto_threshold": f"{settings.auto_resolve_threshold:.0%}",
            "review_threshold": f"{settings.review_threshold:.0%}",
            "categories": categories,
        })

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(str(STATIC_DIR / "favicon.svg"), media_type="image/svg+xml")

    return app


app = create_app()
