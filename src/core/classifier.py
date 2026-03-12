"""AI-powered ticket classification engine."""

import json
from dataclasses import dataclass

from config.categories import TICKET_CATEGORIES, TicketCategory
from config.routing_rules import is_hr_ticket
from src.llm.provider import get_llm_provider
from src.core.language_detector import detect_language
from src.core.confidence import combine_confidence_scores, normalize_confidence


@dataclass
class ClassificationResult:
    category_id: str
    category_name: str
    confidence: float
    language: str
    sentiment: str  # "positive", "neutral", "negative", "frustrated"
    urgency: str  # "low", "medium", "high", "critical"
    is_hr: bool
    summary: str
    raw_text: str


CLASSIFICATION_PROMPT = """You are a support ticket classifier for Operation HOPE, a nonprofit that provides financial literacy and empowerment services. Your job is to classify support tickets into the correct category.

Available categories:
{categories}

Analyze the following support ticket and classify it. Respond in JSON format with these fields:
- category_id: the category ID from the list above
- confidence: a float between 0.0 and 1.0 indicating your confidence
- sentiment: one of "positive", "neutral", "negative", "frustrated"
- urgency: one of "low", "medium", "high", "critical"
  - low: informational request
  - medium: single client experiencing friction
  - high: multiple clients or stakeholders affected
  - critical: system-wide stoppage
- summary: a one-sentence summary of the issue
- is_hr: boolean, true if this is an HR-related ticket (payroll, benefits, employee complaints, etc.)

Support Ticket:
Subject: {subject}
Description: {description}
Submitter: {submitter}
"""


def _build_categories_text() -> str:
    lines = []
    for cat_id, cat in TICKET_CATEGORIES.items():
        lines.append(f"- {cat_id}: {cat.description} (type: {cat.ticket_type})")
    return "\n".join(lines)


def classify_ticket(
    subject: str,
    description: str,
    submitter: str = "Unknown",
) -> ClassificationResult:
    """Classify a support ticket using AI with keyword fallback."""
    full_text = f"{subject} {description}".strip()

    if is_hr_ticket(full_text):
        return ClassificationResult(
            category_id="hr_excluded",
            category_name="HR (Excluded)",
            confidence=0.95,
            language=detect_language(full_text),
            sentiment="neutral",
            urgency="medium",
            is_hr=True,
            summary="HR-related ticket - excluded from AI processing",
            raw_text=full_text,
        )

    try:
        llm = get_llm_provider()
        result = _classify_with_llm(llm, subject, description, submitter)
        if result:
            result.raw_text = full_text
            # Boost confidence by combining LLM score with keyword match
            keyword_score = _compute_keyword_score(full_text, result.category_id)
            if keyword_score > 0:
                result.confidence = combine_confidence_scores(
                    result.confidence, keyword_score
                )
            return result
    except Exception:
        pass

    return _classify_with_keywords(subject, description, submitter)


def _classify_with_llm(llm, subject: str, description: str, submitter: str) -> ClassificationResult | None:
    categories_text = _build_categories_text()
    prompt = CLASSIFICATION_PROMPT.format(
        categories=categories_text,
        subject=subject,
        description=description,
        submitter=submitter,
    )

    messages = [
        {"role": "system", "content": "You are a precise ticket classifier. Always respond with valid JSON."},
        {"role": "user", "content": prompt},
    ]

    response = llm.chat_json(messages, temperature=0.1, max_tokens=500)
    data = json.loads(response)

    category_id = data.get("category_id", "no_information")
    if category_id not in TICKET_CATEGORIES:
        category_id = "no_information"

    cat = TICKET_CATEGORIES[category_id]
    language = detect_language(f"{subject} {description}")

    return ClassificationResult(
        category_id=category_id,
        category_name=cat.name,
        confidence=min(max(float(data.get("confidence", 0.5)), 0.0), 1.0),
        language=language,
        sentiment=data.get("sentiment", "neutral"),
        urgency=data.get("urgency", "medium"),
        is_hr=bool(data.get("is_hr", False)),
        summary=data.get("summary", ""),
        raw_text="",
    )


def _compute_keyword_score(text: str, category_id: str) -> float:
    """Compute a keyword match score for a given category against the text."""
    cat = TICKET_CATEGORIES.get(category_id)
    if not cat or not cat.keywords:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for kw in cat.keywords if kw.lower() in text_lower)
    if matches == 0:
        return 0.0
    return min(0.3 + (matches * 0.15), 0.9)


def _classify_with_keywords(subject: str, description: str, submitter: str) -> ClassificationResult:
    """Fallback keyword-based classification."""
    full_text = f"{subject} {description}".lower()
    language = detect_language(f"{subject} {description}")

    best_match = "no_information"
    best_score = 0

    for cat_id, cat in TICKET_CATEGORIES.items():
        score = sum(1 for kw in cat.keywords if kw.lower() in full_text)
        if score > best_score:
            best_score = score
            best_match = cat_id

    cat = TICKET_CATEGORIES[best_match]
    confidence = min(0.3 + (best_score * 0.15), 0.75) if best_score > 0 else 0.2

    return ClassificationResult(
        category_id=best_match,
        category_name=cat.name,
        confidence=confidence,
        language=language,
        sentiment="neutral",
        urgency="medium",
        is_hr=False,
        summary=f"Keyword match: {best_match} (score: {best_score})",
        raw_text=f"{subject} {description}",
    )
