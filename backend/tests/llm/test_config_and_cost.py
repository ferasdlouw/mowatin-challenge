"""Pricing table, provider factory, and the smoke CLI (mocked; no network)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from app.config import Settings
from app.llm import pricing
from app.llm.base import Usage
from app.llm.factory import (
    LLMConfigError,
    build_provider,
    build_router,
    configured_providers,
)
from app.llm.gemini import GeminiClient
from app.llm.openrouter import OpenRouterClient
from app.llm.pricing import actual_cost, estimate_cost, list_price_for, price_for
from app.llm.router import NOT_CONFIGURED
from app.llm.smoke import main as smoke_main
from tests.llm.conftest import FAKE_KEY, GEMINI_URL, OPENROUTER_URL, Answer

ENV_NAMES = [
    f"{prefix}_{field}"
    for prefix in ("LLM", "FALLBACK", "JUDGE")
    for field in ("PROVIDER", "API_KEY", "MODEL")
] + ["LLM_TIMEOUT_S"]

# ── Pricing ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("model", "price"),
    [
        ("gemini-3.5-flash-lite", (0.30, 2.50)),
        ("gemini-3.1-flash-lite", (0.25, 1.50)),
        ("gemini-3.8-flash", (0.75, 3.75)),
        ("gemini-2.5-pro", (1.25, 10.00)),
        ("gemini-2.0-flash", (0.10, 0.40)),
        ("mistralai/mistral-large", (2.00, 6.00)),
        ("qwen/qwen3.8-27b", (0.42, 3.00)),
        ("qwen/qwen3.8-27b:free", (0.0, 0.0)),
        ("unknown-model", None),
    ],
)
def test_price_lookup_by_exact_id(model: str, price: tuple[float, float] | None) -> None:
    assert price_for(model) == price


@pytest.mark.parametrize(
    "model",
    ["mistralai/mistral-large-2512", "gemini-2.0-flash-lite", "gemini-3.5-flash", "gemini-3.8"],
)
def test_other_variants_are_never_priced_by_prefix(model: str) -> None:
    # mistral-large-2512 lists at 0.50/1.50, not the 2.00/6.00 alias row: never guess.
    assert price_for(model) is None
    assert estimate_cost(model, Usage(10, 10)) is None


def test_free_model_list_price_is_its_paid_variant() -> None:
    assert list_price_for("qwen/qwen3.8-27b:free") == (0.42, 3.00)
    assert list_price_for("gemini-3.5-flash-lite") == (0.30, 2.50)


def test_estimate_cost_arithmetic() -> None:
    cost = estimate_cost("mistralai/mistral-large", Usage(1_000_000, 500_000))

    assert cost == pytest.approx(2.00 + 3.00)


def test_estimate_cost_unknown_model_is_none() -> None:
    assert estimate_cost("unknown", Usage(10, 10)) is None


@pytest.mark.parametrize(
    ("model", "free_tier", "expected"),
    [
        ("gemini-3.5-flash-lite", False, 0.30 + 1.25),
        ("gemini-3.5-flash-lite", True, 0.0),
        ("qwen/qwen3.8-27b:free", False, 0.0),
        ("unknown-model", True, 0.0),
        ("unknown-model", False, None),
    ],
)
def test_actual_cost_is_zero_on_free_tiers_only(
    model: str, free_tier: bool, expected: float | None
) -> None:
    cost = actual_cost(model, Usage(1_000_000, 500_000), free_tier)

    assert cost == (None if expected is None else pytest.approx(expected))


def test_price_table_names_its_sources_and_check_date() -> None:
    source = Path(pricing.__file__).read_text(encoding="utf-8")

    assert "https://ai.google.dev/gemini-api/docs/pricing" in source
    assert "https://openrouter.ai/api/v1/models" in source
    assert "checked 2026-10-03" in source
    assert "unverified 2026-10-03" in source


# ── Factory ──────────────────────────────────────────────────────────


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "test",
        "llm_provider": "gemini",
        "llm_api_key": FAKE_KEY,
        "llm_model": "gemini-2.0-flash",
        "fallback_provider": "openrouter",
        "fallback_api_key": FAKE_KEY,
        "fallback_model": "mistralai/mistral-large",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


async def test_factory_builds_primary_then_fallback(http: httpx.AsyncClient) -> None:
    providers = configured_providers(_settings(llm_timeout_s=7.5), http)

    assert [type(p) for p in providers] == [GeminiClient, OpenRouterClient]
    assert all(p._timeout == 7.5 for p in providers)  # type: ignore[attr-defined]


async def test_factory_provider_name_is_case_insensitive(http: httpx.AsyncClient) -> None:
    providers = configured_providers(_settings(llm_provider=" Gemini "), http)

    assert isinstance(providers[0], GeminiClient)


async def test_factory_skips_unset_fallback(http: httpx.AsyncClient) -> None:
    providers = configured_providers(_settings(fallback_provider=""), http)

    assert [p.name for p in providers] == ["gemini"]


async def test_factory_rejects_unknown_provider(http: httpx.AsyncClient) -> None:
    with pytest.raises(LLMConfigError, match="FALLBACK_PROVIDER must be one of"):
        configured_providers(_settings(fallback_provider="openai"), http)


async def test_factory_rejects_partial_config_without_echoing_values(
    http: httpx.AsyncClient,
) -> None:
    with pytest.raises(LLMConfigError) as info:
        configured_providers(_settings(llm_api_key=""), http)

    assert "LLM_API_KEY" in str(info.value)
    assert "gemini-2.0-flash" not in str(info.value)


def test_billing_defaults_to_paid_and_is_normalized() -> None:
    assert _settings().llm_billing == "paid"
    assert _settings(llm_billing=" Free ").llm_billing == "free"
    with pytest.raises(ValueError, match="llm_billing"):
        _settings(llm_billing="cheap")


@pytest.mark.parametrize(("billing", "free"), [("free", True), ("paid", False)])
async def test_factory_tags_every_slot_with_billing(
    http: httpx.AsyncClient, billing: str, free: bool
) -> None:
    settings = _settings(
        llm_billing=billing,
        judge_provider="gemini",
        judge_api_key=FAKE_KEY,
        judge_model="gemini-3.1-flash-lite",
    )
    providers = [*configured_providers(settings, http), build_provider("JUDGE", settings, http)]

    assert [getattr(p, "free_tier", None) for p in providers] == [free, free, free]


async def test_unconfigured_router_fails_safe(http: httpx.AsyncClient) -> None:
    router = build_router(_settings(llm_provider="", fallback_provider=""), http)

    result = await router.complete_json("p", Answer)

    assert result.data is None and result.error == NOT_CONFIGURED


def test_timeout_setting_validated() -> None:
    with pytest.raises(ValueError, match="llm_timeout_s"):
        _settings(llm_timeout_s=0)


# ── Smoke CLI ────────────────────────────────────────────────────────


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def _write_env(tmp_path: Path, lines: list[str]) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_file


FULL_ENV = [
    "LLM_PROVIDER=gemini",
    f"LLM_API_KEY={FAKE_KEY}",
    "LLM_MODEL=gemini-2.0-flash",
    "FALLBACK_PROVIDER=openrouter",
    f"FALLBACK_API_KEY={FAKE_KEY}",
    "FALLBACK_MODEL=mistralai/mistral-large",
    "JUDGE_PROVIDER=gemini",
    f"JUDGE_API_KEY={FAKE_KEY}",
    "JUDGE_MODEL=gemini-2.0-flash",
]
PONG = '{"ok": true, "echo": "pong"}'


@pytest.mark.usefixtures("clean_env")
def test_smoke_success_calls_all_three_slots_and_never_prints_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_file = _write_env(tmp_path, FULL_ENV)
    with respx.mock(assert_all_mocked=True) as mock:
        gemini = mock.post(GEMINI_URL).mock(
            return_value=httpx.Response(
                200, json={"candidates": [{"content": {"parts": [{"text": PONG}]}}]}
            )
        )
        fallback = mock.post(OPENROUTER_URL).mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": PONG}}]})
        )
        code = smoke_main(["--env-file", str(env_file)])

    out = capsys.readouterr().out
    assert code == 0
    # primary and judge share the mocked Gemini URL
    assert gemini.call_count == 2 and fallback.call_count == 1
    assert "primary" in out and "fallback" in out and "judge" in out and out.count("OK") == 3
    assert out.count("list=$") == 3
    assert FAKE_KEY not in out


@pytest.mark.usefixtures("clean_env")
def test_smoke_reports_failure_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env_file = _write_env(tmp_path, FULL_ENV[:3])
    with respx.mock(assert_all_mocked=True) as mock:
        mock.post(GEMINI_URL).mock(return_value=httpx.Response(401))
        code = smoke_main(["--env-file", str(env_file)])

    assert code == 1
    assert "FAIL (client)" in capsys.readouterr().out


def test_smoke_missing_env_file(tmp_path: Path) -> None:
    assert smoke_main(["--env-file", str(tmp_path / "nope.env")]) == 2


@pytest.mark.usefixtures("clean_env")
def test_smoke_no_provider_configured(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env_file = _write_env(tmp_path, ["ENV=development"])

    assert smoke_main(["--env-file", str(env_file)]) == 1
    assert "No provider configured" in capsys.readouterr().out


@pytest.mark.usefixtures("clean_env")
def test_smoke_config_error_names_variable_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_file = _write_env(tmp_path, ["LLM_PROVIDER=gemini", f"LLM_API_KEY={FAKE_KEY}"])

    assert smoke_main(["--env-file", str(env_file)]) == 2
    out = capsys.readouterr().out
    assert "LLM_MODEL" in out
    assert FAKE_KEY not in out


@pytest.mark.usefixtures("clean_env")
def test_smoke_invalid_settings_never_echo_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_file = _write_env(tmp_path, [*FULL_ENV, "LLM_TIMEOUT_S=not-a-number"])

    assert smoke_main(["--env-file", str(env_file)]) == 2
    out = capsys.readouterr().out
    assert "llm_timeout_s" in out
    assert FAKE_KEY not in out and "not-a-number" not in out
