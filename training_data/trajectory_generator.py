"""Trajectory generator with multi-future branching for soft label distribution synthesis."""

from __future__ import annotations
import math
import random
from typing import Any
import numpy as np

from backend.app.simulation.rule_engine import RuleEngine
from .scenario_generator import ScenarioSpec
from .state_generator import StateGenerator, ExtendedPhysicsState


class TrajectoryGenerator:
    """Executes deterministic trajectories and computes multi-future branch distributions."""

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self.state_gen = StateGenerator()
        self.rule_engine = rule_engine if rule_engine is not None else RuleEngine()

    def generate_trajectory(self, spec: ScenarioSpec) -> list[ExtendedPhysicsState]:
        """Runs a complete deterministic trajectory for a scenario specification."""
        current = self.state_gen.initialize_state(spec)
        states = [current]

        heading_delta = 2.5
        for _ in range(1, spec.duration_ticks + 1):
            current = self.state_gen.step_state(
                current, spec, dt_sec=1.0, target_heading_delta_deg=heading_delta
            )
            states.append(current)
            if current.energy.fuel_level_pct <= 0.0 and current.kinematics.speed_mps <= 0.01:
                # Halt state reached
                break
        return states

    def evaluate_multi_future_soft_labels(
        self,
        state: ExtendedPhysicsState,
        spec: ScenarioSpec,
        num_branches: int = 100,
        horizon_ticks: int = 15,
        seed: int = 42,
    ) -> dict[str, dict[str, float] | float]:
        """Evaluates multiple nearby future rollouts to yield empirical soft outcome distributions.

        Perturbs wind, rain, jamming, and engine efficiency deterministically across
        `num_branches` nearby futures to measure the empirical Bayesian outcome distribution.
        """
        rng = np.random.RandomState(seed + (state.tick * 73) + int(state.kinematics.speed_mps * 10))

        # Base current telemetry
        fuel_curr = state.energy.fuel_level_pct
        wear_curr = state.logistics.vehicle_wear_pct
        speed_curr = state.kinematics.speed_mps
        ammo_curr = state.logistics.ammunition_pct
        jamming_curr = state.comms.jamming_intensity
        sig_curr = state.comms.signal_strength_dbm
        deadline = spec.mission_deadline_ticks
        tick_curr = state.tick

        # Perturbation samples for num_branches
        # Deterministic noise draws
        wind_pert = rng.normal(0.0, 4.0, size=num_branches)
        precip_pert = np.maximum(0.0, state.environment.precipitation_mm_hr + rng.normal(0.0, 5.0, size=num_branches))
        jam_pert = np.clip(jamming_curr + rng.normal(0.0, 0.1, size=num_branches), 0.0, 1.0)
        drag_factors = 1.0 + (precip_pert / 100.0)

        # Vectorized lookahead rollouts over horizon_ticks
        # Step consumption over horizon
        effective_speed = np.clip(speed_curr + rng.normal(0.0, 1.5, size=num_branches), 0.0, 30.0)
        burn_rates = (0.01 + (0.001 * effective_speed)) * drag_factors
        future_fuel = np.maximum(0.0, fuel_curr - (burn_rates * horizon_ticks))
        future_wear = np.minimum(100.0, wear_curr + (0.01 * drag_factors * horizon_ticks))

        # Projected arrival tick
        remaining_ticks = np.where(effective_speed > 1.0, (spec.duration_ticks - tick_curr), 999)
        projected_arrival = tick_curr + remaining_ticks

        # Future RF Signal & comms loss
        future_sig = np.clip(sig_curr - (jam_pert * 30.0) - rng.uniform(0.0, 8.0, size=num_branches), -130.0, -30.0)
        future_packet_loss = np.where(future_sig < -105.0, 100.0, jam_pert * 50.0)

        # Classify outcomes across 100 branches
        failed_mask = (future_fuel <= 0.0) | (future_wear >= 98.0)
        aborted_mask = (~failed_mask) & ((jam_pert >= 0.88) & (future_fuel <= 12.0))
        delayed_mask = (~failed_mask) & (~aborted_mask) & (projected_arrival > deadline)
        success_mask = (~failed_mask) & (~aborted_mask) & (~delayed_mask)

        p_success = float(np.mean(success_mask))
        p_delayed = float(np.mean(delayed_mask))
        p_aborted = float(np.mean(aborted_mask))
        p_failed = float(np.mean(failed_mask))

        # Operational state distribution
        op_failed = (future_fuel <= 0.0) | (future_wear >= 98.0)
        op_critical = (~op_failed) & ((future_fuel <= 15.0) | (future_sig <= -115.0) | (future_wear >= 85.0))
        op_degraded = (~op_failed) & (~op_critical) & ((future_fuel <= 40.0) | (future_sig <= -90.0) | (future_wear >= 50.0))
        op_normal = (~op_failed) & (~op_critical) & (~op_degraded)

        p_op_normal = float(np.mean(op_normal))
        p_op_degraded = float(np.mean(op_degraded))
        p_op_critical = float(np.mean(op_critical))
        p_op_failed = float(np.mean(op_failed))

        # Recommended action distribution
        act_abort = op_failed
        act_resupply = (~act_abort) & ((future_fuel <= 15.0) | (future_wear >= 85.0))
        act_pause = (~act_abort) & (~act_resupply) & ((future_sig <= -115.0) | (precip_pert > 45.0))
        act_reroute = (~act_abort) & (~act_resupply) & (~act_pause) & (precip_pert > 25.0)
        act_continue = (~act_abort) & (~act_resupply) & (~act_pause) & (~act_reroute)

        p_act_continue = float(np.mean(act_continue))
        p_act_reroute = float(np.mean(act_reroute))
        p_act_resupply = float(np.mean(act_resupply))
        p_act_pause = float(np.mean(act_pause))
        p_act_abort = float(np.mean(act_abort))

        # Logistics state distribution
        log_critical = (future_fuel <= 5.0) | (future_wear >= 85.0) | (ammo_curr <= 5.0)
        log_resupply = (~log_critical) & ((future_fuel <= 20.0) | (future_wear >= 70.0) | (ammo_curr <= 25.0))
        log_low = (~log_critical) & (~log_resupply) & ((future_fuel <= 45.0) | (future_wear >= 45.0) | (ammo_curr <= 50.0))
        log_healthy = (~log_critical) & (~log_resupply) & (~log_low)

        p_log_healthy = float(np.mean(log_healthy))
        p_log_low = float(np.mean(log_low))
        p_log_resupply = float(np.mean(log_resupply))
        p_log_critical = float(np.mean(log_critical))

        # Comms state distribution
        comm_lost = (future_sig <= -115.0) | (future_packet_loss >= 95.0)
        comm_interm = (~comm_lost) & ((future_sig <= -95.0) | (future_packet_loss >= 40.0))
        comm_deg = (~comm_lost) & (~comm_interm) & ((future_sig <= -80.0) | (future_packet_loss >= 10.0))
        comm_conn = (~comm_lost) & (~comm_interm) & (~comm_deg)

        p_comm_conn = float(np.mean(comm_conn))
        p_comm_deg = float(np.mean(comm_deg))
        p_comm_interm = float(np.mean(comm_interm))
        p_comm_lost = float(np.mean(comm_lost))

        # Expected risk score
        risk_samples = (
            (1.0 - (future_fuel / 100.0)) * 0.35
            + (future_wear / 100.0) * 0.25
            + (jam_pert) * 0.20
            + (precip_pert / 80.0) * 0.20
        )
        avg_risk = float(np.clip(np.mean(risk_samples), 0.0, 1.0))

        # Normalize probability vectors to strictly sum to 1.0
        def norm_dict(d: dict[str, float]) -> dict[str, float]:
            tot = sum(d.values())
            if tot <= 1e-9:
                k = list(d.keys())[0]
                return {x: (1.0 if x == k else 0.0) for x in d}
            return {k: round(v / tot, 4) for k, v in d.items()}

        return {
            "mission_outcome": norm_dict({
                "SUCCESS": p_success,
                "DELAYED": p_delayed,
                "ABORTED": p_aborted,
                "FAILED": p_failed,
            }),
            "operational_state": norm_dict({
                "NORMAL": p_op_normal,
                "DEGRADED": p_op_degraded,
                "CRITICAL": p_op_critical,
                "FAILED": p_op_failed,
            }),
            "recommended_action": norm_dict({
                "CONTINUE": p_act_continue,
                "REROUTE": p_act_reroute,
                "RESUPPLY": p_act_resupply,
                "PAUSE": p_act_pause,
                "ABORT": p_act_abort,
            }),
            "logistics_state": norm_dict({
                "HEALTHY": p_log_healthy,
                "LOW_RESERVE": p_log_low,
                "RESUPPLY_REQUIRED": p_log_resupply,
                "CRITICAL": p_log_critical,
            }),
            "comms_state": norm_dict({
                "CONNECTED": p_comm_conn,
                "DEGRADED": p_comm_deg,
                "INTERMITTENT": p_comm_interm,
                "LOST": p_comm_lost,
            }),
            "risk_score": round(avg_risk, 4),
        }
