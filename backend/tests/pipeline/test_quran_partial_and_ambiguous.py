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


def test_ambiguous_quote_whose_places_translate_differently_is_reviewed():
    result = resolve_quran("﴿إن الله مع الصابرين﴾", "en")
    assert _keys(result)["quran_ambiguous"] == "warn"
    assert result["output"] is not None
    assert result["review"] is True


def test_repeated_verse_with_one_translation_stays_certain():
    # 31 places, the same translation (some end with « -» where the verse runs on).
    result = resolve_quran("﴿فبأي آلاء ربكما تكذبان﴾", "en")
    assert _keys(result)["quran_ambiguous"] == "info"
    assert result["review"] is False


def test_basmala_is_not_every_sura_opening():
    result = resolve_quran("﴿بسم الله الرحمن الرحيم﴾", "en")
    ambiguous = next(flag for flag in result["flags"] if flag.key == "quran_ambiguous")
    assert ambiguous.detail == "1:1, 27:30"
    assert [s.ref for s in result["sources"]] == ["1:1"]


def test_partial_quote_keeps_the_verse_and_is_reviewed():
    result = resolve_quran("﴿فإذا عزمت فتوكل على الله﴾", "en")
    assert [s.ref for s in result["sources"]] == ["3:159"]
    assert result["output"] is not None
    assert _keys(result)["quran_partial"] == "warn"
    assert result["review"] is True
    partial = next(flag for flag in result["flags"] if flag.key == "quran_partial")
    # Until flags.ar.json has its own text (content slot).
    assert render_flag(partial).text == load_messages()["low_confidence"]


def test_whole_verse_is_not_partial():
    result = resolve_quran("﴿وما أرسلناك إلا رحمة للعالمين﴾", "en")
    assert "quran_partial" not in _keys(result)
    assert result["review"] is False
