"""Verifier: term check + back-translation + judge, combined into confidence (D-004).

A check that cannot run (provider unset, call failed, no data) scores 0, never 1:
an unverified segment must end in review (D-021).
"""

from __future__ import annotations

import contextlib
import logging
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.config import get_settings
from app.llm.base import JsonCompleter, LLMResult
from app.llm.factory import build_provider
from app.llm.router import LLMRouter
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
    output: str, target_lang: TargetLang, locked_terms: list[LockedTerm]
) -> tuple[float, list[str], list[Flag]]:
    """(a) Required rendering present (marks = exact rendered strings) and no ``avoid`` word."""
    score, marks, flags = 1.0, [], []
    output_lower = output.lower()
    for term in locked_terms:
        idx = output_lower.find(term.out.lower())
        if idx >= 0:
            marks.append(output[idx : idx + len(term.out)])
        else:
            score = 0.0
            flags.append(Flag(type="warn", key="term_check_failed", detail=term.ar))
        entry = get_index().entries.get(term.glossary_id) or {}
        for word in entry.get(target_lang, {}).get("avoid", []):
            if find_whole_word(word, output):
                score = 0.0
                flags.append(Flag(type="warn", key="avoid_word_found", detail=f"{term.ar}|{word}"))
    return score, marks, flags


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
    """Router for the ``JUDGE_*`` slot on the localizer's HTTP client; ``None`` when unset."""
    providers = getattr(llm_router, "_providers", None) or []
    http = getattr(providers[0], "_http", None) if providers else None
    if http is None:
        return None
    provider = None
    with contextlib.suppress(Exception):
        provider = build_provider("JUDGE", get_settings(), http)
    return LLMRouter([provider]) if provider else None


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


async def verify(  # noqa: PLR0913
    text: str,
    output: str | None,
    target_lang: TargetLang,
    audience: str,
    locked_terms: list[LockedTerm],
    llm_router: JsonCompleter,
    on_usage: UsageHook | None = None,
    on_back: Callable[[str], None] | None = None,
) -> tuple[float, list[str], list[Flag]]:
    """Return (confidence, marks, flags). ``on_usage`` receives the judge result for cost totals;
    ``on_back`` receives the Arabic back-translation when there is one (shown to the user)."""
    if not output:
        return 0.0, [], []
    term_score, marks, flags = _term_check(output, target_lang, locked_terms)
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
