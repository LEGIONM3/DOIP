"""Evaluation pipeline calculating macro metrics, ECE, latency, and confusion matrices."""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
from training.evaluate_laya import evaluate_model


def compute_brier_score(probs, targets, num_classes: int = None) -> float:
    """Calculates multi-class Brier score."""
    probs = np.asarray(probs)
    targets = np.asarray(targets)
    n = len(targets)
    if num_classes is None:
        num_classes = probs.shape[1]
    one_hot = np.zeros_like(probs)
    one_hot[np.arange(n), targets] = 1.0
    return float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))


def compute_metrics(y_true, y_pred) -> dict:
    """Calculates accuracy, precision, recall, and macro F1 using pure numpy."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    accuracy = float(np.mean(y_true == y_pred))

    classes = np.unique(np.concatenate([y_true, y_pred]))
    precisions = []
    recalls = []
    f1s = []

    for c in classes:
        tp = np.sum((y_pred == c) & (y_true == c))
        fp = np.sum((y_pred == c) & (y_true != c))
        fn = np.sum((y_pred != c) & (y_true == c))

        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0

        precisions.append(p)
        recalls.append(r)
        f1s.append(f1)

    return {
        "accuracy": accuracy,
        "precision": float(np.mean(precisions)) if precisions else 0.0,
        "recall": float(np.mean(recalls)) if recalls else 0.0,
        "f1": float(np.mean(f1s)) if f1s else 0.0,
    }


def main():
    evaluate_model(model_version="v1")


if __name__ == "__main__":
    main()
