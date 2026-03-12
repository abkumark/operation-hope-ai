"""Analytics insights engine for ticket trend analysis and knowledge gap detection."""
from collections import Counter

from config.categories import TICKET_CATEGORIES
from src.core.router import RoutingAction
from src.workflow.approval import get_all_approvals, get_pending_approvals
from src.workflow.pipeline import PipelineResult, get_processed_tickets


def get_category_distribution() -> dict[str, int]:
    """Get ticket count per category."""
    tickets = get_processed_tickets()
    return dict(Counter(t.classification.category_id for t in tickets))


def get_routing_distribution() -> dict[str, int]:
    """Get count per routing action."""
    tickets = get_processed_tickets()
    return dict(Counter(t.routing.action.value for t in tickets))


def get_language_distribution() -> dict[str, int]:
    """Get ticket count per language."""
    tickets = get_processed_tickets()
    return dict(Counter(t.classification.language for t in tickets))


def get_urgency_distribution() -> dict[str, int]:
    """Get ticket count per urgency level."""
    tickets = get_processed_tickets()
    return dict(Counter(t.classification.urgency for t in tickets))


def get_sentiment_distribution() -> dict[str, int]:
    """Get ticket count per sentiment."""
    tickets = get_processed_tickets()
    return dict(Counter(t.classification.sentiment for t in tickets))


def get_queue_distribution() -> dict[str, int]:
    """Get ticket count per queue."""
    tickets = get_processed_tickets()
    return dict(Counter(t.routing.queue for t in tickets))


def detect_knowledge_gaps() -> list[dict]:
    """Identify categories with low confidence or no KB coverage."""
    tickets = get_processed_tickets()
    category_confidences: dict[str, list[float]] = {}
    for t in tickets:
        cat = t.classification.category_id
        category_confidences.setdefault(cat, []).append(t.classification.confidence)

    gaps = []
    for cat_id, confidences in category_confidences.items():
        avg_conf = sum(confidences) / len(confidences)
        cat = TICKET_CATEGORIES.get(cat_id)
        if avg_conf < 0.7:
            gaps.append({
                "category": cat_id,
                "category_name": cat.name if cat else cat_id,
                "avg_confidence": avg_conf,
                "ticket_count": len(confidences),
                "recommendation": "Add or improve KB articles for this category",
            })

    # Also check categories with zero tickets but have KB articles
    seen = set(category_confidences.keys())
    for cat_id, cat in TICKET_CATEGORIES.items():
        if cat_id not in seen and cat.kb_articles:
            gaps.append({
                "category": cat_id,
                "category_name": cat.name,
                "avg_confidence": 0.0,
                "ticket_count": 0,
                "recommendation": "No tickets seen for this category - verify KB relevance",
            })

    return sorted(gaps, key=lambda x: x["avg_confidence"])


def get_auto_resolution_metrics() -> dict:
    """Calculate AI draft and send metrics."""
    tickets = get_processed_tickets()
    if not tickets:
        return {"total": 0, "ai_drafted": 0, "draft_rate": 0.0, "sent": 0, "sent_rate": 0.0}

    approvals = get_all_approvals()
    ai_drafted = [t for t in tickets if t.routing.action == RoutingAction.AUTO_RESOLVE]
    sent = [a for a in approvals if a.status.value == "sent"]
    pending = [a for a in approvals if a.status.value == "pending_approval"]
    return {
        "total": len(tickets),
        "ai_drafted": len(ai_drafted),
        "draft_rate": len(ai_drafted) / len(tickets) if tickets else 0,
        "sent": len(sent),
        "sent_rate": len(sent) / len(tickets) if tickets else 0,
        "pending_approval": len(pending),
        "avg_confidence": (
            sum(t.classification.confidence for t in ai_drafted) / len(ai_drafted)
            if ai_drafted
            else 0
        ),
        "avg_processing_ms": (
            sum(t.processing_time_ms for t in ai_drafted) / len(ai_drafted)
            if ai_drafted
            else 0
        ),
    }


def get_processing_time_stats() -> dict:
    """Get processing time statistics."""
    tickets = get_processed_tickets()
    if not tickets:
        return {"avg_ms": 0, "min_ms": 0, "max_ms": 0, "total": 0}
    times = [t.processing_time_ms for t in tickets]
    return {
        "avg_ms": sum(times) / len(times),
        "min_ms": min(times),
        "max_ms": max(times),
        "total": len(times),
    }


