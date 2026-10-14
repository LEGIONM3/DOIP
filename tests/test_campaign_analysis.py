"""Phase 4H Test Suite: Global Replay & Campaign Intelligence Analysis.

Invariants:
- Multi-theater campaign comparative analysis.
- Extraction of strategic lessons learned, systemic weaknesses, and resource bottlenecks.
- KPI performance deltas (completion rate, fuel efficiency, incident reduction).
- Persisted to database replay reports.
"""

from pathlib import Path
import pytest
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.campaign_replay import CampaignReplayEngine, campaign_replay_engine
from app import db


def test_campaign_replay_engine_comparative_analysis():
    """Verify engine compares two campaigns, calculating KPI deltas and lessons learned."""
    engine = CampaignReplayEngine()
    cmp_res = engine.compare_campaigns(
        campaign_id_a="CMP-EXERCISE-2025",
        campaign_id_b="CMP-EXERCISE-2026",
    )

    assert cmp_res["comparison_id"].startswith("CMP-CMP-")
    assert cmp_res["campaign_a"]["id"] == "CMP-EXERCISE-2025"
    assert cmp_res["campaign_b"]["id"] == "CMP-EXERCISE-2026"

    # KPI deltas
    deltas = cmp_res["kpi_deltas"]
    assert "mission_completion_rate_delta_pct" in deltas
    assert "fuel_consumption_delta_liters" in deltas
    assert "incident_reduction_pct" in deltas

    # Strategic insights
    assert len(cmp_res["strategic_lessons_learned"]) >= 2
    assert len(cmp_res["systemic_weaknesses"]) >= 1
    assert len(cmp_res["resource_bottlenecks"]) >= 1
    assert len(cmp_res["executive_summary"]) > 0

    # Bottleneck format
    first_bottleneck = cmp_res["resource_bottlenecks"][0]
    assert "asset" in first_bottleneck
    assert "severity" in first_bottleneck
    assert "detail" in first_bottleneck

    # Verify persistence
    report = db.get_replay_report(cmp_res["comparison_id"])
    assert report is not None
    assert report["run_id"] == "CMP-EXERCISE-2025"
    assert report["comparison_run_id"] == "CMP-EXERCISE-2026"


def test_campaign_compare_rest_api_endpoint():
    """Verify FastAPI endpoint for comparative campaign intelligence."""
    client = TestClient(app)
    req = {
        "campaign_id_a": "CMP-EXERCISE-2025",
        "campaign_id_b": "CMP-EXERCISE-2026",
    }
    res = client.post("/api/campaigns/compare", json=req)
    assert res.status_code == 200
    data = res.json()

    assert data["comparison_id"].startswith("CMP-CMP-")
    assert "kpi_deltas" in data
    assert "strategic_lessons_learned" in data
    assert "resource_bottlenecks" in data
    assert "executive_summary" in data
