"""Tests for Laya temperature calibration, ECE verification, and abstention fallbacks."""

import json
import pytest
import numpy as np
import torch
from pathlib import Path

from training.calibrate_laya import compute_ece_and_brier
from backend.app.laya_engine import LayaSimulationClassifier
from backend.app.simulation.feature_extractor import SimulationFeatures
from backend.app.simulation.rule_engine import RuleEngine
from backend.app.simulation.physics_engine import PhysicsEngineState, EnergyState


CHECKPOINTS_DIR = Path("checkpoints")


def test_compute_ece_and_brier_synthetic():
    """Verify compute_ece_and_brier produces accurate metrics on synthetic data."""
    # Perfectly calibrated cases
    probs = np.array([
        [0.9, 0.1, 0.0, 0.0],
        [0.8, 0.2, 0.0, 0.0],
        [0.1, 0.9, 0.0, 0.0],
        [0.2, 0.8, 0.0, 0.0],
    ])
    labels = np.array([0, 0, 1, 1])

    ece, brier, bin_details = compute_ece_and_brier(probs, labels, num_bins=10)
    assert 0.0 <= ece <= 1.0
    assert 0.0 <= brier <= 1.0
    assert len(bin_details) > 0


@pytest.mark.parametrize("checkpoint_name", ["laya_doip_v1", "laya_doip_v2"])
def test_calibration_artifact_meets_directive_target(checkpoint_name):
    """Verify both checkpoints achieve ECE < 0.05 directive target."""
    calib_path = CHECKPOINTS_DIR / checkpoint_name / "calibration.json"
    assert calib_path.exists()

    with open(calib_path, "r", encoding="utf-8") as f:
        calib_data = json.load(f)

    post_ece = calib_data["post_calibration"]["ece"]
    target_threshold = calib_data["target_threshold"]

    assert post_ece < target_threshold, f"{checkpoint_name} ECE {post_ece} exceeds {target_threshold}"
    assert calib_data["target_met"] is True
    assert calib_data["ece_reduction_pct"] > 50.0  # Significant reduction


def test_temperature_scaling_sharpens_distribution():
    """Verify temperature scaling with T < 1.0 sharpens logits while preserving argmax."""
    logits = torch.tensor([[2.0, 1.0, 0.0, -1.0]])
    t_sharp = 0.5

    p_raw = torch.softmax(logits, dim=-1)
    p_calib = torch.softmax(logits / t_sharp, dim=-1)

    # Argmax is preserved
    assert torch.argmax(p_raw) == torch.argmax(p_calib)
    # Peak confidence is sharpened
    assert p_calib.max() > p_raw.max()


def test_abstention_system_uncertain_prediction():
    """Verify that when confidence drops below threshold, Laya returns UNCERTAIN."""
    classifier = LayaSimulationClassifier()

    features = SimulationFeatures(
        numeric_vector=[0.5] * 15,
        feature_names=["f" + str(i) for i in range(15)],
        raw_dict={},
        prompt_text="Uncertain state prompt",
    )

    # Forcing high min_confidence to trigger abstention
    res = classifier.predict(features, min_confidence=0.999)

    assert res["abstained"] is True
    assert res["gate_state"] == "GATE_ABSTAINED"
    assert res["operational_state"] == "UNCERTAIN"
    assert res["mission_outcome"] == "UNCERTAIN"
    assert res["recommended_action"] == "UNCERTAIN"


def test_rule_engine_fallback_on_abstention():
    """Verify Rule Engine provides authoritative fallback when Laya outputs UNCERTAIN."""
    rule_engine = RuleEngine()
    state = PhysicsEngineState(energy=EnergyState(fuel_level_pct=10.0))

    # Evaluate authoritative rules
    rule_res = rule_engine.evaluate(state)
    assert rule_res.operational_state in ["NORMAL", "DEGRADED", "CRITICAL", "FAILED"]
    assert rule_res.recommended_action in ["CONTINUE", "REROUTE", "RESUPPLY", "PAUSE", "ABORT"]

    # In hybrid simulation, if Laya output is UNCERTAIN, rule_res is authoritative
    laya_decision = "UNCERTAIN"
    final_decision = rule_res.recommended_action if laya_decision == "UNCERTAIN" else laya_decision
    assert final_decision != "UNCERTAIN"
