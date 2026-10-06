"""Verifier: term check + back-translation + judge, combined into confidence (D-004).

A check that cannot run (provider unset, call failed, no data) scores 0, never 1:
an unverified segment must end in review (D-021).
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.llm.base import JsonCompleter, LLMResult
from app.pipeline.glossary import get_index
from app.pipeline.injection import neutralize_tags
from app.pipeline.normalize import normalize_text
from app.schemas import Flag, LockedTerm, TargetLang

logger = logging.getLogger("app.pipeline.verifier")

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
TERM_WEIGHT, BT_WEIGHT, JUDGE_WEIGHT = 0.35, 0.25, 0.40
THRESHOLD = 0.75
TERM_FAILURE_CAP = 0.74
NGRAM = 3
# v2 restate the data-only rule after the tags; the judge scores steering text 0 (D-037).
BACKTRANSLATE_PROMPT = "backtranslate_v2.txt"
JUDGE_PROMPT = "judge_v2.txt"
_NON_WORD_RE = re.compile(r"[\W_]+")

UsageHook = Callable[[LLMResult[Any]], None]


class BackTranslation(BaseModel):
    arabic_text: str


class JudgeOutput(BaseModel):
    score: float


def find_whole_word(word: str, text: str) -> re.Match[str] | None:
    """Case-insensitive whole-word match ("tax" is not in "syntax"); ``\\w`` is Unicode-aware."""
    if not word.strip():
        return None
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.IGNORECASE)


def find_rendering(rendering: str, text: str) -> re.Match[str] | None:
    """The approved rendering as a whole word, optionally plural (D-065): «prophets» has
    «prophet», «Hajjaj» does not have «Hajj». The match is taken from ``text`` itself, so a
    mark never shifts when lowercasing changes a string's length («İ»)."""
    if not rendering.strip():
        return None
    pattern = rf"(?<!\w){re.escape(rendering)}(?:e?s|x)?(?!\w)"
    return re.search(pattern, text, re.IGNORECASE)


def _trigrams(text: str) -> Counter[str]:
    collapsed = _NON_WORD_RE.sub(" ", normalize_text(text)).strip()
    padded = f" {collapsed} "
    return Counter(padded[i : i + NGRAM] for i in range(len(padded) - NGRAM + 1))


def backtranslation_similarity(original: str, back: str) -> float:
    """Dice coefficient over normalized character trigrams, from 0 to 1 (deterministic)."""
    left, right = _trigrams(original), _trigrams(back)
    total = sum(left.values()) + sum(right.values())
    if not original.strip() or not back.strip() or total == 0:
        return 0.0
    return 2 * sum((left & right).values()) / total


def _lang_name(target_lang: TargetLang) -> str:
    return "English" if target_lang == "en" else "French"


