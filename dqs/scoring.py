from __future__ import annotations

from typing import Any


def range_score(forecast_payload: dict[str, Any], actual_close: float) -> dict[str, Any]:
    probs = forecast_payload["forecast"]["range_probabilities"]
    ordered = sorted(probs, key=lambda x: x["probability"], reverse=True)
    actual = None
    for item in probs:
        if item["lower"] <= actual_close < item["upper"]:
            actual = item
            break
    exact = bool(ordered and actual and ordered[0]["lower"] == actual["lower"] and ordered[0]["upper"] == actual["upper"])
    top2 = bool(
        actual
        and any(x["lower"] == actual["lower"] and x["upper"] == actual["upper"] for x in ordered[:2])
    )

    brier = 0.0
    for item in probs:
        y = 1.0 if actual and item["lower"] == actual["lower"] and item["upper"] == actual["upper"] else 0.0
        brier += (item["probability"] - y) ** 2
    brier = brier / len(probs) if probs else None

    return {
        "actual_close": actual_close,
        "actual_bracket": actual,
        "exact_primary": exact,
        "top2": top2,
        "brier_discovered_brackets": brier,
    }
