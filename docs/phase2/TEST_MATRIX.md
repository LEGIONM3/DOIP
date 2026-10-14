# Phase 2 Verification & Test Matrix

**Owner:** TEST_ENGINEER Agent (ECC Protocol)  
**Program:** Defense Operations Intelligence Platform (DOIP)  

---

## 1. Test Suite Layout

| Test Suite | Subsystem | Invariants & Test Coverage |
|---|---|---|
| `test_phase2_routing.py` | Route Engine | A* grid pathfinding, threat avoidance, fuel/time/safety strategies, PostGIS intersection |
| `test_phase2_missions.py` | Mission Planner | Lifecycle transitions (`Draft -> Review -> Approved -> ...`), resource estimation, approval gate |
| `test_phase2_warroom.py` | War Room Hub | Multi-operator presence, cursor broadcast, task creation & assignment |
| `test_phase2_optimizer.py` | Investment Optimizer | Optimization constraints, budget bounds, Pareto tradeoff calculation, What-If scoring |
| `test_phase2_redteam.py` | Red Team Engine | Adversarial scenario generation, DSL whitelist compliance, human approval requirement |
| `test_golden_run.py` | Sim Engine | Invariance test: `tests/golden/sc2_seed8841.hash` must remain 100% byte-identical |
| `src/services/*.test.ts` | Frontend Clients | Typed API clients, WebSocket connection, error handling, offline resilience |

---

## 2. Invariant Gate Verification
All Phase 1 tests (44 Pytest + 4 Vitest) + all Phase 2 tests must pass before the Integration Lead can declare Phase 2 complete.
