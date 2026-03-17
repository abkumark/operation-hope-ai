"""ChromaDB vector store for Knowledge Base RAG and ticket similarity.

Includes:
- Embedding model tracking to prevent cross-model mismatches
- Content hashing for KB article updates
- Ticket embedding collection for semantic similar-ticket search
- Relevance threshold support
"""

import hashlib
import logging
from pathlib import Path

import chromadb

from config.settings import get_settings
from src.llm.embeddings import get_embedding_function
from src.knowledge.kb_ingester import load_all_kb_articles, KBArticle

logger = logging.getLogger(__name__)

_KB_COLLECTION = "hope_kb"
_TICKET_COLLECTION = "hope_tickets"


class LangChainEmbeddingAdapter:
    """Adapter that lets Chroma use LangChain embedding providers.

    Implements both __call__ (for document embedding during ingestion)
    and embed_query (for query-time embedding) to support all ChromaDB versions.
    """

    def __init__(self, embedder):
        self.embedder = embedder
        self.is_legacy = False

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self.embedder.embed_documents(list(input))

    def embed_query(self, input: list[str]) -> list[list[float]]:
        """ChromaDB >= 0.6 calls this for query-time embedding."""
        return [self.embedder.embed_query(text) for text in list(input)]

    def name(self) -> str:
        return "langchain_adapter"


def _get_embedding_model_name() -> str:
    """Return a string identifying the current embedding model for tracking."""
    settings = get_settings()
    if settings.active_provider == "azure":
        return f"azure:{settings.azure_openai_embedding_deployment}"
    elif settings.active_provider == "openai":
        return "openai:text-embedding-3-small"
    else:
        return "huggingface:all-MiniLM-L6-v2"


def get_chroma_client() -> chromadb.ClientAPI:
    settings = get_settings()
    persist_dir = settings.chroma_persist_dir
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


def _get_embedding_adapter() -> LangChainEmbeddingAdapter:
    return LangChainEmbeddingAdapter(get_embedding_function())


def get_or_create_collection(
    client: chromadb.ClientAPI,
    name: str = _KB_COLLECTION,
) -> chromadb.Collection:
    """Get or create a Chroma collection with embedding model tracking.

    Logs a warning if there's an embedding model mismatch.

    Query-time embedding is handled explicitly in search functions so this
    helper avoids eagerly initializing embedding providers for existing
    collections, which can trigger network/model loading during tests.
    """
    current_model = _get_embedding_model_name()

    try:
        collection = client.get_collection(name=name)
        # Check for embedding model mismatch
        stored_model = collection.metadata.get("embedding_model", "")
        if stored_model and stored_model != current_model:
            logger.warning(
                "Embedding model mismatch for collection '%s': "
                "stored=%s, current=%s. Results may be degraded. "
                "Consider re-ingesting with force_reingest=True.",
                name, stored_model, current_model,
            )
        return collection
    except Exception:
        embedding_function = _get_embedding_adapter()
        return client.get_or_create_collection(
            name=name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": current_model,
            },
            embedding_function=embedding_function,
        )


# ---------------------------------------------------------------------------
# KB Article Ingestion
# ---------------------------------------------------------------------------

