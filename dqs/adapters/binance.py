from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from dqs.http import get_json
from dqs.models import Candle


BINANCE_BASE = "https://api.binance.com"


_INTERVAL_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}


@dataclass
class BinanceAdapter:
    base_url: str = BINANCE_BASE

    def ping(self) -> bool:
        get_json(f"{self.base_url}/api/v3/ping")
        return True

    def price(self, symbol: str) -> float:
        data = get_json(f"{self.base_url}/api/v3/ticker/price", {"symbol": symbol})
        return float(data["price"])

    def fetch_klines(
        self,
        symbol: str,
        interval: str = "15m",
        total: int = 3000,
        end_time_ms: int | None = None,
    ) -> list[Candle]:
        if interval not in _INTERVAL_MS:
            raise ValueError(f"Unsupported interval: {interval}")
        remaining = total
        cursor = end_time_ms
        chunks: list[list[Candle]] = []

        while remaining > 0:
            limit = min(1000, remaining)
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            if cursor is not None:
                params["endTime"] = cursor
            raw = get_json(f"{self.base_url}/api/v3/klines", params)
            if not raw:
                break
            parsed = [self._parse_kline(row) for row in raw]
            chunks.append(parsed)
            remaining -= len(parsed)
            first_open = parsed[0].open_time_ms
            cursor = first_open - 1
            if len(parsed) < limit:
                break

        candles = [item for chunk in reversed(chunks) for item in chunk]
        dedup = {c.open_time_ms: c for c in candles}
        ordered = [dedup[k] for k in sorted(dedup)]
        return ordered[-total:]

    def fetch_one_minute_at(self, symbol: str, open_time_ms: int) -> Candle:
        raw = get_json(
            f"{self.base_url}/api/v3/klines",
            {"symbol": symbol, "interval": "1m", "startTime": open_time_ms, "limit": 1},
        )
        if not raw:
            raise RuntimeError("No Binance 1m candle returned for resolution timestamp")
        candle = self._parse_kline(raw[0])
        tolerance = _INTERVAL_MS["1m"]
        if abs(candle.open_time_ms - open_time_ms) >= tolerance:
            raise RuntimeError(
                f"Unexpected Binance candle timestamp: wanted {open_time_ms}, got {candle.open_time_ms}"
            )
        return candle

    @staticmethod
    def _parse_kline(row: Iterable[object]) -> Candle:
        row = list(row)
        return Candle(
            open_time_ms=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            close_time_ms=int(row[6]),
        )
