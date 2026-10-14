"""Generates authoritative ground-truth labels for states using RuleEngine."""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from backend.app.simulation.physics_engine import PhysicsEngineState
from backend.app.simulation.rule_engine import RuleEngine, RuleEvaluationResult


@dataclass
class GroundTruthLabel:
    operational_state: str
    mission_outcome: str
    logistics_state: str
    comms_state: str
    environmental_impact: str
    recommended_action: str
    risk_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LabelGenerator:
    """Produces verified ground-truth labels from authoritative rule engine evaluations."""

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self.rule_engine = rule_engine if rule_engine is not None else RuleEngine()

    def generate_label(self, state: PhysicsEngineState) -> GroundTruthLabel:
        """Evaluates state against deterministic rules to yield ground truth label."""
        eval_res: RuleEvaluationResult = self.rule_engine.evaluate(state)
        return GroundTruthLabel(
            operational_state=eval_res.operational_state,
            mission_outcome=eval_res.mission_outcome,
            logistics_state=eval_res.logistics_state,
            comms_state=eval_res.comms_state,
            environmental_impact=eval_res.environmental_impact,
            recommended_action=eval_res.recommended_action,
            risk_score=round(eval_res.rule_risk_score, 4),
        )
