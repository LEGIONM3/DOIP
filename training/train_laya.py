"""High-throughput multi-task training script for Laya with soft distribution alignment."""

from __future__ import annotations
import sys
import os
import json
import time
import argparse
from typing import Any
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.laya_engine import (
    LayaNeuralScorer,
    OPERATIONAL_STATES,
    MISSION_OUTCOMES,
    LOGISTICS_STATES,
    COMMS_STATES,
    ENV_IMPACTS,
    ACTIONS,
)
from backend.app.training.dataset_builder import DatasetSample, OperationalDataset


def load_dataset_samples(path: str) -> list[DatasetSample]:
    """Loads dataset split from disk and instantiates typed DatasetSample objects."""
    if not os.path.exists(path) and os.path.exists(path + ".zip"):
        import zipfile
        print(f"Extracting {path}.zip...")
        with zipfile.ZipFile(path + ".zip", "r") as zip_ref:
            zip_ref.extractall(os.path.dirname(path))
    print(f"Loading samples from {path}...")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    samples = []
    for d in data:
        samples.append(
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
        )
    print(f"Successfully loaded {len(samples):,} samples from {path}")
    return samples


load_samples = load_dataset_samples


def soft_cross_entropy_loss(logits: torch.Tensor, soft_targets: torch.Tensor) -> torch.Tensor:
    """Computes cross-entropy loss against soft probability distributions: -sum(q * log_softmax(z))."""
    log_probs = F.log_softmax(logits, dim=-1)
    loss = -(soft_targets * log_probs).sum(dim=-1).mean()
    return loss


