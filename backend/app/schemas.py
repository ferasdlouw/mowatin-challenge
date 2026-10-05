"""Request / response schemas — mirrors docs/ARCHITECTURE.md §4."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Request ──────────────────────────────────────────────────────────

TargetLang = Literal["en", "fr"]
Audience = Literal["general_non_muslim", "new_muslim", "youth", "academic"]
Mode = Literal["localize", "raw", "compare"]
SegmentType = Literal["quran", "hadith", "term_heavy", "general", "fatwa_like"]
Level = Literal["A", "B", "C", "D"]
Severity = Literal["info", "warn", "block"]


class TranslateRequest(BaseModel):
    """POST /v1/translate request body (ARCHITECTURE.md §4)."""

    text: str = Field(..., min_length=1, max_length=4000)
    target_lang: TargetLang = "en"
    audience: Audience = "general_non_muslim"
    mode: Mode = "localize"

    model_config = {"extra": "forbid"}


# ── Response ─────────────────────────────────────────────────────────


class SourceRef(BaseModel):
    """A source reference (Quran verse, hadith, glossary term)."""

    kind: Literal["quran", "hadith", "glossary"]
    ref: str = ""
    edition: str | None = None
    grade: str | None = None


class LockedTerm(BaseModel):
    """A glossary term locked to its approved rendering in ``output``."""

    ar: str = ""
    out: str = ""
    glossary_id: str = ""


class Flag(BaseModel):
    """Internal notice raised by a pipeline stage; mapped to ``SegmentFlag`` for the client."""

    type: Severity = "info"
    key: str = ""
    msg: str = ""
    detail: str = ""


class SegmentFlag(BaseModel):
    """A flag as the client sees it: severity plus Arabic text."""

    severity: Severity = "info"
    text: str = ""


class Baseline(BaseModel):
    """Raw-mode baseline for compare responses."""

    output: str = ""
    wrong: list[str] = Field(default_factory=list)
    why: str = ""


class Segment(BaseModel):
    """One segment of the pipeline output."""

    id: int
    source: str = ""
    output: str | None = None
    type: SegmentType = "general"
    level: Level = "A"
    locked_terms: list[LockedTerm] = Field(default_factory=list)
    marks: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    flags: list[SegmentFlag] = Field(default_factory=list)
    baseline: Baseline | None = None
    # The verifier's Arabic back-translation of ``output`` (null when there is none, D-049).
    back_translation: str | None = None


class Summary(BaseModel):
    """Response-level counts the client shows above the segments."""

    segments: int = 0
    flagged: int = 0
    avg_confidence: float = 0.0


class TranslateResponse(BaseModel):
    """POST /v1/translate success response (ARCHITECTURE.md §4)."""

    segments: list[Segment] = Field(default_factory=list)
    summary: Summary = Field(default_factory=Summary)
    review_queue: list[int] = Field(default_factory=list)
    disclosure: str = ""


# ── Glossary ─────────────────────────────────────────────────────────


class GlossaryResult(BaseModel):
    """One glossary search result."""

    id: str
    ar: str = ""
    en: str = ""
    fr: str = ""
    strategy: Literal["keep_and_gloss", "translate", "context"] = "translate"


class GlossaryResponse(BaseModel):
    """GET /v1/glossary response."""

    results: list[GlossaryResult] = Field(default_factory=list)


# ── Health ───────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str = "ok"
    glossary_terms: int = 0
    quran_verses: int = 0
    hadith_entries: int = 0
    version: str = "0.0.0"


# ── Error ────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """Error response shape."""

    error: bool = True
    message: str = ""
    code: Literal["VALIDATION_ERROR", "RATE_LIMITED", "TEXT_TOO_LONG", "INTERNAL_ERROR"] = (
        "INTERNAL_ERROR"
    )
