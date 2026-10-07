from __future__ import annotations

from datetime import date

from dqs.adapters.binance import BinanceAdapter
from dqs.timeutils import market_datetime, to_epoch_ms


def resolve_binance_close(
    adapter: BinanceAdapter,
    symbol: str,
    day: date,
    market_timezone: str,
    resolution_hhmm: str,
) -> dict:
    dt = market_datetime(day, resolution_hhmm, market_timezone)
    candle = adapter.fetch_one_minute_at(symbol, to_epoch_ms(dt))
    return {
        "source": "Binance",
        "symbol": symbol,
        "rule": f"1m candle opened at {resolution_hhmm} {market_timezone}; score uses Close",
        "resolution_datetime": dt.isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "open_time_ms": candle.open_time_ms,
        "close_time_ms": candle.close_time_ms,
    }
