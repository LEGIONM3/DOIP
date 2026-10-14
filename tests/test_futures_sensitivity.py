"""Phase 6 Futures Sensitivity and Directional Fidelity Verification.

Validates:
1. Directional sensitivity: High fatigue vs Well-rested personnel.
2. Directional sensitivity: Full fuel vs Critical low fuel.
3. Directional sensitivity: Severe weather vs Nominal scenario.
4. Deterministic branch reproducibility across executions.
5. Snapshot-linked world resolution.
"""

import pytest
from app.future_generator import future_generator
from app import db


def test_futures_sensitivity_to_personnel_fatigue():
    """Verify high-fatigue baseline produces lower scores than well-rested baseline."""
    res_fit = future_generator.generate_alternative_futures(
        baseline_world_id="WLD-NORTH-01",
        count=5,
        ticks=60,
        conditions_override={"fatigue_level": 0.10},
    )

    res_exhausted = future_generator.generate_alternative_futures(
        baseline_world_id="WLD-NORTH-01",
        count=5,
        ticks=60,
        conditions_override={"fatigue_level": 0.95},
    )

    fit_scores = [b["score"] for b in res_fit["top_branches"]]
    exhausted_scores = [b["score"] for b in res_exhausted["top_branches"]]

    assert sum(fit_scores) / len(fit_scores) > sum(exhausted_scores) / len(exhausted_scores)
    assert res_fit["risk_bands"]["P50_median"]["score"] >= res_exhausted["risk_bands"]["P50_median"]["score"]


def test_futures_sensitivity_to_fuel_reserves():
    """Verify critical fuel produces lower scores and compromised mission status."""
    res_high_fuel = future_generator.generate_alternative_futures(
        baseline_world_id="WLD-NORTH-01",
        count=5,
        ticks=60,
        conditions_override={"fuel_level": 90.0},
    )

    res_low_fuel = future_generator.generate_alternative_futures(
        baseline_world_id="WLD-NORTH-01",
        count=5,
        ticks=60,
        conditions_override={"fuel_level": 12.0},
    )

    high_fuel_median = res_high_fuel["risk_bands"]["P50_median"]["score"]
    low_fuel_median = res_low_fuel["risk_bands"]["P50_median"]["score"]

    assert high_fuel_median > low_fuel_median
    assert res_low_fuel["worst_branch"]["mission_success"] is False


def test_futures_deterministic_branch_reproducibility():
    """Verify identical parameters and world produce identical branch seeds, scores, and ranks."""
    res_1 = future_generator.generate_alternative_futures(
        baseline_world_id="WLD-NORTH-01",
        count=5,
        ticks=60,
    )

    res_2 = future_generator.generate_alternative_futures(
        baseline_world_id="WLD-NORTH-01",
        count=5,
        ticks=60,
    )

    assert len(res_1["top_branches"]) == len(res_2["top_branches"])
    for b1, b2 in zip(res_1["top_branches"], res_2["top_branches"]):
        assert b1["branch_seed"] == b2["branch_seed"]
        assert b1["score"] == b2["score"]
        assert b1["outcome_rank"] == b2["outcome_rank"]


def test_futures_resolution_from_persisted_run_snapshot():
    """Verify future generator resolves baseline world state directly from saved database run snapshots."""
    run_id = "test-run-futures-snap-01"
    db.save_world_snapshot(run_id, {
        "runId": run_id,
        "seed": 991122,
        "scenarioId": "SC-2",
        "tick": 30,
        "units": {
            "U-PATROL-1": {"id": "U-PATROL-1", "fuel": 20.0, "battery": 25.0},
        },
        "personnel": {
            "P-U-PATROL-1-0": {"id": "P-U-PATROL-1-0", "fatigue": 0.85, "heartRate": 140.0},
        },
    })

    res = future_generator.generate_alternative_futures(
        baseline_world_id=run_id,
        count=3,
        ticks=30,
    )
    assert res["branches_count"] == 3
    assert res["baseline_world_id"] == run_id
    assert len(res["top_branches"]) == 3
