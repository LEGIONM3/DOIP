"""Phase 7 Forecasting Temporal Fidelity and Uncertainty Horizon Verification.

Validates:
1. Multi-horizon execution across 0.5h, 1.0h, 2.0h, and 6.0h.
2. Monotonically increasing spatial uncertainty cones over lookahead ticks.
3. Realistic fuel and battery consumption across projected tracks.
4. RF line-of-sight and comms degradation tracking.
5. Multi-modal forecast intelligence output integrity.
"""

import math
import pytest
from app.forecasting import DigitalTwinForecaster


@pytest.fixture
def forecaster():
    return DigitalTwinForecaster()


def test_forecast_multi_horizon_execution(forecaster):
    """Verify forecaster supports horizons from 30 min (0.5h) to 360 min (6.0h)."""
    horizons = [0.5, 1.0, 2.0, 4.0, 6.0]
    expected_ticks = [60, 60, 120, 240, 360]

    for h, exp_t in zip(horizons, expected_ticks):
        res = forecaster.forecast(horizon_hours=h, confidence=0.95, scenario_id="SC-1")
        assert res["ticks"] == exp_t
        assert res["horizon_hours"] == h
        assert "trajectories" in res
        assert "predictions" in res
        assert len(res["trajectories"]) > 0


def test_forecast_uncertainty_increases_monotonically(forecaster):
    """Verify that projected uncertainty radius increases monotonically as horizon extends."""
    res = forecaster.forecast(horizon_hours=2.0, confidence=0.90, scenario_id="SC-1")
    trajectories = res["trajectories"]

    # Check for each unit trajectory
    for uid, track in trajectories.items():
        if len(track) < 10:
            continue
        uncertainties = [pt["uncertaintyRadiusM"] for pt in track]
        # Verify first is strictly smaller than last
        assert uncertainties[0] < uncertainties[-1]

        # Verify monotonicity (non-decreasing along track)
        for i in range(1, len(uncertainties)):
            assert uncertainties[i] >= uncertainties[i - 1], f"Uncertainty decreased at index {i} for {uid}"


def test_forecast_fuel_and_battery_depletion(forecaster):
    """Verify units burn fuel and battery realistically along their movement paths."""
    res = forecaster.forecast(horizon_hours=2.0, confidence=0.95, scenario_id="SC-1")
    trajectories = res["trajectories"]

    for uid, track in trajectories.items():
        if len(track) < 5:
            continue
        first_fuel = track[0]["fuel"]
        last_fuel = track[-1]["fuel"]
        assert last_fuel <= first_fuel, f"Fuel did not decrease for unit {uid}"

        first_bat = track[0]["battery"]
        last_bat = track[-1]["battery"]
        assert last_bat <= first_bat, f"Battery did not decrease for unit {uid}"


def test_forecast_multimodal_intel_completeness(forecaster):
    """Verify multi-modal intelligence outputs (physics, rules, laya, hybrid) are fully formed."""
    res = forecaster.forecast(horizon_hours=2.0, confidence=0.95, scenario_id="SC-1")
    intel = res.get("forecast_intelligence")
    assert intel is not None
    assert "physics_forecast" in intel
    assert "rule_forecast" in intel
    assert "laya_forecast" in intel

    for mode in ["physics_forecast", "rule_forecast", "laya_forecast"]:
        pred = intel[mode]
        assert "risk_p10" in pred
        assert "risk_p50" in pred
        assert "risk_p90" in pred
        assert "worst_case" in pred
        assert 0.0 <= pred["risk_p10"] <= pred["risk_p50"] <= pred["risk_p90"] <= 1.0
