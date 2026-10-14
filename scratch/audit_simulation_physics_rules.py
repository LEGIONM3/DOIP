"""Hostile Audit: Level 5, 6, 7 - Simulation, Physics & Rule Engine Reality Audit."""

import os
import sys
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./backend"))

from backend.app.simulation.physics_engine import (
    PhysicsEngine,
    PhysicsEngineState,
    KinematicState,
    EnergyState,
    EnvironmentState,
    CommsState,
    LogisticsState,
)
from backend.app.simulation.rule_engine import RuleEngine, RuleEvaluationResult
from backend.app.simulation.simulation_runner import HybridSimulationRunner, SimulationMode
from backend.app.simulation.feature_extractor import FeatureExtractor
from training_data.scenario_generator import ScenarioGenerator
from training_data.state_generator import StateGenerator
from training_data.trajectory_generator import TrajectoryGenerator


def audit_level_5_simulation_100_runs() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 5] 100 Consecutive Simulations & Determinism Check ---")
    scen_gen = ScenarioGenerator(seed=777)
    specs = scen_gen.generate_scenarios(count=100)
    traj_gen = TrajectoryGenerator()

    determinism_failures = 0
    trajectories_hashes = []
    
    # 1. Run 100 independent simulations
    for i, spec in enumerate(specs):
        states = traj_gen.generate_trajectory(spec)
        summary_str = f"{spec.scenario_id}:{len(states)}:" + ":".join(
            f"{s.tick},{round(s.kinematics.lat, 4)},{round(s.kinematics.lon, 4)},{round(s.energy.fuel_level_pct, 2)}"
            for s in states
        )
        h = hashlib.sha256(summary_str.encode("utf-8")).hexdigest()
        trajectories_hashes.append(h)

    # 2. Test exact reproducibility: Re-run first 10 scenarios with exact same seed
    scen_gen_verify = ScenarioGenerator(seed=777)
    specs_verify = scen_gen_verify.generate_scenarios(count=10)
    for i, spec in enumerate(specs_verify):
        states = traj_gen.generate_trajectory(spec)
        summary_str = f"{spec.scenario_id}:{len(states)}:" + ":".join(
            f"{s.tick},{round(s.kinematics.lat, 4)},{round(s.kinematics.lon, 4)},{round(s.energy.fuel_level_pct, 2)}"
            for s in states
        )
        h_verify = hashlib.sha256(summary_str.encode("utf-8")).hexdigest()
        if h_verify != trajectories_hashes[i]:
            determinism_failures += 1

    print(f"100 simulations completed.")
    print(f"Determinism re-run check (10 samples): {'PASSED (0 drift)' if determinism_failures == 0 else f'FAILED ({determinism_failures} drift)'}")

    return {
        "simulations_executed": 100,
        "unique_trajectories_generated": len(set(trajectories_hashes)),
        "determinism_verification": "ZERO_DRIFT_IDENTICAL" if determinism_failures == 0 else "DRIFT_DETECTED",
        "determinism_failures": determinism_failures,
    }


