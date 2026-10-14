"""Test Suite for Replay Intelligence & After Action Review Subsystem (Phase 3F).

Verifies:
- Timeline turning point detection across multiple tactical event types.
- AI AAR executive summary generation with objective and efficiency KPIs.
- Run comparison engine (fuel deltas, casualty deltas, spatial divergence).
- Report persistence in database.
"""

from __future__ import annotations

import pytest
from app import db
from app.replay_intelligence import replay_service, ReplayIntelligenceEngine, haversine_km


@pytest.fixture(autouse=True)
def setup_db():
    db.init()


def test_replay_singleton():
    """Verify singleton instance of ReplayIntelligenceEngine exists."""
    assert replay_service is not None
    assert isinstance(replay_service, ReplayIntelligenceEngine)


def test_haversine_distance():
    """Verify great-circle distance calculation."""
    # Bangalore Central HQ (12.9716, 77.5946) to North Ridge (13.0150, 77.5850) is ~5 km
    dist = haversine_km(12.9716, 77.5946, 13.0150, 77.5850)
    assert 4.5 < dist < 5.5


def test_turning_points_detection():
    """Verify inflection point detection across critical simulation events."""
    sample_events = [
        {"type": "incident_open", "tick": 14, "severity": "critical", "payload": {"detail": "Hostile drone spotted"}},
        {"type": "fuel_low", "tick": 28, "severity": "warning", "payload": {"fuel_remaining": 18.5, "unit_id": "U-1"}},
        {"type": "comms_jamming", "tick": 42, "severity": "medium", "payload": {"unit_id": "U-2"}},
        {"type": "route_reroute", "tick": 50, "severity": "low", "payload": {"unit_id": "U-1"}},
    ]

    tps = replay_service.detect_turning_points(events=sample_events)
    assert len(tps) == 4

    kinds = [tp["kind"] for tp in tps]
    assert "THREAT_ESCALATION" in kinds
    assert "FUEL_CRITICAL" in kinds
    assert "COMMS_LOSS" in kinds
    assert "TRAJECTORY_DIVERGENCE" in kinds

    threat_tp = next(tp for tp in tps if tp["kind"] == "THREAT_ESCALATION")
    assert threat_tp["severity"] == "CRITICAL"
    assert threat_tp["significance_score"] >= 0.8


def test_aar_generation_and_persistence():
    """Verify structured AAR generation and database persistence."""
    sample_events = [
        {"type": "incident_open", "tick": 20, "severity": "critical", "payload": {"detail": "Sector 4 Ambush"}},
    ]
    tps = replay_service.detect_turning_points(events=sample_events)

    aar = replay_service.generate_aar_summary(run_id="run-test-aar-01", turning_points=tps)

    assert aar["run_id"] == "run-test-aar-01"
    assert len(aar["executive_brief"]) > 10
    assert "objectives_summary" in aar
    assert "resource_efficiency" in aar
    assert aar["resource_efficiency"]["fuel_consumed_liters"] > 0
    assert len(aar["recommendations"]) >= 2

    # Verify report was saved to DB
    reports = replay_service.list_reports(run_id="run-test-aar-01")
    assert len(reports) >= 1
    assert reports[0]["run_id"] == "run-test-aar-01"


def test_run_comparison_deltas():
    """Verify What-If comparison deltas and spatial trajectory divergence."""
    comparison = replay_service.compare_runs(
        baseline_run_id="run-baseline-001",
        branch_run_id="run-branch-002",
    )

    assert comparison["baseline_run_id"] == "run-baseline-001"
    assert comparison["branch_run_id"] == "run-branch-002"
    assert "kpi_deltas" in comparison
    assert "fuel_consumed_delta" in comparison["kpi_deltas"]
    assert "casualty_delta" in comparison["kpi_deltas"]

    assert "spatial_divergence" in comparison
    assert comparison["spatial_divergence"]["max_divergence_km"] > 0.0
    assert "outcome_diff" in comparison
    assert len(comparison["outcome_diff"]["narrative"]) > 10
