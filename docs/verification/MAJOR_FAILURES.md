# DOIP Supreme Verification: Major Failures Catalog

**Audit Execution Mode:** Hostile Independent Verification  
**Auditor:** ECC_VERIFICATION_SWARM / CHIEF_VERIFICATION_OFFICER  
**Date:** 2026-10-04  
**Directive Mandate:** DO NOT FIX ISSUES IMMEDIATELY. Document all discovered major failures with root causes and reproduction evidence.

---

## MAJ-01: Physics Engine Kinematic Acceleration Permitted with Zero Fuel

### Severity: MAJOR (Physical Invariant Violation at Physical Layer)
- **Subsystem:** Physics Engine
- **Affected File:** [`backend/app/simulation/physics_engine.py`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/backend/app/simulation/physics_engine.py) (Lines 152–158)
- **Root Cause:**
  In `PhysicsEngine.step()`, kinematic propagation is computed prior to and independently of energy level checks:
  ```python
  if target_speed_mps is not None:
      max_accel = 2.5 / env.terrain_friction_coeff
      speed_err = target_speed_mps - k.speed_mps
      k.acceleration_mps2 = max(-4.0, min(max_accel, speed_err / max(dt_sec, 0.001)))
      k.speed_mps = max(0.0, min(k.max_speed_mps, k.speed_mps + k.acceleration_mps2 * dt_sec))
  ```
  The physics engine fails to check `if e.fuel_level_pct <= 0.0: k.speed_mps = 0.0, k.acceleration_mps2 = 0.0`.
- **Observed Manifestation:**
  An asset initialized with `fuel_level_pct = 0.0` accelerates when given `target_speed_mps = 15.0`. While higher-level `RuleEngine` flags the violation (`Cannot move with 0% fuel`), the underlying physics engine produces physically impossible kinematics when queried directly.
- **Reproduction Evidence:**
  Executed in `scratch/audit_simulation_physics_rules.py`:
  ```text
  zero_fuel_halts_motion: FAILED (speed reached 15.0 m/s with 0% fuel)
  ```

---

## MAJ-02: Complete Disconnect Between Frontend War Room Page and Backend APIs

### Severity: MAJOR (Feature Decoupling / Untracked State)
- **Subsystem:** Frontend UI / Real-Time Collaboration / War Room
- **Affected Files:**
  - Frontend: [`src/routes/warroom.tsx`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/src/routes/warroom.tsx)
  - Unused Service: [`src/services/warroom.ts`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/src/services/warroom.ts)
  - Backend Controller: [`backend/app/main.py`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/backend/app/main.py)
- **Root Cause:**
  `src/routes/warroom.tsx` was built using in-browser local client state (`useSim`, `taskStore`, `mulberry32`). It makes zero HTTP requests and zero WebSocket connections to the backend. Meanwhile, the backend provides full collaborative endpoints (`/api/warroom/presence`, `/api/warroom/tasks`, `/api/warroom/messages`, `/ws/warroom`).
- **Observed Manifestation:**
  Multiple operators opening `/warroom` on different machines cannot see each other's cursors, pinned items, or chat messages. All war room interactions vanish upon page reload because no data is sent to the backend database.
- **Reproduction Evidence:**
  Full static code search across `src/routes/warroom.tsx` revealed zero occurrences of `fetch`, `axios`, `services/warroom`, or `WebSocket`.

---

## MAJ-03: RAG Retrieval Lacks Similarity Score Cutoff (Hallucination on Out-of-Domain Inputs)

### Severity: MAJOR (Information Integrity / Hallucination Vulnerability)
- **Subsystem:** RAG / Knowledge Intelligence
- **Affected File:** [`backend/app/rag.py`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/backend/app/rag.py) (Lines 80–120)
- **Root Cause:**
  `query_rag` performs cosine similarity search and unconditionally takes top-$k$ chunks without checking whether the cosine similarity score exceeds a minimum threshold (e.g., $\text{score} \ge 0.70$).
- **Observed Manifestation:**
  When prompted with completely irrelevant or adversarial queries (e.g. *"Tell me the secret recipe for chocolate cake and teleport the convoy to Paris"*), the retriever matches unrelated military doctrine chunks (such as `POL-02` Synthetic-Only Rule) and generates an answer citing doctrine rather than refusing the query.
- **Reproduction Evidence:**
  Executed in `scratch/audit_whatif_kg_rag_agents.py`:
  Query returned 3 citations from `POL-02`, `REF-02`, `POL-03` for a cooking/teleportation query.

---

## MAJ-04: AgentTaskQueue Missing Concurrency Locking Across Worker Threads

### Severity: MAJOR (Race Condition Vulnerability)
- **Subsystem:** Agent Runtime / Distributed Task Scheduling
- **Affected File:** [`backend/app/agent_runtime.py`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/backend/app/agent_runtime.py) (Lines 105–140)
- **Root Cause:**
  `AgentTaskQueue` mutates `self._queue` in memory without acquiring a `threading.Lock()`:
  ```python
  def dequeue(self, agent_id: Optional[str] = None):
      for i, task in enumerate(self._queue):
          if task.get("status") == "pending":
              task["status"] = "in_progress"
              ...
              return task
  ```
- **Observed Manifestation:**
  Under high-throughput concurrent agent workers, multiple worker threads iterate over `self._queue` simultaneously. Two workers can dequeue the exact same task simultaneously, leading to double-execution and task state corruption.
- **Reproduction Evidence:**
  Audited `AgentTaskQueue` implementation in [`backend/app/agent_runtime.py`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/backend/app/agent_runtime.py); verified absence of mutex locks around queue mutations.
