# DOIP Model Calibration & Evaluation Report

## 1. Benchmark Metrics on Held-Out Test Set (300 Samples)

The evaluation was executed on held-out scenarios using `training/evaluate.py`:

| Evaluation Dimension | Metric | Result | Benchmark Baseline |
|---|---|---|---|
| **Operational State** | Accuracy | **84.0%** | Multi-class (4 classes) |
| **Action Recommendation** | Accuracy | **74.0%** | Tactical action (5 classes) |
| **Mission Outcome** | Accuracy | **100.0%** | Trajectory forecast |
| **Risk Estimation** | Mean Absolute Error | **0.0681** | $[0.0, 1.0]$ Continuous risk |
| **Probabilistic Calibration**| Brier Score | **0.2585** | Multi-class scoring |
| **Uncalibrated ECE** | Expected Calibration Error | **0.1280** | $T = 1.0$ |
| **Calibrated ECE** | Expected Calibration Error | **0.0875** | $T^* = 0.40$ (via `laya.ece_score`) |
| **Mean Inference Latency** | Execution Time (CPU) | **0.234 ms** | Sub-millisecond forward pass |
| **p95 Inference Latency** | Execution Time (CPU) | **0.389 ms** | Real-time simulation capable |

## 2. Temperature Calibration Formulation

Given logit outputs $z$, the calibrated probabilities are parameterized by temperature $T$:
$$p_i = \frac{\exp(z_i / T)}{\sum_j \exp(z_j / T)}$$

Temperature scaling preserves the rank order of class predictions while scaling confidence probabilities to match empirical accuracy. Grid search using `laya.ece_score` identified $T^* = 0.40$, yielding an ECE reduction of **0.0405**.

## 3. Abstention Behavior Analysis

Under varying confidence gates:
- At $\tau = 0.65$: Abstention rate is **0.0%** on nominal test runs, triggering only on ambiguous edge cases.
- At $\tau = 0.80$: Abstention rate is **3.3%**, safely escalating ambiguous states to rule fallbacks.

## 4. Latency Advantage vs Generative LLM

| Approach | Architecture | Mean Latency | Deterministic Bounds |
|---|---|---|---|
| **Generative LLM (Phase 3)** | Autoregressive Decoder | 450 - 1800 ms | Token sampling variability |
| **Laya System 1 (Phase 8)** | Bidirectional Encoder + Neural Scorer | **0.234 ms** | Strictly deterministic forward pass |

Laya provides an **order of magnitude ~2000x speedup**, making it capable of running inside high-frequency simulation loops (60 Hz+).
