"""Partial-hadith completion from the derived corpus (D-077): a labelled suggestion, verbatim
from the file, never chosen among disagreeing records, never ahead of the fabricated list."""

from __future__ import annotations

import gzip
import json
import random
import time
import tracemalloc
from pathlib import Path

import pytest

from app.pipeline import cache, hadith_corpus, orchestrator
from app.pipeline.hadith import load_items, match_key, resolve_hadith
from app.pipeline.report import render_flag
from app.schemas import TranslateRequest

NOT_TAKHRIJ = "ليس رقم التخريج المطبوع"

# Small made-up records in the corpus file's shape; never shipped as content.
RECORDS = [
    {
        "c": "muslim",
        "r": 9,
        "t": "وحدثنا محمد عن سفيان قال رسول الله ﷺ إنما الأعمال بالنيات وإنما لكل امرئ ما نوى "
        "فمن كانت هجرته إلى دنيا يصيبها",
    },
    {
        "c": "bukhari",
        "r": 1,
        "t": "حَدَّثَنَا الْحُمَيْدِيُّ قَالَ سَمِعْتُ رَسُولَ اللَّهِ ﷺ يَقُولُ إِنَّمَا الْأَعْمَالُ "
        "بِالنِّيَّاتِ، وَإِنَّمَا لِكُلِّ امْرِئٍ مَا نَوَى، فَمَنْ كَانَتْ هِجْرَتُهُ إِلَى دُنْيَا يُصِيبُهَا",
    },
    {
        "c": "bukhari",
        "r": 7,
        "t": "حدثنا قتيبة عن مالك الطهور شطر الإيمان كله والحمد لله تملأ الميزان",
    },
    {"c": "muslim", "r": 3, "t": "حدثنا يحيى الطهور شطر الإيمان كله والصلاة نور والصدقة برهان"},
]

PARTIAL_FORMS = [
    "قال رسول الله ﷺ: «إنما الأعمال بالنيات وإنما لكل»",
    "قال رسول الله ﷺ: «إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ وَإِنَّمَا لِكُلِّ»",
    "قَالَ رَسُولُ اللَّهِ صلى الله عليه وسلم: «إنّما الأعمـال بالنيّات، وإنّما‌ لكلّ…»",
]


def _write(path, records) -> None:
    items = [{**record, "k": match_key(record["t"])} for record in records]
    data = {"status": "draft", "collections": {"bukhari": "صحيح البخاري", "muslim": "صحيح مسلم"}}
    path.write_bytes(gzip.compress(json.dumps({**data, "items": items}).encode("utf-8")))


@pytest.fixture(autouse=True)
def corpus(monkeypatch, tmp_path):
    path = tmp_path / "corpus.json.gz"
    _write(path, RECORDS)
    monkeypatch.setattr(hadith_corpus, "CORPUS_PATH", path)
    hadith_corpus.load_corpus.cache_clear()
    load_items.cache_clear()
    cache.clear()
    yield path
    hadith_corpus.load_corpus.cache_clear()
    cache.clear()


def _keys(flags) -> list[str]:
    return [flag.key for flag in flags]


@pytest.mark.parametrize("text", PARTIAL_FORMS)
def test_partial_in_plain_diacritized_or_pasted_form_gives_one_completion(text):
    sources, flags = resolve_hadith(text)
    assert _keys(flags) == ["hadith_corpus_partial"]
    assert flags[0].type == "warn"
    refs, _, completion = flags[0].detail.partition("|")
    # Verbatim from the first record in order (bukhari before muslim), not from the user.
    assert completion == "امْرِئٍ مَا نَوَى، فَمَنْ كَانَتْ هِجْرَتُهُ إِلَى دُنْيَا يُصِيبُهَا"
    assert [s.ref for s in sources] == [
        "صحيح البخاري، معرّف السجل في الملف المرجعي: 1 (ليس رقم التخريج المطبوع)",
        "صحيح مسلم، معرّف السجل في الملف المرجعي: 9 (ليس رقم التخريج المطبوع)",
    ]
    assert all(s.grade is None for s in sources)
    assert refs.count(NOT_TAKHRIJ) == 2


def test_every_input_form_gives_identical_results():
    results = [resolve_hadith(text) for text in PARTIAL_FORMS]
    assert all(result == results[0] for result in results)


def test_records_that_continue_differently_give_no_completion():
    sources, flags = resolve_hadith("قال رسول الله ﷺ: «الطهور شطر الإيمان كله»")
    assert _keys(flags) == ["hadith_corpus_ambiguous"]
    assert "|" not in flags[0].detail
    assert [s.ref.split("،")[0] for s in sources] == ["صحيح البخاري", "صحيح مسلم"]
    text = render_flag(flags[0]).text
    assert "تملأ" not in text and "نور" not in text
    assert "المراجع الشرعي / المختص" in text


