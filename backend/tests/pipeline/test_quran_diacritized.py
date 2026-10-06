"""Matched verses come back with Tanzil's own tashkeel, never generated (Phase QT, D-044).

The diacritized words are a slice of ``data/quran/tanzil/quran-simple.txt``, taken at the word
positions the matcher found in the clean text. Anything unsure shows no diacritized text.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

import app.pipeline.quran as quran_module
from app.llm.base import LLMResult
from app.pipeline import cache, orchestrator
from app.pipeline.budget import DailyBreaker, RequestLimits
from app.pipeline.quran import resolve_quran
from app.schemas import Flag, TranslateRequest

SIMPLE = Path(__file__).resolve().parents[3] / "data" / "quran" / "tanzil" / "quran-simple.txt"
ZWSP, ZWNJ, RLO = "\u200b", "\u200c", "\u202e"
HERO = "قال الله تعالى: ﴿إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ﴾."


def _line(ref: str) -> str:
    """The verse exactly as the Tanzil file has it."""
    prefix = ref.replace(":", "|") + "|"
    for line in SIMPLE.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise AssertionError(ref)


def _words(ref: str, start: int, end: int) -> str:
    return " ".join(_line(ref).split()[start:end])


def _diacritized(res: dict) -> Flag | None:
    return next((f for f in res["flags"] if f.key == "quran_diacritized"), None)


@pytest.fixture(autouse=True)
def fresh_index():
    quran_module.get_index.cache_clear()
    yield
    quran_module.get_index.cache_clear()


def test_undiacritized_full_verse_gets_the_file_line_exactly():
    res = resolve_quran("قال الله تعالى: ﴿وما أرسلناك إلا رحمة للعالمين﴾", "en")
    flag = _diacritized(res)
    assert flag is not None
    assert flag.type == "info"
    assert flag.detail == f"21:107|{_line('21:107')}"


def test_hero_partial_quote_gets_only_its_words_with_the_files_marks():
    # The hero types shadda before fatha; Tanzil stores shadda first (U+0651 U+064E). The
    # answer carries the file's code points, not the user's.
    expected = "إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ"
    assert expected == _words("49:10", 0, 3)
    assert _diacritized(resolve_quran(HERO, "en")).detail == f"49:10|{expected}"


def test_partial_quote_from_the_middle_of_a_verse():
    res = resolve_quran("قال تعالى: ﴿آمنوا استعينوا بالصبر والصلاة﴾", "en")
    assert _diacritized(res).detail == f"2:153|{_words('2:153', 3, 7)}"


def test_quote_across_two_verses_joins_each_part():
    res = resolve_quran("قال تعالى: ﴿الحمد لله رب العالمين الرحمن الرحيم﴾", "en")
    expected = f"{_line('1:2')} {_line('1:3')}"
    assert _diacritized(res).detail == f"1:2-3|{expected}"
    assert res["sources"][0].ref == "1:2-3"


@pytest.mark.parametrize(
    "typed",
    [
        "﴿وَمِا أَرْسَلْنَاكُ إلا رَحْمَةٌ لِلْعَالَمِينَ﴾",  # wrong marks
        "﴿وَمَا أرسلناك إلا رَحمة للعالمين﴾",  # partial marks
        "﴿ومـــا أرسلـناك إلا رحمة للعالمين﴾",  # tatweel
        f"﴿وما أرسل{ZWSP}ناك إلا رح{ZWNJ}مة للعا{RLO}لمين﴾",  # zero-width and bidi
    ],
)
def test_typed_marks_and_hidden_characters_are_replaced_by_the_files(typed):
    res = resolve_quran(f"قال الله تعالى: {typed}", "en")
    assert _diacritized(res).detail == f"21:107|{_line('21:107')}"


def test_unbracketed_attributed_verse_is_diacritized_too():
    res = resolve_quran("قال الله تعالى: وما أرسلناك إلا رحمة للعالمين", "en")
    assert res["output"] is not None
    assert _diacritized(res).detail == f"21:107|{_line('21:107')}"


def test_misquote_shows_the_correct_verse_diacritized_and_stays_blocked():
    res = resolve_quran("قال الله تعالى: ﴿الْحَمْدُ لِلَّهِ رَبِّ الْمُسْلِمِينَ﴾.", "en")
    mismatch = next(f for f in res["flags"] if f.key == "quran_mismatch")
    assert mismatch.type == "block"
    assert mismatch.detail == f"1:2|{_line('1:2')}"
    assert res["review"] is True
    # The correct text is already in the block flag: no second copy.
    assert _diacritized(res) is None


@pytest.mark.parametrize(
    "text",
    [
        "قال تعالى: ﴿فبأي آلاء ربكما تكذبان﴾",  # 31 places: quran_ambiguous
        "قال الله تعالى: ﴿هذا نص لا يوجد في القرآن الكريم أبدا﴾",  # not found
        "قال تعالى: ﴿ا أرسلناك إلا رحمة للعالمين﴾",  # starts inside a word
    ],
)
def test_unsure_match_shows_no_diacritized_text(text):
    assert _diacritized(resolve_quran(text, "en")) is None


@pytest.mark.parametrize(
    ("text", "ref", "start", "end"),
    [
        # «بعدما» in the matching file is «بَعْدَ مَا» (two words) in Simple 1.1.
        ("قال تعالى: ﴿فمن بدله بعدما سمعه فإنما إثمه على الذين يبدلونه﴾", "2:181", 0, 10),
        # «الزنا» is «الزِّنَىٰ» in Simple 1.1.
        ("قال تعالى: ﴿ولا تقربوا الزنا﴾", "17:32", 0, 3),
        ("قال تعالى: ﴿يا ويلتا أعجزت أن أكون مثل هذا الغراب﴾", "5:31", 12, 20),
    ],
)
def test_verse_spelled_differently_in_1_1_shows_the_files_words(text, ref, start, end):
    # D-045: the matching text keeps its spelling; what is shown is the Tanzil 1.1 line.
    assert _diacritized(resolve_quran(text, "en")).detail == f"{ref}|{_words(ref, start, end)}"


@pytest.mark.parametrize(
    ("text", "ref", "start", "end", "partial"),
    [
        ("قال تعالى: ﴿ولا تقربوا الزنا إنه كان فاحشة وساء سبيلا﴾", "17:32", 0, 8, False),
        (
            "قال تعالى: ﴿لا تأخذه سنة ولا نوم له ما في السماوات وما في الأرض﴾",
            "2:255",
            7,
            19,
            True,
        ),
        (
            "قال تعالى: ﴿إنما المؤمنون إخوة فأصلحوا بين أخويكم واتقوا الله لعلكم ترحمون﴾",
            "49:10",
            0,
            10,
            False,
        ),
    ],
)
def test_quote_across_a_pause_mark_is_the_verse_not_a_misquote(text, ref, start, end, partial):
    # D-046: the matching file keeps pause marks as separate tokens, which left a double space
    # in the index, so a correct quote across one was "corrected" as a misquote (block).
    # D-055: a quote under 40% of its verse (12 words of Ayat al-Kursi) is also reviewed.
    res = resolve_quran(text, "en")
    expected = [
        "quran_from_approved",
        *(["quran_partial"] if partial else []),
        "quran_diacritized",
    ]
    assert [f.key for f in res["flags"]] == expected
    assert res["review"] is partial
    assert _diacritized(res).detail == f"{ref}|{_words(ref, start, end)}"


def test_missing_file_turns_the_feature_off(monkeypatch, tmp_path):
    monkeypatch.setattr(quran_module, "TANZIL_DIACRITIZED_PATH", tmp_path / "missing.txt")
    res = resolve_quran(HERO, "en")
    assert res["output"] is not None
    assert _diacritized(res) is None
    misquote = resolve_quran("قال الله تعالى: ﴿الحمد لله رب المسلمين﴾", "en")
    mismatch = next(f for f in misquote["flags"] if f.key == "quran_mismatch")
    assert mismatch.detail == "1:2|الحمد لله رب العالمين"


def test_misaligned_file_turns_the_verse_off_not_the_app(monkeypatch, tmp_path):
    broken = tmp_path / "quran-simple.txt"
    lines = SIMPLE.read_text(encoding="utf-8").splitlines()
    broken.write_text(
        "\n".join("21|107|كلمة واحدة" if line.startswith("21|107|") else line for line in lines),
        encoding="utf-8",
    )
    monkeypatch.setattr(quran_module, "TANZIL_DIACRITIZED_PATH", broken)
    assert _diacritized(resolve_quran("قال تعالى: ﴿وما أرسلناك إلا رحمة للعالمين﴾", "en")) is None
    assert _diacritized(resolve_quran(HERO, "en")) is not None


def test_translation_path_is_unchanged():
    res = resolve_quran(HERO, "en")
    assert res["output"].startswith("﴿") and res["output"].endswith("﴾")
    assert [s.ref for s in res["sources"]] == ["49:10"]
    # D-055: 3 words of 49:10 get the whole verse's translation, so the segment is reviewed.
    assert res["review"] is True
    keys = [f.key for f in res["flags"]]
    assert keys == ["quran_from_approved", "quran_partial", "quran_diacritized"]


class _CountingRouter:
    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        self.calls += 1
        return LLMResult(data=None, error="unused")


def test_hero_text_through_the_pipeline_needs_no_llm_and_keeps_the_contract():
    cache.clear()
    router = _CountingRouter()
    req = TranslateRequest(text=HERO, target_lang="en", mode="localize")
    resp = asyncio.run(orchestrator.translate(req, router, RequestLimits(daily=DailyBreaker(100))))
    assert router.calls == 0
    seg = resp.segments[0]
    assert seg.type == "quran"
    assert seg.source == HERO
    # D-055: a partial quote keeps its approved translation and is reviewed.
    assert seg.output and seg.output.startswith("﴿")
    assert seg.confidence == 0.0
    assert resp.review_queue == [1]
    info = [f.text for f in seg.flags if f"﴿{_words('49:10', 0, 3)}﴾ (49:10)" in f.text]
    assert len(info) == 1
    assert set(seg.model_dump()) == {
        "id", "source", "output", "type", "level", "locked_terms", "marks",
        "sources", "confidence", "flags", "baseline", "back_translation",
    }  # fmt: skip


def test_bare_three_word_verse_typed_without_hamza_gets_the_files_marks():
    # The screen of 2026-10-04: «انما المؤمنون اخوة», no brackets, no formula, no hamza.
    res = resolve_quran("انما المؤمنون اخوة", "en")
    assert res["sources"][0].ref == "49:10"
    assert res["output"] is not None
    # D-055: 3 words of a 10-word verse: the whole verse's translation, reviewed.
    assert res["review"] is True
    assert _diacritized(res).detail == f"49:10|{_words('49:10', 0, 3)}"
