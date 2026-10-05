import json
import re
from functools import lru_cache
from pathlib import Path

from app.pipeline.glossary import detect as detect_glossary
from app.pipeline.normalize import canonicalize_for_matching, strip_marks


@lru_cache(maxsize=1)
def load_fatwa_signals():
    """Read once: the segmenter asks per sentence, so a re-read per call cost ~0.5 ms each."""
    path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "data"
        / "policy"
        / "fatwa_signals.json"
    )
    if not path.exists():
        return [], []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("phrases", []), data.get("exclusions", [])


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

    # Fallback to prompt-specified hardcoded signals if not fully updated in JSON
    hardcoded = ["هل يجوز لي", "ما حكم", "هل يحل", "هل علي", "في حالتي"]
    return any(_contains(canon, hc) for hc in hardcoded)


def _contains(canon_text: str, phrase: object) -> bool:
    """``phrase``, canonicalized, occurs in ``canon_text``; a missing or blank phrase never does."""
    if not isinstance(phrase, str) or not phrase.strip():
        return False
    return canonicalize_for_matching(phrase) in canon_text


def is_fatwa_like(text: str) -> bool:
    """The classifier's fatwa test, exclusions first; the segmenter uses it per sentence."""
    phrases, exclusions = load_fatwa_signals()
    return _is_fatwa_like(text, phrases, exclusions)


# Formulas that attribute the words that follow to God or to the Prophet ﷺ (D-036). Without
# recognised brackets the quoted span cannot be checked, so the segment goes to the Quran or
# hadith handler, which finds no checkable quote: no LLM call, ``output: null``, review.
QURAN_ATTRIBUTIONS = tuple(
    canonicalize_for_matching(p)
    for p in ("قال الله", "قال تعالى", "قوله تعالى", "يقول الله", "يقول تعالى")
)
_HADITH_ATTRIBUTIONS = tuple(
    canonicalize_for_matching(p)
    for p in (
        "قال رسول الله",
        "قال النبي",
        "يقول رسول الله",
        "يقول النبي",
        "قال ﷺ",
        "قال صلى الله عليه وسلم",
    )
)
_QUOTED_HADITH_ATTRIBUTIONS = tuple(
    canonicalize_for_matching(p) for p in ("قال رسول الله", "النبي", "ﷺ")
)


_ORNATE_QUOTE = re.compile(r"\uFD3F(.*?)\uFD3E", re.S)
_ARABIC_LETTER = re.compile(r"[\u0621-\u064A]")


def _scripture_category(text: str) -> str | None:
    """``quran`` or ``hadith`` when the text quotes or attributes scripture, else ``None``."""
    # Ornate brackets mark a verse only around Arabic: an English or French quote of a verse
    # is not checked against the Mushaf (D-051).
    if any(_ARABIC_LETTER.search(q) for q in _ORNATE_QUOTE.findall(text)):
        return "quran"
    canon = canonicalize_for_matching(text)
    if "«" in text and "»" in text and any(a in canon for a in _QUOTED_HADITH_ATTRIBUTIONS):
        return "hadith"
    if any(attr in canon for attr in QURAN_ATTRIBUTIONS):
        return "quran"
    if any(attr in canon for attr in _HADITH_ATTRIBUTIONS):
        return "hadith"
    # Imported here: quran.py imports QURAN_ATTRIBUTIONS from this module.
    from app.pipeline.quran import contains_bare_verse

    if contains_bare_verse(text):
        return "quran"
    # A known hadith quoted with no formula and no «…» (D-052).
    from app.pipeline.hadith import find_bare

    return "hadith" if find_bare(text) is not None else None


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
