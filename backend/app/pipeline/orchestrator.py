"""Deterministic pipeline: segment -> classify -> handler -> report."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.llm.base import JsonCompleter, LLMResult, T
from app.llm.router import LLMRouter, tokens_per_second
from app.pipeline import cache, fatwa_guard
from app.pipeline.budget import LIMIT_ERROR, RequestBudget, RequestLimits
from app.pipeline.classifier import classify
from app.pipeline.glossary import detect, get_index
from app.pipeline.hadith import resolve_hadith, unsourced_quotes
from app.pipeline.injection import looks_steered
from app.pipeline.localizer import localize_segment, raw_translate
from app.pipeline.quran import resolve_quran
from app.pipeline.report import MessageKeyError, assemble, load_messages, render_flag
from app.pipeline.segmenter import segment_capped
from app.pipeline.verifier import Draft, find_whole_word, verify
from app.schemas import (
    Baseline,
    Flag,
    Level,
    Segment,
    SegmentFlag,
    SegmentType,
    SourceRef,
    TargetLang,
    TranslateRequest,
    TranslateResponse,
)
from app.security.privacy import fingerprint

# Every model failed for a segment (D-049); text in flags.ar.json.
UNAVAILABLE = "translation_unavailable"

logger = logging.getLogger("app.pipeline.orchestrator")

_RAW_TYPE: SegmentType = "general"
_RAW_LEVEL: Level = "B"
_PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}")
_VERSE_BRACKETS = "﴿﴾ "
RAW_FLAG = "raw_unprotected"
MAX_LOOKUP_QUOTES = 2


@dataclass
class _CostMeter:
    """LLM usage summed over one request (Phase 3a accounting, reported in docs/SUSTAINABILITY.md)."""

    llm_completions: int = 0
    llm_failed: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    list_cost_usd: float = 0.0
    latency_ms: int = 0

    def record(self, result: LLMResult[Any]) -> None:
        if result.error == LIMIT_ERROR:
            return  # refused by the budget (D-034): never sent, so nothing to count
        self.llm_completions += 1
        self.llm_failed += 0 if result.ok else 1
        self.prompt_tokens += result.usage.prompt_tokens
        self.output_tokens += result.usage.output_tokens
        self.cost_usd += result.cost_usd
        self.list_cost_usd += result.list_cost_usd
        self.latency_ms += result.latency_ms


class _MeteredRouter:
    """Passes calls to the request's router within the request budget (D-034), and records
    each result's usage and cost. A refused call is not sent and returns ``data=None``; a call
    still running at the deadline is cancelled and returns ``data=None`` too (D-060).
    """

    def __init__(
        self,
        inner: JsonCompleter,
        meter: _CostMeter,
        budget: RequestBudget,
        record: bool = True,
    ) -> None:
        self._inner = inner
        self._meter = meter
        self._budget = budget
        self._record = record

    @property
    def hadith_lookup(self) -> Any:
        """The app's Dorar lookup (D-067), or ``None`` when switched off."""
        return getattr(self._inner, "hadith_lookup", None)

    @property
    def judge(self) -> JsonCompleter | None:
        """The app's judge router (D-061); the verifier puts it under this request's budget."""
        return getattr(self._inner, "judge", None)

    @property
    def budget(self) -> RequestBudget:
        return self._budget

    def record(self, result: LLMResult[Any]) -> None:
        """Adds a result sent through another router (the judge) to this request's cost."""
        self._meter.record(result)

    def share_budget(self, inner: JsonCompleter) -> _MeteredRouter:
        """The same budget for another router (the verifier's judge), which records its own usage."""
        return _MeteredRouter(inner, self._meter, self._budget, record=False)

    async def complete_json(self, prompt: str, schema: type[T]) -> LLMResult[T]:
        if not self._budget.allow():
            return LLMResult(data=None, error=LIMIT_ERROR)
        try:
            # A started call may not outlive the deadline either (D-060): with retries and
            # failover one call could run ~80 s past it, after the browser had given up.
            result = await asyncio.wait_for(
                self._inner.complete_json(prompt, schema), timeout=self._budget.remaining()
            )
        except TimeoutError:
            self._budget.expire()
            return LLMResult(data=None, error=LIMIT_ERROR)
        if self._record:
            self._meter.record(result)
        return result


@dataclass
class _Handled:
    """What one handler decided for a segment."""

    output: str | None = None
    confidence: float = 0.0
    sources: list[SourceRef] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    locked_terms: list = field(default_factory=list)
    marks: list[str] = field(default_factory=list)
    back_translation: str | None = None


