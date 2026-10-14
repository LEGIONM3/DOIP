"""Phase 4C Test Suite: Autonomous Agent Swarm Infrastructure.

Invariants:
- 6 specialized planning agents: Commander, Logistics, Threat, Weather, Mission, Optimization.
- Swarm consensus aggregation and LLM executive brief synthesis.
- STRICT AI SAFETY INVARIANT: The swarm proposes; humans approve. Operational plans
  are generated in 'proposed' status with requires_human_confirmation=True.
- Full persistence into copilot sessions for operator review and audit.
"""

from pathlib import Path
import pytest
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.swarm import (
    CommanderAgent,
    LogisticsAgent,
    ThreatAgent,
    WeatherAgent,
    MissionAgent,
    OptimizationAgent,
    AgentSwarmCoordinator,
    swarm_coordinator,
)
from app import db


def test_individual_swarm_agents_functionality():
    """Verify each of the 6 specialized agents produces structured domain analysis."""
    # 1. Commander
    cmd = CommanderAgent()
    c_out = cmd.synthesize_intent("Establish forward screen", "THEATER-NORTH")
    assert c_out["role"] == "COMMANDER"
    assert c_out["theater_id"] == "THEATER-NORTH"
    assert "strategic_intent" in c_out

    # 2. Logistics
    logistics = LogisticsAgent()
    l_out = logistics.evaluate_sustainment("THEATER-NORTH")
    assert l_out["role"] == "LOGISTICS"
    assert l_out["fuel_budget_liters"] > 0
    assert l_out["pnr_margin_pct"] >= 20.0

    # 3. Threat
    threat = ThreatAgent()
    t_out = threat.assess_hostiles("THEATER-NORTH")
    assert t_out["role"] == "THREAT"
    assert isinstance(t_out["active_threat_sectors"], list)
    assert "ew_jamming_risk" in t_out

    # 4. Weather
    weather = WeatherAgent()
    w_out = weather.evaluate_environment("THEATER-NORTH")
    assert w_out["role"] == "WEATHER"
    assert w_out["visibility_km"] > 0
    assert w_out["cloud_ceiling_m"] > 0

    # 5. Mission
    mission = MissionAgent()
    m_tasks = mission.plan_tactical_tasks("Secure supply line", "THEATER-NORTH")
    assert isinstance(m_tasks, list)
    assert len(m_tasks) >= 2
    for t in m_tasks:
        assert "task_id" in t
        assert "assigned_units" in t

    # 6. Optimization
    opt = OptimizationAgent()
    o_out = opt.optimize_pareto_weights()
    assert o_out["role"] == "OPTIMIZATION"
    assert 0.0 <= o_out["pareto_optimality_score"] <= 1.0


def test_swarm_coordinator_generates_plan_with_human_gate():
    """Verify swarm synthesizes complete operational plan and enforces human gate."""
    coordinator = AgentSwarmCoordinator()
    plan = coordinator.generate_operational_plan(
        prompt="Execute high-altitude reconnaissance along northern ridgeline",
        theater_id="THEATER-NORTH",
    )

    assert plan["plan_id"].startswith("SWARM-PLAN-")
    assert plan["theater_id"] == "THEATER-NORTH"

    # STRICT INVARIANT: Must be proposed status requiring human confirmation
    assert plan["status"] == "proposed"
    assert plan["requires_human_confirmation"] is True

    # Consensus checks
    consensus = plan["swarm_consensus"]
    assert consensus["commander"]["role"] == "COMMANDER"
    assert consensus["logistics"]["role"] == "LOGISTICS"
    assert consensus["threat"]["role"] == "THREAT"
    assert consensus["weather"]["role"] == "WEATHER"
    assert consensus["optimization"]["role"] == "OPTIMIZATION"
    assert consensus["confidence_score"] > 0.7

    assert len(plan["tasks"]) >= 2
    assert len(plan["executive_brief"]) > 0

    # Verify persisted in copilot sessions
    session = db.get_copilot_session(plan["plan_id"])
    assert session is not None
    assert len(session["proposals"]) > 0
    assert session["proposals"][0]["requires_human_confirmation"] is True
    assert session["status"] == "active"


def test_swarm_plan_rest_endpoint():
    """Verify FastAPI endpoint for swarm operational plan generation."""
    client = TestClient(app)
    req = {
        "prompt": "Intercept detected hostile reconnaissance drone",
        "theater_id": "THEATER-EAST",
    }
    res = client.post("/api/swarm/plan", json=req)
    assert res.status_code == 200
    plan = res.json()

    assert plan["plan_id"].startswith("SWARM-PLAN-")
    assert plan["theater_id"] == "THEATER-EAST"
    assert plan["status"] == "proposed"
    assert plan["requires_human_confirmation"] is True
    assert "swarm_consensus" in plan
    assert "tasks" in plan
