from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def local_now(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def market_datetime(day: date, hhmm: str, market_tz: str) -> datetime:
    t = parse_hhmm(hhmm)
    return datetime.combine(day, t, ZoneInfo(market_tz))


def candle_open_for_close(close_at: datetime, interval_minutes: int = 1) -> datetime:
    return close_at - timedelta(minutes=interval_minutes)


def ceil_steps(start: datetime, end: datetime, step_minutes: int) -> int:
    seconds = (end - start).total_seconds()
    if seconds <= 0:
        return 0
    step = step_minutes * 60
    return int((seconds + step - 1) // step)


def in_local_window(now: datetime, start_hhmm: str, end_hhmm: str) -> bool:
    start = parse_hhmm(start_hhmm)
    end = parse_hhmm(end_hhmm)
    return start <= now.timetz().replace(tzinfo=None) <= end


def day_start(day: date, tz_name: str) -> datetime:
    return datetime.combine(day, time(0, 0), ZoneInfo(tz_name))


def to_epoch_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def from_epoch_ms(ms: int, tz_name: str = "UTC") -> datetime:
    return datetime.fromtimestamp(ms / 1000, ZoneInfo(tz_name))
