"""Simulation runner providing unified execution for DETERMINISTIC_SIM and HYBRID_AI_SIM modes."""

from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from .physics_engine import PhysicsEngine, PhysicsEngineState
from .rule_engine import RuleEngine, RuleEvaluationResult
from .feature_extractor import FeatureExtractor, SimulationFeatures
from .state_transition import StateTransitionValidator, TransitionValidationResult
from .outcome_engine import ConsensusOutcomeEngine, DecisionOutcome


class SimulationMode(str, Enum):
    DETERMINISTIC_SIM = "DETERMINISTIC_SIM"
    HYBRID_AI_SIM = "HYBRID_AI_SIM"


class HybridSimulationRunner:
    """Manages operational simulation runs in both deterministic and hybrid AI modes."""

    def __init__(
        self,
        initial_state: Optional[PhysicsEngineState] = None,
        laya_engine: Optional[Any] = None,
        mode: SimulationMode = SimulationMode.HYBRID_AI_SIM,
        confidence_threshold: float = 0.65,
    ) -> None:
        self.physics = PhysicsEngine(initial_state)
        self.rule_engine = RuleEngine()
        self.feature_extractor = FeatureExtractor()
        self.validator = StateTransitionValidator(self.rule_engine)
        self.outcome_engine = ConsensusOutcomeEngine(self.rule_engine)
        self.laya_engine = laya_engine
        self.mode = mode
        self.confidence_threshold = confidence_threshold
        self.history: list[dict[str, Any]] = []

    def set_mode(self, mode: SimulationMode) -> None:
        self.mode = mode

    def step(
        self,
        dt_sec: float = 1.0,
        target_speed_mps: Optional[float] = None,
        target_heading_deg: Optional[float] = None,
        environmental_perturbation: Optional[dict[str, float]] = None,
    ) -> dict[str, Any]:
        """Executes one simulation step according to the configured mode."""
        # 1. Authoritative physical state evolution
        next_phys_state = self.physics.step(
            dt_sec=dt_sec,
            target_speed_mps=target_speed_mps,
            target_heading_deg=target_heading_deg,
            environmental_perturbation=environmental_perturbation,
        )

        # 2. Authoritative rule evaluation
        rule_eval: RuleEvaluationResult = self.rule_engine.evaluate(next_phys_state)

        # 3. Deterministic feature extraction
        features: SimulationFeatures = self.feature_extractor.extract(next_phys_state)

        laya_eval: Optional[dict[str, Any]] = None
        validation_result: Optional[TransitionValidationResult] = None

        if self.mode == SimulationMode.HYBRID_AI_SIM and self.laya_engine is not None:
            # 4. Learned decision model evaluation
            laya_eval = self.laya_engine.predict_operational_decision(
                features=features,
                min_confidence=self.confidence_threshold,
            )

            # 5. Rule-validated state transition invariant gating
            passed_gate = not bool(laya_eval.get("abstained", False))
            validation_result = self.validator.validate_and_apply(
                current_state=next_phys_state,
                laya_decision=laya_eval,
                confidence_gate_passed=passed_gate,
            )
        else:
            validation_result = TransitionValidationResult(
                action_accepted=True,
                final_action=rule_eval.recommended_action,
                decision_source="RULE_ENGINE",
                validation_status="ACCEPTED",
                reason="Deterministic simulation mode active; authoritative rule engine selected.",
                audit_trace={"rule_eval": rule_eval.to_dict()},
            )

        # 6. Consensus & outcome arbitration
        outcome: DecisionOutcome = self.outcome_engine.arbitrate(
            physics_state=next_phys_state,
            laya_eval=laya_eval,
            confidence_threshold=self.confidence_threshold,
        )

        step_record = {
            "tick": next_phys_state.tick,
            "sim_time_sec": next_phys_state.sim_time_sec,
            "mode": self.mode.value,
            "physics_state": next_phys_state.to_dict(),
            "rule_evaluation": rule_eval.to_dict(),
            "features": features.to_dict(),
            "laya_decision": laya_eval,
            "validation_result": validation_result.to_dict(),
            "consensus_outcome": outcome.to_dict(),
        }

        self.history.append(step_record)
        return step_record

    def run_ticks(self, num_ticks: int = 10, dt_sec: float = 1.0) -> list[dict[str, Any]]:
        """Runs the simulation forward for num_ticks steps."""
        results = []
        for _ in range(num_ticks):
            step_data = self.step(dt_sec=dt_sec)
            results.append(step_data)
        return results
