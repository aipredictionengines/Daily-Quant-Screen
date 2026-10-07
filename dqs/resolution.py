from __future__ import annotations

from datetime import date

from dqs.adapters.binance import BinanceAdapter
from dqs.timeutils import candle_open_for_close, market_datetime, to_epoch_ms


def resolve_binance_close(
    adapter: BinanceAdapter,
    symbol: str,
    day: date,
    market_timezone: str,
    resolution_hhmm: str,
    candle_reference: str = "CLOSE_AT",
) -> dict:
    market_dt = market_datetime(day, resolution_hhmm, market_timezone)

    if candle_reference != "CLOSE_AT":
        raise ValueError(f"Unsupported resolution candle reference: {candle_reference}")

    candle_open_dt = candle_open_for_close(market_dt, interval_minutes=1)
    candle = adapter.fetch_one_minute_at(symbol, to_epoch_ms(candle_open_dt))

    return {
        "source": "Binance",
        "symbol": symbol,
        "candle_reference": candle_reference,
        "rule": (
            f"1m Binance candle closing at {resolution_hhmm} {market_timezone}; "
            "score uses its final Close"
        ),
        "market_close_at": market_dt.isoformat(),
        "binance_candle_open_at": candle_open_dt.isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "open_time_ms": candle.open_time_ms,
        "close_time_ms": candle.close_time_ms,
    }
