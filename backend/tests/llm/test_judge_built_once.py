"""D-061 (code audit item 9): the judge router is built once, from the app's settings.

Before, ``verifier._judge_router`` built a new ``LLMRouter`` for every verified segment from
``get_settings()``: it re-read the environment and ``.env`` each time and ignored the settings
the app was created with. An invalid ``JUDGE_*`` slot was swallowed without a trace.
"""

from __future__ import annotations

import logging

import httpx
import pytest

import app.pipeline.verifier as verifier_module
from app.config import Settings
from app.llm.factory import build_router
from app.llm.router import LLMRouter
from app.pipeline.budget import RequestBudget, RequestLimits
from app.pipeline.orchestrator import _CostMeter, _MeteredRouter

KEY = "judge-key-value-not-for-logs"


def _settings(**judge: str) -> Settings:
    return Settings(_env_file=None, env="test", **judge)  # type: ignore[call-arg]


@pytest.fixture()
def http():
    return httpx.AsyncClient()


def test_router_carries_the_judge_built_from_the_given_settings(http):
    settings = _settings(judge_provider="gemini", judge_api_key=KEY, judge_model="judge-model")
    router = build_router(settings, http)
    assert isinstance(router.judge, LLMRouter)
    assert [p.model for p in router.judge._providers] == ["judge-model"]


def test_unset_judge_slot_means_no_judge(http):
    assert build_router(_settings(), http).judge is None


def test_invalid_judge_slot_is_logged_once_without_values(http, caplog):
    settings = _settings(judge_provider="nope", judge_api_key=KEY, judge_model="m")
    with caplog.at_level(logging.WARNING, logger="app.llm"):
        router = build_router(settings, http)
    assert router.judge is None
    lines = [r.getMessage() for r in caplog.records if "judge_config_invalid" in r.getMessage()]
    assert len(lines) == 1
    assert "JUDGE_PROVIDER" in lines[0]
    assert KEY not in lines[0]


def test_verifier_uses_the_apps_judge_and_never_reads_the_environment(monkeypatch, http):
    # The environment says there is a judge; the app was built without one.
    monkeypatch.setenv("JUDGE_PROVIDER", "gemini")
    monkeypatch.setenv("JUDGE_API_KEY", KEY)
    monkeypatch.setenv("JUDGE_MODEL", "env-model")
    no_judge = _settings(
        llm_provider="gemini", llm_api_key="k", llm_model="m", judge_provider="", judge_model=""
    )
    router = build_router(no_judge, http)
    assert verifier_module._judge_router(router) is None
    metered = _MeteredRouter(router, _CostMeter(), RequestBudget(RequestLimits()))
    assert verifier_module._judge_router(metered) is None


def test_metered_router_hands_over_the_same_judge(http):
    settings = _settings(judge_provider="gemini", judge_api_key=KEY, judge_model="judge-model")
    router = build_router(settings, http)
    metered = _MeteredRouter(router, _CostMeter(), RequestBudget(RequestLimits()))
    assert verifier_module._judge_router(metered) is router.judge
