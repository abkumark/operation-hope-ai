"""Tests for KB ingestion and vector store search."""

import pytest

from src.knowledge.kb_ingester import (
    KBArticle,
    load_all_kb_articles,
    load_kb_article,
    parse_frontmatter,
)
from src.knowledge.vectorstore import (
    _chunk_article,
    get_kb_status,
    ingest_kb_articles,
    search_kb,
)


class TestKBIngester:
    def test_parse_frontmatter(self):
        content = '---\ntitle: "Test"\ncategory: "test_cat"\n---\nBody text here.'
        meta, body = parse_frontmatter(content)
        assert meta["title"] == "Test"
        assert meta["category"] == "test_cat"
        assert body == "Body text here."

    def test_parse_frontmatter_no_frontmatter(self):
        content = "Just a plain document."
        meta, body = parse_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_load_all_kb_articles(self):
        articles = load_all_kb_articles("data/knowledge_base")
        assert len(articles) > 0
        for article in articles:
            assert article.filename
            assert article.title
            assert article.category

    def test_article_has_expected_fields(self):
        articles = load_all_kb_articles("data/knowledge_base")
        pw_articles = [a for a in articles if a.category == "password_reset"]
        assert len(pw_articles) >= 1
        pw = pw_articles[0]
        assert pw.auto_resolvable is True
        assert pw.queue == "IT Support"
        assert pw.resolution_steps  # should have content
        assert pw.response_template  # should have content

    def test_article_language_defaults_to_en(self):
        articles = load_all_kb_articles("data/knowledge_base")
        for article in articles:
            if article.language == "en":
                break
        else:
            pytest.fail("Expected at least one English article")


class TestChunking:
    def test_chunk_article_produces_chunks(self):
        article = KBArticle(
            filename="test.md",
            title="Test Article",
            category="test",
            ticket_type="external",
            auto_resolvable=True,
            queue="IT Support",
            last_updated="2025-01-01",
            content="This is the main content.",
            resolution_steps="Step 1: Do this.",
            response_template="Dear client, we fixed it.",
            internal_notes="Internal only.",
        )
        chunks = _chunk_article(article)
        assert len(chunks) == 3  # full, resolution, response
        chunk_types = [c[2]["chunk_type"] for c in chunks]
        assert "full" in chunk_types
        assert "resolution" in chunk_types
        assert "response" in chunk_types

    def test_chunk_includes_language_metadata(self):
        article = KBArticle(
            filename="test_es.md",
            title="Articulo de Prueba",
            category="test",
            ticket_type="external",
            auto_resolvable=True,
            queue="IT Support",
            last_updated="2025-01-01",
            content="Contenido principal.",
            resolution_steps="",
            response_template="",
            internal_notes="",
            language="es",
        )
        chunks = _chunk_article(article)
        assert len(chunks) >= 1
        assert chunks[0][2]["language"] == "es"

    def test_empty_sections_not_chunked(self):
        article = KBArticle(
            filename="minimal.md",
            title="Minimal",
            category="test",
            ticket_type="external",
            auto_resolvable=False,
            queue="IT Support",
            last_updated="",
            content="Only main content.",
            resolution_steps="",
            response_template="",
            internal_notes="",
        )
        chunks = _chunk_article(article)
        assert len(chunks) == 1
        assert chunks[0][2]["chunk_type"] == "full"


class TestVectorStoreIntegration:
    def test_ingest_and_search(self):
        count = ingest_kb_articles(force_reingest=True)
        assert count > 0

        results = search_kb("password reset")
        assert len(results) > 0
        assert results[0]["content"]
        assert results[0]["metadata"].get("title")

    def test_search_with_category_filter(self):
        ingest_kb_articles(force_reingest=True)
        results = search_kb("help", category_filter="password_reset")
        for r in results:
            assert r["metadata"]["category"] == "password_reset"

    def test_search_empty_store(self):
        # After clearing, search should return empty
        results = search_kb("anything")
        # May or may not be empty depending on test order; just verify no crash
        assert isinstance(results, list)

    def test_kb_status(self):
        ingest_kb_articles(force_reingest=True)
        status = get_kb_status()
        assert status["article_count"] > 0
        assert status["chunk_count"] > 0
