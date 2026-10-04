from __future__ import annotations

import pytest

import app.pipeline.verifier as verifier_module
from app.llm.base import LLMResult
from app.llm.router import LLMRouter
from app.pipeline.verifier import backtranslation_similarity, combine, find_whole_word, verify
from app.schemas import LockedTerm, TargetLang


@pytest.mark.asyncio
async def test_deterministic_term_failure_caps_confidence():
    locked_terms = [LockedTerm(ar="التوحيد", out="Tawhid", glossary_id="tawhid")]

    # Missing term in output
    output = "This is a translation."
    text = "التوحيد أساس الإسلام."
    lang: TargetLang = "en"

    # Create empty router that returns None for llm calls
    router = LLMRouter([])

    confidence, marks, flags = await verify(
        text, output, lang, "general_non_muslim", locked_terms, router
    )
    assert confidence < 0.75
    assert any(f.key == "term_check_failed" for f in flags)


@pytest.mark.asyncio
async def test_marks_contain_exact_rendered_strings():
    locked_terms = [LockedTerm(ar="التوحيد", out="Tawhid", glossary_id="tawhid")]

    output = "Tawhid is the basis of Islam."
    text = "التوحيد أساس الإسلام."
    lang: TargetLang = "en"

    router = LLMRouter([])

    confidence, marks, flags = await verify(
        text, output, lang, "general_non_muslim", locked_terms, router
    )
    assert "Tawhid" in marks


TEXT = "التوحيد أساس الإسلام."
GOOD_OUTPUT = "Tawhid is the basis of Islam."
TAWHID = [LockedTerm(ar="التوحيد", out="Tawhid", glossary_id="tawhid")]


class _Answers:
    """Fake completer: ``None`` for a schema means the call failed (``data=None``)."""

    def __init__(self, **answers):
        self.answers = answers
        self.calls = []

    async def complete_json(self, prompt, schema):
        self.calls.append(schema.__name__)
        raw = self.answers.get(schema.__name__)
        data = None if raw is None else schema.model_validate(raw)
        return LLMResult(data=data)


def test_backtranslation_close_pair_scores_high():
    back = "التَّوحيدُ أساسُ الاسلام"  # diacritics, hamza and punctuation differ
    assert backtranslation_similarity(TEXT, back) >= 0.9
    assert backtranslation_similarity(TEXT, "التوحيد هو أساس دين الإسلام") >= 0.6


def test_backtranslation_unrelated_pair_scores_low():
    assert backtranslation_similarity(TEXT, "ذهبت إلى السوق لشراء الخبز") <= 0.2


def test_backtranslation_identical_and_empty():
    assert backtranslation_similarity(TEXT, TEXT) == 1.0
    assert backtranslation_similarity(TEXT, "") == 0.0
    assert backtranslation_similarity("", "") == 0.0


@pytest.mark.parametrize(
    ("text", "found"),
    [("syntax error", False), ("taxes", False), ("a TAX.", True), ("tax", True), ("(Tax)", True)],
)
def test_avoid_word_matches_whole_words_only(text, found):
    assert (find_whole_word("tax", text) is not None) is found


def test_avoid_word_whole_word_is_unicode_aware():
    assert find_whole_word("unicité", "L'Unicité de Dieu") is not None
    assert find_whole_word("unicit", "L'unicité de Dieu") is None
    assert find_whole_word("dieu", "Dieux") is None


async def test_avoid_word_inside_longer_word_does_not_fail_term_check():
    # "unity" is a tawhid avoid word; it appears only inside "community".
    output = "Tawhid unites the community."
    router = _Answers(BackTranslation={"arabic_text": TEXT})
    _, _, flags = await verify(TEXT, output, "en", "general_non_muslim", TAWHID, router)
    assert not any(f.key == "avoid_word_found" for f in flags)


async def test_avoid_word_as_whole_word_fails_term_check():
    output = "Tawhid, or Unity, is the basis of Islam."
    router = _Answers(BackTranslation={"arabic_text": TEXT})
    confidence, _, flags = await verify(TEXT, output, "en", "general_non_muslim", TAWHID, router)
    assert any(f.key == "avoid_word_found" for f in flags)
    assert confidence < 0.75


async def test_judge_unset_keeps_confidence_below_threshold():
    """Perfect term check and back-translation, but no JUDGE_* slot: the segment goes to review."""
    router = _Answers(BackTranslation={"arabic_text": TEXT})
    confidence, _, flags = await verify(
        TEXT, GOOD_OUTPUT, "en", "general_non_muslim", TAWHID, router
    )
    assert flags == []
    assert confidence == 0.6
    assert confidence < 0.75


async def test_judge_failure_scores_zero(monkeypatch):
    judge = _Answers(JudgeOutput=None)
    monkeypatch.setattr(verifier_module, "_judge_router", lambda _router: judge)
    router = _Answers(BackTranslation={"arabic_text": TEXT})
    seen = []
    confidence, _, _ = await verify(
        TEXT, GOOD_OUTPUT, "en", "general_non_muslim", TAWHID, router, on_usage=seen.append
    )
    assert judge.calls == ["JudgeOutput"]
    assert len(seen) == 1
    assert confidence == 0.6


async def test_all_checks_pass_reaches_threshold(monkeypatch):
    judge = _Answers(JudgeOutput={"score": 0.9})
    monkeypatch.setattr(verifier_module, "_judge_router", lambda _router: judge)
    router = _Answers(BackTranslation={"arabic_text": TEXT})
    confidence, _, _ = await verify(TEXT, GOOD_OUTPUT, "en", "general_non_muslim", TAWHID, router)
    assert confidence == 0.96


async def test_backtranslation_failure_scores_zero(monkeypatch):
    judge = _Answers(JudgeOutput={"score": 1.0})
    monkeypatch.setattr(verifier_module, "_judge_router", lambda _router: judge)
    router = _Answers(BackTranslation=None)
    confidence, _, _ = await verify(TEXT, GOOD_OUTPUT, "en", "general_non_muslim", TAWHID, router)
    assert confidence == 0.75


def test_combine_formula_and_term_failure_cap():
    assert combine(1.0, 1.0, 1.0) == 1.0
    assert combine(0.0, 1.0, 1.0) == 0.65
    assert combine(0.0, 1.0, 1.0) < 0.75


def test_prompts_keep_criteria_and_delimit_user_text():
    judge = verifier_module._prompt("judge_v1.txt", lang_name="English", text="T", output="O")
    assert "meaning preserved, no added claims" in judge
    assert "<original>\nT\n</original>" in judge and "<translation>\nO\n</translation>" in judge
    back = verifier_module._prompt("backtranslate_v1.txt", lang_name="English", output="O")
    assert "<translation>\nO\n</translation>" in back
