"""hadith.py against temporary slot files (the real slots are placeholders until Rudaina fills them)."""

from __future__ import annotations

import json

import pytest

import app.pipeline.hadith as hadith_module
from app.pipeline.hadith import load_items, match_key, resolve_hadith

# Shapes copied from data/CONTENT_SLOTS.md §2; test fixtures only, never shipped as content.
SOURCED = {
    "status": "verified",
    "reviewed_by": {"name": "fixture", "date": "2026-10-02"},
    "items": [
        {
            "id": "h_niyyat",
            "text_ar": "إنما الأعمال بالنيات",
            "variants_ar": ["إنما الأعمال بالنية", "الأعمال بالنيات"],
            "collection": "bukhari",
            "number": "1",
            "grade": "صحيح",
            "source_url": "https://dorar.net/h/fixture",
        }
    ],
}
FABRICATED = {
    "status": "verified",
    "reviewed_by": {"name": "fixture", "date": "2026-10-02"},
    "items": [
        {
            "id": "f_seen_china",
            "text_ar": "اطلبوا العلم ولو في الصين",
            "variants_ar": ["اطلبوا العلم ولو بالصين"],
            "ruling": "موضوع",
            "source_url": "https://dorar.net/h/fixture",
        }
    ],
}
EMPTY = {"status": "placeholder", "reviewed_by": {"name": "", "date": ""}, "items": []}


@pytest.fixture()
def slots(monkeypatch, tmp_path):
    """Point the handler at tmp slot files; returns a writer."""

    def write(hadith: dict, fabricated: dict) -> None:
        (tmp_path / "hadith.json").write_text(json.dumps(hadith), encoding="utf-8")
        (tmp_path / "fabricated.json").write_text(json.dumps(fabricated), encoding="utf-8")
        load_items.cache_clear()

    monkeypatch.setattr(hadith_module, "HADITH_DIR", tmp_path)
    yield write
    load_items.cache_clear()


def test_sourced_hadith_gets_source_and_info(slots):
    slots(SOURCED, FABRICATED)
    sources, flags = resolve_hadith("قال رسول الله ﷺ: «إنما الأعمالُ بالنيّات».")
    assert [(s.kind, s.ref, s.grade) for s in sources] == [("hadith", "bukhari 1", "صحيح")]
    assert [(f.type, f.key) for f in flags] == [("info", "hadith_sourced")]


def test_variant_matches(slots):
    slots(SOURCED, FABRICATED)
    assert resolve_hadith("قال النبي ﷺ: «الأعمال بالنيات»")[0]


def test_quote_with_added_clause_is_not_sourced(slots):
    """Containing an approved text is not enough: the added words have no source."""
    slots(SOURCED, FABRICATED)
    sources, flags = resolve_hadith("قال النبي ﷺ: «الأعمال بالنيات ومن نوى الخير دخل الجنة»")
    assert sources == []
    assert [(f.type, f.key) for f in flags] == [("warn", "hadith_unsourced")]


def test_every_quote_in_a_segment_is_checked(slots):
    slots(SOURCED, FABRICATED)
    text = "قال النبي ﷺ: «إنما الأعمال بالنيات» وقال: «اطلبوا العلم ولو في الصين» و«حب الوطن من الإيمان»"
    sources, flags = resolve_hadith(text)
    assert [s.ref for s in sources] == ["bukhari 1"]
    assert [(f.type, f.key) for f in flags] == [
        ("info", "hadith_sourced"),
        ("block", "hadith_fabricated"),
        ("warn", "hadith_unsourced"),
    ]


def test_partial_word_does_not_match(slots):
    slots(SOURCED, FABRICATED)
    _, flags = resolve_hadith("قال النبي ﷺ: «والأعمال بالنياتهم»")
    assert flags[0].key == "hadith_unsourced"


def test_fabricated_is_blocked_with_ruling(slots):
    slots(SOURCED, FABRICATED)
    sources, flags = resolve_hadith("قال النبي ﷺ: «اطلبوا العلم ولو بالصين»")
    assert sources == []
    assert [(f.type, f.key, f.detail) for f in flags] == [("block", "hadith_fabricated", "موضوع")]


def test_fabricated_wins_over_sourced(slots):
    both = {**SOURCED, "items": [*SOURCED["items"], {**FABRICATED["items"][0], "number": "9"}]}
    slots(both, FABRICATED)
    assert resolve_hadith("«اطلبوا العلم ولو في الصين»")[1][0].key == "hadith_fabricated"


def test_unmatched_is_unsourced_warn(slots):
    slots(SOURCED, FABRICATED)
    sources, flags = resolve_hadith("قال النبي ﷺ: «حب الوطن من الإيمان»")
    assert sources == []
    assert [(f.type, f.key) for f in flags] == [("warn", "hadith_unsourced")]


def test_empty_slots_send_every_hadith_to_review(slots):
    slots(EMPTY, EMPTY)
    for text in ("«إنما الأعمال بالنيات»", "«اطلبوا العلم ولو في الصين»"):
        sources, flags = resolve_hadith(text)
        assert sources == []
        assert flags[0].key == "hadith_unsourced"


def test_missing_slot_files_are_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(hadith_module, "HADITH_DIR", tmp_path / "absent")
    load_items.cache_clear()
    try:
        assert resolve_hadith("«إنما الأعمال بالنيات»")[1][0].key == "hadith_unsourced"
    finally:
        load_items.cache_clear()


def test_no_quote_is_unsourced():
    assert resolve_hadith("قال النبي ﷺ كلامًا")[1][0].key == "hadith_unsourced"


def test_match_key_ignores_tashkeel_and_punctuation():
    assert match_key("«إنَّما الأعمالُ بالنِّيّات!»") == match_key("انما الاعمال بالنيات")
