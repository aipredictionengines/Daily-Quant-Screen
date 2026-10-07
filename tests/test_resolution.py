from datetime import date

from dqs.models import Candle
from dqs.resolution import resolve_binance_close
from dqs.timeutils import candle_open_for_close, market_datetime, to_epoch_ms


class FakeBinance:
    def __init__(self):
        self.requested = None

    def fetch_one_minute_at(self, symbol: str, open_time_ms: int) -> Candle:
        self.requested = open_time_ms
        return Candle(
            open_time_ms=open_time_ms,
            open=83000.0,
            high=83100.0,
            low=82900.0,
            close=83050.0,
            volume=1.0,
            close_time_ms=open_time_ms + 60_000 - 1,
        )


def test_resolution_fetches_1159_for_market_candle_closing_1200_et():
    adapter = FakeBinance()
    out = resolve_binance_close(
        adapter,
        "BTCUSDT",
        date(2026, 10, 7),
        "America/New_York",
        "12:00",
        "CLOSE_AT",
    )
    close_at = market_datetime(date(2026, 10, 7), "12:00", "America/New_York")
    expected_open = candle_open_for_close(close_at, 1)
    assert adapter.requested == to_epoch_ms(expected_open)
    assert out["market_close_at"].startswith("2026-10-07T12:00:00")
    assert out["binance_candle_open_at"].startswith("2026-10-07T11:59:00")
    assert out["close"] == 83050.0
