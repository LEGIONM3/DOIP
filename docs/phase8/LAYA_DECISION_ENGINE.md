# DOIP Laya Learned Decision Engine Architecture

## 1. Overview & Upstream Principles

Laya (`convaiinnovations/laya`) is a specialized non-autoregressive decision foundation model designed for fast, calibrated, discrete and ordinal operational decisions. Unlike traditional generative large language models that generate tokens sequentially through autoregressive decoding loops (incurring hundreds of milliseconds of latency and unpredictable hallucinatory drift), Laya executes in a **single forward pass** (~0.23 ms on CPU).

## 2. Decision Task Taxonomy for DOIP

| Task Name | Type | Target Classes / Range | Description |
|---|---|---|---|
| **Operational State** | Categorical Choice | `NORMAL`, `DEGRADED`, `CRITICAL`, `FAILED` | Unit operational health assessment |
| **Mission Outcome** | Categorical Choice | `SUCCESS`, `DELAYED`, `ABORTED`, `FAILED` | Trajectory mission forecast |
| **Logistics State** | Categorical Choice | `HEALTHY`, `LOW_RESERVE`, `RESUPPLY_REQUIRED`, `CRITICAL` | Consumable supply readiness |
| **Comms State** | Categorical Choice | `CONNECTED`, `DEGRADED`, `INTERMITTENT`, `LOST` | RF link and telemetry status |
| **Environmental Impact**| Categorical Choice | `LOW`, `MODERATE`, `HIGH`, `SEVERE` | Weather and terrain resistance |
| **Action Recommendation**| Categorical Choice | `CONTINUE`, `REROUTE`, `RESUPPLY`, `PAUSE`, `ABORT` | Tactical response action |
| **Risk Score** | Calibrated Score | $[0.0, 1.0]$ Continuous | Overall composite threat probability |

## 3. Question Schema Specification

```python
LAYA_DECISION_QUESTIONS = {
    "operational_state": {
        "type": "choice",
        "instructions": "Classify the operational health status of the asset based on telemetry.",
        "criteria": {
            "NORMAL": "Asset operating within nominal telemetry tolerances",
            "DEGRADED": "Minor subsystems impacted but asset remains operable",
            "CRITICAL": "Severe energy, comms, or environmental threat detected",
            "FAILED": "Asset fully incapacitated, out of fuel, or destroyed",
        },
    },
    ...
}
```

## 4. Confidence Gating & Abstention

Laya computes normalized softmax probabilities for each decision category $y_i$:
$$P(y_i) = \frac{\exp(z_i / T)}{\sum_j \exp(z_j / T)}$$
The composite confidence metric $C$ is computed across decisions. When $C < C_{\text{threshold}}$, the engine marks `abstained = True` with status `GATE_ABSTAINED`. In this condition, the state transition validator automatically executes an authoritative fallback to the Rule Engine.
