from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dqs.adapters.binance import BinanceAdapter
from dqs.adapters.gemini import GeminiContextAdapter
from dqs.adapters.polymarket import PolymarketAdapter, PolymarketStructure
from dqs.models import RangeBracket
from dqs.quant.features import calculate_features
from dqs.quant.forecast import deterministic_seed, simulate
from dqs.storage import write_immutable
from dqs.timeutils import ceil_steps, market_datetime


@dataclass
class Pipeline:
    config: dict[str, Any]
    root: Path
    binance: BinanceAdapter
    polymarket: PolymarketAdapter
    gemini: GeminiContextAdapter

    @classmethod
    def from_config(cls, config_path: Path, root: Path) -> "Pipeline":
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        return cls(
            config=cfg,
            root=root,
            binance=BinanceAdapter(),
            polymarket=PolymarketAdapter(),
            gemini=GeminiContextAdapter(model=cfg.get("gemini_model", "gemini-3.8-flash")),
        )

    def paper_dir(self, day: date) -> Path:
        return self.root / "artifacts" / "paper" / day.isoformat() / "BTC"

    def morning(self, day: date, now: datetime | None = None) -> dict[str, Path | str]:
        local_tz = ZoneInfo(self.config["local_timezone"])
        now = now.astimezone(local_tz) if now else datetime.now(local_tz)
        locked_at = now.isoformat()
        out_dir = self.paper_dir(day)

        weekday = day.strftime("%A")
        static_skip = weekday in self.config.get("skip_weekdays", [])

        context = self.gemini.analyze(day, asset="BTC")
        fomc_skip = bool(
            self.config.get("skip_official_fomc_meeting_days", True)
            and context.official_fomc_meeting_day is True
        )

        structure = self.polymarket.discover_btc_daily(day)
        if self.config.get("require_polymarket_structure", True) and not structure.ranges:
            raise RuntimeError("Polymarket BTC daily range structure was not discovered; refusing PAPER forecast")

        candles = self.binance.fetch_klines(
            self.config["asset"],
            interval=self.config.get("historical_interval", "15m"),
            total=int(self.config.get("historical_candles", 3000)),
            end_time_ms=int(now.timestamp() * 1000),
        )
        features = calculate_features(candles)

        range_dt = market_datetime(day, self.config["range_resolution_time"], self.config["market_timezone"])
        hit_dt = market_datetime(day, self.config["hit_resolution_time"], self.config["market_timezone"])
        now_market = now.astimezone(ZoneInfo(self.config["market_timezone"]))
        range_steps = ceil_steps(now_market, range_dt, 15)
        hit_steps = ceil_steps(now_market, hit_dt, 15)

        if not structure.ranges:
            structure = self._fallback_structure(features.current_price, structure)

        seed = deterministic_seed(self.config["asset"], day.isoformat(), locked_at)
        forecast = simulate(
            candles=candles,
            features=features,
            range_steps=range_steps,
            hit_steps=hit_steps,
            ranges=structure.ranges,
            hit_levels=structure.hit_levels,
            simulations=int(self.config.get("simulations", 12000)),
            seed=seed,
        )

        decision = "FORECAST"
        reasons = []
        if static_skip:
            decision = "SKIP"
            reasons.append(f"weekday_gate:{weekday}")
        if fomc_skip:
            decision = "SKIP"
            reasons.append("official_fomc_meeting_day")
        if context.event_risk == "EXTREME" and self.config.get("extreme_event_risk_skips", False):
            decision = "SKIP"
            reasons.append("extreme_event_risk")
        if forecast["confidence"] < int(self.config.get("min_confidence", 55)) and decision != "SKIP":
            decision = "LOW_CONF"
            reasons.append("confidence_below_threshold")
        if context.status != "PASS":
            reasons.append(f"gemini_context:{context.status}")

        payload = {
            "schema_version": "dqs.paper.forecast.v0.1",
            "paper_test": "BTC DAILY RANGE PAPER 20",
            "asset": self.config["asset"],
            "market_date": day.isoformat(),
            "locked_at": locked_at,
            "decision": decision,
            "decision_reasons": reasons,
            "data_gate": {
                "binance": "PASS",
                "polymarket_structure": "PASS" if structure.ranges else "FAIL",
                "gemini_context": context.status,
            },
            "rules": {
                "range_resolution_timezone": self.config["market_timezone"],
                "range_resolution_time": self.config["range_resolution_time"],
                "hit_resolution_time": self.config["hit_resolution_time"],
                "skip_weekdays": self.config.get("skip_weekdays", []),
                "skip_official_fomc_meeting_days": self.config.get("skip_official_fomc_meeting_days", True),
            },
            "polymarket_structure": structure.to_dict(),
            "features": features.to_dict(),
            "context": context.to_dict(),
            "forecast": forecast,
            "integrity_note": "Polymarket probabilities are intentionally fetched only after this forecast is locked.",
        }

        forecast_path = out_dir / "forecast.json"
        forecast_hash = write_immutable(forecast_path, payload)

        benchmark_data = self.polymarket.benchmark_structure(structure)
        benchmark_payload = {
            "schema_version": "dqs.paper.benchmark.v0.1",
            "market_date": day.isoformat(),
            "forecast_sha256": forecast_hash,
            "captured_at": datetime.now(local_tz).isoformat(),
            "source": "Polymarket CLOB midpoint",
            **benchmark_data,
        }
        benchmark_path = out_dir / "benchmark.json"
        write_immutable(benchmark_path, benchmark_payload)
        return {"forecast": forecast_path, "benchmark": benchmark_path, "decision": decision}

    def _fallback_structure(self, price: float, existing: PolymarketStructure) -> PolymarketStructure:
        step = float(self.config.get("auto_bracket_step", 2000))
        base = int(price // step) * step
        ranges = [
            RangeBracket(base + i * step, base + (i + 1) * step, f"{base + i*step:,.0f}–{base + (i+1)*step:,.0f}")
            for i in range(-2, 3)
            if base + i * step > 0
        ]
        return PolymarketStructure(
            range_event_id=existing.range_event_id,
            range_event_slug=existing.range_event_slug,
            ranges=ranges,
            hit_event_id=existing.hit_event_id,
            hit_event_slug=existing.hit_event_slug,
            hit_levels=existing.hit_levels,
        )
