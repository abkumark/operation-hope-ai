"""Strategic Insight Generation — the Trend Engine.

Performs bulk analysis of the ticket database to produce:
  A. Trend & Root Cause Analysis  (problem clusters, volume spikes)
  B. Knowledge Gap Identification  (how-to filter, training alerts)
  C. Engineer Performance metrics   (assignment turnaround)
  D. AI vs Human resolution ratio
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

from config.categories import TICKET_CATEGORIES
from src.storage.sqlite_db import get_connection, init_database

logger = logging.getLogger(__name__)

HOW_TO_KEYWORDS = [
    "how to", "how do i", "where do i", "can't find", "cannot find",
    "don't know how", "need help with", "instructions for", "steps to",
    "guide", "tutorial", "walkthrough", "unable to locate", "where is",
    "how can i", "please show", "i don't understand",
]

TRAINING_ALERT_THRESHOLD = 5


@dataclass
class ProblemCluster:
    label: str
    ticket_ids: list[str] = field(default_factory=list)
    count: int = 0
    percentage: float = 0.0
    sample_subjects: list[str] = field(default_factory=list)
    is_spiking: bool = False


@dataclass
class TrainingAlert:
    category: str
    category_name: str
    how_to_count: int
    total_in_category: int
    sample_subjects: list[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class EngineerMetric:
    username: str
    display_name: str
    assigned_count: int = 0
    resolved_count: int = 0
    avg_resolution_hours: float = 0.0
    open_count: int = 0


def _load_tickets() -> list[dict]:
    """Load all ticket rows as dicts for analysis."""
    init_database()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticket_id, subject, description, status, assigned_to, "
            "ai_resolution, classification_json, routing_json, "
            "processed_at, processing_time_ms "
            "FROM tickets ORDER BY processed_at ASC"
        ).fetchall()
    results = []
    for r in rows:
        try:
            cls = json.loads(r["classification_json"])
        except (json.JSONDecodeError, TypeError):
            cls = {}
        try:
            rte = json.loads(r["routing_json"])
        except (json.JSONDecodeError, TypeError):
            rte = {}
        results.append({
            "ticket_id": r["ticket_id"],
            "subject": r["subject"],
            "description": r["description"],
            "status": r["status"],
            "assigned_to": r["assigned_to"],
            "ai_resolution": r["ai_resolution"] or "",
            "category_id": cls.get("category_id", ""),
            "category_name": cls.get("category_name", cls.get("category_id", "")),
            "confidence": cls.get("confidence", 0),
            "routing_action": rte.get("action", ""),
            "queue": rte.get("queue", ""),
            "processed_at": r["processed_at"],
        })
    return results


def _is_how_to(subject: str, description: str, resolution: str) -> bool:
    """Detect if the ticket + resolution is a simple how-to rather than a technical fix."""
    combined = f"{subject} {description} {resolution}".lower()
    return any(kw in combined for kw in HOW_TO_KEYWORDS)


def _subject_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def generate_problem_clusters(tickets: list[dict] | None = None) -> list[ProblemCluster]:
    """Group tickets into problem clusters based on category + subject similarity."""
    if tickets is None:
        tickets = _load_tickets()
    if not tickets:
        return []

    cat_groups: dict[str, list[dict]] = defaultdict(list)
    for t in tickets:
        cat_groups[t["category_id"]].append(t)

    clusters: list[ProblemCluster] = []
    total = len(tickets)

    for cat_id, group in sorted(cat_groups.items(), key=lambda x: -len(x[1])):
        cat_name = TICKET_CATEGORIES[cat_id].name if cat_id in TICKET_CATEGORIES else cat_id
        sub_clusters: list[list[dict]] = []
        used = set()

        for i, t in enumerate(group):
            if i in used:
                continue
            cluster = [t]
            used.add(i)
            for j in range(i + 1, len(group)):
                if j in used:
                    continue
                if _subject_similarity(t["subject"], group[j]["subject"]) > 0.55:
                    cluster.append(group[j])
                    used.add(j)
            sub_clusters.append(cluster)

        for sc in sub_clusters:
            if len(sc) < 2:
                continue
            pct = (len(sc) / total) * 100 if total else 0
            clusters.append(ProblemCluster(
                label=f"{cat_name}: {sc[0]['subject'][:60]}",
                ticket_ids=[t["ticket_id"] for t in sc],
                count=len(sc),
                percentage=round(pct, 1),
                sample_subjects=list({t["subject"] for t in sc[:5]}),
            ))

        if len(group) >= 2 and not any(c for c in clusters if c.label.startswith(cat_name)):
            pct = (len(group) / total) * 100 if total else 0
            clusters.append(ProblemCluster(
                label=cat_name,
                ticket_ids=[t["ticket_id"] for t in group],
                count=len(group),
                percentage=round(pct, 1),
                sample_subjects=list({t["subject"] for t in group[:5]}),
            ))

    clusters.sort(key=lambda c: c.count, reverse=True)

    if len(clusters) > 1:
        avg_size = sum(c.count for c in clusters) / len(clusters)
        for c in clusters:
            if c.count >= avg_size * 2:
                c.is_spiking = True

    return clusters[:10]


def generate_training_alerts(tickets: list[dict] | None = None) -> list[TrainingAlert]:
    """Identify categories where how-to tickets exceed the threshold."""
    if tickets is None:
        tickets = _load_tickets()
    if not tickets:
        return []

    cat_how_to: dict[str, list[dict]] = defaultdict(list)
    cat_total: dict[str, int] = Counter()

    for t in tickets:
        cat_id = t["category_id"]
        cat_total[cat_id] += 1
        if _is_how_to(t["subject"], t["description"], t["ai_resolution"]):
            cat_how_to[cat_id].append(t)

    alerts: list[TrainingAlert] = []
    for cat_id, how_to_tickets in cat_how_to.items():
        if len(how_to_tickets) >= TRAINING_ALERT_THRESHOLD:
            cat_name = TICKET_CATEGORIES[cat_id].name if cat_id in TICKET_CATEGORIES else cat_id
            alerts.append(TrainingAlert(
                category=cat_id,
                category_name=cat_name,
                how_to_count=len(how_to_tickets),
                total_in_category=cat_total[cat_id],
                sample_subjects=list({t["subject"] for t in how_to_tickets[:5]}),
                recommendation=(
                    f"Frequent how-to tickets regarding {cat_name} suggest a need for "
                    f"a targeted FAQ or a 15-minute training session for the team. "
                    f"({len(how_to_tickets)} of {cat_total[cat_id]} tickets are basic how-to requests.)"
                ),
            ))

    alerts.sort(key=lambda a: a.how_to_count, reverse=True)
    return alerts


def generate_engineer_performance(tickets: list[dict] | None = None) -> list[EngineerMetric]:
    """Track per-engineer assignment counts, resolution rates, and open counts."""
    from src.auth import ENGINEER_LIST

    if tickets is None:
        tickets = _load_tickets()

    eng_map: dict[str, EngineerMetric] = {}
    for e in ENGINEER_LIST:
        eng_map[e["username"]] = EngineerMetric(
            username=e["username"], display_name=e["display_name"]
        )

    for t in tickets:
        engineer = t.get("assigned_to", "")
        if not engineer or engineer not in eng_map:
            continue
        m = eng_map[engineer]
        m.assigned_count += 1
        if t["status"] == "Approved":
            m.resolved_count += 1
        elif t["status"] in ("Assigned", "PendingApproval"):
            m.open_count += 1

    return sorted(eng_map.values(), key=lambda m: m.resolved_count, reverse=True)


def generate_ai_vs_human_ratio(tickets: list[dict] | None = None) -> dict:
    """Calculate what percentage of tickets were resolved by AI vs routed to engineers."""
    if tickets is None:
        tickets = _load_tickets()
    if not tickets:
        return {"total": 0, "ai_resolved": 0, "human_resolved": 0, "ai_pct": 0, "human_pct": 0, "pending": 0}

    total = len(tickets)
    ai_resolved = 0
    human_resolved = 0
    pending = 0

    for t in tickets:
        action = t.get("routing_action", "")
        status = t.get("status", "Open")
        assigned = t.get("assigned_to", "")

        if status != "Approved":
            pending += 1
        elif assigned or action == "route_to_human":
            human_resolved += 1
        else:
            ai_resolved += 1

    return {
        "total": total,
        "ai_resolved": ai_resolved,
        "human_resolved": human_resolved,
        "ai_pct": round((ai_resolved / total) * 100, 1) if total else 0,
        "human_pct": round((human_resolved / total) * 100, 1) if total else 0,
        "pending": pending,
    }


LD_QUEUE = "L&D"
LD_CATEGORIES = {
    "course_video_issue", "workplan_navigation", "program_not_showing",
    "stuck_on_task", "hud_certificate", "lms_enrollment", "survey_issue",
    "course_feedback", "course_tools",
}


def generate_ld_insights(tickets: list[dict] | None = None) -> dict:
    """L&D-specific metrics: category breakdown, feedback themes, training recs."""
    if tickets is None:
        tickets = _load_tickets()
    ld_tickets = [t for t in tickets if t["category_id"] in LD_CATEGORIES or t["queue"] == LD_QUEUE]
    if not ld_tickets:
        return {"total": 0, "categories": [], "feedback_count": 0, "recommendations": []}

    cat_counts: Counter = Counter()
    feedback_subjects: list[str] = []
    how_to_count = 0
    for t in ld_tickets:
        cat_counts[t["category_id"]] += 1
        if t["category_id"] == "course_feedback":
            feedback_subjects.append(t["subject"])
        if _is_how_to(t["subject"], t["description"], t["ai_resolution"]):
            how_to_count += 1

    categories = []
    for cat_id, count in cat_counts.most_common():
        cat_name = TICKET_CATEGORIES[cat_id].name if cat_id in TICKET_CATEGORIES else cat_id
        categories.append({"category": cat_id, "name": cat_name, "count": count})

    recs: list[str] = []
    if how_to_count > 2:
        pct = round((how_to_count / len(ld_tickets)) * 100)
        recs.append(
            f"{pct}% of L&D tickets are basic how-to questions. "
            "Consider creating a self-service FAQ or short video walkthroughs."
        )
    if len(feedback_subjects) >= 3:
        recs.append(
            f"{len(feedback_subjects)} course feedback tickets received. "
            "Review course content for accuracy and update materials accordingly."
        )
    top_cat = categories[0] if categories else None
    if top_cat and top_cat["count"] >= 3:
        recs.append(
            f"'{top_cat['name']}' is the most common L&D issue ({top_cat['count']} tickets). "
            "Prioritize a targeted training session or improved documentation for this topic."
        )

    return {
        "total": len(ld_tickets),
        "categories": categories,
        "feedback_count": len(feedback_subjects),
        "how_to_pct": round((how_to_count / len(ld_tickets)) * 100) if ld_tickets else 0,
        "recommendations": recs,
    }


def generate_product_insights(tickets: list[dict] | None = None) -> dict:
    """Product team insights: bug vs user-error, friction points, feature gaps."""
    if tickets is None:
        tickets = _load_tickets()
    if not tickets:
        return {"total": 0, "bug_count": 0, "user_error_count": 0, "friction_points": [], "feature_gaps": []}

    bug_count = sum(1 for t in tickets if t["category_id"] == "system_bug")
    user_error_count = sum(
        1 for t in tickets if _is_how_to(t["subject"], t["description"], t["ai_resolution"])
    )

    cat_stats: dict[str, dict] = {}
    for t in tickets:
        cid = t["category_id"]
        if cid not in cat_stats:
            cat_name = TICKET_CATEGORIES[cid].name if cid in TICKET_CATEGORIES else cid
            auto = TICKET_CATEGORIES[cid].auto_resolvable if cid in TICKET_CATEGORIES else False
            cat_stats[cid] = {"name": cat_name, "total": 0, "auto_resolvable": auto, "low_conf": 0}
        cat_stats[cid]["total"] += 1
        if t["confidence"] < 0.6:
            cat_stats[cid]["low_conf"] += 1

    friction = []
    for cid, s in cat_stats.items():
        if s["total"] >= 2 and not s["auto_resolvable"]:
            friction.append({
                "category": cid,
                "name": s["name"],
                "count": s["total"],
                "reason": "High volume, requires manual handling",
            })
    friction.sort(key=lambda x: x["count"], reverse=True)

    feature_gaps = []
    for cid, s in cat_stats.items():
        if s["low_conf"] >= 2:
            feature_gaps.append({
                "category": cid,
                "name": s["name"],
                "low_confidence_count": s["low_conf"],
                "total": s["total"],
                "reason": "Low AI confidence suggests KB gap or emerging issue",
            })
    feature_gaps.sort(key=lambda x: x["low_confidence_count"], reverse=True)

    return {
        "total": len(tickets),
        "bug_count": bug_count,
        "user_error_count": user_error_count,
        "bug_pct": round((bug_count / len(tickets)) * 100, 1) if tickets else 0,
        "user_error_pct": round((user_error_count / len(tickets)) * 100, 1) if tickets else 0,
        "friction_points": friction[:5],
        "feature_gaps": feature_gaps[:5],
    }


def generate_time_trends(tickets: list[dict] | None = None) -> dict:
    """Week-over-week and category-level time-series analysis.

    Returns volume by week, WoW change percentages, and per-category weekly counts.
    """
    if tickets is None:
        tickets = _load_tickets()
    if not tickets:
        return {
            "weekly_volume": [],
            "wow_change_pct": 0.0,
            "category_weekly": {},
            "busiest_day": None,
        }

    from collections import OrderedDict

    weekly: dict[str, int] = OrderedDict()
    cat_weekly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    daily: dict[str, int] = Counter()

    for t in tickets:
        try:
            dt = datetime.fromisoformat(t["processed_at"])
        except (ValueError, TypeError):
            continue
        iso_year, iso_week, iso_day = dt.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        weekly[week_key] = weekly.get(week_key, 0) + 1
        cat_weekly[t["category_id"]][week_key] = cat_weekly[t["category_id"]].get(week_key, 0) + 1
        day_name = dt.strftime("%A")
        daily[day_name] += 1

    weeks_list = list(weekly.items())
    wow_change = 0.0
    if len(weeks_list) >= 2:
        prev = weeks_list[-2][1]
        curr = weeks_list[-1][1]
        if prev > 0:
            wow_change = round(((curr - prev) / prev) * 100, 1)

    busiest = max(daily, key=daily.get) if daily else None

    # Build per-category weekly series (top 5 categories)
    cat_totals = Counter()
    for cid, weeks_data in cat_weekly.items():
        cat_totals[cid] = sum(weeks_data.values())
    top_cats = [cid for cid, _ in cat_totals.most_common(5)]
    all_weeks = list(weekly.keys())
    cat_weekly_out = {}
    for cid in top_cats:
        cat_name = TICKET_CATEGORIES[cid].name if cid in TICKET_CATEGORIES else cid
        cat_weekly_out[cat_name] = [cat_weekly[cid].get(w, 0) for w in all_weeks]

    return {
        "weekly_volume": [{"week": w, "count": c} for w, c in weekly.items()],
        "wow_change_pct": wow_change,
        "busiest_day": busiest,
        "category_weekly": {
            "weeks": all_weeks,
            "series": cat_weekly_out,
        },
    }


def generate_trend_report() -> dict:
    """Produce the full trend analysis report consumed by the API."""
    tickets = _load_tickets()
    clusters = generate_problem_clusters(tickets)
    training_alerts = generate_training_alerts(tickets)
    engineer_perf = generate_engineer_performance(tickets)
    ai_human = generate_ai_vs_human_ratio(tickets)
    ld = generate_ld_insights(tickets)
    product = generate_product_insights(tickets)
    time_trends = generate_time_trends(tickets)

    top_recurring = [
        {
            "label": c.label,
            "count": c.count,
            "percentage": c.percentage,
            "is_spiking": c.is_spiking,
            "sample_subjects": c.sample_subjects[:3],
        }
        for c in clusters[:5]
    ]

    alerts = [
        {
            "category": a.category,
            "category_name": a.category_name,
            "how_to_count": a.how_to_count,
            "total_in_category": a.total_in_category,
            "sample_subjects": a.sample_subjects[:3],
            "recommendation": a.recommendation,
        }
        for a in training_alerts
    ]

    engineers = [
        {
            "username": e.username,
            "display_name": e.display_name,
            "assigned_count": e.assigned_count,
            "resolved_count": e.resolved_count,
            "open_count": e.open_count,
        }
        for e in engineer_perf
    ]

    return {
        "generated_at": datetime.now().isoformat(),
        "top_recurring_issues": top_recurring,
        "problem_clusters": [
            {
                "label": c.label,
                "count": c.count,
                "percentage": c.percentage,
                "is_spiking": c.is_spiking,
                "sample_subjects": c.sample_subjects[:3],
                "ticket_ids": c.ticket_ids[:10],
            }
            for c in clusters
        ],
        "training_alerts": alerts,
        "engineer_performance": engineers,
        "ai_vs_human": ai_human,
        "ld_insights": ld,
        "product_insights": product,
        "time_trends": time_trends,
    }
