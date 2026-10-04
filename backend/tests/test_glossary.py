from app.pipeline.glossary import detect, get_index


def test_glossary_singleton():
    idx1 = get_index()
    idx2 = get_index()
    assert idx1 is idx2
    assert len(idx1.glossary_terms) > 0


def test_detect_simple():
    text = "يجب الحفاظ على الإسلام والتوحيد"
    matches = detect(text)

    # الإسلام -> islam
    # والتوحيد -> tawhid

    matched_ids = [m["id"] for m in matches]
    assert "islam" in matched_ids
    assert "tawhid" in matched_ids


def test_exclusion():
    # Should not match 'islam' for المسلم / المسلمين / المسلمون
    text = "المسلم والمسلمين والمسلمون"
    matches = detect(text)

    matched_ids = [m["id"] for m in matches]
    assert "islam" not in matched_ids


def test_longest_match():
    # Example: if glossary has "صلاة" and "صلاة الفجر"
    # we should match "صلاة الفجر" as a single token span.
    # We will test this generally by ensuring phrases work.
    pass
