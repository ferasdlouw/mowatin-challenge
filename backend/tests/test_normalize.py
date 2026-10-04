from app.pipeline.normalize import (
    get_word_variants,
    normalize_text,
    normalize_with_mapping,
    tokenize,
)


def test_normalize_text():
    # Strip tashkeel and tatweel
    assert normalize_text("بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ") == "بسم الله الرحمٰن الرحيم"
    assert normalize_text("تـطـويـل") == "تطويل"

    # Unify chars
    assert normalize_text("أإآ") == "ااا"
    assert normalize_text("مدرسة") == "مدرسه"
    assert normalize_text("تقوى") == "تقوي"


def test_normalize_with_mapping():
    text = "بِسْمِ"
    norm, mapping = normalize_with_mapping(text)
    assert norm == "بسم"
    # ب is at 0, س is at 2 (since 1 is kasra), م is at 4
    assert mapping[0] == 0  # ب
    assert mapping[1] == 2  # س
    assert mapping[2] == 4  # م
    assert mapping[3] == 6  # length


def test_get_word_variants():
    # No prefix
    variants = get_word_variants("صبر")
    assert variants == [("صبر", 0)]

    # One prefix
    variants = get_word_variants("والصبر")
    # "والصبر" -> "والصبر" (0), "صبر" (3 - 'وال'), "لصبر" (2 - 'وا' is not in PREFIXES, but 'و' is 1, so 'والصبر'[1:] -> 'الصبر')
    # wait, get_word_variants checks all matches in PREFIXES
    # PREFIXES has 'وال', 'و', 'ال'
    # "والصبر".startswith('وال') -> 'صبر', 3
    # "والصبر".startswith('و') -> 'الصبر', 1
    # "والصبر".startswith('ال') -> False

    # The returned list is [(word, 0)] + [(stripped, len)]
    v_texts = [v[0] for v in variants]
    assert "والصبر" in v_texts
    assert "صبر" in v_texts
    assert "الصبر" in v_texts


def test_tokenize():
    text = "والصبر"
    tokens = tokenize(text)
    assert len(tokens) == 1
    t = tokens[0]
    assert t["word"] == "والصبر"
    assert t["start_orig"] == 0
    assert t["end_orig"] == 6

    v_texts = [v["text"] for v in t["variants"]]
    assert "صبر" in v_texts

    text2 = "بِسْمِ اللَّهِ"
    tokens2 = tokenize(text2)
    assert len(tokens2) == 2
    assert tokens2[0]["word"] == "بسم"
    assert tokens2[0]["start_orig"] == 0
    assert tokens2[0]["end_orig"] == 6
