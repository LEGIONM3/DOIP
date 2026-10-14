# DOIP Synthetic Training & Data Generation Pipeline

## 1. Overview & Anti-Hallucination Guarantees

Phase 8 adheres strictly to the **No Fake Training** invariant. All training data is generated through real physics simulations, labeled by authoritative rule evaluations, and trained with real PyTorch neural optimization loops.

```
Scenario Generator (120 Parameterized Specs)
              ↓
Physics Engine Trajectory Simulation (2,883 Steps)
              ↓
Rule Engine Ground-Truth Labeling
              ↓
Stratified Scenario Partitioning (80/10/10 Split Isolation)
              ↓
Data Output: data/laya_training/ (train.json, val.json, test.json)
```

## 2. Scenario Families

1. **`BASELINE_PATROL`**: Nominal conditions, clean comms, moderate speed (10-25 m/s).
2. **`ADVERSE_WEATHER`**: Gale force winds (15-32 m/s), torrential rain (15-50 mm/h), low visibility.
3. **`ELECTRONIC_WARFARE`**: Hostile RF jamming (0.4-0.95 intensity), long distance to relays (4-9 km).
4. **`LOGISTICS_STRESS`**: Critical initial fuel (5-25%), elevated mechanical wear (55-92%).
5. **`COMBINED_HIGH_THREAT`**: Concurrent storm, electronic warfare, and mechanical strain.
6. **`BORDER_SURVEILLANCE`**: High-speed intercept trajectories (20-30 m/s), prolonged patrol duration.

## 3. Strict Split Isolation

Partitioning is grouped strictly at the **scenario level**, not the step level:
- Scenarios in the `train` set (80%) never appear in `val` or `test`.
- Scenarios in `val` (10%) and `test` (10%) represent entirely unseen operational trajectories.
- Guarantees zero data leakage between training and evaluation.

## 4. Pipeline Execution Scripts

- `python training/prepare_dataset.py`: Synthesizes 2,883 operational states across 120 scenarios.
- `python training/train_laya.py`: Optimizes multi-task neural head over 15 epochs.
- `python training/calibrate.py`: Calibrates temperature scaling on validation set.
- `python training/evaluate.py`: Generates comprehensive evaluation report on test set.
- `python training/export.py`: Traces TorchScript model graph and builds production manifest.
