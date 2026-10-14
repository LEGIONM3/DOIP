# Current Simulation Pipeline Analysis

**Document Date:** October 2026  
**Module:** `docs/laya_upgrade/CURRENT_SIMULATION_PIPELINE.md`  
**Status:** Audit Complete  

---

## 1. Simulation Architecture & Pipeline Flow

The DOIP simulation pipeline operates along two parallel tracks:

1. **Legacy Deterministic Engine (`SimEngine`)**:
   - Resides in `backend/app/engine.py`.
   - Powers the baseline simulation, Golden Run regression suite (`test_golden_run.py`), and standard operational playback.
   - Guaranteed byte-identical repeatability. Drift is strictly 0.00%.

2. **Phase 8 Hybrid Simulation Suite (`backend/app/simulation/`)**:
   - Introduced modular physics, rule enforcement, feature extraction, and learned arbitration.
   - Flow:
     ```text
     State_{t}
        ↓
     PhysicsEngine.step(dt_sec, target_speed, target_heading, perturbations)
        ↓
     State_{t+1}
        ↓
     RuleEngine.evaluate(State_{t+1})  --> Invariant Checks (6 physical rules)
        ↓
     FeatureExtractor.extract(State_{t+1}) --> 15-d Normalized Vector
        ↓
     LayaSimulationClassifier.predict(features, min_confidence)
        ↓
     ConsensusOutcomeEngine.arbitrate(State_{t+1}, LayaOutput, threshold)
        ↓
     StateTransitionValidator.validate_and_apply(State_{t+1}, LayaAction)
        ↓
     Final Decision & Next State Committed
     ```

---

## 2. Invariant Enforcement & Safety Gating

The simulation pipeline strictly enforces physical realities:
- **Zero Fuel Invariant**: If fuel $\le 0\%$, unit velocity must decay to $0$. A proposed action of `CONTINUE` is rejected by `StateTransitionValidator` and overridden to `ABORT` or `RESUPPLY` with `RULE_ENGINE_OVERRIDE`.
- **Speed Ceiling**: Unit speed cannot exceed `max_speed_mps`.
- **Comms Shadow / Jamming**: If signal $\le -115$ dBm or packet loss $\ge 95\%$, status is forced to `LOST`.
- **Confidence Gating & Abstention**: If Laya composite confidence $< 0.65$, Laya marks `abstained = True`. The `ConsensusOutcomeEngine` falls back to authoritative rules with `SAFETY_OVERRIDE` and audit logs the event.

---

## 3. Existing Simulation Modes

Defined in `backend/app/simulation/simulation_runner.py`:
- `SimulationMode.DETERMINISTIC_SIM`: Bypasses Laya inference; evaluates physics and deterministic rules only. Guarantees zero regression on baseline workflows.
- `SimulationMode.HYBRID_AI_SIM`: Steps physics, computes rules, extracts features, queries Laya non-autoregressive scorer, arbitrates consensus, and logs agreement/disagreement metrics.

---

## 4. Current Gaps in Simulation Pipeline

1. **What-If Isolation**: `backend/app/whatif.py` still operates on the discrete event `SimEngine`, running fixed seeded Monte Carlo runs without tapping into Laya's continuous learned state classifiers.
2. **Forecasting Isolation**: `backend/app/forecasting.py` computes kinematic lookahead projections (fuel depletion, RF shadow) but does not synthesize Laya's learned multi-task risk predictions or hybrid outcome probability distributions.
3. **No Multi-Future Branching during State Generation**: The simulation pipeline only runs linear trajectories rather than branching trees of future scenarios to estimate soft probability densities.
