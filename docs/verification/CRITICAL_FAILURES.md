# DOIP Supreme Verification: Critical Failures Catalog

**Audit Execution Mode:** Hostile Independent Verification  
**Auditor:** ECC_VERIFICATION_SWARM / CHIEF_VERIFICATION_OFFICER  
**Date:** 2026-10-04  
**Directive Mandate:** DO NOT FIX ISSUES IMMEDIATELY. Document all discovered critical failures with root causes and reproduction evidence.

---

## CRIT-01: Docker Backend Image Omission of Trained Laya Checkpoints

### Severity: CRITICAL (Blocks Production Deployment & Intelligence)
- **Subsystem:** Deployment / Model Management / Laya Engine
- **Affected File:** [`Dockerfile.backend`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/Dockerfile.backend) (Lines 18–24)
- **Root Cause:**
  `Dockerfile.backend` explicitly copies application source folders:
  ```dockerfile
  COPY backend/ /app/backend/
  COPY corpus/ /app/corpus/
  COPY scenarios/ /app/scenarios/
  COPY tests/ /app/tests/
  ```
  However, it completely omits:
  ```dockerfile
  COPY checkpoints/ /app/checkpoints/
  COPY data/ /app/data/
  ```
- **Observed Manifestation:**
  In any containerized build (`docker compose up --build`), the container filesystem lacks `/app/checkpoints/laya_doip_v1/model.pt` and `/app/checkpoints/laya_doip_v2/model.pt`. When `LayaDecisionEngine` initializes in production, `os.path.exists(checkpoint_dir)` fails, causing the engine to silently fall back to untrained random weights. All production inference decisions become meaningless noise despite local test suites passing.
- **Verification Evidence:**
  Inspected [`Dockerfile.backend`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/Dockerfile.backend); verified `checkpoints/` directory is not part of the build context copy instructions.

---

## CRIT-02: Nginx Reverse Proxy Route Rewrite Strips `/api` Prefix, Breaking All Endpoints

### Severity: CRITICAL (Complete Functional Disconnect in Production)
- **Subsystem:** Production Deployment / Reverse Proxy / API Gateway
- **Affected File:** [`nginx.conf`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/nginx.conf) (Lines 18–24)
- **Root Cause:**
  In `nginx.conf`, the backend proxy block is configured as:
  ```nginx
  location /api/ {
      proxy_pass http://backend:8000/;
      ...
  }
  ```
  In Nginx URI processing semantics, specifying a trailing URI slash on `proxy_pass` causes Nginx to strip the matched location prefix (`/api/`) when forwarding to upstream.
- **Observed Manifestation:**
  When a browser calls `http://localhost/api/missions`, Nginx strips `/api/` and requests `http://backend:8000/missions`.
  However, the FastAPI backend in [`backend/app/main.py`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/backend/app/main.py) registers the route as `@app.get("/api/missions")`.
  Consequently:
  - Upstream backend returns **HTTP 404 Not Found** on **EVERY SINGLE API CALL**.
  - Additionally, non-prefixed routes like `/runs` and `/whatif` are completely ignored by `location /api/`, falling through to `location /` and returning raw `index.html` instead of JSON.
- **Verification Evidence:**
  Inspected [`nginx.conf`](file:///C:/Users/mohith/OneDrive/Documents/MiniProject/DOIP/nginx.conf) and compared with FastAPI router route tables in `backend/app/main.py`.