def detect_submitter_knowledge_gaps() -> list[dict]:
    """Identify submitters or submitter groups with recurring issues.

    Groups tickets by submitter email and detects those who submit repeated
    tickets in the same category – a signal they need targeted training.
    """
    tickets = get_processed_tickets()
    if not tickets:
        return []

    submitter_cats: dict[str, Counter] = {}
    for t in tickets:
        email = getattr(t, "submitter_email", "") or ""
        if not email:
            continue
        submitter_cats.setdefault(email, Counter())
        submitter_cats[email][t.classification.category_id] += 1

    gaps = []
    for email, cat_counter in submitter_cats.items():
        for cat_id, count in cat_counter.items():
            if count >= 2:
                cat = TICKET_CATEGORIES.get(cat_id)
                gaps.append({
                    "submitter_email": email,
                    "category_id": cat_id,
                    "category_name": cat.name if cat else cat_id,
                    "repeat_count": count,
                    "recommendation": (
                        f"Submitter has submitted {count} tickets for "
                        f"{cat.name if cat else cat_id}. Consider sending "
                        f"targeted training material or a self-service guide."
                    ),
                })
    return sorted(gaps, key=lambda x: x["repeat_count"], reverse=True)


def detect_program_knowledge_gaps() -> list[dict]:
    """Identify which program queues/categories have the most how-to or
    low-confidence tickets — a proxy for 'which programs confuse users most'.
    """
    tickets = get_processed_tickets()
    if not tickets:
        return []

    HOW_TO_KW = [
        "how to", "how do i", "where do i", "can't find", "cannot find",
        "don't know how", "need help with", "instructions for",
    ]

    queue_stats: dict[str, dict] = {}
    for t in tickets:
        q = t.routing.queue
        if q not in queue_stats:
            queue_stats[q] = {"total": 0, "how_to": 0, "low_conf": 0, "categories": Counter()}
        queue_stats[q]["total"] += 1
        queue_stats[q]["categories"][t.classification.category_id] += 1
        text = f"{t.subject} {t.description}".lower()
        if any(kw in text for kw in HOW_TO_KW):
            queue_stats[q]["how_to"] += 1
        if t.classification.confidence < 0.6:
            queue_stats[q]["low_conf"] += 1

    results = []
    for queue, stats in queue_stats.items():
        total = stats["total"]
        if total < 2:
            continue
        top_cat_id = stats["categories"].most_common(1)[0][0]
        cat = TICKET_CATEGORIES.get(top_cat_id)
        how_to_pct = round((stats["how_to"] / total) * 100)
        results.append({
            "queue": queue,
            "total_tickets": total,
            "how_to_count": stats["how_to"],
            "how_to_pct": how_to_pct,
            "low_confidence_count": stats["low_conf"],
            "top_category": cat.name if cat else top_cat_id,
            "recommendation": (
                f"{queue} queue: {how_to_pct}% how-to questions "
                f"(top issue: {cat.name if cat else top_cat_id}). "
                + ("Consider targeted training or FAQ content." if how_to_pct > 30 else "")
            ),
        })
    return sorted(results, key=lambda x: x["how_to_count"], reverse=True)


def generate_actionable_insights() -> list[dict]:
    """Produce concrete recommendations from observed ticket patterns."""
    tickets = get_processed_tickets()
    if not tickets:
        return []

    insights: list[dict] = []
    category_distribution = get_category_distribution()
    routing_distribution = get_routing_distribution()
    language_distribution = get_language_distribution()
    knowledge_gaps = detect_knowledge_gaps()
    pending_approvals = get_pending_approvals()

    if category_distribution:
        top_category, top_count = max(category_distribution.items(), key=lambda item: item[1])
        category_name = TICKET_CATEGORIES.get(top_category).name if top_category in TICKET_CATEGORIES else top_category
        insights.append(
            {
                "type": "volume",
                "title": f"Top recurring issue: {category_name}",
                "detail": f"{top_count} tickets were classified into {category_name}.",
                "recommendation": "Consider improving KB coverage, self-service guidance, or targeted product fixes for this issue.",
            }
        )

    human_routed = routing_distribution.get(RoutingAction.ROUTE_TO_HUMAN.value, 0)
    if human_routed:
        insights.append(
            {
                "type": "routing",
                "title": "High manual handling demand",
                "detail": f"{human_routed} tickets required full human handling.",
                "recommendation": "Review low-confidence categories and add examples/KB content to increase automation coverage.",
            }
        )

    if pending_approvals:
        insights.append(
            {
                "type": "approval",
                "title": "Approval queue backlog",
                "detail": f"{len(pending_approvals)} AI-drafted tickets are waiting for admin/engineer review.",
                "recommendation": "Introduce approval SLAs, queue ownership, or a dedicated approval dashboard.",
            }
        )

    if language_distribution.get("es", 0):
        insights.append(
            {
                "type": "language",
                "title": "Spanish-language support demand detected",
                "detail": f"{language_distribution.get('es', 0)} tickets were submitted in Spanish.",
                "recommendation": "Expand bilingual KB content and response templates for the highest-volume categories.",
            }
        )

    for gap in knowledge_gaps[:3]:
        if gap["ticket_count"] > 0:
            insights.append(
                {
                    "type": "knowledge_gap",
                    "title": f"Knowledge gap: {gap['category_name']}",
                    "detail": f"Average confidence is {gap['avg_confidence']:.0%} across {gap['ticket_count']} tickets.",
                    "recommendation": gap["recommendation"],
                }
            )

    return insights
