"""D-057 (code audit item 5): hadith matching uses the canonical form (D-036).

Before, the key used ``normalize_text`` only, so an alef wasla or a madda/hamza mark in a
quote turned a fabricated saying (block) into an unknown one (warn) and a sourced saying into
an unsourced one.
"""

from __future__ import annotations

import pytest

from app.pipeline.hadith import load_items, match_key, resolve_hadith

ZWJ = "‍"


def _variants(text: str) -> list[str]:
    """The same saying with a wasla, a madda mark, a tatweel and a zero-width joiner."""
    return [
        text.replace("ا", "ٱ", 1),
        text[:2] + "ٓ" + text[2:],
        text.replace("ل", "لـ", 1),
        text[:3] + ZWJ + text[3:],
    ]


def _flags(saying: str) -> list[tuple[str, str]]:
    return [(flag.type, flag.key) for flag in resolve_hadith(f"قال النبي ﷺ: «{saying}»")[1]]


@pytest.mark.parametrize("item", load_items("fabricated"), ids=lambda item: item.get("id", ""))
def test_fabricated_saying_stays_fabricated_however_it_is_written(item):
    for saying in _variants(item["text_ar"]):
        assert _flags(saying) == [("block", "hadith_fabricated")], saying


@pytest.mark.parametrize("item", load_items("hadith")[:10], ids=lambda item: item.get("id", ""))
def test_sourced_hadith_stays_sourced_however_it_is_written(item):
    for saying in _variants(item["text_ar"]):
        sources, flags = resolve_hadith(f"قال النبي ﷺ: «{saying}»")
        assert [(flag.type, flag.key) for flag in flags] == [("info", "hadith_sourced")], saying
        assert len(sources) == 1


def test_no_sourced_hadith_shares_a_key_with_a_fabricated_one():
    sourced = {
        match_key(t)
        for i in load_items("hadith")
        for t in [i["text_ar"], *i.get("variants_ar", [])]
    }
    fabricated = {
        match_key(t)
        for i in load_items("fabricated")
        for t in [i["text_ar"], *i.get("variants_ar", [])]
    }
    assert not sourced & fabricated
