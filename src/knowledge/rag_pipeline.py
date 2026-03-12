"""RAG pipeline for generating contextual responses from Knowledge Base."""

from src.llm.provider import get_llm_provider
from src.knowledge.vectorstore import search_kb
from src.core.classifier import ClassificationResult


RESPONSE_GENERATION_PROMPT = """You are a helpful support agent for Operation HOPE, a nonprofit organization that provides financial literacy and empowerment services to underserved communities.

Using the knowledge base context below, generate a professional, empathetic response to the client's support ticket.

Guidelines:
- Be warm, professional, and empathetic
- Provide clear, step-by-step instructions when applicable
- Use simple language (many clients are not tech-savvy)
- Include specific action items the client can follow
- If the response is for a Spanish-speaking client, respond entirely in Spanish
- Do not reference internal processes or systems the client cannot see
- End with an invitation to follow up if the issue persists
- Sign off with "Thank you," (do not include a name - the technician will add their own)

Language: {language}

Knowledge Base Context:
{kb_context}

Support Ticket:
Subject: {subject}
Description: {description}

Classification: {category_name}
Confidence: {confidence}

Generate the response:"""


SPANISH_SYSTEM_PROMPT = """You are a bilingual support agent. When the language is 'es' (Spanish),
respond entirely in Spanish with a warm, professional tone appropriate for Latin American Spanish speakers.
Use "usted" form for formal address."""


def generate_response(
    classification: ClassificationResult,
    subject: str,
    description: str,
) -> dict:
    """Generate a contextual response using RAG over the Knowledge Base.

    Returns dict with:
    - response: the generated response text
    - kb_articles_used: list of KB article references
    - language: response language
    """
    query = f"{subject} {description}"
    kb_results = search_kb(
        query=query,
        n_results=3,
        category_filter=classification.category_id if classification.confidence > 0.6 else None,
        language=classification.language if classification.language != "en" else None,
    )
    # If no results found for non-English, fall back to English articles
    if not kb_results and classification.language != "en":
        kb_results = search_kb(
            query=query,
            n_results=3,
            category_filter=classification.category_id if classification.confidence > 0.6 else None,
        )

    kb_context = _format_kb_context(kb_results)
    kb_articles_used = [r["metadata"].get("title", r["metadata"].get("filename", "")) for r in kb_results]

    if not kb_context:
        kb_context = "No specific knowledge base articles found for this issue."

    language = "Spanish" if classification.language == "es" else "English"
    llm = get_llm_provider()

    prompt = RESPONSE_GENERATION_PROMPT.format(
        language=language,
        kb_context=kb_context,
        subject=subject,
        description=description,
        category_name=classification.category_name,
        confidence=f"{classification.confidence:.0%}",
    )

    system_msg = SPANISH_SYSTEM_PROMPT if classification.language == "es" else \
        "You are a professional, empathetic support agent for Operation HOPE."

    try:
        response_text = llm.chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
        )
    except Exception:
        response_text = _generate_fallback_response(classification, kb_results)

    return {
        "response": response_text,
        "kb_articles_used": kb_articles_used,
        "language": classification.language,
    }


def _format_kb_context(kb_results: list[dict]) -> str:
    """Format KB search results into context for the LLM."""
    if not kb_results:
        return ""

    sections = []
    for i, result in enumerate(kb_results, 1):
        title = result["metadata"].get("title", "Article")
        chunk_type = result["metadata"].get("chunk_type", "full")
        content = result["content"]
        similarity = result.get("similarity", 0)
        sections.append(
            f"--- Article {i}: {title} (relevance: {similarity:.0%}, section: {chunk_type}) ---\n{content}"
        )

    return "\n\n".join(sections)


def _generate_fallback_response(classification: ClassificationResult, kb_results: list[dict]) -> str:
    """Generate a basic response without LLM when API is unavailable."""
    for result in kb_results:
        if result["metadata"].get("chunk_type") == "response":
            return result["content"].replace("Response Template for:", "").strip()

    if classification.language == "es":
        return (
            "Gracias por comunicarse con nosotros. Hemos recibido su solicitud y estamos "
            "investigando el problema. Un miembro de nuestro equipo se pondrá en contacto "
            "con usted pronto.\n\nGracias,"
        )

    return (
        "Thank you for reaching out to us. We have received your request and are looking "
        "into the issue. A member of our team will follow up with you shortly.\n\nThank you,"
    )
