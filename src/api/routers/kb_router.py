"""Knowledge Base routes — search, articles, drafts, ingestion."""

from __future__ import annotations

import re
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config.settings import get_settings
from src.auth import User
from src.api.deps import require_admin, require_auth
from src.knowledge.kb_ingester import load_all_kb_articles
from src.knowledge.vectorstore import get_kb_status, ingest_kb_articles, search_kb
from src.storage.sqlite_db import (
    create_kb_draft,
    delete_kb_draft,
    get_kb_draft,
    list_kb_drafts,
    publish_kb_draft,
)

_logger = logging.getLogger(__name__)

router = APIRouter(tags=["knowledge-base"])


@router.post("/kb/ingest")
async def kb_ingest(
    force: bool = False, user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Trigger KB ingestion (admin)."""
    settings = get_settings()
    count = ingest_kb_articles(kb_dir=str(settings.knowledge_base_dir), force_reingest=force)
    return {"documents_added": count, "status": "success"}


@router.get("/kb/status")
async def kb_status() -> dict[str, Any]:
    """Return KB article and vector store status."""
    status = get_kb_status()
    return {"status": "success", **status}


@router.get("/kb/articles")
async def kb_articles() -> dict[str, Any]:
    """Return KB article metadata."""
    settings = get_settings()
    articles = load_all_kb_articles(settings.knowledge_base_dir)
    return {
        "count": len(articles),
        "articles": [
            {
                "filename": article.filename,
                "title": article.title,
                "category": article.category,
                "ticket_type": article.ticket_type,
                "auto_resolvable": article.auto_resolvable,
                "queue": article.queue,
                "last_updated": article.last_updated,
            }
            for article in articles
        ],
    }


@router.get("/kb/articles/{filename}")
async def kb_article_detail(filename: str) -> dict[str, Any]:
    """Return full content for a single KB article by filename."""
    settings = get_settings()
    articles = load_all_kb_articles(settings.knowledge_base_dir)
    for article in articles:
        if article.filename == filename:
            return {
                "filename": article.filename,
                "title": article.title,
                "category": article.category,
                "ticket_type": article.ticket_type,
                "auto_resolvable": article.auto_resolvable,
                "queue": article.queue,
                "last_updated": article.last_updated,
                "content": article.content,
                "resolution_steps": article.resolution_steps,
                "response_template": article.response_template,
                "internal_notes": article.internal_notes,
            }
    raise HTTPException(status_code=404, detail="KB article not found")


@router.get("/kb/search")
async def kb_search(
    query: str, category: Optional[str] = None, limit: int = 5,
) -> dict[str, Any]:
    """Search the knowledge base (authenticated)."""
    results = search_kb(query=query, n_results=limit, category_filter=category)
    return {
        "query": query,
        "count": len(results),
        "results": [
            {
                "content": r["content"][:500],
                "title": r["metadata"].get("title", ""),
                "category": r["metadata"].get("category", ""),
                "similarity": r.get("similarity", 0),
            }
            for r in results
        ],
    }


@router.get("/kb/self-service")
async def kb_self_service(query: str, limit: int = 5) -> dict[str, Any]:
    """Public (unauthenticated) self-service KB search."""
    if len(query.strip()) < 3:
        raise HTTPException(status_code=422, detail="Query must be at least 3 characters")
    results = search_kb(query=query, n_results=limit)
    return {
        "query": query,
        "count": len(results),
        "results": [
            {
                "title": r["metadata"].get("title", "Untitled"),
                "summary": r["content"][:300],
                "category": r["metadata"].get("category", ""),
            }
            for r in results
        ],
    }


# ── KB Drafts ────────────────────────────────────────────────────────────


class KBDraftCreateRequest(BaseModel):
    ticket_id: str = Field(..., description="Source ticket ID")
    title: str = Field(..., description="Draft article title", min_length=3, max_length=300)
    category: str = Field(default="", description="Category ID for the KB article")
    content: str = Field(..., description="Article content (resolution text)", min_length=10)
    created_by: str = Field(default="", description="Admin who created the draft")


@router.post("/kb/drafts")
async def create_kb_draft_endpoint(
    request: KBDraftCreateRequest, user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Create a KB article draft from a resolved ticket."""
    draft_id = create_kb_draft(
        ticket_id=request.ticket_id, title=request.title,
        category=request.category, content=request.content,
        created_by=request.created_by,
    )
    return {"status": "success", "draft_id": draft_id}


@router.get("/kb/drafts")
async def list_kb_drafts_endpoint(
    status: Optional[str] = None, user: User = Depends(require_admin),
) -> dict[str, Any]:
    """List KB article drafts."""
    drafts = list_kb_drafts(status=status)
    return {"count": len(drafts), "drafts": drafts}


@router.get("/kb/drafts/{draft_id}")
async def get_kb_draft_endpoint(
    draft_id: int, user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Get a single KB draft by ID."""
    draft = get_kb_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="KB draft not found")
    return draft


@router.post("/kb/drafts/{draft_id}/publish")
async def publish_kb_draft_endpoint(
    draft_id: int, user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Publish a KB draft."""
    draft = get_kb_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="KB draft not found")
    if draft["status"] != "draft":
        raise HTTPException(status_code=400, detail="Draft is already published")

    settings = get_settings()
    kb_dir = settings.knowledge_base_dir
    safe_title = re.sub(r"[^a-z0-9_]+", "_", draft["title"].lower()).strip("_")
    filename = f"{safe_title}.md"
    filepath = kb_dir / filename

    md_content = (
        f"---\ntitle: \"{draft['title']}\"\ncategory: \"{draft['category']}\"\n"
        f"ticket_type: \"any\"\nauto_resolvable: false\nqueue: \"IT Support\"\n"
        f"last_updated: \"{draft['created_at'][:10]}\"\n---\n\n"
        f"# {draft['title']}\n\n{draft['content']}\n"
    )
    filepath.write_text(md_content, encoding="utf-8")

    published = publish_kb_draft(draft_id)
    if not published:
        raise HTTPException(status_code=500, detail="Failed to mark draft as published")

    added = ingest_kb_articles(kb_dir=str(kb_dir), force_reingest=True)
    return {"status": "success", "draft_id": draft_id, "filename": filename, "documents_ingested": added}


@router.delete("/kb/drafts/{draft_id}")
async def delete_kb_draft_endpoint(
    draft_id: int, user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Delete a KB draft."""
    found = delete_kb_draft(draft_id)
    if not found:
        raise HTTPException(status_code=404, detail="KB draft not found")
    return {"status": "success", "draft_id": draft_id}