def train_model(
    model_version: str = "v1",
    epochs: int = 10,
    batch_size: int = 128,
    lr: float = 1.5e-3,
    extra_hard_examples_path: str | None = None,
) -> dict[str, Any]:
    device = torch.device("cpu")
    print(f"\n=================================================================")
    print(f"=== [DOIP Phase 8.5] Training Laya Model ({model_version.upper()}) ===")
    print(f"=================================================================")
    print(f"Device: {device} | Epochs: {epochs} | Batch Size: {batch_size} | Learning Rate: {lr}")

    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "laya_training"))
    train_path = os.path.join(data_dir, "train.json")
    val_path = os.path.join(data_dir, "val.json")

    train_samples = load_dataset_samples(train_path)
    val_samples = load_dataset_samples(val_path)

    # If active learning hard examples are provided for v2, inject them
    if extra_hard_examples_path and os.path.exists(extra_hard_examples_path):
        print(f"Injecting active learning hard examples from {extra_hard_examples_path}...")
        hard_samples = load_dataset_samples(extra_hard_examples_path)
        train_samples.extend(hard_samples)
        print(f"Total training samples after active learning injection: {len(train_samples):,}")

    train_ds = OperationalDataset(train_samples)
    val_ds = OperationalDataset(val_samples)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size * 2, shuffle=False)

    ckpt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", f"laya_doip_{model_version}"))
    os.makedirs(ckpt_dir, exist_ok=True)
    model_file = os.path.join(ckpt_dir, "model.pt")

    model = LayaNeuralScorer(input_dim=15, hidden_dim=128).to(device)

    # If fine-tuning v2 from v1 weights
    if model_version == "v2":
        v1_ckpt = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "laya_doip_v1", "model.pt"))
        if os.path.exists(v1_ckpt):
            print(f"Loading initial weights from {v1_ckpt} for v2 fine-tuning...")
            saved = torch.load(v1_ckpt, map_location=device)
            state_dict = saved.get("state_dict", saved)
            if state_dict.get("encoder.0.weight", None) is not None and state_dict["encoder.0.weight"].shape[0] == 128:
                model.load_state_dict(state_dict)

    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion_mse = nn.MSELoss()

    best_val_loss = float("inf")
    history: list[dict[str, Any]] = []
    start_train_time = time.time()

    for epoch in range(1, epochs + 1):
        epoch_start = time.time()
        model.train()
        train_loss = 0.0
        batches_processed = 0

        for batch in train_loader:
            feats = batch["features"].to(device)
            op_hard = batch["operational"].to(device)
            out_hard = batch["outcome"].to(device)
            act_hard = batch["action"].to(device)
            log_hard = batch["logistics"].to(device)
            comms_hard = batch["comms"].to(device)

            op_soft = batch["operational_soft"].to(device)
            out_soft = batch["outcome_soft"].to(device)
            log_soft = batch["logistics_soft"].to(device)
            comms_soft = batch["comms_soft"].to(device)
            act_soft = batch["action_soft"].to(device)
            risk_tgt = batch["risk"].to(device)

            optimizer.zero_grad()
            preds = model(feats)

            l_op = 0.6 * F.cross_entropy(preds["operational_logits"], op_hard) + 0.4 * soft_cross_entropy_loss(preds["operational_logits"], op_soft)
            l_out = 0.6 * F.cross_entropy(preds["outcome_logits"], out_hard) + 0.4 * soft_cross_entropy_loss(preds["outcome_logits"], out_soft)
            l_act = 0.6 * F.cross_entropy(preds["action_logits"], act_hard) + 0.4 * soft_cross_entropy_loss(preds["action_logits"], act_soft)
            l_log = 0.6 * F.cross_entropy(preds["logistics_logits"], log_hard) + 0.4 * soft_cross_entropy_loss(preds["logistics_logits"], log_soft)
            l_comms = 0.6 * F.cross_entropy(preds["comms_logits"], comms_hard) + 0.4 * soft_cross_entropy_loss(preds["comms_logits"], comms_soft)
            l_risk = criterion_mse(preds["risk_score"], risk_tgt)

            # Balanced multi-task loss
            loss = (2.0 * l_op) + (2.0 * l_out) + (1.5 * l_act) + (0.5 * l_log) + (0.5 * l_comms) + (2.0 * l_risk)
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            batches_processed += 1

        scheduler.step()
        avg_train_loss = train_loss / max(1, batches_processed)

        # Validation pass
        model.eval()
        val_loss = 0.0
        val_batches = 0
        op_correct = 0
        outcome_correct = 0
        action_correct = 0
        total_val = len(val_ds)

        with torch.no_grad():
            for batch in val_loader:
                feats = batch["features"].to(device)
                op_hard = batch["operational"].to(device)
                out_hard = batch["outcome"].to(device)
                act_hard = batch["action"].to(device)
                log_hard = batch["logistics"].to(device)
                comms_hard = batch["comms"].to(device)

                op_soft = batch["operational_soft"].to(device)
                out_soft = batch["outcome_soft"].to(device)
                log_soft = batch["logistics_soft"].to(device)
                comms_soft = batch["comms_soft"].to(device)
                act_soft = batch["action_soft"].to(device)
                risk_tgt = batch["risk"].to(device)

                preds = model(feats)
                l_op = 0.6 * F.cross_entropy(preds["operational_logits"], op_hard) + 0.4 * soft_cross_entropy_loss(preds["operational_logits"], op_soft)
                l_out = 0.6 * F.cross_entropy(preds["outcome_logits"], out_hard) + 0.4 * soft_cross_entropy_loss(preds["outcome_logits"], out_soft)
                l_act = 0.6 * F.cross_entropy(preds["action_logits"], act_hard) + 0.4 * soft_cross_entropy_loss(preds["action_logits"], act_soft)
                l_log = 0.6 * F.cross_entropy(preds["logistics_logits"], log_hard) + 0.4 * soft_cross_entropy_loss(preds["logistics_logits"], log_soft)
                l_comms = 0.6 * F.cross_entropy(preds["comms_logits"], comms_hard) + 0.4 * soft_cross_entropy_loss(preds["comms_logits"], comms_soft)
                l_risk = criterion_mse(preds["risk_score"], risk_tgt)

                loss = (2.0 * l_op) + (2.0 * l_out) + (1.5 * l_act) + (0.5 * l_log) + (0.5 * l_comms) + (2.0 * l_risk)
                val_loss += loss.item()
                val_batches += 1

                op_correct += (preds["operational_logits"].argmax(dim=-1) == op_hard).sum().item()
                outcome_correct += (preds["outcome_logits"].argmax(dim=-1) == out_hard).sum().item()
                action_correct += (preds["action_logits"].argmax(dim=-1) == act_hard).sum().item()

        avg_val_loss = val_loss / max(1, val_batches)
        op_acc = op_correct / total_val
        out_acc = outcome_correct / total_val
        act_acc = action_correct / total_val
        epoch_sec = time.time() - epoch_start

        epoch_stats = {
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(avg_val_loss, 4),
            "op_acc": round(op_acc, 4),
            "outcome_acc": round(out_acc, 4),
            "action_acc": round(act_acc, 4),
            "time_sec": round(epoch_sec, 2),
        }
        history.append(epoch_stats)

        print(
            f"Epoch {epoch:02d}/{epochs:02d} | Train Loss: {avg_train_loss:.4f} | "
            f"Val Loss: {avg_val_loss:.4f} | Op Acc: {op_acc*100:.2f}% | "
            f"Out Acc: {out_acc*100:.2f}% | Act Acc: {act_acc*100:.2f}% | Time: {epoch_sec:.1f}s"
        )

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            # Save checkpoint
            torch.save(
                {
                    "model_id": f"laya_doip_{model_version}",
                    "state_dict": model.state_dict(),
                    "epoch": epoch,
                    "val_loss": best_val_loss,
                    "op_acc": op_acc,
                    "outcome_acc": out_acc,
                    "action_acc": act_acc,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                model_file,
            )

    total_training_sec = time.time() - start_train_time
    print(f"\nTraining Complete in {total_training_sec:.1f}s! Best Val Loss: {best_val_loss:.4f}")
    print(f"Saved Checkpoint to: {model_file}")

    metadata = {
        "model_id": f"laya_doip_{model_version}",
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": lr,
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
        "best_val_loss": round(best_val_loss, 4),
        "final_operational_acc": round(op_acc, 4),
        "final_outcome_acc": round(out_acc, 4),
        "final_action_acc": round(act_acc, 4),
        "training_time_sec": round(total_training_sec, 2),
        "checkpoint_file": model_file,
        "history": history,
    }

    meta_path = os.path.join(ckpt_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Save to experiments/
    exp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "experiments"))
    os.makedirs(exp_dir, exist_ok=True)
    exp_file = os.path.join(exp_dir, f"exp_{model_version}_{int(time.time())}.json")
    with open(exp_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Experiment log saved to: {exp_file}")

    return metadata


def main():
    parser = argparse.ArgumentParser(description="Train Laya decision engine")
    parser.add_argument("--version", type=str, default="v1", choices=["v1", "v2"], help="Model version (v1 or v2)")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size")
    parser.add_argument("--lr", type=float, default=1.5e-3, help="Learning rate")
    parser.add_argument("--hard-examples", type=str, default=None, help="Path to hard examples JSON for active learning")
    args = parser.parse_args()

    train_model(
        model_version=args.version,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        extra_hard_examples_path=args.hard_examples,
    )


if __name__ == "__main__":
    main()
