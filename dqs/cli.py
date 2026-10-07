from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from dqs.adapters.binance import BinanceAdapter
from dqs.pipeline import Pipeline
from dqs.qa import load_bug_log, readiness_report
from dqs.render import render_screen
from dqs.resolution import resolve_binance_close
from dqs.scoring import range_score
from dqs.storage import read_envelope, write_immutable


def _day(value: str) -> date:
    return date.fromisoformat(value)


def _mode(value: str) -> str:
    mode = value.upper()
    if mode not in {"PAPER", "CANDIDATE"}:
        raise argparse.ArgumentTypeError("mode must be paper or candidate")
    return mode


def main() -> None:
    parser = argparse.ArgumentParser(prog="dqs", description="Daily Quant Screen — paper-only BUILD-001")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="cmd", required=True)

    morning = sub.add_parser("morning", help="Build and lock a BTC forecast, then capture Polymarket benchmark")
    morning.add_argument("--date", type=_day, default=date.today())
    morning.add_argument("--mode", type=_mode, default="PAPER")

    resolve = sub.add_parser("resolve", help="Resolve one candidate/paper day from Binance and score it")
    resolve.add_argument("--date", type=_day, required=True)
    resolve.add_argument("--mode", type=_mode, default="PAPER")

    render = sub.add_parser("render", help="Render HTML screen from locked artifacts")
    render.add_argument("--date", type=_day, required=True)
    render.add_argument("--mode", type=_mode, default="PAPER")

    sub.add_parser("scoreboard", help="Aggregate completed official PAPER days only")
    sub.add_parser("buglog", help="Show current QA bug inventory")
    sub.add_parser("readiness", help="Show candidate/PAPER readiness")

    args = parser.parse_args()
    root = Path(args.root).resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    pipeline = Pipeline.from_config(config_path, root)

    if args.cmd == "morning":
        result = pipeline.morning(args.date, run_mode=args.mode)
        print(json.dumps({k: str(v) for k, v in result.items()}, indent=2))
        return

    if args.cmd == "resolve":
        out = pipeline.artifact_dir(args.date, args.mode)
        forecast_env = read_envelope(out / "forecast.json")
        payload = forecast_env["payload"]
        resolution_payload = resolve_binance_close(
            BinanceAdapter(),
            payload["asset"],
            args.date,
            payload["rules"]["range_resolution_timezone"],
            payload["rules"]["range_resolution_time"],
            payload["rules"].get("range_resolution_reference", "CLOSE_AT"),
        )
        resolution_payload["run_mode"] = args.mode
        resolution_path = out / "resolution.json"
        write_immutable(resolution_path, resolution_payload)
        score_payload = {
            "schema_version": "dqs.score.v0.2",
            "run_mode": args.mode,
            "counts_toward_paper_20": args.mode == "PAPER",
            "market_date": args.date.isoformat(),
            "forecast_sha256": forecast_env["sha256"],
            "decision": payload["decision"],
            **range_score(payload, resolution_payload["close"]),
        }
        score_path = out / "score.json"
        write_immutable(score_path, score_payload)
        print(json.dumps({"resolution": str(resolution_path), "score": str(score_path)}, indent=2))
        return

    if args.cmd == "render":
        out = pipeline.artifact_dir(args.date, args.mode)
        forecast = read_envelope(out / "forecast.json")["payload"]
        benchmark_path = out / "benchmark.json"
        benchmark = read_envelope(benchmark_path)["payload"] if benchmark_path.exists() else None
        target = out / "screen.html"
        render_screen(forecast, benchmark, target)
        print(target)
        return

    if args.cmd == "buglog":
        log = load_bug_log(root)
        bugs = log.get("bugs", [])
        summary = {
            "total": len(bugs),
            "active": sum(1 for b in bugs if str(b.get("status", "OPEN")).upper() != "CLOSED"),
            "bugs": bugs,
        }
        print(json.dumps(summary, indent=2))
        return

    if args.cmd == "readiness":
        print(json.dumps(readiness_report(root), indent=2))
        return

    if args.cmd == "scoreboard":
        paper_root = root / "artifacts" / "paper"
        completed = []
        for score_path in sorted(paper_root.glob("*/BTC/score.json")) if paper_root.exists() else []:
            payload = read_envelope(score_path)["payload"]
            if payload.get("decision") == "SKIP":
                continue
            if payload.get("run_mode", "PAPER") != "PAPER":
                continue
            completed.append(payload)
        exact = sum(1 for x in completed if x.get("exact_primary"))
        top2 = sum(1 for x in completed if x.get("top2"))
        briers = [x["brier_discovered_brackets"] for x in completed if x.get("brier_discovered_brackets") is not None]
        result = {
            "paper_target": pipeline.config.get("paper_target", 20),
            "completed_eligible": len(completed),
            "exact_primary": f"{exact}/{len(completed)}" if completed else "0/0",
            "top2": f"{top2}/{len(completed)}" if completed else "0/0",
            "mean_brier": sum(briers) / len(briers) if briers else None,
        }
        print(json.dumps(result, indent=2))
        return


if __name__ == "__main__":
    main()
