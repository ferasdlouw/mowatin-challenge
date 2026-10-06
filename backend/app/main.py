"""Application factory and route wiring."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Query, Request

from app.config import Settings, get_settings
from app.errors import TextTooLongError, register_error_handlers
from app.llm.factory import build_router
from app.pipeline import orchestrator
from app.pipeline.budget import DailyBreaker, RequestLimits
from app.pipeline.classifier import load_fatwa_signals
from app.pipeline.dorar import DorarLookup
from app.pipeline.glossary import get_index
from app.pipeline.hadith import load_items as load_hadith_items
from app.pipeline.normalize import normalize_text
from app.pipeline.quran import approved_verse_count
from app.schemas import (
    GlossaryResponse,
    GlossaryResult,
    HealthResponse,
    TranslateRequest,
    TranslateResponse,
)
from app.security import install_security
from app.security.privacy import fingerprint

logger = logging.getLogger(__name__)

# ── Glossary search ──────────────────────────────────────────────────


def _search_glossary(q: str) -> list[GlossaryResult]:
    """Substring search over ``ar``, ``variants_ar``, ``en.preferred`` and ``fr.preferred``.

    Arabic is compared after ``normalize_text`` (tashkeel, hamza forms); Latin lowercased.
    """
    query = normalize_text(q.strip()).lower()
    if not query:
        return []
    results: list[GlossaryResult] = []
    for tid, term in get_index().entries.items():
        en = term.get("en", {}).get("preferred", "")
        fr = term.get("fr", {}).get("preferred", "")
        haystack = [term.get("ar", ""), *term.get("variants_ar", []), en, fr]
        if any(query in normalize_text(h).lower() for h in haystack):
            results.append(
                GlossaryResult(
                    id=tid,
                    ar=term.get("ar", ""),
                    en=en,
                    fr=fr,
                    strategy=term.get("strategy", "translate"),
                )
            )
    return results


# ── LLM slot status ──────────────────────────────────────────────────

LLM_SLOTS = ("llm", "fallback", "judge")


def llm_slot_status(settings: Settings) -> dict[str, str]:
    """``configured`` / ``unset`` / ``incomplete`` per slot; never a value.

    An unset fallback or judge is allowed: the router fails safe to ``output: null`` +
    review instead of crashing, so the app must start without them.
    """
    status: dict[str, str] = {}
    for slot in LLM_SLOTS:
        fields = [getattr(settings, f"{slot}_{name}") for name in ("provider", "api_key", "model")]
        if all(fields):
            status[slot] = "configured"
        elif any(fields):
            status[slot] = "incomplete"
        else:
            status[slot] = "unset"
    return status


def _configure_logging() -> None:
    """Send ``app.*`` INFO lines to stderr; uvicorn only configures its own loggers."""
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        app_logger.addHandler(handler)


def _log_llm_slots(settings: Settings) -> None:
    status = llm_slot_status(settings)
    level = logging.INFO if all(v == "configured" for v in status.values()) else logging.WARNING
    logger.log(level, json.dumps({"event": "llm_slots", **status}))


def request_limits(settings: Settings) -> RequestLimits:
    """Per-request LLM limits plus one daily breaker for this process (D-034)."""
    return RequestLimits(
        max_segments=settings.max_segments,
        call_budget=settings.llm_call_budget,
        deadline_s=settings.request_deadline_s,
        daily=DailyBreaker(settings.llm_daily_call_budget),
    )


# ── App factory ──────────────────────────────────────────────────────


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    show_docs = settings.env != "production"
    _configure_logging()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        get_index()  # load data/glossary/*.json once, before the first request
        load_fatwa_signals()  # a missing or empty signals file stops the app (fail safe)
        _log_llm_slots(settings)
        async with httpx.AsyncClient() as http:
            _app.state.llm_router = build_router(settings, http)
            # Reviewer references for unsourced hadith (D-067), only when switched on.
            lookup = DorarLookup(http) if settings.hadith_lookup == "dorar" else None
            _app.state.llm_router.hadith_lookup = lookup
            yield

    app = FastAPI(
        title="Muwattin API",
        version="0.0.0",
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url="/openapi.json" if show_docs else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.limits = request_limits(settings)

    register_error_handlers(app)
    install_security(app, settings)

    # ── Routes ───────────────────────────────────────────────────────

    @app.post("/v1/translate", response_model=TranslateResponse)
    async def translate(req: TranslateRequest, request: Request) -> TranslateResponse:
        """Translate Arabic Islamic content with protections (deterministic pipeline, Phase 2d)."""
        if len(req.text) > settings.max_text_chars:
            raise TextTooLongError(settings.max_text_chars)
        entry = {"event": "translate_request", **fingerprint(req.text)}
        entry |= {"target_lang": req.target_lang, "mode": req.mode, "audience": req.audience}
        logger.info(json.dumps(entry))
        return await orchestrator.translate(
            req,
            request.app.state.llm_router,
            request.app.state.limits,
            use_cache=settings.response_cache,
        )

    @app.get("/v1/glossary", response_model=GlossaryResponse)
    async def glossary(q: str = Query(default="", max_length=200)) -> GlossaryResponse:
        """Search the glossary by Arabic text or the EN/FR preferred term."""
        return GlossaryResponse(results=_search_glossary(q))

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Health check — no LLM call, no secrets."""
        return HealthResponse(
            status="ok",
            glossary_terms=len(get_index().entries),
            quran_verses=approved_verse_count(),
            hadith_entries=len(load_hadith_items("hadith")),
            version="0.0.0",
        )

    return app
