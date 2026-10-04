"""Tests for scripts/build_summary.py (summary.json filling)."""

from __future__ import annotations

import json

import build_summary as b
import pytest

from .conftest import REPO

SUMMARY = REPO / "eval" / "results" / "summary.json"


def _run(term, scripture, recall, quran_err):
    return {
        "term_accuracy": term,
        "scripture_integrity": scripture,
        "referral_recall": recall,
        "referral_precision": None,
        "over_referral": 0.0,
        "errors_per_100": {"quran": quran_err, "hadith": 0.0, "term": 0.0, "referral": 0.0},
    }


def _metrics(split="test"):
    return {
        "split": split,
        "generated_at": "2026-10-10T12:00:00+00:00",
        "runs": 3,
        "systems": {
            "mowatin": [
                _run(90.0, 100.0, 100.0, 0.0),
                _run(92.0, 100.0, 100.0, 0.0),
                _run(94.0, 100.0, None, 0.0),
            ],
            "llm": [_run(40.0, 0.0, 0.0, 30.0)] * 3,
        },
    }


def test_mean_sd():
    assert b.mean_sd([90.0, 92.0, 94.0]) == {"mean": 92.0, "sd": 2.0}
    assert b.mean_sd([50.0]) == {"mean": 50.0, "sd": 0.0}
    assert b.mean_sd([None, None]) is None
    assert b.mean_sd([None, 10.0]) == {"mean": 10.0, "sd": 0.0}


def test_fill_summary_writes_values_and_keeps_pending():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    filled = b.fill_summary(summary, _metrics())
    by_id = {m["id"]: m for m in filled["metrics"]}
    assert by_id["term_accuracy"]["values"]["mowatin"] == {"mean": 92.0, "sd": 2.0}
    assert by_id["safe_referral"]["values"]["llm"] == {"mean": 0.0, "sd": 0.0}
    assert by_id["meaning"]["values"] == {}  # human-rated, untouched
    assert filled["errors_per_100"]["llm"]["quran"] == {"mean": 30.0, "sd": 0.0}
    assert filled["status"] == "pending"
    assert filled["runs"] == 3
    assert filled["generated_at"] == "2026-10-10"
    assert summary["generated_at"] is None  # input not mutated


def test_cli_refuses_dev_metrics(tmp_path):
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps(_metrics("dev")), encoding="utf-8")
    with pytest.raises(SystemExit, match="--allow-dev"):
        b.main(
            [
                "--metrics",
                str(metrics),
                "--summary",
                str(SUMMARY),
                "--out",
                str(tmp_path / "s.json"),
            ]
        )
    assert not (tmp_path / "s.json").exists()


def test_cli_writes_out_without_touching_real_summary(tmp_path):
    before = SUMMARY.read_bytes()
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps(_metrics("dev")), encoding="utf-8")
    out = tmp_path / "summary.json"
    b.main(
        ["--metrics", str(metrics), "--summary", str(SUMMARY), "--out", str(out), "--allow-dev"]
    )
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "pending"
    assert SUMMARY.read_bytes() == before


def test_fill_summary_drops_stale_values_of_absent_system():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in summary["metrics"]}
    by_id["term_accuracy"]["values"]["mt"] = {"mean": 55.0, "sd": 1.0}
    by_id["meaning"]["values"]["mt"] = {"mean": 3.0, "sd": 0.5}  # human-rated: kept
    summary["errors_per_100"]["mt"] = {"term": {"mean": 9.0, "sd": 0.0}}
    filled = b.fill_summary(summary, _metrics())  # no "mt" in this run
    filled_by_id = {m["id"]: m for m in filled["metrics"]}
    assert "mt" not in filled_by_id["term_accuracy"]["values"]
    assert filled_by_id["meaning"]["values"]["mt"] == {"mean": 3.0, "sd": 0.5}
    assert filled["errors_per_100"]["mt"] == {}
