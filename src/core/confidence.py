"""Confidence scoring utilities for classification and routing."""
from typing import Optional


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
