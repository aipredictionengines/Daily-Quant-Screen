from datetime import date
from zoneinfo import ZoneInfo

from dqs.timeutils import market_datetime


def _sofia_hour(day: date) -> int:
    dt = market_datetime(day, "12:00", "America/New_York")
    return dt.astimezone(ZoneInfo("Europe/Sofia")).hour


def test_normal_winter_is_19_sofia():
    assert _sofia_hour(date(2026, 1, 15)) == 19


def test_us_eu_spring_dst_mismatch_is_18_sofia():
    assert _sofia_hour(date(2026, 3, 20)) == 18


def test_normal_summer_is_19_sofia():
    assert _sofia_hour(date(2026, 10, 7)) == 19


def test_us_eu_fall_dst_mismatch_is_18_sofia():
    assert _sofia_hour(date(2026, 10, 28)) == 18


def test_normal_late_fall_is_19_sofia():
    assert _sofia_hour(date(2026, 11, 15)) == 19
