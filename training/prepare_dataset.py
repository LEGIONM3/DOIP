"""Generates >= 100,000 diverse operational synthetic dataset for Laya training with soft labels."""

import sys
import os
import json
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from training_data.dataset_builder import LargeScaleDatasetBuilder
from training_data.quality_validator import validate_dataset


def main():
    print("=== [DOIP Phase 8.5] Generating Large-Scale Operational Synthetic Training Data ===")
    target_count = 100000
    builder = LargeScaleDatasetBuilder(seed=2026)
    splits = builder.build_dataset(target_states=target_count)

    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "laya_training"))
    stats = builder.save_splits(splits, out_dir)

    print(f"\nRunning dataset quality validation on {out_dir}...")
    quality_report = validate_dataset(out_dir)

    print(f"\n=== Completed Dataset Preparation ===")
    print(f"Total Samples: {stats['total_samples']:,}")
    print(f"Train: {stats['train_samples']:,} | Val: {stats['val_samples']:,} | Test: {stats['test_samples']:,}")
    print(f"Quality Validation: {quality_report['validation_status']}")


if __name__ == "__main__":
    main()
