"""Unit and integration tests for Laya learned decision engine and inference gating."""

import os
import pytest
from backend.app.laya_engine import (
    LayaSimulationClassifier,
    LayaDecisionEngine,
    OPERATIONAL_STATES,
    MISSION_OUTCOMES,
    ACTIONS,
)
from backend.app.simulation.feature_extractor import FeatureExtractor, SimulationFeatures
from backend.app.simulation.physics_engine import PhysicsEngineState


def test_laya_classifier_forward_pass_and_checkpoint():
    """Verify LayaSimulationClassifier loads trained checkpoint and outputs valid decision schema."""
    ckpt_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "checkpoints", "laya_doip_v1", "model.pt")
    )
    classifier = LayaSimulationClassifier(checkpoint_path=ckpt_path if os.path.exists(ckpt_path) else None)

    extractor = FeatureExtractor()
    state = PhysicsEngineState()
    features = extractor.extract(state)

    res = classifier.predict(features, min_confidence=0.50)

    assert res["operational_state"] in OPERATIONAL_STATES
    assert res["mission_outcome"] in MISSION_OUTCOMES
    assert res["recommended_action"] in ACTIONS
    assert 0.0 <= res["risk_score"] <= 1.0
    assert 0.0 <= res["confidence"] <= 1.0
    assert res["latency_ms"] < 100.0  # Fast single forward pass


def test_laya_confidence_gating_and_abstention():
    """Verify min_confidence parameter enforces abstention gating."""
    classifier = LayaSimulationClassifier()
    extractor = FeatureExtractor()
    features = extractor.extract(PhysicsEngineState())

    # With very high confidence gate (0.999), classifier must abstain
    res_abstain = classifier.predict(features, min_confidence=0.999)
    assert res_abstain["abstained"] is True
    assert res_abstain["gate_state"] == "GATE_ABSTAINED"

    # With low confidence gate (0.10), classifier passes
    res_pass = classifier.predict(features, min_confidence=0.10)
    assert res_pass["abstained"] is False
    assert res_pass["gate_state"] == "GATE_PASSED"


def test_laya_decision_engine_status():
    """Verify LayaDecisionEngine interface and metadata report."""
    engine = LayaDecisionEngine()
    status = engine.get_status()

    assert status["model_name"] == "laya-doip-v1"
    assert status["abstention_support"] is True
    assert "operational_state" in status["supported_tasks"]
