# DOIP Supreme Verification: Minor Failures Catalog

**Audit Execution Mode:** Hostile Independent Verification  
**Auditor:** ECC_VERIFICATION_SWARM / CHIEF_VERIFICATION_OFFICER  
**Date:** 2026-10-04  
**Directive Mandate:** DO NOT FIX ISSUES IMMEDIATELY. Document all discovered minor failures with root causes and reproduction evidence.

---

## MIN-01: Calibrated Softmax Temperature Nullifies Default Confidence Threshold

### Severity: MINOR (Gating Sensitivity Desynchronization)
- **Subsystem:** Laya Neural Engine / Calibration & Abstention
- **Affected File:** [`backend/app/laya_engine.py`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/backend/app/laya_engine.py) (Lines 155–185)
- **Root Cause:**
  Temperature scaling calibration sets optimal temperature $T = 0.160$. Dividing logits by $T = 0.160$ scales logit magnitude by $6.25\times$. Softmax output distributions become exceptionally peaky (e.g., maximum probability routinely exceeds $0.99+$ even on noisy or ambiguous input vectors).
- **Observed Manifestation:**
  The default confidence threshold $\tau = 0.65$ almost never triggers abstention on calibrated logits because confidence is nearly always $>0.95$. Abstention only triggers when threshold is manually set to $>0.999$, making the default threshold ineffective at gating ambiguous inputs.
- **Reproduction Evidence:**
  Demonstrated in `scratch/audit_laya_reality.py`: passing an all-zero vector yielded `confidence = 0.9959`, bypassing the default $\tau=0.65$ gate.

---

## MIN-02: Endpoint Route Naming Inconsistency (`/runs` vs `/api/runs`)

### Severity: MINOR (API Architectural Hygiene)
- **Subsystem:** Backend API Routing
- **Affected File:** [`backend/app/main.py`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/backend/app/main.py)
- **Root Cause:**
  Early Phase 0/1 endpoints were mounted directly at the root path (`/runs`, `/runs/{id}/report`, `/whatif`), whereas later Phase 2–8 endpoints were mounted under the `/api/` prefix (`/api/missions`, `/api/forecast`, `/api/laya/...`).
- **Observed Manifestation:**
  Inconsistent URL prefixes across client services and reverse proxies. If a reverse proxy only routes `/api/`, root-mounted endpoints are unreachable.
- **Reproduction Evidence:**
  Inspected route table in `backend/app/main.py`: `POST /runs` vs `POST /api/missions`.

---

## MIN-03: Redundant Duplicate Service Client Files in Frontend

### Severity: MINOR (Code Maintenance / Technical Debt)
- **Subsystem:** Frontend Service Architecture
- **Affected Files:**
  - [`src/services/copilot.ts`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/src/services/copilot.ts)
  - [`src/services/replay.ts`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/src/services/replay.ts)
  - [`src/services/vision.ts`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/src/services/vision.ts)
- **Root Cause:**
  Earlier phases added API helper methods directly into [`src/lib/api.ts`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/src/lib/api.ts). Later phases created dedicated typed modules in `src/services/`. However, existing routes continue to import from `src/lib/api.ts`, leaving corresponding `src/services/` modules dead and unreferenced.
- **Observed Manifestation:**
  Dead code in `src/services/` that requires dual maintenance when backend APIs evolve.
- **Reproduction Evidence:**
  Detected in `scratch/audit_service_connections.py`: `copilot.ts`, `replay.ts`, `vision.ts` are never imported by any UI route in `src/routes/`.
