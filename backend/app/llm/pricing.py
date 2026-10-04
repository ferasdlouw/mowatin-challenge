"""Cost per call, for the operational-realism report (decisions D-012, D-031).

Two figures per call:
- **list cost**: what the call would cost at the provider's public paid list price
  (USD per 1M tokens, input / output), i.e. the cost at scale;
- **actual cost**: what is billed today: 0 for an OpenRouter ``:free`` model and for
  every slot when ``LLM_BILLING=free`` (Google AI Studio free tier), else the list cost.

Sources, checked 2026-10-03:
- Google: https://ai.google.dev/gemini-api/docs/pricing (paid tier, standard, text,
  prompts up to 200k tokens).
- OpenRouter: https://openrouter.ai/api/v1/models (``pricing.prompt`` / ``pricing.completion``
  per token, the price list behind https://openrouter.ai/models).
"""

from __future__ import annotations

from app.llm.base import Usage

FREE_SUFFIX = ":free"

# Exact model ids only: a prefix match priced e.g. "mistralai/mistral-large-2512"
# (0.50 / 1.50) at the "mistralai/mistral-large" row (2.00 / 6.00). Unknown ids are
# never guessed: they cost $0 and the log says price_unknown (D-026).
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    # Google, verified 2026-10-03 (Google page).
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    # The page marks this price "through Dec 31, 2026"; higher from Jan 1, 2027.
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-2.5-pro": (1.25, 10.00),
    # unverified 2026-10-03: no longer listed on the Google page (model retired).
    "gemini-2.0-flash": (0.10, 0.40),
    # OpenRouter, verified 2026-10-03 (models API).
    "mistralai/mistral-large": (2.00, 6.00),
    # Paid variant of the free fallback: the list price used for "cost at scale".
    "qwen/qwen3.8-27b": (0.42, 3.00),
    "qwen/qwen3.8-27b:free": (0.0, 0.0),
}


def price_for(model: str) -> tuple[float, float] | None:
    """Table price for this exact model id (a ``:free`` id has its own 0 row)."""
    return PRICES_PER_MTOK.get(model)


def list_price_for(model: str) -> tuple[float, float] | None:
    """Paid list price: a ``:free`` id is priced as its paid variant."""
    return price_for(model.removesuffix(FREE_SUFFIX))


def estimate_cost(model: str, usage: Usage) -> float | None:
    """USD cost of one call at paid list price, or ``None`` when the model is not in the table."""
    price = list_price_for(model)
    if price is None:
        return None
    input_price, output_price = price
    return (usage.prompt_tokens * input_price + usage.output_tokens * output_price) / 1_000_000


def actual_cost(model: str, usage: Usage, free_tier: bool) -> float | None:
    """USD billed today: 0 on a free tier or a ``:free`` model, else the list cost."""
    if free_tier or model.endswith(FREE_SUFFIX):
        return 0.0
    return estimate_cost(model, usage)
