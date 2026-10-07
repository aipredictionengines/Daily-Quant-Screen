from __future__ import annotations

import hashlib
import math
import random
import statistics
from dataclasses import dataclass
from typing import Any

from dqs.models import Candle, HitLevel, RangeBracket
from dqs.quant.features import FeatureSet


@dataclass(frozen=True)
class CandleShape:
    body_log: float
    high_log: float
    low_log: float


def _shape(c: Candle) -> CandleShape:
    if c.open <= 0:
        return CandleShape(0.0, 0.0, 0.0)
    return CandleShape(
        body_log=math.log(c.close / c.open),
        high_log=max(0.0, math.log(c.high / c.open)),
        low_log=min(0.0, math.log(c.low / c.open)),
    )


def deterministic_seed(asset: str, market_date: str, locked_at: str) -> int:
    raw = f"{asset}|{market_date}|{locked_at}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:16], 16)


def simulate(
    candles: list[Candle],
    features: FeatureSet,
    range_steps: int,
    hit_steps: int,
    ranges: list[RangeBracket],
    hit_levels: list[HitLevel],
    simulations: int,
    seed: int,
) -> dict[str, Any]:
    if not candles:
        raise ValueError("No candles")
    shapes = [_shape(c) for c in candles[-3000:]]
    bodies = [x.body_log for x in shapes]
    long_sd = statistics.pstdev(bodies) if len(bodies) > 1 else 0.0
    recent = bodies[-96:] if len(bodies) >= 96 else bodies
    recent_sd = statistics.pstdev(recent) if len(recent) > 1 else long_sd
    scale = recent_sd / long_sd if long_sd > 1e-12 else 1.0
    scale = max(0.55, min(1.85, scale))

    drift = statistics.fmean(recent) if recent else 0.0
    drift_cap = (recent_sd or 1e-6) * 0.20
    drift = max(-drift_cap, min(drift_cap, drift))

    rng = random.Random(seed)
    start = features.current_price
    max_steps = max(range_steps, hit_steps, 1)

    terminal_prices: list[float] = []
    path_highs: list[float] = []
    path_lows: list[float] = []

    for _ in range(simulations):
        price = start
        p_high = start
        p_low = start
        terminal = start
        for step in range(1, max_steps + 1):
            s = rng.choice(shapes)
            body = drift + (s.body_log - drift) * scale
            hi = max(0.0, s.high_log * scale)
            lo = min(0.0, s.low_log * scale)
            step_high = price * math.exp(hi)
            step_low = price * math.exp(lo)
            close = price * math.exp(body)
            p_high = max(p_high, step_high, close)
            p_low = min(p_low, step_low, close)
            price = close
            if step == max(1, range_steps):
                terminal = price
        terminal_prices.append(terminal)
        path_highs.append(p_high)
        path_lows.append(p_low)

    range_probs = []
    for bracket in ranges:
        count = sum(1 for p in terminal_prices if bracket.contains(p))
        range_probs.append({**bracket.to_dict(), "probability": count / simulations})
    range_probs.sort(key=lambda x: x["probability"], reverse=True)

    hit_probs = []
    for level in hit_levels:
        if level.direction == "UP":
            count = sum(1 for x in path_highs if x >= level.target)
        else:
            count = sum(1 for x in path_lows if x <= level.target)
        hit_probs.append({**level.to_dict(), "probability": count / simulations})
    hit_probs.sort(key=lambda x: (x["direction"], x["target"]))

    sorted_terminal = sorted(terminal_prices)
    sorted_high = sorted(path_highs)
    sorted_low = sorted(path_lows)

    def q(values: list[float], p: float) -> float:
        if not values:
            return start
        idx = min(len(values) - 1, max(0, round((len(values) - 1) * p)))
        return values[idx]

    top_prob = range_probs[0]["probability"] if range_probs else 0.0
    data_score = min(1.0, len(candles) / 2800)
    concentration = min(1.0, top_prob / 0.60) if top_prob else 0.35
    stability = max(0.0, 1.0 - abs(features.vol_ratio - 1.0) * 0.35)
    confidence = round(100 * (0.35 * data_score + 0.40 * concentration + 0.25 * stability))
    confidence = max(1, min(99, confidence))

    return {
        "model": "empirical_15m_bootstrap_v0.1",
        "simulations": simulations,
        "volatility_scale": scale,
        "range_steps_15m": range_steps,
        "hit_steps_15m": hit_steps,
        "terminal_quantiles": {
            "p10": q(sorted_terminal, 0.10),
            "p25": q(sorted_terminal, 0.25),
            "p50": q(sorted_terminal, 0.50),
            "p75": q(sorted_terminal, 0.75),
            "p90": q(sorted_terminal, 0.90),
        },
        "expected_path_low": {"p10": q(sorted_low, 0.10), "p50": q(sorted_low, 0.50), "p90": q(sorted_low, 0.90)},
        "expected_path_high": {"p10": q(sorted_high, 0.10), "p50": q(sorted_high, 0.50), "p90": q(sorted_high, 0.90)},
        "range_probabilities": range_probs,
        "hit_probabilities": hit_probs,
        "confidence": confidence,
    }
