# Current Training Pipeline Analysis

**Document Date:** October 2026  
**Module:** `docs/laya_upgrade/CURRENT_TRAINING_PIPELINE.md`  
**Status:** Audit Complete  

---

## 1. Existing Scripts and Workflow

The Phase 8 baseline training pipeline resides in `training/` with supporting data generators in `backend/app/training/`:

```text
training/
├── prepare_dataset.py   # Invokes ScenarioGenerator (count=120) and DatasetBuilder
├── train_laya.py        # PyTorch multi-task training loop (15 epochs, AdamW)
├── calibrate.py         # Post-hoc temperature scaling grid search
├── evaluate.py          # Calculates test metrics, macro F1, ECE, latency
└── export.py            # Exports TorchScript model_traced.pt & manifest.json
```

Execution sequence:
```bash
python training/prepare_dataset.py
python training/train_laya.py
python training/calibrate.py
python training/evaluate.py
python training/export.py
```

---

## 2. Pipeline Stage Details

### Stage 1: Data Preparation (`prepare_dataset.py`)
- **Generator**: Generates 120 synthetic scenarios across 6 families: `BASELINE_PATROL`, `ADVERSE_WEATHER`, `ELECTRONIC_WARFARE`, `LOGISTICS_STRESS`, `COMBINED_HIGH_THREAT`, `BORDER_SURVEILLANCE`.
- **Trajectory Length**: 15–30 ticks per scenario.
- **Dataset Size**:
  - Total samples: 2,883
  - Train split (80%): 2,292 samples
  - Validation split (10%): 291 samples
  - Test split (10%): 300 samples
- **Format**: JSON files (`train.json`, `val.json`, `test.json`) in `data/laya_training/`.

### Stage 2: Model Training (`train_laya.py`)
- **Model**: `LayaNeuralScorer` (input_dim=15, hidden_dim=64, 2 Linear layers + LayerNorm + GELU + Dropout(0.1)).
- **Heads**: 6 discrete classification heads (`operational`, `outcome`, `logistics`, `comms`, `env`, `action`) + 1 continuous head (`risk_score`).
- **Loss Function**:
  $$\mathcal{L} = \mathcal{L}_{op} + \mathcal{L}_{out} + \mathcal{L}_{act} + 0.5\mathcal{L}_{log} + 0.5\mathcal{L}_{comms} + 0.5\mathcal{L}_{env} + 2.0\mathcal{L}_{risk}$$
  where classification heads use standard hard-label `CrossEntropyLoss` and risk uses `MSELoss`.
- **Optimizer**: `AdamW(lr=1e-3, weight_decay=1e-4)`. Batch size: 32. Epochs: 15.
- **Output Artifact**: `checkpoints/laya_doip_v1/model.pt`.

### Stage 3: Calibration (`calibrate.py`)
- Evaluates temperatures $T \in [0.1, 3.0]$ with step 0.1 on the validation set.
- Objective: Minimize cross-entropy / Brier score on `operational_state`.
- Found temperature: $T = 0.4$.
- Calibration output: `calibration.json`.

### Stage 4: Evaluation (`evaluate.py`)
- Evaluates on 300 test samples.
- Measured metrics recorded in `evaluation_report.json`:
  - Operational Accuracy: 84.0% (Macro F1: 0.4148)
  - Mission Outcome Accuracy: 100.0% (Macro F1: 0.2500 — complete class collapse!)
  - Action Accuracy: 74.0% (Macro F1: 0.3344)
  - Expected Calibration Error (ECE): 0.1427
  - Brier Score: 0.2585
  - Latency: Mean 0.234 ms (P95: 0.389 ms)

### Stage 5: Export (`export.py`)
- Exports traced model via `torch.jit.trace(model, dummy_input)`.
- Generates `checkpoints/laya_doip_v1/manifest.json`.

---

## 3. Critical Defects in Current Pipeline

1. **Severe Dataset Undersizing**: 2,883 samples is negligible for learning generalized physical boundaries across 15 continuous dimensions.
2. **Hard Labels Only**: Rule evaluations produce a single one-hot label per tick. No soft future branching distribution is modeled.
3. **Severe Class Imbalance**: All test samples for `mission_outcome` were labeled `SUCCESS`, yielding a misleading 100% accuracy with a fatal 0.25 Macro F1.
4. **Poor Calibration**: ECE is 0.1427, almost 3x higher than the required threshold ($<0.05$).
5. **No Experiment Tracking**: No organized directory structure (`experiments/`) recording git commits, dataset hashes, seeds, learning rate sweeps, and training histories.
6. **No Active Learning Retraining Pipeline**: Low confidence samples and rule-model disagreements are not systematically harvested or used for continuous fine-tuning.
