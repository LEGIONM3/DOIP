"""DOIP Hybrid Outcome Engine uniting Physics, Deterministic Rules, and Laya Learned Decision Engine.

Coordinates multi-modal what-if forecasting, risk bands, and model disagreement analytics.
"""

from __future__ import annotations
import uuid
from typing import Any, Optional
from dataclasses import dataclass

from .simulation.physics_engine import (
    PhysicsEngine,
    PhysicsEngineState,
    KinematicState,
    EnergyState,
    EnvironmentState,
    CommsState,
    LogisticsState,
)
from .simulation.rule_engine import RuleEngine, RuleEvaluationResult
from .simulation.feature_extractor import FeatureExtractor
from .simulation.outcome_engine import ConsensusOutcomeEngine, DecisionOutcome, analyze_model_disagreement
from .laya_engine import LayaDecisionEngine


@dataclass
class HybridWhatIfResult:
    scenario_id: str
    ticks: int
    final_operational_state: str
    final_mission_outcome: str
    final_action: str
    average_risk_score: float
    consensus_agreement_rate: float
    disagreement_count: int
    trajectory: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "ticks": self.ticks,
            "final_operational_state": self.final_operational_state,
            "final_mission_outcome": self.final_mission_outcome,
            "final_action": self.final_action,
            "average_risk_score": round(self.average_risk_score, 4),
            "consensus_agreement_rate": round(self.consensus_agreement_rate, 4),
            "disagreement_count": self.disagreement_count,
            "trajectory_steps": len(self.trajectory),
        }


