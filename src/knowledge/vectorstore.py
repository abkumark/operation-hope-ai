"""ChromaDB vector store for Knowledge Base RAG."""

from pathlib import Path
import chromadb
from config.settings import get_settings
from src.llm.embeddings import get_embedding_function
from src.knowledge.kb_ingester import load_all_kb_articles, KBArticle


class LangChainEmbeddingAdapter:
    """Adapter that lets Chroma use LangChain embedding providers."""

    def __init__(self, embedder):
        self.embedder = embedder
        self.is_legacy = False

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self.embedder.embed_documents(list(input))

    def name(self) -> str:
        return "langchain_adapter"


def get_chroma_client() -> chromadb.ClientAPI:
    settings = get_settings()
    persist_dir = settings.chroma_persist_dir
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


def get_or_create_collection(client: chromadb.ClientAPI, name: str = "hope_kb"):
    try:
        return client.get_collection(name=name)
    except Exception:
        embedding_function = LangChainEmbeddingAdapter(get_embedding_function())
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_function,
        )


def ingest_kb_articles(kb_dir: str | None = None, force_reingest: bool = False) -> int:
    """Ingest all KB articles into the vector store. Returns number of documents added."""
    settings = get_settings()
    kb_dir = kb_dir or str(settings.knowledge_base_dir)
    articles = load_all_kb_articles(kb_dir)
    if not articles:
        return 0

    client = get_chroma_client()
    collection = get_or_create_collection(client)

    if force_reingest:
        try:
            client.delete_collection("hope_kb")
        except Exception:
            pass
        collection = get_or_create_collection(client)

    existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()

    documents = []
    metadatas = []
    ids = []

    for article in articles:
        chunks = _chunk_article(article)
        for chunk_id, chunk_text, chunk_meta in chunks:
            if chunk_id not in existing_ids:
                documents.append(chunk_text)
                metadatas.append(chunk_meta)
                ids.append(chunk_id)

    if documents:
        batch_size = 50
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            collection.add(documents=batch_docs, metadatas=batch_meta, ids=batch_ids)

    return len(documents)


def get_kb_status() -> dict:
    """Return KB article and chunk counts."""
    settings = get_settings()
    articles = load_all_kb_articles(settings.knowledge_base_dir)
    client = get_chroma_client()
    collection = get_or_create_collection(client)
    return {
        "article_count": len(articles),
        "chunk_count": collection.count(),
        "persist_dir": settings.chroma_persist_dir,
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
    id_prefix = f"{article.language}::{article.filename}" if article.language != "en" else article.filename

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

    results = collection.query(
        query_texts=[query],
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
