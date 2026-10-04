"""data/demo/examples.json: each item's `shows` is what the pipeline returns for its text_ar.

The demo (Eng. Feras's UI and video) breaks silently if a data or code change moves an example
off its feature, so every item is checked for both targets. No LLM: the flags are deterministic.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.pipeline.report import load_messages

DEMO_PATH = Path(__file__).resolve().parents[3] / "data" / "demo" / "examples.json"
_DEMO = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
_ITEMS = [] if _DEMO.get("status") == "placeholder" else _DEMO.get("items", [])


def _prefix(key: str) -> str:
    return re.split(r"\{[a-z_]+\}", load_messages()[key])[0]


def _shows(segments: list[dict]) -> set[str]:
    flags = [f for s in segments for f in s["flags"]]
    found = set()
    if any(
        s["type"] == "term_heavy" and any(x["kind"] == "glossary" for x in s["sources"])
        for s in segments
    ):
        found.add("term_lock")
    for key, severity in (
        ("quran_mismatch", "block"),
        ("hadith_unsourced", "warn"),
        ("fatwa_referral", "warn"),
    ):
        if any(f["severity"] == severity and f["text"].startswith(_prefix(key)) for f in flags):
            found.add(key)
    referred = any(s["level"] == "D" for s in segments)
    if not referred and all(f["severity"] == "info" for f in flags):
        found.add("general")
    return found


@pytest.mark.skipif(not _ITEMS, reason="demo slot is a placeholder")
@pytest.mark.parametrize("target", ["en", "fr"])
@pytest.mark.parametrize("item", _ITEMS, ids=[i["id"] for i in _ITEMS])
def test_demo_item_shows_its_feature(client, item, target):
    resp = client.post("/v1/translate", json={"text": item["text_ar"], "target_lang": target})
    assert resp.status_code == 200
    assert item["shows"] in _shows(resp.json()["segments"])