def _quran(text: str, lang: TargetLang) -> _Handled:
    result = resolve_quran(text, lang)
    output = result["output"]
    # A corrected misquote (D-007) has output but needs review: it must not count as certain.
    certain = output is not None and not result["review"]
    return _Handled(
        output=output,
        confidence=1.0 if certain else 0.0,
        sources=result["sources"],
        flags=result["flags"],
    )


def _steering_flags(text: str, output: str | None) -> list[Flag]:
    """Warn (review) when the output carries a data tag, an override phrase or an odd length (D-037)."""
    if output and looks_steered(text, output):
        return [Flag(type="warn", key="injection_suspected")]
    return []


async def _localize(
    text: str, lang: TargetLang, audience: str, term_ids: list[str], router: _MeteredRouter
) -> _Handled:
    """Localizer (term lock on ``term_ids``) then verifier; glossary sources for the terms."""
    denied_before = router.budget.denied
    output, locked_terms, llm_flags = await localize_segment(
        text, lang, audience, term_ids, router
    )
    back: list[str] = []
    confidence, marks, verifier_flags = await verify(
        Draft(text, output, lang, locked_terms, term_ids),
        llm_router=router,
        on_usage=router.record,
        on_back=back.append,
    )
    return _Handled(
        output=output,
        confidence=confidence,
        sources=_glossary_sources(term_ids),
        flags=llm_flags
        + verifier_flags
        + _steering_flags(text, output)
        + _unavailable(output, router, denied_before),
        locked_terms=locked_terms,
        marks=marks,
        back_translation=back[0] if back else None,
    )


def _unavailable(output: str | None, router: _MeteredRouter, denied_before: int) -> list[Flag]:
    """No translation because every model failed (not the budget, which has its own flag):
    say so, so a segment never shows an empty translation without a reason (D-049)."""
    if output is None and router.budget.denied == denied_before:
        return [Flag(type="warn", key=UNAVAILABLE)]
    return []


async def _hadith(text: str, lang: TargetLang, audience: str, router: _MeteredRouter) -> _Handled:
    """A sourced saying gets a meaning translation, as the ``hadith_sourced`` flag promises.

    The LLM runs only when every quote matched ``hadith.json`` (info flags only): a segment
    holding any unsourced or fabricated quote keeps ``output`` null and stays in review, so
    a fluent translation never lends it authority.
    """
    sources, flags = resolve_hadith(text)
    if not sources or any(flag.type != "info" for flag in flags):
        references = await _dorar_references(text, router)
        return _Handled(sources=sources + references, flags=flags)
    handled = await _localize(text, lang, audience, _glossary_detected_ids(text), router)
    handled.sources = sources + handled.sources
    # "A translation of the meaning follows" is only true when one does (D-049).
    handled.flags = (flags if handled.output else []) + handled.flags
    return handled


async def _dorar_references(text: str, router: _MeteredRouter) -> list[SourceRef]:
    """Dorar entries for each quote not in the approved or fabricated lists (D-067): for the
    reviewer, next to the unsourced flag that keeps the segment untranslated and in review.
    Bounded by the request deadline; at most ``MAX_LOOKUP_QUOTES`` quotes per segment."""
    lookup = router.hadith_lookup
    if lookup is None:
        return []
    references: list[SourceRef] = []
    for quote in unsourced_quotes(text)[:MAX_LOOKUP_QUOTES]:
        references += await lookup.references(quote, router.budget.remaining())
    return references


async def _fatwa(text: str, lang: TargetLang, router: _MeteredRouter) -> _Handled:
    """Level D: the question translated literally (never answered), then the referral.

    The verifier sees the question alone, so a ruling the LLM added is judged as an added
    claim. No translation keeps ``output`` null; the warn flag keeps the segment in review.
    """
    flags = fatwa_guard.referral_flags()
    denied_before = router.budget.denied
    question, llm_flags = await raw_translate(text, lang, router)
    if not question:
        return _Handled(flags=flags + llm_flags + _unavailable(question, router, denied_before))
    back: list[str] = []
    confidence, _marks, verifier_flags = await verify(
        Draft(text, question, lang),
        llm_router=router,
        on_usage=router.record,
        on_back=back.append,
    )
    referral = fatwa_guard.referral_text(lang)
    return _Handled(
        output=f"{question}\n\n{referral}" if referral else question,
        confidence=confidence,
        flags=flags + llm_flags + verifier_flags + _steering_flags(text, question),
        back_translation=back[0] if back else None,
    )


