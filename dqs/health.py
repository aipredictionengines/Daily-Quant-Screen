from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dqs.adapters.binance import BinanceAdapter
from dqs.adapters.gemini import GeminiContextAdapter
from dqs.adapters.polymarket import PolymarketAdapter
from dqs.calendar import is_official_fomc_meeting_day
from dqs.rules import first_rules_text, verify_btc_range_rules
from dqs.timeutils import candle_open_for_close, market_datetime, to_epoch_ms


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def run_health(day: date, config: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    root = root or Path(".")
    binance = BinanceAdapter()
    polymarket = PolymarketAdapter()
    gemini = GeminiContextAdapter(model=config.get("gemini_model", "gemini-3.8-flash"))

    checks: dict[str, Any] = {}

    # Binance public market data
    try:
        ping = binance.ping()
        price = binance.price(config.get("asset", "BTCUSDT"))
        candles = binance.fetch_klines(config.get("asset", "BTCUSDT"), interval="15m", total=16)
        checks["binance"] = {
            "status": _status(bool(ping and price > 0 and len(candles) >= 10)),
            "price": price,
            "candles": len(candles),
            "base_url_used": binance.last_base_url,
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

    # Require full categorical coverage, including both open-ended tails.
    try:
        if not structure or not structure.ranges:
            raise RuntimeError("No range brackets discovered.")
        has_lower_tail = any(x.lower is None and x.upper is not None for x in structure.ranges)
        has_upper_tail = any(x.upper is None and x.lower is not None for x in structure.ranges)
        finite = [x for x in structure.ranges if x.lower is not None and x.upper is not None]
        checks["range_coverage"] = {
            "status": _status(has_lower_tail and has_upper_tail and len(finite) >= 1),
            "total_brackets": len(structure.ranges),
            "finite_brackets": len(finite),
            "lower_tail": has_lower_tail,
            "upper_tail": has_upper_tail,
        }
    except Exception as exc:
        checks["range_coverage"] = {"status": "FAIL", "error": str(exc)}

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

    # Exact market rules signature.
    rules_text = first_rules_text(raw_event)
    rule_check = verify_btc_range_rules(rules_text)
    checks["rules"] = rule_check.to_dict()
    if rules_text:
        checks["rules"]["rules_excerpt"] = " ".join(rules_text.split())[:700]

    # Independent official FOMC meeting-day snapshot. Gemini does not control this hard gate.
    fomc_path = root / config.get("fomc_calendar_file", "config/fomc-2026.json")
    fomc_day, fomc_status = is_official_fomc_meeting_day(day, fomc_path)
    checks["fomc_calendar"] = {
        "status": fomc_status,
        "official_meeting_day": fomc_day,
        "calendar_file": str(fomc_path),
    }

    # Timezone mapping. Rules say the 1m candle CLOSES at 12:00 ET, therefore
    # the Binance 1m candle opens one minute earlier at 11:59 ET.
    try:
        resolution_close = market_datetime(day, config["range_resolution_time"], config["market_timezone"])
        sofia_close = resolution_close.astimezone(ZoneInfo(config["local_timezone"]))
        reference = config.get("range_resolution_reference", "CLOSE_AT")
        if reference != "CLOSE_AT":
            raise RuntimeError(f"Expected CLOSE_AT resolution reference, got {reference}")
        candle_open = candle_open_for_close(resolution_close, 1)
        checks["timezone"] = {
            "status": "PASS",
            "candle_reference": reference,
            "market_close_at": resolution_close.isoformat(),
            "binance_candle_open_at": candle_open.isoformat(),
            "sofia_close_at": sofia_close.isoformat(),
            "candle_open_epoch_ms": to_epoch_ms(candle_open),
        }
    except Exception as exc:
        checks["timezone"] = {"status": "FAIL", "error": str(exc)}

    # Historical replay proves that the calculated close-at timestamp addresses
    # exactly the previous day's Binance 1m candle.
    try:
        replay_day = day - timedelta(days=1)
        replay_close = market_datetime(
            replay_day,
            config["range_resolution_time"],
            config["market_timezone"],
        )
        replay_open = candle_open_for_close(replay_close, 1)
        expected_open_ms = to_epoch_ms(replay_open)
        expected_close_ms = to_epoch_ms(replay_close) - 1
        candle = binance.fetch_one_minute_at(config.get("asset", "BTCUSDT"), expected_open_ms)
        exact = candle.open_time_ms == expected_open_ms and candle.close_time_ms == expected_close_ms
        checks["resolution_replay"] = {
            "status": _status(exact),
            "replay_day": replay_day.isoformat(),
            "market_close_at": replay_close.isoformat(),
            "expected_open_time_ms": expected_open_ms,
            "actual_open_time_ms": candle.open_time_ms,
            "expected_close_time_ms": expected_close_ms,
            "actual_close_time_ms": candle.close_time_ms,
            "close": candle.close,
            "base_url_used": binance.last_base_url,
        }
    except Exception as exc:
        checks["resolution_replay"] = {"status": "FAIL", "error": str(exc)}

    # Gemini is supportive, not authoritative; missing key is VERIFY rather than FAIL.
    if not os.getenv("GEMINI_API_KEY"):
        checks["gemini"] = {
            "status": "VERIFY",
            "note": "GEMINI_API_KEY is not configured in this runtime. Numerical forecast and FOMC hard gate remain independent.",
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

    hard = (
        "binance",
        "polymarket_gamma",
        "range_coverage",
        "polymarket_clob",
        "rules",
        "fomc_calendar",
        "timezone",
        "resolution_replay",
    )
    red = [name for name in hard if checks.get(name, {}).get("status") == "FAIL"]
    yellow = [name for name, value in checks.items() if value.get("status") == "VERIFY"]

    overall = "FAIL" if red else ("VERIFY" if yellow else "PASS")
    return {
        "schema_version": "dqs.health.v0.3",
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
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    report = run_health(date.fromisoformat(args.date), cfg, Path(args.root))
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["overall"] == "FAIL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