def _content_hash(text: str) -> str:
    """Generate a short hash of content for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def ingest_kb_articles(kb_dir: str | None = None, force_reingest: bool = False) -> int:
    """Ingest all KB articles into the vector store. Returns number of documents added.

    Uses content hashing to detect modified articles and update them.
    """
    settings = get_settings()
    kb_dir = kb_dir or str(settings.knowledge_base_dir)
    articles = load_all_kb_articles(kb_dir)
    if not articles:
        return 0

    client = get_chroma_client()

    if force_reingest:
        try:
            client.delete_collection(_KB_COLLECTION)
            logger.info("Deleted existing KB collection for re-ingestion")
        except Exception:
            pass

    collection = get_or_create_collection(client, _KB_COLLECTION)

    existing_data = {}
    if collection.count() > 0:
        all_existing = collection.get(include=["metadatas"])
        for i, doc_id in enumerate(all_existing["ids"]):
            meta = all_existing["metadatas"][i] if all_existing["metadatas"] else {}
            existing_data[doc_id] = meta.get("content_hash", "")

    documents = []
    metadatas = []
    ids = []
    ids_to_delete = []

    for article in articles:
        chunks = _chunk_article(article)
        for chunk_id, chunk_text, chunk_meta in chunks:
            new_hash = _content_hash(chunk_text)
            chunk_meta["content_hash"] = new_hash

            if chunk_id in existing_data:
                if existing_data[chunk_id] == new_hash:
                    continue  # Content unchanged, skip
                else:
                    # Content changed — delete old, re-add
                    ids_to_delete.append(chunk_id)
                    logger.info("KB article chunk updated: %s", chunk_id)

            documents.append(chunk_text)
            metadatas.append(chunk_meta)
            ids.append(chunk_id)

    # Delete outdated chunks
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)

    # Add new/updated chunks
    if documents:
        embedding_function = _get_embedding_adapter()
        batch_size = 50
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            embeddings = embedding_function(batch_docs)
            collection.add(
                documents=batch_docs,
                metadatas=batch_meta,
                ids=batch_ids,
                embeddings=embeddings,
            )

    if documents:
        logger.info("Ingested %d KB chunks (%d updated)", len(documents), len(ids_to_delete))

    return len(documents)


def get_kb_status() -> dict:
    """Return KB article and chunk counts."""
    settings = get_settings()
    articles = load_all_kb_articles(settings.knowledge_base_dir)
    client = get_chroma_client()
    collection = get_or_create_collection(client)
    model_name = _get_embedding_model_name()
    return {
        "article_count": len(articles),
        "chunk_count": collection.count(),
        "persist_dir": settings.chroma_persist_dir,
        "embedding_model": model_name,
        "stored_model": collection.metadata.get("embedding_model", "unknown"),
    }


def _chunk_article(article: KBArticle) -> list[tuple[str, str, dict]]:
    """Split an article into searchable chunks."""
    chunks = []
    base_meta = {
        "filename": article.filename,
        "category": article.category,
        "queue": article.queue,
        "auto_resolvable": str(article.auto_resolvable),
        "title": article.title,
        "language": article.language,
    }
    # Include language in chunk ID to avoid collisions between translations
    id_prefix = (
        f"{article.language}::{article.filename}"
        if article.language != "en"
        else article.filename
    )

    if article.content:
        chunks.append((
            f"{id_prefix}::full",
            f"Title: {article.title}\n\n{article.content}",
            {**base_meta, "chunk_type": "full"},
        ))

    if article.resolution_steps:
        chunks.append((
            f"{id_prefix}::resolution",
            f"Resolution Steps for: {article.title}\n\n{article.resolution_steps}",
            {**base_meta, "chunk_type": "resolution"},
        ))

    if article.response_template:
        chunks.append((
            f"{id_prefix}::response",
            f"Response Template for: {article.title}\n\n{article.response_template}",
            {**base_meta, "chunk_type": "response"},
        ))

    return chunks


def search_kb(
    query: str,
    n_results: int = 3,
    category_filter: str | None = None,
    language: str | None = None,
) -> list[dict]:
    """Search the KB vector store for relevant articles."""
    client = get_chroma_client()
    try:
        collection = get_or_create_collection(client)
    except Exception:
        return []

    if collection.count() == 0:
        return []

    where_filter = None
    conditions = []
    if category_filter:
        conditions.append({"category": category_filter})
    if language:
        conditions.append({"language": language})
    if len(conditions) == 1:
        where_filter = conditions[0]
    elif len(conditions) > 1:
        where_filter = {"$and": conditions}

    try:
        query_embedding = _get_embedding_adapter()([query])[0]
    except Exception as exc:
        logger.debug("KB query embedding unavailable: %s", exc)
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        where=where_filter,
    )

    formatted = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            formatted.append({
                "content": doc,
                "metadata": meta,
                "similarity": 1 - distance,
                "id": results["ids"][0][i] if results["ids"] else "",
            })

    return formatted


# ---------------------------------------------------------------------------
# Ticket Embeddings (for similar ticket search)
# ---------------------------------------------------------------------------

def upsert_ticket_embedding(
    ticket_id: str,
    subject: str,
    description: str,
    status: str = "Open",
    ai_resolution: str = "",
) -> None:
    """Add or update a ticket embedding in the ticket similarity collection."""
    try:
        client = get_chroma_client()
        collection = get_or_create_collection(client, _TICKET_COLLECTION)
        text = f"{subject} {description}"
        embedding_fn = _get_embedding_adapter()
        embeddings = embedding_fn([text])
        collection.upsert(
            ids=[ticket_id],
            documents=[text],
            metadatas=[{
                "ticket_id": ticket_id,
                "subject": subject[:300],
                "description": description[:500],
                "status": status,
                "ai_resolution": ai_resolution[:500],
            }],
            embeddings=embeddings,
        )
    except Exception as exc:
        logger.debug("Failed to upsert ticket embedding for %s: %s", ticket_id, exc)


def search_tickets(
    query: str,
    n_results: int = 5,
) -> list[dict]:
    """Search ticket embeddings for semantically similar tickets."""
    client = get_chroma_client()
    try:
        collection = get_or_create_collection(client, _TICKET_COLLECTION)
    except Exception:
        return []

    if collection.count() == 0:
        return []

    try:
        query_embedding = _get_embedding_adapter()([query])[0]
    except Exception as exc:
        logger.debug("Ticket query embedding unavailable: %s", exc)
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
    )

    formatted = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            formatted.append({
                "content": doc,
                "metadata": meta,
                "similarity": 1 - distance,
                "id": results["ids"][0][i] if results["ids"] else "",
            })

    return formatted
