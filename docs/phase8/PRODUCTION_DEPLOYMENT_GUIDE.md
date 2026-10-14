# DOIP Laya Production Deployment Guide

## 1. Production Artifacts & Directory Structure

All trained checkpoints, serialized graphs, and calibration parameters are located in `checkpoints/laya_doip_v1/`:

```text
checkpoints/laya_doip_v1/
├── model.pt                 # PyTorch state_dict & calibrated temperature
├── model_traced.pt          # JIT TorchScript traced graph for C++ / high-speed serving
├── manifest.json            # Model architecture schema and input feature contracts
├── calibration.json         # Temperature calibration and ECE validation metrics
├── metadata.json            # Training run hyperparameters and epoch metrics
└── evaluation_report.json   # Full test set performance scorecard
```

## 2. Air-Gapped Operation

In restricted tactical command centers without Internet connectivity or Hugging Face Hub access:
- The system automatically detects and loads local weights from `checkpoints/laya_doip_v1/model.pt`.
- Feature normalization executes locally without remote embedding calls.
- In case of missing checkpoints, the simulation automatically operates in `DETERMINISTIC_SIM` mode with 100% authoritative rule coverage.

## 3. REST API Contracts

### `POST /api/simulation/hybrid/step`
Executes single hybrid step with state update, rule checking, and Laya decision.
```json
{
  "dt_sec": 1.0,
  "target_speed_mps": 15.0,
  "target_heading_deg": 90.0,
  "mode": "HYBRID_AI_SIM",
  "confidence_threshold": 0.65
}
```

### `POST /api/simulation/hybrid/run`
Executes multi-tick trajectory with consensus outcome reporting.
```json
{
  "ticks": 20,
  "dt_sec": 1.0,
  "perturbations": {
    "wind_speed_mps": 12.0,
    "jamming_intensity": 0.4
  },
  "confidence_threshold": 0.65
}
```

### `POST /api/laya/decide`
Executes pure non-autoregressive decision inference.
```json
{
  "features": [0.5, 0.5, 0.6, 0.25, 0.8, 1.0, 0.2, 0.0, 0.7, 0.1, 0.7, 0.0, 0.1, 0.2, 0.9],
  "min_confidence": 0.65
}
```
