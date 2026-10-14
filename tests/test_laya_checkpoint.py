"""Tests for trained Laya checkpoints, TorchScript export, and model registry artifacts."""

import json
import pytest
import torch
from pathlib import Path

from backend.app.laya_engine import LayaSimulationClassifier, LayaDecisionEngine, LayaModelRegistry
from backend.app.simulation.feature_extractor import SimulationFeatures


CHECKPOINTS_DIR = Path("checkpoints")


@pytest.mark.parametrize("checkpoint_name", ["laya_doip_v1", "laya_doip_v2"])
def test_checkpoint_files_exist(checkpoint_name):
    """Verify all mandatory checkpoint files exist for the version."""
    ckpt_dir = CHECKPOINTS_DIR / checkpoint_name
    assert ckpt_dir.exists(), f"Checkpoint directory {ckpt_dir} does not exist"

    expected_files = [
        "model.pt",
        "model_traced.pt",
        "calibration.json",
        "manifest.json",
        "metadata.json",
        "benchmark_metrics.json",
        "evaluation_report.json",
    ]
    for filename in expected_files:
        file_path = ckpt_dir / filename
        assert file_path.exists(), f"Missing required checkpoint file: {file_path}"
        assert file_path.stat().st_size > 0, f"File {file_path} is empty"


@pytest.mark.parametrize("checkpoint_name", ["laya_doip_v1", "laya_doip_v2"])
def test_torchscript_model_loading_and_inference(checkpoint_name):
    """Verify TorchScript traced model can be loaded and run independently."""
    traced_path = CHECKPOINTS_DIR / checkpoint_name / "model_traced.pt"
    traced_model = torch.jit.load(str(traced_path))
    traced_model.eval()

    test_input = torch.tensor([[0.5] * 15, [0.1] * 15], dtype=torch.float32)
    with torch.no_grad():
        out = traced_model(test_input)

    assert isinstance(out, dict)
    assert "operational_logits" in out
    assert "outcome_logits" in out
    assert "logistics_logits" in out
    assert "comms_logits" in out
    assert "action_logits" in out
    assert "risk_score" in out

    assert out["operational_logits"].shape == (2, 4)
    assert out["outcome_logits"].shape == (2, 4)
    assert out["risk_score"].shape == (2,) or out["risk_score"].shape == (2, 1)


@pytest.mark.parametrize("checkpoint_name", ["laya_doip_v1", "laya_doip_v2"])
def test_checkpoint_performance_targets(checkpoint_name):
    """Verify the checkpoint evaluation report meets Phase 8.5 performance targets."""
    report_path = CHECKPOINTS_DIR / checkpoint_name / "evaluation_report.json"
    with open(report_path, "r") as f:
        report = json.load(f)

    # Operational Accuracy > 95%
    op_acc = report["tasks"]["operational_state"]["accuracy"]
    assert op_acc > 0.95, f"{checkpoint_name} Operational Accuracy {op_acc:.4f} is below 95%"

    # Outcome Accuracy > 95%
    outcome_acc = report["tasks"]["mission_outcome"]["accuracy"]
    assert outcome_acc > 0.95, f"{checkpoint_name} Outcome Accuracy {outcome_acc:.4f} is below 95%"

    # Operational Macro F1 > 0.93
    macro_f1 = report["tasks"]["operational_state"]["macro_f1"]
    assert macro_f1 > 0.93, f"{checkpoint_name} Macro F1 {macro_f1:.4f} is below 0.93"

    # Calibrated ECE < 0.05
    calib_ece = report["calibration"]["expected_calibration_error_ece"]
    assert calib_ece < 0.05, f"{checkpoint_name} Calibrated ECE {calib_ece:.4f} is above 0.05"


@pytest.mark.parametrize("checkpoint_name", ["laya_doip_v1", "laya_doip_v2"])
def test_laya_decision_engine_loads_checkpoints(checkpoint_name):
    """Verify LayaDecisionEngine initializes and executes inference with trained checkpoints."""
    ckpt_dir = str(CHECKPOINTS_DIR / checkpoint_name)
    engine = LayaDecisionEngine(checkpoint_dir=ckpt_dir)

    assert engine.classifier.checkpoint_loaded is True
    assert engine.classifier.temperature > 0.0

    features = SimulationFeatures(
        numeric_vector=[0.8, 0.5, 0.0, 0.25, 0.9, 0.8, 0.85, 0.1, 0.0, 0.9, 0.0, 0.0, 0.5, 0.1, 0.2],
        feature_names=["f" + str(i) for i in range(15)],
        raw_dict={},
        prompt_text="Test prompt for checkpoint inference",
    )
    pred = engine.predict_operational_decision(features)

    assert pred["operational_state"] in ["NORMAL", "DEGRADED", "CRITICAL", "FAILED", "UNCERTAIN"]
    assert 0.0 <= pred["confidence"] <= 1.0
    assert 0.0 <= pred["risk_score"] <= 1.0


def test_model_registry_contains_versions():
    """Verify LayaModelRegistry tracks laya-base, laya-doip-v1, and laya-doip-v2."""
    registry = LayaModelRegistry()
    models = registry.list_models()
    model_ids = [m["model_id"] for m in models]

    assert "laya-base" in model_ids
    assert "laya-doip-v1" in model_ids
    assert "laya-doip-v2" in model_ids

    v1 = registry.get_model("laya-doip-v1")
    assert v1["status"] == "ACTIVE"
    assert v1["accuracy"] > 0.95
    assert v1["ece"] < 0.05
