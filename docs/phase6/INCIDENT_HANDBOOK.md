# DOIP Incident Response Handbook
## Defense Operations Intelligence Platform — Runbooks & Failure Remediation
### Phase 6 Production Hardening & Operational Continuity

---

## 1. Incident Severity Matrix & Response SLAs

| Severity | Definition | Target MTTR | Escalation Path |
|---|---|---|---|
| **SEV-1 (CRITICAL)** | Total loss of War Room collaboration, simulation lockup, authoritative state divergence, or failure of Human-in-the-Loop gate. | < 15 minutes | Lead Systems Architect, Operations Commander, SecOps Lead |
| **SEV-2 (HIGH)** | Core service degradation: AI reasoning circuit breaker tripped, tactical routing failure, or telemetry batch ingestion lag > 10,000 events. | < 30 minutes | Infrastructure Engineer, Platform Lead |
| **SEV-3 (MEDIUM)** | Non-blocking degradation: Cache eviction thrashing, secondary sensor stream drop, or single federation child node disconnect. | < 2 hours | DevOps On-Call, Support Lead |
| **SEV-4 (LOW)** | Minor UI anomalies, documentation drift, or non-critical background metric latency. | Next Sprint | Platform Contributor |

---

## 2. Circuit Breaker Trips & Recovery Runbook

### 2.1 Symptoms
- Client receives `503 Service Unavailable` or `CircuitBreakerOpenError`.
- System operates in degraded fallback mode (e.g., using rule-based reasoning rather than LLM inference).
- Querying `GET /api/resilience/status` returns `"state": "OPEN"` for one or more services.

```json
{
  "circuit_breakers": {
    "ollama_inference_service": {
      "state": "OPEN",
      "failure_count": 5,
      "failure_threshold": 3,
      "recovery_timeout": 30.0,
      "last_failure_time": 1775294100.12
    }
  }
}
```

### 2.2 Diagnosis & Root Cause Analysis
1. Check the target dependency's container/daemon status:
   ```bash
   curl -I http://localhost:11434/api/tags  # Check local Ollama
   docker ps | grep vllm                   # Check GPU inference worker
   ```
2. Verify GPU memory utilization:
   ```bash
   nvidia-smi  # Look for OOM or hung worker processes
   ```

### 2.3 Remediation & Reset Procedure
1. Restart the offending upstream dependency if crashed.
2. Allow the circuit breaker to enter `HALF_OPEN` automatically (default: 30s recovery window) to execute a canary probe.
3. If manual override is urgently required by command:
   ```bash
   curl -X POST http://localhost:8000/api/resilience/reset \
     -H "Content-Type: application/json" \
     -d '{"name": "ollama_inference_service"}'
   ```
4. Verify all circuit breakers return to `"state": "CLOSED"`.

---

## 3. Simulation Drift & Hash Divergence Remediation

### 3.1 Symptoms
- Federated nodes report diverging event checksums for the same scenario tick.
- CI/CD validation fails at `tests/test_golden_run.py` with hash mismatch against `sc2_seed8841.hash`.

### 3.2 Immediate Containment
1. Freeze authoritative tick progression across connected nodes (`POST /api/sim/pause`).
2. Isolate nodes reporting divergent checksums from the federation swarm to prevent corrupted state propagation.

### 3.3 Root Cause Analysis & Recovery
1. Compare event ledger log entries for the diverging tick:
   ```bash
   python -c "from app import db; print(db.get_scenario_events('SC-02', tick_range=(100, 110)))"
   ```
2. Identify divergence vector:
   - **Floating-point rounding differences**: Confirm all nodes run Python 3.12 64-bit on IEEE-754 compliant hardware.
   - **Unseeded randomness**: Inspect recent commits for unseeded `random.random()`, `time.time()`, or dict order non-determinism.
3. Resynchronize divergent nodes by streaming the authoritative snapshot from the primary command node:
   ```bash
   curl -X POST http://localhost:8000/api/federation/sync \
     -H "Content-Type: application/json" \
     -d '{"peer_id": "NODE_PRIMARY_01", "force_snapshot": true}'
   ```

---

## 4. Database Deadlocks & Lock Contention Remediation

### 4.1 SQLite `database is locked` (Edge Profile)
- **Cause**: Unclosed read transactions or multiple simultaneous write threads in default DELETE journal mode.
- **Verification**: Check if WAL mode is enabled:
  ```bash
  sqlite3 doip.db "PRAGMA journal_mode;"
  ```
- **Remediation**:
  1. Ensure WAL mode is active:
     ```bash
     sqlite3 doip.db "PRAGMA journal_mode=WAL;"
     sqlite3 doip.db "PRAGMA synchronous=NORMAL;"
     sqlite3 doip.db "PRAGMA busy_timeout=5000;"
     ```
  2. Kill hung read locks:
     ```bash
     fuser -k doip.db  # Linux
     ```

### 4.2 PostgreSQL Connection Exhaustion / Lock Wait (Enterprise Profile)
- **Verification**:
  ```sql
  SELECT pid, age(clock_timestamp(), query_start), usename, query, state
  FROM pg_stat_activity
  WHERE state != 'idle' AND age(clock_timestamp(), query_start) > interval '10 seconds';
  ```
- **Remediation**: Terminate blocking session:
  ```sql
  SELECT pg_terminate_backend(blocking_pid);
  ```

---

## 5. Degraded Fallback Operation & PACE Plan

When primary subsystems suffer sustained degradation, DOIP automatically activates the **Primary, Alternate, Contingency, Emergency (PACE)** response matrix:

```text
┌───────────────┬────────────────────────────┬────────────────────────────┬────────────────────────────┐
│ CAPABILITY    │ PRIMARY                    │ ALTERNATE                  │ CONTINGENCY / EMERGENCY    │
├───────────────┼────────────────────────────┼────────────────────────────┼────────────────────────────┤
│ AI Reasoning  │ Heavy LLM (Ollama/vLLM)    │ Fast Local SLM (Mistral-7B)│ Grounded Rule Provider     │
│ Storage       │ PostGIS 16 + pgvector      │ Local PostGIS Replica      │ Embedded SQLite (WAL)      │
│ Federation    │ WAN / High-Bandwidth Mesh  │ Tactical Radio (VHF/HF)    │ Disconnected Local Node    │
│ Route Plan    │ Multi-factor A* with Threat│ Simplified Euclidean A*    │ Direct Waypoint Corridor   │
└───────────────┴────────────────────────────┴────────────────────────────┴────────────────────────────┘
```
