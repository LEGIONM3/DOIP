"""Active Learning candidate mining and persistent hard example storage."""

from __future__ import annotations
import os
import sys
import json
import time
import uuid
from typing import Any, Optional

from backend.app.simulation.physics_engine import PhysicsEngineState
from backend.app.simulation.rule_engine import RuleEvaluationResult
from backend.app.simulation.feature_extractor import FeatureExtractor, SimulationFeatures


class ActiveLearningCollector:
    """Collects low confidence, misclassified, and high-disagreement samples for model fine-tuning."""

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        self.storage_dir = storage_dir or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "hard_examples")
        )
        os.makedirs(self.storage_dir, exist_ok=True)
        self.collector_file = os.path.join(self.storage_dir, "hard_examples.json")
        self.extractor = FeatureExtractor()

    def load_collected_examples(self) -> list[dict[str, Any]]:
        """Loads already persisted hard examples from disk."""
        if not os.path.exists(self.collector_file):
            return []
        try:
            with open(self.collector_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def should_collect(
        self,
        laya_eval: Optional[dict[str, Any]],
        rule_eval: RuleEvaluationResult,
        confidence_threshold: float = 0.65,
    ) -> tuple[bool, str]:
        """Evaluates whether an inference instance qualifies as an active learning hard sample."""
        if laya_eval is None:
            return False, "NO_LAYA_PREDICTION"

        conf = float(laya_eval.get("confidence", 1.0))
        abstained = bool(laya_eval.get("abstained", False))

        # Criterion 1: Low confidence / Abstention
        if conf < confidence_threshold or abstained:
            return True, f"LOW_CONFIDENCE (conf={conf:.2f} < {confidence_threshold:.2f})"

        # Criterion 2: Misclassification against authoritative ground truth rules
        op_rule = rule_eval.operational_state
        op_laya = laya_eval.get("operational_state")
        if op_rule != op_laya:
            return True, f"MISCLASSIFIED_OPERATIONAL (Rule={op_rule} vs Laya={op_laya})"

        out_rule = rule_eval.mission_outcome
        out_laya = laya_eval.get("mission_outcome")
        if out_rule != out_laya:
            return True, f"MISCLASSIFIED_OUTCOME (Rule={out_rule} vs Laya={out_laya})"

        # Criterion 3: Severe risk score discrepancy
        r_rule = float(rule_eval.rule_risk_score)
        r_laya = float(laya_eval.get("risk_score", r_rule))
        if abs(r_rule - r_laya) > 0.30:
            return True, f"HIGH_RISK_DIVERGENCE (diff={abs(r_rule - r_laya):.2f})"

        return False, "NOMINAL"

    def collect_sample(
        self,
        physics_state: PhysicsEngineState,
        rule_eval: RuleEvaluationResult,
        laya_eval: Optional[dict[str, Any]],
        scenario_id: str = "ONLINE_SIM",
        scenario_family: str = "ACTIVE_LEARNING_MINE",
    ) -> Optional[dict[str, Any]]:
        """Formats and stores a hard example if criteria are met."""
        qualifies, reason = self.should_collect(laya_eval, rule_eval)
        if not qualifies:
            return None

        feats = self.extractor.extract(physics_state)
        sample = {
            "sample_id": f"HARD_{uuid.uuid4().hex[:8].upper()}_t{physics_state.tick:03d}",
            "scenario_id": scenario_id,
            "scenario_family": scenario_family,
            "tick": physics_state.tick,
            "numeric_vector": feats.numeric_vector,
            "prompt_text": feats.prompt_text,
            "labels": {
                "operational_state": rule_eval.operational_state,
                "mission_outcome": rule_eval.mission_outcome,
                "logistics_state": rule_eval.logistics_state,
                "comms_state": rule_eval.comms_state,
                "environmental_impact": rule_eval.environmental_impact,
                "recommended_action": rule_eval.recommended_action,
                "risk_score": round(float(rule_eval.rule_risk_score), 4),
            },
            "mining_metadata": {
                "reason": reason,
                "laya_confidence": laya_eval.get("confidence", 0.0) if laya_eval else 0.0,
                "mined_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        }

        # Append and persist
        existing = self.load_collected_examples()
        existing.append(sample)
        with open(self.collector_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

        return sample

    def harvest_from_trajectory(
        self,
        states: list[PhysicsEngineState],
        rule_results: list[RuleEvaluationResult],
        laya_results: list[dict[str, Any]],
        scenario_id: str = "BATCH_SIM",
    ) -> list[dict[str, Any]]:
        """Scans a trajectory and extracts all qualifying hard examples."""
        mined = []
        n = min(len(states), len(rule_results), len(laya_results))
        for i in range(n):
            s = states[i]
            r = rule_results[i]
            l = laya_results[i]
            res = self.collect_sample(s, r, l, scenario_id=scenario_id)
            if res is not None:
                mined.append(res)
        return mined


# Global instance
_collector = ActiveLearningCollector()


def collect_hard_examples(
    physics_state: PhysicsEngineState,
    rule_eval: RuleEvaluationResult,
    laya_eval: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Functional convenience facade for collecting hard examples."""
    return _collector.collect_sample(physics_state, rule_eval, laya_eval)
