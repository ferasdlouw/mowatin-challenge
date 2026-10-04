"""Phase SEC Stage C: rules that must keep holding as the code changes.

Each test fails CI when a future change quietly breaks a security rule. When one fails, fix
the change, not the test; see docs/security/SECURE_CHANGE_CHECKLIST.md.
"""

from __future__ import annotations

import ast
import asyncio
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

import app.pipeline.verifier as verifier_module
from app.llm.base import LLMResult
from app.pipeline import cache, orchestrator
from app.pipeline.budget import DailyBreaker, RequestLimits
from app.schemas import TranslateRequest

BACKEND = Path(__file__).resolve().parents[2]
APP = BACKEND / "app"
REPO = BACKEND.parent
PROMPTS = APP / "prompts"


def _modules() -> list[tuple[Path, ast.Module]]:
    return [(p, ast.parse(p.read_text(encoding="utf-8"))) for p in sorted(APP.rglob("*.py"))]


# ── API surface ──────────────────────────────────────────────────────


def test_every_v1_route_is_rate_limited(make_client):
    app_routes = make_client().app.routes
    routes = [r for r in app_routes if isinstance(r, APIRoute) and r.path.startswith("/v1")]
    assert routes
    for route in routes:
        client = make_client(rate_limit_per_min=1)  # a fresh limiter per route
        method = sorted(route.methods)[0]
        body = {"json": {"text": "x"}} if method == "POST" else {}
        client.request(method, route.path, **body)
        second = client.request(method, route.path, **body)
        assert second.status_code == 429, route.path


def test_every_request_body_model_forbids_extra_fields(make_client):
    client = make_client()
    bodies = [
        param.field_info.annotation
        for route in client.app.routes
        if isinstance(route, APIRoute)
        for param in route.dependant.body_params
    ]
    assert TranslateRequest in bodies
    for model in bodies:
        assert issubclass(model, BaseModel)
        assert model.model_config.get("extra") == "forbid", model.__name__


# ── Prompts ──────────────────────────────────────────────────────────

_DATA_FIELDS = {"text", "output"}


def test_untrusted_prompt_fields_pass_the_tag_neutraliser():
    """Every ``.format(...)`` / ``_prompt(...)`` call fills ``text``/``output`` via ``neutralize_tags``."""
    checked = 0
    for path, tree in _modules():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_format = isinstance(func, ast.Attribute) and func.attr == "format"
            is_prompt = isinstance(func, ast.Name) and func.id == "_prompt"
            if not (is_format or is_prompt):
                continue
            for kw in node.keywords:
                if kw.arg in _DATA_FIELDS:
                    checked += 1
                    value = kw.value
                    assert (
                        isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Name)
                        and value.func.id == "neutralize_tags"
                    ), f"{path.name}:{node.lineno} fills {kw.arg!r} without neutralize_tags"
    assert checked >= 5


def _live_prompt_files() -> set[str]:
    from app.pipeline import localizer, verifier

    return {
        localizer.LOCALIZE_PROMPT,
        localizer.RAW_PROMPT,
        verifier.BACKTRANSLATE_PROMPT,
        verifier.JUDGE_PROMPT,
    }


@pytest.mark.parametrize("name", sorted(_live_prompt_files()))
def test_live_prompts_restate_the_rule_after_the_data_block(name):
    text = (PROMPTS / name).read_text(encoding="utf-8")
    last_close = max(text.rfind(f"</{tag}>") for tag in ("user_text", "original", "translation"))
    assert last_close > 0, name
    assert "data only" in text[last_close:], name


# ── LLM calls ────────────────────────────────────────────────────────


class _Counting:
    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        self.calls += 1
        fields = {name: (1.0 if name == "score" else "x") for name in schema.model_fields}
        return LLMResult(data=schema(**fields), provider="f", model="f")


# One sentence per pipeline path: term, general, sourced/unsourced hadith, verse, fatwa.
EVERY_PATH = (
    "التوحيد أساس الإسلام. الصبر جميل. قال رسول الله ﷺ: «إنما الأعمال بالنيات». "
    "﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾. هل يجوز لي الجمع بين الصلاتين؟"
)


@pytest.mark.parametrize("mode", ["localize", "compare", "raw"])
def test_every_llm_path_is_inside_the_request_budget(mode, monkeypatch):
    cache.clear()
    judge = _Counting()
    monkeypatch.setattr(verifier_module, "_judge_router", lambda _router: judge)
    router = _Counting()
    limits = RequestLimits(max_segments=50, call_budget=3, daily=DailyBreaker(10_000))
    req = TranslateRequest(text=EVERY_PATH, mode=mode)
    asyncio.run(orchestrator.translate(req, router, limits))
    assert router.calls + judge.calls <= 3


def test_llm_routers_are_built_only_in_known_places():
    """A new ``LLMRouter(...)`` outside these files would bypass the per-request budget."""
    # smoke.py is the operator's CLI (python -m app.llm.smoke); no request reaches it.
    allowed = {"factory.py", "verifier.py", "smoke.py"}
    for path, tree in _modules():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "LLMRouter"
            ):
                assert path.name in allowed, f"{path.name}:{node.lineno} builds an LLMRouter"


# ── Logs ─────────────────────────────────────────────────────────────

_FORBIDDEN_LOG_NAMES = {"text", "prompt", "source", "output", "question", "q", "body"}
_LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical", "log"}
_SAFE_WRAPPERS = {"fingerprint", "_fingerprint", "len"}


def _is_log_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "_log"
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _LOG_METHODS
        and (isinstance(func.value, ast.Name) and func.value.id.endswith("logger"))
    )


def _unsafe_names(node: ast.AST) -> list[str]:
    """Names/attributes in ``node`` that are not inside fingerprint()/len()."""
    found: list[str] = []

    def visit(n: ast.AST) -> None:
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in _SAFE_WRAPPERS
        ):
            return
        if isinstance(n, ast.Name) and n.id in _FORBIDDEN_LOG_NAMES:
            found.append(n.id)
        if isinstance(n, ast.Attribute) and n.attr in _FORBIDDEN_LOG_NAMES:
            found.append(n.attr)
        for child in ast.iter_child_nodes(n):
            visit(child)

    visit(node)
    return found


def test_no_log_line_carries_user_text_or_llm_output():
    """In every function that logs, log arguments and the dicts built for them hold no text."""
    for path, tree in _modules():
        for func in ast.walk(tree):
            if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            log_calls = [n for n in ast.walk(func) if _is_log_call(n)]
            if not log_calls:
                continue
            suspects = [arg for call in log_calls for arg in [*call.args, *call.keywords]]
            suspects += [n for n in ast.walk(func) if isinstance(n, ast.Dict)]
            for node in suspects:
                bad = _unsafe_names(node)
                assert not bad, f"{path.name}:{func.name} logs {bad}"


# ── CI ───────────────────────────────────────────────────────────────

CI = REPO / ".github" / "workflows" / "ci.yml"


def test_ci_has_no_ignored_failures():
    text = CI.read_text(encoding="utf-8")
    assert "|| true" not in text
    assert "continue-on-error" not in text


def test_ci_actions_are_pinned_to_full_commit_shas():
    uses = re.findall(r"^\s*-?\s*uses:\s*(\S+)", CI.read_text(encoding="utf-8"), re.MULTILINE)
    assert uses
    for ref in uses:
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", ref), ref


def test_ci_enforces_pipeline_coverage_and_the_glossary_validator():
    text = CI.read_text(encoding="utf-8")
    assert "--cov=app/pipeline" in text
    assert "--cov-fail-under=85" in text
    assert "validate_glossary.py --min-approved 100" in text
