import json
import re
from functools import lru_cache
from pathlib import Path

from app.pipeline.glossary import detect as detect_glossary
from app.pipeline.hadith import fabricated_in, has_attribution, is_approved_text
from app.pipeline.normalize import canonicalize_for_matching, strip_marks
from app.pipeline.quran import QURAN_ATTRIBUTIONS, contains_bare_verse

FATWA_SIGNALS_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "policy" / "fatwa_signals.json"
)
# «هل يحل» alone is not in the verified list yet (it has «هل يحل لي»): kept here until the
# content owner decides (PROGRESS.md, waiting on humans). The other former fallbacks are in the
# file (D-075).
_PENDING_SIGNALS = ("هل يحل",)


class FatwaSignalsError(RuntimeError):
    """The fatwa signals file is missing or holds no phrase: ruling questions would reach the
    LLM as plain text, so the app does not start (fail safe)."""


@lru_cache(maxsize=1)
def load_fatwa_signals():
    """Read once: the segmenter asks per sentence, so a re-read per call cost ~0.5 ms each."""
    if not FATWA_SIGNALS_PATH.exists():
        raise FatwaSignalsError(f"{FATWA_SIGNALS_PATH.name} is missing")
    with open(FATWA_SIGNALS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    phrases = data.get("phrases", [])
    if not any(_usable(phrase.get("text_ar")) for phrase in phrases if isinstance(phrase, dict)):
        raise FatwaSignalsError(f"{FATWA_SIGNALS_PATH.name} holds no phrase")
    return phrases, data.get("exclusions", [])


def _is_fatwa_like(text: str, phrases: list, exclusions: list) -> bool:
    # Every match runs on canonical forms (D-036): a damma, a tatweel or a zero-width joiner
    # inside «ما حكم» must not turn a ruling question into plain text.
    canon = canonicalize_for_matching(text)
    if any(_contains(canon, exc.get("text_ar")) for exc in exclusions):
        return False
    if any(_contains(canon, phrase.get("text_ar")) for phrase in phrases):
        return True

    # Hamza kept: with one alef, «إنا» in a quoted verse followed by «؟» would read «أنا».
    if re.search(r"أنا[^.؟!،؛]*[?؟]", strip_marks(text)):
        return True

    return any(_contains(canon, pending) for pending in _PENDING_SIGNALS)


def _usable(phrase: object) -> bool:
    return isinstance(phrase, str) and bool(phrase.strip())


def _contains(canon_text: str, phrase: object) -> bool:
    """``phrase``, canonicalized, occurs in ``canon_text``; a missing or blank phrase never does."""
    return _usable(phrase) and canonicalize_for_matching(phrase) in canon_text


def is_fatwa_like(text: str) -> bool:
    """The classifier's fatwa test, exclusions first; the segmenter uses it per sentence."""
    phrases, exclusions = load_fatwa_signals()
    return _is_fatwa_like(text, phrases, exclusions)


_QUOTED_HADITH_ATTRIBUTIONS = tuple(
    canonicalize_for_matching(p) for p in ("قال رسول الله", "النبي", "ﷺ")
)


def _is_unquoted_hadith(text: str) -> bool:
    """Attributed to the Prophet ﷺ, or a fabricated saying anywhere, or an approved one
    written alone (D-068): all go to the hadith handler, never to the LLM as plain text."""
    return has_attribution(text) or fabricated_in(text) is not None or is_approved_text(text)


def _scripture_category(text: str) -> str | None:
    """``quran`` or ``hadith`` when the text quotes or attributes scripture, else ``None``."""
    if "﴿" in text and "﴾" in text:
        return "quran"
    canon = canonicalize_for_matching(text)
    if "«" in text and "»" in text and any(a in canon for a in _QUOTED_HADITH_ATTRIBUTIONS):
        return "hadith"
    if any(attr in canon for attr in QURAN_ATTRIBUTIONS):
        return "quran"
    if _is_unquoted_hadith(text):
        return "hadith"
    if contains_bare_verse(text):
        return "quran"
    return None


_SCRIPTURE_LEVELS = {"quran": "A", "hadith": "C"}


def classify(text: str) -> dict:
    # Fatwa first (D-018): a personal ruling question that quotes a verse or hadith must
    # still be referred, never handled as plain scripture.
    if is_fatwa_like(text):
        return {"category": "fatwa_like", "level": "D"}

    scripture = _scripture_category(text)
    if scripture:
        return {"category": scripture, "level": _SCRIPTURE_LEVELS[scripture]}

    terms = detect_glossary(text)
    if terms:
        return {"category": "term_heavy", "level": "A"}

    return {"category": "general", "level": "B"}
