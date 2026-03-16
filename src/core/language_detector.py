"""Language detection for bilingual (EN/ES) support.

Improved: Lowered the minimum text length for detection and added
common Spanish word heuristic for very short texts.
"""

from langdetect import detect, detect_langs, LangDetectException


# Common Spanish words that appear in short support messages
_SPANISH_INDICATORS = {
    "ayuda", "hola", "gracias", "por favor", "necesito", "problema",
    "cuenta", "contraseña", "acceso", "no puedo", "mi cuenta",
}


def detect_language(text: str) -> str:
    """Detect language of text. Returns 'en', 'es', or 'unknown'.

    For very short texts (< 20 chars), uses a Spanish keyword heuristic
    before falling back to 'en', since langdetect is unreliable on short strings.
    """
    if not text or len(text.strip()) < 3:
        return "en"

    stripped = text.strip()

    # For very short text, use keyword heuristic
    if len(stripped) < 20:
        lower = stripped.lower()
        if any(word in lower for word in _SPANISH_INDICATORS):
            return "es"
        # Try langdetect anyway — it sometimes works on short text
        try:
            lang = detect(stripped)
            if lang == "es":
                return "es"
        except LangDetectException:
            pass
        return "en"

    # Standard detection for longer text
    try:
        lang = detect(stripped)
        if lang in ("en", "es"):
            return lang
        return "en"
    except LangDetectException:
        return "en"


def get_language_confidence(text: str) -> dict[str, float]:
    """Get confidence scores for detected languages."""
    if not text or len(text.strip()) < 3:
        return {"en": 1.0}
    try:
        langs = detect_langs(text)
        return {str(lang.lang): lang.prob for lang in langs}
    except LangDetectException:
        return {"en": 1.0}
