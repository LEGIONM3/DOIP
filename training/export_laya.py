"""Export script compiling PyTorch model to TorchScript and manifest package."""

from __future__ import annotations
import sys
import os
import json
import argparse
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.laya_engine import (
    LayaNeuralScorer,
    OPERATIONAL_STATES,
    MISSION_OUTCOMES,
    ACTIONS,
    LOGISTICS_STATES,
    COMMS_STATES,
)


def export_model(model_version: str = "v1") -> str:
    print(f"\n=== [DOIP Phase 8.5] Exporting Laya Model ({model_version.upper()}) ===")
    ckpt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", f"laya_doip_{model_version}"))
    model_file = os.path.join(ckpt_dir, "model.pt")

    if not os.path.exists(model_file):
        raise FileNotFoundError(f"Model file not found: {model_file}")

    device = torch.device("cpu")
    saved = torch.load(model_file, map_location=device)
    state_dict = saved.get("state_dict", saved)
    h_dim = state_dict["encoder.0.weight"].shape[0] if "encoder.0.weight" in state_dict else 64
    model = LayaNeuralScorer(input_dim=15, hidden_dim=h_dim).to(device)
    model.load_state_dict(state_dict)
    model.eval()

    dummy_input = torch.zeros((1, 15), dtype=torch.float32, device=device)
    traced_model = torch.jit.trace(model, dummy_input, strict=False)
    traced_path = os.path.join(ckpt_dir, "model_traced.pt")
    traced_model.save(traced_path)

    # Verification: compare outputs
    with torch.no_grad():
        out_eager = model(dummy_input)
        out_traced = traced_model(dummy_input)
        diff = float((out_eager["operational_logits"] - out_traced["operational_logits"]).abs().max())
        assert diff < 1e-5, f"Traced model discrepancy: {diff}"

    # Load calibration info if present
    temperature = saved.get("temperature", 1.0)
    calib_file = os.path.join(ckpt_dir, "calibration.json")
    if os.path.exists(calib_file):
        with open(calib_file, "r", encoding="utf-8") as f:
            cdata = json.load(f)
            temperature = float(cdata.get("calibrated_temperature", temperature))

    manifest = {
        "model_id": f"laya_doip_{model_version}",
        "architecture": "LayaNeuralScorer / Non-Autoregressive System 1",
        "input_features": 15,
        "hidden_dim": 64,
        "calibrated_temperature": round(temperature, 4),
        "task_heads": {
            "operational_state": OPERATIONAL_STATES,
            "mission_outcome": MISSION_OUTCOMES,
            "recommended_action": ACTIONS,
            "logistics_state": LOGISTICS_STATES,
            "comms_state": COMMS_STATES,
            "risk_score": "continuous_score_[0,1]",
        },
        "artifacts": {
            "weights": "model.pt",
            "traced_model": "model_traced.pt",
            "metadata": "metadata.json",
            "calibration": "calibration.json",
            "evaluation": "evaluation_report.json",
        },
    }

    manifest_path = os.path.join(ckpt_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Exported TorchScript traced model to: {traced_path}")
    print(f"Manifest written to: {manifest_path}")
    return traced_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, default="v1", choices=["v1", "v2"])
    args = parser.parse_args()
    export_model(model_version=args.version)


if __name__ == "__main__":
    main()
