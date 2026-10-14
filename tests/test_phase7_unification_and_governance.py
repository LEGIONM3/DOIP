"""Test Suite for DOIP Phase 7 — Platform Unification & Autonomous Governance."""

import pytest
from app.platform_unification import (
    PlatformRegistry,
    PlatformService,
    PlatformConfiguration,
    PlatformLifecycleManager,
    platform_registry,
    platform_lifecycle,
    platform_config,
)
from app.governance import (
    GovernanceEngine,
    GovernanceViolationError,
    governance_engine,
)
from app.self_healing import self_healing_engine
from app.validation_engine import validation_engine


def test_platform_registry_and_lifecycle():
    """Verify platform services register cleanly and lifecycle manager bootstraps successfully."""
    boot = platform_lifecycle.bootstrap_platform()
    assert boot["status"] in ("BOOTSTRAP_COMPLETE", "ALREADY_BOOTSTRAPPED")

    services = platform_registry.list_services()
    assert len(services) >= 15

    subsystems = platform_registry.get_subsystems()
    assert "simulation" in subsystems
    assert "routing" in subsystems
    assert "governance" in subsystems
    assert "reliability" in subsystems

    health = platform_registry.check_all_health()
    assert health["total_services"] >= 15
    assert health["overall_status"] in ("HEALTHY", "DEGRADED")


def test_governance_approval_boundary_enforcement():
    """Verify that kinetic and execution actions strictly require human authorization."""
    # 1. Missing actor on critical execution action must raise GovernanceViolationError
    with pytest.raises(GovernanceViolationError):
        governance_engine.verify_approval_boundary(
            action="mission_execution",
            actor=None,
        )

    # 2. Blank actor must raise GovernanceViolationError
    with pytest.raises(GovernanceViolationError):
        governance_engine.verify_approval_boundary(
            action="fire_mission",
            actor="   ",
        )

    # 3. Authorized commander sign-off passes
    res = governance_engine.verify_approval_boundary(
        action="mission_execution",
        actor="commander_nash",
        role="commander",
    )
    assert res["compliant"] is True
    assert res["actor"] == "commander_nash"


def test_governance_determinism_and_data_integrity():
    """Verify seed verification and payload structure validation."""
    # Determinism check with null seed must raise error
    with pytest.raises(GovernanceViolationError):
        governance_engine.verify_simulation_determinism("SC-01", seed=None)

    # Determinism check with valid integer seed passes
    det = governance_engine.verify_simulation_determinism("SC-01", seed=8841)
    assert det["compliant"] is True
    assert det["seed"] == 8841

    # Data integrity check
    data = {"mission_id": "MSN-101", "waypoints": [[34.0, 43.0]]}
    integ = governance_engine.verify_data_integrity(data, required_fields=["mission_id", "waypoints"])
    assert integ["compliant"] is True

    # Missing field raises error
    with pytest.raises(GovernanceViolationError):
        governance_engine.verify_data_integrity(data, required_fields=["mission_id", "target_eta"])


def test_self_healing_staged_and_approved_actions():
    """Verify that state-changing self-healing actions require operator sign-off."""
    # 1. Unapproved restart is staged
    staged = self_healing_engine.service_restart(
        service_name="deterministic_sim_engine",
        operator_authorized=False,
    )
    assert staged["status"] == "STAGED_PENDING_APPROVAL"

    # 2. Operator-approved restart executes
    completed = self_healing_engine.service_restart(
        service_name="deterministic_sim_engine",
        operator_authorized=True,
        operator_id="operator_davis",
    )
    assert completed["status"] == "COMPLETED"
    assert completed["approved_by"] == "operator_davis"

    # 3. Cache rebuild executes
    c_res = self_healing_engine.cache_rebuild(namespace="test_healing", operator_id="operator_davis")
    assert c_res["status"] == "COMPLETED"

    # 4. Connection recovery executes
    conn = self_healing_engine.connection_recovery(target="sqlite_primary")
    assert conn["status"] == "COMPLETED"


def test_continuous_validation_suite():
    """Verify that continuous validation engine runs and passes all 5 pillars."""
    report = validation_engine.run_full_validation_suite()
    assert report["suite"] == "CONTINUOUS_VALIDATION_SUITE"
    assert report["status"] == "PASSED"
    assert report["all_passed"] is True
    assert report["golden_run"]["passed"] is True
    assert report["security"]["unauthorized_actions_blocked"] is True
    assert report["api_contracts"]["passed"] is True
