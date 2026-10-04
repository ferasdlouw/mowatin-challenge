"""Application configuration via environment variables."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Required variables will cause a fast failure at startup if missing.
    """

    # LLM Provider (required in production, optional in dev/test)
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # Fallback LLM
    fallback_provider: str = ""
    fallback_api_key: str = ""
    fallback_model: str = ""

    # Judge LLM (verification)
    judge_provider: str = ""
    judge_api_key: str = ""
    judge_model: str = ""

    # Base URL per slot, used only by the openai_compat provider (D-026): https anywhere,
    # http only for localhost/127.0.0.1. Ignored by gemini and openrouter.
    llm_base_url: str = ""
    fallback_base_url: str = ""
    judge_base_url: str = ""

    # Billing tier of the LLM keys (D-031): "free" logs actual cost 0 for every slot;
    # "paid" logs the list price. Default "paid", so cost is never under-reported.
    llm_billing: Literal["free", "paid"] = "paid"

    # Per-request HTTP timeout for every LLM call (seconds)
    llm_timeout_s: float = Field(default=20.0, gt=0, le=120)

    # Security
    allowed_origins: str = ""
    rate_limit_per_min: int = Field(default=30, ge=1)
    max_text_chars: int = Field(default=4000, ge=1)
    # LLM consumption limits (D-034): segments sent through the pipeline per request (the
    # rest is returned as one null segment in review), routed LLM calls per request, seconds
    # after which a request starts no new LLM call, and routed calls per UTC day per process.
    max_segments: int = Field(default=6, ge=1, le=200)
    llm_call_budget: int = Field(default=28, ge=1, le=1000)
    request_deadline_s: float = Field(default=90.0, gt=0, le=600)
    llm_daily_call_budget: int = Field(default=1000, ge=1)
    # Proxies in front of the app that append to X-Forwarded-For (Render: 1).
    # 0 means use the socket address; forged left-hand entries are always ignored.
    trusted_proxy_hops: int = Field(default=0, ge=0, le=3)

    # Environment
    env: str = Field(default="development")

    # Google Translate (optional, for eval baseline)
    gt_api_key: str = ""

    @field_validator("llm_billing", mode="before")
    @classmethod
    def _normalize_billing(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("env")
    @classmethod
    def _normalize_env(cls, value: str) -> str:
        """``ENV=Production`` must hide the docs just like ``production``."""
        return value.strip().lower()

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    """Create and return validated settings.

    Raises ``ValidationError`` immediately if required values are
    missing or invalid — this is the "fail fast" behaviour.
    """
    return Settings()  # type: ignore[call-arg]
