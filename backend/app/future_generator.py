"""Autonomous Simulation Future Generator for DOIP (Phase 4G).

Enables massive-scale Monte Carlo lookahead by generating deterministic alternative futures:
- Generates 10, 100, or 1000 futures from a baseline simulation world.
- Evaluates outcomes, categorizing into risk bands: P10 (Optimistic), P50 (Median), P90 (Conservative), WORST.
- Ranks alternative trajectories and outcomes to identify optimal decisions and hazard boundaries.

STRICT INVARIANT:
Deterministic branching: Each future branch uses a strictly reproducible PRNG seed.
Live simulation state remains completely immutable.
"""

from __future__ import annotations

import copy
import datetime
import logging
import random
import uuid
from typing import Any

try:
    from . import db
    from .engine import SimEngine
    from .multiworld import world_manager
except ImportError:
    from app import db
    from app.engine import SimEngine
    from app.multiworld import world_manager

log = logging.getLogger(__name__)


class FutureGenerator:
    """Generates and analyzes deterministic alternative simulation futures."""

    def __init__(self) -> None:
        self.world_mgr = world_manager

    def generate_alternative_futures(
        self,
        baseline_world_id: str = "WLD-NORTH-01",
        count: int = 10,
        ticks: int = 120,
        conditions_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate N deterministic future branches and evaluate risk bands."""
        batch_id = f"FUT-BATCH-{uuid.uuid4().hex[:6].upper()}"
        world = self.world_mgr.get_world(baseline_world_id)
        if not world:
            snap = db.load_world_snapshot(baseline_world_id)
            if snap:
                world = {
                    "id": baseline_world_id,
                    "theater_id": "THEATER-NORTH",
                    "tick": snap.get("tick", 0),
                    "scenario_id": snap.get("scenarioId", "SC-1"),
                    "state_snapshot": snap,
                }
            else:
                run_rec = db.get_run(baseline_world_id)
                if run_rec:
                    world = {
                        "id": baseline_world_id,
                        "theater_id": "THEATER-NORTH",
                        "tick": run_rec.get("ticks", 0),
                        "scenario_id": run_rec.get("scenarioId", "SC-1"),
                        "state_snapshot": {"seed": run_rec.get("seed", 20260101), "scenarioId": run_rec.get("scenarioId", "SC-1")},
                    }
                else:
                    world = {
                        "id": baseline_world_id,
                        "theater_id": "THEATER-NORTH",
                        "tick": 0,
                        "state_snapshot": {"seed": 20260101},
                    }

        base_seed = int(world.get("state_snapshot", {}).get("seed", 20260101))
        branches: list[dict[str, Any]] = []

        # Generate N deterministic branches grounded in authoritative simulation execution
        scenario_id = world.get("scenario_id") or world.get("state_snapshot", {}).get("scenarioId", "SC-1")
        for i in range(1, count + 1):
            branch_seed = (base_seed + (i * 7919)) % 2147483647

            # Forward lookahead simulation using the authoritative SimEngine
            eng = SimEngine()
            eng.start(branch_seed, scenario_id)

            # Calibrate from snapshot if available
            snap = world.get("state_snapshot")
            if snap and isinstance(snap, dict):
                if "units" in snap and isinstance(snap["units"], dict):
                    for u in eng._units:
                        if u.id in snap["units"]:
                            su = snap["units"][u.id]
                            if "fuel" in su:
                                u.fuel = su["fuel"]
                            if "battery" in su:
                                u.battery = su["battery"]
                if "personnel" in snap and isinstance(snap["personnel"], dict):
                    for p in eng._personnel:
                        if p.id in snap["personnel"]:
                            sp = snap["personnel"][p.id]
                            if "fatigue" in sp:
                                p.fatigue = sp["fatigue"]
                            if "heartRate" in sp:
                                p.heartRate = sp["heartRate"]

            # Apply explicit operational condition overrides if specified
            if conditions_override:
                if "fuel_level" in conditions_override:
                    target_fuel = float(conditions_override["fuel_level"])
                    for u in eng._units:
                        u.fuel = target_fuel
                if "fatigue_level" in conditions_override:
                    target_fatigue = float(conditions_override["fatigue_level"])
                    for p in eng._personnel:
                        p.fatigue = target_fatigue
                if "battery_level" in conditions_override:
                    target_battery = float(conditions_override["battery_level"])
                    for u in eng._units:
                        u.battery = target_battery

            initial_fuel = sum(u.fuel for u in eng._units)
            branch_events = []
            for _ in range(ticks):
                branch_events.extend(eng.step())

            final_fuel = sum(u.fuel for u in eng._units)
            fuel_delta = round(final_fuel - initial_fuel, 1)

            incidents_encountered = sum(1 for e in branch_events if e.type == "incident_open")
            crit_alerts = sum(1 for e in branch_events if e.type == "alert_raise" and e.severity == "critical")
            resource_stress = sum(1 for e in branch_events if e.type == "resource_level" and e.severity == "high")
            stale_units = sum(1 for u in eng._units if u.status == "stale")
            weather_hits = sum(1 for e in branch_events if e.type == "unit_move" and e.payload.get("inWeather"))
            fatigued_vitals = sum(1 for e in branch_events if e.type == "vitals" and e.payload.get("fatigue", 0) > 0.8)

            # Explicit outcome rule grounded in actual simulated telemetry
            avg_fuel = final_fuel / max(1, len(eng._units))
            mission_success = bool(
                crit_alerts <= 1
                and stale_units == 0
                and avg_fuel >= 20.0
                and fatigued_vitals <= 3
            )

            # Score calculated strictly from simulated evidence
            score = (
                80.0
                + (avg_fuel * 0.2)
                - (incidents_encountered * 10.0)
                - (crit_alerts * 8.0)
                - (resource_stress * 1.5)
                - (weather_hits * 0.5)
                - (fatigued_vitals * 2.5)
            )
            if not mission_success:
                score -= 25.0
            score = max(5.0, min(100.0, round(score, 1)))

            explanation = (
                f"Simulated {ticks} ticks with {incidents_encountered} incidents, {crit_alerts} critical alerts, "
                f"{weather_hits} weather encounters. Remaining fuel {final_fuel:.1f}L ({fuel_delta:+.1f}L delta). "
                f"Mission outcome: {'SUCCESS' if mission_success else 'COMPROMISED'}."
            )

            branches.append({
                "branch_id": f"FUT-{batch_id}-{i:03d}",
                "branch_seed": branch_seed,
                "ticks": ticks,
                "score": score,
                "mission_success": mission_success,
                "fuel_delta_liters": fuel_delta,
                "incidents_count": incidents_encountered,
                "critical_alerts_count": crit_alerts,
                "provenance": {
                    "snapshot_id": baseline_world_id,
                    "seed": branch_seed,
                    "ticks": ticks,
                    "model": "SimEngine-Mulberry32-Authoritative",
                    "explanation": explanation,
                },
            })

        # Rank branches: 1 = Best outcome (highest score)
        branches.sort(key=lambda b: b["score"], reverse=True)
        for rank, b in enumerate(branches, 1):
            b["outcome_rank"] = rank

            # Assign risk band based on percentile rank
            percentile = (rank / count) * 100.0
            if rank == count:
                band = "WORST"
            elif percentile <= 20.0:
                band = "P10"
            elif percentile <= 70.0:
                band = "P50"
            else:
                band = "P90"
            b["risk_band"] = band

            # Persist to database
            db.save_future_branch({
                "id": b["branch_id"],
                "baseline_world_id": baseline_world_id,
                "branch_seed": b["branch_seed"],
                "ticks": ticks,
                "outcome_rank": rank,
                "outcome": b,
                "risk_band": band,
            })

        # Aggregate risk bands
        p10_branch = branches[0]
        p50_branch = branches[count // 2]
        p90_branch = branches[min(count - 1, int(count * 0.9))]
        worst_branch = branches[-1]

        return {
            "batch_id": batch_id,
            "baseline_world_id": baseline_world_id,
            "branches_count": count,
            "ticks": ticks,
            "risk_bands": {
                "P10_optimistic": {
                    "score": p10_branch["score"],
                    "branch_id": p10_branch["branch_id"],
                    "incidents": p10_branch["incidents_count"],
                },
                "P50_median": {
                    "score": p50_branch["score"],
                    "branch_id": p50_branch["branch_id"],
                    "incidents": p50_branch["incidents_count"],
                },
                "P90_conservative": {
                    "score": p90_branch["score"],
                    "branch_id": p90_branch["branch_id"],
                    "incidents": p90_branch["incidents_count"],
                },
                "WORST_case": {
                    "score": worst_branch["score"],
                    "branch_id": worst_branch["branch_id"],
                    "incidents": worst_branch["incidents_count"],
                },
            },
            "top_branches": branches[:5],
            "worst_branch": worst_branch,
            "summary": (
                f"Generated {count} deterministic future branches for world '{baseline_world_id}'. "
                f"Median score (P50): {p50_branch['score']}/100. Best outcome: {p10_branch['branch_id']} "
                f"(Rank 1, Score {p10_branch['score']}). Worst outcome score: {worst_branch['score']}."
            ),
        }


# Singleton
future_generator = FutureGenerator()
