# Red Team Adversarial Planner Specification (Phase 2E)

**Owner:** REDTEAM_ENGINEER Agent (ECC Protocol)  
**Program:** Defense Operations Intelligence Platform (DOIP)  

---

## 1. Role & Operational Invariants

The Red Team Adversarial Planner stress-tests planned operational missions and tactical deployments by identifying vulnerabilities and synthesizing realistic adversarial injects.

### Safety Invariants
1. **Zero Direct Mutation:** The Red Team CANNOT mutate running simulation state or live databases.
2. **Proposal Only:** All generated adversarial scenarios are staged as `ProposedInject` items.
3. **DSL Whitelist Enforced:** Injects must strictly map to valid DOIP DSL actions:
   - `INJECT_WEATHER`: Alters atmospheric intensity and wind.
   - `TRIGGER_INCIDENT`: Spawns simulated hostile contact or obstacle.
   - `JAM_COMMS`: Degrades telemetry or causes stale unit states.
   - `IMPAIR_UNIT`: Simulates mechanical or fuel loss.
4. **Mandatory Human Approval:** Injects remain inert until a human operator or exercise coordinator approves and explicitly schedules them.

---

## 2. Vulnerability Analysis & Inject Generation

The planner analyzes:
1. **Planned Route Geometry:** Choke-points, narrow mountain passes, proximity to borders.
2. **Unit Posture:** Units with $<50\%$ fuel, solitary units without escort, units with degraded comms.
3. **Environmental Windows:** High crosswind or dense cloud cover creating UAV blind spots.

---

## 3. REST API Contract
- `POST /api/redteam/generate`: Analyzes mission and outputs structured stress scenarios with risk rating (`CRITICAL`, `HIGH`, `MEDIUM`).
- `POST /api/redteam/validate`: Passes proposed injects through `dsl_parser.py` validation gate.
- `POST /api/redteam/injects/{id}/approve`: Exercise coordinator approval action.
- `GET /api/redteam/scenarios`: List generated adversarial stress scenarios.
