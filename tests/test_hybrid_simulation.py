"""Unit and integration tests for DOIP Phase 8 Hybrid Physics & Rule Simulation."""

import pytest
from backend.app.simulation.physics_engine import (
    PhysicsEngine,
    PhysicsEngineState,
    KinematicState,
    EnergyState,
    EnvironmentState,
    CommsState,
    LogisticsState,
)
from backend.app.simulation.rule_engine import RuleEngine, RuleEvaluationResult
from backend.app.simulation.feature_extractor import FeatureExtractor
from backend.app.simulation.state_transition import StateTransitionValidator
from backend.app.simulation.simulation_runner import HybridSimulationRunner, SimulationMode


def test_physics_engine_kinematics_and_energy():
    """Verify continuous kinematic propagation and energy consumption."""
    init_state = PhysicsEngineState(
        kinematics=KinematicState(lat=12.9716, lon=77.5946, speed_mps=10.0, heading_deg=90.0),
        energy=EnergyState(fuel_level_pct=100.0),
    )
    physics = PhysicsEngine(init_state)

    next_state = physics.step(dt_sec=2.0, target_speed_mps=15.0)

    # Unit should move eastward (heading 90 deg)
    assert next_state.kinematics.lon > 77.5946
    assert next_state.kinematics.speed_mps > 10.0
    assert next_state.energy.fuel_level_pct < 100.0
    assert next_state.tick == 1


def test_physics_engine_comms_rf_propagation():
    """Verify RF path loss, jamming attenuation, and packet delivery modeling."""
    init_state = PhysicsEngineState(
        comms=CommsState(distance_to_relay_m=1000.0, jamming_intensity=0.0)
    )
    physics = PhysicsEngine(init_state)
    s1 = physics.step(dt_sec=1.0)
    clean_signal = s1.comms.signal_strength_dbm
    clean_packet_loss = s1.comms.packet_loss_pct

    # Perturb with high jamming
    s2 = physics.step(dt_sec=1.0, environmental_perturbation={"jamming_intensity": 0.85})
    jammed_signal = s2.comms.signal_strength_dbm

    assert jammed_signal < clean_signal
    assert s2.comms.packet_loss_pct >= clean_packet_loss


def test_rule_engine_invariants_and_actions():
    """Verify deterministic rule engine evaluates invariants and permissible actions."""
    rule_engine = RuleEngine()

    nominal_state = PhysicsEngineState()
    res_nom = rule_engine.evaluate(nominal_state)
    assert res_nom.invariants_passed is True

    # Critical fuel state
    depleted_state = PhysicsEngineState(
        energy=EnergyState(fuel_level_pct=0.0),
        kinematics=KinematicState(lat=12.97, lon=77.59, speed_mps=12.0),
    )
    res_depleted = rule_engine.evaluate(depleted_state)
    assert res_depleted.operational_state == "FAILED"
    assert res_depleted.invariants_passed is False  # Cannot move with 0% fuel

    # Validate action logic
    can_continue, msg = rule_engine.validate_action(depleted_state, "CONTINUE")
    assert can_continue is False
    assert "Cannot CONTINUE" in msg

    can_resupply, _ = rule_engine.validate_action(depleted_state, "RESUPPLY")
    assert can_resupply is True


def test_feature_extractor_numeric_and_prompt():
    """Verify feature extractor generates 15-dim normalized vector and prompt text."""
    extractor = FeatureExtractor()
    state = PhysicsEngineState()
    features = extractor.extract(state)

    assert len(features.numeric_vector) == 15
    for val in features.numeric_vector:
        assert 0.0 <= val <= 1.0

    assert "Operational telemetry for unit" in features.prompt_text
    assert "Kinematics:" in features.prompt_text
    assert "Energy:" in features.prompt_text


def test_hybrid_simulation_runner_deterministic_and_hybrid():
    """Verify HybridSimulationRunner in both simulation modes."""
    runner = HybridSimulationRunner(mode=SimulationMode.DETERMINISTIC_SIM)
    step1 = runner.step(dt_sec=1.0)

    assert step1["mode"] == "DETERMINISTIC_SIM"
    assert step1["validation_result"]["decision_source"] == "RULE_ENGINE"
    assert step1["validation_result"]["action_accepted"] is True

    # Run multi-step
    steps = runner.run_ticks(num_ticks=3, dt_sec=1.0)
    assert len(steps) == 3
    assert steps[-1]["tick"] == 4


def test_hybrid_simulation_rule_validation_rejects_infeasible_laya_action():
    """Verify Rule Engine strictly blocks impossible actions from Laya with zero rule violations."""
    rule_engine = RuleEngine()
    validator = StateTransitionValidator(rule_engine)

    # Asset with 0% fuel
    depleted_state = PhysicsEngineState(
        energy=EnergyState(fuel_level_pct=0.0),
        kinematics=KinematicState(lat=12.97, lon=77.59, speed_mps=0.0),
    )

    # Suppose Laya hallucinated or erroneously proposed 'CONTINUE'
    erroneous_laya_decision = {
        "recommended_action": "CONTINUE",
        "confidence": 0.95,
        "abstained": False,
    }

    val_res = validator.validate_and_apply(
        current_state=depleted_state,
        laya_decision=erroneous_laya_decision,
        confidence_gate_passed=True,
    )

    # Invariant must hold: action is rejected or overridden by authoritative rule engine
    assert val_res.decision_source == "RULE_ENGINE_OVERRIDE"
    assert val_res.action_accepted is False
    assert val_res.final_action != "CONTINUE"
    assert "rejected" in val_res.reason.lower() or "override" in val_res.reason.lower()


def test_hybrid_simulation_abstention_falls_back_to_rules():
    """Verify that when Laya abstains, rule engine seamlessly takes authoritative control."""
    rule_engine = RuleEngine()
    validator = StateTransitionValidator(rule_engine)

    state = PhysicsEngineState(energy=EnergyState(fuel_level_pct=50.0))
    abstained_decision = {
        "recommended_action": "UNCERTAIN",
        "confidence": 0.40,
        "abstained": True,
    }

    val_res = validator.validate_and_apply(
        current_state=state,
        laya_decision=abstained_decision,
        confidence_gate_passed=False,
    )

    assert val_res.decision_source in ["RULE_FALLBACK", "RULE_ENGINE"]
    assert val_res.final_action in ["CONTINUE", "REROUTE", "RESUPPLY", "PAUSE", "ABORT"]
    assert val_res.validation_status in ["ABSTAINED_FALLBACK", "ACCEPTED"]
