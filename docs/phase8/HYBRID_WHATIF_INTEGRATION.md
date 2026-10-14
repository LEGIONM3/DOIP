# DOIP Hybrid What-If Simulation Integration

## 1. Overview

DOIP Phase 8 seamlessly extends the massive What-If engine (`backend/app/massive_whatif.py`) and Future Generator (`backend/app/future_generator.py`) with hybrid intelligence:
- The **Physics Engine** models physical vehicle dynamics and RF degradation across thousands of Monte Carlo runs.
- The **Rule Engine** enforces physical and tactical safety invariants.
- The **Laya Decision Engine** scores risk bands and forecasts outcomes across diverse perturbations in sub-millisecond timeframes.

## 2. Multi-Permutation Execution Workflow

```python
hybrid_engine = HybridOutcomeEngine()
results = hybrid_engine.evaluate_whatif_alternatives(
    base_state=current_state,
    variations=[
        {"name": "Nominal Baseline", "perturbations": {}},
        {"name": "High Jamming", "perturbations": {"jamming_intensity": 0.8}},
        {"name": "Severe Storm", "perturbations": {"wind_speed_mps": 25.0, "precipitation_mm_hr": 40.0}},
        {"name": "Combined Threat", "perturbations": {"jamming_intensity": 0.7, "wind_speed_mps": 20.0}},
    ]
)
```

## 3. Disagreement Analytics (`analyze_model_disagreement`)

The outcome engine systematically compares Rule predictions against Laya classifications across three tiers:
1. **FULL_CONSENSUS**: Rules and Laya agree on operational state, outcome, and action.
2. **PARTIAL_CONSENSUS**: Minor divergence in risk weighting or nuance, resolved via weighted blending (40% Rule / 60% Laya).
3. **SAFETY_OVERRIDE**: Rule engine invariant triggers (e.g., zero fuel, structural limits breached). Laya's optimistic prediction is forcefully overridden by the Rule Engine.
