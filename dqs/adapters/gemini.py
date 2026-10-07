from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from typing import Any

from dqs.http import post_json
from dqs.models import ContextEvent, ContextReport


INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

_CONTEXT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "event_risk": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "EXTREME"]},
        "official_fomc_meeting_day": {"type": "boolean"},
        "summary": {"type": "string"},
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "category": {"type": "string"},
                    "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "EXTREME"]},
                    "time_et": {"type": ["string", "null"]},
                    "source_note": {"type": ["string", "null"]}
                },
                "required": ["title", "category", "severity", "time_et", "source_note"]
            }
        }
    },
    "required": ["event_risk", "official_fomc_meeting_day", "summary", "events"]
}


@dataclass
class GeminiContextAdapter:
    model: str = "gemini-3.8-flash"
    api_key: str | None = None

    def analyze(self, day: date, asset: str = "BTC") -> ContextReport:
        key = self.api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            return ContextReport(status="DISABLED", raw_error="GEMINI_API_KEY is not set")

        prompt = f"""
You are the event-context analyst for a PAPER-ONLY quantitative forecasting system.
Date: {day.isoformat()}
Asset: {asset}

Use Google Search to identify only information that could materially change same-day volatility or price range.
Prioritize authoritative/primary sources where possible: Federal Reserve, BLS, BEA, EIA, SEC, exchange status pages,
issuer/company investor-relations pages, and major wire/services for breaking news.

Important: DO NOT predict the price and DO NOT copy prediction-market probabilities.
Classify event risk only. Explicitly determine whether {day.isoformat()} is an official scheduled FOMC meeting day.
A day with FOMC minutes, speeches, or other Fed publications is NOT the same as an official FOMC meeting day.
Return concise structured JSON.
""".strip()

        payload = {
            "model": self.model,
            "input": prompt,
            "tools": [{"type": "google_search"}],
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": _CONTEXT_SCHEMA,
            },
        }
        try:
            response = post_json(
                INTERACTIONS_URL,
                payload,
                headers={"x-goog-api-key": key},
                timeout=60,
            )
            text = self._extract_output_text(response)
            parsed = json.loads(text)
            sources = self._extract_sources(response)
            events = [ContextEvent(**item) for item in parsed.get("events", [])]
            return ContextReport(
                status="PASS",
                event_risk=parsed.get("event_risk", "UNKNOWN"),
                official_fomc_meeting_day=parsed.get("official_fomc_meeting_day"),
                summary=parsed.get("summary", ""),
                events=events,
                sources=sources,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            return ContextReport(status="FAIL", raw_error=str(exc))

    @staticmethod
    def _extract_output_text(response: dict[str, Any]) -> str:
        direct = response.get("output_text") or response.get("outputText")
        if direct:
            return str(direct)
        pieces: list[str] = []
        for step in response.get("steps", []):
            if step.get("type") != "model_output":
                continue
            for block in step.get("content", []):
                if block.get("type") == "text" and block.get("text"):
                    pieces.append(str(block["text"]))
        if not pieces:
            raise RuntimeError("Gemini response did not contain output text")
        return "".join(pieces)

    @staticmethod
    def _extract_sources(response: dict[str, Any]) -> list[str]:
        out: list[str] = []
        for step in response.get("steps", []):
            for block in step.get("content", []) if isinstance(step, dict) else []:
                for ann in block.get("annotations", []) if isinstance(block, dict) else []:
                    if ann.get("type") == "url_citation" and ann.get("url"):
                        out.append(str(ann["url"]))
        return list(dict.fromkeys(out))
