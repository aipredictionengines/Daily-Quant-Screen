from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dqs.storage import read_envelope


def _iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def review_candidate(root: Path, market_date: str) -> dict[str, Any]:
    base = root / "artifacts" / "candidates" / market_date / "BTC"
    forecast_env = read_envelope(base / "forecast.json")
    benchmark_env = read_envelope(base / "benchmark.json")
    resolution_env = read_envelope(base / "resolution.json")
    score_env = read_envelope(base / "score.json")

    forecast = forecast_env["payload"]
    benchmark = benchmark_env["payload"]
    resolution = resolution_env["payload"]
    score = score_env["payload"]

    checks: dict[str, bool] = {}

    checks["candidate_mode"] = (
        forecast.get("run_mode") == "CANDIDATE"
        and benchmark.get("run_mode") == "CANDIDATE"
        and resolution.get("run_mode") == "CANDIDATE"
        and score.get("run_mode") == "CANDIDATE"
        and forecast.get("counts_toward_paper_20") is False
        and score.get("counts_toward_paper_20") is False
    )

    checks["forecast_integrity"] = bool(forecast_env.get("sha256"))
    checks["benchmark_links_forecast"] = benchmark.get("forecast_sha256") == forecast_env["sha256"]
    checks["score_links_forecast"] = score.get("forecast_sha256") == forecast_env["sha256"]

    locked_at = _iso(forecast["locked_at"])
    benchmark_at = _iso(benchmark["captured_at"])
    checks["anti_leakage_order"] = benchmark_at >= locked_at

    rules = forecast.get("rules", {}).get("verified_market_rules", {})
    checks["rules_verified"] = rules.get("status") == "PASS"
    checks["close_at_semantics"] = (
        forecast.get("rules", {}).get("range_resolution_reference") == "CLOSE_AT"
        and resolution.get("candle_reference") == "CLOSE_AT"
    )

    ranges = forecast.get("polymarket_structure", {}).get("ranges", [])
    checks["full_range_structure"] = (
        len(ranges) >= 3
        and any(x.get("lower") is None and x.get("upper") is not None for x in ranges)
        and any(x.get("upper") is None and x.get("lower") is not None for x in ranges)
    )

    benchmark_ranges = benchmark.get("ranges", [])
    checks["benchmark_complete"] = (
        len(benchmark_ranges) == len(ranges)
        and len(benchmark_ranges) > 0
        and all(x.get("polymarket_midpoint") is not None for x in benchmark_ranges)
    )

    checks["resolution_timestamp_exact"] = (
        isinstance(resolution.get("open_time_ms"), int)
        and isinstance(resolution.get("close_time_ms"), int)
        and resolution["close_time_ms"] - resolution["open_time_ms"] == 59_999
    )

    checks["score_has_actual_bracket"] = score.get("actual_bracket") is not None
    checks["not_protocol_skip"] = forecast.get("decision") != "SKIP"

    passed = all(checks.values())
    return {
        "schema_version": "dqs.qa.candidate-review.v0.1",
        "candidate_id": "DQS-BTC-CANDIDATE-001",
        "market_date": market_date,
        "reviewed_at": datetime.now(ZoneInfo("Europe/Sofia")).isoformat(),
        "state": "READY_FOR_PAPER" if passed else "CANDIDATE_REVIEW_FAILED",
        "passed": passed,
        "checks": checks,
        "forecast_sha256": forecast_env["sha256"],
        "decision": forecast.get("decision"),
        "exact_primary": score.get("exact_primary"),
        "top2": score.get("top2"),
        "brier_discovered_brackets": score.get("brier_discovered_brackets"),
        "actual_close": score.get("actual_close"),
        "actual_bracket": score.get("actual_bracket"),
        "note": (
            "A passing candidate validates the lifecycle and unlocks PAPER 20. "
            "Candidate accuracy itself is diagnostic and does not count toward PAPER 20."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Review a non-counting Daily Quant Screen candidate")
    parser.add_argument("--root", default=".")
    parser.add_argument("--date", required=True)
    parser.add_argument("--output", default="qa/candidate-gate.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    result = review_candidate(root, args.date)
    target = Path(args.output)
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
