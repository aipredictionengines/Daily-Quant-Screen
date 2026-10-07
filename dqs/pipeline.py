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
from dqs.calendar import is_official_fomc_meeting_day
from dqs.models import RangeBracket
from dqs.quant.features import calculate_features
from dqs.quant.forecast import deterministic_seed, simulate
from dqs.rules import first_rules_text, verify_btc_range_rules
from dqs.storage import write_immutable
from dqs.timeutils import ceil_steps, in_local_window, market_datetime


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

    def candidate_dir(self, day: date) -> Path:
        return self.root / "artifacts" / "candidates" / day.isoformat() / "BTC"

    def artifact_dir(self, day: date, run_mode: str) -> Path:
        mode = run_mode.upper()
        if mode == "PAPER":
            return self.paper_dir(day)
        if mode == "CANDIDATE":
            return self.candidate_dir(day)
        raise ValueError(f"Unsupported run_mode: {run_mode}")

    def next_paper_test_id(self) -> str:
        paper_root = self.root / "artifacts" / "paper"
        existing = list(paper_root.glob("*/BTC/forecast.json")) if paper_root.exists() else []
        return f"DQS-BTC-P{len(existing) + 1:03d}"

    def morning(
        self,
        day: date,
        now: datetime | None = None,
        run_mode: str = "PAPER",
    ) -> dict[str, Path | str]:
        mode = run_mode.upper()
        local_tz = ZoneInfo(self.config["local_timezone"])
        now = now.astimezone(local_tz) if now else datetime.now(local_tz)
        locked_at = now.isoformat()
        out_dir = self.artifact_dir(day, mode)

        if now.date() != day:
            raise RuntimeError(
                f"Morning forecast date mismatch: requested {day.isoformat()}, local date is {now.date().isoformat()}"
            )

        window = self.config.get("forecast_window_local", ["05:00", "08:00"])
        if not in_local_window(now, window[0], window[1]):
            raise RuntimeError(
                f"Forecast lock outside allowed {window[0]}–{window[1]} {self.config['local_timezone']} window"
            )

        weekday = day.strftime("%A")
        static_skip = weekday in self.config.get("skip_weekdays", [])

        context = self.gemini.analyze(day, asset="BTC")
        fomc_path = self.root / self.config.get("fomc_calendar_file", "config/fomc-2026.json")
        fomc_day, fomc_calendar_status = is_official_fomc_meeting_day(day, fomc_path)
        if fomc_calendar_status != "PASS":
            raise RuntimeError("Official FOMC calendar snapshot is unavailable; refusing forecast")
        fomc_skip = bool(
            self.config.get("skip_official_fomc_meeting_days", True)
            and fomc_day
        )

        raw_range_event = self.polymarket._find_event(day, kind="range")
        structure = self.polymarket.discover_btc_daily(day)
        if self.config.get("require_polymarket_structure", True) and not structure.ranges:
            raise RuntimeError("Polymarket BTC daily range structure was not discovered; refusing forecast")

        has_lower_tail = any(x.lower is None and x.upper is not None for x in structure.ranges)
        has_upper_tail = any(x.upper is None and x.lower is not None for x in structure.ranges)
        if self.config.get("require_polymarket_structure", True) and not (has_lower_tail and has_upper_tail):
            raise RuntimeError("Polymarket range structure is incomplete; open-ended tails are required")

        rule_check = verify_btc_range_rules(first_rules_text(raw_range_event))
        if rule_check.status != "PASS":
            raise RuntimeError(f"Polymarket range rules are not verified: {rule_check.evidence}")

        configured_reference = self.config.get("range_resolution_reference", "CLOSE_AT")
        if rule_check.candle_reference != configured_reference:
            raise RuntimeError(
                f"Resolution reference mismatch: market={rule_check.candle_reference}, config={configured_reference}"
            )

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
        reasons: list[str] = []
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

        test_id = "DQS-BTC-CANDIDATE-001" if mode == "CANDIDATE" else self.next_paper_test_id()

        payload = {
            "schema_version": "dqs.forecast.v0.3",
            "run_mode": mode,
            "test_id": test_id,
            "series": "BTC DAILY RANGE PAPER 20",
            "counts_toward_paper_20": mode == "PAPER",
            "asset": self.config["asset"],
            "market_date": day.isoformat(),
            "locked_at": locked_at,
            "decision": decision,
            "decision_reasons": reasons,
            "data_gate": {
                "binance": "PASS",
                "polymarket_structure": "PASS",
                "polymarket_rules": rule_check.status,
                "fomc_calendar": fomc_calendar_status,
                "gemini_context": context.status,
            },
            "rules": {
                "verified_market_rules": rule_check.to_dict(),
                "range_resolution_timezone": self.config["market_timezone"],
                "range_resolution_time": self.config["range_resolution_time"],
                "range_resolution_reference": configured_reference,
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
            "schema_version": "dqs.benchmark.v0.2",
            "run_mode": mode,
            "test_id": test_id,
            "market_date": day.isoformat(),
            "forecast_sha256": forecast_hash,
            "captured_at": datetime.now(local_tz).isoformat(),
            "source": "Polymarket CLOB midpoint",
            **benchmark_data,
        }
        benchmark_path = out_dir / "benchmark.json"
        write_immutable(benchmark_path, benchmark_payload)
        return {
            "forecast": forecast_path,
            "benchmark": benchmark_path,
            "decision": decision,
            "run_mode": mode,
            "test_id": test_id,
        }

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
