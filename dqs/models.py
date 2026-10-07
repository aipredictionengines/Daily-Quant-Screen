from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Candle:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RangeBracket:
    lower: float | None
    upper: float | None
    label: str
    market_id: str | None = None
    yes_asset_id: str | None = None

    def contains(self, price: float) -> bool:
        lower_ok = self.lower is None or price >= self.lower
        upper_ok = self.upper is None or price < self.upper
        return lower_ok and upper_ok

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HitLevel:
    target: float
    direction: str
    label: str
    market_id: str | None = None
    yes_asset_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextEvent:
    title: str
    category: str
    severity: str
    time_et: str | None = None
    source_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextReport:
    status: str
    event_risk: str = "UNKNOWN"
    official_fomc_meeting_day: bool | None = None
    summary: str = ""
    events: list[ContextEvent] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    raw_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "event_risk": self.event_risk,
            "official_fomc_meeting_day": self.official_fomc_meeting_day,
            "summary": self.summary,
            "events": [x.to_dict() for x in self.events],
            "sources": self.sources,
            "raw_error": self.raw_error,
        }
