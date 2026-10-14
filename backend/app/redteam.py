"""Red Team Adversarial Planner Engine (Phase 2E).

Synthesizes adversarial stress tests and operational injects against planned missions.
Safety Invariants:
1. ZERO DIRECT MUTATION: Red team cannot directly mutate live simulation state.
2. PROPOSAL ONLY: Injects are staged and require explicit human-in-the-loop approval.
3. STRICT DSL WHITELIST: All injects must validate against dsl_parser.WHITELISTED_ACTIONS.
"""

from __future__ import annotations

import datetime
import math
import uuid
from typing import Any

from app.db import (
    add_audit,
    get_mission,
    get_redteam_scenario,
    list_redteam_scenarios,
    save_redteam_scenario,
    update_redteam_inject_status,
)
from app.dsl_parser import DSLValidationError, WHITELISTED_ACTIONS, validate_scenario_dict
from app.time_utils import utc_iso


def analyze_vulnerabilities(
    mission_data: dict[str, Any] | None = None,
    route_data: dict[str, Any] | None = None,
    world_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Analyze mission parameters, route geometry, and assets to detect tactical vulnerabilities."""
    vulnerabilities: list[dict[str, Any]] = []

    mission = mission_data or {}
    waypoints = route_data.get("waypoints", []) if route_data else []
    assets = mission.get("assigned_assets", []) or mission.get("assets", [])

    # 1. Chokepoint & Route exposure
    if len(waypoints) >= 4:
        # Mid-route is typically the most vulnerable point
        mid_idx = len(waypoints) // 2
        mid_pt = waypoints[mid_idx]
        vulnerabilities.append({
            "id": f"VULN-ROUTE-{uuid.uuid4().hex[:6].upper()}",
            "type": "ROUTE_CHOKEPOINT",
            "severity": "HIGH",
            "title": "Corridor Chokepoint Exposure",
            "description": f"Mid-route sector at ({mid_pt[0]:.4f}, {mid_pt[1]:.4f}) forces low maneuverability through narrow passage.",
            "location": {"lat": mid_pt[0], "lon": mid_pt[1]},
            "recommended_inject": "create_incident",
        })

    # 2. Asset composition vulnerabilities
    has_uav = any("uav" in str(a).lower() or "drone" in str(a).lower() for a in assets)
    if not has_uav:
        vulnerabilities.append({
            "id": f"VULN-ISR-{uuid.uuid4().hex[:6].upper()}",
            "type": "ISR_BLIND_SPOT",
            "severity": "MEDIUM",
            "title": "Absence of Aerial Reconnaissance",
            "description": "Formation lacks organic UAV or aerial sensor coverage, exposing flanking routes to unmonitored hazards.",
            "location": None,
            "recommended_inject": "spawn_weather",
        })

    # 3. Solo or light asset vulnerability
    if len(assets) == 1:
        vulnerabilities.append({
            "id": f"VULN-ESCORT-{uuid.uuid4().hex[:6].upper()}",
            "type": "NO_ESCORT",
            "severity": "HIGH",
            "title": "Single Unit Convoy Vulnerability",
            "description": "Unit deployed without security escort or secondary backup element.",
            "location": None,
            "recommended_inject": "modify_speed",
        })

    # 4. Environmental vulnerability
    weather = (world_state or {}).get("weather", "CLEAR").upper()
    if weather in ("STORM", "RAIN", "FOG") or (route_data and route_data.get("risk_score", 0) > 40):
        vulnerabilities.append({
            "id": f"VULN-ENV-{uuid.uuid4().hex[:6].upper()}",
            "type": "ADVERSE_WEATHER_CORRIDOR",
            "severity": "HIGH",
            "title": "Severe Environmental Impedance",
            "description": f"Atmospheric turbulence ({weather}) or high terrain threat score degrades communications and fuel burn rates.",
            "location": None,
            "recommended_inject": "spawn_weather",
        })

    # Fallback vulnerability if none triggered
    if not vulnerabilities:
        vulnerabilities.append({
            "id": f"VULN-DEF-{uuid.uuid4().hex[:6].upper()}",
            "type": "PERIMETER_SURVEILLANCE",
            "severity": "MEDIUM",
            "title": "Perimeter Patrol Vulnerability",
            "description": "Standard patrol pattern is predictable and subject to timing exploitation.",
            "location": None,
            "recommended_inject": "unit_report",
        })

    return vulnerabilities


def validate_inject_against_dsl(inject: dict[str, Any]) -> tuple[bool, str]:
    """Validate a proposed inject against the DOIP Scenario DSL grammar and AGENTS.md whitelist."""
    action = inject.get("action")
    if not action:
        return False, "Proposed inject is missing 'action' field"
    
    if action not in WHITELISTED_ACTIONS:
        return False, f"Action '{action}' is forbidden. Must be one of {sorted(list(WHITELISTED_ACTIONS))}"

    params = inject.get("params", {})
    if not isinstance(params, dict):
        return False, "'params' must be a valid dictionary"

    # Construct test scenario dict to run full DSL validation
    dummy_scenario = {
        "name": "REDTEAM-VALIDATION-STUB",
        "seed": 1001,
        "duration_minutes": 120,
        "entities": [],
        "timeline": [
            {
                "tick": inject.get("trigger_tick", 10),
                "action": action,
                "params": params,
            }
        ],
        "rules": [],
    }

    try:
        validate_scenario_dict(dummy_scenario, source_name="redteam_validation")
        return True, "Valid DSL action"
    except DSLValidationError as e:
        return False, str(e)


def generate_adversarial_scenario(
    mission_id: str | None = None,
    mission_data: dict[str, Any] | None = None,
    route_data: dict[str, Any] | None = None,
    world_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Synthesize an adversarial stress-testing scenario for a mission.
    
    Adversarial injects are staged and strictly subject to human approval before execution.
    """
    if mission_id and not mission_data:
        mission_data = get_mission(mission_id)

    vulnerabilities = analyze_vulnerabilities(
        mission_data=mission_data,
        route_data=route_data,
        world_state=world_state,
    )

    scenario_id = f"RED-{uuid.uuid4().hex[:8].upper()}"
    proposed_injects: list[dict[str, Any]] = []

    # Map vulnerabilities to whitelisted DSL actions
    for idx, v in enumerate(vulnerabilities):
        action_type = v.get("recommended_inject", "create_incident")
        tick = (idx + 1) * 20

        if action_type == "create_incident":
            loc = v.get("location") or {"lat": 34.05, "lon": 71.55}
            params = {
                "incident_id": f"INC-RED-{uuid.uuid4().hex[:6].upper()}",
                "type": "simulated_hostile_ambush",
                "lat": loc["lat"],
                "lon": loc["lon"],
                "severity": v["severity"],
                "description": f"Simulated adversarial obstacle exploiting {v['title'].lower()}.",
            }
        elif action_type == "spawn_weather":
            params = {
                "type": "STORM",
                "intensity": 0.85,
                "duration_ticks": 45,
                "description": "Simulated sudden convective storm cell degrading visual sensor fidelity.",
            }
        elif action_type == "modify_speed":
            params = {
                "speed_multiplier": 0.45,
                "reason": "Simulated terrain mud/mechanical breakdown slowing column advance.",
            }
        else:
            params = {
                "report_type": "COMMS_INTERFERENCE",
                "channel": "TACTICAL_PRIMARY",
                "signal_loss_pct": 60,
                "description": "Simulated RF electronic warfare jamming.",
            }

        inj = {
            "id": f"INJ-{scenario_id}-{idx + 1:02d}",
            "scenario_id": scenario_id,
            "title": f"Adversarial Stress: {v['title']}",
            "action": action_type,
            "params": params,
            "trigger_tick": tick,
            "risk_rating": v["severity"],
            "vulnerability_targeted": v["id"],
            "vulnerability_description": v["description"],
            "status": "staged",  # Human approval required
            "approved_by": None,
            "created_at": utc_iso(),
        }

        # Verify against DSL
        valid, msg = validate_inject_against_dsl(inj)
        inj["dsl_valid"] = valid
        inj["dsl_validation_message"] = msg

        proposed_injects.append(inj)

    # Determine aggregate risk
    severities = [v["severity"] for v in vulnerabilities]
    if "CRITICAL" in severities:
        overall_risk = "CRITICAL"
    elif "HIGH" in severities:
        overall_risk = "HIGH"
    else:
        overall_risk = "MEDIUM"

    mission_title = (mission_data or {}).get("name", "Tactical Mission")
    scenario_doc = {
        "id": scenario_id,
        "mission_id": mission_id,
        "title": f"Red Team Stress: {mission_title}",
        "risk_rating": overall_risk,
        "vulnerability_summary": f"Identified {len(vulnerabilities)} tactical vulnerabilities across route geometry, unit escort, and environmental posture.",
        "injects": proposed_injects,
        "status": "staged",
        "approved_by": None,
        "created_at": utc_iso(),
    }

    # Persist in DB
    save_redteam_scenario(scenario_doc)
    add_audit("REDTEAM_ENGINEER", "REDTEAM_SCENARIO_GENERATED", f"Created staged adversarial scenario {scenario_id} for mission {mission_id or 'GENERAL'}")

    return scenario_doc


def approve_adversarial_inject(scenario_id: str, inject_id: str, approved_by: str) -> dict[str, Any]:
    """Approve a staged adversarial inject. Strictly requires a human operator or exercise coordinator."""
    if not approved_by or approved_by.strip().lower() in ("ai", "autonomous", "system", "redteam_agent"):
        raise PermissionError(f"Autonomous approval forbidden. Staged inject requires authorized human coordinator, got '{approved_by}'.")

    scenario = get_redteam_scenario(scenario_id)
    if not scenario:
        raise ValueError(f"Red Team Scenario '{scenario_id}' not found.")

    inject_target = None
    for inj in scenario.get("injects", []):
        if inj.get("id") == inject_id:
            inject_target = inj
            break

    if not inject_target:
        raise ValueError(f"Inject '{inject_id}' not found in scenario '{scenario_id}'.")

    # Safety validation
    valid, msg = validate_inject_against_dsl(inject_target)
    if not valid:
        raise ValueError(f"Cannot approve inject failing DSL whitelist: {msg}")

    # Mark approved in persistence
    success = update_redteam_inject_status(scenario_id, inject_id, "approved", approved_by=approved_by)
    if not success:
        raise RuntimeError("Failed to update inject status in persistence.")

    add_audit(
        actor=approved_by,
        action="REDTEAM_INJECT_APPROVED",
        detail=f"Approved inject {inject_id} ({inject_target['action']}) for scenario {scenario_id}",
    )

    return {
        "success": True,
        "scenario_id": scenario_id,
        "inject_id": inject_id,
        "status": "approved",
        "approved_by": approved_by,
        "approved_at": utc_iso(),
    }
