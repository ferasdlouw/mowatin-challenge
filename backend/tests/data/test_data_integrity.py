"""Read-only integrity checks over the approved data in data/**.

These tests guard the closed-knowledge sources the pipeline retrieves from. They never edit
data and never print item text: failures name ids, keys or counts only. The test-set check
compares normalized SHA-256 hashes, so no sealed item text is ever shown.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

import app.pipeline.quran as quran_module
from app.pipeline.normalize import canonicalize_for_matching, normalize_text

DATA = Path(__file__).resolve().parents[3] / "data"
SCRIPTS = DATA.parent / "scripts"
QURAN_VERSES = 6236
ISLAM_CLASH = ("المسلم", "المسلمين", "المسلمون")


def _load(rel: str) -> dict[str, Any]:
    return json.loads((DATA / rel).read_text(encoding="utf-8"))


def _glossary_terms() -> list[dict[str, Any]]:
    terms: list[dict[str, Any]] = []
    for path in sorted((DATA / "glossary").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        terms.extend(payload["terms"] if isinstance(payload, dict) else payload)
    return terms


def _forms(item: dict[str, Any], main_key: str) -> list[str]:
    return [form for form in [item.get(main_key, ""), *item.get("variants_ar", [])] if form]


def _digest(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def test_no_glossary_variant_maps_to_two_term_ids() -> None:
    owners: dict[str, set[str]] = defaultdict(set)
    for term in _glossary_terms():
        for form in _forms(term, "ar"):
            owners[normalize_text(form)].add(term["id"])
    clashes = {key: sorted(ids) for key, ids in owners.items() if len(ids) > 1}
    assert not clashes, f"variants shared by several term ids: {sorted(clashes.values())}"


def test_islam_does_not_claim_muslim_forms() -> None:
    # «المسلم» means "the Muslim", not "Islam"; locking it to "Islam" would mistranslate.
    islam = next(term for term in _glossary_terms() if term["id"] == "islam")
    claimed = {normalize_text(form) for form in _forms(islam, "ar")}
    assert not claimed & {normalize_text(form) for form in ISLAM_CLASH}


def _hadith_keys(name: str) -> dict[str, str]:
    return {
        normalize_text(form): item["id"]
        for item in _load(f"hadith/{name}.json").get("items", [])
        for form in _forms(item, "text_ar")
    }


def test_no_text_is_both_sourced_hadith_and_fabricated() -> None:
    sourced, fabricated = _hadith_keys("hadith"), _hadith_keys("fabricated")
    both = sorted((sourced[key], fabricated[key]) for key in sourced.keys() & fabricated.keys())
    assert not both, f"(hadith id, fabricated id) pairs with the same text: {both}"


def test_demo_examples_are_not_in_the_test_set() -> None:
    testset = DATA / "testset" / "testset.jsonl"
    case_hashes = {
        _digest(json.loads(line)["text_ar"])
        for line in testset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    leaked = [
        item["id"]
        for item in _load("demo/examples.json").get("items", [])
        if _digest(item["text_ar"]) in case_hashes
    ]
    assert not leaked, f"demo ids whose text is a test-set case: {leaked}"


def _tanzil_keys() -> set[str]:
    lines = (DATA / "quran" / "tanzil" / "quran-simple-clean.txt").read_text(encoding="utf-8-sig")
    keys = set()
    for line in lines.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            keys.add(f"{parts[0]}:{parts[1]}")
    return keys


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_quran_translation_has_every_verse_with_valid_keys(lang: str) -> None:
    verses = _load(f"quran/translations/{lang}.json")["verses"]
    valid = _tanzil_keys()
    assert len(valid) == QURAN_VERSES
    assert len(verses) == QURAN_VERSES
    invalid = sorted(set(verses) - valid)
    assert not invalid, (
        f"{lang}: keys that are not a surah:ayah in the Tanzil text: {invalid[:10]}"
    )


def _tanzil_lines(name: str) -> dict[tuple[int, int], str]:
    """``(sura, aya) -> text`` of a Tanzil ``sura|aya|text`` file; its ``#`` notice is skipped."""
    lines = (DATA / "quran" / "tanzil" / name).read_text(encoding="utf-8").splitlines()
    rows = [line.split("|", 2) for line in lines if line and not line.startswith("#")]
    return {(int(sura), int(aya)): text for sura, aya, text in rows}


# Spelled differently in the older Simple Clean matching file and in Simple 1.1 (بعدما / بعد ما,
# ويلتا / ويلتى, الزنا / الزنى, حسرتا / حسرتى); the resolver aligns them by rule (D-045).
QURAN_SPELLING_DIFFERS = {(2, 181), (5, 31), (8, 6), (13, 37), (17, 32), (39, 56)}


def test_diacritized_quran_aligns_word_for_word_with_the_matching_text() -> None:
    clean = _tanzil_lines("quran-simple-clean.txt")
    diacritized = _tanzil_lines("quran-simple.txt")
    assert len(clean) == len(diacritized) == QURAN_VERSES
    assert clean.keys() == diacritized.keys()
    misaligned = {
        key
        for key, text in clean.items()
        if canonicalize_for_matching(text).split()
        != canonicalize_for_matching(diacritized[key]).split()
    }
    assert misaligned == QURAN_SPELLING_DIFFERS, f"keys: {sorted(misaligned)}"


def test_every_verse_gets_diacritized_words_for_its_matching_words() -> None:
    # D-045: the 6 spelling differences align by rule, so all 6236 verses are covered.
    quran_module.get_index.cache_clear()
    try:
        index = quran_module.get_index()
        missing = [v["ref"] for i, v in enumerate(index.verses) if i not in index.diacritized]
    finally:
        quran_module.get_index.cache_clear()
    assert len(index.verses) == QURAN_VERSES
    assert not missing, f"verses without diacritized words: {missing}"


def test_diacritized_quran_is_the_verbatim_tanzil_simple_file() -> None:
    raw = (DATA / "quran" / "tanzil" / "quran-simple.txt").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == (
        "7c30902a1060d14249791a24cb364ac8ae178455373fd545633b33a2254d3151"
    )
    assert b"Tanzil Quran Text (Simple, Version 1.1)" in raw
    # Pause and sajdah marks were left out on download: one mark per word slot is what aligns.
    assert not re.search("[\u06d6-\u06dc\u06de\u06e9]", raw.decode("utf-8"))


def _declared_placeholders() -> dict[str, set[str]]:
    spec = importlib.util.spec_from_file_location(
        "validate_content", SCRIPTS / "validate_content.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PLACEHOLDERS


def test_every_placeholder_the_code_fills_is_in_its_message() -> None:
    messages = _load("messages/flags.ar.json")["messages"]
    missing = sorted(
        f"{key}:{placeholder}"
        for key, placeholders in _declared_placeholders().items()
        for placeholder in placeholders
        if placeholder not in messages.get(key, "")
    )
    assert not missing, f"messages without a placeholder the code fills: {missing}"
