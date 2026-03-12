"""Knowledge Base article ingestion and management."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KBArticle:
    filename: str
    title: str
    category: str
    ticket_type: str
    auto_resolvable: bool
    queue: str
    last_updated: str
    content: str
    resolution_steps: str
    response_template: str
    internal_notes: str
    language: str = "en"
    metadata: dict = field(default_factory=dict)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()

    metadata = {}
    for line in frontmatter_text.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value.lower() in ("true", "false"):
                value = value.lower() == "true"
            metadata[key] = value

    return metadata, body


def extract_section(body: str, section_name: str) -> str:
    """Extract content under a specific ## heading."""
    pattern = rf"## {re.escape(section_name)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, body, re.DOTALL)
    return match.group(1).strip() if match else ""


def load_kb_article(filepath: Path) -> KBArticle:
    """Load a single KB article from a markdown file."""
    content = filepath.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)

    return KBArticle(
        filename=filepath.name,
        title=metadata.get("title", filepath.stem.replace("_", " ").title()),
        category=metadata.get("category", "unknown"),
        ticket_type=metadata.get("type", "external"),
        auto_resolvable=metadata.get("auto_resolvable", False),
        queue=metadata.get("queue", "IT Support"),
        last_updated=metadata.get("last_updated", ""),
        content=body,
        resolution_steps=extract_section(body, "Resolution Steps"),
        response_template=extract_section(body, "Response Template"),
        internal_notes=extract_section(body, "Internal Notes"),
        language=metadata.get("language", "en"),
        metadata=metadata,
    )


def load_all_kb_articles(kb_dir: Path | str = "data/knowledge_base") -> list[KBArticle]:
    """Load all KB articles from the knowledge base directory, including language subdirectories."""
    kb_path = Path(kb_dir)
    if not kb_path.exists():
        return []

    articles = []
    # Load top-level articles
    for filepath in sorted(kb_path.glob("*.md")):
        try:
            article = load_kb_article(filepath)
            articles.append(article)
        except Exception as e:
            print(f"Warning: Failed to load {filepath}: {e}")

    # Load articles from language subdirectories (e.g., es/, fr/)
    for subdir in sorted(kb_path.iterdir()):
        if subdir.is_dir():
            for filepath in sorted(subdir.glob("*.md")):
                try:
                    article = load_kb_article(filepath)
                    # Infer language from directory name if not set in frontmatter
                    if article.language == "en" and subdir.name != "en":
                        article.language = subdir.name
                    articles.append(article)
                except Exception as e:
                    print(f"Warning: Failed to load {filepath}: {e}")

    return articles


def get_article_for_category(articles: list[KBArticle], category_id: str) -> list[KBArticle]:
    """Find KB articles matching a specific category."""
    return [a for a in articles if a.category == category_id]
