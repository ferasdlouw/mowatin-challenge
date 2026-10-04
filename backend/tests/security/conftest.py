"""App factory for security tests: each test builds the settings it needs."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PROD_ORIGIN = "https://mowatin.pages.dev"


@pytest.fixture()
def make_client() -> Iterator[Callable[..., TestClient]]:
    """Build a started TestClient from setting overrides; closes them all at teardown."""
    clients: list[TestClient] = []

    def factory(**overrides: Any) -> TestClient:
        values: dict[str, Any] = {"env": "test", "allowed_origins": PROD_ORIGIN}
        values.update(overrides)
        client = TestClient(create_app(Settings(_env_file=None, **values)))  # type: ignore[call-arg]
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)
