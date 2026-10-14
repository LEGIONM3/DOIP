# Investment Optimization Engine Specification (Phase 2D)

**Owner:** OPTIMIZATION_ENGINEER Agent (ECC Protocol)  
**Program:** Defense Operations Intelligence Platform (DOIP)  

---

## 1. Problem Formulation

The Investment Optimizer provides transparent, deterministic, and explainable decision support for capital and operational expenditure across theater assets.

### Decision Variables ($x_i \in \mathbb{Z}_{\ge 0}$)
1. $x_{\text{uav}}$: Additional high-altitude surveillance UAVs ($C_{\text{uav}} = \$120\text{k}$, $+15\%$ coverage, $+12\%$ readiness).
2. $x_{\text{vehicle}}$: Armored escort vehicles ($C_{\text{veh}} = \$80\text{k}$, $+10\%$ readiness, $-8\%$ response time).
3. $x_{\text{comms}}$: Encrypted radio relays / EW countermeasures ($C_{\text{comms}} = \$35\text{k}$, $-25\%$ comms loss risk).
4. $x_{\text{depot\_fuel}}$: Forward fuel bladders ($C_{\text{fuel}} = \$25\text{k}$, $+30\%$ fuel resilience).
5. $x_{\text{medic}}$: Mobile tactical triage stations ($C_{\text{medic}} = \$45\text{k}$, $-20\%$ casualty risk).

### Objective Function
$$\max \quad Z = w_{\text{readiness}} \cdot \Delta R + w_{\text{coverage}} \cdot \Delta C + w_{\text{response}} \cdot \Delta T_{\text{resp}} + w_{\text{fuel}} \cdot \Delta F - w_{\text{risk}} \cdot \Delta \text{Risk}$$

### Constraints
$$\sum_{i} C_i \cdot x_i \le B_{\text{total}} \quad (\text{Budget Constraint})$$
$$x_i \le \text{MaxCapacity}_i \quad (\text{Logistics Ceiling})$$

---

## 2. Explainability & Tradeoff Analysis
- Generates Pareto-optimal frontier between Budget Expenditure and Operational Readiness.
- Produces plain-language rationale: e.g. *"Investing \$120k into 1 UAV and 1 Radio Relay yields +15% radar coverage and reduces comms loss risk by 25%, while remaining within the \$150k target cap."*
- Supports What-If baseline comparison against frozen simulation KPI history.

---

## 3. REST API Contract
- `POST /api/optimizer/solve`: Execute optimization with custom budget and objective weightings.
- `GET /api/optimizer/history`: List past optimization run comparisons and trade-offs.
