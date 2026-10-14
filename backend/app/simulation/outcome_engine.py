"""Consensus and outcome arbitration engine comparing Physics, Rules, and Laya decisions."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from .physics_engine import PhysicsEngineState
from .rule_engine import RuleEngine, RuleEvaluationResult


@dataclass
class DecisionOutcome:
    consensus_operational_state: str
    consensus_mission_outcome: str
    consensus_action: str
    risk_score: float
    confidence: float
    agreement_level: str  # FULL_CONSENSUS | PARTIAL_CONSENSUS | DISAGREEMENT | SAFETY_OVERRIDE
    rule_result: dict[str, Any]
    laya_result: Optional[dict[str, Any]]
    disagreement_details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "consensus_operational_state": self.consensus_operational_state,
            "consensus_mission_outcome": self.consensus_mission_outcome,
            "consensus_action": self.consensus_action,
            "risk_score": round(self.risk_score, 4),
            "confidence": round(self.confidence, 4),
            "agreement_level": self.agreement_level,
            "rule_result": self.rule_result,
            "laya_result": self.laya_result,
            "disagreement_details": self.disagreement_details,
        }


class ConsensusOutcomeEngine:
    """Arbitrates multi-modal operational decisions between Physics, Rules, and Laya."""

    def __init__(self, rule_engine: Optional[RuleEngine] = None) -> None:
        self.rule_engine = rule_engine if rule_engine is not None else RuleEngine()

    def arbitrate(
        self,
        physics_state: PhysicsEngineState,
        laya_eval: Optional[dict[str, Any]],
        confidence_threshold: float = 0.65,
    ) -> DecisionOutcome:
        """Arbitrates between authoritative rule evaluation and learned Laya output."""
        rule_eval: RuleEvaluationResult = self.rule_engine.evaluate(physics_state)
        rule_dict = rule_eval.to_dict()

        if laya_eval is None:
            return DecisionOutcome(
                consensus_operational_state=rule_eval.operational_state,
                consensus_mission_outcome=rule_eval.mission_outcome,
                consensus_action=rule_eval.recommended_action,
                risk_score=rule_eval.rule_risk_score,
                confidence=1.0,
                agreement_level="FULL_CONSENSUS",
                rule_result=rule_dict,
                laya_result=None,
                disagreement_details=["Laya not present; 100% authoritative rule decision."],
            )

        laya_conf = float(laya_eval.get("confidence", 0.85))
        laya_abstained = (
            bool(laya_eval.get("abstained", False))
            or (laya_conf < confidence_threshold)
            or laya_eval.get("operational_state") == "UNCERTAIN"
            or laya_eval.get("recommended_action") == "UNCERTAIN"
        )

        # Active Learning & Disagreement Logging
        try:
            from .disagreement_engine import analyze_disagreement
            from .active_learning import collect_hard_examples
            analyze_disagreement(physics_state, rule_eval, laya_eval)
            collect_hard_examples(physics_state, rule_eval, laya_eval)
        except Exception:
            pass

        if laya_abstained:
            return DecisionOutcome(
                consensus_operational_state=rule_eval.operational_state,
                consensus_mission_outcome=rule_eval.mission_outcome,
                consensus_action=rule_eval.recommended_action,
                risk_score=rule_eval.rule_risk_score,
                confidence=laya_conf,
                agreement_level="SAFETY_OVERRIDE",
                rule_result=rule_dict,
                laya_result=laya_eval,
                disagreement_details=[
                    f"Laya output UNCERTAIN (conf={laya_conf:.2f} < threshold={confidence_threshold:.2f}). Authoritative Rule Engine took over."
                ],
            )

        laya_op = laya_eval.get("operational_state", rule_eval.operational_state)
        laya_outcome = laya_eval.get("mission_outcome", rule_eval.mission_outcome)
        laya_action = laya_eval.get("recommended_action", rule_eval.recommended_action)
        laya_risk = float(laya_eval.get("risk_score", rule_eval.rule_risk_score))

        disagreements = []
        if laya_op != rule_eval.operational_state:
            disagreements.append(f"Operational State: Rule={rule_eval.operational_state} vs Laya={laya_op}")
        if laya_outcome != rule_eval.mission_outcome:
            disagreements.append(f"Mission Outcome: Rule={rule_eval.mission_outcome} vs Laya={laya_outcome}")
        if laya_action != rule_eval.recommended_action:
            disagreements.append(f"Action: Rule={rule_eval.recommended_action} vs Laya={laya_action}")

        risk_diff = abs(laya_risk - rule_eval.rule_risk_score)
        if risk_diff > 0.25:
            disagreements.append(f"Risk Score divergence: Rule={rule_eval.rule_risk_score:.2f} vs Laya={laya_risk:.2f} (diff={risk_diff:.2f})")

        # Invariant check: if rules say FAILED, Laya cannot override to SUCCESS/NORMAL
        if rule_eval.operational_state == "FAILED" and laya_op != "FAILED":
            disagreements.append("CRITICAL: Rule invariant FAILED triggered, overruling optimistic Laya assessment")
            return DecisionOutcome(
                consensus_operational_state="FAILED",
                consensus_mission_outcome="FAILED",
                consensus_action="ABORT",
                risk_score=1.0,
                confidence=laya_conf,
                agreement_level="SAFETY_OVERRIDE",
                rule_result=rule_dict,
                laya_result=laya_eval,
                disagreement_details=disagreements,
            )

        if len(disagreements) == 0:
            agreement_level = "FULL_CONSENSUS"
            consensus_op = rule_eval.operational_state
            consensus_outcome = rule_eval.mission_outcome
            consensus_action = rule_eval.recommended_action
            consensus_risk = (rule_eval.rule_risk_score + laya_risk) / 2.0
        elif len(disagreements) <= 2 and not any("CRITICAL" in d for d in disagreements):
            agreement_level = "PARTIAL_CONSENSUS"
            # In partial consensus, Laya's nuanced risk weighting is factored in
            consensus_op = laya_op
            consensus_outcome = laya_outcome
            consensus_action = laya_action
            consensus_risk = (rule_eval.rule_risk_score * 0.4) + (laya_risk * 0.6)
        else:
            agreement_level = "DISAGREEMENT"
            # On major disagreement, prefer safer option
            consensus_op = rule_eval.operational_state
            consensus_outcome = rule_eval.mission_outcome
            consensus_action = rule_eval.recommended_action
            consensus_risk = max(rule_eval.rule_risk_score, laya_risk)

        return DecisionOutcome(
            consensus_operational_state=consensus_op,
            consensus_mission_outcome=consensus_outcome,
            consensus_action=consensus_action,
            risk_score=consensus_risk,
            confidence=laya_conf,
            agreement_level=agreement_level,
            rule_result=rule_dict,
            laya_result=laya_eval,
            disagreement_details=disagreements,
        )


def analyze_model_disagreement(
    rule_results: list[RuleEvaluationResult],
    laya_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Computes aggregate statistical disagreement metrics between rule and learned models."""
    n = min(len(rule_results), len(laya_results))
    if n == 0:
        return {"sample_count": 0, "agreement_rate": 1.0}

    op_matches = 0
    outcome_matches = 0
    action_matches = 0
    risk_diffs: list[float] = []

    for r, l in zip(rule_results[:n], laya_results[:n]):
        if r.operational_state == l.get("operational_state"):
            op_matches += 1
        if r.mission_outcome == l.get("mission_outcome"):
            outcome_matches += 1
        if r.recommended_action == l.get("recommended_action"):
            action_matches += 1
        risk_diffs.append(abs(r.rule_risk_score - float(l.get("risk_score", r.rule_risk_score))))

    return {
        "sample_count": n,
        "operational_state_agreement": round(op_matches / n, 4),
        "mission_outcome_agreement": round(outcome_matches / n, 4),
        "action_agreement": round(action_matches / n, 4),
        "overall_agreement_rate": round((op_matches + outcome_matches + action_matches) / (3 * n), 4),
        "mean_risk_divergence": round(float(sum(risk_diffs) / n), 4),
        "max_risk_divergence": round(float(max(risk_diffs)), 4) if risk_diffs else 0.0,
    }
