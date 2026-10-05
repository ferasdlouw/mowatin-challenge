"""D-052: a known hadith quoted with no «…» (with or without the attribution formula)."""

from __future__ import annotations

import pytest

from app.pipeline.classifier import classify
from app.pipeline.hadith import find_bare, load_items, resolve_hadith
from app.pipeline.segmenter import segment

NIYYAT = "إنما الأعمال بالنيات، وإنما لكل امرئ ما نوى"


@pytest.fixture(autouse=True)
def real_slots():
    load_items.cache_clear()
    yield
    load_items.cache_clear()


def _keys(flags):
    return [f.key for f in flags]


@pytest.mark.parametrize(
    "text",
    [
        NIYYAT,
        "إنما الأعمال بالنية",
        f"قال رسول الله ﷺ: {NIYYAT}",
        f"قال رسول الله صلى الله عليه وسلم: {NIYYAT}",
    ],
)
def test_bare_hadith_is_sourced_and_shown_in_full(text):
    assert classify(text)["category"] == "hadith"
    sources, flags = resolve_hadith(text)
    assert [s.ref for s in sources] == ["bukhari 1"]
    assert _keys(flags) == ["hadith_sourced", "hadith_identified"]
    assert flags[1].detail == f"bukhari 1|{NIYYAT}"


def test_extra_words_keep_the_source_but_go_to_review():
    sources, flags = resolve_hadith(f"{NIYYAT} ولو كان العمل قليلًا")
    assert [s.ref for s in sources] == ["bukhari 1"]
    assert _keys(flags) == ["hadith_identified", "hadith_partial"]
    assert flags[1].type == "warn"


def test_bare_fabricated_saying_is_blocked():
    assert classify("اطلبوا العلم ولو في الصين")["category"] == "hadith"
    sources, flags = resolve_hadith("اطلبوا العلم ولو في الصين")
    assert sources == []
    assert flags[0].key == "hadith_fabricated" and flags[0].type == "block"


@pytest.mark.parametrize(
    "text",
    [
        "النية مهمة في الأعمال بالنيات",  # a two-word variant inside a longer sentence
        "الصبر مفتاح الفرج",
        "كان النبي ﷺ رحيمًا بالناس.",
    ],
)
def test_ordinary_text_is_not_taken_for_a_hadith(text):
    assert find_bare(text) is None
    assert classify(text)["category"] != "hadith"


def test_forms_of_one_hadith_cover_the_sentence_together():
    # «الإحسان» is only in a variant, «فإن لم تكن تراه فإنه يراك» only in the full text.
    text = "الإحسان أن تعبد الله كأنك تراه، فإن لم تكن تراه فإنه يراك."
    found = find_bare(text)
    assert found is not None and found[1]["id"] == "h_jibril_ihsan" and found[2]
    assert segment(text) == [text]


def test_a_comment_after_the_hadith_is_its_own_segment():
    assert segment(f"{NIYYAT}، فأخلص نيتك في عملك") == [f"{NIYYAT}،", "فأخلص نيتك في عملك"]


def test_unmatched_extra_clause_keeps_the_sentence_whole():
    # No run of clauses is the hadith alone: the sentence stays whole and goes to review.
    text = "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى ولو كان قليلًا، والله أعلم"
    assert segment(text) == [text]
