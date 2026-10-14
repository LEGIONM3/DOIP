# Current Datasets Audit & Gap Analysis

**Document Date:** October 2026  
**Module:** `docs/laya_upgrade/CURRENT_DATASETS.md`  
**Status:** Audit Complete  

---

## 1. Inventory of Current Datasets

The repository currently maintains training data in `data/laya_training/`:

| File | Size on Disk | Record Count | Purpose |
|---|---|---|---|
| `train.json` | 2,548,060 bytes (~2.5 MB) | 2,292 | Training split |
| `val.json` | 323,743 bytes (~324 KB) | 291 | Validation / Hyperparameter tuning split |
| `test.json` | 333,427 bytes (~333 KB) | 300 | Hold-out benchmark evaluation split |
| `dataset_stats.json` | 345 bytes | N/A | Metadata summary |

Total world states across all splits: **2,883 samples**.

---

## 2. Sample Schema and Structure

Each record in `train.json`, `val.json`, and `test.json` adheres to the following structure:
```json
{
  "sample_id": "SCEN-0001_t000",
  "scenario_id": "SCEN-0001",
  "scenario_family": "BASELINE_PATROL",
  "tick": 0,
  "numeric_vector": [
    0.4858, 0.5473, 0.435, 0.125, 0.842, 1.0, 0.125, 0.0, 0.8, 0.1333, 0.6818, 0.0, 0.12, 0.1875, 0.75
  ],
  "prompt_text": "Operational telemetry for unit PATROL-001 (PATROL) at tick 0:\nKinematics: Position (12.9716, 77.5946), Heading 45.0 deg, Speed 13.1 m/s (max 30.0 m/s).\n...",
  "labels": {
    "operational_state": "NORMAL",
    "mission_outcome": "SUCCESS",
    "logistics_state": "HEALTHY",
    "comms_state": "CONNECTED",
    "environmental_impact": "LOW",
    "recommended_action": "CONTINUE",
    "risk_score": 0.12
  }
}
```

---

## 3. Analysis of Dataset Deficiencies

### Defect 1: Insufficient Volume (< 3,000 vs Target 100,000+)
At only 2,883 samples across 120 scenario runs, the continuous 15-dimensional state space is sparsely populated. The model suffers from high variance and poor generalizability when subjected to novel combinations of jamming, weather, and fuel burn.

### Defect 2: Extreme Class Collapse
Inspection of the labels reveals severe class distribution pathology:
- **`mission_outcome`**: ~98.5% of samples in `train.json` are labeled `SUCCESS`. In `test.json`, 100% of samples are `SUCCESS`, resulting in a catastrophic macro F1 score of 0.25.
- **`operational_state`**: Dominated by `NORMAL` (>75%) and `DEGRADED` (~18%). Critical emergencies (`CRITICAL` and `FAILED`) comprise $<7\%$ of samples.
- **`recommended_action`**: `CONTINUE` is over-represented (>80%), while `ABORT`, `PAUSE`, and `RESUPPLY` are sparsely sampled.

### Defect 3: Absence of Soft Probability Labels
The existing dataset utilizes exclusively deterministic, single-step hard labels. Operational wargaming inherently involves stochastic branching: given an asset at 15% fuel facing heavy weather, the actual future outcome is a distribution:
$$\{ \text{SUCCESS}: 0.20, \text{DELAYED}: 0.55, \text{ABORTED}: 0.15, \text{FAILED}: 0.10 \}$$
Without soft labels generated from multi-future rollouts, the neural model cannot learn calibrated uncertainty distributions.

### Defect 4: Missing Edge Case Stress Testing
Scenarios rarely push systems to true boundary limits:
- Complete fuel exhaustion ($0\%$) under movement.
- High-intensity electronic warfare ($\text{jamming} > 0.95$, SNR $\le -120$ dBm).
- Category 5 weather extremes ($\text{wind} > 35$ m/s, $\text{rain} > 50$ mm/hr).
- Severe mechanical breakdown ($\text{wear} > 95\%$).

---

## 4. Dataset Target Specification for Phase 8.5

- **Minimum Size**: 100,000 unique world states (with stretch capability to 500,000).
- **Balanced Class Generation**: Targeted scenario injection ensuring minimum 15% representations for `CRITICAL` and `FAILED` states.
- **Soft Label Multi-Future Branching**: Each representative state rollout evaluated across 100 nearby future perturbations to generate authentic empirical outcome probability distributions.
- **Rigorous Validation**: Automated quality validator script (`quality_validator.py`) reporting class balance, edge case representation, Shannon entropy, and feature distribution metrics.
