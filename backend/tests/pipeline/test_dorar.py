"""D-067: Dorar references for unsourced hadith, for the reviewer only.

The fixture has the shape of a ``dorar_api.json`` answer (numbering «1 -», search-key spans,
a stray ``</span>``, a saying cut short with «. . .», an HTML entity); its content is ours.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx
import respx
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import Settings
from app.llm.base import LLMResult
from app.main import create_app
from app.pipeline import cache, orchestrator
from app.pipeline.budget import DailyBreaker, RequestLimits
from app.pipeline.dorar import API_URL, EDITION, USER_AGENT, DorarLookup, matching, parse
from app.schemas import TranslateRequest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "dorar" / "search_niyyat.json"
QUOTE = "إنما الأعمال بالنيات"
TEXT = f"قال رسول الله ﷺ: «{QUOTE}». والتوحيد أساس الدين."


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_reads_every_field():
    first, second, third = parse(_payload())
    assert first.text == "إنَّما الأعمالُ بالنياتِ"
    assert (first.rawi, first.muhaddith, first.book, first.number, first.grade) == (
        "عمر بن الخطاب",
        "البخاري",
        "صحيح البخاري",
        "1",
        "[صحيح]",
    )
    assert second.text.endswith("ما نَوى &")
    assert second.grade == "خطأ [يعني في إسناده]"
    assert third.number == "6607"


def test_parse_of_anything_else_is_empty():
    assert parse({}) == parse({"ahadith": {"result": 5}}) == parse([]) == []


def test_matching_keeps_the_saying_and_its_longer_or_cut_forms_only():
    entries = parse(_payload())
    assert [e.number for e in matching(QUOTE, entries)] == ["1", "21/270"]
    # Dorar's shorter saying inside a longer quote.
    assert [e.number for e in matching("إنما الأعمال بخواتيمها", entries)] == ["6607"]
    assert matching("إنما الأعمال", entries) == []  # under 3 words: too many sayings


def _lookup_run(mock: respx.MockRouter, *quotes: str) -> list[list[Any]]:
    async def run() -> list[list[Any]]:
        async with httpx.AsyncClient() as http:
            lookup = DorarLookup(http)
            return [await lookup.references(q) for q in quotes]

    return asyncio.run(run())


@respx.mock
def test_lookup_sends_only_the_quote_and_caches_it():
    route = respx.get(API_URL).mock(return_value=httpx.Response(200, json=_payload()))
    first, again = _lookup_run(respx.mock, QUOTE, QUOTE)
    assert route.call_count == 1
    assert dict(route.calls[0].request.url.params) == {"skey": QUOTE}
    assert first == again
    ref = first[0]
    assert (ref.kind, ref.edition) == ("hadith", EDITION)
    assert ref.ref == "صحيح البخاري 1 (البخاري)"
    assert ref.grade == "البخاري: [صحيح]"
    assert first[1].grade == "ابن عبدالبر: خطأ [يعني في إسناده]"


@respx.mock
def test_lookup_failure_gives_no_reference():
    respx.get(API_URL).mock(side_effect=[httpx.Response(500), httpx.ConnectTimeout("t")])
    assert _lookup_run(respx.mock, QUOTE, "من قال لا إله إلا الله") == [[], []]


@respx.mock
def test_lookup_identifies_itself_and_logs_the_refusal_status(caplog):
    """A refusal by Dorar is diagnosable from the log (status code), still without the text."""
    caplog.set_level(logging.INFO, logger="app.pipeline.dorar")
    route = respx.get(API_URL).mock(return_value=httpx.Response(403))
    assert _lookup_run(respx.mock, QUOTE) == [[]]
    assert route.calls[0].request.headers["user-agent"] == USER_AGENT
    (record,) = [json.loads(r.getMessage()) for r in caplog.records]
    assert (record["outcome"], record["status"]) == ("HTTPStatusError", 403)
    assert "الأعمال" not in caplog.text


class NoLLM:
    calls = 0

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        NoLLM.calls += 1
        fields = {name: (1.0 if name == "score" else "x") for name in schema.model_fields}
        return LLMResult(data=schema(**fields), provider="fake", model="fake")


def _translate(text: str, lookup: DorarLookup | None):
    cache.clear()
    router = NoLLM()
    router.hadith_lookup = lookup  # type: ignore[attr-defined]
    req = TranslateRequest(text=text, mode="localize")
    return asyncio.run(
        orchestrator.translate(req, router, RequestLimits(daily=DailyBreaker(1000)))
    )


@respx.mock
def test_unsourced_hadith_stays_untranslated_and_in_review_with_dorar_references():
    route = respx.get(API_URL).mock(return_value=httpx.Response(200, json=_payload()))

    async def run():
        async with httpx.AsyncClient() as http:
            return await asyncio.to_thread(_translate, TEXT, DorarLookup(http))

    response = asyncio.run(run())
    hadith = response.segments[0]
    assert hadith.type == "hadith"
    assert hadith.output is None
    assert 1 in response.review_queue
    assert any(flag.severity == "warn" for flag in hadith.flags)
    assert [(s.edition, s.ref) for s in hadith.sources] == [
        (EDITION, "صحيح البخاري 1 (البخاري)"),
        (EDITION, "التمهيد 21/270 (ابن عبدالبر)"),
    ]
    # Only the quote left the server, not the sentence around it.
    assert [dict(call.request.url.params) for call in route.calls] == [{"skey": QUOTE}]


@respx.mock
def test_fabricated_or_approved_saying_and_switched_off_lookup_send_nothing():
    route = respx.get(API_URL).mock(return_value=httpx.Response(200, json=_payload()))

    async def run():
        async with httpx.AsyncClient() as http:
            lookup = DorarLookup(http)
            fabricated = await asyncio.to_thread(
                _translate, "قال النبي ﷺ: «اطلبوا العلم ولو في الصين»", lookup
            )
            approved = await asyncio.to_thread(_translate, "قال النبي ﷺ: «الدين النصيحة»", lookup)
            off = await asyncio.to_thread(_translate, TEXT, None)
            return fabricated, approved, off

    fabricated, approved, off = asyncio.run(run())
    assert route.call_count == 0
    assert all(
        s.edition != EDITION
        for r in (fabricated, approved, off)
        for seg in r.segments
        for s in seg.sources
    )


def test_lookup_is_off_by_default_and_built_once_when_switched_on():
    off = Settings(_env_file=None, env="test")  # type: ignore[call-arg]
    assert off.hadith_lookup == "off"
    with TestClient(create_app(off)) as client:
        assert client.app.state.llm_router.hadith_lookup is None
    on = Settings(_env_file=None, env="test", hadith_lookup="dorar")  # type: ignore[call-arg]
    with TestClient(create_app(on)) as client:
        assert isinstance(client.app.state.llm_router.hadith_lookup, DorarLookup)
