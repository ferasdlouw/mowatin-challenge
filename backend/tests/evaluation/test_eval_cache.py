"""D-059 (code audit item 7): evaluation runs never reuse cached answers.

``run_eval.py --runs 3`` (the documented reproduce command) sends the same texts three times
to one app; with the response cache on, runs 2 and 3 were served from memory without a model
call, so the run-to-run spread read as zero.
"""

from __future__ import annotations

from typing import Any

import pytest
import run_eval as r
from fastapi.testclient import TestClient
from pydantic import BaseModel

import app.main as main_module
from app.config import Settings
from app.llm.base import LLMResult
from app.pipeline import cache

TEXT = {"text": "التوحيد أساس الإسلام", "target_lang": "en"}


class CountingRouter:
    """Every call succeeds, so a response is cacheable."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        self.calls += 1
        fields = {name: (1.0 if name == "score" else "x") for name in schema.model_fields}
        return LLMResult(data=schema(**fields), provider="fake", model="fake")


@pytest.fixture()
def router(monkeypatch) -> CountingRouter:
    fake = CountingRouter()
    monkeypatch.setattr(main_module, "build_router", lambda _settings, _http: fake)
    cache.clear()
    return fake


def _calls_per_request(client_post, router: CountingRouter, times: int = 2) -> list[int]:
    counts = []
    for _ in range(times):
        before = router.calls
        assert client_post(TEXT).status_code == 200
        counts.append(router.calls - before)
    return counts


def test_in_process_eval_calls_the_models_on_every_run(router):
    post, close = r._in_process_post()
    try:
        counts = _calls_per_request(post, router)
    finally:
        close()
    assert counts[0] > 0
    assert counts[1] == counts[0]


@pytest.mark.parametrize(("enabled", "second"), [(True, 0), (False, None)])
def test_response_cache_setting(router, enabled, second):
    settings = Settings(_env_file=None, env="test", response_cache=enabled)  # type: ignore[call-arg]
    with TestClient(main_module.create_app(settings)) as client:
        counts = _calls_per_request(lambda body: client.post("/v1/translate", json=body), router)
    assert counts[0] > 0
    assert counts[1] == (counts[0] if second is None else second)


def test_several_runs_against_a_server_warn_about_its_cache(monkeypatch, capsys):
    monkeypatch.setattr(r, "evaluate", lambda *args, **kwargs: {})
    monkeypatch.setattr(r, "format_table", lambda scores: "")
    monkeypatch.setattr(r, "_gt_key", lambda: "")
    monkeypatch.setattr(r.Path, "write_text", lambda self, *a, **k: 0)
    r.main(["--split", "dev", "--runs", "2", "--api-url", "http://127.0.0.1:9"])
    assert "RESPONSE_CACHE=false" in capsys.readouterr().err
