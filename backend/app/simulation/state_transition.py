"""Rule-validated state transition engine ensuring neural predictions cannot violate physical invariants."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from .physics_engine import PhysicsEngineState
from .rule_engine import RuleEngine, RuleEvaluationResult


@dataclass
class TransitionValidationResult:
    action_accepted: bool
    final_action: str
    decision_source: str  # "LAYA_LEARNED" | "RULE_ENGINE_OVERRIDE" | "RULE_FALLBACK"
    validation_status: str # "ACCEPTED" | "OVERRIDDEN" | "ABSTAINED_FALLBACK"
    reason: str
    audit_trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_accepted": self.action_accepted,
            "final_action": self.final_action,
            "decision_source": self.decision_source,
            "validation_status": self.validation_status,
            "reason": self.reason,
            "audit_trace": self.audit_trace,
        }


class StateTransitionValidator:
    """Enforces safety, physics, and logical invariant gates over learned decision outputs."""

    def __init__(self, rule_engine: Optional[RuleEngine] = None) -> None:
        self.rule_engine = rule_engine if rule_engine is not None else RuleEngine()

    def validate_and_apply(
        self,
        current_state: PhysicsEngineState,
        laya_decision: Optional[dict[str, Any]] = None,
        confidence_gate_passed: bool = True,
    ) -> TransitionValidationResult:
        """Validates proposed learned decision against authoritative physics rules."""
        rule_eval: RuleEvaluationResult = self.rule_engine.evaluate(current_state)

        # Case 1: Laya was not queried or abstained due to low confidence
        if laya_decision is None or not confidence_gate_passed:
            return TransitionValidationResult(
                action_accepted=False,
                final_action=rule_eval.recommended_action,
                decision_source="RULE_FALLBACK",
                validation_status="ABSTAINED_FALLBACK",
                reason="Laya model abstained or confidence gate triggered; fell back to authoritative rule engine",
                audit_trace={
                    "rule_eval": rule_eval.to_dict(),
                    "laya_confidence_passed": confidence_gate_passed,
                },
            )

        proposed_action = laya_decision.get("recommended_action") or laya_decision.get("action", "CONTINUE")
        proposed_action = str(proposed_action).upper().strip()

        # Case 2: Validate against physical invariants
        is_valid, validation_msg = self.rule_engine.validate_action(current_state, proposed_action)

        if not is_valid:
            # Override with rule engine recommendation
            return TransitionValidationResult(
                action_accepted=False,
                final_action=rule_eval.recommended_action,
                decision_source="RULE_ENGINE_OVERRIDE",
                validation_status="OVERRIDDEN",
                reason=f"Learned action '{proposed_action}' rejected by invariant gate: {validation_msg}. Overridden to '{rule_eval.recommended_action}'.",
                audit_trace={
                    "proposed_action": proposed_action,
                    "rejection_detail": validation_msg,
                    "rule_eval": rule_eval.to_dict(),
                },
            )

        # Case 3: Action is valid according to physical and logical rules
        return TransitionValidationResult(
            action_accepted=True,
            final_action=proposed_action,
            decision_source="LAYA_LEARNED",
            validation_status="ACCEPTED",
            reason=f"Learned action '{proposed_action}' validated against all physical rules and invariants.",
            audit_trace={
                "proposed_action": proposed_action,
                "validation_message": validation_msg,
                "rule_eval": rule_eval.to_dict(),
            },
        )
