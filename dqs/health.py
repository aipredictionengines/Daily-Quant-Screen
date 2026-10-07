from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dqs.adapters.binance import BinanceAdapter
from dqs.adapters.gemini import GeminiContextAdapter
from dqs.adapters.polymarket import PolymarketAdapter
from dqs.rules import first_rules_text, verify_btc_range_rules
from dqs.timeutils import market_datetime, to_epoch_ms


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def run_health(day: date, config: dict[str, Any]) -> dict[str, Any]:
    binance = BinanceAdapter()
    polymarket = PolymarketAdapter()
    gemini = GeminiContextAdapter(model=config.get("gemini_model", "gemini-3.8-flash"))

    checks: dict[str, Any] = {}

    # Binance
    try:
        ping = binance.ping()
        price = binance.price(config.get("asset", "BTCUSDT"))
        candles = binance.fetch_klines(config.get("asset", "BTCUSDT"), interval="15m", total=16)
        checks["binance"] = {
            "status": _status(bool(ping and price > 0 and len(candles) >= 10)),
            "price": price,
            "candles": len(candles),
        }
    except Exception as exc:
        checks["binance"] = {"status": "FAIL", "error": str(exc)}

    # Polymarket Gamma + CLOB
    structure = None
    raw_event = None
    try:
        raw_event = polymarket._find_event(day, kind="range")
        structure = polymarket.discover_btc_daily(day)
        checks["polymarket_gamma"] = {
            "status": _status(bool(structure.ranges)),
            "range_event_id": structure.range_event_id,
            "range_event_slug": structure.range_event_slug,
            "range_count": len(structure.ranges),
            "hit_count": len(structure.hit_levels),
        }
    except Exception as exc:
        checks["polymarket_gamma"] = {"status": "FAIL", "error": str(exc)}

    try:
        token = None
        if structure:
            token = next((x.yes_asset_id for x in structure.ranges if x.yes_asset_id), None)
        if not token:
            raise RuntimeError("No YES outcome token was discovered from Gamma.")
        midpoint = polymarket.midpoint(token)
        checks["polymarket_clob"] = {
            "status": _status(0.0 <= midpoint <= 1.0),
            "sample_midpoint": midpoint,
            "sample_token_id": token,
        }
    except Exception as exc:
        checks["polymarket_clob"] = {"status": "FAIL", "error": str(exc)}

    # Rules
    rules_text = first_rules_text(raw_event)
    rule_check = verify_btc_range_rules(rules_text)
    checks["rules"] = rule_check.to_dict()
    if rules_text:
        checks["rules"]["rules_excerpt"] = " ".join(rules_text.split())[:700]

    # Timezone exact mapping + Binance candle addressability.
    try:
        resolution_dt = market_datetime(day, config["range_resolution_time"], config["market_timezone"])
        sofia_dt = resolution_dt.astimezone(ZoneInfo(config["local_timezone"]))
        exact_epoch = to_epoch_ms(resolution_dt)
        tz_status = "PASS"
        tz_error = None
        # Exact live candle only if the resolution time is already in the past.
        live_candle = None
        if resolution_dt <= datetime.now(ZoneInfo(config["market_timezone"])):
            candle = binance.fetch_one_minute_at(config.get("asset", "BTCUSDT"), exact_epoch)
            live_candle = {
                "open_time_ms": candle.open_time_ms,
                "close_time_ms": candle.close_time_ms,
                "close": candle.close,
            }
            if candle.open_time_ms != exact_epoch:
                tz_status = "FAIL"
                tz_error = f"Expected open_time_ms={exact_epoch}, got {candle.open_time_ms}"
        checks["timezone"] = {
            "status": tz_status,
            "market_datetime": resolution_dt.isoformat(),
            "sofia_datetime": sofia_dt.isoformat(),
            "epoch_ms": exact_epoch,
            "live_candle": live_candle,
            "error": tz_error,
        }
    except Exception as exc:
        checks["timezone"] = {"status": "FAIL", "error": str(exc)}

    # Gemini is supportive, not authoritative; missing key is VERIFY rather than FAIL.
    if not os.getenv("GEMINI_API_KEY"):
        checks["gemini"] = {
            "status": "VERIFY",
            "note": "GEMINI_API_KEY is not configured in this runtime. Numerical forecast remains independent.",
        }
    else:
        report = gemini.analyze(day, asset="BTC")
        checks["gemini"] = {
            "status": "PASS" if report.status == "PASS" else "VERIFY",
            "event_risk": report.event_risk,
            "official_fomc_meeting_day": report.official_fomc_meeting_day,
            "summary": report.summary,
            "error": report.raw_error,
        }

    hard = ("binance", "polymarket_gamma", "polymarket_clob", "rules", "timezone")
    red = [name for name in hard if checks.get(name, {}).get("status") == "FAIL"]
    yellow = [name for name, value in checks.items() if value.get("status") == "VERIFY"]

    overall = "FAIL" if red else ("VERIFY" if yellow else "PASS")
    return {
        "schema_version": "dqs.health.v0.2",
        "market_date": day.isoformat(),
        "generated_at": datetime.now(ZoneInfo(config["local_timezone"])).isoformat(),
        "overall": overall,
        "red_checks": red,
        "verify_checks": yellow,
        "paper_candidate_allowed": not red,
        "official_paper_allowed": overall == "PASS",
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily Quant Screen LIVE-DATA-001 health check")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output")
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    report = run_health(date.fromisoformat(args.date), cfg)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["overall"] == "FAIL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
