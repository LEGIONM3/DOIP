"""Phase 4D Test Suite: Strategic Copilot.

Invariants:
- Multi-theater strategic campaign planning and lifecycle.
- Four core strategic deliverables:
  1. Campaign Brief (LLM synthesized directive)
  2. Strategic Readiness Report (Cross-theater posture)
  3. Strategic Risk Assessment (Distributed forecast & cascade models)
  4. Strategic Investment Outlook (Capital allocation & ROI)
- STRICT AI SAFETY INVARIANT: All campaign briefs, operations, and allocations
  strictly enforce requires_human_confirmation=True and remain staged until approved.
"""

from pathlib import Path
import pytest
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.strategic_copilot import StrategicCopilot, strategic_copilot
from app import db


def test_strategic_copilot_campaign_creation_and_lifecycle():
    """Verify strategic campaigns are authored in draft mode and stored in database."""
    copilot = StrategicCopilot()
    campaign = copilot.create_campaign(
        title="Operation Sovereign Bastion",
        theater_ids=["THEATER-NORTH", "THEATER-EAST"],
        objectives=["Establish joint radar coverage", "Secure maritime logistics corridors"],
    )

    cid = campaign["id"]
    assert cid.startswith("CMP-")
    assert campaign["title"] == "Operation Sovereign Bastion"
    assert campaign["status"] == "draft"
    assert len(campaign["theater_ids"]) == 2

    persisted = db.get_campaign(cid)
    assert persisted is not None
    assert persisted["title"] == "Operation Sovereign Bastion"


def test_strategic_campaign_brief_and_human_gate_invariant():
    """Verify campaign brief synthesis generates staged brief requiring human approval."""
    copilot = StrategicCopilot()
    campaign = copilot.create_campaign(
        title="Operation Iron Sentinel",
        theater_ids=["THEATER-NORTH"],
        objectives=["Neutralize simulated border electronic jamming"],
    )
    cid = campaign["id"]

    brief = copilot.generate_campaign_brief(cid)
    assert brief["campaign_id"] == cid
    assert len(brief["brief_text"]) > 0
    # STRICT SAFETY INVARIANT: Campaign brief is staged and requires human confirmation
    assert brief["status"] == "staged_for_approval"
    assert brief["requires_human_confirmation"] is True


def test_strategic_readiness_and_risk_reports():
    """Verify readiness, risk assessments, and investment outlook generation."""
    copilot = StrategicCopilot()
    cid = "CMP-EXERCISE-2026"

    # 1. Readiness Report
    readiness = copilot.generate_strategic_readiness_report(cid)
    assert readiness["campaign_id"] == cid
    assert 0.0 <= readiness["readiness_score"] <= 100.0
    assert readiness["active_theaters"] >= 1
    assert readiness["sustainment_posture"] in ["SUFFICIENT", "CONSTRAINED"]

    # 2. Risk Assessment
    risks = copilot.generate_strategic_risk_assessment(cid)
    assert risks["campaign_id"] == cid
    assert risks["composite_risk_level"] in ["LOW", "MODERATE", "ELEVATED", "HIGH", "CRITICAL"]
    assert "cascading_failures" in risks

    # 3. Investment Outlook
    investments = copilot.generate_investment_outlook(cid)
    assert investments["campaign_id"] == cid
    assert len(investments["recommended_investments"]) >= 1
    assert investments["requires_human_confirmation"] is True
    for inv in investments["recommended_investments"]:
        assert "domain" in inv
        assert "roi_score" in inv


def test_strategic_copilot_rest_api_endpoints():
    """Verify FastAPI endpoints for strategic copilot operations."""
    client = TestClient(app)

    # 1. Create campaign
    create_req = {
        "title": "Operation REST Validation",
        "theater_ids": ["THEATER-NORTH", "THEATER-LITTORAL"],
        "objectives": ["Coordinate littoral surveillance"],
    }
    res_c = client.post("/api/strategic/campaigns", json=create_req)
    assert res_c.status_code == 200
    camp = res_c.json()
    cid = camp["id"]
    assert camp["status"] == "draft"

    # 2. List campaigns
    res_list = client.get("/api/strategic/campaigns")
    assert res_list.status_code == 200
    assert any(c["id"] == cid for c in res_list.json())

    # 3. Campaign Brief
    res_brief = client.post(f"/api/strategic/campaigns/{cid}/brief")
    assert res_brief.status_code == 200
    brief_data = res_brief.json()
    assert brief_data["requires_human_confirmation"] is True
    assert brief_data["status"] == "staged_for_approval"

    # 4. Readiness Report
    res_ready = client.get(f"/api/strategic/campaigns/{cid}/readiness")
    assert res_ready.status_code == 200
    assert "readiness_score" in res_ready.json()

    # 5. Risks Report
    res_risk = client.get(f"/api/strategic/campaigns/{cid}/risks")
    assert res_risk.status_code == 200
    assert "composite_risk_level" in res_risk.json()

    # 6. Investment Outlook
    res_inv = client.get(f"/api/strategic/campaigns/{cid}/investments")
    assert res_inv.status_code == 200
    assert "recommended_investments" in res_inv.json()
