from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from dqs.http import HttpError, get_json
from dqs.models import Candle


# Binance documents data-api.binance.vision as the market-data-only base for
# endpoints with NONE security. Keep api.binance.com first because Polymarket's
# resolution language points to Binance spot data; use data-api as an official
# Binance fallback when the primary hostname is geo-blocked from a runner.
BINANCE_BASES = (
    "https://api.binance.com",
    "https://data-api.binance.vision",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
)

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
    base_url: str | None = None
    last_base_url: str | None = None

    def _bases(self) -> tuple[str, ...]:
        return (self.base_url,) if self.base_url else BINANCE_BASES

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        errors: list[str] = []
        for base in self._bases():
            try:
                data = get_json(f"{base}{path}", params)
                self.last_base_url = base
                return data
            except HttpError as exc:
                errors.append(f"{base}: {exc}")
        raise HttpError("All Binance public market-data bases failed: " + " | ".join(errors))

    def ping(self) -> bool:
        self._get("/api/v3/ping")
        return True

    def price(self, symbol: str) -> float:
        data = self._get("/api/v3/ticker/price", {"symbol": symbol})
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
            params: dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
            if cursor is not None:
                params["endTime"] = cursor
            raw = self._get("/api/v3/klines", params)
            if not raw:
                break
            parsed = [self._parse_kline(row) for row in raw]
            chunks.append(parsed)
            remaining -= len(parsed)
            cursor = parsed[0].open_time_ms - 1
            if len(parsed) < limit:
                break

        candles = [item for chunk in reversed(chunks) for item in chunk]
        dedup = {c.open_time_ms: c for c in candles}
        ordered = [dedup[k] for k in sorted(dedup)]
        return ordered[-total:]

    def fetch_one_minute_at(self, symbol: str, open_time_ms: int) -> Candle:
        raw = self._get(
            "/api/v3/klines",
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
