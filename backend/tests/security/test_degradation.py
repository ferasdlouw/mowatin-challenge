"""The app starts and serves with the fallback or judge (or every LLM) unconfigured."""

from __future__ import annotations

import json
import logging

import pytest

from app.config import Settings
from app.main import llm_slot_status

PRIMARY = {"llm_provider": "gemini", "llm_api_key": "test-key-not-real", "llm_model": "m"}


@pytest.mark.parametrize("overrides", [{}, PRIMARY], ids=["no-llm", "primary-only"])
def test_serves_without_fallback_or_judge(make_client, overrides, caplog):
    caplog.set_level(logging.INFO)
    client = make_client(env="production", **overrides)
    assert client.get("/health").status_code == 200
    assert client.post("/v1/translate", json={"text": "نص"}).status_code == 200
    slots = [r.getMessage() for r in caplog.records if '"llm_slots"' in r.getMessage()]
    assert len(slots) == 1
    assert json.loads(slots[0])["fallback"] == "unset"
    assert "test-key-not-real" not in caplog.text


def test_slot_status_names_states_not_values():
    settings = Settings(_env_file=None, **PRIMARY, judge_provider="gemini", fallback_model="x")  # type: ignore[call-arg]
    assert llm_slot_status(settings) == {
        "llm": "configured",
        "fallback": "incomplete",
        "judge": "incomplete",
    }
