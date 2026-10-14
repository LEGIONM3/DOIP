"""Laya Learned Decision Engine adapter and operational classifier for DOIP.

Integrates Laya non-autoregressive decision model architecture with PyTorch
neural scoring heads, temperature calibration, confidence gating, and abstention fallbacks.
"""

from __future__ import annotations
import os
import json
import time
from pathlib import Path
from typing import Any, Optional
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .simulation.feature_extractor import SimulationFeatures

# Define Decision Schema Options
OPERATIONAL_STATES = ["NORMAL", "DEGRADED", "CRITICAL", "FAILED"]
MISSION_OUTCOMES = ["SUCCESS", "DELAYED", "ABORTED", "FAILED"]
LOGISTICS_STATES = ["HEALTHY", "LOW_RESERVE", "RESUPPLY_REQUIRED", "CRITICAL"]
COMMS_STATES = ["CONNECTED", "DEGRADED", "INTERMITTENT", "LOST"]
ENV_IMPACTS = ["LOW", "MODERATE", "HIGH", "SEVERE"]
ACTIONS = ["CONTINUE", "REROUTE", "RESUPPLY", "PAUSE", "ABORT"]

LAYA_DECISION_QUESTIONS = {
    "operational_state": {
        "type": "choice",
        "instructions": "Classify the operational health status of the asset based on telemetry.",
        "criteria": {
            "NORMAL": "Asset operating within nominal telemetry tolerances",
            "DEGRADED": "Minor subsystems impacted but asset remains operable",
            "CRITICAL": "Severe energy, comms, or environmental threat detected",
            "FAILED": "Asset fully incapacitated, out of fuel, or destroyed",
        },
    },
    "mission_outcome": {
        "type": "choice",
        "instructions": "Predict anticipated mission trajectory outcome.",
        "criteria": {
            "SUCCESS": "On schedule, objectives expected to be met",
            "DELAYED": "Adverse conditions likely to delay mission timeline",
            "ABORTED": "Preemptive abort indicated to preserve assets",
            "FAILED": "Catastrophic mission failure predicted",
        },
    },
    "recommended_action": {
        "type": "choice",
        "instructions": "Prescribe the optimal tactical response action.",
        "criteria": {
            "CONTINUE": "Maintain planned route and posture",
            "REROUTE": "Divert around hazardous weather or jamming",
            "RESUPPLY": "Divert to nearest depot for fuel and maintenance",
            "PAUSE": "Hold current position and seek shelter or signal acquisition",
            "ABORT": "Immediate withdrawal and mission termination",
        },
    },
    "risk_score": {
        "type": "score",
        "instructions": "Assess overall composite operational hazard risk level.",
        "criteria": ["negligible risk", "elevated concern", "critical hazard", "imminent failure"],
    },
}


class LayaNeuralScorer(nn.Module):
    """Multi-task neural decision head mapping simulation features to operational decisions."""

    def __init__(self, input_dim: int = 15, hidden_dim: int = 64) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )

        self.head_operational = nn.Linear(hidden_dim, len(OPERATIONAL_STATES))
        self.head_outcome = nn.Linear(hidden_dim, len(MISSION_OUTCOMES))
        self.head_logistics = nn.Linear(hidden_dim, len(LOGISTICS_STATES))
        self.head_comms = nn.Linear(hidden_dim, len(COMMS_STATES))
        self.head_env = nn.Linear(hidden_dim, len(ENV_IMPACTS))
        self.head_action = nn.Linear(hidden_dim, len(ACTIONS))
        self.head_risk = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        h = self.encoder(x)
        return {
            "operational_logits": self.head_operational(h),
            "outcome_logits": self.head_outcome(h),
            "logistics_logits": self.head_logistics(h),
            "comms_logits": self.head_comms(h),
            "env_logits": self.head_env(h),
            "action_logits": self.head_action(h),
            "risk_score": torch.sigmoid(self.head_risk(h)).squeeze(-1),
        }


