"""Every live prompt names the JSON keys its schema requires (D-032).

Fakes answer by schema, so a prompt that never names its key passes every other test
while a real model answers with its own keys and every call fails validation.
"""

from __future__ import annotations

from collections import defaultdict

import pytest
from pydantic import BaseModel

from app.pipeline.localizer import LOCALIZE_PROMPT, PROMPTS_DIR, RAW_PROMPT, TranslationOutput
from app.pipeline.verifier import BACKTRANSLATE_PROMPT, JUDGE_PROMPT, BackTranslation, JudgeOutput


@pytest.mark.parametrize(
    ("prompt_file", "schema"),
    [
        (LOCALIZE_PROMPT, TranslationOutput),
        (RAW_PROMPT, TranslationOutput),
        ("backtranslate_v1.txt", BackTranslation),
        ("judge_v1.txt", JudgeOutput),
        (BACKTRANSLATE_PROMPT, BackTranslation),
        (JUDGE_PROMPT, JudgeOutput),
    ],
)
def test_prompt_names_every_required_json_key(prompt_file: str, schema: type[BaseModel]) -> None:
    template = (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")
    rendered = template.format_map(defaultdict(str))

    for name, field in schema.model_fields.items():
        if field.is_required():
            assert f'"{name}"' in rendered, f"{prompt_file} never names the key {name!r}"


def test_raw_prompt_is_v3_and_keeps_the_plain_baseline_wording() -> None:
    v1 = (PROMPTS_DIR / "raw_v1.txt").read_text(encoding="utf-8")
    v2 = (PROMPTS_DIR / RAW_PROMPT).read_text(encoding="utf-8")

    # v3 (D-037) = v2 + the data-only rule restated after <user_text>.
    assert RAW_PROMPT == "raw_v3.txt"
    assert v2.startswith(v1.split("\n", 1)[0])
    assert "<user_text>\n{text}\n</user_text>" in v2
