"""Comprehensive test set evaluation and benchmarking script for Laya decision engine."""

from __future__ import annotations
import sys
import os
import json
import time
import argparse
from typing import Any
import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.laya_engine import (
    LayaNeuralScorer,
    OPERATIONAL_STATES,
    MISSION_OUTCOMES,
    LOGISTICS_STATES,
    COMMS_STATES,
    ACTIONS,
)
from backend.app.training.dataset_builder import DatasetSample, OperationalDataset
from training.calibrate_laya import compute_ece_and_brier


def compute_classification_metrics(y_true: list[int], y_pred: list[int], class_names: list[str]) -> dict[str, Any]:
    """Computes accuracy, per-class metrics, macro precision, macro recall, and macro F1."""
    num_classes = len(class_names)
    matrix = np.zeros((num_classes, num_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            matrix[t, p] += 1

    total = len(y_true)
    correct = sum(matrix[i, i] for i in range(num_classes))
    accuracy = correct / max(1, total)

    precisions = []
    recalls = []
    f1s = []
    per_class = {}

    for i, c_name in enumerate(class_names):
        tp = matrix[i, i]
        fp = sum(matrix[j, i] for j in range(num_classes) if j != i)
        fn = sum(matrix[i, j] for j in range(num_classes) if j != i)

        prec = tp / max(1, tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / max(1, tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / max(1e-9, prec + rec) if (prec + rec) > 0 else 0.0

        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)
        per_class[c_name] = {
            "support": int(tp + fn),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
        }

    macro_prec = float(np.mean(precisions))
    macro_rec = float(np.mean(recalls))
    macro_f1 = float(np.mean(f1s))

    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_prec, 4),
        "macro_recall": round(macro_rec, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
    }


def evaluate_model(model_version: str = "v1") -> dict[str, Any]:
    print(f"\n=== [DOIP Phase 8.5] Comprehensive Evaluation of Laya ({model_version.upper()}) ===")
    device = torch.device("cpu")
    ckpt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", f"laya_doip_{model_version}"))
    model_file = os.path.join(ckpt_dir, "model.pt")

    if not os.path.exists(model_file):
        raise FileNotFoundError(f"Missing model checkpoint: {model_file}")

    # Load calibration info if available
    calib_file = os.path.join(ckpt_dir, "calibration.json")
    temperature = 1.0
    if os.path.exists(calib_file):
        with open(calib_file, "r", encoding="utf-8") as f:
            cdata = json.load(f)
            temperature = float(cdata.get("calibrated_temperature", 1.0))

    print(f"Loaded calibrated temperature: T = {temperature:.4f}")

    # Load test split
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "laya_training"))
    test_path = os.path.join(data_dir, "test.json")
    with open(test_path, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    test_samples = [
        DatasetSample(
            sample_id=d["sample_id"],
            scenario_id=d["scenario_id"],
            scenario_family=d.get("scenario_family", "PATROL"),
            tick=d["tick"],
            numeric_vector=d["numeric_vector"],
            prompt_text=d["prompt_text"],
            labels=d["labels"],
            soft_labels=d.get("soft_labels", {}),
        )
        for d in test_data
    ]
    test_ds = OperationalDataset(test_samples)
    test_loader = torch.utils.data.DataLoader(test_ds, batch_size=256, shuffle=False)

    # Load Model
    saved = torch.load(model_file, map_location=device)
    state_dict = saved.get("state_dict", saved)
    h_dim = state_dict["encoder.0.weight"].shape[0] if "encoder.0.weight" in state_dict else 64
    model = LayaNeuralScorer(hidden_dim=h_dim).to(device)
    model.load_state_dict(state_dict)
    model.eval()

    # Track predictions & latencies
    latencies: list[float] = []
    true_op, pred_op = [], []
    true_out, pred_out = [], []
    true_act, pred_act = [], []
    true_log, pred_log = [], []
    true_com, pred_com = [], []

    all_op_probs = []
    true_risk, pred_risk = [], []
    confidences = []

    with torch.no_grad():
        for batch in test_loader:
            feats = batch["features"].to(device)
            t0 = time.perf_counter()
            out = model(feats)
            t_batch = (time.perf_counter() - t0) * 1000.0 / len(feats)
            latencies.extend([t_batch] * len(feats))

            # Temperature-scaled probabilities
            op_p = F.softmax(out["operational_logits"] / temperature, dim=-1).cpu().numpy()
            out_p = F.softmax(out["outcome_logits"] / temperature, dim=-1).cpu().numpy()
            act_p = F.softmax(out["action_logits"] / temperature, dim=-1).cpu().numpy()
            log_p = F.softmax(out["logistics_logits"] / temperature, dim=-1).cpu().numpy()
            com_p = F.softmax(out["comms_logits"] / temperature, dim=-1).cpu().numpy()

            all_op_probs.append(op_p)

            pred_op.extend(np.argmax(op_p, axis=1).tolist())
            pred_out.extend(np.argmax(out_p, axis=1).tolist())
            pred_act.extend(np.argmax(act_p, axis=1).tolist())
            pred_log.extend(np.argmax(log_p, axis=1).tolist())
            pred_com.extend(np.argmax(com_p, axis=1).tolist())

            true_op.extend(batch["operational"].cpu().tolist())
            true_out.extend(batch["outcome"].cpu().tolist())
            true_act.extend(batch["action"].cpu().tolist())
            true_log.extend(batch["logistics"].cpu().tolist())
            true_com.extend(batch["comms"].cpu().tolist())

            r_true = batch["risk"].cpu().numpy()
            r_pred = out["risk_score"].cpu().numpy()
            true_risk.extend(r_true.tolist())
            pred_risk.extend(r_pred.tolist())

            # Mean top-choice confidence
            batch_conf = (np.max(op_p, axis=1) + np.max(out_p, axis=1) + np.max(act_p, axis=1)) / 3.0
            confidences.extend(batch_conf.tolist())

    op_metrics = compute_classification_metrics(true_op, pred_op, OPERATIONAL_STATES)
    out_metrics = compute_classification_metrics(true_out, pred_out, MISSION_OUTCOMES)
    act_metrics = compute_classification_metrics(true_act, pred_act, ACTIONS)
    log_metrics = compute_classification_metrics(true_log, pred_log, LOGISTICS_STATES)
    com_metrics = compute_classification_metrics(true_com, pred_com, COMMS_STATES)

    # Critical Recall: recall specifically on CRITICAL and FAILED operational states
    crit_indices = [OPERATIONAL_STATES.index("CRITICAL"), OPERATIONAL_STATES.index("FAILED")]
    crit_true_total = sum(1 for t in true_op if t in crit_indices)
    crit_correct = sum(1 for t, p in zip(true_op, pred_op) if t in crit_indices and p == t)
    critical_recall = crit_correct / max(1, crit_true_total)

    # Calibration on test set
    op_probs_all = np.vstack(all_op_probs)
    test_ece, test_brier, _ = compute_ece_and_brier(op_probs_all, np.array(true_op))

    # Abstention rates
    conf_arr = np.array(confidences)
    abstain_65 = float(np.mean(conf_arr < 0.65))
    abstain_80 = float(np.mean(conf_arr < 0.80))

    # Risk errors
    risk_mae = float(np.mean(np.abs(np.array(true_risk) - np.array(pred_risk))))
    risk_rmse = float(np.sqrt(np.mean((np.array(true_risk) - np.array(pred_risk)) ** 2)))

    # Latency percentiles
    lat_arr = np.array(latencies)
    lat_stats = {
        "mean_ms": round(float(np.mean(lat_arr)), 3),
        "p50_ms": round(float(np.percentile(lat_arr, 50)), 3),
        "p95_ms": round(float(np.percentile(lat_arr, 95)), 3),
        "p99_ms": round(float(np.percentile(lat_arr, 99)), 3),
    }

    report = {
        "model_id": f"laya_doip_{model_version}",
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "test_samples": len(test_samples),
        "calibrated_temperature": round(temperature, 4),
        "tasks": {
            "operational_state": {
                "accuracy": op_metrics["accuracy"],
                "macro_precision": op_metrics["macro_precision"],
                "macro_recall": op_metrics["macro_recall"],
                "macro_f1": op_metrics["macro_f1"],
                "per_class": op_metrics["per_class"],
            },
            "mission_outcome": {
                "accuracy": out_metrics["accuracy"],
                "macro_precision": out_metrics["macro_precision"],
                "macro_recall": out_metrics["macro_recall"],
                "macro_f1": out_metrics["macro_f1"],
                "per_class": out_metrics["per_class"],
            },
            "recommended_action": {
                "accuracy": act_metrics["accuracy"],
                "macro_precision": act_metrics["macro_precision"],
                "macro_recall": act_metrics["macro_recall"],
                "macro_f1": act_metrics["macro_f1"],
                "per_class": act_metrics["per_class"],
            },
            "logistics_state": {
                "accuracy": log_metrics["accuracy"],
                "macro_f1": log_metrics["macro_f1"],
            },
            "comms_state": {
                "accuracy": com_metrics["accuracy"],
                "macro_f1": com_metrics["macro_f1"],
            },
        },
        "critical_recall": round(critical_recall, 4),
        "calibration": {
            "expected_calibration_error_ece": round(test_ece, 4),
            "brier_score": round(test_brier, 4),
            "ece_target_met": test_ece < 0.05,
        },
        "risk_estimation": {
            "mae": round(risk_mae, 4),
            "rmse": round(risk_rmse, 4),
        },
        "abstention_rates": {
            "threshold_0_65": round(abstain_65, 4),
            "threshold_0_80": round(abstain_80, 4),
        },
        "latency": lat_stats,
    }

    report_path = os.path.join(ckpt_dir, "evaluation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    cm_path = os.path.join(ckpt_dir, "confusion_matrices.json")
    with open(cm_path, "w", encoding="utf-8") as f:
        json.dump({
            "operational_state": op_metrics["confusion_matrix"],
            "mission_outcome": out_metrics["confusion_matrix"],
            "recommended_action": act_metrics["confusion_matrix"],
        }, f, indent=2)

    print("\n=== Evaluation Results ===")
    print(f"Operational State Accuracy: {op_metrics['accuracy']*100:.2f}% (Macro F1: {op_metrics['macro_f1']:.4f})")
    print(f"Mission Outcome Accuracy:   {out_metrics['accuracy']*100:.2f}% (Macro F1: {out_metrics['macro_f1']:.4f})")
    print(f"Recommended Action Accuracy:{act_metrics['accuracy']*100:.2f}% (Macro F1: {act_metrics['macro_f1']:.4f})")
    print(f"Critical Recall (>97% tgt): {critical_recall*100:.2f}%")
    print(f"Expected Calibration Error: {test_ece:.4f} (Target < 0.05: {'MET' if test_ece < 0.05 else 'NOT MET'})")
    print(f"Inference Latency: P50={lat_stats['p50_ms']} ms | P95={lat_stats['p95_ms']} ms")
    print(f"Saved evaluation report to {report_path}")

    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, default="v1", choices=["v1", "v2"])
    args = parser.parse_args()
    evaluate_model(model_version=args.version)


if __name__ == "__main__":
    main()
