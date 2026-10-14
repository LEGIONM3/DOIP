"""Tests for scenario synthesis, trajectory simulation, and dataset isolation."""

import pytest
from backend.app.training.scenario_generator import ScenarioGenerator
from backend.app.training.state_generator import StateTrajectoryGenerator
from backend.app.training.label_generator import LabelGenerator
from backend.app.training.dataset_builder import DatasetBuilder


def test_scenario_generator_coverage():
    """Verify scenario generator produces valid specs across all operational families."""
    gen = ScenarioGenerator(seed=123)
    specs = gen.generate_scenarios(count=30)

    families = {s.family for s in specs}
    unit_types = {s.unit_type for s in specs}

    assert len(specs) == 30
    assert len(families) >= 4
    assert "patrol" in unit_types
    assert "uav" in unit_types
    assert "convoy" in unit_types


def test_state_trajectory_generator_and_labeling():
    """Verify state trajectory generation and authoritative rule labeling."""
    gen = ScenarioGenerator(seed=456)
    spec = gen.generate_scenarios(count=1)[0]
    spec.duration_ticks = 5

    traj_gen = StateTrajectoryGenerator()
    states = traj_gen.run_trajectory(spec)

    assert len(states) == 6  # t=0 plus 5 steps
    assert states[0].tick == 0
    assert states[-1].tick == 5

    label_gen = LabelGenerator()
    lbl = label_gen.generate_label(states[-1])

    assert lbl.operational_state in ["NORMAL", "DEGRADED", "CRITICAL", "FAILED"]
    assert lbl.recommended_action in ["CONTINUE", "REROUTE", "RESUPPLY", "PAUSE", "ABORT"]
    assert 0.0 <= lbl.risk_score <= 1.0


def test_dataset_builder_split_isolation():
    """Verify train, val, and test partitions are scenario-isolated (zero leakage)."""
    gen = ScenarioGenerator(seed=789)
    scenarios = gen.generate_scenarios(count=20)

    builder = DatasetBuilder()
    splits = builder.build_dataset(scenarios)

    train_scens = {s.scenario_id for s in splits["train"]}
    val_scens = {s.scenario_id for s in splits["val"]}
    test_scens = {s.scenario_id for s in splits["test"]}

    # Ensure zero overlap
    assert len(train_scens.intersection(val_scens)) == 0
    assert len(train_scens.intersection(test_scens)) == 0
    assert len(val_scens.intersection(test_scens)) == 0
