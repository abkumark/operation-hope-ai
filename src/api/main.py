"""FastAPI application with HTML UI and API routes."""
try:
    __import__("pysqlite3")
    import sys
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config.settings import get_settings
from config.categories import get_all_categories
from src.api.routes import router
from src.knowledge.vectorstore import get_kb_status, ingest_kb_articles
from src.storage.sqlite_db import init_database

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_database()
    if settings.auto_ingest_kb_on_startup:
        kb_status = get_kb_status()
        if kb_status["chunk_count"] == 0:
            ingest_kb_articles(kb_dir=str(settings.knowledge_base_dir), force_reingest=False)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Operation HOPE AI",
        description="AI-powered support ticket system for Operation HOPE",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
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

    return app


app = create_app()
