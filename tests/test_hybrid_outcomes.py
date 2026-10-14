"""Unit and integration tests for consensus outcome arbitration and disagreement analytics."""

import pytest
from backend.app.simulation.physics_engine import PhysicsEngineState, EnergyState
from backend.app.simulation.rule_engine import RuleEngine, RuleEvaluationResult
from backend.app.simulation.outcome_engine import ConsensusOutcomeEngine, analyze_model_disagreement
from backend.app.hybrid_outcome_engine import HybridOutcomeEngine


def test_consensus_outcome_engine_full_consensus():
    """Verify full consensus when rules and Laya agree."""
    rule_engine = RuleEngine()
    consensus_engine = ConsensusOutcomeEngine(rule_engine)

    state = PhysicsEngineState()
    rule_eval = rule_engine.evaluate(state)

    laya_eval = {
        "operational_state": rule_eval.operational_state,
        "mission_outcome": rule_eval.mission_outcome,
        "recommended_action": rule_eval.recommended_action,
        "risk_score": rule_eval.rule_risk_score,
        "confidence": 0.90,
        "abstained": False,
    }

    outcome = consensus_engine.arbitrate(state, laya_eval)
    assert outcome.agreement_level == "FULL_CONSENSUS"
    assert outcome.consensus_action == rule_eval.recommended_action


def test_consensus_outcome_safety_override():
    """Verify safety override when physical invariant triggers FAILED but Laya is optimistic."""
    rule_engine = RuleEngine()
    consensus_engine = ConsensusOutcomeEngine(rule_engine)

    # State has 0% fuel -> Rule engine triggers FAILED
    depleted_state = PhysicsEngineState(energy=EnergyState(fuel_level_pct=0.0))

    # Malfunctioning/optimistic learned decision proposing CONTINUE
    optimistic_laya = {
        "operational_state": "NORMAL",
        "mission_outcome": "SUCCESS",
        "recommended_action": "CONTINUE",
        "risk_score": 0.1,
        "confidence": 0.85,
        "abstained": False,
    }

    outcome = consensus_engine.arbitrate(depleted_state, optimistic_laya)
    assert outcome.agreement_level == "SAFETY_OVERRIDE"
    assert outcome.consensus_operational_state == "FAILED"
    assert outcome.consensus_action == "ABORT"


def test_model_disagreement_analysis():
    """Verify aggregate statistical disagreement calculation."""
    r1 = RuleEvaluationResult(
        operational_state="NORMAL",
        mission_outcome="SUCCESS",
        logistics_state="HEALTHY",
        comms_state="CONNECTED",
        environmental_impact="LOW",
        recommended_action="CONTINUE",
        rule_risk_score=0.1,
    )
    r2 = RuleEvaluationResult(
        operational_state="CRITICAL",
        mission_outcome="DELAYED",
        logistics_state="LOW_RESERVE",
        comms_state="DEGRADED",
        environmental_impact="HIGH",
        recommended_action="REROUTE",
        rule_risk_score=0.7,
    )

    l1 = {
        "operational_state": "NORMAL",
        "mission_outcome": "SUCCESS",
        "recommended_action": "CONTINUE",
        "risk_score": 0.15,
    }
    l2 = {
        "operational_state": "DEGRADED",  # Disagrees with CRITICAL
        "mission_outcome": "DELAYED",
        "recommended_action": "REROUTE",
        "risk_score": 0.5,
    }

    stats = analyze_model_disagreement([r1, r2], [l1, l2])
    assert stats["sample_count"] == 2
    assert stats["operational_state_agreement"] == 0.5
    assert stats["mission_outcome_agreement"] == 1.0
    assert stats["action_agreement"] == 1.0
    assert stats["mean_risk_divergence"] > 0.0


def test_hybrid_outcome_engine_trajectory_run():
    """Verify HybridOutcomeEngine executes multi-tick trajectory."""
    engine = HybridOutcomeEngine()
    res = engine.run_hybrid_trajectory(ticks=5)

    assert "trajectory_id" in res
    assert res["ticks"] == 5
    assert len(res["trajectory"]) == 5
    assert "model_comparison_stats" in res
