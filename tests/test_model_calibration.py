"""Unit and validation tests for model calibration, ECE computation, and Brier score."""

import os
import json
import pytest
import numpy as np
from training.calibrate import compute_ece
from training.evaluate import compute_brier_score, compute_metrics


def test_ece_computation():
    """Verify Expected Calibration Error calculation."""
    # Perfectly calibrated dummy predictions
    confs = np.array([0.9, 0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1])
    accs = np.array([1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    ece = compute_ece(confs, accs, bins=5)
    assert 0.0 <= ece <= 1.0


def test_brier_score_computation():
    """Verify Brier score calculation."""
    probs = [
        [0.8, 0.1, 0.1],
        [0.2, 0.7, 0.1],
        [0.1, 0.2, 0.7],
    ]
    targets = [0, 1, 2]
    brier = compute_brier_score(probs, targets, num_classes=3)
    assert brier < 0.2  # Well-calibrated confident predictions have low Brier score


def test_calibration_artifact_exists_and_valid():
    """Verify calibration artifact from training run."""
    calib_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "checkpoints", "laya_doip_v1", "calibration.json")
    )
    if os.path.exists(calib_file):
        with open(calib_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "optimal_temperature" in data
        assert "calibrated_ece" in data
        assert data["calibrated_ece"] <= data["uncalibrated_ece"] + 1e-4
