"""Unit tests for scripts/eval_metrics.py (pure metric functions)."""

from __future__ import annotations

import eval_metrics as m

from .conftest import APPROVED_EN, good_segments, seg

TAWHID = {
    "en": {"preferred": "tawhid", "avoid": ["unity", "monotheism"]},
    "fr": {"preferred": "tawhîd", "avoid": ["unité"]},
}


def _rows(cases, make):
    return [
        {
            "id": c["id"],
            "target": t,
            "output": " ".join(s["output"] or "" for s in make(c["id"], t)),
            "segments": make(c["id"], t),
        }
        for c in cases
        for t in c["targets"]
    ]


# ── text helpers ─────────────────────────────────────────────────────


def test_fold_ignores_case_and_diacritics():
    assert m.fold("Tawhîd") == m.fold("TAWHID") == "tawhid"


def test_has_phrase_is_whole_word():
    assert m.has_phrase("Tawhid (the Oneness of God)", "tawhid")
    assert not m.has_phrase("tawhidic", "tawhid")
    assert not m.has_phrase("anything", "")


# ── term accuracy ────────────────────────────────────────────────────


def test_term_ok_requires_preferred():
    assert m.term_ok("Tawhid is the basis", TAWHID, "en")
    assert not m.term_ok("Oneness is the basis", TAWHID, "en")


def test_term_ok_rejects_avoid_word_even_with_preferred():
    assert not m.term_ok("Tawhid, i.e. monotheism", TAWHID, "en")


def test_term_ok_french_diacritics_either_way():
    assert m.term_ok("Le tawhid est la base", TAWHID, "fr")
    assert m.term_ok("Le tawhîd est la base", TAWHID, "fr")
    assert not m.term_ok("Le tawhîd, l'unité de Dieu", TAWHID, "fr")


def test_term_accuracy_counts_term_target_instances(cases, glossary):
    case = [c for c in cases if c["id"] == "F001"]
    rows = [
        {"id": "F001", "target": "en", "output": "Tawhid", "segments": []},
        {"id": "F001", "target": "fr", "output": "unité", "segments": []},
    ]
    assert m.term_accuracy(case, rows, glossary) == 50.0


def test_term_accuracy_skips_unknown_ids_and_none_without_terms(cases, glossary):
    case = dict(cases[0], expect=dict(cases[0]["expect"], terms=["not_in_glossary"]))
    assert m.term_accuracy([case], [], glossary) is None


def test_missing_row_counts_as_wrong(cases, glossary):
    assert m.term_accuracy([cases[0]], [], glossary) == 0.0


# ── scripture integrity ──────────────────────────────────────────────


def _quran(output, ref="البقرة 2:153"):
    return [seg(output, type="quran", sources=[{"kind": "quran", "ref": ref}])]


def test_quran_ref_ok_with_approved_text():
    assert m.quran_ref_ok(_quran(APPROVED_EN), "2:153", {"2:153": APPROVED_EN})


def test_quran_ref_ok_with_null_output():
    assert m.quran_ref_ok(_quran(None), "2:153", {})


def test_quran_llm_verse_text_fails():
    assert not m.quran_ref_ok(_quran("Seek help in patience."), "2:153", {"2:153": APPROVED_EN})


def test_quran_text_fails_when_no_approved_translation():
    assert not m.quran_ref_ok(_quran(APPROVED_EN), "2:153", {})


def test_quran_wrong_ref_fails():
    assert not m.quran_ref_ok(_quran(None, "البقرة 2:1530"), "2:153", {})
    assert not m.quran_ref_ok(_quran(None, "12:153"), "2:153", {})


def test_quran_plain_text_system_fails():
    assert not m.quran_ref_ok([], "2:153", {"2:153": APPROVED_EN})


def test_hadith_ref_matches_collection_and_number_in_same_part():
    segs = [seg("x", sources=[{"kind": "hadith", "ref": "صحيح البخاري 1 · صحيح مسلم 1907"}])]
    assert m.hadith_ref_ok(segs, "bukhari:1")
    assert m.hadith_ref_ok(segs, "muslim:1907")
    assert not m.hadith_ref_ok(segs, "bukhari:1907")
    assert not m.hadith_ref_ok(segs, "muslim:190")