def glossary_ref(term_ar: str) -> str:
    """``ref`` for a glossary source from the optional ``glossary_source`` message (A?{term}A)."""
    template = load_messages().get("glossary_source")
    if not isinstance(template, str) or "{term}" not in template:
        return term_ar
    ref = template.strip().replace("{term}", term_ar)
    return term_ar if _PLACEHOLDER_RE.search(ref) else ref


def _glossary_detected_ids(text: str) -> list[str]:
    """Detect terms and return unique IDs."""
    return list(dict.fromkeys(match["id"] for match in detect(text)))


def _glossary_sources(ids: list[str]) -> list[SourceRef]:
    """One glossary source per detected term ID."""
    entries = get_index().entries
    return [
        SourceRef(kind="glossary", ref=glossary_ref(entries.get(tid, {}).get("ar", tid)))
        for tid in ids
    ]


async def _handle(
    category: str, text: str, req: TranslateRequest, router: _MeteredRouter
) -> _Handled:
    lang, audience = req.target_lang, req.audience
    if req.mode == "raw":
        # Unprotected by design (comparison only, D-038): never certain, always in review.
        output, llm_flags = await raw_translate(text, lang, router)
        return _Handled(
            output=output, confidence=0.0, flags=[*llm_flags, Flag(type="warn", key=RAW_FLAG)]
        )

    if category == "quran":
        return _quran(text, lang)
    if category == "hadith":
        return await _hadith(text, lang, audience, router)
    if category == "fatwa_like":
        return await _fatwa(text, lang, router)
    if category in ("term_heavy", "general"):
        term_ids = _glossary_detected_ids(text) if category == "term_heavy" else []
        return await _localize(text, lang, audience, term_ids, router)
    return _Handled()


def _term_wrong(text: str, raw: str, lang: TargetLang) -> tuple[list[str], Flag | None]:
    """Every ``avoid`` word of a detected term, as the exact span found in the raw output."""
    wrong: list[str] = []
    why: Flag | None = None
    entries = get_index().entries
    for tid in _glossary_detected_ids(text):
        entry = entries.get(tid) or {}
        for word in entry.get(lang, {}).get("avoid", []):
            match = find_whole_word(word, raw)
            if match is None:
                continue
            wrong.append(match.group(0))
            if why is None:
                detail = f"{entry.get('ar', tid)}|{match.group(0)}"
                why = Flag(type="info", key="compare_why_term", detail=detail)
    return list(dict.fromkeys(wrong)), why


def _quran_wrong(text: str, raw: str, lang: TargetLang) -> tuple[list[str], Flag | None]:
    """Raw mishandled the verse unless it reproduced the approved translation."""
    approved = _quran(text, lang).output
    if approved and approved.strip(_VERSE_BRACKETS) in raw:
        return [], None
    # The segment is the verse, so the whole raw segment is the machine-translated verse.
    return [raw], Flag(type="info", key="compare_why_quran")


def _render_why(why: Flag | None) -> str:
    if why is None:
        return ""
    try:
        return render_flag(why).text
    except MessageKeyError:
        return ""


async def _baseline(
    seg_type: str, text: str, lang: TargetLang, router: _MeteredRouter
) -> Baseline:
    """``mode=compare``: raw translation + ``wrong``/``why`` found deterministically (no extra LLM)."""
    raw_out, _raw_flags = await raw_translate(text, lang, router)
    raw = raw_out or ""
    if not raw:
        return Baseline()
    wrong: list[str] = []
    why: Flag | None = None
    if seg_type in ("general", "term_heavy"):
        wrong, why = _term_wrong(text, raw, lang)
    elif seg_type == "quran":
        wrong, why = _quran_wrong(text, raw, lang)
    elif seg_type == "hadith":
        # Raw presents the whole saying as the Prophet's with no approved source.
        wrong, why = [raw], Flag(type="info", key="compare_why_hadith")
    return Baseline(output=raw, wrong=wrong, why=_render_why(why))


