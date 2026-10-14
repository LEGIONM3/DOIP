"""Hostile Audit: Level 8 - Laya Neural Engine Reality & Authenticity Audit."""

import os
import sys
import json
import torch
import numpy as np
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./backend"))

from backend.app.laya_engine import LayaNeuralScorer, LayaSimulationClassifier, LayaDecisionEngine
from backend.app.simulation.feature_extractor import SimulationFeatures
from training.calibrate_laya import compute_ece_and_brier


def audit_laya_reality() -> Dict[str, Any]:
    print("\n--- [AUDIT LEVEL 8] Laya Training, Checkpoint & Inference Hostile Audit ---")
    results = {}

    # 1. Dataset Verification
    data_dir = Path("data/laya_training")
    train_path = data_dir / "train.json"
    val_path = data_dir / "val.json"
    test_path = data_dir / "test.json"
    quality_path = data_dir / "dataset_quality_report.json"

    dataset_audit = {
        "data_dir_exists": data_dir.exists(),
        "train_exists": train_path.exists(),
        "val_exists": val_path.exists(),
        "test_exists": test_path.exists(),
        "quality_report_exists": quality_path.exists(),
    }

    if train_path.exists():
        train_size_mb = round(train_path.stat().st_size / (1024 * 1024), 2)
        with open(train_path, "r", encoding="utf-8") as fp:
            train_samples = json.load(fp)
        dataset_audit["train_samples_count"] = len(train_samples)
        dataset_audit["train_file_size_mb"] = train_size_mb
        # Verify first sample structure
        s0 = train_samples[0]
        dataset_audit["sample_has_soft_labels"] = "soft_labels" in s0 and len(s0["soft_labels"]) > 0
        dataset_audit["sample_numeric_dim"] = len(s0.get("numeric_vector", []))

    if test_path.exists():
        with open(test_path, "r", encoding="utf-8") as fp:
            test_samples = json.load(fp)
        dataset_audit["test_samples_count"] = len(test_samples)

    print(f"Dataset Verified: {dataset_audit.get('train_samples_count', 0)} train, {dataset_audit.get('test_samples_count', 0)} test samples ({dataset_audit.get('train_file_size_mb', 0)} MB)")
    results["dataset"] = dataset_audit

    # 2. Checkpoints Weight & Norm Analysis (Detecting Fake / Mock / Uniform weights)
    checkpoints_audit = {}
    for v in ["laya_doip_v1", "laya_doip_v2"]:
        ckpt_dir = Path(f"checkpoints/{v}")
        pt_path = ckpt_dir / "model.pt"
        traced_path = ckpt_dir / "model_traced.pt"
        calib_path = ckpt_dir / "calibration.json"
        eval_path = ckpt_dir / "evaluation_report.json"

        v_audit = {
            "dir_exists": ckpt_dir.exists(),
            "model_pt_exists": pt_path.exists(),
            "model_traced_exists": traced_path.exists(),
            "calibration_exists": calib_path.exists(),
            "evaluation_exists": eval_path.exists(),
        }

        if pt_path.exists():
            saved = torch.load(pt_path, map_location="cpu")
            state_dict = saved.get("state_dict", saved)
            weight_keys = list(state_dict.keys())
            v_audit["num_weight_tensors"] = len(weight_keys)
            
            # Inspect first layer weights
            w0 = state_dict["encoder.0.weight"].numpy()
            v_audit["encoder_w0_shape"] = list(w0.shape)
            v_audit["encoder_w0_mean"] = float(np.mean(w0))
            v_audit["encoder_w0_std"] = float(np.std(w0))
            v_audit["encoder_w0_norm"] = float(np.linalg.norm(w0))
            # If standard deviation is 0 or extremely close, it's uninitialized or fake
            v_audit["is_non_trivial_trained_weights"] = bool(v_audit["encoder_w0_std"] > 0.01)

            # Test TorchScript loading
            traced_model = torch.jit.load(str(traced_path))
            test_tensor = torch.randn(5, 15)
            out_traced = traced_model(test_tensor)
            v_audit["torchscript_functional"] = bool(isinstance(out_traced, dict) and "operational_logits" in out_traced)

        if calib_path.exists():
            with open(calib_path, "r", encoding="utf-8") as fp:
                cdata = json.load(fp)
            v_audit["calibrated_temperature"] = cdata.get("calibrated_temperature")
            v_audit["post_calib_ece"] = cdata.get("post_calibration", {}).get("ece")
            v_audit["ece_target_met"] = cdata.get("target_met", False)

        print(f"Checkpoint {v}: weights std={v_audit.get('encoder_w0_std', 0):.4f}, TorchScript={v_audit.get('torchscript_functional')}, ECE={v_audit.get('post_calib_ece')}")
        checkpoints_audit[v] = v_audit

    results["checkpoints"] = checkpoints_audit

    # 3. Live Batch Inference and Empirical Calibration Test
    print("Testing live inference on 200 real test samples...")
    classifier = LayaSimulationClassifier(checkpoint_path="checkpoints/laya_doip_v1/model.pt")
    
    inference_latencies = []
    correct_ops = 0
    test_sub = test_samples[:200]
    
    for s in test_sub:
        feats = SimulationFeatures(
            numeric_vector=s["numeric_vector"],
            feature_names=["f" + str(i) for i in range(15)],
            raw_dict={},
            prompt_text="Audit prompt",
        )
        t0 = torch.cuda.Event(enable_timing=True) if torch.cuda.is_available() else None
        res = classifier.predict(feats, min_confidence=0.5)
        inference_latencies.append(res["latency_ms"])
        if res["raw_operational_state"] == s["labels"]["operational_state"]:
            correct_ops += 1

    sample_acc = round(correct_ops / len(test_sub), 4)
    p50_lat = float(np.percentile(inference_latencies, 50))
    p95_lat = float(np.percentile(inference_latencies, 95))
    
    print(f"Live Sample Accuracy (200 test cases): {sample_acc * 100:.2f}%")
    print(f"Measured P50 Latency: {p50_lat:.3f} ms | P95 Latency: {p95_lat:.3f} ms")

    results["live_inference"] = {
        "test_sample_count": len(test_sub),
        "measured_accuracy": sample_acc,
        "measured_p50_latency_ms": p50_lat,
        "measured_p95_latency_ms": p95_lat,
        "status": "PASSED" if sample_acc > 0.90 else "FAILED",
    }

    # 4. Abstention & Fallback Behavior Test
    # Pass pure noise vector to force low confidence
    noisy_feats = SimulationFeatures(
        numeric_vector=[0.0] * 15,
        feature_names=["f" + str(i) for i in range(15)],
        raw_dict={},
        prompt_text="Out of distribution noise",
    )
    abstain_res = classifier.predict(noisy_feats, min_confidence=0.99)
    results["abstention_test"] = {
        "abstained": abstain_res["abstained"],
        "gate_state": abstain_res["gate_state"],
        "operational_state": abstain_res["operational_state"],
        "status": "PASSED" if (abstain_res["abstained"] and abstain_res["operational_state"] == "UNCERTAIN") else "FAILED",
    }
    print(f"Abstention System Test: {results['abstention_test']['status']}")

    return results


def main():
    res = audit_laya_reality()
    out_json = Path("docs/verification/laya_reality_audit.json")
    with open(out_json, "w", encoding="utf-8") as fp:
        json.dump(res, fp, indent=2)
    print(f"\nAudit results persisted to {out_json}")


if __name__ == "__main__":
    main()
