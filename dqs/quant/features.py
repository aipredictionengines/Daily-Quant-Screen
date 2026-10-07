from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, asdict
from typing import Any

from dqs.models import Candle


@dataclass
class FeatureSet:
    current_price: float
    return_24h: float
    realized_vol_24h: float
    realized_vol_7d: float
    vol_ratio: float
    atr_24h_pct: float
    volume_ratio_24h_vs_prev: float
    regime: str
    data_points: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stdev(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def calculate_features(candles: list[Candle], periods_per_day: int = 96) -> FeatureSet:
    if len(candles) < periods_per_day * 7:
        raise ValueError("Need at least 7 days of 15m candles")

    closes = [c.close for c in candles]
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
    recent_24 = returns[-periods_per_day:]
    recent_7d = returns[-periods_per_day * 7:]
    price_now = closes[-1]
    price_24h = closes[-1 - periods_per_day]
    return_24h = price_now / price_24h - 1.0

    rv24 = _stdev(recent_24) * math.sqrt(periods_per_day)
    rv7 = _stdev(recent_7d) * math.sqrt(periods_per_day)
    vol_ratio = rv24 / rv7 if rv7 > 0 else 1.0

    tr = []
    for i in range(max(1, len(candles) - periods_per_day), len(candles)):
        prev_close = candles[i - 1].close
        c = candles[i]
        tr.append(max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close)))
    atr_pct = (sum(tr) / len(tr)) / price_now if tr else 0.0

    recent_vol = sum(c.volume for c in candles[-periods_per_day:])
    prev_vol = sum(c.volume for c in candles[-periods_per_day * 2:-periods_per_day])
    volume_ratio = recent_vol / prev_vol if prev_vol > 0 else 1.0

    directional_score = abs(return_24h) / max(rv24, 1e-9)
    if vol_ratio >= 1.35:
        vol_label = "HIGH_VOL"
    elif vol_ratio <= 0.75:
        vol_label = "LOW_VOL"
    else:
        vol_label = "MED_VOL"

    if directional_score >= 0.9:
        direction = "TREND_UP" if return_24h > 0 else "TREND_DOWN"
    else:
        direction = "SIDEWAYS"
    regime = f"{direction}_{vol_label}"

    return FeatureSet(
        current_price=price_now,
        return_24h=return_24h,
        realized_vol_24h=rv24,
        realized_vol_7d=rv7,
        vol_ratio=vol_ratio,
        atr_24h_pct=atr_pct,
        volume_ratio_24h_vs_prev=volume_ratio,
        regime=regime,
        data_points=len(candles),
    )
