"""Manual smoke call against the real providers, one per configured slot.

Run from ``backend/``:  python -m app.llm.smoke --env-file ../.env

Sends a fixed prompt (never user text) to the primary, fallback and judge slots and
prints provider, model, outcome, tokens, actual cost and cost at list price. Never prints keys or any env value.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.config import Settings
from app.llm.base import ProviderClient
from app.llm.factory import LLMConfigError, build_provider, configured_providers
from app.llm.router import LLMRouter

SMOKE_PROMPT = 'Reply with only this JSON object and nothing else: {"ok": true, "echo": "pong"}'


class SmokeReply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ok: bool
    echo: str


async def _run(settings: Settings) -> bool:
    async with httpx.AsyncClient() as http:
        providers = configured_providers(settings, http)
        if not providers:
            print("No provider configured: set LLM_PROVIDER, LLM_API_KEY, LLM_MODEL.")
            return False
        slots = list(zip(("primary", "fallback"), providers, strict=False))
        judge = build_provider("JUDGE", settings, http)
        if judge is not None:
            slots.append(("judge", judge))
        all_ok = True
        for slot, provider in slots:
            all_ok = await _check(slot, provider) and all_ok
        return all_ok


async def _check(slot: str, provider: ProviderClient) -> bool:
    """One fixed-prompt call; prints the outcome, tokens, actual and list-price cost."""
    result = await LLMRouter([provider]).complete_json(SMOKE_PROMPT, SmokeReply)
    passed = result.ok and result.data is not None and result.data.echo == "pong"
    print(
        f"{slot:<9} {provider.name:<11} {provider.model:<28} "
        f"{'OK' if passed else 'FAIL (' + str(result.error) + ')':<22} "
        f"tokens={result.usage.prompt_tokens}/{result.usage.output_tokens} "
        f"cost=${result.cost_usd:.6f} list=${result.list_cost_usd:.6f}"
    )
    return passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default="../.env", type=Path)
    parser.add_argument("--verbose", action="store_true", help="show llm_call log lines")
    args = parser.parse_args(argv)
    if not args.env_file.is_file():
        print(f"Env file not found: {args.env_file}")
        return 2
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    try:
        settings = Settings(_env_file=args.env_file)  # type: ignore[call-arg]
        return 0 if asyncio.run(_run(settings)) else 1
    except LLMConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    except ValidationError as exc:
        # str(exc) would echo input values, which may be keys: print field names only.
        fields = sorted({".".join(str(part) for part in err["loc"]) for err in exc.errors()})
        print(f"Invalid settings in env file: {', '.join(fields)}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
