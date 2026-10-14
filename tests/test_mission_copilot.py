"""Test Suite for Multi-Agent Mission Copilot Engine (Phase 3E).

Verifies:
- Conversational chat flow and session persistence.
- Multi-perspective consensus package generation.
- Strict Human-in-the-Loop approval gate invariant (requires_human_confirmation=True).
- Human commander approval state transition.
"""

from __future__ import annotations

import pytest
from app import db
from app.copilot import copilot_service, MissionCopilot


@pytest.fixture(autouse=True)
def setup_db():
    db.init()


def test_copilot_singleton():
    """Verify singleton instance of MissionCopilot exists."""
    assert copilot_service is not None
    assert isinstance(copilot_service, MissionCopilot)


def test_copilot_chat():
    """Verify conversational chat stores messages and returns synthesized advice."""
    res = copilot_service.chat(
        session_id=None,
        message="Plan supply escort to North Depot along River Highway",
        user="Commander_Test",
    )

    assert "session_id" in res
    assert len(res["messages"]) >= 2
    assert res["messages"][0]["role"] == "user"
    assert res["messages"][1]["role"] == "assistant"
    assert res["session"]["status"] == "active"


def test_copilot_proposal_human_gate_invariant():
    """Strict Invariant: Copilot proposals are staged in 'proposed' status and REQUIRE human approval."""
    chat_res = copilot_service.chat(None, "Establish perimeter defense at forward post")
    session_id = chat_res["session_id"]

    prop_res = copilot_service.propose_mission_package(
        session_id=session_id,
        prompt="Forward post defense package",
    )

    proposal = prop_res["proposal"]
    assert proposal["status"] == "proposed"
    assert proposal["requires_human_confirmation"] is True, (
        "Violated Safety Invariant: proposal must require human confirmation!"
    )
    assert len(proposal["objectives"]) >= 2
    assert len(proposal["assets_required"]) >= 1
    assert "fuel_pnr_analysis" in proposal
    assert "safe_to_dispatch" in proposal["fuel_pnr_analysis"]
    assert "risk_envelope" in proposal
    assert "contingencies" in proposal
    assert "consensus" in proposal
    assert proposal["consensus"]["overall_confidence"] > 0.0


def test_copilot_human_approval_flow():
    """Verify that only explicit human commander approval transitions proposal status."""
    chat_res = copilot_service.chat(None, "Recon corridor Alpha")
    session_id = chat_res["session_id"]

    prop_res = copilot_service.propose_mission_package(session_id, "Recon corridor Alpha")
    prop_id = prop_res["proposal"]["id"]

    appv_res = copilot_service.approve_proposal(
        session_id=session_id,
        proposal_id=prop_id,
        user="General_Commander",
    )

    assert appv_res["success"] is True
    assert appv_res["approved_by"] == "General_Commander"

    # Verify state in DB
    persisted = copilot_service.get_session(session_id)
    assert persisted is not None
    assert persisted["status"] == "approved"
    assert persisted["approved_by"] == "General_Commander"

    approved_prop = next(p for p in persisted["proposals"] if p["id"] == prop_id)
    assert approved_prop["status"] == "approved"
    assert approved_prop["approved_by"] == "General_Commander"
