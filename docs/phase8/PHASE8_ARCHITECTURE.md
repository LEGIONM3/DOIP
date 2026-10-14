# DOIP Phase 8: Hybrid Physics Simulation + Laya Learned Decision Engine Architecture

## 1. Executive Overview

DOIP Phase 8 transforms the defense operations intelligence platform by integrating a high-fidelity **Deterministic Synthetic Physics & Rule Engine** with the **Laya Learned Decision Engine** (convaiinnovations/laya).

```
   Authoritative State S_t
              ↓
  Physics + Rule Dynamics Engine
              ↓
  Deterministic Feature Extraction
              ↓
    Laya Decision Scorer (System 1)
              ↓
  Rule-Validated State Transition Gate
              ↓
      Next State S_{t+1}
```

### Critical Invariant
The physics and rule engine remains authoritative at all times. Laya operates as a fast, learned non-autoregressive decision classification and scoring layer. The physical invariants (conservation of energy, kinematic boundaries, communication degradation) are rigorously enforced by invariant gates: an illegal neural decision is never permitted to mutate operational reality.

---

## 2. Core Subsystems

### A. Synthetic Physics Engine (`backend/app/simulation/physics_engine.py`)
- **Kinematics**: 6-DOF planar/altitude movement, turn-rate limits, velocity updates, acceleration limits clamped by terrain friction.
- **Energy Dynamics**: Speed- and mass-dependent fuel and battery drain models accounting for aerodynamic drag.
- **Environmental Aerodynamics**: Vector wind resistance (headwind/tailwind/crosswind), precipitation attenuation, temperature effects.
- **RF Communications Propagation**: Friis log-distance path loss, terrain occlusion penalties, electronic warfare jamming attenuation.
- **Logistics Dynamics**: Mechanical wear accumulation, ammunition consumption, depot proximity.

### B. Authoritative Rule Engine (`backend/app/simulation/rule_engine.py`)
- Evaluates hard boundaries and logical preconditions.
- Evaluates failure states (`FAILED`, `CRITICAL`, `DEGRADED`, `NORMAL`).
- Determines baseline action recommendations (`CONTINUE`, `REROUTE`, `RESUPPLY`, `PAUSE`, `ABORT`).
- Validates proposed actions against physical invariants.

### C. Deterministic Feature Extractor (`backend/app/simulation/feature_extractor.py`)
- Maps 5 multi-physics state facets into a normalized continuous 15-dimensional vector:
  `[lat_norm, lon_norm, speed_norm, heading_norm, fuel_norm, battery_norm, wind_norm, precip_norm, visibility_norm, friction_norm, signal_norm, jamming_norm, wear_norm, depot_dist_norm, ammo_norm]`.
- Constructs structured prompt text for Laya question answering.

### D. Laya Decision Engine (`backend/app/laya_engine.py`)
- ModernBERT encoder multi-task scoring head mapping operational states to decision outcomes in a single non-autoregressive forward pass (~0.23 ms).
- Evaluates 4 multi-class tasks and 1 calibrated continuous risk head.
- Supports confidence gating and abstention (`GATE_ABSTAINED` vs `GATE_PASSED`) using `min_confidence`.

### E. Rule-Validated State Transition Engine (`backend/app/simulation/state_transition.py`)
- Acts as safety arbitrator between neural predictions and physical laws.
- Overrides invalid predictions with rule-derived fallbacks.

### F. Consensus Outcome Engine (`backend/app/simulation/outcome_engine.py`)
- Arbitrates decisions across Physics, Rules, and Laya.
- Calculates model disagreement statistics and risk divergence.
