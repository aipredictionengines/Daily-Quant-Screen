from pathlib import Path

from dqs.review import review_candidate
from dqs.storage import write_immutable


def test_candidate_review_passes_clean_lifecycle(tmp_path: Path):
    base = tmp_path / "artifacts" / "candidates" / "2026-10-09" / "BTC"

    forecast = {
        "run_mode": "CANDIDATE",
        "counts_toward_paper_20": False,
        "locked_at": "2026-10-09T06:15:00+03:00",
        "decision": "FORECAST",
        "rules": {
            "range_resolution_reference": "CLOSE_AT",
            "verified_market_rules": {"status": "PASS"},
        },
        "polymarket_structure": {
            "ranges": [
                {"lower": None, "upper": 80000.0},
                {"lower": 80000.0, "upper": 82000.0},
                {"lower": 82000.0, "upper": None},
            ]
        },
    }
    fh = write_immutable(base / "forecast.json", forecast)

    benchmark = {
        "run_mode": "CANDIDATE",
        "forecast_sha256": fh,
        "captured_at": "2026-10-09T06:15:01+03:00",
        "ranges": [
            {"lower": None, "upper": 80000.0, "polymarket_midpoint": 0.1},
            {"lower": 80000.0, "upper": 82000.0, "polymarket_midpoint": 0.7},
            {"lower": 82000.0, "upper": None, "polymarket_midpoint": 0.2},
        ],
    }
    write_immutable(base / "benchmark.json", benchmark)

    resolution = {
        "run_mode": "CANDIDATE",
        "candle_reference": "CLOSE_AT",
        "open_time_ms": 1000,
        "close_time_ms": 60999,
        "close": 81000.0,
    }
    write_immutable(base / "resolution.json", resolution)

    score = {
        "run_mode": "CANDIDATE",
        "counts_toward_paper_20": False,
        "forecast_sha256": fh,
        "actual_close": 81000.0,
        "actual_bracket": {"lower": 80000.0, "upper": 82000.0},
        "exact_primary": True,
        "top2": True,
        "brier_discovered_brackets": 0.1,
    }
    write_immutable(base / "score.json", score)

    result = review_candidate(tmp_path, "2026-10-09")
    assert result["passed"] is True
    assert result["state"] == "READY_FOR_PAPER"
