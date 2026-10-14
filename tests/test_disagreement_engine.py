"""Tests for Model Disagreement Engine, triad comparison, and divergence classification."""

import pytest
from backend.app.simulation.physics_engine import (
    PhysicsEngineState,
    KinematicState,
    EnergyState,
    EnvironmentState,
    CommsState,
    LogisticsState,
)
from backend.app.simulation.rule_engine import RuleEngine, RuleEvaluationResult
from backend.app.simulation.disagreement_engine import (
    ModelDisagreementEngine,
    analyze_disagreement,
    compute_physics_risk,
    risk_score_to_category,
)


def test_compute_physics_risk_nominal_vs_extreme():
    """Verify physics risk score calculation under nominal and extreme parameters."""
    nominal_state = PhysicsEngineState(
        energy=EnergyState(fuel_level_pct=95.0),
        comms=CommsState(jamming_intensity=0.0, packet_loss_pct=0.0),
        logistics=LogisticsState(vehicle_wear_pct=5.0),
    )
    score_nom, cat_nom = compute_physics_risk(nominal_state)
    assert 0.0 <= score_nom < 0.25
    assert cat_nom == "LOW"

    depleted_state = PhysicsEngineState(
        energy=EnergyState(fuel_level_pct=2.0),
        comms=CommsState(jamming_intensity=0.9, packet_loss_pct=80.0),
        logistics=LogisticsState(vehicle_wear_pct=95.0),
    )
    score_dep, cat_dep = compute_physics_risk(depleted_state)
    assert score_dep > 0.70
    assert cat_dep in ["HIGH", "CRITICAL"]


def test_full_consensus_returns_none():
    """Verify that when Physics, Rules, and Laya agree, no disagreement is recorded."""
    engine = ModelDisagreementEngine()
    state = PhysicsEngineState(energy=EnergyState(fuel_level_pct=90.0))

    rule_eval = RuleEvaluationResult(
        operational_state="NORMAL",
        recommended_action="CONTINUE",
        mission_outcome="SUCCESS",
        logistics_state="HEALTHY",
        comms_state="CONNECTED",
        environmental_impact="LOW",
        rule_risk_score=0.10,
        invariants_passed=True,
    )

    laya_eval = {
        "operational_state": "NORMAL",
        "recommended_action": "CONTINUE",
        "mission_outcome": "SUCCESS",
        "risk_score": 0.12,
        "confidence": 0.98,
    }

    record = engine.analyze_disagreement(state, rule_eval, laya_eval)
    assert record is None


def test_disagreement_detection_and_severity():
    """Verify detection and classification of operational state divergence."""
    engine = ModelDisagreementEngine()
    state = PhysicsEngineState(energy=EnergyState(fuel_level_pct=10.0))

    rule_eval = RuleEvaluationResult(
        operational_state="CRITICAL",
        recommended_action="RESUPPLY",
        mission_outcome="DELAYED",
        logistics_state="CRITICAL",
        comms_state="CONNECTED",
        environmental_impact="LOW",
        rule_risk_score=0.85,
        invariants_passed=True,
        triggered_rules=["FUEL_CRITICAL"],
    )

    # Laya falsely optimistic
    laya_eval = {
        "operational_state": "NORMAL",
        "recommended_action": "CONTINUE",
        "mission_outcome": "SUCCESS",
        "risk_score": 0.15,
        "confidence": 0.70,
    }

    record = engine.analyze_disagreement(state, rule_eval, laya_eval)
    assert record is not None
    assert record.physics_risk in ["LOW", "MODERATE", "HIGH"]
    assert record.rules_risk == "CRITICAL"
    assert record.laya_risk == "LOW"
    assert record.divergence_severity in ["MODERATE", "SEVERE"]
    assert "Operational State conflict" in record.explanation
    assert "Tactical Action conflict" in record.explanation


def test_severe_failure_conflict():
    """Verify catastrophic rule failure vs optimistic Laya flags SEVERE divergence."""
    state = PhysicsEngineState(energy=EnergyState(fuel_level_pct=0.0))

    rule_eval = RuleEvaluationResult(
        operational_state="FAILED",
        recommended_action="ABORT",
        mission_outcome="FAILED",
        logistics_state="CRITICAL",
        comms_state="LOST",
        environmental_impact="LOW",
        rule_risk_score=1.0,
        invariants_passed=False,
    )

    laya_eval = {
        "operational_state": "DEGRADED",
        "recommended_action": "CONTINUE",
        "mission_outcome": "DELAYED",
        "risk_score": 0.40,
        "confidence": 0.60,
    }

    result = analyze_disagreement(state, rule_eval, laya_eval)
    assert result is not None
    assert result["divergence_severity"] == "SEVERE"
    assert "FAILED" in result["explanation"]


def test_disagreement_history_and_statistics():
    """Verify disagreement engine history tracking and summary statistics."""
    engine = ModelDisagreementEngine()
    state = PhysicsEngineState(tick=1)

    rule_eval = RuleEvaluationResult(
        operational_state="DEGRADED",
        recommended_action="REROUTE",
        mission_outcome="DELAYED",
        logistics_state="LOW_RESERVE",
        comms_state="DEGRADED",
        environmental_impact="LOW",
        rule_risk_score=0.60,
        invariants_passed=True,
    )
    laya_eval = {
        "operational_state": "NORMAL",
        "recommended_action": "CONTINUE",
        "mission_outcome": "SUCCESS",
        "risk_score": 0.10,
    }

    engine.analyze_disagreement(state, rule_eval, laya_eval)
    stats = engine.get_statistics()

    assert stats["total_disagreements"] >= 1
    assert "severity_counts" in stats
    recent = engine.get_recent_disagreements(limit=10)
    assert len(recent) >= 1
    assert "disagreement_id" in recent[0]
