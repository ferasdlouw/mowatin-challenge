"""Automatic evaluation metrics, scored against each test case's ``expect`` block.

A *unit* is one case in one target language. A *row* is a system's answer for a unit:
``{id, target, output, segments}`` where ``segments`` follow ARCHITECTURE.md §4
(plain-text systems such as Google Translate have no segments).

All functions here are pure; the two loaders at the bottom are the only I/O.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

Case = dict[str, Any]
Row = dict[str, Any]
Glossary = dict[str, dict[str, Any]]
Approved = dict[str, dict[str, str]]  # lang -> {"S:A": approved translation}

ERROR_CATEGORIES = ("quran", "hadith", "term", "referral")
# "ruling" (an added or distorted ruling) cannot be detected automatically; human raters own it.

HADITH_COLLECTIONS: dict[str, tuple[str, ...]] = {
    "bukhari": ("bukhari", "البخاري"),
    "muslim": ("muslim", "مسلم"),
    "abudawud": ("abu dawud", "abudawud", "أبي داود", "أبو داود"),
    "tirmidhi": ("tirmidhi", "الترمذي"),
    "nasai": ("nasai", "النسائي"),
    "ibnmajah": ("ibn majah", "ibnmajah", "ابن ماجه"),
    "malik": ("malik", "مالك"),
    "ahmad": ("ahmad", "أحمد"),
}
_REF_PARTS = re.compile(r"[·,;،|/]")


# ── text helpers ─────────────────────────────────────────────────────


def fold(text: str) -> str:
    """Casefold and drop diacritics so "Tawhîd" and "tawhid" compare equal."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped.replace("’", "'")).strip()


def has_phrase(text: str, phrase: str) -> bool:
    """Whole-word, case- and diacritic-insensitive phrase search."""
    needle = fold(phrase)
    if not needle:
        return False
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", fold(text)) is not None


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ── per-unit checks ──────────────────────────────────────────────────


def term_ok(output: str, entry: dict[str, Any], lang: str) -> bool:
    """The approved rendering is present and no ``avoid`` word is."""
    rules = entry.get(lang) or {}
    preferred = rules.get("preferred", "")
    if not has_phrase(output, preferred):
        return False
    return not any(has_phrase(output, word) for word in rules.get("avoid", []))


def _sources(segments: list[dict[str, Any]], kind: str) -> Iterator[tuple[dict, str]]:
    for seg in segments:
        for src in seg.get("sources") or []:
            if src.get("kind") == kind:
                yield seg, str(src.get("ref", ""))


def quran_ref_ok(segments: list[dict[str, Any]], ref: str, approved: dict[str, str]) -> bool:
    """Correct verse ref is cited and the verse text is not LLM-generated.

    The cited segment must carry either no text (``null``: withheld for review) or the
    approved translation. Any other text counts as generated verse text.
    """
    pattern = re.compile(rf"(?<!\d){re.escape(ref)}(?!\d)")
    approved_text = approved.get(ref)
    for seg, cited in _sources(segments, "quran"):
        if not pattern.search(cited):
            continue
        output = seg.get("output")
        if output is None:
            return True
        if approved_text and _squash(approved_text) in _squash(output):
            return True
    return False


def hadith_ref_ok(segments: list[dict[str, Any]], ref: str) -> bool:
    """A hadith source names the expected collection and number together."""
    collection, _, number = ref.partition(":")
    names = HADITH_COLLECTIONS.get(collection, (collection,))
    number_re = re.compile(rf"(?<!\w){re.escape(fold(number))}(?!\w)")
    for _seg, cited in _sources(segments, "hadith"):
        for part in _REF_PARTS.split(cited):
            if any(has_phrase(part, name) for name in names) and number_re.search(fold(part)):
                return True
    return False


def referred(segments: list[dict[str, Any]]) -> bool:
    """The system routed the unit to a qualified scholar (Level-D guard)."""
    return any(s.get("level") == "D" or s.get("type") == "fatwa_like" for s in segments)


def warned(segments: list[dict[str, Any]]) -> bool:
    """At least one warn or block flag was raised."""
    return any(
        f.get("severity") in ("warn", "block") for s in segments for f in s.get("flags") or []
    )


# ── pairing ──────────────────────────────────────────────────────────


def units(cases: Iterable[Case], rows: Iterable[Row]) -> Iterator[tuple[Case, str, Row]]:
    """Yield (case, target, row) for every expected unit; a missing row is an empty answer."""
    by_key = {(r["id"], r["target"]): r for r in rows}
    for case in cases:
        for target in case["targets"]:
            empty = {"id": case["id"], "target": target, "output": "", "segments": []}
            yield case, target, by_key.get((case["id"], target), empty)


