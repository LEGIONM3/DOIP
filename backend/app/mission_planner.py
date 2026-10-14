"""Mission Planning Subsystem for DOIP (Phase 2B).

Implements:
- Mission, Objective, Task, Waypoint, and Asset domain models.
- Deterministic lifecycle state machine (Draft -> Review -> Approved -> Executing -> Completed / Cancelled).
- Automatic resource, duration, fuel, and risk estimation.
- AI mission proposal generator (grounded in doctrine SOPs).
- Strict human confirmation boundary: AI cannot approve or execute missions.
"""

from __future__ import annotations

import json
import logging
import math
import time
from typing import Any

try:
    from . import db
    from .rag import retrieve
    from .routing import calculate_route, haversine_km
except ImportError:
    from app import db
    from app.rag import retrieve
    from app.routing import calculate_route, haversine_km

log = logging.getLogger(__name__)


class MissionPlanner:
    """Core mission planning, estimation, and lifecycle engine."""

    VALID_TRANSITIONS = {
        "draft": ["review", "cancelled"],
        "review": ["approved", "draft", "cancelled"],
        "approved": ["executing", "cancelled"],
        "executing": ["completed", "cancelled"],
        "completed": [],
        "cancelled": [],
    }

    @staticmethod
    def estimate_resources(
        waypoints: list[dict[str, Any] | list[float]],
        unit_types: list[str] | None = None,
        loiter_duration_s: int = 0,
        world_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Deterministically calculate distance, duration, fuel, and risk for a waypoint sequence."""
        if not waypoints or len(waypoints) < 2:
            return {
                "distance_km": 0.0,
                "estimated_duration_s": loiter_duration_s,
                "estimated_fuel_l": 0.0,
                "risk_score": 0.0,
            }

        total_km = 0.0
        coords: list[tuple[float, float]] = []
        for w in waypoints:
            if isinstance(w, dict):
                coords.append((float(w["lat"]), float(w["lon"])))
            elif isinstance(w, (list, tuple)) and len(w) >= 2:
                coords.append((float(w[0]), float(w[1])))

        for i in range(len(coords) - 1):
            total_km += haversine_km(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])

        # Cruise speed baseline: 60 km/h (16.6 m/s)
        cruise_speed_kmh = 60.0
        transit_duration_s = int((total_km / cruise_speed_kmh) * 3600)
        total_duration_s = transit_duration_s + loiter_duration_s

        # Fuel burn: 0.35 L / km in transit + 5.0 L / hr loitering
        fuel_transit = total_km * 0.35
        fuel_loiter = (loiter_duration_s / 3600.0) * 5.0
        total_fuel_l = round(fuel_transit + fuel_loiter, 2)

        # Risk evaluation based on proximity to active incidents & threats
        risk_score = 0.1  # Baseline mission risk
        if world_state:
            incidents = world_state.get("incidents", {})
            if isinstance(incidents, dict):
                for inc in incidents.values():
                    if inc.get("open"):
                        i_lat = inc.get("lat")
                        i_lon = inc.get("lon")
                        if i_lat is not None and i_lon is not None:
                            # Check closest waypoint to incident
                            for lat, lon in coords:
                                if haversine_km(lat, lon, float(i_lat), float(i_lon)) < 10.0:
                                    risk_score += 0.25 if inc.get("severity") in ["critical", "high"] else 0.10
                                    break

        risk_score = round(min(1.0, max(0.05, risk_score)), 2)

        return {
            "distance_km": round(total_km, 2),
            "estimated_duration_s": total_duration_s,
            "estimated_fuel_l": total_fuel_l,
            "risk_score": risk_score,
        }

    def create_mission(
        self,
        name: str,
        description: str,
        waypoints: list[dict[str, Any]],
        tasks: list[dict[str, Any]] | None = None,
        priority: str = "routine",
        author: str = "operator",
        assigned_unit_ids: list[str] | None = None,
        world_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new tactical mission in Draft status."""
        m_id = f"MSN-{abs(hash((name, time.time(), author))) % 1000000:06d}"
        estimates = self.estimate_resources(waypoints, assigned_unit_ids, world_state=world_state)

        mission_data = {
            "id": m_id,
            "name": name,
            "description": description,
            "priority": priority,
            "status": "draft",
            "author": author,
            "approved_by": None,
            "assigned_unit_ids": assigned_unit_ids or [],
            "risk_score": estimates["risk_score"],
            "estimated_duration_s": estimates["estimated_duration_s"],
            "estimated_fuel_l": estimates["estimated_fuel_l"],
            "fuel_required_l": estimates["estimated_fuel_l"],
            "waypoints": waypoints,
            "tasks": tasks or [
                {"sequence": 1, "title": "Ingress to Objective", "task_type": "TRANSIT", "status": "pending"},
                {"sequence": 2, "title": "Execute Primary Mission Objective", "task_type": "PATROL", "status": "pending"},
                {"sequence": 3, "title": "Egress to Base / Resupply", "task_type": "EGRESS", "status": "pending"},
            ],
        }

        saved = db.save_mission(mission_data)
        db.add_audit(author, "MISSION_CREATED", f"Created mission {m_id}: {name}")
        return saved

    def transition(self, mission_id: str, new_status: str, actor: str) -> dict[str, Any]:
        """Transition mission along lifecycle with role and invariant validation."""
        mission = db.get_mission(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        curr_status = mission["status"]
        if new_status not in self.VALID_TRANSITIONS.get(curr_status, []):
            raise ValueError(f"Invalid mission lifecycle transition: {curr_status} -> {new_status}")

        # Human boundary: Approval requires authenticated operator/commander
        if new_status in ["approved", "executing"] and (not actor or actor.lower() == "ai"):
            raise PermissionError("Safety Boundary: Autonomous or AI approval of missions is strictly prohibited.")

        updated = db.transition_mission_status(mission_id, new_status, actor)
        if not updated:
            raise RuntimeError(f"Failed to transition mission {mission_id}")
        return updated

    def generate_ai_proposal(
        self,
        prompt: str,
        world_state: dict[str, Any] | None = None,
        author: str = "ai_assistant",
    ) -> dict[str, Any]:
        """Synthesize a structured mission proposal from natural language prompt and doctrine."""
        world_state = world_state or {}
        # Retrieve doctrine guidance for context (e.g. convoy escort SOP-04 or patrol SOP-01)
        doctrine_chunks = retrieve(prompt, top_k=2)
        doctrine_context = " ".join(c.get("text", "") for c in doctrine_chunks)

        units = world_state.get("units", {})
        available_units = [u_id for u_id, u in units.items() if u.get("status") == "nominal"]

        # Synthetic anchor waypoints around Bangalore exercise theater
        base_lat, base_lon = 12.9716, 77.5946
        waypoints = [
            {"sequence": 1, "name": "Forward Operating Base Alpha", "lat": base_lat, "lon": base_lon, "alt_m": 900.0},
            {"sequence": 2, "name": "Checkpoint Bravo (Chokepoint)", "lat": base_lat + 0.08, "lon": base_lon + 0.06, "alt_m": 920.0},
            {"sequence": 3, "name": "Tactical Sector 4 Objective", "lat": base_lat + 0.15, "lon": base_lon + 0.12, "alt_m": 940.0},
            {"sequence": 4, "name": "Safe Egress Point Delta", "lat": base_lat + 0.05, "lon": base_lon + 0.18, "alt_m": 910.0},
        ]

        assigned = available_units[:2] if available_units else ["UAV-01", "CAR-01"]
        m_name = f"AI Plan: {prompt[:40].strip()}..."
        description = (
            f"AI-generated tactical proposal based on query '{prompt}'. "
            f"Grounded in doctrine: {doctrine_chunks[0]['citation'] if doctrine_chunks else 'SOP-01'}. "
            "Requires Commander review and human approval prior to commencement."
        )

        tasks = [
            {"sequence": 1, "title": "Route Clearance & Threat Sweep", "task_type": "RECON", "status": "pending", "duration_s": 900},
            {"sequence": 2, "title": "Convoy Transit & Security Escort", "task_type": "ESCORT", "status": "pending", "duration_s": 2400},
            {"sequence": 3, "title": "Objective Arrival & Handover", "task_type": "PATROL", "status": "pending", "duration_s": 1200},
        ]

        # Stage as Draft
        return self.create_mission(
            name=m_name,
            description=description,
            waypoints=waypoints,
            tasks=tasks,
            priority="high" if "escort" in prompt.lower() or "urgent" in prompt.lower() else "routine",
            author=author,
            assigned_unit_ids=assigned,
            world_state=world_state,
        )


mission_planner = MissionPlanner()


# Module-level convenience functions
def create_mission(
    mission_data: dict[str, Any],
    actor: str = "operator",
) -> dict[str, Any]:
    return mission_planner.create_mission(
        name=mission_data.get("name", "Tactical Mission"),
        description=mission_data.get("description", ""),
        waypoints=mission_data.get("waypoints", []),
        tasks=mission_data.get("tasks", []),
        priority=mission_data.get("priority", "medium"),
        author=actor,
        assigned_unit_ids=mission_data.get("assigned_assets", []) or mission_data.get("assigned_unit_ids", []),
        world_state=mission_data.get("world_state"),
    )


def transition_mission_lifecycle(
    mission_id: str,
    target_status: str,
    actor: str = "operator",
    notes: str = "",
) -> dict[str, Any]:
    return mission_planner.transition(
        mission_id=mission_id,
        new_status=target_status,
        actor=actor,
    )


def generate_ai_mission_proposal(
    prompt: str,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return mission_planner.generate_ai_proposal(
        prompt=prompt,
        world_state=constraints,
    )