async def _build_segment(
    seg_id: int, text: str, req: TranslateRequest, router: _MeteredRouter
) -> Segment:
    denied_before = router.budget.denied
    if req.mode == "raw":
        seg_type, level = _RAW_TYPE, _RAW_LEVEL
    else:
        classified = classify(text)
        seg_type, level = classified["category"], classified["level"]
        if seg_type == "fatwa_like":
            level = fatwa_guard.LEVEL
    handled = await _handle(seg_type, text, req, router)
    baseline = None
    if req.mode == "compare":
        baseline = await _baseline(seg_type, text, req.target_lang, router)
    flags = handled.flags
    if router.budget.denied > denied_before:
        # A call this segment needed was refused (D-034): warn, so it is always reviewed.
        flags = [*flags, Flag(type="warn", key=LIMIT_ERROR)]
    final_flags = [f if isinstance(f, SegmentFlag) else render_flag(f) for f in flags]

    return Segment(
        id=seg_id,
        source=text,
        output=handled.output,
        type=seg_type,
        level=level,
        sources=handled.sources,
        confidence=handled.confidence,
        locked_terms=handled.locked_terms,
        marks=handled.marks,
        flags=final_flags,
        baseline=baseline,
        back_translation=handled.back_translation,
    )


def _remainder_segment(seg_id: int, rest: str) -> Segment:
    """Text past ``MAX_SEGMENTS`` (D-034): one untranslated segment in review, no LLM call."""
    classified = classify(rest)
    return Segment(
        id=seg_id,
        source=rest,
        output=None,
        type=classified["category"],
        level=classified["level"],
        confidence=0.0,
        flags=[render_flag(Flag(type="warn", key=LIMIT_ERROR))],
    )


def _log_limit(req: TranslateRequest, reason: str, segments: int, budget: RequestBudget) -> None:
    """One ``limit_hit`` line per limited request: counters and a fingerprint, never text."""
    record = {
        "event": "limit_hit",
        "reason": reason,
        "segments": segments,
        "llm_calls": budget.calls,
        "llm_denied": budget.denied,
        **fingerprint(req.text),
    }
    logger.warning(json.dumps(record, sort_keys=True))


def _log_cost(req: TranslateRequest, meter: _CostMeter, segments: int, cache_hit: bool) -> None:
    """One ``request_cost`` line per request; the text appears only as length + hash prefix."""
    record = {
        "event": "request_cost",
        "mode": req.mode,
        "target_lang": req.target_lang,
        "segments": segments,
        "cache_hit": cache_hit,
        "llm_completions": meter.llm_completions,
        "llm_failed": meter.llm_failed,
        "prompt_tokens": meter.prompt_tokens,
        "output_tokens": meter.output_tokens,
        # Actual cost (0 on free tiers) and the same calls at paid list price (D-031).
        "cost_usd": round(meter.cost_usd, 6),
        "list_cost_usd": round(meter.list_cost_usd, 6),
        # Time spent waiting on LLM calls (summed per call), the basis for docs/MODELS.md speed.
        "llm_latency_ms": meter.latency_ms,
        "output_tokens_per_s": tokens_per_second(meter.output_tokens, meter.latency_ms),
        **fingerprint(req.text),
    }
    logger.info(json.dumps(record, sort_keys=True))


async def translate(
    req: TranslateRequest,
    router: LLMRouter,
    limits: RequestLimits | None = None,
    use_cache: bool = True,
) -> TranslateResponse:
    """Run the pipeline over the request text within ``limits`` and log the request's LLM cost.

    ``limits`` comes from the app (one daily breaker per process); without it each call gets
    the default limits and its own breaker. ``use_cache=False`` (``RESPONSE_CACHE=false``,
    evaluation runs, D-059) neither reads nor stores the response cache.
    """
    limits = limits or RequestLimits()
    meter = _CostMeter()
    cache_key = cache.get_cache_key(req.text, req.target_lang, req.audience, req.mode)
    cached_resp = cache.get(cache_key) if use_cache else None
    if cached_resp:
        _log_cost(req, meter, len(cached_resp.segments), cache_hit=True)
        return cached_resp

    budget = RequestBudget(limits)
    metered = _MeteredRouter(router, meter, budget)
    parts, rest = segment_capped(req.text, limits.max_segments)
    segments = []
    for i, text in enumerate(parts, start=1):
        seg = await _build_segment(i, text, req, metered)
        segments.append(seg)
    if rest:
        segments.append(_remainder_segment(len(segments) + 1, rest))
    reason = "max_segments" if rest else budget.reason
    if reason:
        _log_limit(req, reason, len(parts) + (1 if rest else 0), budget)

    response = assemble(segments)
    if use_cache and meter.llm_failed == 0 and budget.denied == 0 and not rest:
        # A degraded answer (failed or refused call, cut text) is not kept (D-039): once the
        # quota is back, the same text must be translated again, not served "in review".
        cache.set(cache_key, response)
    _log_cost(req, meter, len(segments), cache_hit=False)
    return response
