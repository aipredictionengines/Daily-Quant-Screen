from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from dqs.http import HttpError, get_json
from dqs.models import HitLevel, RangeBracket

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"


def _number(text: str) -> float:
    clean = text.replace("$", "").replace(",", "").strip().lower()
    multiplier = 1.0
    if clean.endswith("k"):
        multiplier = 1000.0
        clean = clean[:-1]
    elif clean.endswith("m"):
        multiplier = 1_000_000.0
        clean = clean[:-1]
    return float(clean) * multiplier


def parse_range_label(text: str) -> tuple[float, float] | None:
    candidates = re.findall(r"\$?\d[\d,]*(?:\.\d+)?\s*[kKmM]?", text)
    nums: list[float] = []
    for item in candidates:
        try:
            nums.append(_number(item))
        except ValueError:
            pass
    large = [x for x in nums if x >= 1000]
    if len(large) >= 2:
        a, b = large[0], large[1]
        if a != b:
            return (min(a, b), max(a, b))
    return None


def parse_hit_label(text: str) -> tuple[str, float] | None:
    direction = None
    lower = text.lower()
    if "↑" in text or "above" in lower or "over" in lower or ">=" in text:
        direction = "UP"
    elif "↓" in text or "below" in lower or "under" in lower or "<=" in text:
        direction = "DOWN"
    if not direction:
        return None
    candidates = re.findall(r"\$?\d[\d,]*(?:\.\d+)?\s*[kKmM]?", text)
    values = []
    for item in candidates:
        try:
            values.append(_number(item))
        except ValueError:
            pass
    large = [x for x in values if x >= 100]
    if not large:
        return None
    return direction, large[0]


def _asset_ids(market: dict[str, Any]) -> list[str]:
    version = str(market.get("version") or "").lower()
    if version == "v2" and isinstance(market.get("positionIds"), list):
        return [str(x) for x in market["positionIds"]]
    raw = market.get("clobTokenIds")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError:
            pass
    if isinstance(raw, list):
        return [str(x) for x in raw]
    positions = market.get("positionIds")
    if isinstance(positions, list):
        return [str(x) for x in positions]
    return []


@dataclass
class PolymarketStructure:
    range_event_id: str | None
    range_event_slug: str | None
    ranges: list[RangeBracket]
    hit_event_id: str | None
    hit_event_slug: str | None
    hit_levels: list[HitLevel]

    def to_dict(self) -> dict[str, Any]:
        return {
            "range_event_id": self.range_event_id,
            "range_event_slug": self.range_event_slug,
            "ranges": [x.to_dict() for x in self.ranges],
            "hit_event_id": self.hit_event_id,
            "hit_event_slug": self.hit_event_slug,
            "hit_levels": [x.to_dict() for x in self.hit_levels],
        }


@dataclass
class PolymarketAdapter:
    gamma_base: str = GAMMA_BASE
    clob_base: str = CLOB_BASE

    def discover_btc_daily(self, day: date) -> PolymarketStructure:
        range_event = self._find_event(day, kind="range")
        hit_event = self._find_event(day, kind="hit")
        ranges = self._extract_ranges(range_event) if range_event else []
        hits = self._extract_hits(hit_event) if hit_event else []
        return PolymarketStructure(
            range_event_id=str(range_event.get("id")) if range_event else None,
            range_event_slug=range_event.get("slug") if range_event else None,
            ranges=ranges,
            hit_event_id=str(hit_event.get("id")) if hit_event else None,
            hit_event_slug=hit_event.get("slug") if hit_event else None,
            hit_levels=hits,
        )

    def midpoint(self, asset_id: str) -> float:
        data = get_json(f"{self.clob_base}/midpoint", {"token_id": asset_id})
        return float(data["mid"])

    def benchmark_structure(self, structure: PolymarketStructure) -> dict[str, Any]:
        ranges = []
        for bracket in structure.ranges:
            prob = None
            error = None
            if bracket.yes_asset_id:
                try:
                    prob = self.midpoint(bracket.yes_asset_id)
                except Exception as exc:
                    error = str(exc)
            ranges.append({**bracket.to_dict(), "polymarket_midpoint": prob, "error": error})

        hits = []
        for level in structure.hit_levels:
            prob = None
            error = None
            if level.yes_asset_id:
                try:
                    prob = self.midpoint(level.yes_asset_id)
                except Exception as exc:
                    error = str(exc)
            hits.append({**level.to_dict(), "polymarket_midpoint": prob, "error": error})
        return {"ranges": ranges, "hit_levels": hits}

    def _find_event(self, day: date, kind: str) -> dict[str, Any] | None:
        month = day.strftime("%B").lower()
        d = day.day
        y = day.year
        if kind == "range":
            slugs = [f"bitcoin-price-on-{month}-{d}-{y}", f"bitcoin-price-on-{month}-{d}"]
            title_needles = [f"bitcoin price on {day.strftime('%B')} {d}"]
        else:
            slugs = [f"what-price-will-bitcoin-hit-on-{month}-{d}-{y}", f"what-price-will-bitcoin-hit-on-{month}-{d}"]
            title_needles = [f"what price will bitcoin hit on {day.strftime('%B')} {d}"]

        for slug in slugs:
            try:
                event = get_json(f"{self.gamma_base}/events/slug/{slug}")
                if isinstance(event, dict) and event.get("markets"):
                    return event
            except HttpError:
                pass

        cursor = None
        for _ in range(8):
            params: dict[str, Any] = {"closed": "false", "limit": 100}
            if cursor:
                params["after_cursor"] = cursor
            try:
                page = get_json(f"{self.gamma_base}/events/keyset", params)
            except HttpError:
                return None
            events = page.get("events", []) if isinstance(page, dict) else []
            for event in events:
                title = str(event.get("title") or "").lower()
                if any(needle.lower() in title for needle in title_needles):
                    event_id = event.get("id")
                    if event_id:
                        try:
                            return get_json(f"{self.gamma_base}/events/{event_id}")
                        except HttpError:
                            return event
            cursor = page.get("next_cursor") if isinstance(page, dict) else None
            if not cursor:
                break
        return None

    @staticmethod
    def _extract_ranges(event: dict[str, Any]) -> list[RangeBracket]:
        out: list[RangeBracket] = []
        for market in event.get("markets", []):
            label = str(market.get("groupItemTitle") or market.get("question") or market.get("slug") or "")
            parsed = parse_range_label(label)
            if not parsed:
                continue
            ids = _asset_ids(market)
            out.append(RangeBracket(
                lower=parsed[0],
                upper=parsed[1],
                label=label,
                market_id=str(market.get("id")) if market.get("id") else None,
                yes_asset_id=ids[0] if ids else None,
            ))
        uniq: dict[tuple[float, float], RangeBracket] = {(x.lower, x.upper): x for x in out}
        return [uniq[k] for k in sorted(uniq)]

    @staticmethod
    def _extract_hits(event: dict[str, Any]) -> list[HitLevel]:
        out: list[HitLevel] = []
        for market in event.get("markets", []):
            label = str(market.get("groupItemTitle") or market.get("question") or market.get("slug") or "")
            parsed = parse_hit_label(label)
            if not parsed:
                continue
            ids = _asset_ids(market)
            out.append(HitLevel(
                target=parsed[1],
                direction=parsed[0],
                label=label,
                market_id=str(market.get("id")) if market.get("id") else None,
                yes_asset_id=ids[0] if ids else None,
            ))
        uniq: dict[tuple[str, float], HitLevel] = {(x.direction, x.target): x for x in out}
        return [uniq[k] for k in sorted(uniq)]
