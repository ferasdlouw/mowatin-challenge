"""Run the evaluation: every test case through each system, N times, then score it.

    python scripts/run_eval.py --split dev --runs 1
    python scripts/run_eval.py --split test --i-confirm-frozen --runs 3   # official, frozen set only

Systems: ``raw`` and ``localize`` through POST /v1/translate (in-process by default, or
``--api-url`` for a running server), plus ``gt`` (Google Translate) only when GT_API_KEY is set.
Writes ``{out}/{gt|raw|mowatten}_run{n}.jsonl`` (rows ``{id, target, output, segments}``,
readable by ``scripts/split_testset.py blind``) and ``{out}/metrics.json`` for build_summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

import httpx

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_metrics import load_approved, load_glossary, score_run  # noqa: E402


@dataclass(frozen=True)
class SystemIds:
    """One system under three names. A mapping, not a rename: each tool keeps its own ids."""

    file_id: str  # scripts/split_testset.py (run file names)
    summary_id: str  # eval/results/summary.json
    api_mode: str | None  # POST /v1/translate mode; None = not our API


SYSTEMS: dict[str, SystemIds] = {
    "gt": SystemIds("gt", "mt", None),
    "raw": SystemIds("raw", "llm", "raw"),
    "localize": SystemIds("mowatten", "mowatin", "localize"),
}
GT_URL = "https://translation.googleapis.com/language/translate/v2"
METRIC_KEYS = (
    "term_accuracy",
    "scripture_integrity",
    "referral_recall",
    "referral_precision",
    "over_referral",
)

Translate = Callable[[str, str], tuple[str, list[dict[str, Any]]]]
Post = Callable[[dict[str, Any]], httpx.Response]


class FrozenSplitError(SystemExit):
    """Raised before any file access when the frozen test split is requested without consent."""


# ── test set ─────────────────────────────────────────────────────────


def resolve_split(split: str, confirmed: bool, testset_dir: Path) -> Path:
    """Path to the split file. The test split needs explicit consent and a matching checksum."""
    if split == "dev":
        return testset_dir / "dev.jsonl"
    if not confirmed:
        raise FrozenSplitError(
            "Refusing --split test: it is the frozen test set. Re-run with --i-confirm-frozen "
            "only for the official runs."
        )
    path = testset_dir / "test.jsonl"
    expected = (testset_dir / "test.sha256").read_text(encoding="utf-8").split()[0]
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise FrozenSplitError(
            "test.jsonl does not match test.sha256; the frozen set was changed."
        )
    return path


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ── systems ──────────────────────────────────────────────────────────


def available_systems(gt_api_key: str) -> list[str]:
    """``gt`` runs only with a key; the two API systems always run."""
    return (["gt"] if gt_api_key else []) + ["raw", "localize"]


def api_translator(post: Post, mode: str, audience: str) -> Translate:
    """Translate through our API with the ARCHITECTURE.md §4 request."""

    def translate(text: str, target: str) -> tuple[str, list[dict[str, Any]]]:
        resp = post({"text": text, "target_lang": target, "audience": audience, "mode": mode})
        resp.raise_for_status()
        segments = resp.json()["segments"]
        output = " ".join(s["output"] for s in segments if s.get("output"))
        return output, segments

    return translate


def throttled(post: Post, delay_s: float, sleep: Callable[[float], None] = time.sleep) -> Post:
    """Waits ``delay_s`` before every API request after the first (free-tier per-minute limits)."""
    if delay_s <= 0:
        return post
    calls = 0

    def send(body: dict[str, Any]) -> httpx.Response:
        nonlocal calls
        if calls:
            sleep(delay_s)
        calls += 1
        return post(body)

    return send


def gt_translator(client: httpx.Client, api_key: str) -> Translate:
    """Google Translate v2. The key travels in a header so it never appears in a URL or log."""

    def translate(text: str, target: str) -> tuple[str, list[dict[str, Any]]]:
        resp = client.post(
            GT_URL,
            headers={"X-Goog-Api-Key": api_key},
            json={"q": text, "source": "ar", "target": target, "format": "text"},
        )
        resp.raise_for_status()
        return resp.json()["data"]["translations"][0]["translatedText"], []

    return translate


# ── running ──────────────────────────────────────────────────────────


def run_system(
    cases: list[dict[str, Any]], translate: Translate
) -> tuple[list[dict[str, Any]], int]:
    """One pass over every unit. A failed call becomes an empty answer (scored as wrong)."""
    rows, failures = [], 0
    for case in cases:
        for target in case["targets"]:
            try:
                output, segments = translate(case["text_ar"], target)
            except (httpx.HTTPError, KeyError, ValueError):
                output, segments, failures = "", [], failures + 1
            rows.append(
                {"id": case["id"], "target": target, "output": output, "segments": segments}
            )
    return rows, failures


def write_rows(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def evaluate(
    cases: list[dict[str, Any]],
    translators: dict[str, Translate],
    runs: int,
    out_dir: Path,
    data_dir: Path,
) -> dict[str, list[dict[str, Any]]]:
    """Run every system ``runs`` times, write run files, return metrics per summary id."""
    glossary = load_glossary(data_dir / "glossary")
    approved = load_approved(data_dir / "quran" / "translations")
    scores: dict[str, list[dict[str, Any]]] = {}
    for n in range(1, runs + 1):
        for name, translate in translators.items():
            ids = SYSTEMS[name]
            rows, failures = run_system(cases, translate)
            write_rows(rows, out_dir / f"{ids.file_id}_run{n}.jsonl")
            scores.setdefault(ids.summary_id, []).append(
                score_run(cases, rows, glossary, approved)
            )
            print(f"run {n} {name:9s} units={len(rows)} failed_calls={failures}")
    return scores


def format_table(scores: dict[str, list[dict[str, Any]]]) -> str:
    """Mean over runs per system; n/a where a metric has no applicable cases."""

    def cell(values: list[float | None]) -> str:
        nums = [v for v in values if v is not None]
        return f"{mean(nums):6.1f}%" if nums else "    n/a"

    systems = list(scores)
    lines = [f"{'metric':22s}" + "".join(f"{s:>12s}" for s in systems)]
    for key in METRIC_KEYS:
        lines.append(
            f"{key:22s}" + "".join(f"{cell([r[key] for r in scores[s]]):>12s}" for s in systems)
        )
    for cat in next(iter(scores.values()))[0]["errors_per_100"]:
        label = f"errors/100 {cat}"
        vals = [f"{mean(r['errors_per_100'][cat] for r in scores[s]):7.1f}" for s in systems]
        lines.append(f"{label:22s}" + "".join(f"{v:>12s}" for v in vals))
    return "\n".join(lines)


# ── wiring (I/O edge) ────────────────────────────────────────────────

IN_PROCESS_RATE_LIMIT = 1_000_000  # per minute; far above any split size


def _in_process_post() -> tuple[Post, Callable[[], None]]:
    sys.path.insert(0, str(REPO / "backend"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    # Every case comes from one client address; the per-IP limit guards the public service,
    # so here it would only turn units into failed calls (429) after the first few.
    settings = get_settings().model_copy(update={"rate_limit_per_min": IN_PROCESS_RATE_LIMIT})
    # A server crash must score as one failed unit (HTTP 500), not abort the whole run.
    client = TestClient(create_app(settings=settings), raise_server_exceptions=False)
    client.__enter__()  # runs startup (glossary load)
    return (lambda body: client.post("/v1/translate", json=body)), lambda: client.__exit__(
        None, None, None
    )


def _gt_key() -> str:
    sys.path.insert(0, str(REPO / "backend"))
    from app.config import get_settings

    return get_settings().gt_api_key


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--split", choices=("dev", "test"), default="dev")
    p.add_argument("--i-confirm-frozen", action="store_true", help="required for --split test")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--audience", default="general_non_muslim")
    p.add_argument("--api-url", help="call a running server instead of the in-process app")
    p.add_argument("--out", type=Path, default=REPO / "eval" / "results" / "runs")
    p.add_argument("--data-dir", type=Path, default=REPO / "data")
    p.add_argument(
        "--delay", type=float, default=0.0, help="seconds between API requests (free-tier limits)"
    )
    args = p.parse_args(argv)
    if args.runs < 1:
        p.error("--runs must be at least 1")
    if args.delay < 0:
        p.error("--delay must be 0 or more")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    cases = load_cases(resolve_split(args.split, args.i_confirm_frozen, args.data_dir / "testset"))
    http = httpx.Client(timeout=60)
    if args.api_url:
        post: Post = lambda body: http.post(f"{args.api_url.rstrip('/')}/v1/translate", json=body)  # noqa: E731
        close = http.close
    else:
        post, close = _in_process_post()
    post = throttled(post, args.delay)
    gt_key = _gt_key()
    translators = {
        name: gt_translator(http, gt_key)
        if name == "gt"
        else api_translator(post, SYSTEMS[name].api_mode or name, args.audience)
        for name in available_systems(gt_key)
    }
    try:
        scores = evaluate(cases, translators, args.runs, args.out, args.data_dir)
    finally:
        close()
        http.close()
    metrics = {
        "split": args.split,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "runs": args.runs,
        "cases": len(cases),
        "systems": scores,
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\nsplit={args.split} cases={len(cases)} runs={args.runs}\n{format_table(scores)}")
    print(f"\nrun files + metrics.json -> {args.out}")


if __name__ == "__main__":
    main()
