# Replay Intelligence & After Action Review Specification (Phase 3F)

**Program:** Defense Operations Intelligence Platform (DOIP)  
**Subsystem:** Replay Intelligence & Run Comparison Engine  
**Author:** REPLAY_ENGINEER  

---

## 1. Capabilities

1. **Timeline Turning-Point Detection:**
   - Automatically parses recorded simulation event streams.
   - Detects moments of significant trajectory divergence, critical escalation, or missed resupply windows.
2. **AI After-Action Review (AAR):**
   - Synthesizes comprehensive structured executive summary.
   - Categorizes outcomes into:
     - Mission Objectives Achieved / Failed
     - Resource Efficiency (Fuel burn, comms reliability)
     - Key Decision Points (Human interventions vs missed warnings)
     - Root-Cause Attribution
3. **Run Comparison Engine (What-If Diff):**
   - Diff between Baseline Run and Branch Run:
     - Delta in total fuel consumed.
     - Delta in casualty / incident count.
     - Spatial trajectory divergence (maximum and average separation in km).

---

## 2. Data Contract & Persistence

- Table `replay_reports`:
  - `id`: String(64) Primary Key
  - `run_id`: String(64) Indexed
  - `comparison_run_id`: String(64) Nullable
  - `summary`: Text
  - `turning_points_json`: JSON
  - `kpi_deltas_json`: JSON
  - `created_at`: DateTime
