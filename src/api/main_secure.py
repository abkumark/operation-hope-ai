"""
Secure FastAPI Application with Enterprise Security Controls

This module provides a hardened FastAPI application with comprehensive
security middleware, authentication, and monitoring capabilities.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException, status
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
from src.database.connection import init_database, close_connection, get_db_manager
from src.knowledge.vectorstore import get_kb_status, ingest_kb_articles
from src.security.middleware import (
    AuthenticationMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware
)
from src.services.scheduler import SchedulerService
from src.services.health import HealthService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Directory paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Rate limiter configuration
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute", "2000/hour"]
)


class SecureApplication:
    """
    Secure FastAPI application with enterprise security controls.
    """

    def __init__(self):
        """Initialize secure application."""
        self.scheduler_service = None
        self.health_service = None
        self.settings = get_settings()

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """
        Application lifespan management with secure initialization.
        """
        try:
            logger.info("Starting Operation HOPE AI application...")

            # Initialize secure database
            await self._initialize_database()

            # Initialize knowledge base
            await self._initialize_knowledge_base()

            # Start background services
            await self._start_background_services()

            # Initialize health monitoring
            self.health_service = HealthService()
            await self.health_service.start()

            logger.info("Application startup completed successfully")
            yield

        except Exception as e:
            logger.error(f"Application startup failed: {e}")
            raise

        finally:
            # Cleanup on shutdown
            await self._cleanup_services()
            logger.info("Application shutdown completed")

    async def _initialize_database(self) -> None:
        """Initialize database with security checks."""
        try:
            # Initialize database schema
            init_database()

            # Clean up any stuck tickets from previous crashes
            db_manager = get_db_manager()
            with db_manager.transaction() as conn:
                cursor = conn.execute(
                    "UPDATE tickets SET status = 'Open' "
                    "WHERE status = 'Processing' AND "
                    "datetime(processed_at) < datetime('now', '-30 minutes')"
                )
                if cursor.rowcount > 0:
                    logger.warning(f"Cleaned up {cursor.rowcount} stuck processing tickets")

            # Backfill missing timestamps
            with db_manager.transaction() as conn:
                cursor = conn.execute(
                    """
                    UPDATE tickets
                    SET created_at = processed_at, updated_at = processed_at
                    WHERE (created_at IS NULL OR created_at = '')
                      AND processed_at IS NOT NULL AND processed_at != ''
                    """
                )
                if cursor.rowcount > 0:
                    logger.info(f"Backfilled timestamps for {cursor.rowcount} tickets")

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    async def _initialize_knowledge_base(self) -> None:
        """Initialize knowledge base if needed."""
        try:
            if self.settings.auto_ingest_kb_on_startup:
                kb_status = get_kb_status()
                if kb_status["chunk_count"] == 0:
                    logger.info("Knowledge base empty, starting ingestion...")
                    ingest_kb_articles(
                        kb_dir=str(self.settings.knowledge_base_dir),
                        force_reingest=False
                    )
                    logger.info("Knowledge base ingestion completed")
                else:
                    logger.info(f"Knowledge base ready: {kb_status['chunk_count']} chunks")

        except Exception as e:
            logger.error(f"Knowledge base initialization failed: {e}")
            # Don't fail startup for KB issues
            pass

    async def _start_background_services(self) -> None:
        """Start background services like escalation scheduler."""
        try:
            self.scheduler_service = SchedulerService(self.settings)
            await self.scheduler_service.start()
            logger.info("Background services started")

        except Exception as e:
            logger.error(f"Failed to start background services: {e}")
            # Don't fail startup for scheduler issues
            pass

    async def _cleanup_services(self) -> None:
        """Clean up services on shutdown."""
        try:
            if self.scheduler_service:
                await self.scheduler_service.stop()

            if self.health_service:
                await self.health_service.stop()

            # Close database connections
            close_connection()

            logger.info("Services cleanup completed")

        except Exception as e:
            logger.error(f"Service cleanup failed: {e}")

    def create_app(self) -> FastAPI:
        """
        Create FastAPI application with security middleware.

        Returns:
            Configured FastAPI application
        """
        app = FastAPI(
            title="Operation HOPE AI",
            description="AI-powered support ticket system with enterprise security",
            version="2.0.0",
            lifespan=self.lifespan,
            docs_url="/docs" if self.settings.debug else None,
            redoc_url="/redoc" if self.settings.debug else None,
        )

        # Add security middleware (order matters!)
        self._add_security_middleware(app)

        # Add rate limiting
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

        # Add CORS (configured securely)
        self._add_cors_middleware(app)

        # Mount static files
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        # Include API routes
        app.include_router(router, prefix="/api/v1")

        # Add application routes
        self._add_application_routes(app)

        # Add error handlers
        self._add_error_handlers(app)

        return app

    def _add_security_middleware(self, app: FastAPI) -> None:
        """Add security middleware stack."""

        # Request logging (outermost)
        app.add_middleware(RequestLoggingMiddleware)

        # Security headers
        app.add_middleware(SecurityHeadersMiddleware)

        # Rate limiting per IP
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=60,
            requests_per_hour=1000
        )

        # Authentication middleware (inner)
        public_endpoints = {
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/favicon.ico",
            "/api/v1/tickets/submit",  # Public ticket submission
            "/static",  # Static files
        }

        app.add_middleware(
            AuthenticationMiddleware,
            public_endpoints=public_endpoints,
            require_auth_by_default=True
        )

    def _add_cors_middleware(self, app: FastAPI) -> None:
        """Add CORS middleware with secure configuration."""
        allowed_origins = self.settings.cors_origins

        # In production, be more restrictive
        if not self.settings.debug:
            # Filter out localhost origins in production
            allowed_origins = [
                origin for origin in allowed_origins
                if not any(local in origin for local in ['localhost', '127.0.0.1'])
            ]

        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Accept"],
            expose_headers=["X-Process-Time"],
        )

    def _add_application_routes(self, app: FastAPI) -> None:
        """Add application-specific routes."""
        templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

        @app.get("/", response_class=HTMLResponse)
        async def index(request: Request):
            """Main application page."""
            try:
                categories = get_all_categories()
                return templates.TemplateResponse("index.html", {
                    "request": request,
                    "provider": self.settings.active_provider.upper(),
                    "model": (
                        self.settings.azure_openai_deployment or
                        self.settings.openai_model or
                        "fallback"
                    ),
                    "auto_threshold": f"{self.settings.auto_resolve_threshold:.0%}",
                    "review_threshold": f"{self.settings.review_threshold:.0%}",
                    "categories": categories,
                })
            except Exception as e:
                logger.error(f"Index page error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Application error"
                )

        @app.get("/health")
        async def health_check():
            """Health check endpoint for monitoring."""
            try:
                health_status = {
                    "status": "healthy",
                    "version": "2.0.0",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "services": {
                        "database": "healthy",
                        "knowledge_base": "healthy",
                        "scheduler": "healthy" if self.scheduler_service else "stopped"
                    }
                }

                # Check database connectivity
                try:
                    db_manager = get_db_manager()
                    with db_manager.get_connection() as conn:
                        conn.execute("SELECT 1")
                except Exception as e:
                    health_status["services"]["database"] = "unhealthy"
                    health_status["status"] = "degraded"
                    logger.warning(f"Database health check failed: {e}")

                # Check knowledge base
                try:
                    kb_status = get_kb_status()
                    if kb_status["chunk_count"] == 0:
                        health_status["services"]["knowledge_base"] = "empty"
                        health_status["status"] = "degraded"
                except Exception as e:
                    health_status["services"]["knowledge_base"] = "unhealthy"
                    logger.warning(f"Knowledge base health check failed: {e}")

                return health_status

            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"status": "unhealthy", "error": "Health check failed"}
                )

        @app.get("/favicon.ico", include_in_schema=False)
        async def favicon():
            """Favicon endpoint."""
            favicon_path = STATIC_DIR / "favicon.svg"
            if favicon_path.exists():
                return FileResponse(str(favicon_path), media_type="image/svg+xml")
            else:
                raise HTTPException(status_code=404, detail="Favicon not found")

    def _add_error_handlers(self, app: FastAPI) -> None:
        """Add global error handlers."""

        @app.exception_handler(ValueError)
        async def validation_error_handler(request: Request, exc: ValueError):
            """Handle validation errors."""
            logger.warning(f"Validation error on {request.url}: {exc}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": f"Validation error: {str(exc)}"}
            )

        @app.exception_handler(PermissionError)
        async def permission_error_handler(request: Request, exc: PermissionError):
            """Handle permission errors."""
            logger.warning(f"Permission denied on {request.url}: {exc}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Permission denied"}
            )

        @app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            """Handle unexpected errors."""
            logger.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)

            # Don't expose internal errors in production
            if self.settings.debug:
                detail = f"Internal error: {str(exc)}"
            else:
                detail = "Internal server error"

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": detail}
            )


# Create application instance
secure_app = SecureApplication()
app = secure_app.create_app()

# Backward compatibility
create_app = secure_app.create_app