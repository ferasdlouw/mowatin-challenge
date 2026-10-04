"""Shared helpers for the evaluation-tooling tests (scripts/run_eval.py and friends)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "backend" / "tests" / "fixtures" / "eval"
sys.path.insert(0, str(REPO / "scripts"))

APPROVED_EN = "Fixture approved verse two one five three."
API_REQUEST = httpx.Request("POST", "http://testserver/v1/translate")


def seg(output: str | None, **extra: Any) -> dict[str, Any]:
    """A §4 segment with defaults, overridden by ``extra``."""
    base = {
        "id": 1,
        "source": "",
        "output": output,
        "type": "general",
        "level": "A",
        "locked_terms": [],
        "marks": [],
        "sources": [],
        "confidence": 0.9,
        "flags": [],
    }
    return base | extra


def good_segments(case_id: str, target: str) -> list[dict[str, Any]]:
    """What a correct Muwattin answer looks like for each fixture case."""
    approved = json.loads((FIXTURES / "quran/translations" / f"{target}.json").read_text("utf-8"))
    tawhid = "tawhid" if target == "en" else "tawhîd"
    return {
        "F001": [seg(f"{tawhid.title()} is the basis.", type="term_heavy")],
        "F002": [
            seg(
                approved["verses"]["2:153"],
                type="quran",
                sources=[{"kind": "quran", "ref": "البقرة 2:153"}],
            )
        ],
        "F003": [
            seg(
                "Deeds are by intentions.",
                type="hadith",
                sources=[{"kind": "hadith", "ref": "صحيح البخاري 1 · صحيح مسلم 1907"}],
            )
        ],
        "F004": [seg(None, type="fatwa_like", level="D")],
        "F005": [
            seg(
                None,
                type="quran",
                sources=[{"kind": "quran", "ref": "الفاتحة 1:2"}],
                flags=[{"severity": "block", "text": "x"}],
            )
        ],
    }[case_id]


@pytest.fixture()
def cases() -> list[dict[str, Any]]:
    lines = (FIXTURES / "testset" / "dev.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@pytest.fixture()
def glossary():
    from eval_metrics import load_glossary

    return load_glossary(FIXTURES / "glossary")


@pytest.fixture()
def approved():
    from eval_metrics import load_approved

    return load_approved(FIXTURES / "quran" / "translations")


@pytest.fixture()
def fake_post(cases):
    """Stand-in for POST /v1/translate: perfect localize answers, plain raw answers."""
    by_text = {c["text_ar"]: c["id"] for c in cases}
    seen: list[dict[str, Any]] = []

    def post(body: dict[str, Any]) -> httpx.Response:
        seen.append(body)
        case_id = by_text[body["text"]]
        if body["mode"] == "raw":
            segments = [seg("The unity of God, a plain translation.")]
        else:
            segments = good_segments(case_id, body["target_lang"])
        body_out = {"segments": segments, "summary": {}, "review_queue": []}
        return httpx.Response(200, json=body_out, request=API_REQUEST)

    post.seen = seen  # type: ignore[attr-defined]
    return post
