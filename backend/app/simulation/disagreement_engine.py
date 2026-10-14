"""Model Disagreement Engine comparing Physics, Authoritative Rules, and Laya decisions."""

from __future__ import annotations
import math
import uuid
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from .physics_engine import PhysicsEngineState
from .rule_engine import RuleEngine, RuleEvaluationResult


def risk_score_to_category(score: float) -> str:
    """Converts a continuous risk score [0, 1] to discrete categorical severity."""
    if score >= 0.75:
        return "CRITICAL"
    elif score >= 0.50:
        return "HIGH"
    elif score >= 0.25:
        return "MODERATE"
    return "LOW"


def compute_physics_risk(state: PhysicsEngineState) -> tuple[float, str]:
    """Computes direct empirical risk derived strictly from physical telemetry equations."""
    k = state.kinematics
    e = state.energy
    env = state.environment
    c = state.comms
    log = state.logistics

    # Energy exhaustion risk
    fuel_risk = max(0.0, 1.0 - (e.fuel_level_pct / 100.0))
    # Wear risk
    wear_risk = min(1.0, log.vehicle_wear_pct / 100.0)
    # Environmental drag/weather risk
    env_risk = min(1.0, (env.precipitation_mm_hr / 60.0) * 0.5 + (env.wind_speed_mps / 40.0) * 0.5)
    # Comms & jamming risk
    jam_risk = min(1.0, c.jamming_intensity * 0.6 + (c.packet_loss_pct / 100.0) * 0.4)

    composite = (fuel_risk * 0.35) + (wear_risk * 0.25) + (env_risk * 0.20) + (jam_risk * 0.20)
    score = round(float(min(1.0, max(0.0, composite))), 4)
    return score, risk_score_to_category(score)


@dataclass
class DisagreementRecord:
    disagreement_id: str
    tick: int
    physics_risk: str
    rules_risk: str
    laya_risk: str
    physics_score: float
    rules_score: float
    laya_score: float
    rules_decision: dict[str, Any]
    laya_decision: dict[str, Any]
    divergence_type: str
    explanation: str
    divergence_severity: str  # MINOR | MODERATE | SEVERE
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelDisagreementEngine:
    """Detects, categorizes, and explains operational decision divergence across subsystems."""

    def __init__(self) -> None:
        self.disagreement_history: list[DisagreementRecord] = []

    def analyze_disagreement(
        self,
        physics_state: PhysicsEngineState,
        rule_eval: RuleEvaluationResult,
        laya_eval: Optional[dict[str, Any]],
    ) -> Optional[DisagreementRecord]:
        """Analyzes agreement/disagreement triad across Physics, Rules, and Laya."""
        if laya_eval is None:
            return None

        # 1. Compute triad risk profiles
        p_score, p_risk = compute_physics_risk(physics_state)
        r_score = float(rule_eval.rule_risk_score)
        r_risk = risk_score_to_category(r_score)

        l_score = float(laya_eval.get("risk_score", r_score))
        l_risk = risk_score_to_category(l_score)

        # 2. Check for decision mismatches
        op_rule = rule_eval.operational_state
        op_laya = laya_eval.get("operational_state", op_rule)

        act_rule = rule_eval.recommended_action
        act_laya = laya_eval.get("recommended_action", act_rule)

        out_rule = rule_eval.mission_outcome
        out_laya = laya_eval.get("mission_outcome", out_rule)

        risk_diff = abs(r_score - l_score)
        categories = [p_risk, r_risk, l_risk]
        has_risk_divergence = len(set(categories)) > 1 or risk_diff > 0.20
        has_decision_divergence = (op_rule != op_laya) or (act_rule != act_laya) or (out_rule != out_laya)

        if not has_risk_divergence and not has_decision_divergence:
            return None  # Full consensus

        # 3. Categorize severity
        severity = "MINOR"
        if op_rule == "FAILED" and op_laya != "FAILED":
            severity = "SEVERE"
        elif "CRITICAL" in categories and "LOW" in categories:
            severity = "SEVERE"
        elif risk_diff > 0.35 or (act_rule in ["ABORT", "PAUSE"] and act_laya == "CONTINUE"):
            severity = "MODERATE"

        # 4. Generate structured explanation
        explanations = []
        divergence_type = f"Physics: {p_risk} | Rules: {r_risk} | Laya: {l_risk}"

        if op_rule != op_laya:
            explanations.append(
                f"Operational State conflict: Rules assessed '{op_rule}' (due to physical triggers: {rule_eval.triggered_rules or 'bounds'}), whereas Laya predicted '{op_laya}'."
            )
        if act_rule != act_laya:
            explanations.append(
                f"Tactical Action conflict: Rules prescribe '{act_rule}', whereas Laya suggested '{act_laya}'."
            )
        if risk_diff > 0.20:
            explanations.append(
                f"Hazard score diverged by {risk_diff:.2f}: Rule score is {r_score:.2f} ({r_risk}) vs Laya score {l_score:.2f} ({l_risk})."
            )
        if p_risk != r_risk:
            explanations.append(
                f"Physics baseline ({p_risk}) differs from Rule interpretation ({r_risk}) due to specific operational thresholds."
            )

        explanation_str = " ".join(explanations)

        record = DisagreementRecord(
            disagreement_id=f"DISAGREE-{uuid.uuid4().hex[:8].upper()}",
            tick=physics_state.tick,
            physics_risk=p_risk,
            rules_risk=r_risk,
            laya_risk=l_risk,
            physics_score=p_score,
            rules_score=r_score,
            laya_score=l_score,
            rules_decision=rule_eval.to_dict(),
            laya_decision=laya_eval,
            divergence_type=divergence_type,
            explanation=explanation_str,
            divergence_severity=severity,
        )

        self.disagreement_history.append(record)
        # Keep ring buffer
        if len(self.disagreement_history) > 500:
            self.disagreement_history.pop(0)

        return record

    def get_recent_disagreements(self, limit: int = 50) -> list[dict[str, Any]]:
        """Returns recent disagreements in reverse chronological order."""
        return [r.to_dict() for r in reversed(self.disagreement_history[-limit:])]

    def get_statistics(self) -> dict[str, Any]:
        """Returns summary statistics of tracked model disagreements."""
        total = len(self.disagreement_history)
        if total == 0:
            return {"total_disagreements": 0, "severity_counts": {}}

        sev_counts: dict[str, int] = {}
        for r in self.disagreement_history:
            sev_counts[r.divergence_severity] = sev_counts.get(r.divergence_severity, 0) + 1

        return {
            "total_disagreements": total,
            "severity_counts": sev_counts,
            "most_common_divergence": max(
                set(r.divergence_type for r in self.disagreement_history),
                key=lambda x: [r.divergence_type for r in self.disagreement_history].count(x)
            ),
        }


# Global singleton instance
_disagreement_engine = ModelDisagreementEngine()


def analyze_disagreement(
    physics_state: PhysicsEngineState,
    rule_eval: RuleEvaluationResult,
    laya_eval: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Functional convenience facade for model disagreement analysis."""
    rec = _disagreement_engine.analyze_disagreement(physics_state, rule_eval, laya_eval)
    return rec.to_dict() if rec is not None else None
