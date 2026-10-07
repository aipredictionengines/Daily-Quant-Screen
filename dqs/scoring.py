from __future__ import annotations

from typing import Any


def _contains(item: dict[str, Any], price: float) -> bool:
    lower = item.get("lower")
    upper = item.get("upper")
    return (lower is None or price >= lower) and (upper is None or price < upper)


def range_score(forecast_payload: dict[str, Any], actual_close: float) -> dict[str, Any]:
    probs = forecast_payload["forecast"]["range_probabilities"]
    ordered = sorted(probs, key=lambda x: x["probability"], reverse=True)
    actual = next((item for item in probs if _contains(item, actual_close)), None)

    exact = bool(
        ordered
        and actual
        and ordered[0].get("lower") == actual.get("lower")
        and ordered[0].get("upper") == actual.get("upper")
    )
    top2 = bool(
        actual
        and any(
            x.get("lower") == actual.get("lower") and x.get("upper") == actual.get("upper")
            for x in ordered[:2]
        )
    )

    brier = 0.0
    for item in probs:
        y = 1.0 if actual and item.get("lower") == actual.get("lower") and item.get("upper") == actual.get("upper") else 0.0
        brier += (item["probability"] - y) ** 2
    brier = brier / len(probs) if probs else None

    return {
        "actual_close": actual_close,
        "actual_bracket": actual,
        "exact_primary": exact,
        "top2": top2,
        "brier_discovered_brackets": brier,
    }
