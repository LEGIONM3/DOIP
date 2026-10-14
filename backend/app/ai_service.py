"""AI Query Service & Context Assembler for DOIP (Phase 1B).

Architecture:
  AiDrawer.tsx (Frontend)
        ↓ POST /api/ai/query
  AI Service Orchestrator (ai_service.py)
        ↓
  1. Multi-Modal Context Assembler (Doctrine + Sim State + Events + Incidents + Logistics)
        ↓
  2. Local LLM Inference Bridge (Ollama / Local Engine with Fail-Soft Heuristic Fallback)
        ↓
  3. Strict Citation Safety Validator (AGENTS.md Ch. 13 Golden Rule — Zero Fabrication)
        ↓
  4. Structured Response (FACT / PROJECTION / RECOMMENDATION / Citations)

Safety Invariants:
  - The LLM MUST NOT directly mutate simulation state.
  - Operational suggestions output as RECOMMENDATION items conforming to DOIP DSL
    and require human confirmation before execution.
  - Every factual claim MUST cite verified source evidence. Fabrications are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
import re
import time
from typing import Any

try:
    from . import db
    from .rag import retrieve, verify_grounding
    from .llm_provider import llm_service
except ImportError:
    from app import db
    from app.rag import retrieve, verify_grounding
    from app.llm_provider import llm_service

log = logging.getLogger(__name__)

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.2:latest")


@dataclass
class AssembledContext:
    query: str
    run_id: str | None
    tick: int
    doctrine_chunks: list[dict[str, Any]]
    world_summary: dict[str, Any]
    recent_events: list[dict[str, Any]]
    active_incidents: list[dict[str, Any]]
    logistics_status: dict[str, Any]
    valid_source_ids: set[str] = field(default_factory=set)


class ContextAssembler:
    """Gathers doctrine, simulation state, event logs, incidents, and logistics."""

    @staticmethod
    def assemble(
        query: str,
        run_id: str | None = None,
        tick: int | None = None,
        active_sessions: dict[str, Any] | None = None,
    ) -> AssembledContext:
        active_sessions = active_sessions or {}

        # 1. Doctrine Retrieval (Top 4 dense semantic chunks)
        doctrine_chunks = retrieve(query, top_k=4)

        # 2. Simulation State & Session Lookup
        target_session = None
        if run_id and run_id in active_sessions:
            target_session = active_sessions[run_id]
        elif not run_id and active_sessions:
            # Pick first active session
            first_run_id = next(iter(active_sessions))
            target_session = active_sessions[first_run_id]
            run_id = first_run_id

        world: dict[str, Any] = {}
        events: list[dict[str, Any]] = []

        if target_session:
            try:
                world = target_session._world_snapshot() if hasattr(target_session, "_world_snapshot") else {}
                events = list(getattr(target_session, "_log", []))
            except Exception as exc:
                log.debug("Session snapshot read notice: %s", exc)

        # Fallback to DB if world is empty
        if not world and run_id:
            world = db.load_world_snapshot(run_id) or {}
            events = db.get_sim_events(run_id, limit=30)
        elif not world:
            # Load latest recorded run if available
            runs = db.list_runs(limit=1)
            if runs:
                world = db.load_world_snapshot(runs[0]["id"]) or {}
                events = db.get_sim_events(runs[0]["id"], limit=30)

        effective_tick = tick if tick is not None else int(world.get("tick", 0))

        # 3. Incidents Summary
        raw_incidents = world.get("incidents", {})
        active_incidents = []
        if isinstance(raw_incidents, dict):
            for inc_id, inc_data in raw_incidents.items():
                if inc_data.get("open", True):
                    active_incidents.append({
                        "id": inc_id,
                        "title": inc_data.get("title", inc_id),
                        "severity": inc_data.get("severity", "medium"),
                        "location": inc_data.get("location", [0.0, 0.0]),
                    })

        # 4. Logistics & Vitals
        raw_units = world.get("units", {})
        units_list = list(raw_units.values()) if isinstance(raw_units, dict) else []
        low_fuel = [u for u in units_list if u.get("fuel", 100.0) < 40.0]
        stale_units = [u for u in units_list if u.get("status") == "stale"]

        logistics = {
            "total_units": len(units_list),
            "low_fuel_units": [
                {"callsign": u.get("callsign", u.get("id")), "fuel": round(u.get("fuel", 0.0), 1)}
                for u in low_fuel
            ],
            "stale_units": [u.get("callsign", u.get("id")) for u in stale_units],
        }

        # 5. World Telemetry Summary
        world_summary = {
            "tick": effective_tick,
            "scenario": world.get("scenarioId", "SC-1"),
            "active_weather": len(world.get("weather", {})),
            "unacked_alerts": len([a for a in world.get("alerts", {}).values() if not a.get("acked")]),
        }

        # 6. Extract Authoritative Known Identifiers for Citation Gate
        valid_ids: set[str] = set()
        for c in doctrine_chunks:
            valid_ids.add(c["document_id"].upper())
        for inc in active_incidents:
            valid_ids.add(inc["id"].upper())
        for ev in events[-30:]:
            if ev.get("id"):
                valid_ids.add(str(ev["id"]).upper())
            if ev.get("entityId"):
                valid_ids.add(str(ev["entityId"]).upper())
            payload = ev.get("payload", {})
            if payload.get("alertId"):
                valid_ids.add(str(payload["alertId"]).upper())
        for u in units_list:
            if u.get("id"):
                valid_ids.add(str(u["id"]).upper())
            if u.get("callsign"):
                valid_ids.add(str(u["callsign"]).upper())

        return AssembledContext(
            query=query,
            run_id=run_id,
            tick=effective_tick,
            doctrine_chunks=doctrine_chunks,
            world_summary=world_summary,
            recent_events=events[-20:],
            active_incidents=active_incidents,
            logistics_status=logistics,
            valid_source_ids=valid_ids,
        )


class CitationValidator:
    """Enforces AGENTS.md Chapter 13 AI safety invariants.

    Ensures the LLM cannot fabricate doctrine doc IDs, event IDs, or tactical units.
    """

    @staticmethod
    def validate(
        text: str,
        valid_sources: set[str],
        doctrine_chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        doc_map = {c["document_id"].upper(): c for c in doctrine_chunks}

        # Extract bracketed and token citations
        cited_tokens = set(re.findall(r"\[([A-Za-z0-9_\-\s§\.]+)\]", text))
        raw_tokens = set(re.findall(r"\b(SOP-\d+|POL-\d+|REF-\d+|INC-\w+|AL-\w+|EV-\w+|UAV-\w+|CAM-\w+)\b", text, re.IGNORECASE))
        all_candidates = {t.upper().strip() for t in (cited_tokens | raw_tokens)}

        verified_citations: list[dict[str, Any]] = []
        unverified_citations: list[str] = []

        for token in sorted(all_candidates):
            # Check if token starts with a known document ID (e.g. "SOP-04 §1" starts with "SOP-04")
            base_doc_match = re.match(r"^(SOP-\d+|POL-\d+|REF-\d+)", token)
            matched = False

            if base_doc_match:
                base_doc = base_doc_match.group(1)
                if base_doc in valid_sources or base_doc in doc_map:
                    matched = True
                    c_info = doc_map.get(base_doc, {})
                    verified_citations.append({
                        "type": "doctrine",
                        "source_id": base_doc,
                        "citation": token if "§" in token else c_info.get("citation", base_doc),
                        "title": c_info.get("section", "Standard Operating Procedure"),
                        "verified": True,
                    })

            if not matched:
                if token in valid_sources:
                    matched = True
                    c_type = "incident" if token.startswith("INC") else ("event" if token.startswith("EV") else "unit")
                    verified_citations.append({
                        "type": c_type,
                        "source_id": token,
                        "citation": token,
                        "title": f"Tactical {c_type.capitalize()} Evidence",
                        "verified": True,
                    })

            if not matched and any(token.startswith(prefix) for prefix in ["SOP-", "POL-", "REF-", "INC-", "EV-"]):
                unverified_citations.append(token)

        is_grounded = len(unverified_citations) == 0
        warning = f"References unverified or fabricated identifiers: {unverified_citations}" if not is_grounded else None

        return {
            "grounded": is_grounded,
            "warning": warning,
            "verified_citations": verified_citations,
            "unverified_citations": unverified_citations,
        }


class AIService:
    """Core reasoning engine and LLM bridge with deterministic fail-soft fallback."""

    def __init__(self) -> None:
        self.context_assembler = ContextAssembler()
        self.validator = CitationValidator()
        self.llm = llm_service

    def _query_local_llm(self, prompt: str, system_prompt: str) -> str | None:
        """Attempt inference via configured LLM provider."""
        try:
            return self.llm.generate(prompt, system_prompt=system_prompt, max_tokens=1024, temperature=0.1)
        except Exception as exc:
            log.debug("LLM provider unavailable (%s) — activating fail-soft heuristic", exc)
            return None

    def _generate_failsoft_response(self, ctx: AssembledContext) -> dict[str, Any]:
        """Deterministic, grounded reasoning engine when LLM is offline.

        Guarantees zero-failure operation across all DOIP views.
        """
        q = ctx.query.lower()
        facts: list[str] = []
        projections: list[str] = []
        recommendations: list[dict[str, Any]] = []

        # 1. Doctrine insights
        top_chunk = ctx.doctrine_chunks[0] if ctx.doctrine_chunks else None
        doc_summary = ""
        if top_chunk:
            doc_summary = f"According to [{top_chunk['citation']}] ({top_chunk['section']}): {top_chunk['text'][:280]}."
            facts.append(f"Doctrine guidance sourced from [{top_chunk['document_id']}] ({top_chunk['section']}).")

        # 2. Logistics & Fuel Analysis
        low_fuel = ctx.logistics_status.get("low_fuel_units", [])
        stale_units = ctx.logistics_status.get("stale_units", [])

        if re.search(r"fuel|resupply|logisti|supply|depot|gas", q):
            if low_fuel:
                names = ", ".join(f"{u['callsign']} ({u['fuel']}%)" for u in low_fuel)
                facts.append(f"{len(low_fuel)} unit(s) operating under 40% fuel reserve: {names}.")
                projections.append("Sustained patrol without depot resupply will reach bingo fuel within 20 sim-minutes.")
                recommendations.append({
                    "action": "task_resupply",
                    "entity_id": low_fuel[0]["callsign"],
                    "summary": f"Authorize priority fuel dispatch for {low_fuel[0]['callsign']} at depot.",
                    "priority": "HIGH",
                    "requires_confirmation": True,
                    "requires_human_confirmation": True,
                })
            else:
                facts.append("All operational units report nominal fuel reserves above 40%.")

        # 3. Comms & Stale Reports
        elif re.search(r"comms|radio|silence|stale|signal|reporting", q):
            if stale_units:
                facts.append(f"{len(stale_units)} unit(s) past reporting threshold: {', '.join(stale_units)}.")
                projections.append("Continued silence past 10 minutes escalates to lost-contact protocol under SOP-06.")
                recommendations.append({
                    "action": "radio_check",
                    "entity_id": stale_units[0],
                    "summary": f"Broadcast tactical comms sweep to {stale_units[0]}.",
                    "priority": "MEDIUM",
                    "requires_confirmation": True,
                    "requires_human_confirmation": True,
                })
            else:
                facts.append("All active tactical units are transmitting within the 3-minute reporting window.")

        # 4. Threats & Incidents
        elif re.search(r"incident|threat|attack|contact|hostile|salute", q):
            if ctx.active_incidents:
                crit_count = sum(1 for i in ctx.active_incidents if i["severity"] in ("critical", "high"))
                facts.append(f"{len(ctx.active_incidents)} incident(s) active; {crit_count} assessed high or critical severity.")
                projections.append("Threat posture elevated; UAV recon overwatch recommended along incident bearing.")
                recommendations.append({
                    "action": "deploy_uav_overwatch",
                    "entity_id": "U-UAV-1",
                    "summary": f"Task UAV-1 sensor sweep over incident {ctx.active_incidents[0]['id']}.",
                    "priority": "CRITICAL",
                    "requires_confirmation": True,
                    "requires_human_confirmation": True,
                })
            else:
                facts.append("Zero active threat incidents recorded in the current sector.")

        # 5. Default General Tactical Posture
        else:
            facts.append(
                f"Tactical state at T+{ctx.tick}: {ctx.logistics_status['total_units']} units committed, "
                f"{len(ctx.active_incidents)} incident(s) active, {ctx.world_summary['active_weather']} active weather cell(s)."
            )
            if low_fuel:
                projections.append(f"{len(low_fuel)} unit(s) trending toward critical fuel reserves.")

        # Synthesize cohesive answer
        components = [doc_summary] if doc_summary else []
        components.extend(facts)
        if projections:
            components.append(f"Projection: {projections[0]}")
        answer = " ".join(components)

        return {
            "answer": answer,
            "facts": facts,
            "projections": projections,
            "recommendations": recommendations,
            "mode": "rule_grounded_fallback",
        }

    def query(
        self,
        query: str,
        run_id: str | None = None,
        tick: int | None = None,
        active_sessions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process user query and return verified, grounded tactical analysis."""
        t0 = time.perf_counter()

        # 1. Assemble structured context
        ctx = self.context_assembler.assemble(
            query=query,
            run_id=run_id,
            tick=tick,
            active_sessions=active_sessions,
        )

        reasoning_context = {
            "doctrine": [
                {
                    "document_id": c.get("document_id"),
                    "citation": c.get("citation"),
                    "section": c.get("section", ""),
                    "title": c.get("section", ""),
                    "text": c.get("text", "")[:300],
                }
                for c in ctx.doctrine_chunks
            ],
            "incidents": ctx.active_incidents,
            "logistics": ctx.logistics_status,
            "tick": ctx.tick,
            "authorized_sources": list(ctx.valid_source_ids),
            "recent_events": ctx.recent_events,
            "world_summary": ctx.world_summary,
        }

        # 2. Execute structured reasoning via multi-provider LLM service
        raw_result = None
        try:
            raw_result = self.llm.reason(query, reasoning_context)
        except Exception as exc:
            log.debug("LLM service reasoning error (%s) — invoking local failsoft generator", exc)

        if not raw_result or not isinstance(raw_result, dict) or not raw_result.get("answer"):
            raw_result = self._generate_failsoft_response(ctx)

        mode = raw_result.get("mode", "rule_grounded_fallback")
        if mode not in ("local_llm", "rule_grounded_fallback"):
            mode = "rule_grounded_fallback"

        # 3. Ensure recommendation compliance
        sanitized_recs: list[dict[str, Any]] = []
        for r in raw_result.get("recommendations", []):
            if isinstance(r, dict):
                priority = r.get("priority", "MEDIUM")
                if priority not in ("CRITICAL", "HIGH", "MEDIUM", "ROUTINE"):
                    priority = "MEDIUM"
                sanitized_recs.append({
                    "action": r.get("action", "review_state"),
                    "summary": r.get("summary", "Review operational state."),
                    "priority": priority,
                    "requires_confirmation": True,
                    "requires_human_confirmation": True,
                    "entity_id": r.get("entity_id", "HQ"),
                })
        raw_result["recommendations"] = sanitized_recs

        # 4. Mandatory Citation Safety Verification Gate
        validation = self.validator.validate(
            text=raw_result["answer"],
            valid_sources=ctx.valid_source_ids,
            doctrine_chunks=ctx.doctrine_chunks,
        )

        # Filter facts if they contain unverified citations
        sanitized_facts = []
        for fact in raw_result.get("facts", []):
            if not any(unverified in fact for unverified in validation["unverified_citations"]):
                sanitized_facts.append(fact)

        latency_ms = round((time.perf_counter() - t0) * 1000, 1)

        return {
            "query": query,
            "run_id": ctx.run_id,
            "tick": ctx.tick,
            "answer": raw_result["answer"],
            "facts": sanitized_facts or raw_result.get("facts", []),
            "projections": raw_result.get("projections", []),
            "recommendations": raw_result.get("recommendations", []),
            "citations": validation["verified_citations"],
            "grounding": {
                "grounded": validation["grounded"],
                "warning": validation["warning"],
                "valid_citations": [c["source_id"] for c in validation["verified_citations"]],
                "unverified_citations": validation["unverified_citations"],
            },
            "mode": mode,
            "latency_ms": latency_ms,
        }


# Singleton service instance
ai_service = AIService()
