"""Dataset builder assembling >= 100,000 world states with soft label distributions for Laya."""

from __future__ import annotations
import os
import sys
import json
import time
from dataclasses import dataclass, asdict
from typing import Any
import numpy as np

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.simulation.feature_extractor import FeatureExtractor
from backend.app.simulation.rule_engine import RuleEngine
from .scenario_generator import ScenarioGenerator, ScenarioSpec
from .state_generator import StateGenerator, ExtendedPhysicsState
from .trajectory_generator import TrajectoryGenerator


@dataclass
class HighScaleDatasetSample:
    sample_id: str
    scenario_id: str
    scenario_family: str
    tick: int
    numeric_vector: list[float]
    prompt_text: str
    labels: dict[str, Any]
    soft_labels: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LargeScaleDatasetBuilder:
    """Builds and partitions massive 100,000+ world-state datasets with multi-future soft labels."""

    def __init__(self, seed: int = 2026) -> None:
        self.scenario_gen = ScenarioGenerator(seed=seed)
        self.traj_gen = TrajectoryGenerator()
        self.extractor = FeatureExtractor()
        self.rule_engine = RuleEngine()

    def build_dataset(
        self,
        target_states: int = 100000,
        scenarios_count: int | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Generates target world states, computing deterministic physics and soft branch distributions."""
        start_time = time.time()
        print(f"=== [Simulation Dataset Program] Target: {target_states:,} World States ===")

        # Estimate scenarios needed: ~26 ticks per scenario
        if scenarios_count is None:
            scenarios_count = int(math.ceil(target_states / 26.0) + 150)

        print(f"Generating {scenarios_count} scenarios across 10 tactical families...")
        scenarios = self.scenario_gen.generate_scenarios(count=scenarios_count)

        all_samples: list[dict[str, Any]] = []
        family_counts: dict[str, int] = {}

        print("Executing deterministic physics trajectories & 100-branch future rollouts...")
        for s_idx, spec in enumerate(scenarios):
            traj = self.traj_gen.generate_trajectory(spec)
            for state in traj:
                feats = self.extractor.extract(state)
                rule_res = self.rule_engine.evaluate(state)
                soft_dist = self.traj_gen.evaluate_multi_future_soft_labels(
                    state=state, spec=spec, num_branches=100, seed=2026 + s_idx
                )

                # Authoritative discrete labels (argmax from rules/physics)
                labels = {
                    "operational_state": rule_res.operational_state,
                    "mission_outcome": rule_res.mission_outcome,
                    "logistics_state": rule_res.logistics_state,
                    "comms_state": rule_res.comms_state,
                    "environmental_impact": rule_res.environmental_impact,
                    "recommended_action": rule_res.recommended_action,
                    "risk_score": round(float(soft_dist["risk_score"]), 4),
                }

                sample = HighScaleDatasetSample(
                    sample_id=f"{spec.scenario_id}_t{state.tick:03d}",
                    scenario_id=spec.scenario_id,
                    scenario_family=spec.family,
                    tick=state.tick,
                    numeric_vector=feats.numeric_vector,
                    prompt_text=feats.prompt_text,
                    labels=labels,
                    soft_labels=soft_dist,
                )

                all_samples.append(sample.to_dict())
                family_counts[spec.family] = family_counts.get(spec.family, 0) + 1

                if len(all_samples) >= target_states:
                    break

            if (s_idx + 1) % 500 == 0 or len(all_samples) >= target_states:
                elapsed = time.time() - start_time
                print(
                    f"Progress: {len(all_samples):,}/{target_states:,} states generated "
                    f"({s_idx + 1} scenarios completed, elapsed: {elapsed:.1f}s)"
                )

            if len(all_samples) >= target_states:
                break

        print(f"Generated {len(all_samples):,} total states in {time.time() - start_time:.2f} seconds.")

        # Stratified scenario-based partitioning: 80% train, 10% val, 10% test
        rng = np.random.RandomState(2026)
        scenario_ids = list(dict.fromkeys(s["scenario_id"] for s in all_samples))
        rng.shuffle(scenario_ids)

        n_scenarios = len(scenario_ids)
        train_end = int(0.80 * n_scenarios)
        val_end = int(0.90 * n_scenarios)

        train_scens = set(scenario_ids[:train_end])
        val_scens = set(scenario_ids[train_end:val_end])
        test_scens = set(scenario_ids[val_end:])

        splits: dict[str, list[dict[str, Any]]] = {
            "train": [s for s in all_samples if s["scenario_id"] in train_scens],
            "val": [s for s in all_samples if s["scenario_id"] in val_scens],
            "test": [s for s in all_samples if s["scenario_id"] in test_scens],
        }

        print(
            f"Dataset Splits: Train={len(splits['train']):,}, "
            f"Val={len(splits['val']):,}, Test={len(splits['test']):,}"
        )
        return splits

    def save_splits(self, splits: dict[str, list[dict[str, Any]]], output_dir: str) -> dict[str, Any]:
        """Saves generated dataset splits and comprehensive metadata to disk."""
        os.makedirs(output_dir, exist_ok=True)
        stats = {
            "total_samples": sum(len(v) for v in splits.values()),
            "train_samples": len(splits["train"]),
            "val_samples": len(splits["val"]),
            "test_samples": len(splits["test"]),
            "feature_dim": 15,
            "target_tasks": [
                "operational_state",
                "mission_outcome",
                "logistics_state",
                "comms_state",
                "recommended_action",
                "risk_score",
            ],
            "soft_label_support": True,
            "multi_future_branches": 100,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        for split_name, samples in splits.items():
            path = os.path.join(output_dir, f"{split_name}.json")
            print(f"Writing {len(samples):,} records to {path}...")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(samples, f)

        stats_path = os.path.join(output_dir, "dataset_stats.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

        print(f"Saved dataset stats to {stats_path}")
        return stats


import math  # ensure math import
