# DOIP Phase 1 — Real AI Query API & Citation Safety Specification

**Author:** AI-BACKEND-ENGINEER Agent (ECC Orchestration Team)  
**Target:** `POST /api/ai/query` + Context Assembler + Citation Safety Validator  
**Status:** Approved for Implementation  

---

## 1. Operational Paradigm & Safety Boundary

The AI Query service powers the interactive AI Drawer and Tactical Advisor across DOIP screens.

### Mandatory Safety Invariants (AGENTS.md & Chapter 13 Rules):
1. **The LLM is an observer and recommender, NOT an authoritative engine**:
   - The LLM receives read-only snapshots of the world and doctrine.
   - It cannot mutate simulation state or execute unconfirmed actions.
   - Any suggested operational actions output as `RECOMMENDATION` items conforming to the DOIP DSL.
2. **Strict Citation Grounding (Zero Fabrication)**:
   - The LLM is provided an explicit list of known source IDs (`valid_sources`).
   - The Citation Validator scans all references in the LLM response (`[SOP-xx]`, `[POL-xx]`, `[REF-xx]`, `[EV-xx]`, `[INC-xx]`, `[AL-xx]`).
   - If an identifier was not in the retrieved context, it is flagged as `unverified` and excluded from verified citations.
   - Unverified assertions cannot be labeled as `FACT`.
3. **Fail-Soft Degradation**:
   - If Ollama or the local LLM is unreachable or times out, the backend executes a deterministic rule-based grounding pipeline.
   - An HTTP 500 is never returned for an AI service timeout; a valid fail-soft response is returned with `mode: "fallback"`.

---

## 2. API Contract: `POST /api/ai/query`

### Request Body
```json
{
  "query": "What is the convoy escort doctrine and current fuel state?",
  "run_id": "RUN-SC2-01",
  "tick": 45
}
```
All fields except `query` are optional. If `run_id` is omitted, the active live simulation session is queried.

### Response Body
```json
{
  "query": "What is the convoy escort doctrine and current fuel state?",
  "answer": "According to [SOP-04 §1], convoys exceeding six cargo vehicles require middle escort elements. In the current operational picture at T+45, 1 unit is operating below 40% fuel (UAV-01 at 38%).",
  "facts": [
    "SOP-04 mandates lead, cargo, and trail elements for escorted movements.",
    "UAV-01 is currently reporting 38% fuel reserve."
  ],
  "projections": [
    "UAV-01 will reach bingo fuel in approximately 22 sim-minutes at current consumption rate."
  ],
  "recommendations": [
    {
      "action": "task_unit",
      "entity_id": "U-DEPOT-1",
      "summary": "Authorize depot refueling task for UAV-01 at Waypoint Bravo.",
      "requires_human_confirmation": true
    }
  ],
  "citations": [
    {
      "type": "doctrine",
      "source_id": "SOP-04",
      "citation": "SOP-04 §1",
      "title": "Convoy Escort Procedures",
      "verified": true
    },
    {
      "type": "simulation_entity",
      "source_id": "UAV-01",
      "citation": "Unit Telemetry T+45",
      "verified": true
    }
  ],
  "grounding": {
    "grounded": true,
    "warning": null,
    "valid_citations": ["SOP-04", "UAV-01"],
    "unverified_citations": []
  },
  "mode": "llm_grounded",
  "latency_ms": 142.5
}
```

---

## 3. Context Assembly Pipeline

Before prompting the LLM, the context builder gathers 5 structured context packets:
1. **Doctrine Context**: Top 3-5 chunks retrieved from `retrieve(query)`.
2. **Current Simulation State**: Active units count, average fuel/battery, posture, weather cells.
3. **Recent Event Log**: Last 15-30 events from the simulation log (incidents, alarms, comms changes).
4. **Active Incidents**: High and critical incidents from `world.incidents`.
5. **Logistics & Vitals**: Units below reserve thresholds (< 40% fuel, stale comms).

---

## 4. Citation Safety Validator Pipeline

```text
       Context Assembly
  [Doctrine + Events + State]
               ↓
  Extract Authoritative IDs
  (e.g., {"SOP-04", "INC-01", "UAV-01"})
               ↓
    LLM Inference Prompt
   (Strict reference syntax)
               ↓
        Raw LLM Response
               ↓
    Citation Validator Engine
  (Extract all bracketed / token citations)
               ↓
         Matches set?
         ├── YES ──> Mark Citation VERIFIED
         └── NO  ──> Flag UNVERIFIED, Strip from Claims
               ↓
     Classify Content Segments:
      - FACT (100% verified evidence)
      - PROJECTION (Sim trends / forward estimates)
      - RECOMMENDATION (DSL actions requiring confirmation)
               ↓
       Final Output
```
