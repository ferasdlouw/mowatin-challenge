"""Speed evidence for model choice (docs/MODELS.md): latency and output tokens/s, no text."""

from __future__ import annotations

import json
import logging

import pytest

from app.llm.base import Completion, Usage
from app.llm.errors import ErrorKind, ProviderError
from app.llm.router import LLMRouter, tokens_per_second
from tests.llm.conftest import Answer, answer_json

CANARY = "CANARY-SPEED الصبر ضياء"


class _Clock:
    """Each read advances 0.25 s, so one attempt (two reads) lasts exactly 250 ms."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.25
        return self.now


class _Provider:
    name, model = "fake", "fake-model"

    def __init__(self, failures: int = 0) -> None:
        self.failures = failures

    async def generate(self, prompt: str) -> Completion:
        if self.failures:
            self.failures -= 1
            raise ProviderError(ErrorKind.SERVER, 503)
        return Completion(text=answer_json(CANARY), usage=Usage(100, 50))


async def _no_sleep(_seconds: float) -> None:
    return None


def _calls(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    records = [json.loads(r.getMessage()) for r in caplog.records if r.name == "app.llm"]
    return [r for r in records if r["event"] == "llm_call"]


@pytest.mark.parametrize(
    ("tokens", "latency_ms", "expected"),
    [(50, 250, 200.0), (1, 3, 333.3), (0, 250, None), (50, 0, None)],
)
def test_tokens_per_second(tokens: int, latency_ms: int, expected: float | None) -> None:
    assert tokens_per_second(tokens, latency_ms) == expected


async def test_call_log_has_latency_and_tokens_per_second_without_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.llm")
    router = LLMRouter([_Provider()], sleep=_no_sleep, clock=_Clock())

    result = await router.complete_json(CANARY, Answer)

    (call,) = _calls(caplog)
    assert (call["latency_ms"], call["output_tokens_per_s"]) == (250, 200.0)
    assert result.latency_ms == 250
    for record in caplog.records:
        assert "CANARY" not in record.getMessage()
        assert "الصبر" not in record.getMessage()


async def test_result_latency_sums_every_attempt(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.llm")
    router = LLMRouter([_Provider(failures=1)], sleep=_no_sleep, clock=_Clock())

    result = await router.complete_json("p", Answer)

    failed, ok = _calls(caplog)
    assert failed["outcome"] == "server" and failed["output_tokens_per_s"] is None
    assert ok["output_tokens_per_s"] == 200.0
    assert result.latency_ms == 500


async def test_failed_result_still_reports_latency() -> None:
    router = LLMRouter([_Provider(failures=5)], sleep=_no_sleep, clock=_Clock())

    result = await router.complete_json("p", Answer)

    assert result.data is None and result.latency_ms == 500