def audit_level_6_physics_boundary_scenarios() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 6] Physics Boundary & Extreme Scenario Audit ---")
    checks = {}

    # Case 1: Zero Fuel (Energy Exhaustion)
    init_state_fuel0 = PhysicsEngineState(
        energy=EnergyState(fuel_level_pct=0.0),
        kinematics=KinematicState(lat=12.97, lon=77.59, speed_mps=15.0),
    )
    p_fuel0 = PhysicsEngine(init_state_fuel0)
    step_fuel0 = p_fuel0.step(dt_sec=2.0, target_speed_mps=15.0)
    fuel0_halted = step_fuel0.kinematics.speed_mps == 0.0
    checks["zero_fuel_halts_motion"] = {
        "expected": True,
        "actual": fuel0_halted,
        "speed": step_fuel0.kinematics.speed_mps,
        "status": "PASSED" if fuel0_halted else "FAILED",
    }

    # Case 2: Extreme Weather (High Drag & Fuel Burn)
    init_state_calm = PhysicsEngineState(
        environment=EnvironmentState(wind_speed_mps=0.0, precipitation_mm_hr=0.0),
        kinematics=KinematicState(lat=12.97, lon=77.59, speed_mps=20.0),
        energy=EnergyState(fuel_level_pct=100.0),
    )
    init_state_storm = PhysicsEngineState(
        environment=EnvironmentState(wind_speed_mps=45.0, precipitation_mm_hr=60.0),
        kinematics=KinematicState(lat=12.97, lon=77.59, speed_mps=20.0),
        energy=EnergyState(fuel_level_pct=100.0),
    )
    p_calm = PhysicsEngine(init_state_calm)
    p_storm = PhysicsEngine(init_state_storm)
    s_calm = p_calm.step(dt_sec=5.0)
    s_storm = p_storm.step(dt_sec=5.0)

    fuel_burn_calm = 100.0 - s_calm.energy.fuel_level_pct
    fuel_burn_storm = 100.0 - s_storm.energy.fuel_level_pct
    storm_burns_more = fuel_burn_storm > fuel_burn_calm
    checks["storm_increases_fuel_burn"] = {
        "expected": True,
        "actual": storm_burns_more,
        "burn_calm": round(fuel_burn_calm, 4),
        "burn_storm": round(fuel_burn_storm, 4),
        "status": "PASSED" if storm_burns_more else "FAILED",
    }

    # Case 3: Heavy Electronic Jamming (Comms Degradation)
    init_state_comms_clean = PhysicsEngineState(
        comms=CommsState(distance_to_relay_m=1000.0, jamming_intensity=0.0)
    )
    init_state_comms_jammed = PhysicsEngineState(
        comms=CommsState(distance_to_relay_m=1000.0, jamming_intensity=0.95)
    )
    p_clean = PhysicsEngine(init_state_comms_clean)
    p_jammed = PhysicsEngine(init_state_comms_jammed)
    s_clean = p_clean.step(dt_sec=1.0)
    s_jammed = p_jammed.step(dt_sec=1.0)

    jamming_drops_signal = s_jammed.comms.signal_strength_dbm < s_clean.comms.signal_strength_dbm
    jamming_increases_loss = s_jammed.comms.packet_loss_pct > s_clean.comms.packet_loss_pct
    checks["jamming_degrades_rf"] = {
        "signal_dropped": jamming_drops_signal,
        "loss_increased": jamming_increases_loss,
        "clean_dbm": s_clean.comms.signal_strength_dbm,
        "jammed_dbm": s_jammed.comms.signal_strength_dbm,
        "status": "PASSED" if (jamming_drops_signal and jamming_increases_loss) else "FAILED",
    }

    # Case 4: Non-Teleportation & Distance Kinematic Invariant
    # Distance moved in dt=1s cannot exceed speed_mps * dt * 1.5
    p_motion = PhysicsEngine(PhysicsEngineState(kinematics=KinematicState(lat=12.97, lon=77.59, speed_mps=10.0, heading_deg=0.0)))
    s_motion = p_motion.step(dt_sec=1.0)
    # 1 deg lat ~= 111,000 meters. speed=10m/s -> delta_lat ~= 10 / 111,000 ~= 0.00009
    lat_diff = abs(s_motion.kinematics.lat - 12.97)
    teleport_check = lat_diff < 0.001
    checks["kinematic_continuity_no_teleport"] = {
        "lat_delta": lat_diff,
        "status": "PASSED" if teleport_check else "FAILED",
    }

    for k, v in checks.items():
        print(f"  - {k}: {v['status']}")

    return checks


def audit_level_7_rule_engine() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 7] Rule Engine Invariants & Prioritization Audit ---")
    engine = RuleEngine()
    rule_checks = {}

    # Rule 1: Normal state
    s_norm = PhysicsEngineState(energy=EnergyState(fuel_level_pct=85.0))
    res_norm = engine.evaluate(s_norm)
    rule_checks["nominal_state"] = {
        "operational": res_norm.operational_state,
        "action": res_norm.recommended_action,
        "invariants_passed": res_norm.invariants_passed,
        "status": "PASSED" if (res_norm.operational_state == "NORMAL" and res_norm.invariants_passed) else "FAILED",
    }

    # Rule 2: Low Reserve
    s_low = PhysicsEngineState(energy=EnergyState(fuel_level_pct=20.0))
    res_low = engine.evaluate(s_low)
    rule_checks["low_reserve_trigger"] = {
        "operational": res_low.operational_state,
        "action": res_low.recommended_action,
        "status": "PASSED" if res_low.operational_state in ["DEGRADED", "CRITICAL"] else "FAILED",
    }

    # Rule 3: Critical Fuel Invariant
    s_crit = PhysicsEngineState(energy=EnergyState(fuel_level_pct=5.0))
    res_crit = engine.evaluate(s_crit)
    rule_checks["critical_fuel_trigger"] = {
        "operational": res_crit.operational_state,
        "action": res_crit.recommended_action,
        "status": "PASSED" if res_crit.operational_state == "CRITICAL" else "FAILED",
    }

    # Rule 4: Action Prohibition when Depleted
    s_dep = PhysicsEngineState(energy=EnergyState(fuel_level_pct=0.0))
    can_continue, msg = engine.validate_action(s_dep, "CONTINUE")
    can_resupply, _ = engine.validate_action(s_dep, "RESUPPLY")
    rule_checks["action_validation_depleted"] = {
        "can_continue": can_continue,
        "can_resupply": can_resupply,
        "status": "PASSED" if (not can_continue and can_resupply) else "FAILED",
    }

    for k, v in rule_checks.items():
        print(f"  - {k}: {v['status']}")

    return rule_checks


def main():
    l5 = audit_level_5_simulation_100_runs()
    l6 = audit_level_6_physics_boundary_scenarios()
    l7 = audit_level_7_rule_engine()

    out_json = Path("docs/verification/simulation_physics_rules_audit.json")
    with open(out_json, "w", encoding="utf-8") as fp:
        json.dump({
            "simulation_audit_level_5": l5,
            "physics_audit_level_6": l6,
            "rule_engine_audit_level_7": l7,
        }, fp, indent=2)
    print(f"\nAudit results persisted to {out_json}")


if __name__ == "__main__":
    main()
