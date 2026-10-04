"""Fill eval/results/summary.json (mean ± sd over runs) from run_eval's metrics.json.

    python scripts/build_summary.py                      # official: metrics from --split test
    python scripts/build_summary.py --allow-dev --out /tmp/summary.json   # dry run on dev numbers

Reads only metrics.json, never a test set. Fills ``metrics[].values`` and ``errors_per_100``
per eval/results/SCHEMA.md and leaves ``status`` untouched ("pending" until the evaluation owner
marks it final). Metrics the runner cannot measure (meaning, clarity, ruling) stay empty.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, stdev
from typing import Any

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "eval" / "results"
# summary.json metric id -> metrics.json key
METRIC_SOURCES = {
    "term_accuracy": "term_accuracy",
    "scripture_integrity": "scripture_integrity",
    "safe_referral": "referral_recall",
}


def mean_sd(values: list[float | None]) -> dict[str, float] | None:
    """Mean and sample sd over runs (sd 0 for a single run); None when no run had cases."""
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    sd = stdev(nums) if len(nums) > 1 else 0.0
    return {"mean": round(mean(nums), 2), "sd": round(sd, 2)}


def fill_summary(summary: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``summary`` with the measured values written in."""
    out = json.loads(json.dumps(summary))
    systems: dict[str, list[dict[str, Any]]] = metrics["systems"]
    # Clear every automatic value first so a system absent from this run (gt without a key)
    # cannot keep numbers from an older run under the new date.
    out["errors_per_100"] = {s["id"]: {} for s in out["systems"]}
    for metric in out["metrics"]:
        key = METRIC_SOURCES.get(metric["id"])
        if key is None:
            continue
        metric["values"] = {}
        for system, runs in systems.items():
            value = mean_sd([r[key] for r in runs])
            if value is not None:
                metric["values"][system] = value
    for system, runs in systems.items():
        categories = runs[0]["errors_per_100"]
        out["errors_per_100"][system] = {
            cat: mean_sd([r["errors_per_100"][cat] for r in runs]) for cat in categories
        }
    out["generated_at"] = metrics["generated_at"][:10]
    out["runs"] = metrics["runs"]
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--metrics", type=Path, default=RESULTS / "runs" / "metrics.json")
    p.add_argument("--summary", type=Path, default=RESULTS / "summary.json")
    p.add_argument("--out", type=Path, help="defaults to --summary (in place)")
    p.add_argument("--allow-dev", action="store_true", help="accept metrics from --split dev")
    args = p.parse_args(argv)

    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    if metrics["split"] != "test" and not args.allow_dev:
        raise SystemExit(
            f"metrics.json comes from --split {metrics['split']}; summary.json is for the frozen "
            "test set. Pass --allow-dev (with --out elsewhere) for a dry run."
        )
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    out = args.out or args.summary
    out.write_text(
        json.dumps(fill_summary(summary, metrics), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"summary written -> {out} (status: {summary['status']})")


if __name__ == "__main__":
    main()
