from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app.llm.router import LLMRouter
from app.pipeline.glossary import get_index
from app.pipeline.injection import neutralize_tags
from app.schemas import Audience, LockedTerm, TargetLang

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
# v2 added explicit guardrails (D-025); v3 restates them after the data block (D-037).
# Older versions stay unchanged on disk.
LOCALIZE_PROMPT = "localize_v3.txt"
# raw_v2 named the JSON key (D-032); v3 restates the rules after the data block (D-037).
RAW_PROMPT = "raw_v3.txt"

# One instruction per ARCHITECTURE.md §4 audience; a test keeps the keys equal to `Audience`.
AUDIENCE_MAP: dict[Audience, str] = {
    "general_non_muslim": "general non-Muslims. Explain concepts simply and avoid assuming prior Islamic knowledge.",
    "new_muslim": "new Muslims. Keep standard Islamic terms, explain each briefly in plain words on first use, and use a warm, encouraging tone; assume little knowledge of practice.",
    "youth": "young readers. Use short sentences and clear, everyday wording while keeping a respectful tone.",
    "academic": "academics and students of knowledge. Maintain academic rigor, precise terminology, and a scholarly tone.",
}


class TranslationOutput(BaseModel):
    output: str


async def localize_segment(
    text: str,
    target_lang: TargetLang,
    audience: Audience,
    detected_term_ids: list[str],
    router: LLMRouter,
) -> tuple[str | None, list[LockedTerm], list]:
    """Translate a segment with audience adaptation and term locking."""
    lang_name = "English" if target_lang == "en" else "French"
    audience_instruction = AUDIENCE_MAP[audience]

    constraints = []
    locked_terms = []

    if detected_term_ids:
        constraints.append("You MUST adhere to the following terminology constraints:")
        glossary_index = get_index()
        for term_id in detected_term_ids:
            term = glossary_index.entries.get(term_id)
            if not term:
                continue

            lang_data = term.get(target_lang)
            if not isinstance(lang_data, dict):
                continue

            ar_text = term.get("ar", "")
            strategy = term.get("strategy", "translate")
            preferred = lang_data.get("preferred", "")
            gloss = lang_data.get("gloss", "")
            avoid = lang_data.get("avoid", [])

            if strategy == "keep_and_gloss" and preferred:
                gloss_text = f" ({gloss})" if gloss else ""
                constraints.append(
                    f"- For '{ar_text}', use the romanized term and provide a short gloss on first use: '{preferred}{gloss_text}'"
                )
                locked_terms.append(LockedTerm(ar=ar_text, out=preferred, glossary_id=term_id))
            elif strategy == "translate" and preferred:
                constraints.append(
                    f"- For '{ar_text}', ALWAYS translate exactly as: '{preferred}'"
                )
                locked_terms.append(LockedTerm(ar=ar_text, out=preferred, glossary_id=term_id))
            elif strategy == "context":
                constraints.append(_context_constraint(ar_text, preferred, gloss, avoid))

    constraints_section = "\n".join(constraints) if constraints else ""

    template = (PROMPTS_DIR / LOCALIZE_PROMPT).read_text(encoding="utf-8")
    prompt = template.format(
        lang_name=lang_name,
        audience_instruction=audience_instruction,
        constraints_section=constraints_section,
        text=neutralize_tags(text),
    )

    res = await router.complete_json(prompt, TranslationOutput)

    output = res.data.output if res.data else None
    return output, locked_terms, res.flags


def _context_constraint(ar_text: str, preferred: str, gloss: str, avoid: list[str]) -> str:
    """A multi-sense term (D-058): the approved rendering is the default, not forced, since
    another sense may be meant («الإحسان» said of Allah is beneficence); avoid words never."""
    rule = f"- For '{ar_text}', the sense depends on the context"
    if preferred:
        usual = f"{preferred} ({gloss})" if gloss else preferred
        rule += f"; the approved rendering of its usual sense is '{usual}', use it unless the context requires another sense"
    if avoid:
        rule += f"; AVOID these words: {', '.join(avoid)}"
    return rule + "."


async def raw_translate(
    text: str, target_lang: TargetLang, router: LLMRouter
) -> tuple[str | None, list]:
    """Translate a segment directly, forming a baseline for comparison."""
    lang_name = "English" if target_lang == "en" else "French"

    template = (PROMPTS_DIR / RAW_PROMPT).read_text(encoding="utf-8")
    prompt = template.format(lang_name=lang_name, text=neutralize_tags(text))

    res = await router.complete_json(prompt, TranslationOutput)

    output = res.data.output if res.data else None
    return output, res.flags
