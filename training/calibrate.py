"""Calibration pipeline for Laya operational model.

Fits temperature scaling to optimize softmax probabilities and minimize Expected Calibration Error (ECE).
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
from training.calibrate_laya import calibrate_model, compute_ece_and_brier


def compute_ece(confidences, accuracies, bins: int = 10) -> float:
    """Calculates Expected Calibration Error given confidences and 0/1 accuracies."""
    confidences = np.asarray(confidences)
    accuracies = np.asarray(accuracies)
    n = len(confidences)
    bin_boundaries = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for i in range(bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        bin_count = int(np.sum(in_bin))
        if bin_count > 0:
            bin_acc = float(np.mean(accuracies[in_bin]))
            bin_conf = float(np.mean(confidences[in_bin]))
            ece += (bin_count / n) * abs(bin_acc - bin_conf)
    return float(ece)


def main():
    calibrate_model(model_version="v1")


if __name__ == "__main__":
    main()