def test_fabricated_saying_holding_a_true_fragment_still_blocks(corpus):
    _write(
        corpus,
        [*RECORDS, {"c": "muslim", "r": 12, "t": "حدثنا جابر كل بدعة ضلالة وكل ضلالة في النار"}],
    )
    hadith_corpus.load_corpus.cache_clear()
    for text in (
        "«كل بدعة ضلالة إلا بدعة في عبادة»",
        "قال ﷺ: «كل بدعة ضلالة إلا بدعة في عبادة حسنة»",
    ):
        sources, flags = resolve_hadith(text)
        assert _keys(flags) == ["hadith_fabricated"] and flags[0].type == "block"
        assert sources == []


@pytest.mark.parametrize(
    "text",
    [
        "قال رسول الله ﷺ: «شطر الإيمان كله»",  # 3 words
        "«حدثنا قتيبة عن مالك»",  # 4 words, only 2 outside the formulas
        "قال رسول الله ﷺ: «الطهور شطر الإيمان كله والزكاة»",  # not a contiguous run
    ],
)
def test_short_formulaic_or_noncontiguous_quote_gets_no_completion(text):
    sources, flags = resolve_hadith(text)
    assert _keys(flags) == ["hadith_unsourced"] and sources == []


def test_order_of_the_file_does_not_change_the_result(corpus):
    first = resolve_hadith(PARTIAL_FORMS[0])
    _write(corpus, list(reversed(RECORDS)))
    hadith_corpus.load_corpus.cache_clear()
    assert resolve_hadith(PARTIAL_FORMS[0]) == first == resolve_hadith(PARTIAL_FORMS[0])


def test_more_than_five_sources_are_listed_with_a_count(corpus):
    same = "حدثنا راو قال رسول الله ﷺ غرس النخيل في الوادي صدقة جارية"
    _write(corpus, [{"c": "muslim", "r": n, "t": same} for n in range(1, 8)])
    hadith_corpus.load_corpus.cache_clear()
    sources, flags = resolve_hadith("قال ﷺ: «غرس النخيل في الوادي»")
    assert _keys(flags) == ["hadith_corpus_partial"]
    assert len(sources) == 5
    assert flags[0].detail.split("|")[0].endswith("، +2")


def test_a_quote_in_too_many_records_is_listed_not_completed(corpus):
    same = "حدثنا راو قال رسول الله ﷺ غرس النخيل في الوادي صدقة جارية"
    count = hadith_corpus.MAX_COMPARED_RECORDS + 1
    _write(corpus, [{"c": "muslim", "r": n, "t": same} for n in range(1, count + 1)])
    hadith_corpus.load_corpus.cache_clear()
    _, flags = resolve_hadith("قال ﷺ: «غرس النخيل في الوادي»")
    assert _keys(flags) == ["hadith_corpus_ambiguous"]
    assert flags[0].detail.endswith(f"، +{count - 5}")


def test_absent_corpus_leaves_the_quote_unsourced(monkeypatch, tmp_path):
    monkeypatch.setattr(hadith_corpus, "CORPUS_PATH", tmp_path / "absent.json.gz")
    hadith_corpus.load_corpus.cache_clear()
    assert _keys(resolve_hadith(PARTIAL_FORMS[0])[1]) == ["hadith_unsourced"]


async def test_suggestion_keeps_the_users_text_null_output_and_review():
    class NoLLM:
        async def complete_json(self, prompt, schema):
            raise AssertionError("no LLM call for a corpus suggestion")

    req = TranslateRequest(text=PARTIAL_FORMS[0], target_lang="en", mode="localize")
    resp = await orchestrator.translate(req, NoLLM())
    seg = resp.segments[0]
    assert seg.source == PARTIAL_FORMS[0]
    assert seg.output is None and resp.review_queue == [seg.id]
    assert any("يُصِيبُهَا" in flag.text and flag.severity == "warn" for flag in seg.flags)


def test_index_build_time_and_memory_on_a_fixture(corpus):
    rng = random.Random(77)
    words = [f"كلمة{n}" for n in range(3000)]
    records = [
        {"c": "bukhari", "r": n, "t": " ".join(rng.choices(words, k=80))} for n in range(1, 2001)
    ]
    _write(corpus, records)
    hadith_corpus.load_corpus.cache_clear()
    tracemalloc.start()
    started = time.perf_counter()
    hadith_corpus.load_corpus()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # 2000 records ≈ 1/7 of the real corpus; budget for the real one is +120 MB and +3 s.
    assert elapsed < 1.5
    assert peak < 30 * 2**20


def test_shipped_corpus_is_a_draft_with_keys_the_server_would_compute():
    shipped = Path(hadith_corpus.__file__).resolve().parents[3] / "data" / "hadith"
    data = json.loads(gzip.decompress((shipped / "corpus_bukhari_muslim.json.gz").read_bytes()))
    assert data["status"] == "draft" and data["grade"] is None
    assert len(data["items"]) == 14736
    for item in random.Random(0).sample(data["items"], 200):
        assert item["k"] == match_key(item["t"])
