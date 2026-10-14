"""Authoritative deterministic rule engine for operational bounds checking and state classification.

Enforces physical invariants, logical preconditions, and deterministic baseline decisions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from .physics_engine import PhysicsEngineState


@dataclass
class TransitionRule:
    rule_id: str
    category: str
    condition_description: str
    action_if_violated: str
    priority: int  # 1 (critical) to 10 (informational)


@dataclass
class RuleEvaluationResult:
    operational_state: str  # NORMAL, DEGRADED, CRITICAL, FAILED
    mission_outcome: str    # SUCCESS, DELAYED, ABORTED, FAILED
    logistics_state: str    # HEALTHY, LOW_RESERVE, RESUPPLY_REQUIRED, CRITICAL
    comms_state: str        # CONNECTED, DEGRADED, INTERMITTENT, LOST
    environmental_impact: str # LOW, MODERATE, HIGH, SEVERE
    recommended_action: str # CONTINUE, REROUTE, RESUPPLY, PAUSE, ABORT
    rule_risk_score: float  # [0.0, 1.0]
    triggered_rules: list[str] = field(default_factory=list)
    invariants_passed: bool = True
    rejection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operational_state": self.operational_state,
            "mission_outcome": self.mission_outcome,
            "logistics_state": self.logistics_state,
            "comms_state": self.comms_state,
            "environmental_impact": self.environmental_impact,
            "recommended_action": self.recommended_action,
            "rule_risk_score": round(self.rule_risk_score, 4),
            "triggered_rules": self.triggered_rules,
            "invariants_passed": self.invariants_passed,
            "rejection_reasons": self.rejection_reasons,
        }


class RuleEngine:
    """Deterministic, invariant-preserving operational rule evaluator."""

    def __init__(self) -> None:
        self.rules: list[TransitionRule] = [
            TransitionRule("RULE-01", "energy", "Fuel level zero or below", "HALT_UNIT", 1),
            TransitionRule("RULE-02", "energy", "Fuel level below 15%", "FORCE_RESUPPLY_OR_REROUTE", 2),
            TransitionRule("RULE-03", "comms", "Signal loss below -110 dBm", "COMMS_LOST_PROTOCOL", 2),
            TransitionRule("RULE-04", "logistics", "Mechanical wear exceeding 85%", "MAINTENANCE_REQUIRED", 3),
            TransitionRule("RULE-05", "environment", "Visibility below 1 km with heavy precipitation", "SLOW_TRANSIT", 4),
            TransitionRule("RULE-06", "kinematics", "Speed exceeding maximum rated specification", "CLAMP_SPEED", 1),
        ]

    def evaluate(self, state: PhysicsEngineState) -> RuleEvaluationResult:
        """Evaluates operational physics state against deterministic rules."""
        k = state.kinematics
        e = state.energy
        env = state.environment
        c = state.comms
        log = state.logistics

        triggered: list[str] = []
        reasons: list[str] = []
        invariants_ok = True
        risk = 0.0

        # --- Comms State Evaluation ---
        if c.signal_strength_dbm <= -115.0 or c.packet_loss_pct >= 95.0:
            comms = "LOST"
            triggered.append("RULE-03: Signal lost or critical packet loss")
            risk += 0.35
        elif c.signal_strength_dbm <= -95.0 or c.packet_loss_pct >= 40.0:
            comms = "INTERMITTENT"
            risk += 0.20
        elif c.signal_strength_dbm <= -80.0 or c.packet_loss_pct >= 10.0:
            comms = "DEGRADED"
            risk += 0.10
        else:
            comms = "CONNECTED"

        # --- Environmental Impact Evaluation ---
        if env.visibility_km < 1.0 or env.precipitation_mm_hr > 35.0 or env.wind_speed_mps > 25.0:
            env_impact = "SEVERE"
            triggered.append("RULE-05: Severe weather threshold breached")
            risk += 0.30
        elif env.visibility_km < 3.0 or env.precipitation_mm_hr > 15.0 or env.wind_speed_mps > 15.0:
            env_impact = "HIGH"
            risk += 0.20
        elif env.visibility_km < 6.0 or env.precipitation_mm_hr > 5.0 or env.wind_speed_mps > 8.0:
            env_impact = "MODERATE"
            risk += 0.10
        else:
            env_impact = "LOW"

        # --- Logistics State Evaluation ---
        if log.vehicle_wear_pct >= 85.0 or e.fuel_level_pct <= 5.0 or log.ammunition_pct <= 5.0:
            logistics = "CRITICAL"
            triggered.append("RULE-04: Critical logistics wear/fuel exhaustion")
            risk += 0.35
        elif log.vehicle_wear_pct >= 70.0 or e.fuel_level_pct <= 20.0 or log.ammunition_pct <= 25.0:
            logistics = "RESUPPLY_REQUIRED"
            triggered.append("RULE-02: Fuel below 20% or elevated mechanical wear")
            risk += 0.25
        elif log.vehicle_wear_pct >= 45.0 or e.fuel_level_pct <= 45.0 or log.ammunition_pct <= 50.0:
            logistics = "LOW_RESERVE"
            risk += 0.15
        else:
            logistics = "HEALTHY"

        # --- Invariant Physical Bounds Check ---
        if e.fuel_level_pct <= 0.0:
            triggered.append("RULE-01: Out of fuel invariant violation")
            if k.speed_mps > 0.0:
                invariants_ok = False
                reasons.append("Physical invariant violated: Unit moving with 0% fuel")

        if k.speed_mps > k.max_speed_mps + 0.1:
            triggered.append("RULE-06: Maximum speed ceiling breach")
            invariants_ok = False
            reasons.append(f"Physical invariant violated: Speed {k.speed_mps:.1f} m/s exceeds max {k.max_speed_mps:.1f} m/s")

        # --- Operational State Synthesis ---
        if e.fuel_level_pct <= 0.0 or log.vehicle_wear_pct >= 98.0:
            operational = "FAILED"
            risk = 1.0
        elif e.fuel_level_pct <= 15.0 or comms == "LOST" or logistics == "CRITICAL" or env_impact == "SEVERE":
            operational = "CRITICAL"
            risk = max(risk, 0.75)
        elif logistics in ("RESUPPLY_REQUIRED", "LOW_RESERVE") or comms in ("INTERMITTENT", "DEGRADED") or env_impact == "HIGH":
            operational = "DEGRADED"
            risk = max(risk, 0.40)
        else:
            operational = "NORMAL"
            risk = min(risk, 0.20)

        # --- Recommended Action Baseline ---
        if operational == "FAILED":
            action = "ABORT"
        elif e.fuel_level_pct <= 12.0 or logistics == "CRITICAL":
            action = "RESUPPLY"
        elif env_impact == "SEVERE" or comms == "LOST":
            action = "PAUSE"
        elif operational == "CRITICAL" or env_impact == "HIGH":
            action = "REROUTE"
        else:
            action = "CONTINUE"

        # --- Mission Outcome Forecast Baseline ---
        if operational == "FAILED":
            outcome = "FAILED"
        elif operational == "CRITICAL" and action == "ABORT":
            outcome = "ABORTED"
        elif operational in ("CRITICAL", "DEGRADED") or env_impact in ("HIGH", "SEVERE"):
            outcome = "DELAYED"
        else:
            outcome = "SUCCESS"

        rule_risk_score = min(1.0, max(0.0, risk))

        return RuleEvaluationResult(
            operational_state=operational,
            mission_outcome=outcome,
            logistics_state=logistics,
            comms_state=comms,
            environmental_impact=env_impact,
            recommended_action=action,
            rule_risk_score=rule_risk_score,
            triggered_rules=triggered,
            invariants_passed=invariants_ok,
            rejection_reasons=reasons,
        )

    def validate_action(
        self,
        current_state: PhysicsEngineState,
        proposed_action: str,
    ) -> tuple[bool, str]:
        """Verifies if a proposed action is physically and logically permissible."""
        action = proposed_action.upper().strip()
        e = current_state.energy
        log = current_state.logistics

        if action == "CONTINUE":
            if e.fuel_level_pct <= 0.0:
                return False, "Cannot CONTINUE: Fuel is completely depleted"
            if log.vehicle_wear_pct >= 98.0:
                return False, "Cannot CONTINUE: Critical vehicle breakdown"
            return True, "CONTINUE permitted"

        if action == "REROUTE":
            if e.fuel_level_pct <= 2.0:
                return False, "Cannot REROUTE: Insufficient fuel for detour"
            return True, "REROUTE permitted"

        if action in ("RESUPPLY", "PAUSE", "ABORT"):
            return True, f"{action} always permissible as a safety fall-back"

        return False, f"Unknown action: {proposed_action}"