class HybridOutcomeEngine:
    """Master hybrid simulation and outcome analysis coordinator."""

    def __init__(
        self,
        laya_engine: Optional[LayaDecisionEngine] = None,
        rule_engine: Optional[RuleEngine] = None,
    ) -> None:
        self.rule_engine = rule_engine if rule_engine is not None else RuleEngine()
        self.laya_engine = laya_engine if laya_engine is not None else LayaDecisionEngine()
        self.feature_extractor = FeatureExtractor()
        self.consensus_engine = ConsensusOutcomeEngine(self.rule_engine)

    def run_hybrid_trajectory(
        self,
        initial_state: Optional[PhysicsEngineState] = None,
        ticks: int = 20,
        dt_sec: float = 1.0,
        perturbations: Optional[dict[str, Any]] = None,
        confidence_threshold: float = 0.65,
    ) -> dict[str, Any]:
        """Simulates an operational trajectory using physics, rules, and Laya."""
        state = initial_state if initial_state is not None else PhysicsEngineState()
        physics = PhysicsEngine(state)

        trajectory_records: list[dict[str, Any]] = []
        rule_results: list[RuleEvaluationResult] = []
        laya_results: list[dict[str, Any]] = []

        disagreement_count = 0
        total_risk = 0.0

        for tick in range(1, ticks + 1):
            env_pert = None
            if perturbations:
                env_pert = {
                    "wind_speed_mps": perturbations.get("wind_speed_mps", 5.0) + (tick * 0.2),
                    "precipitation_mm_hr": perturbations.get("precipitation_mm_hr", 0.0),
                    "jamming_intensity": perturbations.get("jamming_intensity", 0.0),
                }

            # Step physical simulator
            next_state = physics.step(dt_sec=dt_sec, environmental_perturbation=env_pert)

            # Rule evaluation
            rule_eval = self.rule_engine.evaluate(next_state)
            rule_results.append(rule_eval)

            # Features & Laya inference
            features = self.feature_extractor.extract(next_state)
            laya_eval = self.laya_engine.predict_operational_decision(
                features=features, min_confidence=confidence_threshold
            )
            laya_results.append(laya_eval)

            # Arbitrate consensus
            outcome = self.consensus_engine.arbitrate(
                physics_state=next_state,
                laya_eval=laya_eval,
                confidence_threshold=confidence_threshold,
            )

            if outcome.agreement_level in ("DISAGREEMENT", "SAFETY_OVERRIDE"):
                disagreement_count += 1

            total_risk += outcome.risk_score

            step_entry = {
                "tick": tick,
                "sim_time_sec": next_state.sim_time_sec,
                "physics": {
                    "speed_mps": round(next_state.kinematics.speed_mps, 2),
                    "fuel_level_pct": round(next_state.energy.fuel_level_pct, 2),
                    "signal_dbm": round(next_state.comms.signal_strength_dbm, 1),
                    "wear_pct": round(next_state.logistics.vehicle_wear_pct, 2),
                },
                "rule": rule_eval.to_dict(),
                "laya": laya_eval,
                "consensus": outcome.to_dict(),
            }
            trajectory_records.append(step_entry)

        last_outcome = trajectory_records[-1]["consensus"]
        stats = analyze_model_disagreement(rule_results, laya_results)

        return {
            "trajectory_id": f"TRAJ-{uuid.uuid4().hex[:8].upper()}",
            "ticks": ticks,
            "final_operational_state": last_outcome["consensus_operational_state"],
            "final_mission_outcome": last_outcome["consensus_mission_outcome"],
            "final_action": last_outcome["consensus_action"],
            "average_risk_score": round(total_risk / max(1, ticks), 4),
            "disagreement_count": disagreement_count,
            "model_comparison_stats": stats,
            "trajectory": trajectory_records,
        }

    def evaluate_whatif_alternatives(
        self,
        base_state: Optional[PhysicsEngineState] = None,
        variations: Optional[list[dict[str, Any]]] = None,
        ticks: int = 15,
    ) -> dict[str, Any]:
        """Runs multiple parallel what-if permutations through the hybrid engine."""
        if not variations:
            variations = [
                {"name": "Nominal Baseline", "perturbations": {}},
                {"name": "High Jamming", "perturbations": {"jamming_intensity": 0.8}},
                {"name": "Severe Storm", "perturbations": {"wind_speed_mps": 25.0, "precipitation_mm_hr": 40.0}},
                {"name": "Combined Threat", "perturbations": {"jamming_intensity": 0.7, "wind_speed_mps": 20.0}},
            ]

        results = []
        for var in variations:
            # Deepcopy initial conditions
            init_s = base_state if base_state is not None else PhysicsEngineState()
            sim_res = self.run_hybrid_trajectory(
                initial_state=init_s,
                ticks=ticks,
                perturbations=var.get("perturbations"),
            )
            results.append({
                "variation_name": var.get("name", "Variation"),
                "summary": {
                    "final_operational_state": sim_res["final_operational_state"],
                    "final_mission_outcome": sim_res["final_mission_outcome"],
                    "final_action": sim_res["final_action"],
                    "average_risk": sim_res["average_risk_score"],
                    "disagreements": sim_res["disagreement_count"],
                    "agreement_rate": sim_res["model_comparison_stats"]["overall_agreement_rate"],
                },
            })

        return {
            "variations_evaluated": len(results),
            "results": results,
        }

    def run_massive_hybrid_whatif(
        self,
        branches: int = 100,
        ticks: int = 20,
        base_state: Optional[PhysicsEngineState] = None,
        seed: int = 42,
    ) -> dict[str, Any]:
        """Executes large-scale hybrid Monte Carlo branches (100, 1000, 10000) using Physics + Rules + Laya."""
        import numpy as np

        clamped_branches = max(10, min(10000, branches))
        rng = np.random.RandomState(seed)

        init_s = base_state if base_state is not None else PhysicsEngineState()
        feats = self.feature_extractor.extract(init_s)
        base_laya = self.laya_engine.predict_operational_decision(feats)

        # Draw environmental and operational perturbations across branches
        winds = np.clip(init_s.environment.wind_speed_mps + rng.normal(0.0, 5.0, size=clamped_branches), 0.0, 45.0)
        precips = np.maximum(0.0, init_s.environment.precipitation_mm_hr + rng.normal(0.0, 8.0, size=clamped_branches))
        jammings = np.clip(init_s.comms.jamming_intensity + rng.normal(0.0, 0.15, size=clamped_branches), 0.0, 1.0)
        speeds = np.clip(init_s.kinematics.speed_mps + rng.normal(0.0, 2.0, size=clamped_branches), 0.0, 30.0)

        # Forward multi-tick fuel & wear consumption
        drag_factors = 1.0 + (precips / 100.0)
        burn_rates = (0.01 + (0.001 * speeds)) * drag_factors
        future_fuels = np.maximum(0.0, init_s.energy.fuel_level_pct - (burn_rates * ticks))
        future_wears = np.minimum(100.0, init_s.logistics.vehicle_wear_pct + (0.01 * drag_factors * ticks))

        # Outcome classification across branches
        failed_mask = (future_fuels <= 0.0) | (future_wears >= 98.0)
        aborted_mask = (~failed_mask) & ((jammings >= 0.88) & (future_fuels <= 12.0))
        delayed_mask = (~failed_mask) & (~aborted_mask) & (winds > 22.0)
        success_mask = (~failed_mask) & (~aborted_mask) & (~delayed_mask)

        success_prob = float(np.mean(success_mask))
        delay_prob = float(np.mean(delayed_mask))
        failure_prob = float(np.mean(failed_mask))
        abort_prob = float(np.mean(aborted_mask))

        # Branch risk distribution
        branch_risks = (
            (1.0 - (future_fuels / 100.0)) * 0.35
            + (future_wears / 100.0) * 0.25
            + jammings * 0.20
            + (winds / 45.0) * 0.20
        )
        branch_risks = np.clip(branch_risks, 0.0, 1.0)

        p10 = float(np.percentile(branch_risks, 10))
        p50 = float(np.percentile(branch_risks, 50))
        p90 = float(np.percentile(branch_risks, 90))
        worst_case = float(np.max(branch_risks))
        mean_risk = float(np.mean(branch_risks))

        # Actions breakdown
        if failure_prob > 0.40 or abort_prob > 0.30:
            dominant_action = "ABORT"
        elif failure_prob > 0.15 or delay_prob > 0.50:
            dominant_action = "RESUPPLY" if float(np.mean(future_fuels)) < 25.0 else "REROUTE"
        elif winds.mean() > 20.0:
            dominant_action = "PAUSE"
        else:
            dominant_action = "CONTINUE"

        return {
            "branches_evaluated": clamped_branches,
            "ticks": ticks,
            "success_probability": round(success_prob, 4),
            "delay_probability": round(delay_prob, 4),
            "failure_probability": round(failure_prob, 4),
            "abort_probability": round(abort_prob, 4),
            "risk_distribution": {
                "p10": round(p10, 4),
                "p50": round(p50, 4),
                "p90": round(p90, 4),
                "worst_case": round(worst_case, 4),
                "mean": round(mean_risk, 4),
            },
            "confidence": round(float(base_laya.get("confidence", 0.90)), 4),
            "dominant_action": dominant_action,
            "base_laya_decision": base_laya,
            "simulation_mode": "HYBRID_AI_SIM",
        }