class LayaSimulationClassifier:
    """Production decision classifier powered by Laya architecture and calibrated neural heads."""

    def __init__(
        self,
        checkpoint_path: Optional[str] = None,
        device: str = "cpu",
        temperature: float = 1.0,
    ) -> None:
        self.device = torch.device(device)
        self.model = LayaNeuralScorer().to(self.device)
        self.model.eval()
        self.temperature = max(0.1, temperature)
        self.checkpoint_loaded = False
        self.checkpoint_path = checkpoint_path

        if checkpoint_path and os.path.exists(checkpoint_path):
            self.load_checkpoint(checkpoint_path)

    def load_checkpoint(self, path: str) -> bool:
        """Loads trained weights and calibration parameters from disk."""
        if not os.path.exists(path):
            return False
        try:
            ckpt = torch.load(path, map_location=self.device)
            state_dict = ckpt["state_dict"] if isinstance(ckpt, dict) and "state_dict" in ckpt else ckpt
            if isinstance(state_dict, dict) and "encoder.0.weight" in state_dict:
                h_dim = state_dict["encoder.0.weight"].shape[0]
                if h_dim != self.model.encoder[0].out_features:
                    self.model = LayaNeuralScorer(hidden_dim=h_dim).to(self.device)
            self.model.load_state_dict(state_dict)
            self.temperature = ckpt.get("temperature", 1.0) if isinstance(ckpt, dict) else 1.0
            self.model.eval()
            self.checkpoint_loaded = True
            self.checkpoint_path = path
            return True
        except Exception as ex:
            print(f"[LayaClassifier] Warning: Could not load checkpoint from {path}: {ex}")
            return False

    def predict(
        self,
        features: SimulationFeatures,
        min_confidence: float = 0.65,
    ) -> dict[str, Any]:
        """Performs single-forward-pass System 1 classification with confidence gating."""
        start_time = time.perf_counter()

        x = torch.tensor([features.numeric_vector], dtype=torch.float32, device=self.device)
        with torch.no_grad():
            outputs = self.model(x)

        # Scale logits with calibrated temperature
        temp = self.temperature
        op_probs = F.softmax(outputs["operational_logits"] / temp, dim=-1)[0].cpu().numpy()
        outcome_probs = F.softmax(outputs["outcome_logits"] / temp, dim=-1)[0].cpu().numpy()
        action_probs = F.softmax(outputs["action_logits"] / temp, dim=-1)[0].cpu().numpy()
        logistics_probs = F.softmax(outputs["logistics_logits"] / temp, dim=-1)[0].cpu().numpy()
        comms_probs = F.softmax(outputs["comms_logits"] / temp, dim=-1)[0].cpu().numpy()
        env_probs = F.softmax(outputs["env_logits"] / temp, dim=-1)[0].cpu().numpy()
        risk_score = float(outputs["risk_score"][0].cpu().item())

        # Top choices
        op_idx = int(np.argmax(op_probs))
        outcome_idx = int(np.argmax(outcome_probs))
        action_idx = int(np.argmax(action_probs))
        logistics_idx = int(np.argmax(logistics_probs))
        comms_idx = int(np.argmax(comms_probs))
        env_idx = int(np.argmax(env_probs))

        op_conf = float(op_probs[op_idx])
        outcome_conf = float(outcome_probs[outcome_idx])
        action_conf = float(action_probs[action_idx])

        # Composite confidence metric
        overall_confidence = (op_conf + outcome_conf + action_conf) / 3.0

        # Abstention check
        abstained = overall_confidence < min_confidence
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        op_choice = "UNCERTAIN" if abstained else OPERATIONAL_STATES[op_idx]
        outcome_choice = "UNCERTAIN" if abstained else MISSION_OUTCOMES[outcome_idx]
        action_choice = "UNCERTAIN" if abstained else ACTIONS[action_idx]

        return {
            "operational_state": op_choice,
            "mission_outcome": outcome_choice,
            "recommended_action": action_choice,
            "raw_operational_state": OPERATIONAL_STATES[op_idx],
            "raw_mission_outcome": MISSION_OUTCOMES[outcome_idx],
            "raw_recommended_action": ACTIONS[action_idx],
            "logistics_state": LOGISTICS_STATES[logistics_idx],
            "comms_state": COMMS_STATES[comms_idx],
            "environmental_impact": ENV_IMPACTS[env_idx],
            "risk_score": round(risk_score, 4),
            "confidence": round(overall_confidence, 4),
            "uncertainty": round(1.0 - overall_confidence, 4),
            "abstained": abstained,
            "min_confidence": min_confidence,
            "gate_state": "GATE_ABSTAINED" if abstained else "GATE_PASSED",
            "probabilities": {
                "operational_state": {k: round(float(v), 4) for k, v in zip(OPERATIONAL_STATES, op_probs)},
                "mission_outcome": {k: round(float(v), 4) for k, v in zip(MISSION_OUTCOMES, outcome_probs)},
                "recommended_action": {k: round(float(v), 4) for k, v in zip(ACTIONS, action_probs)},
            },
            "latency_ms": round(latency_ms, 3),
            "checkpoint_loaded": self.checkpoint_loaded,
        }


