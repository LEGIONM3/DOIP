"""Unit tests for Phase 3 Digital Twin Operational Forecasting (forecasting.py)."""

import copy
import pytest
from app.forecasting import DigitalTwinForecaster, digital_twin, haversine_km, terrain_friction_factor
from app import db


def test_singleton_instance():
    """Verify digital_twin singleton is instantiated and callable."""
    assert isinstance(digital_twin, DigitalTwinForecaster)
    assert hasattr(digital_twin, "forecast")


def test_forecast_default_run():
    """Verify default forecast generation produces required metrics and structure."""
    res = digital_twin.forecast(horizon_hours=2.0, confidence=0.95)
    
    assert res is not None
    assert "id" in res
    assert res["id"].startswith("FC-")
    assert res["confidence"] == 0.95
    assert res["ticks"] == 120
    assert "predictions" in res
    
    preds = res["predictions"]
    metric_keys = list(preds.keys())
    assert "fuel_exhaustion" in metric_keys
    assert "comms_degradation" in metric_keys
    assert "threat_escalation" in metric_keys
    assert "mission_arrival" in metric_keys
    assert "executive_summary" in metric_keys


def test_forecast_tick_clamping():
    """Verify multi-tick lookahead enforces 60 to 360 ticks clamping."""
    # Under-bound test
    res_min = digital_twin.forecast(horizon_hours=0.2)
    assert res_min["ticks"] == 60
    
    # Over-bound test
    res_max = digital_twin.forecast(horizon_hours=10.0)
    assert res_max["ticks"] == 360
    
    # Mid-range test
    res_mid = digital_twin.forecast(horizon_hours=3.5)
    assert res_mid["ticks"] == 210


def test_read_only_invariant_decoupled_memory():
    """Strict Invariant: Under no circumstances may forecasting mutate the input world state."""
    sample_world = {
        "tick": 50,
        "scenarioId": "SC-1",
        "units": {
            "U-PATROL-1": {
                "id": "U-PATROL-1",
                "callsign": "ALPHA-1",
                "kind": "patrol",
                "lat": 12.9716,
                "lon": 77.5946,
                "fuel": 82.5,
                "battery": 91.0,
                "speedKph": 25.0,
                "route": [[12.9716, 77.5946], [12.9816, 77.6046]],
            }
        },
        "depots": {
            "D-1": {
                "id": "D-1",
                "name": "NORTH DEPOT",
                "lat": 12.9800,
                "lon": 77.6000,
                "stock": {"fuel": 2800.0},
            }
        },
        "weather": {},
        "zones": [],
        "incidents": {},
    }

    world_snapshot_before = copy.deepcopy(sample_world)

    res = digital_twin.forecast(
        horizon_hours=2.0,
        confidence=0.95,
        world_state=sample_world,
        scenario_id="SC-1",
    )

    assert sample_world == world_snapshot_before, "Violated Invariant: input world_state was mutated!"
    assert res["predictions"]["fuel_exhaustion"]["units"]["U-PATROL-1"]["initial_fuel"] == 82.5


def test_fuel_exhaustion_and_pnr_detection():
    """Verify fuel exhaustion timelines and Point-of-No-Return (PNR) calculations."""
    low_fuel_world = {
        "tick": 0,
        "scenarioId": "SC-1",
        "units": {
            "U-LOW-1": {
                "id": "U-LOW-1",
                "callsign": "STRANDED-1",
                "kind": "convoy",
                "lat": 13.1500,  # Far from base
                "lon": 77.7500,
                "fuel": 12.0,     # Very low fuel
                "battery": 80.0,
                "speedKph": 30.0,
                "route": [[13.1500, 77.7500], [13.1800, 77.7800]],
            }
        },
        "depots": {
            "D-1": {
                "id": "D-1",
                "name": "CENTRAL DEPOT",
                "lat": 12.9716,
                "lon": 77.5946,
                "stock": {"fuel": 1500.0},
            }
        },
        "weather": {},
        "zones": [],
        "incidents": {},
    }

    res = digital_twin.forecast(horizon_hours=2.0, confidence=0.95, world_state=low_fuel_world)
    fuel_pred = res["predictions"]["fuel_exhaustion"]

    assert "U-LOW-1" in fuel_pred["units"]
    unit_stats = fuel_pred["units"]["U-LOW-1"]
    assert unit_stats["pnr_breached"] is True
    assert unit_stats["pnr_breach_tick"] is not None
    assert unit_stats["status"] == "CRITICAL"
    assert fuel_pred["pnr_breaches_count"] >= 1


def test_comms_degradation_windows():
    """Verify communications degradation and RF shadow windows detection."""
    res = digital_twin.forecast(horizon_hours=2.0, confidence=0.95)
    comms_pred = res["predictions"]["comms_degradation"]

    assert comms_pred["relay_masts_count"] >= 5
    assert "degradation_windows" in comms_pred
    assert "unit_availability" in comms_pred

    for uid, stats in comms_pred["unit_availability"].items():
        assert "availability_pct" in stats
        assert 0.0 <= stats["availability_pct"] <= 100.0


def test_threat_escalation():
    """Verify threat escalation calculates intersection probabilities."""
    res = digital_twin.forecast(horizon_hours=2.0, confidence=0.95)
    threat_pred = res["predictions"]["threat_escalation"]

    assert "threat_sources_evaluated" in threat_pred
    assert "escalation_score" in threat_pred
    assert 0.0 <= threat_pred["escalation_score"] <= 100.0
    assert threat_pred["trend"] in ["STABLE", "ELEVATED", "ESCALATING"]


def test_mission_arrival_percentiles():
    """Verify P10, P50, and P90 mission arrival percentiles are monotonic."""
    res = digital_twin.forecast(horizon_hours=2.0, confidence=0.95)
    arrival_pred = res["predictions"]["mission_arrival"]

    assert "fleet_p10_ticks" in arrival_pred
    assert "fleet_p50_ticks" in arrival_pred
    assert "fleet_p90_ticks" in arrival_pred
    
    # Monotonicity check
    assert arrival_pred["fleet_p10_ticks"] <= arrival_pred["fleet_p50_ticks"]
    assert arrival_pred["fleet_p50_ticks"] <= arrival_pred["fleet_p90_ticks"]


def test_db_persistence():
    """Verify forecast runs are successfully persisted and retrievable via db functions."""
    res = digital_twin.forecast(horizon_hours=1.5, confidence=0.90)
    run_id = res["id"]

    retrieved = db.get_forecast_run(run_id)
    assert retrieved is not None
    assert retrieved["id"] == run_id
    assert retrieved["confidence"] == 0.90
    assert retrieved["ticks"] == 90
    assert "fuel_exhaustion" in retrieved["predictions"]

    history = db.list_forecast_runs(limit=10)
    assert any(r["id"] == run_id for r in history)

