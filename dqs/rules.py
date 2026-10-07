from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RuleCheck:
    source: str | None
    pair: str | None
    interval: str | None
    metric: str | None
    time_et: str | None
    candle_reference: str | None
    boundary_rule: str | None
    status: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_btc_range_rules(text: str | None) -> RuleCheck:
    if not text:
        return RuleCheck(
            source=None,
            pair=None,
            interval=None,
            metric=None,
            time_et=None,
            candle_reference=None,
            boundary_rule=None,
            status="VERIFY",
            evidence="No rules text was available from the market metadata.",
        )

    compact = " ".join(text.split())
    lower = compact.lower()

    source = "Binance" if "binance" in lower else None
    pair = "BTC/USDT" if "btc/usdt" in lower else None
    interval = "1m" if ("1m" in lower or "1 minute" in lower or "1-minute" in lower) else None
    metric = "Close" if re.search(r'["\']?close["\']?', lower) else None

    time_et = None
    if "12:00" in lower and ("et" in lower or "eastern" in lower or "noon" in lower):
        time_et = "12:00 America/New_York"

    candle_reference = None
    if re.search(r"(closing|close)\s+at\s+12:00", lower):
        candle_reference = "CLOSE_AT"
    elif re.search(r"(opening|open)\s+at\s+12:00", lower):
        candle_reference = "OPEN_AT"

    boundary_rule = None
    if "exactly between two brackets" in lower and "higher range bracket" in lower:
        boundary_rule = "EXACT_BOUNDARY_TO_HIGHER_BRACKET"

    required = [source, pair, interval, metric, time_et, candle_reference, boundary_rule]
    status = "PASS" if all(required) and candle_reference == "CLOSE_AT" else "VERIFY"
    missing = [
        name
        for name, value in [
            ("source", source),
            ("pair", pair),
            ("interval", interval),
            ("metric", metric),
            ("time_et", time_et),
            ("candle_reference", candle_reference),
            ("boundary_rule", boundary_rule),
        ]
        if not value
    ]
    if missing:
        evidence = f"Rules text present but missing/ambiguous: {', '.join(missing)}."
    elif candle_reference != "CLOSE_AT":
        evidence = f"Unexpected candle reference: {candle_reference}."
    else:
        evidence = "Rules signature matched, including candle closing-time semantics."

    return RuleCheck(
        source=source,
        pair=pair,
        interval=interval,
        metric=metric,
        time_et=time_et,
        candle_reference=candle_reference,
        boundary_rule=boundary_rule,
        status=status,
        evidence=evidence,
    )


def first_rules_text(event: dict[str, Any] | None) -> str | None:
    if not event:
        return None

    candidates: list[str] = []
    for key in ("description", "rules", "resolutionSource"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value)

    for market in event.get("markets", []) if isinstance(event.get("markets"), list) else []:
        for key in ("description", "rules", "resolutionSource"):
            value = market.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value)

    if not candidates:
        return None
    return max(candidates, key=len)
