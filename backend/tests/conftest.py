"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.pipeline import cache


@pytest.fixture()
def settings() -> Settings:
    """Test settings with safe defaults. A developer's ``.env`` is not read: its fallback or
    judge key would turn tests into live, slow, flaky LLM calls."""
    return Settings(
        _env_file=None,
        env="test",
        llm_provider="",
        llm_api_key="",
        llm_model="",
    )  # type: ignore[call-arg]


@pytest.fixture()
def app(settings: Settings):
    """FastAPI app configured for testing."""
    return create_app(settings=settings)


@pytest.fixture()
def client(app) -> TestClient:
    """Test client."""

    cache.clear()
    with TestClient(app) as c:
        yield c
