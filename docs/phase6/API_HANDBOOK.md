# DOIP API Handbook
## Defense Operations Intelligence Platform — Production REST & WebSocket Reference
### Phase 6 API Platform Specifications

---

## 1. API Platform Standards & Conventions

- **Protocol**: HTTP/1.1 and HTTP/2 over TLS 1.3; WebSockets (`ws://` / `wss://`) for bidirectional real-time channels.
- **Base URI**: `http://<host>:<port>/api`
- **Data Serialization**: JSON (`application/json`) with ISO-8601 UTC timestamp formatting.
- **Authentication**: Bearer Token in `Authorization` header (`Authorization: Bearer <token>`).
- **Standard Error Format**:
  ```json
  {
    "detail": "Error description message",
    "error_code": "ERR_CODE_IDENTIFIER",
    "status": 403
  }
  ```

---

## 2. Resilience, Caching & Scalability Endpoints (Phase 6)

### 2.1 Resilience Status
- **Method / Path**: `GET /api/resilience/status`
- **Access**: All Authenticated Operators
- **Response**:
  ```json
  {
    "circuit_breakers": {
      "llm_inference_service": {
        "state": "CLOSED",
        "failure_count": 0,
        "failure_threshold": 3,
        "recovery_timeout": 30.0,
        "last_failure_time": 0.0
      }
    }
  }
  ```

### 2.2 Reset Circuit Breakers
- **Method / Path**: `POST /api/resilience/reset`
- **Access**: System Administrator (`role: sysadmin`)
- **Request Body**:
  ```json
  {
    "name": "llm_inference_service" // Optional. If omitted, resets all.
  }
  ```
- **Response**: `{"reset": ["llm_inference_service"], "success": true}`

### 2.3 Cache Statistics & Inspection
- **Method / Path**: `GET /api/cache/stats`
- **Response**:
  ```json
  {
    "size": 42,
    "max_size": 1000,
    "default_ttl": 300.0,
    "namespaces": {
      "routing": 14,
      "knowledge": 28
    }
  }
  ```

### 2.4 Clear Cache
- **Method / Path**: `POST /api/cache/clear`
- **Request Body**: `{"namespace": "routing"}` (Optional. Clears all if omitted).
- **Response**: `{"cleared": true, "namespace": "routing"}`

### 2.5 Scalability Benchmark Execution
- **Method / Path**: `POST /api/scalability/benchmark`
- **Request Body**: `{"n_events": 10000, "batch_size": 250}`
- **Response**:
  ```json
  {
    "events_processed": 10000,
    "duration_seconds": 0.048,
    "throughput_events_per_sec": 208333.3,
    "scale_multiplier": "100x Nominal Baseline"
  }
  ```

---

## 3. Unified Knowledge Platform Endpoints (Phase 6)

### 3.1 Unified Multi-Modal Query
- **Method / Path**: `POST /api/knowledge/unified/query`
- **Request Body**:
  ```json
  {
    "query": "Fuel supply vulnerability along convoy route Charlie",
    "entity_id": "MSN-CONVOY-01",
    "top_k_rag": 3,
    "horizon_hours": 2.0
  }
  ```
- **Response**:
  ```json
  {
    "query": "Fuel supply vulnerability along convoy route Charlie",
    "graph_context": {
      "root_causes": [{"incident": "INC-AMBUSH-01", "score": 0.92}],
      "dependencies": [{"entity": "DEPOT-NORTH", "type": "SUPPLY_NODE"}]
    },
    "memory_context": [
      {"content": "Prior encounter near defile at tick 140", "relevance": 0.88}
    ],
    "rag_citations": [
      {
        "doctrine_id": "SOP-03-CONVOY-OPS.md",
        "citation": "Section 4.2 Dispersal Tactics",
        "verbatim": "In case of logistical interdiction, disperse..."
      }
    ],
    "risk_assessment": {
      "predicted_risks": ["Fuel exhaustion anticipated at tick 280"]
    }
  }
  ```

---

## 4. Mission Planning & Lifecycle Endpoints

### 4.1 Create Tactical Mission
- **Method / Path**: `POST /api/missions`
- **Request Body**:
  ```json
  {
    "name": "Operation Iron Shield",
    "objective": "Escort supply battalion to FOB Bravo",
    "waypoints": [{"lat": 34.5, "lon": 43.1}, {"lat": 34.8, "lon": 43.6}],
    "assigned_unit_ids": ["UNIT-ARMOR-101", "UNIT-INF-204"]
  }
  ```
- **Response**: `{"id": "MSN-7839", "status": "draft", ...}`

### 4.2 Update Mission Status (Human-in-the-Loop Gate)
- **Method / Path**: `POST /api/missions/{mission_id}/status`
- **Request Body**:
  ```json
  {
    "status": "execution",
    "actor": "commander_nash"
  }
  ```
- **Gate Invariant**: If `actor` is omitted or lacks Commander privileges, returns `HTTP 403 Forbidden`:
  ```json
  {
    "detail": "Transition to execution requires authenticated human approval."
  }
  ```

---

## 5. Tactical Routing & Pathfinding Endpoints

### 5.1 Plan Threat-Averse Tactical Route
- **Method / Path**: `POST /api/routing/plan`
- **Request Body**:
  ```json
  {
    "start": [34.5, 43.1],
    "goal": [35.2, 44.0],
    "threat_weight": 2.5,
    "avoid_zones": ["NO_GO_ZONE_ALPHA"]
  }
  ```
- **Response**:
  ```json
  {
    "waypoints": [[34.5, 43.1], [34.7, 43.3], [35.2, 44.0]],
    "distance_km": 84.2,
    "fuel_cost_est": 320.0,
    "threat_exposure_score": 0.08
  }
  ```

---

## 6. Adversarial Red Team Endpoints

### 6.1 Generate Staged Adversarial Injects
- **Method / Path**: `POST /api/redteam/scenarios/generate`
- **Request Body**:
  ```json
  {
    "mission_id": "MSN-7839",
    "risk_tolerance": "MEDIUM"
  }
  ```
- **Response**: Returns staged injects with `status: "staged"` and `approved_by: null`.

### 6.2 Approve Adversarial Inject (HITL Gate)
- **Method / Path**: `POST /api/redteam/injects/{inject_id}/approve`
- **Request Body**:
  ```json
  {
    "scenario_id": "RT-SCENARIO-12",
    "approved_by": "commander_nash"
  }
  ```
- **Response**: `{"status": "approved", "approved_by": "commander_nash", "approved_at": "2026-10-04T09:15:00Z"}`

---

## 7. Real-Time War Room WebSocket Protocol

### 7.1 Connection
- **Endpoint**: `WS /ws/warroom?token=<token>&channel=INC-DEFAULT`
- **Client → Server Events**:
  - `join`: `{"type": "join", "username": "operator_smith", "role": "OPERATOR"}`
  - `scratchpad_update`: `{"type": "scratchpad_update", "content": "Confirmed visual contact at GRID 4432"}`
  - `task_claim`: `{"type": "task_claim", "task_id": "TASK-102"}`
- **Server → Client Events**:
  - `presence`: `{"type": "presence", "users": ["commander_nash", "operator_smith"]}`
  - `state_sync`: `{"type": "state_sync", "tick": 182, "units": [...]}`
  - `alert_broadcast`: `{"type": "alert", "severity": "HIGH", "message": "Threat corridor breach detected"}`
