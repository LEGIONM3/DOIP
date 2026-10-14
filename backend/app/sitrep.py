"""Sitrep generator — rule-based foundation + optional LLM narrative layer (P1-1).

Phase 1 (always runs): derives structured sections from the live event log and
world snapshot, cites every claim with source event IDs, and tags each claim as
FACT (from the live log) or PROJ (modelled extrapolation).

Phase 2 (optional, async): tries to rewrite each section body through an Ollama
LLM (default: llama3.2 via http://localhost:11434) to produce fluent, terse
military prose. Falls back silently to Phase-1 text if Ollama is unreachable or
times out (2 s). Confidence scores and citations are NEVER altered by the LLM.

AI-service boundary (AGENTS.md §Ch13): the LLM receives a structured JSON
context assembled from verified facts — it never reads the raw event stream
directly, and its output only overwrites the `body` field.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any

try:
    from .llm_provider import llm_service
except ImportError:
    from app.llm_provider import llm_service

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM configuration — override via env vars if needed
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT_S", "2.0"))   # hard wall; fail fast so the API stays snappy

# System prompt keeps the LLM in a tightly scoped role
_SYSTEM_PROMPT = (
    "You are a military staff officer writing a situation report. "
    "Rewrite ONLY the 'body' field of each section using concise, authoritative "
    "military prose (≤ 60 words per section). Keep every fact — numbers, "
    "callsigns, ticks — exactly as given. Do not invent information. "
    "Return a JSON array with the same structure but updated 'body' fields only. "
    "If unsure, return the input unchanged."
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class SitrepSection:
    heading: str
    body: str
    confidence: float
    citations: list[dict]
    evidence_kind: str   # FACT | PROJ


# ---------------------------------------------------------------------------
# Phase 1 — rule-based generator (deterministic, always correct)
# ---------------------------------------------------------------------------
def _build_sections(world_snapshot: dict, events: list[dict]) -> list[SitrepSection]:
    def cite(type_: str, n: int = 3) -> list[dict]:
        return [
            {"id": e["id"], "tick": e["tick"], "type": e["type"],
             "entityId": e["entityId"], "severity": e["severity"]}
            for e in reversed(events)
            if e["type"] == type_
        ][:n]

    units     = list(world_snapshot.get("units", {}).values())
    incidents = list(world_snapshot.get("incidents", {}).values())
    alerts    = list(world_snapshot.get("alerts", {}).values())
    depots    = list(world_snapshot.get("depots", {}).values())
    tick      = world_snapshot.get("tick", 0)

    open_inc       = [i for i in incidents if i.get("open")]
    crit_inc       = [i for i in open_inc if i.get("severity") in ("critical", "high")]
    stale          = [u for u in units if tick - u.get("lastSeenTick", 0) >= 180]
    low_fuel       = [u for u in units if u.get("fuel", 100) < 30]
    low_depot_fuel = [d for d in depots if d.get("stock", {}).get("fuel", 999) < 600]
    unacked        = [a for a in alerts if not a.get("acked")]

    def _cs(items: list) -> str:
        return ", ".join(u.get("callsign", u["id"]) for u in items)

    return [
        SitrepSection(
            heading="Overall posture",
            body=(
                f"{len(units)} units committed across "
                f"{world_snapshot.get('scenarioId', 'unknown')} at T+{tick}. "
                + (f"{len(crit_inc)} incident(s) at high or critical severity are shaping the picture."
                   if crit_inc else "No high-severity incidents are currently open.")
                + f" {len(unacked)} alert(s) remain unacknowledged."
            ),
            confidence=0.92,
            citations=cite("incident_open"),
            evidence_kind="FACT",
        ),
        SitrepSection(
            heading="Communications",
            body=(
                f"{len(stale)} unit(s) have exceeded the 3-minute reporting threshold "
                f"and are rendered stale. Recommend comms check on {_cs(stale)}."
                if stale else
                "All units reporting inside the 3-minute threshold; no comms gaps detected."
            ),
            confidence=0.78 if stale else 0.95,
            citations=cite("comms_loss"),
            evidence_kind="FACT",
        ),
        SitrepSection(
            heading="Sustainment",
            body=(
                f"{len(low_fuel)} unit(s) below 30% fuel: {_cs(low_fuel)}. "
                f"{len(low_depot_fuel)} depot(s) below 600-unit fuel threshold. "
                "Consider tasking resupply now."
                if low_fuel or low_depot_fuel else
                "Fuel and battery states nominal across all committed units and depots."
            ),
            confidence=0.71,
            citations=cite("resource_level"),
            evidence_kind="PROJ",
        ),
        SitrepSection(
            heading="Recommended actions",
            body=" ".join(filter(None, [
                f"Prioritise closure of {len(crit_inc)} high/critical incident(s)." if crit_inc else None,
                "Re-establish comms with stale units before the next phase line." if stale else None,
                "Issue resupply tasking from the nearest depot." if low_fuel else None,
                "Maintain current patrol density; no re-tasking required at this time.",
            ])),
            confidence=0.64,
            citations=cite("alert_raise"),
            evidence_kind="PROJ",
        ),
    ]


# ---------------------------------------------------------------------------
# Phase 2 — multi-provider LLM enhancement (best-effort, fail-soft)
# ---------------------------------------------------------------------------
def _llm_rewrite_sync(sections_json: str) -> str | None:
    """Invokes llm_service to synthesize/enhance sitrep sections."""
    try:
        return llm_service.generate(
            prompt=sections_json,
            system_prompt=_SYSTEM_PROMPT,
            max_tokens=800,
            temperature=0.3,
        )
    except Exception as exc:
        log.debug("LLM service unavailable (%s) — using rule-based sitrep", exc)
        return None


async def _llm_enhance(sections: list[SitrepSection]) -> list[SitrepSection]:
    """Try to rewrite bodies via multi-provider LLM service; return originals on any failure."""
    # Build a lean context for the LLM — only the fields it needs
    ctx = [
        {"heading": s.heading, "body": s.body, "evidence_kind": s.evidence_kind}
        for s in sections
    ]
    try:
        raw = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, _llm_rewrite_sync, json.dumps(ctx)),
            timeout=OLLAMA_TIMEOUT_S + 1.0,   # slightly above inner timeout
        )
    except (asyncio.TimeoutError, Exception) as exc:
        log.debug("Sitrep enhancement failed or timed out: %s", exc)
        return sections

    if not raw:
        return sections

    # Parse LLM response — expect a JSON array
    try:
        match = re.search(r"(\[\s*\{.*\}\s*\])", raw, re.DOTALL)
        content_to_parse = match.group(1) if match else raw
        rewritten = json.loads(content_to_parse)
        if not isinstance(rewritten, list) or len(rewritten) != len(sections):
            return sections
        for i, item in enumerate(rewritten):
            if isinstance(item, dict) and isinstance(item.get("body"), str) and item["body"].strip():
                sections[i].body = item["body"].strip()
        return sections
    except (json.JSONDecodeError, KeyError, IndexError, Exception) as exc:
        log.debug("Could not parse LLM sitrep JSON (%s) — retaining base text", exc)
        return sections


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate(world_snapshot: dict, events: list[dict], enhance: bool = False) -> list[dict]:
    """Synchronous entry-point.

    Returns rule-based sections by default, or runs LLM synthesis if enhance=True.
    """
    sections = _build_sections(world_snapshot, events)
    if enhance:
        ctx = [{"heading": s.heading, "body": s.body, "evidence_kind": s.evidence_kind} for s in sections]
        raw = _llm_rewrite_sync(json.dumps(ctx))
        if raw:
            try:
                match = re.search(r"(\[\s*\{.*\}\s*\])", raw, re.DOTALL)
                content = match.group(1) if match else raw
                rewritten = json.loads(content)
                if isinstance(rewritten, list) and len(rewritten) == len(sections):
                    for i, item in enumerate(rewritten):
                        if isinstance(item, dict) and isinstance(item.get("body"), str) and item["body"].strip():
                            sections[i].body = item["body"].strip()
            except Exception:
                pass
    return _serialise(sections)


async def generate_async(world_snapshot: dict, events: list[dict]) -> list[dict]:
    """Async entry-point — runs rule-based layer then attempts LLM enhancement."""
    sections = _build_sections(world_snapshot, events)
    sections = await _llm_enhance(sections)
    return _serialise(sections)


def _serialise(sections: list[SitrepSection]) -> list[dict]:
    return [
        {
            "heading": s.heading,
            "body": s.body,
            "confidence": s.confidence,
            "citations": s.citations,
            "evidenceKind": s.evidence_kind,
        }
        for s in sections
    ]