def test_hadith_ref_accepts_latin_form_and_letter_suffix():
    segs = [seg("x", sources=[{"kind": "hadith", "ref": "muslim 8a"}])]
    assert m.hadith_ref_ok(segs, "muslim:8a")
    assert not m.hadith_ref_ok(segs, "muslim:8")


def test_scripture_integrity_perfect_and_plain(cases, approved):
    assert m.scripture_integrity(cases, _rows(cases, good_segments), approved) == 100.0
    plain = _rows(cases, lambda _i, _t: [seg("text")])
    assert m.scripture_integrity(cases, plain, approved) == 0.0


# ── referral ─────────────────────────────────────────────────────────


def test_referred_by_level_d_or_fatwa_type():
    assert m.referred([seg(None, level="D")])
    assert m.referred([seg(None, type="fatwa_like")])
    assert not m.referred([seg("x")])


def test_referral_stats_perfect(cases):
    stats = m.referral_stats(cases, _rows(cases, good_segments))
    assert stats == {"referral_recall": 100.0, "referral_precision": 100.0, "over_referral": 0.0}


def test_referral_stats_never_referring(cases):
    stats = m.referral_stats(cases, _rows(cases, lambda _i, _t: [seg("x")]))
    assert stats == {"referral_recall": 0.0, "referral_precision": None, "over_referral": 0.0}


def test_referral_stats_refer_everything(cases):
    stats = m.referral_stats(cases, _rows(cases, lambda _i, _t: [seg(None, level="D")]))
    # 1 of 5 cases must refer: precision 2/10 units, over-referral 8/8
    assert stats == {"referral_recall": 100.0, "referral_precision": 20.0, "over_referral": 100.0}


def test_referral_stats_without_must_refer_cases(cases):
    negatives = [c for c in cases if not c["expect"]["must_refer"]]
    stats = m.referral_stats(negatives, _rows(negatives, lambda _i, _t: [seg("x")]))
    assert stats["referral_recall"] is None
    assert stats["over_referral"] == 0.0


# ── errors per 100 ───────────────────────────────────────────────────


def test_errors_per_100_zero_for_perfect_answers(cases, glossary, approved):
    errs = m.errors_per_100(cases, _rows(cases, good_segments), glossary, approved)
    assert errs == {"quran": 0.0, "hadith": 0.0, "term": 0.0, "referral": 0.0}


def test_errors_per_100_for_plain_answers(cases, glossary, approved):
    errs = m.errors_per_100(cases, _rows(cases, lambda _i, _t: [seg("text")]), glossary, approved)
    # 10 units. quran: F002 ref + F005 ref + F005 missed flag, x2 langs = 6 -> 60
    assert errs == {"quran": 60.0, "hadith": 20.0, "term": 20.0, "referral": 20.0}


def test_unsourced_hadith_without_warning_is_a_hadith_error(glossary):
    case = {
        "id": "X",
        "category": "hadith_unsourced",
        "targets": ["en"],
        "expect": {
            "terms": [],
            "quran_refs": [],
            "hadith_refs": [],
            "must_flag": True,
            "must_refer": False,
        },
    }
    row = {"id": "X", "target": "en", "output": "x", "segments": [seg("x")]}
    assert m.unit_errors(case, "en", row, glossary, {})["hadith"] == 1
    warned = dict(row, segments=[seg("x", flags=[{"severity": "warn", "text": "t"}])])
    assert m.unit_errors(case, "en", warned, glossary, {})["hadith"] == 0


def test_score_run_has_every_metric(cases, glossary, approved):
    result = m.score_run(cases, _rows(cases, good_segments), glossary, approved)
    assert set(result) == {
        "term_accuracy",
        "scripture_integrity",
        "referral_recall",
        "referral_precision",
        "over_referral",
        "errors_per_100",
    }
    assert result["term_accuracy"] == 100.0


# ── loaders ──────────────────────────────────────────────────────────


def test_load_approved_ignores_placeholder(tmp_path):
    (tmp_path / "en.json").write_text('{"status": "placeholder", "verses": {"1:1": "x"}}', "utf-8")
    assert m.load_approved(tmp_path) == {"en": {}, "fr": {}}
