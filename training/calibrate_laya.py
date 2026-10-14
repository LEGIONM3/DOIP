"""Model temperature calibration script targeting ECE < 0.05 for DOIP Phase 8.5."""

from __future__ import annotations
import sys
import os
import json
import argparse
from typing import Any
import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.laya_engine import LayaNeuralScorer, OPERATIONAL_STATES
from backend.app.training.dataset_builder import DatasetSample, OperationalDataset


def compute_ece_and_brier(
    probs: np.ndarray,
    labels: np.ndarray,
    num_bins: int = 10,
) -> tuple[float, float, list[dict[str, Any]]]:
    """Calculates Expected Calibration Error (ECE) and Brier Score."""
    confidences = np.max(probs, axis=1)
    predictions = np.argmax(probs, axis=1)
    accuracies = (predictions == labels).astype(float)

    n = len(labels)
    ece = 0.0
    bin_boundaries = np.linspace(0.0, 1.0, num_bins + 1)
    bin_details = []

    for i in range(num_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        bin_count = int(np.sum(in_bin))

        if bin_count > 0:
            bin_acc = float(np.mean(accuracies[in_bin]))
            bin_conf = float(np.mean(confidences[in_bin]))
            bin_error = abs(bin_acc - bin_conf)
            ece += (bin_count / n) * bin_error
            bin_details.append({
                "bin": i + 1,
                "range": [round(float(bin_lower), 2), round(float(bin_upper), 2)],
                "count": bin_count,
                "accuracy": round(bin_acc, 4),
                "confidence": round(bin_conf, 4),
                "calibration_error": round(bin_error, 4),
            })

    # Multiclass Brier score: 1/N sum_i sum_k (p_ik - y_ik)^2
    one_hot = np.zeros_like(probs)
    one_hot[np.arange(n), labels] = 1.0
    brier = float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))

    return float(ece), float(brier), bin_details


def calibrate_model(model_version: str = "v1") -> dict[str, Any]:
    print(f"\n=== [DOIP Phase 8.5] Calibrating Laya Decision Engine ({model_version.upper()}) ===")
    device = torch.device("cpu")
    ckpt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", f"laya_doip_{model_version}"))
    model_file = os.path.join(ckpt_dir, "model.pt")

    if not os.path.exists(model_file):
        raise FileNotFoundError(f"Model checkpoint not found: {model_file}")

    # Load validation data
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "laya_training"))
    val_path = os.path.join(data_dir, "val.json")
    with open(val_path, "r", encoding="utf-8") as f:
        val_data = json.load(f)

    samples = [
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
        for d in val_data
    ]
    val_ds = OperationalDataset(samples)
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=256, shuffle=False)

    # Load Model
    saved = torch.load(model_file, map_location=device)
    state_dict = saved.get("state_dict", saved)
    h_dim = state_dict["encoder.0.weight"].shape[0] if "encoder.0.weight" in state_dict else 64
    model = LayaNeuralScorer(hidden_dim=h_dim).to(device)
    model.load_state_dict(state_dict)
    model.eval()

    # Collect logits
    all_logits = []
    all_labels = []
    with torch.no_grad():
        for batch in val_loader:
            feats = batch["features"].to(device)
            out = model(feats)
            all_logits.append(out["operational_logits"].cpu())
            all_labels.append(batch["operational"].cpu())

    logits = torch.cat(all_logits, dim=0).numpy()
    labels = torch.cat(all_labels, dim=0).numpy()

    # Pre-calibration evaluation (T = 1.0)
    pre_probs = np.exp(logits) / np.sum(np.exp(logits), axis=-1, keepdims=True)
    pre_ece, pre_brier, pre_bins = compute_ece_and_brier(pre_probs, labels)
    print(f"Pre-Calibration (T=1.0)  -> ECE: {pre_ece:.4f} | Brier Score: {pre_brier:.4f}")

    # Temperature Optimization: search T in [0.05, 5.0] to minimize ECE / Brier
    best_t = 1.0
    best_ece = pre_ece
    best_brier = pre_brier

    temperatures = np.linspace(0.1, 4.0, 391)
    for t_cand in temperatures:
        scaled_logits = logits / t_cand
        probs = np.exp(scaled_logits - np.max(scaled_logits, axis=-1, keepdims=True))
        probs = probs / np.sum(probs, axis=-1, keepdims=True)
        ece, brier, _ = compute_ece_and_brier(probs, labels)

        # Optimize for minimum ECE with low Brier penalty
        score = ece + 0.1 * brier
        if ece < best_ece or (abs(ece - best_ece) < 1e-4 and brier < best_brier):
            best_ece = ece
            best_brier = brier
            best_t = float(t_cand)

    # If temperature needs further fine-tuning to meet ECE < 0.05
    scaled_logits = logits / best_t
    post_probs = np.exp(scaled_logits - np.max(scaled_logits, axis=-1, keepdims=True))
    post_probs = post_probs / np.sum(post_probs, axis=-1, keepdims=True)
    post_ece, post_brier, post_bins = compute_ece_and_brier(post_probs, labels)

    print(f"Post-Calibration (T={best_t:.3f}) -> ECE: {post_ece:.4f} | Brier Score: {post_brier:.4f}")
    target_met = post_ece < 0.05
    print(f"Target ECE < 0.05 Met: {'YES (SUCCESS)' if target_met else 'NO'}")

    calib_result = {
        "model_id": f"laya_doip_{model_version}",
        "calibrated_temperature": round(best_t, 4),
        "pre_calibration": {
            "ece": round(pre_ece, 4),
            "brier_score": round(pre_brier, 4),
            "temperature": 1.0,
        },
        "post_calibration": {
            "ece": round(post_ece, 4),
            "brier_score": round(post_brier, 4),
            "temperature": round(best_t, 4),
        },
        "target_threshold": 0.05,
        "target_met": target_met,
        "ece_reduction_pct": round(((pre_ece - post_ece) / max(1e-5, pre_ece)) * 100.0, 2),
        "calibration_bins": post_bins,
    }

    calib_path = os.path.join(ckpt_dir, "calibration.json")
    with open(calib_path, "w", encoding="utf-8") as f:
        json.dump(calib_result, f, indent=2)

    # Also update model checkpoint with calibrated temperature
    saved["temperature"] = best_t
    torch.save(saved, model_file)

    print(f"Calibration metadata saved to {calib_path}")
    return calib_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, default="v1", choices=["v1", "v2"])
    args = parser.parse_args()
    calibrate_model(model_version=args.version)


if __name__ == "__main__":
    main()
