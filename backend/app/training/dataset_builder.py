"""Dataset builder assembling scenario runs into stratified train/val/test splits."""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any
import numpy as np
import torch
from torch.utils.data import Dataset

from backend.app.simulation.feature_extractor import FeatureExtractor
from .scenario_generator import ScenarioGenerator, ScenarioSpec
from .state_generator import StateTrajectoryGenerator
from .label_generator import LabelGenerator
from backend.app.laya_engine import (
    OPERATIONAL_STATES,
    MISSION_OUTCOMES,
    LOGISTICS_STATES,
    COMMS_STATES,
    ENV_IMPACTS,
    ACTIONS,
)


@dataclass
class DatasetSample:
    sample_id: str
    scenario_id: str
    scenario_family: str
    tick: int
    numeric_vector: list[float]
    prompt_text: str
    labels: dict[str, Any]
    soft_labels: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OperationalDataset(Dataset):
    """PyTorch Dataset wrapping numeric feature vectors, hard indices, and soft distributions."""

    def __init__(self, samples: list[DatasetSample]) -> None:
        self.samples = samples
        self.vectors = torch.tensor([s.numeric_vector for s in samples], dtype=torch.float32)

        self.op_targets = torch.tensor(
            [OPERATIONAL_STATES.index(s.labels["operational_state"]) for s in samples], dtype=torch.long
        )
        self.outcome_targets = torch.tensor(
            [MISSION_OUTCOMES.index(s.labels["mission_outcome"]) for s in samples], dtype=torch.long
        )
        self.logistics_targets = torch.tensor(
            [LOGISTICS_STATES.index(s.labels["logistics_state"]) for s in samples], dtype=torch.long
        )
        self.comms_targets = torch.tensor(
            [COMMS_STATES.index(s.labels["comms_state"]) for s in samples], dtype=torch.long
        )
        self.env_targets = torch.tensor(
            [ENV_IMPACTS.index(s.labels.get("environmental_impact", "LOW")) for s in samples], dtype=torch.long
        )
        self.action_targets = torch.tensor(
            [ACTIONS.index(s.labels["recommended_action"]) for s in samples], dtype=torch.long
        )
        self.risk_targets = torch.tensor(
            [float(s.labels["risk_score"]) for s in samples], dtype=torch.float32
        )

        # Soft distribution probability tensors
        def extract_soft(task_name: str, options: list[str], fallback_indices: torch.Tensor) -> torch.Tensor:
            tensor_list = []
            for i, s in enumerate(samples):
                soft_map = getattr(s, "soft_labels", {}) or {}
                if task_name in soft_map and isinstance(soft_map[task_name], dict):
                    row = [float(soft_map[task_name].get(opt, 0.0)) for opt in options]
                    s_sum = sum(row)
                    if s_sum > 0:
                        row = [v / s_sum for v in row]
                    else:
                        row = [1.0 if j == fallback_indices[i].item() else 0.0 for j in range(len(options))]
                    tensor_list.append(row)
                else:
                    # Synthesize 1-hot distribution
                    row = [1.0 if j == fallback_indices[i].item() else 0.0 for j in range(len(options))]
                    tensor_list.append(row)
            return torch.tensor(tensor_list, dtype=torch.float32)

        self.op_soft = extract_soft("operational_state", OPERATIONAL_STATES, self.op_targets)
        self.outcome_soft = extract_soft("mission_outcome", MISSION_OUTCOMES, self.outcome_targets)
        self.logistics_soft = extract_soft("logistics_state", LOGISTICS_STATES, self.logistics_targets)
        self.comms_soft = extract_soft("comms_state", COMMS_STATES, self.comms_targets)
        self.action_soft = extract_soft("recommended_action", ACTIONS, self.action_targets)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return {
            "features": self.vectors[idx],
            "operational": self.op_targets[idx],
            "outcome": self.outcome_targets[idx],
            "logistics": self.logistics_targets[idx],
            "comms": self.comms_targets[idx],
            "env": self.env_targets[idx],
            "action": self.action_targets[idx],
            "risk": self.risk_targets[idx],
            "operational_soft": self.op_soft[idx],
            "outcome_soft": self.outcome_soft[idx],
            "logistics_soft": self.logistics_soft[idx],
            "comms_soft": self.comms_soft[idx],
            "action_soft": self.action_soft[idx],
        }


class DatasetBuilder:
    """Orchestrates end-to-end dataset generation and splitting."""

    def __init__(self) -> None:
        self.extractor = FeatureExtractor()
        self.label_gen = LabelGenerator()
        self.traj_gen = StateTrajectoryGenerator()

    def build_dataset(
        self,
        scenarios: list[ScenarioSpec],
    ) -> dict[str, list[DatasetSample]]:
        """Generates samples and partitions by scenario into train (80%), val (10%), test (10%)."""
        all_samples_by_scen: dict[str, list[DatasetSample]] = {}

        for spec in scenarios:
            states = self.traj_gen.run_trajectory(spec)
            scen_samples = []
            for s in states:
                feats = self.extractor.extract(s)
                lbl = self.label_gen.generate_label(s)
                sample = DatasetSample(
                    sample_id=f"{spec.scenario_id}_T{s.tick:03d}",
                    scenario_id=spec.scenario_id,
                    scenario_family=spec.family,
                    tick=s.tick,
                    numeric_vector=feats.numeric_vector,
                    prompt_text=feats.prompt_text,
                    labels=lbl.to_dict(),
                )
                scen_samples.append(sample)
            all_samples_by_scen[spec.scenario_id] = scen_samples

        scen_ids = list(all_samples_by_scen.keys())
        # Shuffle deterministically
        rng = np.random.RandomState(42)
        rng.shuffle(scen_ids)

        n = len(scen_ids)
        n_train = int(n * 0.8)
        n_val = int(n * 0.1)

        train_ids = set(scen_ids[:n_train])
        val_ids = set(scen_ids[n_train : n_train + n_val])
        test_ids = set(scen_ids[n_train + n_val :])

        train_samples = [s for sid in train_ids for s in all_samples_by_scen[sid]]
        val_samples = [s for sid in val_ids for s in all_samples_by_scen[sid]]
        test_samples = [s for sid in test_ids for s in all_samples_by_scen[sid]]

        return {
            "train": train_samples,
            "val": val_samples,
            "test": test_samples,
        }

    def save_splits(self, splits: dict[str, list[DatasetSample]], output_dir: str) -> None:
        """Saves generated dataset splits as JSON files."""
        os.makedirs(output_dir, exist_ok=True)
        for name, samples in splits.items():
            path = os.path.join(output_dir, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in samples], f, indent=2)
        print(f"[DatasetBuilder] Saved {len(splits['train'])} train, {len(splits['val'])} val, {len(splits['test'])} test samples to {output_dir}")