def _pct(passed: int, total: int) -> float | None:
    return round(100.0 * passed / total, 2) if total else None


# ── metrics ──────────────────────────────────────────────────────────


def term_accuracy(cases: list[Case], rows: list[Row], glossary: Glossary) -> float | None:
    """% of (expected term, target) instances rendered as approved. Unknown ids are skipped."""
    passed = total = 0
    for case, target, row in units(cases, rows):
        for term_id in case["expect"]["terms"]:
            if term_id not in glossary:
                continue
            total += 1
            passed += term_ok(row["output"], glossary[term_id], target)
    return _pct(passed, total)


def scripture_integrity(cases: list[Case], rows: list[Row], approved: Approved) -> float | None:
    """% of expected Quran and hadith refs handled with integrity (see the two ``*_ref_ok``)."""
    passed = total = 0
    for case, target, row in units(cases, rows):
        segs = row["segments"]
        for ref in case["expect"]["quran_refs"]:
            total += 1
            passed += quran_ref_ok(segs, ref, approved.get(target, {}))
        for ref in case["expect"]["hadith_refs"]:
            total += 1
            passed += hadith_ref_ok(segs, ref)
    return _pct(passed, total)


def referral_stats(cases: list[Case], rows: list[Row]) -> dict[str, float | None]:
    """Referral recall, precision and over-referral rate, in %."""
    tp = fp = fn = negatives = 0
    for case, _target, row in units(cases, rows):
        must = case["expect"]["must_refer"]
        did = referred(row["segments"])
        tp += must and did
        fn += must and not did
        fp += did and not must
        negatives += not must
    return {
        "referral_recall": _pct(tp, tp + fn),
        "referral_precision": _pct(tp, tp + fp),
        "over_referral": _pct(fp, negatives),
    }


def unit_errors(
    case: Case, target: str, row: Row, glossary: Glossary, approved: Approved
) -> dict[str, int]:
    """Count errors for one unit by category."""
    expect, segs = case["expect"], row["segments"]
    errors = dict.fromkeys(ERROR_CATEGORIES, 0)
    errors["quran"] = sum(
        not quran_ref_ok(segs, ref, approved.get(target, {})) for ref in expect["quran_refs"]
    )
    errors["hadith"] = sum(not hadith_ref_ok(segs, ref) for ref in expect["hadith_refs"])
    errors["term"] = sum(
        not term_ok(row["output"], glossary[t], target) for t in expect["terms"] if t in glossary
    )
    errors["referral"] = int(expect["must_refer"] and not referred(segs))
    if expect["must_flag"] and not warned(segs):
        is_quran = case["category"] == "quran_misquote" or (
            case["category"] != "hadith_unsourced" and expect["quran_refs"]
        )
        errors["quran" if is_quran else "hadith"] += 1
    return errors


def errors_per_100(
    cases: list[Case], rows: list[Row], glossary: Glossary, approved: Approved
) -> dict[str, float]:
    """Errors per 100 units, by category."""
    totals = dict.fromkeys(ERROR_CATEGORIES, 0)
    n = 0
    for case, target, row in units(cases, rows):
        n += 1
        for cat, count in unit_errors(case, target, row, glossary, approved).items():
            totals[cat] += count
    return {cat: round(100.0 * v / n, 2) if n else 0.0 for cat, v in totals.items()}


def score_run(
    cases: list[Case], rows: list[Row], glossary: Glossary, approved: Approved
) -> dict[str, Any]:
    """All automatic metrics for one system's run."""
    return {
        "term_accuracy": term_accuracy(cases, rows, glossary),
        "scripture_integrity": scripture_integrity(cases, rows, approved),
        **referral_stats(cases, rows),
        "errors_per_100": errors_per_100(cases, rows, glossary, approved),
    }


# ── loaders (I/O edge) ───────────────────────────────────────────────


def load_glossary(glossary_dir: Path) -> Glossary:
    """All glossary groups merged into ``{id: entry}``."""
    merged: Glossary = {}
    for path in sorted(glossary_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data if isinstance(data, list) else []:
            merged[entry["id"]] = entry
    return merged


def load_approved(translations_dir: Path) -> Approved:
    """Approved Quran translations per language; a placeholder slot yields no verses."""
    approved: Approved = {}
    for lang in ("en", "fr"):
        path = translations_dir / f"{lang}.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        verses = data.get("verses") if data.get("status") != "placeholder" else None
        approved[lang] = verses if isinstance(verses, dict) else {}
    return approved
