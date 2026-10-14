"""Tests for Laya training components, dataset loading, and loss functions."""

import pytest
import torch
import torch.nn as nn
from pathlib import Path

from backend.app.training.dataset_builder import OperationalDataset, DatasetSample
from backend.app.laya_engine import LayaNeuralScorer
from training_data.scenario_generator import ScenarioGenerator
from training_data.state_generator import StateGenerator
from training_data.trajectory_generator import TrajectoryGenerator
from training_data.quality_validator import QualityValidator


def test_state_and_trajectory_generator_determinism():
    """Verify deterministic state generation with fixed seeds."""
    scen_gen1 = ScenarioGenerator(seed=42)
    spec1 = scen_gen1.generate_scenarios(1)[0]

    scen_gen2 = ScenarioGenerator(seed=42)
    spec2 = scen_gen2.generate_scenarios(1)[0]

    state_gen = StateGenerator()
    s1 = state_gen.initialize_state(spec1)
    s2 = state_gen.initialize_state(spec2)

    assert s1.kinematics.lat == s2.kinematics.lat
    assert s1.energy.fuel_level_pct == s2.energy.fuel_level_pct
    assert s1.comms.signal_strength_dbm == s2.comms.signal_strength_dbm


def test_trajectory_generator_and_labeling():
    """Verify trajectory simulation produces labels and valid future branches."""
    scen_gen = ScenarioGenerator(seed=123)
    spec = scen_gen.generate_scenarios(1)[0]

    traj_gen = TrajectoryGenerator()
    states = traj_gen.generate_trajectory(spec)
    assert len(states) > 0

    soft_labels = traj_gen.evaluate_multi_future_soft_labels(
        states[0], spec, num_branches=10, horizon_ticks=5, seed=123
    )

    assert "mission_outcome" in soft_labels
    assert "operational_state" in soft_labels
    assert "recommended_action" in soft_labels

    outcome_dist = soft_labels["mission_outcome"]
    assert abs(sum(outcome_dist.values()) - 1.0) < 1e-3


def test_operational_dataset_tensor_shapes():
    """Verify OperationalDataset produces valid PyTorch tensors with soft labels."""
    samples = [
        DatasetSample(
            sample_id="S-001",
            scenario_id="SC-001",
            scenario_family="PATROL",
            tick=1,
            numeric_vector=[0.5] * 15,
            prompt_text="Telemetry test 1",
            labels={
                "operational_state": "NORMAL",
                "logistics_state": "HEALTHY",
                "comms_state": "CONNECTED",
                "recommended_action": "CONTINUE",
                "mission_outcome": "SUCCESS",
                "environmental_impact": "LOW",
                "risk_score": 0.1,
            },
            soft_labels={
                "mission_outcome": {"SUCCESS": 0.8, "DELAYED": 0.1, "ABORTED": 0.05, "FAILED": 0.05},
                "operational_state": {"NORMAL": 0.9, "DEGRADED": 0.1, "CRITICAL": 0.0, "FAILED": 0.0},
            },
        ),
        DatasetSample(
            sample_id="S-002",
            scenario_id="SC-002",
            scenario_family="RECON",
            tick=2,
            numeric_vector=[0.1] * 15,
            prompt_text="Telemetry test 2",
            labels={
                "operational_state": "CRITICAL",
                "logistics_state": "CRITICAL",
                "comms_state": "LOST",
                "recommended_action": "ABORT",
                "mission_outcome": "FAILED",
                "environmental_impact": "SEVERE",
                "risk_score": 0.9,
            },
            soft_labels={
                "mission_outcome": {"SUCCESS": 0.0, "DELAYED": 0.1, "ABORTED": 0.2, "FAILED": 0.7},
                "operational_state": {"NORMAL": 0.0, "DEGRADED": 0.1, "CRITICAL": 0.8, "FAILED": 0.1},
            },
        ),
    ]

    dataset = OperationalDataset(samples)
    assert len(dataset) == 2

    item = dataset[0]
    assert item["features"].shape == (15,)
    assert item["risk"].shape == ()
    assert item["outcome_soft"].shape == (4,)
    assert item["operational_soft"].shape == (4,)
    assert isinstance(item["operational"], torch.Tensor)
    assert isinstance(item["outcome"], torch.Tensor)


def test_training_step_loss_and_backprop():
    """Verify single forward and backward training step with gradient updates."""
    model = LayaNeuralScorer(input_dim=15, hidden_dim=64)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion_ce = nn.CrossEntropyLoss()
    criterion_mse = nn.MSELoss()

    features = torch.randn(4, 15)
    target_op = torch.tensor([0, 1, 2, 3])
    target_risk = torch.tensor([0.1, 0.4, 0.8, 0.95])

    # Initial weights snapshot
    initial_param = model.encoder[0].weight.clone()

    optimizer.zero_grad()
    outputs = model(features)
    loss_op = criterion_ce(outputs["operational_logits"], target_op)
    loss_risk = criterion_mse(outputs["risk_score"], target_risk)
    total_loss = loss_op + loss_risk

    total_loss.backward()
    optimizer.step()

    # Parameters must have updated
    updated_param = model.encoder[0].weight
    assert not torch.equal(initial_param, updated_param)
    assert total_loss.item() > 0.0


def test_quality_validator_rules():
    """Verify QualityValidator detects class balance and anomalies."""
    validator = QualityValidator()
    samples = [
        {"hard_labels": {"operational_state": "NORMAL"}},
        {"hard_labels": {"operational_state": "DEGRADED"}},
        {"hard_labels": {"operational_state": "CRITICAL"}},
        {"hard_labels": {"operational_state": "FAILED"}},
    ]

    report = validator.validate(samples)
    assert report["sample_count"] == 4
    assert "class_distributions" in report
    assert report["class_distributions"]["NORMAL"] == 1
    assert report["valid"] is True
