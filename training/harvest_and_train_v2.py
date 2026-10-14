"""Active Learning harvest and fine-tuning pipeline for laya_doip_v2."""

from __future__ import annotations
import sys
import os
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.laya_engine import LayaSimulationClassifier
from backend.app.simulation.physics_engine import PhysicsEngineState
from backend.app.simulation.rule_engine import RuleEngine
from backend.app.simulation.feature_extractor import FeatureExtractor
from backend.app.simulation.active_learning import ActiveLearningCollector
from training_data.scenario_generator import ScenarioGenerator
from training_data.trajectory_generator import TrajectoryGenerator
from training.train_laya import train_model
from training.calibrate_laya import calibrate_model
from training.evaluate_laya import evaluate_model
from training.export_laya import export_model
from training.benchmark_laya import run_benchmark


def main():
    print("=== [DOIP Phase 8.5] Active Learning Hard Example Harvesting & V2 Training ===")

    # 1. Harvest hard examples on high-stress scenarios
    print("Generating high-threat stress scenarios for active learning mining...")
    gen = ScenarioGenerator(seed=9999)
    stress_specs = [
        s for s in gen.generate_scenarios(count=200)
        if "EDGE" in s.family or "THREAT" in s.family or "LOGISTICS" in s.family or "WEATHER" in s.family
    ]
    print(f"Generated {len(stress_specs)} adversarial stress scenarios.")

    v1_ckpt = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "laya_doip_v1", "model.pt"))
    classifier = LayaSimulationClassifier(checkpoint_path=v1_ckpt)
    extractor = FeatureExtractor()
    rule_engine = RuleEngine()
    traj_gen = TrajectoryGenerator(rule_engine=rule_engine)
    collector = ActiveLearningCollector()

    harvested_samples = []
    print("Running trajectories through Laya v1 to mine hard examples (low confidence / divergence)...")
    for s_idx, spec in enumerate(stress_specs):
        states = traj_gen.generate_trajectory(spec)
        for state in states:
            feats = extractor.extract(state)
            r_eval = rule_engine.evaluate(state)
            l_eval = classifier.predict(feats, min_confidence=0.70)
            sample = collector.collect_sample(
                physics_state=state,
                rule_eval=r_eval,
                laya_eval=l_eval,
                scenario_id=spec.scenario_id,
                scenario_family=spec.family,
            )
            if sample is not None:
                harvested_samples.append(sample)

    print(f"Successfully harvested {len(harvested_samples):,} hard examples into {collector.collector_file}")

    # 2. Train laya_doip_v2 with injected hard examples
    print("\nTraining Laya V2 with Active Learning injection...")
    train_model(
        model_version="v2",
        epochs=10,
        batch_size=128,
        lr=1e-3,
        extra_hard_examples_path=collector.collector_file,
    )

    # 3. Calibrate laya_doip_v2
    print("\nCalibrating Laya V2 temperature...")
    calibrate_model(model_version="v2")

    # 4. Evaluate laya_doip_v2
    print("\nEvaluating Laya V2 on holdout benchmark...")
    evaluate_model(model_version="v2")

    # 5. Export and Benchmark laya_doip_v2
    print("\nExporting and benchmarking Laya V2...")
    export_model(model_version="v2")
    run_benchmark(model_version="v2", iterations=1000)

    print("\n=== Laya V2 Active Learning Pipeline Complete! ===")


if __name__ == "__main__":
    main()
