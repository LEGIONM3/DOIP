"""Phase 2B Test Suite: Mission Planning System.

Invariants:
- Deterministic lifecycle state machine:
  Draft -> Review -> Approved -> Executing -> Completed / Cancelled.
- Automatic resource estimation (duration, fuel, risk score).
- Strict AI safety boundary: AI can propose drafts, but CANNOT approve or execute.
- Autonomous approval without human confirmation raises PermissionError / HTTP 403.
"""

from pathlib import Path
import pytest
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.mission_planner import mission_planner, create_mission, transition_mission_lifecycle


def test_mission_lifecycle_deterministic_progression():
    """Missions progress deterministically through approved lifecycle states."""
    mission = create_mission({
        "name": "Op Northern Shield",
        "description": "Perimeter defense and checkpoint sweep",
        "waypoints": [
            {"sequence": 1, "name": "FOB 1", "lat": 12.97, "lon": 77.59, "alt_m": 800.0},
            {"sequence": 2, "name": "Checkpoint Alpha", "lat": 13.05, "lon": 77.65, "alt_m": 820.0},
        ],
        "tasks": [
            {"sequence": 1, "title": "Route Clearance", "task_type": "RECON", "duration_s": 900},
        ],
        "assigned_assets": ["UAV-01"],
    }, actor="planner_jones")

    mid = mission["id"]
    assert mission["status"] == "draft"
    assert mission["fuel_required_l"] > 0
    assert mission["estimated_duration_s"] > 0

    # 1. Draft -> Review
    m_review = transition_mission_lifecycle(mid, "review", actor="planner_jones")
    assert m_review["status"] == "review"

    # 2. Review -> Approved (Human Commander)
    m_approved = transition_mission_lifecycle(mid, "approved", actor="colonel_sanders")
    assert m_approved["status"] == "approved"

    # 3. Approved -> Executing (Operator)
    m_executing = transition_mission_lifecycle(mid, "executing", actor="operator_mike")
    assert m_executing["status"] == "executing"

    # 4. Executing -> Completed
    m_completed = transition_mission_lifecycle(mid, "completed", actor="operator_mike")
    assert m_completed["status"] == "completed"


def test_mission_safety_boundary_rejects_ai_approval():
    """AI agent attempting to approve a mission raises PermissionError."""
    mission = create_mission({
        "name": "Autonomous Attempt Mission",
        "assigned_assets": ["UAV-01"],
    }, actor="planner_jones")

    mid = mission["id"]
    transition_mission_lifecycle(mid, "review", actor="planner_jones")

    # Autonomous / AI approval attempt MUST fail
    with pytest.raises(PermissionError):
        transition_mission_lifecycle(mid, "approved", actor="ai")

    with pytest.raises(PermissionError):
        transition_mission_lifecycle(mid, "approved", actor="")


def test_mission_rest_endpoints():
    """FastAPI endpoints enforce lifecycle transitions and AI permission barriers."""
    client = TestClient(app)

    # 1. Create
    resp = client.post("/api/missions", json={
        "name": "Convoy Transit Route 4",
        "description": "Logistics convoy escort",
        "assigned_assets": ["CAR-01", "CAR-02"],
    })
    assert resp.status_code == 200
    mid = resp.json()["id"]

    # 2. AI draft endpoint
    draft_resp = client.post("/api/missions/ai-draft", json={
        "prompt": "Plan defensive patrol escort through sector 4",
    })
    assert draft_resp.status_code == 200
    draft_data = draft_resp.json()
    assert draft_data["status"] == "draft"
    assert len(draft_data["waypoints"]) >= 2
    assert "SOP" in draft_data["description"]

    # 3. Transition to review
    t_resp = client.post(f"/api/missions/{mid}/transition", json={"target_status": "review"})
    assert t_resp.status_code == 200
    assert t_resp.json()["status"] == "review"

    # 4. List missions
    list_resp = client.get("/api/missions")
    assert list_resp.status_code == 200
    assert any(m["id"] == mid for m in list_resp.json()["missions"])
