# LAYA Upstream Research Report

**Document Date:** October 2026  
**Investigating Agent:** `LAYA_RESEARCH_AGENT`  
**Target Repository:** [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya)  
**License:** Apache-2.0  
**Module:** `docs/laya_upgrade/LAYA_RESEARCH_REPORT.md`  

---

## 1. Executive Summary

Laya is an open-source, non-autoregressive "System 1" decision engine developed by NandhaKishorM (Convai Innovations). Unlike generative large language models (LLMs) that produce text autoregressively (token by token) and suffer from hallucinations, parse failures, high latency, and uncalibrated confidence, Laya employs a **bidirectional transformer encoder architecture** that processes the operational context and typed decision queries simultaneously, returning typed decisions and well-calibrated probability distributions in a **single forward pass**.

---

## 2. Training Architecture & Design Principles

### Non-Autoregressive System 1 Philosophy
- **Bi-Directional Attention**: Uses encoder models (such as `ModernBERT-large` for English and `mmBERT-base` for 100+ languages) rather than causal decoders.
- **Typed Classification Heads**: Instead of generating text tokens, Laya maps internal representations directly to typed heads:
  - Multi-class categorical heads (`choice`)
  - Continuous/rubric scoring heads (`score`)
  - Binary heads (`noul` / `yes_no`)
- **Single-Pass Inference**: Achieves 33 ms latency for single items and 7.2 ms per item under batching on standard hardware, offering a 10x-50x speedup over autoregressive LLMs.

---

## 3. RLCD Pipeline (Reinforcement Learning for Calibrated Decisions)

Laya utilizes **RLCD** to ensure that predicted output probabilities represent genuine Bayesian posterior beliefs rather than overconfident pseudo-probabilities.

- **Strictly Proper Scoring Rules**: The optimization objective penalizes overconfidence and miscalibration by training against proper scoring rules—predominantly the **Brier Score**:
  $$\text{Brier} = \frac{1}{N} \sum_{i=1}^N \sum_{k=1}^K (p_{ik} - y_{ik})^2$$
  and **Negative Log-Likelihood (Logarithmic Score)**:
  $$\text{NLL} = - \frac{1}{N} \sum_{i=1}^N \sum_{k=1}^K y_{ik} \log(p_{ik})$$
- **Soft Target Alignment**: When trained on empirical multi-future distributions (rather than binary 1-hot targets), the RLCD objective minimizes Kullback-Leibler (KL) divergence between predicted class probabilities and the empirical Monte Carlo distribution:
  $$D_{\text{KL}}(P_{\text{empirical}} \parallel P_{\text{model}}) = \sum_k P_{\text{empirical}}(k) \log\left(\frac{P_{\text{empirical}}(k)}{P_{\text{model}}(k)}\right)$$

---

## 4. Calibration Pipeline & Temperature Scaling

Laya treats calibration as a first-class requirement:

- **Per-Task / Per-Option Temperature Scaling**:
  For logits $\mathbf{z}$, the calibrated probabilities are computed as:
  $$p_k = \frac{\exp(z_k / T)}{\sum_{j} \exp(z_j / T)}$$
  where temperature $T > 0$ is learned on the validation partition via post-hoc optimization (minimizing NLL or Brier score).
- **Calibration Target**: Expected Calibration Error (ECE) must satisfy:
  $$\text{ECE} = \sum_{m=1}^M \frac{|B_m|}{N} |\text{acc}(B_m) - \text{conf}(B_m)| < 0.05$$
  across $M$ confidence bins (typically 10 or 15 equal-width bins).
- **Triggered Recalibration**: Upstream Laya monitoring flags any model drift or domain shift where ECE exceeds $0.05$, triggering automated recalibration or fine-tuning cycles.

---

## 5. Checkpoint Format & Packaging

Upstream Laya uses a standardized model package format containing:
1. **Model Weights**: PyTorch state dictionary (`model.pt`), traced TorchScript (`model_traced.pt`), or ONNX runtime export (`model.onnx`).
2. **`manifest.json`**: Describes model architecture, input dimension/encoder type, supported tasks, and output head specifications.
3. **`metadata.json`**: Records dataset version, sample count, training duration, git commit hash, and loss values.
4. **`calibration.json`**: Contains optimal temperatures ($T$) per head, pre- and post-calibration ECE, and Brier scores.

---

## 6. Supported Decision Tasks

Laya natively defines three canonical decision types:

| Task Type | Description | DOIP Operational Mapping |
|---|---|---|
| **`choice`** | Selects one option from a defined discrete list with a calibrated probability distribution over all options. | 1. `operational_state` (`NORMAL`, `DEGRADED`, `CRITICAL`, `FAILED`)<br>2. `mission_outcome` (`SUCCESS`, `DELAYED`, `ABORTED`, `FAILED`)<br>3. `logistics_state` (`HEALTHY`, `LOW_RESERVE`, `RESUPPLY_REQUIRED`, `CRITICAL`)<br>4. `comms_state` (`CONNECTED`, `DEGRADED`, `INTERMITTENT`, `LOST`)<br>5. `recommended_action` (`CONTINUE`, `REROUTE`, `RESUPPLY`, `PAUSE`, `ABORT`) |
| **`score`** | Predicts a normalized scalar value $\in [0.0, 1.0]$ or ordered rubric level. | 6. `risk_score` (Continuous operational hazard score $[0.0, 1.0]$) |
| **`yes_no` / `noul`** | Predicts binary Bernoulli probability for a predicate. | Invariant violations, Point-of-No-Return (PNR) breach flags. |

---

## 7. Uncertainty Quantification & Selective Classification (Abstention)

Upstream Laya features a built-in selective prediction protocol:

- **Confidence Metric**: Evaluates maximum softmax probability $\max_k p_k$ or prediction entropy $H(P) = - \sum_k p_k \log p_k$.
- **`min_confidence` Gating**:
  When a caller specifies `min_confidence` (e.g., $0.65$ or $0.80$), Laya checks if $\max_k p_k < \text{min\_confidence}$.
  If triggered:
  - `abstained = True`
  - Prediction is flagged as `UNCERTAIN`
  - In DOIP, this triggers an automatic safety fallback: the authoritative Rule Engine takes control, logging `SAFETY_OVERRIDE`.
- **Selective Metrics**: Benchmarked using AURC (Area Under Risk-Coverage curve), selective accuracy, and abstention rate.

---

## 8. Translation to DOIP Phase 8.5 Implementation

To fulfill the ECC directives for DOIP Phase 8.5 without external network dependencies:
1. **Model Architecture**: Retain the high-speed multi-task neural architecture (`LayaNeuralScorer`) with multi-head outputs matching Laya's exact typed decision schema.
2. **Massive Dataset (>100,000 States)**: Synthesize 100,000+ deterministic world states covering all 6 families and extreme corner cases.
3. **Multi-Future Branching (Soft Labels)**: Run 100-branch future rollouts to generate soft distribution targets, training with cross-entropy / KL-divergence.
4. **Rigorous Calibration**: Implement temperature scaling targeting $\text{ECE} < 0.05$.
5. **Abstention & Disagreement**: Fully implement `min_confidence` gating and active learning mining into `data/hard_examples/`.
6. **Model Registry & Dual Checkpoints**: Train and register `laya_doip_v1` and retrained `laya_doip_v2`.
