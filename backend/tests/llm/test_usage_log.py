"""Usage/cost accounting is logged per attempt, and never contains user text or keys."""

from __future__ import annotations

import hashlib
import json
import logging

import httpx
import pytest
import respx

from app.llm.router import LLMRouter
from app.security.privacy import keyed_digest
from tests.llm.conftest import (
    FAKE_KEY,
    GEMINI_URL,
    OPENROUTER_URL,
    Answer,
    answer_json,
    gemini_ok,
    openrouter_ok,
)

USER_TEXT = "CANARY-USER-TEXT إن الله مع الصابرين"
MODEL_TEXT = "CANARY-MODEL-OUTPUT"


def _records(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "app.llm"]


def _assert_private(caplog: pytest.LogCaptureFixture) -> None:
    for record in caplog.records:
        message = record.getMessage()
        assert "CANARY" not in message
        assert "الصابرين" not in message
        assert FAKE_KEY not in message


async def test_success_logs_tokens_cost_and_fingerprint_only(
    mock_api: respx.MockRouter, router: LLMRouter, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.llm")
    mock_api.post(GEMINI_URL).mock(return_value=gemini_ok(answer_json(MODEL_TEXT), 100, 20))

    await router.complete_json(USER_TEXT, Answer)

    (record,) = _records(caplog)
    digest = keyed_digest(USER_TEXT)
    # NEW-6: keyed, so the prompt cannot be confirmed by hashing a guess.
    assert digest != hashlib.sha256(USER_TEXT.encode("utf-8")).hexdigest()[:12]
    assert record == {
        "event": "llm_call",
        "provider": "gemini",
        "model": "gemini-2.0-flash",
        "attempt": 1,
        "outcome": "ok",
        "latency_ms": record["latency_ms"],
        "prompt_tokens": 100,
        "output_tokens": 20,
        "output_tokens_per_s": record["output_tokens_per_s"],
        "cost_usd": pytest.approx((100 * 0.10 + 20 * 0.40) / 1_000_000),
        "list_cost_usd": pytest.approx((100 * 0.10 + 20 * 0.40) / 1_000_000),
        "cost_known": True,
        "price_unknown": False,
        "prompt_len": len(USER_TEXT),
        "prompt_sha256": digest,
    }
    assert isinstance(record["latency_ms"], int)
    _assert_private(caplog)


async def test_failover_path_logs_every_attempt_and_the_failover(
    mock_api: respx.MockRouter, router: LLMRouter, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.llm")
    mock_api.post(GEMINI_URL).mock(
        side_effect=[httpx.ReadTimeout("slow"), gemini_ok(f"{{bad {MODEL_TEXT}", 50, 5)]
    )
    mock_api.post(OPENROUTER_URL).mock(return_value=openrouter_ok(answer_json(MODEL_TEXT)))

    await router.complete_json(USER_TEXT, Answer)

    events = [(r["event"], r.get("provider"), r.get("outcome")) for r in _records(caplog)]
    assert events == [
        ("llm_call", "gemini", "timeout"),
        ("llm_call", "gemini", "invalid_response"),
        ("llm_failover", None, None),
        ("llm_call", "openrouter", "ok"),
    ]
    failover = _records(caplog)[2]
    assert failover == {
        "event": "llm_failover",
        "from": "gemini",
        "to": "openrouter",
        "reason": "invalid_response",
    }
    invalid_attempt = _records(caplog)[1]
    assert (invalid_attempt["prompt_tokens"], invalid_attempt["output_tokens"]) == (50, 5)
    _assert_private(caplog)


async def test_total_failure_logs_llm_failed(
    mock_api: respx.MockRouter, router: LLMRouter, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.llm")
    mock_api.post(GEMINI_URL).mock(return_value=httpx.Response(500, text=MODEL_TEXT))
    mock_api.post(OPENROUTER_URL).mock(return_value=httpx.Response(500, text=MODEL_TEXT))

    await router.complete_json(USER_TEXT, Answer)

    last = _records(caplog)[-1]
    assert last["event"] == "llm_failed"
    assert last["error"] == "server"
    assert last["prompt_len"] == len(USER_TEXT)
    _assert_private(caplog)


async def test_unknown_model_cost_is_null_not_guessed(
    mock_api: respx.MockRouter, http: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    from app.llm.gemini import GeminiClient

    caplog.set_level(logging.INFO, logger="app.llm")
    client = GeminiClient(http, FAKE_KEY, "gemini-9-experimental", 5.0)
    url = GEMINI_URL.replace("gemini-2.0-flash", "gemini-9-experimental")
    mock_api.post(url).mock(return_value=gemini_ok(answer_json()))

    result = await LLMRouter([client]).complete_json("p", Answer)

    (record,) = _records(caplog)
    assert record["cost_usd"] is None
    assert record["list_cost_usd"] is None
    assert record["cost_known"] is False
    assert record["price_unknown"] is True
    assert result.cost_usd == 0.0


async def test_free_tier_logs_actual_zero_and_list_price(
    mock_api: respx.MockRouter, http: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    from app.llm.gemini import GeminiClient

    caplog.set_level(logging.INFO, logger="app.llm")
    client = GeminiClient(http, FAKE_KEY, "gemini-2.0-flash", 5.0)
    client.free_tier = True  # type: ignore[attr-defined]
    mock_api.post(GEMINI_URL).mock(return_value=gemini_ok(answer_json(), 100, 20))

    result = await LLMRouter([client]).complete_json("p", Answer)

    (record,) = _records(caplog)
    list_cost = (100 * 0.10 + 20 * 0.40) / 1_000_000
    assert record["cost_usd"] == 0.0
    assert record["list_cost_usd"] == pytest.approx(list_cost)
    assert record["price_unknown"] is False
    assert result.cost_usd == 0.0
    assert result.list_cost_usd == pytest.approx(list_cost)


async def test_free_model_costs_zero_and_lists_its_paid_variant(
    mock_api: respx.MockRouter, http: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    from app.llm.openrouter import OpenRouterClient

    caplog.set_level(logging.INFO, logger="app.llm")
    client = OpenRouterClient(http, FAKE_KEY, "qwen/qwen3.8-27b:free", 5.0)
    mock_api.post(OPENROUTER_URL).mock(return_value=openrouter_ok(answer_json()))

    result = await LLMRouter([client]).complete_json("p", Answer)

    (record,) = _records(caplog)
    assert record["cost_usd"] == 0.0
    assert result.list_cost_usd > 0
    assert record["list_cost_usd"] == pytest.approx(result.list_cost_usd)