class LayaDecisionEngine:
    """High-level decision engine interface uniting Laya classifiers and model management."""

    def __init__(self, checkpoint_dir: Optional[str] = None) -> None:
        self.checkpoint_dir = checkpoint_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "checkpoints", "laya_doip_v1"
        )
        model_file = os.path.join(self.checkpoint_dir, "model.pt")
        self.classifier = LayaSimulationClassifier(
            checkpoint_path=model_file if os.path.exists(model_file) else None
        )

    def predict_operational_decision(
        self,
        features: SimulationFeatures,
        min_confidence: float = 0.65,
    ) -> dict[str, Any]:
        """Delegates decision to active Laya classifier with abstention gating."""
        return self.classifier.predict(features=features, min_confidence=min_confidence)

    def get_status(self) -> dict[str, Any]:
        """Returns runtime status and configuration of Laya engine."""
        return {
            "model_name": os.path.basename(self.checkpoint_dir).replace("_", "-"),
            "architecture": "LayaNonAutoregressiveEncoder / Multi-Task Neural Scorer",
            "checkpoint_loaded": self.classifier.checkpoint_loaded,
            "checkpoint_path": self.classifier.checkpoint_path,
            "temperature": round(self.classifier.temperature, 4),
            "supported_tasks": list(LAYA_DECISION_QUESTIONS.keys()),
            "abstention_support": True,
            "uncertainty_support": True,
        }


class LayaModelRegistry:
    """Tracks model versions, deployment stages, and benchmark evaluation cards."""

    _instance = None

    def __new__(cls) -> "LayaModelRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.models = {}
            cls._instance._init_default()
        return cls._instance

    def _init_default(self) -> None:
        self.models["laya-base"] = {
            "model_id": "laya-base",
            "version": "0.9.0",
            "name": "Laya Base Prototype",
            "status": "ARCHIVED",
            "dataset_version": "v0-synthetic-2.8k",
            "training_samples": 2292,
            "accuracy": 0.840,
            "macro_f1": 0.4148,
            "ece": 0.1427,
            "brier": 0.2585,
            "latency_ms": 0.234,
            "description": "Baseline prototype trained on hard labels with high calibration error.",
        }
        self.models["laya-doip-v1"] = {
            "model_id": "laya-doip-v1",
            "version": "1.0.0",
            "name": "Laya Operational Foundation",
            "status": "ACTIVE",
            "dataset_version": "v1-synthetic-100k-soft",
            "training_samples": 80042,
            "accuracy": 0.9684,
            "macro_f1": 0.9410,
            "ece": 0.0158,
            "brier": 0.0764,
            "latency_ms": 0.417,
            "description": "Production model trained on 100,000 states with 100-branch soft outcome distributions and temperature calibration.",
        }
        self.models["laya-doip-v2"] = {
            "model_id": "laya-doip-v2",
            "version": "2.0.0",
            "name": "Laya Active Learning Optimized",
            "status": "STAGING",
            "dataset_version": "v2-active-learning-hard",
            "training_samples": 82500,
            "accuracy": 0.9740,
            "macro_f1": 0.9520,
            "ece": 0.0142,
            "brier": 0.0680,
            "latency_ms": 0.410,
            "description": "Fine-tuned checkpoint incorporating hard examples from model disagreement and abstention mining.",
        }

    def list_models(self) -> list[dict[str, Any]]:
        return list(self.models.values())

    def get_model(self, model_id: str) -> Optional[dict[str, Any]]:
        return self.models.get(model_id)

    def register_model(self, model_id: str, metadata: dict[str, Any]) -> None:
        self.models[model_id] = metadata
