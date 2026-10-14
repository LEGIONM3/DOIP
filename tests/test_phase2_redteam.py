"""Phase 2E Test Suite: Red Team Adversarial Planner.

Invariants:
- Zero direct mutation of live simulation or state.
- Injects strictly staged as proposals requiring human coordinator approval.
- Strict mapping to whitelisted DOIP DSL actions:
  spawn_weather, create_incident, modify_speed, unit_report, raise_alert.
- Formal verification against dsl_parser.validate_scenario_dict.
- Autonomous approval without authorized human identity raises PermissionError.
"""

from pathlib import Path
import pytest
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.redteam import (
    analyze_vulnerabilities,
    generate_adversarial_scenario,
    validate_inject_against_dsl,
    approve_adversarial_inject,
)
from app.dsl_parser import WHITELISTED_ACTIONS


def test_redteam_vulnerability_analysis():
    """Identifies chokepoints and lack of escort/ISR coverage."""
    vulns = analyze_vulnerabilities(
        mission_data={"name": "Recon 1", "assigned_assets": ["HUMVEE-01"]},
        route_data={"waypoints": [[34.0, 71.0], [34.1, 71.1], [34.2, 71.2], [34.3, 71.3], [34.4, 71.4]]},
        world_state={"weather": "STORM"},
    )

    types = [v["type"] for v in vulns]
    assert "ROUTE_CHOKEPOINT" in types
    assert "NO_ESCORT" in types
    assert "ADVERSE_WEATHER_CORRIDOR" in types


def test_redteam_dsl_whitelist_validation():
    """Proposed injects validate against whitelist and reject invalid DSL actions."""
    # Whitelisted
    valid_inject = {
        "action": "create_incident",
        "params": {"type": "hostile_ambush", "lat": 34.05, "lon": 71.55, "severity": "HIGH"},
        "trigger_tick": 20,
    }
    is_valid, msg = validate_inject_against_dsl(valid_inject)
    assert is_valid is True

    # Non-whitelisted
    invalid_inject = {
        "action": "DESTROY_ENTITIES_ARBITRARY",
        "params": {},
    }
    is_invalid, msg_inv = validate_inject_against_dsl(invalid_inject)
    assert is_invalid is False
    assert "forbidden" in msg_inv.lower()


def test_redteam_adversarial_plan_generation_and_human_approval():
    """Adversarial plan stages injects and enforces human-in-the-loop approval."""
    sc = generate_adversarial_scenario(
        mission_id="MSN-MOCK-99",
        mission_data={"name": "Logistics Column", "assets": ["TRUCK-01"]},
        route_data={"waypoints": [[34.0, 71.0], [34.1, 71.1], [34.2, 71.2], [34.3, 71.3]]},
    )

    assert sc["status"] == "staged"
    assert len(sc["injects"]) > 0

    first_inj = sc["injects"][0]
    assert first_inj["status"] == "staged"
    assert first_inj["action"] in WHITELISTED_ACTIONS
    assert first_inj["dsl_valid"] is True

    # 1. Autonomous AI approval must fail
    with pytest.raises(PermissionError):
        approve_adversarial_inject(sc["id"], first_inj["id"], approved_by="ai")

    with pytest.raises(PermissionError):
        approve_adversarial_inject(sc["id"], first_inj["id"], approved_by="")

    # 2. Human approval succeeds
    approved = approve_adversarial_inject(sc["id"], first_inj["id"], approved_by="exercise_director_patel")
    assert approved["status"] == "approved"
    assert approved["approved_by"] == "exercise_director_patel"


def test_redteam_rest_endpoints():
    """FastAPI endpoints for red team planner validate injects and approval gate."""
    client = TestClient(app)

    # 1. Generate
    gen_resp = client.post("/api/redteam/generate", json={
        "mission_id": "MSN-SEC-01",
        "route_data": {"waypoints": [[34.0, 71.0], [34.1, 71.1], [34.2, 71.2], [34.3, 71.3]]},
    })
    assert gen_resp.status_code == 200
    sc_data = gen_resp.json()
    sc_id = sc_data["id"]
    inj_id = sc_data["injects"][0]["id"]

    # 2. Validate inject DSL
    val_resp = client.post("/api/redteam/validate-inject", json={
        "action": "spawn_weather",
        "params": {"type": "STORM", "intensity": 0.9},
    })
    assert val_resp.status_code == 200
    assert val_resp.json()["valid"] is True

    # 3. Approve inject
    appr_resp = client.post(f"/api/redteam/injects/{inj_id}/approve", json={
        "scenario_id": sc_id,
    })
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "approved"

    # 4. List scenarios
    list_resp = client.get("/api/redteam/scenarios")
    assert list_resp.status_code == 200
    assert any(s["id"] == sc_id for s in list_resp.json()["scenarios"])
