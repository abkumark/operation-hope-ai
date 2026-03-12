"""Language detection for bilingual (EN/ES) support."""

from langdetect import detect, detect_langs, LangDetectException


def detect_language(text: str) -> str:
    """Detect language of text. Returns 'en', 'es', or 'unknown'."""
    if not text or len(text.strip()) < 10:
        return "en"
    try:
        lang = detect(text)
        if lang in ("en", "es"):
            return lang
        return "en"
    except LangDetectException:
        return "en"


def get_language_confidence(text: str) -> dict[str, float]:
    """Get confidence scores for detected languages."""
    if not text or len(text.strip()) < 10:
        return {"en": 1.0}
    try:
        langs = detect_langs(text)
        return {str(lang.lang): lang.prob for lang in langs}
    except LangDetectException:
        return {"en": 1.0}
