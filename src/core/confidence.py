"""Confidence scoring utilities for classification and routing.

Includes LLM confidence calibration (LLMs are typically overconfident),
keyword cross-validation, and feedback-aware threshold adjustment.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def calibrate_confidence(
    raw_score: float,
    min_score: float = 0.0,
    max_score: float = 1.0,
) -> float:
    """Calibrate a raw confidence score to the [0, 1] range."""
    if raw_score <= min_score:
        return 0.0
    if raw_score >= max_score:
        return 1.0
    return (raw_score - min_score) / (max_score - min_score)


def normalize_confidence(score: float) -> float:
    """Clamp confidence to valid [0, 1] range."""
    return max(0.0, min(1.0, score))


def calibrate_llm_confidence(raw_score: float) -> float:
    """Apply calibration to LLM self-reported confidence.

    LLMs are notoriously overconfident — a self-reported 0.95 is often
    closer to 0.80 in actual accuracy. This applies a conservative
    calibration curve.
    """
    raw_score = normalize_confidence(raw_score)
    # Mild compression: reduces high scores more than low scores
    # Maps: 0.0->0.0, 0.5->0.45, 0.8->0.72, 0.95->0.86, 1.0->0.90
    calibrated = raw_score * (0.9 if raw_score > 0.5 else 1.0)
    return normalize_confidence(calibrated)


def combine_confidence_scores(
    llm_confidence: float,
    keyword_match_score: Optional[float] = None,
    keyword_weight: float = 0.2,
) -> float:
    """
    Combine LLM confidence with optional keyword match score.
    Uses weighted average when keyword score is provided.
    """
    llm_confidence = normalize_confidence(llm_confidence)
    if keyword_match_score is None:
        return llm_confidence

    keyword_match_score = normalize_confidence(keyword_match_score)
    # Weighted average: LLM gets (1 - keyword_weight), keyword gets keyword_weight
    combined = (1 - keyword_weight) * llm_confidence + keyword_weight * keyword_match_score
    return normalize_confidence(combined)


def should_auto_resolve(
    confidence: float,
    threshold: float = 0.85,
) -> bool:
    """Determine if confidence is high enough for auto-resolution."""
    return normalize_confidence(confidence) >= threshold


def get_feedback_adjusted_threshold(
    base_threshold: float,
    category_id: str,
) -> float:
    """Adjust auto-resolve threshold based on historical feedback for a category.

    If a category has poor satisfaction, raises the threshold to require more
    confidence before auto-resolving. Returns the adjusted threshold.
    """
    try:
        from src.storage.sqlite_db import get_feedback_by_category
        feedback_data = get_feedback_by_category()
        for entry in feedback_data:
            if entry.get("category_id") == category_id:
                total = entry.get("total_feedback", 0)
                sat_rate = entry.get("satisfaction_rate", 1.0)
                if total >= 5 and sat_rate < 0.7:
                    # Poor satisfaction — raise threshold by up to 0.10
                    penalty = min((0.7 - sat_rate) * 0.5, 0.10)
                    adjusted = min(base_threshold + penalty, 0.98)
                    logger.info(
                        "Feedback-adjusted threshold for %s: %.2f -> %.2f "
                        "(sat_rate=%.2f, n=%d)",
                        category_id, base_threshold, adjusted, sat_rate, total,
                    )
                    return adjusted
                break
    except Exception:
        pass
    return base_threshold
