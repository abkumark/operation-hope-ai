"""Report generation for stakeholders."""
from datetime import datetime

from src.analytics.insights_engine import (
    detect_knowledge_gaps,
    detect_program_knowledge_gaps,
    detect_submitter_knowledge_gaps,
    generate_actionable_insights,
    get_auto_resolution_metrics,
    get_category_distribution,
    get_processing_time_stats,
    get_queue_distribution,
    get_routing_distribution,
    get_language_distribution,
    get_sentiment_distribution,
    get_urgency_distribution,
)
from src.storage.sqlite_db import get_feedback_summary
from src.workflow.pipeline import get_pipeline_stats


def generate_summary_report() -> dict:
    """Generate a comprehensive summary report."""
    stats = get_pipeline_stats()
    auto_metrics = get_auto_resolution_metrics()
    time_stats = get_processing_time_stats()
    gaps = detect_knowledge_gaps()
    insights = generate_actionable_insights()

    return {
        "generated_at": datetime.now().isoformat(),
        "overview": stats,
        "ai_assistance": auto_metrics,
        "processing_times": time_stats,
        "category_distribution": get_category_distribution(),
        "routing_distribution": get_routing_distribution(),
        "queue_distribution": get_queue_distribution(),
        "language_distribution": get_language_distribution(),
        "urgency_distribution": get_urgency_distribution(),
        "sentiment_distribution": get_sentiment_distribution(),
        "knowledge_gaps": gaps,
        "knowledge_gap_count": len(gaps),
        "submitter_knowledge_gaps": detect_submitter_knowledge_gaps()[:10],
        "program_knowledge_gaps": detect_program_knowledge_gaps(),
        "resolution_feedback": get_feedback_summary(),
        "actionable_insights": insights,
    }


def format_report_text(report: dict) -> str:
    """Format a report dictionary as human-readable text."""
    lines = [
        "=" * 60,
        "HOPE AI - Support Analytics Report",
        f"Generated: {report['generated_at']}",
        "=" * 60,
        "",
    ]

    overview = report.get("overview", {})
    lines.append("TICKET OVERVIEW")
    lines.append(f"  Total Processed:   {overview.get('total', 0)}")
    lines.append(f"  Auto-Resolved:     {overview.get('auto_resolved', 0)}")
    lines.append(f"  Suggested Review:  {overview.get('suggested_review', 0)}")
    lines.append(f"  Routed to Human:   {overview.get('routed_to_human', 0)}")
    lines.append(f"  HR Excluded:       {overview.get('hr_excluded', 0)}")
    lines.append(f"  Escalated:         {overview.get('escalated', 0)}")
    lines.append("")

    auto = report.get("ai_assistance", {})
    rate = auto.get("draft_rate", 0)
    lines.append("AI ASSISTANCE METRICS")
    lines.append(f"  AI Draft Rate:         {rate:.1%}")
    lines.append(f"  Sent After Review:     {auto.get('sent_rate', 0):.1%}")
    lines.append(f"  Pending Approval:      {auto.get('pending_approval', 0)}")
    lines.append(f"  Avg Confidence:        {auto.get('avg_confidence', 0):.1%}")
    lines.append(f"  Avg Processing Time:   {auto.get('avg_processing_ms', 0):.0f}ms")
    lines.append("")

    gaps = report.get("knowledge_gaps", [])
    if gaps:
        lines.append(f"KNOWLEDGE GAPS ({len(gaps)} detected)")
        for gap in gaps[:5]:
            lines.append(
                f"  - {gap['category_name']}: avg confidence "
                f"{gap['avg_confidence']:.1%} ({gap['ticket_count']} tickets)"
            )
    lines.append("")

    cats = report.get("category_distribution", {})
    if cats:
        lines.append("TOP CATEGORIES")
        for cat, count in sorted(cats.items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"  {cat}: {count}")
        lines.append("")

    insights = report.get("actionable_insights", [])
    if insights:
        lines.append("ACTIONABLE INSIGHTS")
        for insight in insights[:5]:
            lines.append(f"  - {insight['title']}: {insight['recommendation']}")

    return "\n".join(lines)