def _prompt(name: str, **fields: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").format(**fields)


def _term_check(
    output: str,
    target_lang: TargetLang,
    locked_terms: Sequence[LockedTerm],
    term_ids: Sequence[str] = (),
) -> tuple[float, list[str], list[Flag]]:
    """(a) Required rendering of each locked term present (marks = exact rendered strings),
    and no ``avoid`` word for any detected term, locked or not (D-058: the ``context`` terms
    are not locked, yet «mohammedanism» or «meditation» is wrong in every sense)."""
    score, marks, flags = 1.0, [], []
    for term in locked_terms:
        found = find_rendering(term.out, output)
        if found is not None:
            marks.append(found.group(0))
        else:
            score = 0.0
            flags.append(Flag(type="warn", key="term_check_failed", detail=term.ar))
    entries = get_index().entries
    checked = {term.glossary_id: term.ar for term in locked_terms}
    for term_id in term_ids:
        checked.setdefault(term_id, (entries.get(term_id) or {}).get("ar", term_id))
    for term_id, term_ar in checked.items():
        approved = _approved_elsewhere(term_id, checked, target_lang)
        for word in (entries.get(term_id) or {}).get(target_lang, {}).get("avoid", []):
            if find_whole_word(word, output) and not find_whole_word(word, approved):
                score = 0.0
                flags.append(Flag(type="warn", key="avoid_word_found", detail=f"{term_ar}|{word}"))
    return score, marks, flags


def _approved_elsewhere(term_id: str, term_ids: Iterable[str], target_lang: TargetLang) -> str:
    """The approved renderings and glosses of the other terms in the segment (D-058): an
    avoid word of one term that another term's approved wording contains («charity» in the
    gloss of sadaqah, avoided for ihsan) was asked for, so it is not a fault."""
    entries = get_index().entries
    parts = []
    for other in term_ids:
        rules = (entries.get(other) or {}).get(target_lang, {}) if other != term_id else {}
        parts += [rules.get("preferred", ""), rules.get("gloss", "")]
    return " | ".join(part for part in parts if part)


async def _backtranslation(
    text: str, output: str, target_lang: TargetLang, router: JsonCompleter
) -> tuple[float, str | None]:
    """(b) Back-translate and compare with the original; a failed call scores 0, no text."""
    prompt = _prompt(
        BACKTRANSLATE_PROMPT, lang_name=_lang_name(target_lang), output=neutralize_tags(output)
    )
    result = await router.complete_json(prompt, BackTranslation)
    if result.data is None:
        return 0.0, None
    back = result.data.arabic_text
    return backtranslation_similarity(text, back), back


def _judge_router(llm_router: Any) -> JsonCompleter | None:
    """The judge router the app built once from its own settings (D-061); ``None`` when unset.

    Before, it was rebuilt for every segment from ``get_settings()``, which read the
    environment and ``.env`` again and ignored the settings the app was created with.
    """
    return getattr(llm_router, "judge", None)


async def _judge_score(
    text: str,
    output: str,
    target_lang: TargetLang,
    judge: JsonCompleter | None,
    on_usage: UsageHook,
) -> float:
    """(c) Meaning preserved, no added claims, scored 0..1 by another model; unset or failed = 0."""
    if judge is None:
        return 0.0
    prompt = _prompt(
        JUDGE_PROMPT,
        lang_name=_lang_name(target_lang),
        text=neutralize_tags(text),
        output=neutralize_tags(output),
    )
    result = await judge.complete_json(prompt, JudgeOutput)
    on_usage(result)
    if result.data is None:
        return 0.0
    return min(max(result.data.score, 0.0), 1.0)


def combine(term: float, bt: float, judge: float) -> float:
    """D-004 formula; a term failure caps confidence below the review threshold."""
    confidence = TERM_WEIGHT * term + BT_WEIGHT * bt + JUDGE_WEIGHT * judge
    if term < 1.0:
        confidence = min(confidence, TERM_FAILURE_CAP)
    return round(confidence, 2)


@dataclass(frozen=True)
class Draft:
    """A source segment and the translation to check. ``locked_terms`` are the renderings the
    localizer locked; ``term_ids`` are every glossary term detected in the source, checked
    for avoid words."""

    text: str
    output: str | None
    target_lang: TargetLang
    locked_terms: Sequence[LockedTerm] = ()
    term_ids: Sequence[str] = ()


async def verify(
    draft: Draft,
    *,
    llm_router: JsonCompleter,
    on_usage: UsageHook | None = None,
    on_back: Callable[[str], None] | None = None,
) -> tuple[float, list[str], list[Flag]]:
    """Return (confidence, marks, flags). ``on_usage`` receives the judge result for cost totals;
    ``on_back`` receives the Arabic back-translation when there is one (shown to the user)."""
    text, output, target_lang = draft.text, draft.output, draft.target_lang
    if not output:
        return 0.0, [], []
    term_score, marks, flags = _term_check(output, target_lang, draft.locked_terms, draft.term_ids)
    bt_score, back = await _backtranslation(text, output, target_lang, llm_router)
    if back and on_back is not None:
        on_back(back)
    judge = _judge_router(llm_router)
    share_budget = getattr(llm_router, "share_budget", None)
    if judge is not None and share_budget is not None:
        # The judge counts against the same request budget as the localizer (D-034).
        judge = share_budget(judge)
    judge_score = await _judge_score(
        text, output, target_lang, judge, on_usage or (lambda _result: None)
    )
    return combine(term_score, bt_score, judge_score), marks, flags
