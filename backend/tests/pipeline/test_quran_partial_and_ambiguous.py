"""D-055 (code audit item 3): a short, partial or ambiguous quote is never certain by chance.

Before: «الله مع» in ornate brackets (2 words found in many verses) got the whole of 2:153 as certain, a
quote found in several places took the first one with only an info flag, and a partial quote
got the whole verse's translation as certain, though D-006 asked for 40% of the verse.
"""

from __future__ import annotations

import pytest

from app.pipeline.quran import resolve_quran
from app.pipeline.report import load_messages, render_flag


def _keys(result: dict) -> dict[str, str]:
    return {flag.key: flag.type for flag in result["flags"] if flag.key != "quran_diacritized"}


def test_two_words_that_are_not_a_whole_verse_get_no_verse():
    result = resolve_quran("﴿الله مع﴾", "en")
    assert result["output"] is None
    assert result["review"] is True
    assert _keys(result)["quran_not_found"] == "warn"


@pytest.mark.parametrize(("quote", "ref"), [("﴿مدهامتان﴾", "55:64"), ("﴿والعصر﴾", "103:1")])
def test_a_short_whole_verse_is_still_the_verse(quote, ref):
    # 103:1 opens with the basmala in the Tanzil text; «والعصر» alone is the whole verse.
    result = resolve_quran(quote, "en")
    assert [s.ref for s in result["sources"]] == [ref]
    assert result["review"] is False


def test_ambiguous_quote_is_reviewed_and_no_place_is_picked():
    # D-076 (amends D-055 (1)): the first place is never taken.
    result = resolve_quran("﴿إن الله مع الصابرين﴾", "en")
    assert _keys(result)["quran_ambiguous"] == "warn"
    assert result["output"] is None
    assert result["sources"] == []
    assert result["review"] is True
    assert [c.ref for c in result["candidates"]] == ["2:153", "8:46"]


def test_repeated_verse_with_one_translation_is_still_ambiguous():
    # 31 places with the same translation: the place is still unknown, so no source is claimed.
    result = resolve_quran("﴿فبأي آلاء ربكما تكذبان﴾", "en")
    assert _keys(result)["quran_ambiguous"] == "warn"
    assert result["verification"] == "ambiguous_verse"
    assert len(result["candidates"]) == 31
    assert result["review"] is True


def test_basmala_is_not_every_sura_opening():
    result = resolve_quran("﴿بسم الله الرحمن الرحيم﴾", "en")
    ambiguous = next(flag for flag in result["flags"] if flag.key == "quran_ambiguous")
    assert ambiguous.detail == "1:1, 27:30"
    assert [c.ref for c in result["candidates"]] == ["1:1", "27:30"]


def test_partial_quote_keeps_the_verse_and_is_reviewed():
    result = resolve_quran("﴿فإذا عزمت فتوكل على الله﴾", "en")
    assert [s.ref for s in result["sources"]] == ["3:159"]
    assert result["output"] is not None
    assert _keys(result)["quran_partial"] == "warn"
    assert result["review"] is True
    assert result["verification"] == "verified_retrieval"
    partial = next(flag for flag in result["flags"] if flag.key == "quran_partial")
    # Its own text, not «low confidence»: the translation is not a low-confidence one (D-076).
    assert render_flag(partial).text == load_messages()["quran_partial"]


def test_whole_verse_is_not_partial():
    result = resolve_quran("﴿وما أرسلناك إلا رحمة للعالمين﴾", "en")
    assert "quran_partial" not in _keys(result)
    assert result["review"] is False
