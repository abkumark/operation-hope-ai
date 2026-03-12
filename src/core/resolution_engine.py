"""AI-Powered Resolution Engine.

Finds similar historical tickets, builds context, and generates a structured
resolution using GPT-5.2 (via the configured LLM provider).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from src.storage.sqlite_db import get_connection, init_database

logger = logging.getLogger(__name__)


@dataclass
class SimilarTicket:
    ticket_id: str
    subject: str
    description: str
    similarity: float
    ai_resolution: str = ""
    status: str = "Open"


@dataclass
class ResolutionResult:
    proposed_resolution: str
    reference_tickets: list[SimilarTicket] = field(default_factory=list)
    similar_ticket_ids: list[str] = field(default_factory=list)


def _text_similarity(a: str, b: str) -> float:
    """Quick token-overlap ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_similar_tickets(
    subject: str,
    description: str,
    exclude_ticket_id: str | None = None,
    top_k: int = 3,
) -> list[SimilarTicket]:
    """Search existing tickets for the most similar issues using keyword similarity."""
    init_database()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticket_id, subject, description, ai_resolution, status FROM tickets"
        ).fetchall()

    query_text = f"{subject} {description}"
    scored: list[tuple[float, SimilarTicket]] = []

    for row in rows:
        if exclude_ticket_id and row["ticket_id"] == exclude_ticket_id:
            continue
        candidate = f"{row['subject']} {row['description']}"
        sim = _text_similarity(query_text, candidate)
        if sim > 0.15:
            scored.append((
                sim,
                SimilarTicket(
                    ticket_id=row["ticket_id"],
                    subject=row["subject"],
                    description=row["description"],
                    similarity=round(sim, 3),
                    ai_resolution=row["ai_resolution"] or "",
                    status=row["status"] or "Open",
                ),
            ))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored[:top_k]]


def generate_resolution(
    subject: str,
    description: str,
    category: str,
    similar_tickets: list[SimilarTicket],
) -> ResolutionResult:
    """Call GPT-5.2 to produce a structured resolution from the issue + similar tickets."""
    from src.llm.provider import get_llm_provider

    similar_context = ""
    for i, st in enumerate(similar_tickets, 1):
        resolution_line = f"  Resolution: {st.ai_resolution}" if st.ai_resolution else "  (no resolution yet)"
        similar_context += (
            f"\n--- Historical Ticket #{i} (ID: {st.ticket_id}, Similarity: {st.similarity:.0%}) ---\n"
            f"  Subject: {st.subject}\n"
            f"  Description: {st.description[:300]}\n"
            f"  Status: {st.status}\n"
            f"{resolution_line}\n"
        )

    if not similar_context:
        similar_context = "\n(No similar historical tickets found.)\n"

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert IT support resolution engine for Operation HOPE, "
                "a non-profit that provides financial coaching and empowerment services. "
                "Given a new support ticket and any similar historical tickets, produce a "
                "structured JSON response with:\n"
                '  "proposed_resolution": a clear, step-by-step resolution guide (numbered steps),\n'
                '  "reference_ticket_ids": an array of ticket IDs from the historical tickets that were most useful.\n'
                "If no similar tickets are relevant, provide a resolution based on general best practices "
                "for the given category. Always be professional, empathetic, and action-oriented."
            ),
        },
        {
            "role": "user",
            "content": (
                f"NEW TICKET:\n"
                f"  Subject: {subject}\n"
                f"  Description: {description}\n"
                f"  Category: {category}\n"
                f"\nSIMILAR HISTORICAL TICKETS:{similar_context}\n"
                f"Produce a JSON object with 'proposed_resolution' (string with numbered steps) "
                f"and 'reference_ticket_ids' (array of ticket ID strings)."
            ),
        },
    ]

    try:
        llm = get_llm_provider()
        raw = llm.chat_json(messages, temperature=0.2, max_tokens=1500)
        data = json.loads(raw)
        proposed = data.get("proposed_resolution", "")
        refs = data.get("reference_ticket_ids", [])
        if not isinstance(refs, list):
            refs = []
        refs = [str(r) for r in refs]
    except Exception as exc:
        logger.warning("LLM resolution generation failed, using fallback: %s", exc)
        proposed = _fallback_resolution(subject, description, category, similar_tickets)
        refs = [st.ticket_id for st in similar_tickets]

    return ResolutionResult(
        proposed_resolution=proposed,
        reference_tickets=similar_tickets,
        similar_ticket_ids=refs if refs else [st.ticket_id for st in similar_tickets],
    )


def _fallback_resolution(
    subject: str,
    description: str,
    category: str,
    similar_tickets: list[SimilarTicket],
) -> str:
    """Rule-based fallback when the LLM is unavailable."""
    steps = [
        f"1. Acknowledge the issue: \"{subject}\"",
        f"2. Category identified: {category}",
        "3. Review the issue description for specific error messages or account details.",
    ]
    if similar_tickets:
        ref_ids = ", ".join(st.ticket_id for st in similar_tickets)
        steps.append(f"4. Reference similar tickets ({ref_ids}) for resolution patterns.")
        for st in similar_tickets:
            if st.ai_resolution:
                steps.append(f"   - {st.ticket_id}: {st.ai_resolution[:120]}...")
                break
    steps.append(f"{len(steps) + 1}. Escalate to the appropriate team if the above steps do not resolve the issue.")
    return "\n".join(steps)
