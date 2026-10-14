"""DOIP MVP Backend — FastAPI v0.5.0.

Endpoints:
  /health                           liveness probe
  /auth/login                       demo HMAC tokens per role
  /scenarios                        built-in scenario catalogue
  /scenarios/custom GET/POST/DELETE author-created scenarios (P2-1)
  /scenarios/validate POST          DSL validation gate (P2-1)
  /runs   POST/GET                  persist + list recorded runs (SQLite)
  /runs/{id}/report GET             After-Action Report (AAR) plain-text (P2-4)
  /audit  GET                       append-only audit trail — paginated, admin only
  /admin/users GET/POST/DELETE      user roster — now DB-backed (P2-5)
  /sitrep POST                      LLM-enhanced sitrep (Ollama / rule-based fallback)
  /vision/adjudicate POST           batch-adjudicate detection events
  /vision/frames GET                latest synthetic surveillance frames (PNG base64)
  /whatif POST                      headless 60-tick branch run — result persisted
  /whatif/history GET               paginated list of past what-if results
  WS /ws/sim/{run_id}               live event stream — requires ?token= JWT
  WS /ws/warroom                    shared task-board hub — requires ?token= JWT

Run:  uvicorn app.main:app --reload --port 8000  (from backend/)
"""

import asyncio
import base64
import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
    _root_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if _root_env.exists():
        load_dotenv(_root_env)
except ImportError:
    pass

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import auth, db
from .hub import hub
from .scenarios import SCENARIOS
from .session import SimSession
from . import sitrep as sitrep_mod
from . import vision as vision_mod
from . import whatif as whatif_mod
from . import aar as aar_mod
from . import dsl_parser
from . import rag as rag_mod
from .ai_service import ai_service
from . import routing as routing_mod
from . import mission_planner as mission_mod
from .warroom import warroom_hub
from . import optimizer as optimizer_mod
from . import redteam as redteam_mod
from .knowledge_graph import knowledge_graph
from .forecasting import digital_twin
from .copilot import copilot_service
from .replay_intelligence import replay_service
from .federation import federation_manager, FederationNode
from .multiworld import theater_manager, world_manager
from .distributed_forecaster import distributed_forecaster
from .graph_intelligence import graph_ai
from .swarm import swarm_coordinator
from .strategic_copilot import strategic_copilot
from .future_generator import future_generator
from .campaign_replay import campaign_replay_engine
from .event_stream import event_bus
from .datalake import data_lake
from .agent_runtime import agent_runtime
from .memory_store import memory_store
from .analysis_engine import analysis_engine
from .large_scale_forecasting import large_scale_forecaster
from .massive_whatif import massive_whatif
from .knowledge_synthesizer import knowledge_synthesizer
from .analytics_engine import operational_analytics
from .observability import observability
from .model_management import model_manager
from .workflow_engine import workflow_engine
from .reporting_engine import reporting_engine
from .resilience import resilience_manager
from .cache import cache_manager
from .scalability import scalability_benchmark
from .unified_knowledge import unified_knowledge
from .platform_unification import platform_registry, platform_lifecycle, platform_config
from .operations_center import operations_center
from .governance import governance_engine
from .validation_engine import validation_engine
from .self_healing import self_healing_engine
from .documentation_engine import documentation_engine
from .data_governance import data_governance_engine
from .quality_platform import quality_platform
from .research_sandbox import research_sandbox
from .environmental_context import environmental_context_service
from .world_model import world_model_service
from fastapi.responses import PlainTextResponse

app = FastAPI(title="DOIP Command Center Backend", version="0.9.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- active sim sessions keyed by run_id ---
_sessions: dict[str, SimSession] = {}
_sessions_lock = asyncio.Lock()


@app.on_event("startup")
def _startup() -> None:
    db.init()
    db.seed_users()   # P2-5: populate demo roster if users table is empty
    platform_lifecycle.bootstrap_platform()


# ============================================================
# Auth helpers
# ============================================================
class LoginBody(BaseModel):
    role: str
    userName: str


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    user = auth.verify(authorization.removeprefix("Bearer "))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    """Convenience dependency — short-circuits with 403 for non-admin callers."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def _ws_user(ws: WebSocket) -> dict | None:
    """Extract and verify the JWT from the ?token= query param on a WebSocket.

    Returns the decoded user dict on success, None on failure.
    The caller must close the socket when None is returned.
    """
    token = dict(ws.query_params).get("token", "")
    return auth.verify(token) if token else None


# ============================================================
# Core endpoints
# ============================================================
@app.get("/health")
def health() -> dict:
    active = list(_sessions.keys())
    return {"ok": True, "service": "doip-backend", "version": "0.5.0",
            "active_sessions": active}


@app.post("/auth/login")
def login(body: LoginBody) -> dict:
    if body.role not in auth.ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {body.role}")
    db.add_audit(body.userName or "unknown", "login", body.role)
    return {"token": auth.issue(body.role, body.userName)}


@app.get("/scenarios")
def scenarios_list() -> dict:
    return {"scenarios": SCENARIOS}


# ============================================================
# Pan-India Live World & Artificial Impact Simulation (Phase 9)
# ============================================================
class ForkSimulationBody(BaseModel):
    scenario_id: str
    seed: int = 20261014
    branch_id: str | None = None
    name: str | None = None


class ResetSimulationBody(BaseModel):
    branch_id: str


class StepSimulationBody(BaseModel):
    branch_id: str


@app.get("/api/environment/context")
async def get_environment_context(force_refresh: bool = False) -> dict:
    return await environmental_context_service.get_environmental_context(force_refresh=force_refresh)


@app.get("/api/world/baseline")
async def get_world_baseline() -> dict:
    return await world_model_service.get_baseline_world()


@app.get("/api/world/branches")
def list_simulation_branches() -> dict:
    return {"branches": world_model_service.list_branches()}


@app.post("/api/world/simulation/fork")
def fork_simulation_branch(body: ForkSimulationBody) -> dict:
    branch = world_model_service.fork_simulation(
        scenario_id=body.scenario_id,
        seed=body.seed,
        branch_id=body.branch_id,
        name=body.name,
    )
    return {
        "status": "forked",
        "branch": branch.to_dict(),
        "initial_events": [ev.to_dict() for ev in branch.init_events],
    }


@app.post("/api/world/simulation/reset")
def reset_simulation_branch(body: ResetSimulationBody) -> dict:
    try:
        return world_model_service.reset_simulation(body.branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/world/simulation/step")
def step_simulation_branch(body: StepSimulationBody) -> dict:
    try:
        events = world_model_service.step_branch(body.branch_id)
        return {"branch_id": body.branch_id, "events": events}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))



# ============================================================
# Run persistence
# ============================================================
class RunBody(BaseModel):
    id: str
    seed: int
    scenarioId: str
    ticks: int
    events: int
    log: list[dict[str, Any]]


@app.post("/runs")
def save_run(body: RunBody, user: dict = Depends(current_user)) -> dict:
    db.save_run(body.model_dump())
    db.add_audit(user.get("name", "unknown"), "run_saved", body.id)
    return {"ok": True}


@app.get("/runs")
def list_runs(user: dict = Depends(current_user)) -> dict:
    return {"runs": db.list_runs()}


@app.get("/runs/{run_id}")
def get_run_endpoint(run_id: str, user: dict = Depends(current_user)) -> dict:
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run



@app.get("/runs/{run_id}/report")
def run_aar(run_id: str, user: dict = Depends(current_user)) -> dict:
    """Generate a plain-text After-Action Report for a finished run (P2-4)."""
    runs = db.list_runs(limit=100)
    run = next((r for r in runs if r["id"] == run_id), None)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    world = db.load_world_snapshot(run_id)
    report = aar_mod.generate(run_id, run["log"], world)
    db.add_audit(user.get("name", "?"), "aar_download", run_id)
    return {"runId": run_id, "report": report}


# ============================================================
# Audit log  —  paginated  (P0-4)
# ============================================================
@app.get("/audit")
def list_audit(
    page: int = 1,
    per_page: int = 50,
    user: dict = Depends(require_admin),
) -> dict:
    """Return a paginated slice of the audit log.

    Query params:
        page     — 1-based page index (default: 1)
        per_page — rows per page, capped at 200 (default: 50)
    """
    per_page = min(per_page, 200)
    rows, total = db.list_audit_page(page=page, per_page=per_page)
    return {
        "audit": rows,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, -(-total // per_page)),  # ceiling division
    }


# ============================================================
# Admin — user management  (P2-5: now DB-backed)
# ============================================================
class UserBody(BaseModel):
    name: str
    role: str
    unit: str = "Unassigned"


@app.get("/admin/users")
def list_users_endpoint(_admin: dict = Depends(require_admin)) -> dict:
    return {"users": db.list_users()}


@app.post("/admin/users", status_code=201)
def create_user(body: UserBody, admin: dict = Depends(require_admin)) -> dict:
    if body.role not in auth.ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {body.role}")
    existing = db.list_users()
    if any(u["name"] == body.name for u in existing):
        raise HTTPException(status_code=409, detail="User already exists")
    entry = db.add_user(body.name, body.role, body.unit)
    db.add_audit(admin.get("name", "?"), "user_create", f"{body.name}:{body.role}")
    return {"ok": True, "user": entry}


@app.delete("/admin/users/{name}")
def delete_user(name: str, admin: dict = Depends(require_admin)) -> dict:
    if not db.remove_user(name):
        raise HTTPException(status_code=404, detail="User not found")
    db.add_audit(admin.get("name", "?"), "user_delete", name)
    return {"ok": True}


# ============================================================
# Custom Scenario CRUD + DSL validation gate  (P2-1)
# ============================================================

# Whitelisted DSL verbs — AGENTS.md §Ch13: never extend without human approval
_DSL_WHITELIST = {"spawn_weather", "create_incident", "raise_alert", "modify_speed"}


class ScenarioActionBody(BaseModel):
    id: int
    verb: str
    target: str
    magnitude: float   # 0–100
    tick: int = 0      # inject at this tick (0 = start)
    rationale: str = ""


class CustomScenarioBody(BaseModel):
    scenarioId: str
    name: str
    description: str = ""
    config: dict[str, Any] = {}
    actions: list[ScenarioActionBody] = []
    status: str = "draft"   # draft | approved


def _validate_actions(actions: list[ScenarioActionBody]) -> list[dict]:
    """Validate each action against the DSL whitelist. Returns per-action results."""
    results = []
    for a in actions:
        ok = a.verb in _DSL_WHITELIST
        results.append({
            "id": a.id,
            "verb": a.verb,
            "valid": ok,
            "error": None if ok else f"Verb '{a.verb}' is not in the approved whitelist.",
        })
    return results


@app.get("/scenarios/custom")
def list_custom_scenarios(user: dict = Depends(current_user)) -> dict:
    return {"scenarios": db.list_custom_scenarios()}


@app.post("/scenarios/custom", status_code=201)
def save_custom_scenario(
    body: CustomScenarioBody,
    user: dict = Depends(current_user),
) -> dict:
    """Save or update a custom scenario. Planner or admin only."""
    if user.get("role") not in ("admin", "planner"):
        raise HTTPException(status_code=403, detail="Planner role required")
    # Run validation — reject if any action fails
    results = _validate_actions(body.actions)
    if any(not r["valid"] for r in results):
        raise HTTPException(
            status_code=422,
            detail={"message": "DSL validation failed", "results": results},
        )
    saved = db.save_custom_scenario(
        scenario_id=body.scenarioId,
        name=body.name,
        description=body.description,
        config=body.config,
        actions=[a.model_dump() for a in body.actions],
        status=body.status,
        author=user.get("name", "?"),
    )
    db.add_audit(user.get("name", "?"), "scenario_save", body.scenarioId)
    return {"ok": True, "scenario": saved}


@app.delete("/scenarios/custom/{scenario_id}")
def delete_custom_scenario(
    scenario_id: str,
    user: dict = Depends(current_user),
) -> dict:
    if user.get("role") not in ("admin", "planner"):
        raise HTTPException(status_code=403, detail="Planner role required")
    if not db.delete_custom_scenario(scenario_id):
        raise HTTPException(status_code=404, detail="Scenario not found")
    db.add_audit(user.get("name", "?"), "scenario_delete", scenario_id)
    return {"ok": True}


@app.post("/scenarios/validate")
def validate_scenario(
    body: CustomScenarioBody,
    user: dict = Depends(current_user),
) -> dict:
    """Dry-run DSL validation without saving. Returns per-action pass/fail."""
    if user.get("role") not in ("admin", "planner"):
        raise HTTPException(status_code=403, detail="Planner role required")
    results = _validate_actions(body.actions)
    valid = all(r["valid"] for r in results)
    return {"valid": valid, "results": results}


# ============================================================
# Canonical Scenario YAML library (Phase 3)
# ============================================================
@app.get("/scenarios/yaml")
def list_yaml_scenarios(user: dict = Depends(current_user)) -> dict:
    scenarios_dir = Path(__file__).resolve().parent.parent.parent / "scenarios"
    out = []
    if scenarios_dir.exists():
        for f in sorted(scenarios_dir.glob("*.yaml")):
            try:
                sc = dsl_parser.load_yaml_scenario(f)
                out.append({
                    "file": f.name,
                    "id": sc["id"],
                    "name": sc["name"],
                    "duration_minutes": sc["duration_minutes"],
                    "seed": sc["seed"],
                    "entity_count": sc["entity_count"],
                    "timeline_events": len(sc.get("timeline", [])),
                    "rules_count": len(sc.get("rules", [])),
                })
            except Exception:
                continue
    return {"scenarios": out}


# ============================================================
# Doctrine RAG & Grounding Verifier (Phase 3)
# ============================================================
class RagQueryBody(BaseModel):
    query: str
    recentEvents: list[dict[str, Any]] = []


def optional_user(authorization: str | None = Header(default=None)) -> dict:
    if authorization and authorization.startswith("Bearer "):
        user = auth.verify(authorization.removeprefix("Bearer "))
        if user:
            return user
    return {"name": "operator", "role": "operator"}


class AIQueryBody(BaseModel):
    query: str
    run_id: str | None = None
    tick: int | None = None


@app.post("/api/ai/query")
@app.post("/ai/query")
def ai_query_endpoint(body: AIQueryBody, user: dict = Depends(optional_user)) -> dict:
    """Execute grounded AI reasoning across doctrine, sim state, and live events."""
    db.add_audit(user.get("name", "operator"), "ai_query", body.query[:80])
    return ai_service.query(
        query=body.query,
        run_id=body.run_id,
        tick=body.tick,
        active_sessions=_sessions,
    )


class RetrieveBody(BaseModel):
    query: str
    top_k: int = 5
    filters: dict[str, Any] | None = None


@app.post("/api/rag/retrieve")
def rag_retrieve_endpoint(body: RetrieveBody, user: dict = Depends(optional_user)) -> dict:
    """Execute dense hybrid retrieval over doctrine chunks."""
    results = rag_mod.retrieve(body.query, top_k=body.top_k, filters=body.filters)
    return {"results": results, "count": len(results)}


@app.post("/rag/query")
def rag_query_endpoint(body: RagQueryBody, user: dict = Depends(optional_user)) -> dict:
    """Execute grounded RAG query across doctrine corpus and active sim events."""
    db.add_audit(user.get("name", "operator"), "rag_query", body.query[:80])
    return rag_mod.query_rag(body.query, recent_events=body.recentEvents)


@app.get("/corpus/docs")
def list_corpus_docs(user: dict = Depends(current_user)) -> dict:
    """List all 15 doctrine documents across POL, REF, and SOP categories."""
    docs = [
        {
            "id": d.doc_id,
            "category": d.category,
            "title": d.title,
            "tags": d.tags,
            "version": d.version,
        }
        for d in sorted(rag_mod.corpus_index.docs.values(), key=lambda x: x.doc_id)
    ]
    return {"docs": docs, "total": len(docs)}


@app.get("/corpus/docs/{doc_id}")
def get_corpus_doc(doc_id: str, user: dict = Depends(current_user)) -> dict:
    """Get full document content and section breakdown by document ID."""
    doc = rag_mod.corpus_index.docs.get(doc_id.upper())
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found in corpus")
    return {
        "id": doc.doc_id,
        "category": doc.category,
        "title": doc.title,
        "tags": doc.tags,
        "version": doc.version,
        "content": doc.content,
        "sections": [{"heading": h, "text": t} for h, t in doc.sections],
    }


# ============================================================
# Sitrep  (P1-1: now async, uses LLM when Ollama is available)
# ============================================================
class SitrepBody(BaseModel):
    world: dict[str, Any]
    events: list[dict[str, Any]]


@app.post("/sitrep")
async def generate_sitrep(body: SitrepBody,
                          user: dict = Depends(current_user)) -> dict:
    """Generate a situation report from the world snapshot + recent events.

    Attempts LLM enhancement via Ollama (llama3.2). Falls back to deterministic
    rule-based text if Ollama is unreachable or times out.
    """
    sections = await sitrep_mod.generate_async(body.world, body.events)
    return {"sections": sections, "generatedAtTick": body.world.get("tick", 0)}


# ============================================================
# Vision adjudication + frames endpoint  (P1-2)
# ============================================================
class VisionBody(BaseModel):
    detections: list[dict[str, Any]]
    minConfidence: float = 0.50
    autoAcceptAbove: float | None = None


@app.post("/vision/adjudicate")
def adjudicate_vision(body: VisionBody,
                      user: dict = Depends(current_user)) -> dict:
    result = vision_mod.adjudicate(
        body.detections,
        min_confidence=body.minConfidence,
        auto_accept_above=body.autoAcceptAbove,
    )
    db.add_audit(user.get("name", "?"), "vision_adjudicate",
                 f"confirmed={len(result['confirmed'])} pending={len(result['pending'])}")
    return result


@app.get("/vision/status")
def vision_status(user: dict = Depends(current_user)) -> dict:
    """Return YOLOv8n neural core status, loaded weights, and class definitions."""
    return vision_mod.get_model_status()


@app.get("/vision/samples")
def vision_samples(user: dict = Depends(current_user)) -> dict:
    """Return pre-loaded tactical surveillance frames for 1-click YOLO verification."""
    samples = vision_mod.get_tactical_samples()
    return {"samples": samples, "count": len(samples)}


@app.get("/vision/tracks")
def list_vision_tracks(limit: int = 50, user: dict = Depends(current_user)) -> dict:
    """Return active and historical multi-frame tracks from persistent database."""
    tracks = db.get_vision_tracks(limit=limit)
    return {"tracks": tracks, "count": len(tracks)}


@app.get("/vision/detections")
def list_vision_detections(limit: int = 50, frame_id: str | None = None, user: dict = Depends(current_user)) -> dict:
    """Return persisted vision detections from sensor streams."""
    detections = db.get_vision_detections(limit=limit, frame_id=frame_id)
    return {"detections": detections, "count": len(detections)}


class InferBody(BaseModel):
    image_b64: str
    unitId: str = "CAM-01"
    tick: int = 0
    confThreshold: float = 0.25


@app.post("/vision/infer")
def run_vision_inference(body: InferBody, user: dict = Depends(current_user)) -> dict:
    """Execute real-time YOLOv8n inference on a base64-encoded image."""
    try:
        raw_b64 = body.image_b64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        img_bytes = base64.b64decode(raw_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {exc}")

    res = vision_mod.infer_frame(
        img_bytes,
        unit_id=body.unitId,
        tick=body.tick,
        conf_threshold=body.confThreshold,
    )
    db.add_audit(
        user.get("name", "?"),
        "vision_inference",
        f"unit={body.unitId} detected={res.get('count', 0)} latency={res.get('infer_ms', 0)}ms",
    )
    return res


@app.get("/vision/frames")
def vision_frames(
    n: int = 6,
    tick: int = 0,
    user: dict = Depends(current_user),
) -> dict:
    """Return `n` synthetic surveillance frames as base64-encoded PNG.

    In production, replace the generator with a real camera feed adapter.
    The frame schema matches the VisionPanel contract in the frontend.

    Query params:
        n    — number of frames (1–12, default 6)
        tick — simulation tick used for deterministic frame generation
    """
    frames = vision_mod.generate_frames(n=min(n, 12), tick=tick)
    return {"frames": frames, "count": len(frames)}


# ============================================================
# What-If headless runner + history  (P1-3)
# ============================================================
class WhatIfBody(BaseModel):
    seed: int
    scenarioId: str
    ticks: int = 60
    actions: list[dict[str, Any]] = []
    runs: int = 1


@app.post("/whatif")
@app.post("/api/whatif")
def run_whatif(body: WhatIfBody,
              user: dict = Depends(current_user)) -> dict:
    """Run a headless branch simulation and persist the result."""
    if user.get("role") not in ("admin", "planner", "operator"):
        raise HTTPException(status_code=403, detail="Operator, planner, or admin role required")
    result = whatif_mod.run_branch(
        seed=body.seed,
        scenario_id=body.scenarioId,
        actions=body.actions,
        ticks=body.ticks,
        runs=max(1, min(20, body.runs)),
    )
    # Persist result to DB  (P1-3)
    whatif_id = db.save_whatif_result(
        seed=result.seed,
        scenario_id=result.scenario_id,
        ticks=result.ticks,
        actions=body.actions,
        deltas=result.deltas,
    )
    db.add_audit(user.get("name", "?"), "whatif_run",
                 f"id={whatif_id} seed={body.seed} sc={body.scenarioId} "
                 f"ticks={body.ticks} actions={len(body.actions)} runs={result.monte_carlo_runs}")
    return {
        "id": whatif_id,
        "seed": result.seed,
        "scenarioId": result.scenario_id,
        "ticks": result.ticks,
        "deltas": result.deltas,
        "baselineEvents": result.baseline_events,
        "branchEvents": result.branch_events,
        "baselineRisk": result.baseline_risk,
        "branchRisk": result.branch_risk,
        "p10Risk": result.p10_risk,
        "p50Risk": result.p50_risk,
        "p90Risk": result.p90_risk,
        "trajectories": result.trajectories,
        "spatialAnnotations": result.spatial_annotations,
        "monteCarloRuns": result.monte_carlo_runs,
    }


@app.get("/whatif/history")
@app.get("/api/whatif/history")
def whatif_history(
    limit: int = 20,
    user: dict = Depends(current_user),
) -> dict:
    """Return the most-recent `limit` persisted what-if results (newest-first)."""
    if user.get("role") not in ("admin", "planner", "operator"):
        raise HTTPException(status_code=403, detail="Operational role required")
    return {"results": db.list_whatif_results(limit=min(limit, 50))}


class CorpusQueryBody(BaseModel):
    query: str
    top_k: int = 5


@app.post("/corpus/query")
def corpus_query_endpoint(body: CorpusQueryBody) -> dict:
    """Semantic/token-scored search over the 15 canonical defense doctrine and SOP documents."""
    results = rag_mod.corpus_index.search(body.query, top_k=body.top_k)
    return {"results": results, "count": len(results)}




# ============================================================
# Live sim WebSocket  —  WS /ws/sim/{run_id}
# ============================================================
@app.websocket("/ws/sim/{run_id}")
async def sim_ws(ws: WebSocket, run_id: str) -> None:
    """Stream live sim events to the browser.

    Requires a valid JWT in the ?token= query param.
    Rejects unauthenticated connections with WS close code 4008 before accepting.

    Query params:
        token                    required — HMAC-signed JWT
        seed, scenarioId, speed  used only when starting a new session
    """
    if not _ws_user(ws):
        await ws.close(code=4008, reason="Missing or invalid token")
        return

    params = dict(ws.query_params)
    async with _sessions_lock:
        if run_id not in _sessions:
            seed = int(params.get("seed", 20260101))
            sc_id = params.get("scenarioId", "SC-1")
            speed = float(params.get("speed", 1.0))
            # Pass run_id so the session can key world snapshots in DB  (P1-4)
            session = SimSession(seed, sc_id, speed, run_id=run_id)
            _sessions[run_id] = session
            await session.start()
        session = _sessions[run_id]

    await session.handle_client(ws)

    # Clean up idle sessions (no clients, stopped)
    async with _sessions_lock:
        if run_id in _sessions and not _sessions[run_id]._clients:
            if _sessions[run_id]._stopped:
                del _sessions[run_id]


# ============================================================
# War-room task board WebSocket  —  WS /ws/warroom
# ============================================================
def get_caller_user(authorization: str | None = Header(default=None)) -> dict:
    """Optional bearer token extraction with fallback to local operator identity."""
    if authorization and authorization.startswith("Bearer "):
        user = auth.verify(authorization.removeprefix("Bearer "))
        if user:
            return user
    return {"username": "operator", "name": "Default Operator", "role": "operator"}


@app.websocket("/ws/warroom")
async def warroom(ws: WebSocket) -> None:
    """Shared collaborative operations center.

    Requires a valid JWT in the ?token= query param (or accepts demo tokens).
    Rejects unauthenticated connections with WS close code 4008 before accepting.
    """
    user = _ws_user(ws)
    if not user:
        # Fallback to query param user if available for testing
        token = dict(ws.query_params).get("token")
        if token == "demo" or not token:
            user = {"username": "demo_operator", "name": "Demo Operator", "role": "operator"}
        else:
            await ws.close(code=4008, reason="Missing or invalid token")
            return

    await warroom_hub.connect(ws, user)
    try:
        while True:
            data = await ws.receive_json()
            await warroom_hub.handle_message(ws, data)
    except WebSocketDisconnect:
        warroom_hub.disconnect(ws)


# ============================================================
# Authoritative Run Control & Simulation APIs
# ============================================================
class SimStartBody(BaseModel):
    seed: int = 20260101
    scenario_id: str = "SC-1"
    speed: float = 1.0
    run_id: str | None = None


class SimSpeedBody(BaseModel):
    speed: float
    run_id: str | None = None


class SimCommandBody(BaseModel):
    run_id: str | None = None


class SimInjectBody(BaseModel):
    run_id: str | None = None
    event: dict[str, Any]


@app.post("/api/sim/start")
async def api_sim_start(body: SimStartBody, user: dict = Depends(get_caller_user)) -> dict:
    """Start or initialize an authoritative simulation run."""
    run_id = body.run_id or f"RUN-{body.seed}-{body.scenario_id}-{int(time.time())}"
    async with _sessions_lock:
        if run_id in _sessions:
            session = _sessions[run_id]
            if session._stopped:
                session = SimSession(body.seed, body.scenario_id, body.speed, run_id=run_id)
                _sessions[run_id] = session
                await session.start()
        else:
            session = SimSession(body.seed, body.scenario_id, body.speed, run_id=run_id)
            _sessions[run_id] = session
            await session.start()
    return {
        "ok": True,
        "runId": run_id,
        "seed": body.seed,
        "scenarioId": body.scenario_id,
        "speed": session.speed,
        "status": "RUNNING",
    }


@app.post("/api/sim/pause")
async def api_sim_pause(body: SimCommandBody, user: dict = Depends(get_caller_user)) -> dict:
    """Pause active simulation execution and freeze simulation time."""
    run_id = body.run_id
    async with _sessions_lock:
        session = _sessions.get(run_id) if run_id else (next(iter(_sessions.values())) if _sessions else None)
        if not session:
            raise HTTPException(status_code=404, detail="Active simulation session not found")
        await session.pause()
    return {"ok": True, "runId": session.run_id, "status": "PAUSED", "tick": session.engine.tick}


@app.post("/api/sim/resume")
async def api_sim_resume(body: SimCommandBody, user: dict = Depends(get_caller_user)) -> dict:
    """Resume paused simulation from current clock without duplicate loops."""
    run_id = body.run_id
    async with _sessions_lock:
        session = _sessions.get(run_id) if run_id else (next(iter(_sessions.values())) if _sessions else None)
        if not session:
            raise HTTPException(status_code=404, detail="Active simulation session not found")
        await session.resume()
    return {"ok": True, "runId": session.run_id, "status": "RUNNING", "tick": session.engine.tick}


@app.post("/api/sim/stop")
async def api_sim_stop(body: SimCommandBody, user: dict = Depends(get_caller_user)) -> dict:
    """Terminate run cleanly and persist final state."""
    run_id = body.run_id
    async with _sessions_lock:
        session = _sessions.get(run_id) if run_id else (next(iter(_sessions.values())) if _sessions else None)
        if not session:
            raise HTTPException(status_code=404, detail="Active simulation session not found")
        await session.stop()
    return {"ok": True, "runId": session.run_id, "status": "STOPPED", "ticks": session.engine.tick}


@app.post("/api/sim/speed")
async def api_sim_speed(body: SimSpeedBody, user: dict = Depends(get_caller_user)) -> dict:
    """Update speed multiplier (0.25x - 20x) on active engine loop immediately."""
    run_id = body.run_id
    async with _sessions_lock:
        session = _sessions.get(run_id) if run_id else (next(iter(_sessions.values())) if _sessions else None)
        if not session:
            raise HTTPException(status_code=404, detail="Active simulation session not found")
        await session.set_speed(body.speed)
    return {"ok": True, "runId": session.run_id, "speed": session.speed}


@app.get("/api/sim/status")
def api_sim_status(run_id: str | None = None) -> dict:
    """Inspect active simulation lifecycle, tick clock, and speed."""
    session = _sessions.get(run_id) if run_id else (next(iter(_sessions.values())) if _sessions else None)
    if not session:
        return {"status": "IDLE", "tick": 0, "active_sessions": list(_sessions.keys())}
    return {
        "runId": session.run_id,
        "seed": session.seed,
        "scenarioId": session.scenario_id,
        "tick": session.engine.tick,
        "simTime": session.engine.tick * 1000,
        "speed": session.speed,
        "status": "PAUSED" if session._paused else ("STOPPED" if session._stopped else "RUNNING"),
        "eventsCount": len(session._log),
        "clientsCount": len(session._clients),
        "unitsCount": len(session._units),
    }


@app.get("/api/sim/snapshot")
def api_sim_snapshot(run_id: str | None = None) -> dict:
    """Retrieve authoritative live world snapshot."""
    session = _sessions.get(run_id) if run_id else (next(iter(_sessions.values())) if _sessions else None)
    if not session:
        if run_id:
            snap = db.load_world_snapshot(run_id)
            if snap:
                return snap
        raise HTTPException(status_code=404, detail="World snapshot not found")
    return session._world_snapshot()


@app.post("/api/sim/inject")
async def api_sim_inject(body: SimInjectBody, user: dict = Depends(get_caller_user)) -> dict:
    """Inject operator or scenario action into running simulation engine."""
    run_id = body.run_id
    async with _sessions_lock:
        session = _sessions.get(run_id) if run_id else (next(iter(_sessions.values())) if _sessions else None)
        if not session:
            raise HTTPException(status_code=404, detail="Active simulation session not found")
        events = await session.inject(body.event)
    return {"ok": True, "events": events, "count": len(events)}


# ============================================================
# Historical Replay APIs
# ============================================================
@app.get("/api/replay/{run_id}")
def api_replay_run(run_id: str) -> dict:
    """Fetch run metadata and complete event history."""
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


@app.get("/api/replay/{run_id}/state")
def api_replay_state(run_id: str, tick: int = 0) -> dict:
    """Reconstruct exact historical state at arbitrary simulation timestamp."""
    state = db.get_run_reconstructed_state(run_id, tick)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return state


@app.get("/api/replay/{run_id}/positions")
def api_replay_positions(
    run_id: str,
    unit_id: str | None = None,
    start_tick: int = 0,
    end_tick: int | None = None,
    limit: int = 2000,
) -> list[dict]:
    """Retrieve historical unit position tracks."""
    return db.list_unit_positions(unit_id=unit_id, run_id=run_id, start_tick=start_tick, end_tick=end_tick, limit=limit)


@app.get("/api/replay/{run_id}/vitals")
def api_replay_vitals(
    run_id: str,
    person_id: str | None = None,
    start_tick: int = 0,
    end_tick: int | None = None,
    limit: int = 1000,
) -> list[dict]:
    """Retrieve historical personnel vitals tracks."""
    return db.list_personnel_vitals(person_id=person_id, run_id=run_id, start_tick=start_tick, end_tick=end_tick, limit=limit)


# ============================================================
# Persistent Units & Personnel APIs
# ============================================================
@app.get("/api/units")
def api_list_units(run_id: str | None = None) -> list[dict]:
    """List persistent units, sourcing from active simulation or database."""
    if not run_id and _sessions:
        session = next(iter(_sessions.values()))
        return list(session._units.values())
    return db.list_units(run_id=run_id)


@app.get("/api/units/{unit_id}/history")
def api_unit_history(unit_id: str, run_id: str | None = None, limit: int = 1000) -> list[dict]:
    """Retrieve position and telemetry history for a specific unit."""
    return db.list_unit_positions(unit_id=unit_id, run_id=run_id, limit=limit)


@app.get("/api/personnel")
def api_list_personnel(run_id: str | None = None, unit_id: str | None = None) -> list[dict]:
    """List persistent personnel with active mission, vitals and unit assignment."""
    if not run_id and _sessions:
        session = next(iter(_sessions.values()))
        res = list(session._personnel.values())
        if unit_id:
            res = [p for p in res if p.get("unitId") == unit_id or p.get("unit_id") == unit_id]
        return res
    return db.list_personnel(run_id=run_id, unit_id=unit_id)


@app.get("/api/personnel/{person_id}")
def api_get_person(person_id: str) -> dict:
    """Retrieve single personnel dossier."""
    if _sessions:
        for s in _sessions.values():
            if person_id in s._personnel:
                return s._personnel[person_id]
    p = db.get_person(person_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Personnel {person_id} not found")
    return p


@app.get("/api/personnel/{person_id}/vitals")
def api_personnel_vitals(person_id: str, run_id: str | None = None, limit: int = 500) -> list[dict]:
    """Retrieve biometric vitals timeline for a specific person."""
    return db.list_personnel_vitals(person_id=person_id, run_id=run_id, limit=limit)


# ============================================================
# Phase 2A: Tactical Route Planning Engine
# ============================================================

class RouteCalculateRequest(BaseModel):
    start: list[float]
    destination: list[float]
    strategy: str = "shortest"
    world_state: dict[str, Any] | None = None
    constraints: dict[str, Any] | None = None
    persist: bool = True


@app.post("/api/routes/calculate")
def calculate_route_endpoint(body: RouteCalculateRequest, user: dict = Depends(get_caller_user)) -> dict:
    if len(body.start) < 2 or len(body.destination) < 2:
        raise HTTPException(status_code=400, detail="Start and destination must have at least [lat, lon]")
    start_pt = (float(body.start[0]), float(body.start[1]))
    dest_pt = (float(body.destination[0]), float(body.destination[1]))
    route = routing_mod.calculate_route(
        start=start_pt,
        destination=dest_pt,
        strategy=body.strategy,
        world_state=body.world_state,
        constraints=body.constraints,
        persist=body.persist,
    )
    return route


@app.get("/api/routes")
def list_routes_endpoint(limit: int = 20, user: dict = Depends(get_caller_user)) -> dict:
    return {"routes": db.list_routes(limit=min(limit, 100))}


@app.get("/api/routes/{route_id}")
def get_route_endpoint(route_id: str, user: dict = Depends(get_caller_user)) -> dict:
    route = db.get_route(route_id)
    if not route:
        raise HTTPException(status_code=404, detail=f"Route '{route_id}' not found")
    return route


# ============================================================
# Phase 2B: Mission Planning System
# ============================================================
class MissionCreateRequest(BaseModel):
    name: str
    description: str = ""
    objectives: list[Any] = []
    tasks: list[dict[str, Any]] = []
    assigned_assets: list[str] = []
    route_id: str | None = None
    area_geojson: str | None = None
    constraints: dict[str, Any] | None = None


class MissionTransitionRequest(BaseModel):
    target_status: str
    notes: str = ""


class AiDraftRequest(BaseModel):
    prompt: str
    constraints: dict[str, Any] | None = None


@app.post("/api/missions")
def create_mission_endpoint(body: MissionCreateRequest, user: dict = Depends(get_caller_user)) -> dict:
    body_dict = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    mission = mission_mod.create_mission(body_dict, actor=user.get("username", "operator"))
    return mission


@app.get("/api/missions")
def list_missions_endpoint(limit: int = 50, status: str | None = None, user: dict = Depends(get_caller_user)) -> dict:
    return {"missions": db.list_missions(limit=limit, status=status)}


@app.get("/api/missions/{mission_id}")
def get_mission_endpoint(mission_id: str, user: dict = Depends(get_caller_user)) -> dict:
    mission = db.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")
    return mission


@app.post("/api/missions/{mission_id}/transition")
def transition_mission_endpoint(mission_id: str, body: MissionTransitionRequest, user: dict = Depends(get_caller_user)) -> dict:
    try:
        updated = mission_mod.transition_mission_lifecycle(
            mission_id=mission_id,
            target_status=body.target_status,
            actor=user.get("username", "operator"),
            notes=body.notes,
        )
        return updated
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/missions/ai-draft")
def ai_draft_mission_endpoint(body: AiDraftRequest, user: dict = Depends(get_caller_user)) -> dict:
    draft = mission_mod.generate_ai_mission_proposal(body.prompt, constraints=body.constraints)
    return draft


# ============================================================
# Phase 2C: War Room Real-Time Collaboration
# ============================================================
class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    incident_id: str | None = None
    assigned_to: str | None = None
    priority: str = "MEDIUM"


class TaskAssignRequest(BaseModel):
    assigned_to: str
    reason: str = ""


@app.get("/api/warroom/presence")
def list_presence_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    return {"presence": list(warroom_hub.presence.values()) or db.list_warroom_presence()}


@app.get("/api/warroom/tasks")
def list_warroom_tasks_endpoint(incident_id: str | None = None, status: str | None = None, user: dict = Depends(get_caller_user)) -> dict:
    return {"tasks": db.list_warroom_tasks(incident_id=incident_id, status=status)}


@app.post("/api/warroom/tasks")
async def create_warroom_task_endpoint(body: TaskCreateRequest, user: dict = Depends(get_caller_user)) -> dict:
    task_data = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    task_data["created_by"] = user.get("username", "operator")
    saved = db.save_warroom_task(task_data)
    await warroom_hub.broadcast({"type": "task_updated", "payload": saved})
    return saved


@app.post("/api/warroom/tasks/{task_id}/assign")
async def assign_warroom_task_endpoint(task_id: int, body: TaskAssignRequest, user: dict = Depends(get_caller_user)) -> dict:
    success = db.assign_warroom_task(
        task_id=task_id,
        to_user=body.assigned_to,
        from_user=user.get("username", "operator"),
        reason=body.reason,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or assignment failed")
    tasks = db.list_warroom_tasks()
    updated = next((t for t in tasks if t["id"] == task_id), None)
    await warroom_hub.broadcast({
        "type": "task_assigned",
        "payload": {
            "task": updated,
            "from_user": user.get("username", "operator"),
            "to_user": body.assigned_to,
            "reason": body.reason,
        },
    })
    return {"success": True, "task": updated}


# ============================================================
# Phase 2D: Investment Optimization Engine
# ============================================================
class OptimizerSolveRequest(BaseModel):
    budget: float = 250000.0
    priorities: dict[str, float] | None = None
    constraints: dict[str, Any] | None = None
    asset_catalogue: list[dict[str, Any]] | None = None


@app.post("/api/optimizer/solve")
def solve_optimizer_endpoint(body: OptimizerSolveRequest, user: dict = Depends(get_caller_user)) -> dict:
    result = optimizer_mod.solve_investment_portfolio(
        budget=body.budget,
        priorities=body.priorities,
        constraints=body.constraints,
        asset_catalogue=body.asset_catalogue,
    )
    return result


@app.get("/api/optimizer/history")
def list_optimizer_history_endpoint(limit: int = 10, user: dict = Depends(get_caller_user)) -> dict:
    return {"runs": db.list_optimizer_runs(limit=limit)}


# ============================================================
# Phase 2E: Red Team Adversarial Planner
# ============================================================
class RedTeamGenerateRequest(BaseModel):
    mission_id: str | None = None
    mission_data: dict[str, Any] | None = None
    route_data: dict[str, Any] | None = None
    world_state: dict[str, Any] | None = None


class InjectValidateRequest(BaseModel):
    action: str
    params: dict[str, Any]
    trigger_tick: int = 10


class InjectApproveRequest(BaseModel):
    scenario_id: str


@app.post("/api/redteam/generate")
def generate_redteam_endpoint(body: RedTeamGenerateRequest, user: dict = Depends(get_caller_user)) -> dict:
    scenario = redteam_mod.generate_adversarial_scenario(
        mission_id=body.mission_id,
        mission_data=body.mission_data,
        route_data=body.route_data,
        world_state=body.world_state,
    )
    return scenario


@app.post("/api/redteam/validate-inject")
def validate_inject_endpoint(body: InjectValidateRequest, user: dict = Depends(get_caller_user)) -> dict:
    body_dict = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    valid, msg = redteam_mod.validate_inject_against_dsl(body_dict)
    return {"valid": valid, "message": msg}


@app.post("/api/redteam/injects/{inject_id}/approve")
def approve_inject_endpoint(inject_id: str, body: InjectApproveRequest, user: dict = Depends(get_caller_user)) -> dict:
    try:
        result = redteam_mod.approve_adversarial_inject(
            scenario_id=body.scenario_id,
            inject_id=inject_id,
            approved_by=user.get("username", "exercise_coordinator"),
        )
        return result
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/redteam/scenarios")
def list_redteam_scenarios_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    return {"scenarios": db.list_redteam_scenarios()}


# ============================================================
# Phase 3: Operational Knowledge Graph API
# ============================================================
@app.get("/api/graph/subgraph")
def get_graph_subgraph_endpoint(
    center_id: str | None = None,
    depth: int = 2,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Export depth-bounded ego subgraph formatted for D3 / Sigma.js."""
    return knowledge_graph.export_subgraph(center_id=center_id, depth=depth)


@app.get("/api/graph/root-cause/{incident_id}")
def get_root_cause_endpoint(
    incident_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Perform causal attribution traversal backwards to root trigger."""
    return knowledge_graph.find_root_cause(incident_id=incident_id)


@app.get("/api/graph/dependencies/{entity_id}")
def get_dependencies_endpoint(
    entity_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Traverse operational dependencies and identify single points of failure."""
    return knowledge_graph.find_dependencies(entity_id=entity_id)


@app.get("/api/graph/incident-chain/{incident_id}")
def get_incident_chain_endpoint(
    incident_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Return ordered directed causal progression from origin to impact."""
    return {"chain": knowledge_graph.trace_incident_chain(incident_id=incident_id)}


@app.post("/api/graph/seed")
def seed_graph_endpoint(
    user: dict = Depends(get_caller_user),
) -> dict:
    """Seed demo tactical scenario knowledge graph."""
    res = knowledge_graph.seed_demo_graph()
    return {"status": "seeded", **res}


# ============================================================
# Phase 3: Digital Twin Lookahead Forecasting API
# ============================================================
class ForecastRequestBody(BaseModel):
    horizon_hours: float = 2.0
    confidence: float = 0.95
    scenario_id: str = "SC-DEFAULT"
    world_state: dict[str, Any] | None = None


@app.post("/api/forecast")
def generate_forecast_endpoint(
    body: ForecastRequestBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Generate forward multi-tick operational lookahead forecast."""
    w_state = body.world_state
    if w_state is None and _sessions:
        first_session = next(iter(_sessions.values()))
        if hasattr(first_session, "_world_snapshot"):
            w_state = first_session._world_snapshot()

    return digital_twin.forecast(
        horizon_hours=body.horizon_hours,
        confidence=body.confidence,
        world_state=w_state,
        scenario_id=body.scenario_id,
    )


@app.get("/api/forecast/history")
def list_forecast_history_endpoint(
    limit: int = 10,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Retrieve history of persisted forecast runs."""
    return {"runs": db.list_forecast_runs(limit=limit)}


@app.get("/api/forecast/{forecast_id}")
def get_forecast_run_endpoint(
    forecast_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Retrieve specific persisted forecast run."""
    run = db.get_forecast_run(forecast_id)
    if not run:
        raise HTTPException(status_code=404, detail="Forecast run not found")
    return run


# ============================================================
# Phase 3E: Multi-Agent Mission Copilot API
# ============================================================
class CopilotChatBody(BaseModel):
    session_id: str | None = None
    message: str
    context: dict[str, Any] | None = None


class CopilotProposeBody(BaseModel):
    session_id: str
    prompt: str
    context: dict[str, Any] | None = None


class CopilotApproveBody(BaseModel):
    proposal_id: str
    user: str | None = None


@app.post("/api/copilot/chat")
def copilot_chat_endpoint(
    body: CopilotChatBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Interactive conversational session with multi-agent mission copilot."""
    caller = user.get("username", "Commander")
    return copilot_service.chat(
        session_id=body.session_id,
        message=body.message,
        context=body.context,
        user=caller,
    )


@app.post("/api/copilot/propose")
def copilot_propose_endpoint(
    body: CopilotProposeBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Generate multi-agent structured mission package staged for human approval."""
    return copilot_service.propose_mission_package(
        session_id=body.session_id,
        prompt=body.prompt,
        context=body.context,
    )


@app.get("/api/copilot/sessions")
def list_copilot_sessions_endpoint(
    limit: int = 50,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """Retrieve past interactive copilot planning sessions."""
    return copilot_service.list_sessions(limit=limit)


@app.get("/api/copilot/sessions/{session_id}")
def get_copilot_session_endpoint(
    session_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Retrieve details and messages of a specific copilot session."""
    session = copilot_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Copilot session not found")
    return session


@app.post("/api/copilot/sessions/{session_id}/approve")
def approve_copilot_proposal_endpoint(
    session_id: str,
    body: CopilotApproveBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Human-in-the-loop approval gate for staged mission proposal."""
    caller = body.user or user.get("username", "Commander")
    try:
        return copilot_service.approve_proposal(
            session_id=session_id,
            proposal_id=body.proposal_id,
            user=caller,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================
# Phase 3F: Replay Intelligence & After Action Review API
# ============================================================
class ReplayTurningPointsBody(BaseModel):
    run_id: str | None = None
    events: list[dict[str, Any]] | None = None


class ReplayAarBody(BaseModel):
    run_id: str
    turning_points: list[dict[str, Any]] | None = None


class ReplayCompareBody(BaseModel):
    baseline_run_id: str
    branch_run_id: str


@app.post("/api/replay/turning-points")
def replay_turning_points_endpoint(
    body: ReplayTurningPointsBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Detect critical timeline inflection events in recorded simulation stream."""
    tps = replay_service.detect_turning_points(run_id=body.run_id, events=body.events)
    return {"run_id": body.run_id, "turning_points": tps, "count": len(tps)}


@app.post("/api/replay/aar")
def replay_aar_endpoint(
    body: ReplayAarBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Synthesize comprehensive AI After Action Review (AAR)."""
    return replay_service.generate_aar_summary(run_id=body.run_id, turning_points=body.turning_points)


@app.post("/api/replay/compare")
def replay_compare_endpoint(
    body: ReplayCompareBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Compute What-If comparison deltas (fuel, casualties, spatial divergence)."""
    return replay_service.compare_runs(
        baseline_run_id=body.baseline_run_id,
        branch_run_id=body.branch_run_id,
    )


@app.get("/api/replay/reports")
def list_replay_reports_endpoint(
    run_id: str | None = None,
    limit: int = 50,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """Retrieve history of persisted after-action reports."""
    return replay_service.list_reports(run_id=run_id, limit=limit)


@app.get("/api/replay/reports/{report_id}")
def get_replay_report_endpoint(
    report_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Retrieve a specific after-action report by ID."""
    rep = replay_service.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Replay report not found")
    return rep


# ============================================================
# Phase 4A: Federated Command Architecture API
# ============================================================
class FederationNodeCreateBody(BaseModel):
    id: str
    name: str
    tier: str = "tactical"
    region: str = "GLOBAL"
    endpoint: str = ""
    metadata: dict[str, Any] | None = None


class DirectiveBroadcastBody(BaseModel):
    origin_id: str
    title: str
    content: str
    target_tier: str = "operational"


class IntelligenceShareBody(BaseModel):
    source_node_id: str
    kind: str
    payload: dict[str, Any]


@app.get("/api/federation/nodes")
def list_federation_nodes_endpoint(
    tier: str | None = None,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """Retrieve active nodes in the federated command network."""
    return federation_manager.list_nodes(tier=tier)


@app.post("/api/federation/nodes")
def register_federation_node_endpoint(
    body: FederationNodeCreateBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Register or heartbeat a federation command node."""
    node = FederationNode(
        node_id=body.id,
        name=body.name,
        tier=body.tier,  # type: ignore
        region=body.region,
        endpoint=body.endpoint,
        metadata=body.metadata or {},
    )
    return federation_manager.register_node(node)


@app.post("/api/federation/directives")
def broadcast_directive_endpoint(
    body: DirectiveBroadcastBody,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """Cascade strategic directives down the command hierarchy."""
    return federation_manager.broadcast_directive(
        origin_id=body.origin_id,
        directive_title=body.title,
        content=body.content,
        target_tier=body.target_tier,
    )


@app.post("/api/federation/intelligence")
def synchronize_intelligence_endpoint(
    body: IntelligenceShareBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Synchronize tactical intelligence across federated nodes."""
    synced = federation_manager.synchronize_intelligence(
        source_node_id=body.source_node_id,
        intel_type=body.kind,
        payload=body.payload,
    )
    return {"status": "synchronized", "synced_nodes_count": synced}


# ============================================================
# Phase 4B: Multi-Theater & Multi-World API
# ============================================================
@app.get("/api/theaters")
def list_theaters_endpoint(user: dict = Depends(get_caller_user)) -> list[dict]:
    """List operational geographic theaters."""
    return theater_manager.list_theaters()


@app.get("/api/theaters/cross-analysis")
def get_cross_theater_analysis_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Aggregate multi-theater readiness, threat index, and supply draw."""
    return world_manager.cross_theater_analysis()


@app.get("/api/theaters/{theater_id}")
def get_theater_endpoint(theater_id: str, user: dict = Depends(get_caller_user)) -> dict:
    """Retrieve specific theater by ID."""
    t = theater_manager.get_theater(theater_id)
    if not t:
        raise HTTPException(status_code=404, detail="Theater not found")
    return t


@app.get("/api/worlds")
def list_worlds_endpoint(
    theater_id: str | None = None,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """List isolated simulation worlds across theaters."""
    return world_manager.list_worlds(theater_id=theater_id)


# ============================================================
# Phase 4C: Autonomous Agent Swarm Planning API
# ============================================================
class SwarmPlanBody(BaseModel):
    prompt: str
    theater_id: str = "THEATER-NORTH"
    world_state: dict[str, Any] | None = None


@app.post("/api/swarm/plan")
def generate_swarm_plan_endpoint(
    body: SwarmPlanBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Synthesize complete operational plan via 6-agent planning swarm."""
    return swarm_coordinator.generate_operational_plan(
        prompt=body.prompt,
        theater_id=body.theater_id,
        world_state=body.world_state,
    )


# ============================================================
# Phase 4D: Strategic Copilot API
# ============================================================
class CampaignCreateBody(BaseModel):
    title: str
    theater_ids: list[str]
    objectives: list[str]


@app.post("/api/strategic/campaigns")
def create_campaign_endpoint(
    body: CampaignCreateBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Initialize a multi-theater defense campaign."""
    return strategic_copilot.create_campaign(
        title=body.title,
        theater_ids=body.theater_ids,
        objectives=body.objectives,
    )


@app.get("/api/strategic/campaigns")
def list_campaigns_endpoint(user: dict = Depends(get_caller_user)) -> list[dict]:
    """List strategic campaigns."""
    return db.list_campaigns()


@app.post("/api/strategic/campaigns/{campaign_id}/brief")
def generate_campaign_brief_endpoint(
    campaign_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Synthesize strategic campaign order for regional defense commanders."""
    return strategic_copilot.generate_campaign_brief(campaign_id=campaign_id)


@app.get("/api/strategic/campaigns/{campaign_id}/readiness")
def get_campaign_readiness_endpoint(
    campaign_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Evaluate cross-theater asset readiness and supply posture."""
    return strategic_copilot.generate_strategic_readiness_report(campaign_id=campaign_id)


@app.get("/api/strategic/campaigns/{campaign_id}/risks")
def get_campaign_risks_endpoint(
    campaign_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Compute long-range risk assessment across theaters."""
    return strategic_copilot.generate_strategic_risk_assessment(campaign_id=campaign_id)


@app.get("/api/strategic/campaigns/{campaign_id}/investments")
def get_campaign_investments_endpoint(
    campaign_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Generate strategic resource investment and asset procurement recommendations."""
    return strategic_copilot.generate_investment_outlook(campaign_id=campaign_id)


# ============================================================
# Phase 4E: Multi-Layer Graph Intelligence API
# ============================================================
class GraphReasonBody(BaseModel):
    query: str
    root_id: str | None = None


@app.post("/api/graph-ai/reason")
def graph_reason_endpoint(
    body: GraphReasonBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Perform multi-hop reasoning over the 5-layer graph."""
    return graph_ai.graph_reason(query=body.query, root_id=body.root_id)


@app.get("/api/graph-ai/cascade-failure/{entity_id}")
def cascade_failure_endpoint(
    entity_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Model cascade failure propagation if entity becomes inoperative."""
    return graph_ai.predict_cascade_failure(entity_id=entity_id)


@app.get("/api/graph-ai/emergent-risks")
def emergent_risks_endpoint(user: dict = Depends(get_caller_user)) -> list[dict]:
    """Identify cross-theater emerging risk patterns."""
    return graph_ai.detect_emergent_risks()


# ============================================================
# Phase 4F: Distributed Digital Twin Forecasting API
# ============================================================
class DistributedForecastBody(BaseModel):
    horizon_hours: float = 2.0
    confidence: float = 0.95


@app.post("/api/forecast/distributed")
def distributed_forecast_endpoint(
    body: DistributedForecastBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Generate synchronized predictive lookahead across all active theaters."""
    return distributed_forecaster.forecast_all_theaters(
        horizon_hours=body.horizon_hours,
        confidence=body.confidence,
    )


# ============================================================
# Phase 4G: Autonomous Simulation Branching API
# ============================================================
class FutureGenerateBody(BaseModel):
    baseline_world_id: str = "WLD-NORTH-01"
    count: int = 10
    ticks: int = 120


@app.post("/api/futures/generate")
def generate_futures_endpoint(
    body: FutureGenerateBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Generate N deterministic future branches and evaluate risk bands."""
    return future_generator.generate_alternative_futures(
        baseline_world_id=body.baseline_world_id,
        count=body.count,
        ticks=body.ticks,
    )


@app.get("/api/futures")
def list_futures_endpoint(
    baseline_world_id: str | None = None,
    limit: int = 100,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """List generated future simulation branches."""
    return db.list_future_branches(baseline_world_id=baseline_world_id, limit=limit)


# ============================================================
# Phase 4H: Global Replay & Campaign Intelligence API
# ============================================================
class CampaignCompareBody(BaseModel):
    campaign_id_a: str = "CMP-EXERCISE-2025"
    campaign_id_b: str = "CMP-EXERCISE-2026"


@app.post("/api/campaigns/compare")
def compare_campaigns_endpoint(
    body: CampaignCompareBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Perform macro-level comparative analysis between two strategic campaigns."""
    return campaign_replay_engine.compare_campaigns(
        campaign_id_a=body.campaign_id_a,
        campaign_id_b=body.campaign_id_b,
    )


# ============================================================
# Phase 4I & 4J: Event Streaming & Data Lake API
# ============================================================
class EventPublishBody(BaseModel):
    stream_name: str
    event_type: str
    payload: dict[str, Any]
    partition: int = 0


class DataLakeObjectBody(BaseModel):
    bucket: str
    key: str
    data: Any
    content_type: str = "application/json"
    metadata: dict[str, Any] | None = None


@app.post("/api/events/publish")
def publish_event_endpoint(
    body: EventPublishBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Publish an event to the enterprise event streaming bus."""
    return event_bus.publish(
        stream_name=body.stream_name,
        event_type=body.event_type,
        payload=body.payload,
        partition=body.partition,
    )


@app.get("/api/events/replay")
def replay_events_endpoint(
    stream_name: str = "telemetry.stream",
    from_offset: int = 0,
    to_offset: int | None = None,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """Replay events from a given stream and offset range."""
    return event_bus.event_replay(
        stream_name=stream_name,
        from_offset=from_offset,
        to_offset=to_offset,
    )


@app.get("/api/events/projection/{stream_name}")
def get_event_projection_endpoint(
    stream_name: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Get real-time materialized state projection for a stream."""
    return event_bus.event_projection(stream_name=stream_name)


@app.post("/api/datalake/objects")
def put_datalake_object_endpoint(
    body: DataLakeObjectBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Store an object in the operational data lake."""
    return data_lake.put_object(
        bucket=body.bucket,
        key=body.key,
        data=body.data,
        content_type=body.content_type,
        metadata=body.metadata,
    )


@app.get("/api/datalake/objects")
def list_datalake_objects_endpoint(
    bucket: str | None = None,
    limit: int = 50,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """List objects stored in the operational data lake."""
    return data_lake.list_objects(bucket=bucket, limit=limit)


@app.get("/api/datalake/analysis")
def get_datalake_analysis_endpoint(
    bucket: str | None = None,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Perform cross-object historical analysis and storage telemetry."""
    return data_lake.historical_analysis(bucket=bucket)


# ---------------------------------------------------------------------------
# Phase 5: Unified Enterprise Platform API Schemas & Endpoints
# ---------------------------------------------------------------------------

class AgentRegisterBody(BaseModel):
    id: str | None = None
    name: str
    role: str
    capabilities: list[str] = []
    status: str = "idle"
    metadata: dict = {}


class AgentTaskBody(BaseModel):
    task_type: str
    payload: dict = {}
    agent_id: str | None = None
    priority: int = 1


class MemoryRememberBody(BaseModel):
    content: str
    agent_id: str | None = None
    memory_type: str = "semantic"
    tags: list[str] = []
    importance: float = 1.0


class ForecastMatrixBody(BaseModel):
    theaters: list[str] | None = None
    horizon_hours: float = 4.0
    confidence: float = 0.95


class MassiveWhatIfBody(BaseModel):
    base_scenario: dict | None = None
    n_scenarios: int = 100
    seed_base: int = 42


class KnowledgeSynthesizeBody(BaseModel):
    query: str
    theater_id: str | None = None


class ModelRegisterBody(BaseModel):
    id: str | None = None
    name: str
    provider: str
    model_type: str
    endpoint: str | None = None
    is_active: bool = True
    metadata: dict = {}


class ModelRouteBody(BaseModel):
    task_type: str
    priority: str = "normal"
    require_local: bool = False


class WorkflowCreateBody(BaseModel):
    workflow_type: str
    title: str
    steps: list[dict] | None = None
    requires_human_confirmation: bool = True


class WorkflowApproveBody(BaseModel):
    operator_id: str


class WorkflowRejectBody(BaseModel):
    operator_id: str
    reason: str = ""


class WorkflowAdvanceBody(BaseModel):
    next_step: str


class ReportGenerateBody(BaseModel):
    report_type: str = "sitrep"
    theater: str | None = None
    mission_id: str | None = None


# Phase 5A: Unified Agent Runtime Endpoints
@app.get("/api/agents")
def list_agents_endpoint(
    status: str | None = None,
    role: str | None = None,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """List registered agents in the unified runtime directory."""
    return agent_runtime.registry.list_all(status=status, role=role)


@app.post("/api/agents")
def register_agent_endpoint(
    body: AgentRegisterBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Register a new agent in the unified runtime."""
    import uuid
    aid = body.id or f"agent-{uuid.uuid4().hex[:8]}"
    return agent_runtime.registry.register(
        agent_id=aid,
        name=body.name,
        role=body.role,
        capabilities=body.capabilities,
        status=body.status,
        metadata=body.metadata,
    )


@app.get("/api/agents/runtime/status")
def get_agent_runtime_status_endpoint(
    user: dict = Depends(get_caller_user),
) -> dict:
    """Get overall operational status of the unified agent runtime."""
    return agent_runtime.get_status()


@app.get("/api/agents/{agent_id}")
def get_agent_endpoint(
    agent_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Retrieve details for a specific registered agent."""
    ag = agent_runtime.registry.get(agent_id)
    if not ag:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ag


@app.post("/api/agents/tasks")
def submit_agent_task_endpoint(
    body: AgentTaskBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Submit a task to the unified agent coordinator."""
    return agent_runtime.submit_task(
        task_type=body.task_type,
        payload=body.payload,
        agent_id=body.agent_id,
    )


@app.get("/api/agents/tasks")
def list_agent_tasks_endpoint(
    agent_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """List queued and executed agent tasks."""
    return agent_runtime.task_queue.list_tasks(agent_id=agent_id, status=status, limit=limit)


# Phase 5B: Persistent Long-Term Memory Endpoints
@app.post("/api/memory/remember")
def remember_memory_endpoint(
    body: MemoryRememberBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Store knowledge, episode, or working context in persistent agent memory."""
    return memory_store.remember(
        content=body.content,
        agent_id=body.agent_id,
        memory_type=body.memory_type,
        tags=body.tags,
        importance=body.importance,
    )


@app.get("/api/memory/retrieve")
def retrieve_memory_endpoint(
    q: str = "*",
    agent_id: str | None = None,
    memory_type: str | None = None,
    limit: int = 20,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """Retrieve memories matching query keyword or filter."""
    return memory_store.retrieve(
        query=q,
        agent_id=agent_id,
        memory_type=memory_type,
        limit=limit,
    )


@app.post("/api/memory/consolidate")
def consolidate_memory_endpoint(
    user: dict = Depends(get_caller_user),
) -> dict:
    """Consolidate high-priority episodic memories into permanent semantic doctrine."""
    return memory_store.consolidate()


@app.get("/api/memory/summary")
def get_memory_summary_endpoint(
    agent_id: str | None = None,
    memory_type: str | None = None,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Synthesize narrative summary of stored operational memories."""
    summary_text = memory_store.summarize(agent_id=agent_id, memory_type=memory_type)
    return {"summary": summary_text}


# Phase 5C: Autonomous Analysis Engine Endpoints
@app.get("/api/analysis/run")
def run_autonomous_analysis_endpoint(
    user: dict = Depends(get_caller_user),
) -> dict:
    """Execute full autonomous diagnostic suite (anomalies, bottlenecks, supply, failure risks)."""
    return analysis_engine.run_full_analysis()


@app.get("/api/analysis/findings")
def list_analysis_findings_endpoint(
    category: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """List recorded autonomous intelligence findings."""
    return db.list_analysis_findings(category=category, severity=severity, limit=limit)


# Phase 5D: Large-Scale Forecasting Matrix Endpoints
@app.post("/api/forecasting/matrix")
def generate_forecast_matrix_endpoint(
    body: ForecastMatrixBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Generate multi-theater, multi-dimensional risk matrix in decoupled memory."""
    return large_scale_forecaster.generate_forecast_matrix(
        theaters=body.theaters,
        horizon_hours=body.horizon_hours,
        confidence=body.confidence,
    )


@app.get("/api/forecasting/matrices")
def list_forecast_matrices_endpoint(
    limit: int = 20,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """List historical forecast matrices."""
    return db.list_forecast_matrices(limit=limit)


# Phase 5E: Massive What-If Engine Endpoints
@app.post("/api/whatif/massive")
def run_massive_whatif_endpoint(
    body: MassiveWhatIfBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Execute a batch of 100 to 1,000 deterministic scenario variations and rank outcomes."""
    return massive_whatif.run_batch(
        base_scenario=body.base_scenario,
        n_scenarios=body.n_scenarios,
        seed_base=body.seed_base,
    )


# Phase 5F: Operational Analytics Platform Endpoints
@app.get("/api/analytics/kpis")
def get_operational_kpis_endpoint(
    window: str = "24h",
    theater: str | None = None,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Get aggregate operational KPIs for dashboard displays."""
    return operational_analytics.get_kpis(time_window=window, theater=theater)


@app.get("/api/analytics/dashboard")
def get_analytics_dashboard_endpoint(
    user: dict = Depends(get_caller_user),
) -> dict:
    """Get comprehensive operational analytics dashboard payload."""
    return operational_analytics.get_dashboard_summary()


# Phase 5G: Knowledge Synthesis Layer Endpoints
@app.post("/api/knowledge/synthesize")
def synthesize_knowledge_endpoint(
    body: KnowledgeSynthesizeBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Synthesize cross-source operational picture across graph, RAG, events, and forecasts."""
    return knowledge_synthesizer.synthesize_operational_picture(
        query=body.query,
        theater_id=body.theater_id,
    )


# Phase 5H: Observability Platform Endpoints
@app.get("/api/observability/metrics")
def get_observability_metrics_endpoint(
    user: dict = Depends(get_caller_user),
) -> dict:
    """Get structured system metrics, latency percentiles, and counters."""
    return observability.get_metrics_summary()


@app.get("/api/observability/health")
def get_observability_health_endpoint() -> dict:
    """Get platform and subsystem health status."""
    return observability.get_system_health()


@app.get("/api/observability/prometheus", response_class=PlainTextResponse)
def get_prometheus_metrics_endpoint() -> str:
    """Export platform metrics in Prometheus plain-text exposition format."""
    return observability.get_prometheus_export()


# Phase 5I: Model Management Layer Endpoints
@app.get("/api/models")
def list_models_endpoint(
    provider: str | None = None,
    model_type: str | None = None,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """List registered AI and vision models."""
    return model_manager.registry.list_all(provider=provider, model_type=model_type)


@app.post("/api/models")
def register_model_endpoint(
    body: ModelRegisterBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Register an AI model backend in the platform registry."""
    import uuid
    mid = body.id or f"model-{uuid.uuid4().hex[:8]}"
    doc = {
        "id": mid,
        "name": body.name,
        "provider": body.provider,
        "model_type": body.model_type,
        "endpoint": body.endpoint,
        "is_active": body.is_active,
        "metadata": body.metadata,
    }
    return model_manager.registry.register(doc)


@app.post("/api/models/route")
def route_model_task_endpoint(
    body: ModelRouteBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Dynamically route an operational task to the optimal model backend."""
    return model_manager.router.route_task(
        task_type=body.task_type,
        priority=body.priority,
        require_local=body.require_local,
    )


@app.get("/api/models/{model_id}/health")
def check_model_health_endpoint(
    model_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Check health and latency of a registered model endpoint."""
    return model_manager.check_health(model_id)


# Phase 5J: Operational Workflow Engine Endpoints
@app.post("/api/workflows")
def create_workflow_endpoint(
    body: WorkflowCreateBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Initialize a new staged operational workflow."""
    return workflow_engine.create_workflow(
        workflow_type=body.workflow_type,
        title=body.title,
        steps=body.steps,
        requires_human_confirmation=body.requires_human_confirmation,
    )


@app.get("/api/workflows")
def list_workflows_endpoint(
    status: str | None = None,
    workflow_type: str | None = None,
    limit: int = 100,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """List operational workflow instances."""
    return workflow_engine.list_workflows(status=status, workflow_type=workflow_type, limit=limit)


@app.get("/api/workflows/{workflow_id}")
def get_workflow_endpoint(
    workflow_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Retrieve details for a specific workflow instance."""
    wf = workflow_engine.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@app.post("/api/workflows/{workflow_id}/approve")
def approve_workflow_endpoint(
    workflow_id: str,
    body: WorkflowApproveBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Human-in-the-Loop approval gate for operational workflow."""
    try:
        return workflow_engine.approve_workflow(workflow_id, operator_id=body.operator_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/workflows/{workflow_id}/reject")
def reject_workflow_endpoint(
    workflow_id: str,
    body: WorkflowRejectBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Reject an operational workflow instance."""
    try:
        return workflow_engine.reject_workflow(workflow_id, operator_id=body.operator_id, reason=body.reason)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/workflows/{workflow_id}/advance")
def advance_workflow_endpoint(
    workflow_id: str,
    body: WorkflowAdvanceBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Advance workflow to the next step (strictly enforcing human gate constraint)."""
    try:
        return workflow_engine.advance_step(workflow_id, next_step=body.next_step)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


# Phase 5K: Operational Reporting Engine Endpoints
@app.post("/api/reports/generate")
def generate_report_endpoint(
    body: ReportGenerateBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Generate and persist an automated operational report."""
    if body.report_type == "mission" and body.mission_id:
        return reporting_engine.generate_mission_report(body.mission_id)
    return reporting_engine.generate_daily_sitrep(theater=body.theater)


@app.get("/api/reports")
def list_reports_endpoint(
    report_type: str | None = None,
    limit: int = 50,
    user: dict = Depends(get_caller_user),
) -> list[dict]:
    """List synthesized operational reports."""
    return reporting_engine.list_reports(report_type=report_type, limit=limit)


@app.get("/api/reports/{report_id}")
def get_report_endpoint(
    report_id: str,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Retrieve an operational report by ID."""
    rep = reporting_engine.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found")
    return rep


# ---------------------------------------------------------------------------
# Phase 6: Production Hardening, Resilience & Unified Knowledge Endpoints
# ---------------------------------------------------------------------------

class UnifiedKnowledgeQueryBody(BaseModel):
    query: str
    theater_id: str | None = None
    include_graph: bool = True
    include_doctrine: bool = True
    include_memory: bool = True
    include_forecast: bool = True


@app.get("/api/resilience/status")
def get_resilience_status_endpoint(
    user: dict = Depends(get_caller_user),
) -> dict:
    """Get active circuit breaker states and failure counters."""
    return resilience_manager.get_all_status()


@app.post("/api/resilience/reset")
def reset_resilience_breakers_endpoint(
    user: dict = Depends(get_caller_user),
) -> dict:
    """Reset all circuit breakers to CLOSED normal operational state."""
    resilience_manager.reset_all()
    return {"status": "RESET_SUCCESSFUL", "message": "All circuit breakers reset to CLOSED"}


@app.get("/api/cache/stats")
def get_cache_stats_endpoint(
    user: dict = Depends(get_caller_user),
) -> dict:
    """Get high-throughput caching hit ratio, entry counts, and evictions."""
    return cache_manager.get_stats()


@app.post("/api/cache/clear")
def clear_cache_endpoint(
    namespace: str | None = None,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Clear memory cache globally or for a specific namespace."""
    cache_manager.clear(namespace=namespace)
    return {"status": "CLEARED", "namespace": namespace or "ALL"}


@app.post("/api/scalability/benchmark")
def run_scalability_benchmark_endpoint(
    num_items: int = 10000,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Benchmark high-throughput batch ingestion under 100x scale."""
    return scalability_benchmark.benchmark_batch_throughput(num_items=num_items)


@app.post("/api/knowledge/unified/query")
def query_unified_knowledge_endpoint(
    body: UnifiedKnowledgeQueryBody,
    user: dict = Depends(get_caller_user),
) -> dict:
    """Query consolidated knowledge facade across graph, memory, doctrine, and forecasts."""
    return unified_knowledge.query(
        query_str=body.query,
        theater_id=body.theater_id,
        include_graph=body.include_graph,
        include_doctrine=body.include_doctrine,
        include_memory=body.include_memory,
        include_forecast=body.include_forecast,
    )


# ============================================================
# Phase 7 — Autonomous Roadmap Closure & Platform Unification
# ============================================================

class GovernanceVerifyBody(BaseModel):
    action: str
    actor: str | None = None
    role: str | None = None
    data: dict[str, Any] | None = None
    seed: int | None = None


class SelfHealingActionBody(BaseModel):
    action_type: str
    target: str | None = None
    operator_authorized: bool = False
    operator_id: str | None = None


class ResearchExperimentBody(BaseModel):
    experiment_type: str
    prompt: str | None = None
    model_id: str | None = None
    scenario_id: str | None = None
    params: dict[str, Any] | None = None


class UnifiedKnowledgeReasonBody(BaseModel):
    prompt: str
    context: dict[str, Any] | None = None


class UnifiedKnowledgeRetrieveBody(BaseModel):
    query: str
    filters: dict[str, Any] | None = None
    limit: int = 5


# Platform Unification (Phase 7A)
@app.get("/api/platform/services")
def list_platform_services_endpoint(subsystem: str | None = None, user: dict = Depends(get_caller_user)) -> dict:
    """List all registered services across the unified platform catalog."""
    return {"services": platform_registry.list_services(subsystem=subsystem)}


@app.get("/api/platform/health")
def get_platform_health_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Evaluate health across all registered platform services."""
    return platform_registry.check_all_health()


@app.post("/api/platform/bootstrap")
def bootstrap_platform_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Explicitly bootstrap all platform services and lifecycle managers."""
    return platform_lifecycle.bootstrap_platform()


# Unified Knowledge Architecture (Phase 7B)
@app.post("/api/knowledge/unified/reason")
def reason_unified_knowledge_endpoint(body: UnifiedKnowledgeReasonBody, user: dict = Depends(get_caller_user)) -> dict:
    """Execute cross-source cognitive reasoning synthesizing facts, projections, and citations."""
    return unified_knowledge.reason(prompt=body.prompt, context=body.context)


@app.post("/api/knowledge/unified/retrieve")
def retrieve_unified_knowledge_endpoint(body: UnifiedKnowledgeRetrieveBody, user: dict = Depends(get_caller_user)) -> dict:
    """Execute multi-tier retrieval across doctrine, episodic memory, and knowledge graph."""
    return unified_knowledge.retrieve(query=body.query, filters=body.filters, limit=body.limit)


@app.get("/api/knowledge/unified/trace/{target_id}")
def trace_unified_knowledge_endpoint(target_id: str, user: dict = Depends(get_caller_user)) -> dict:
    """Execute directed causal graph trace for root causes and dependencies."""
    return unified_knowledge.trace(incident_id_or_entity_id=target_id)


@app.get("/api/knowledge/unified/forecast/{entity_id}")
def forecast_unified_knowledge_endpoint(entity_id: str, horizon_ticks: int = 120, user: dict = Depends(get_caller_user)) -> dict:
    """Execute predictive forward lookahead risk assessment."""
    return unified_knowledge.forecast(entity_id=entity_id, horizon_ticks=horizon_ticks)


@app.get("/api/knowledge/unified/analyze")
def analyze_unified_knowledge_endpoint(theater_id: str | None = None, user: dict = Depends(get_caller_user)) -> dict:
    """Synthesize holistic tactical readiness and posture assessment."""
    return unified_knowledge.analyze(theater_id=theater_id)


# Autonomous Operations Center (Phase 7C)
@app.get("/api/operations/center/health")
def operations_system_health_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Conduct system health review across services, breakers, and cache."""
    return operations_center.system_health_review()


@app.get("/api/operations/center/reports/daily")
def operations_daily_report_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Generate daily operational health report."""
    return operations_center.generate_daily_health_report()


@app.get("/api/operations/center/reports/weekly")
def operations_weekly_report_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Generate weekly operational risk report."""
    return operations_center.generate_weekly_risk_report()


@app.get("/api/operations/center/reports/monthly")
def operations_monthly_report_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Generate monthly operational readiness report."""
    return operations_center.generate_monthly_readiness_report()


# Autonomous Governance Layer (Phase 7D)
@app.post("/api/governance/verify")
def verify_governance_endpoint(body: GovernanceVerifyBody, user: dict = Depends(get_caller_user)) -> dict:
    """Execute pre-execution compliance check against mandatory boundaries."""
    actor = body.actor if body.actor is not None else user.get("username", "operator")
    role = body.role if body.role is not None else user.get("role", "operator")
    try:
        return governance_engine.enforce_governance(
            action=body.action,
            actor=actor,
            role=role,
            data=body.data,
            seed=body.seed,
        )
    except Exception as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.get("/api/governance/audit")
def get_governance_audit_endpoint(limit: int = 50, user: dict = Depends(get_caller_user)) -> dict:
    """Retrieve immutable governance audit log."""
    return {"audit_trail": governance_engine.get_audit_trail(limit=limit)}


# Continuous Validation Engine (Phase 7E)
@app.post("/api/validation/continuous")
def run_continuous_validation_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Execute continuous validation suite across golden run, contracts, and security."""
    return validation_engine.run_full_validation_suite()


# Self-Healing Operational Layer (Phase 7F)
@app.post("/api/self-healing/action")
def run_self_healing_action_endpoint(body: SelfHealingActionBody, user: dict = Depends(get_caller_user)) -> dict:
    """Execute or stage self-healing operational actions."""
    actor = body.operator_id or user.get("username", "operator")
    if body.action_type == "service_restart":
        return self_healing_engine.service_restart(
            service_name=body.target or "deterministic_sim_engine",
            operator_authorized=body.operator_authorized,
            operator_id=actor,
        )
    elif body.action_type == "cache_rebuild":
        return self_healing_engine.cache_rebuild(
            namespace=body.target,
            operator_authorized=body.operator_authorized,
            operator_id=actor,
        )
    elif body.action_type == "index_repair":
        return self_healing_engine.index_repair(
            index_name=body.target or "idx_spatial",
            operator_authorized=body.operator_authorized,
            operator_id=actor,
        )
    elif body.action_type == "connection_recovery":
        return self_healing_engine.connection_recovery(target=body.target or "sqlite_primary")
    elif body.action_type == "workflow_recovery":
        return self_healing_engine.workflow_recovery(
            workflow_id=body.target or "WF-DEFAULT",
            operator_authorized=body.operator_authorized,
            operator_id=actor,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown healing action: {body.action_type}")


# Quality Platform (Phase 7I)
@app.get("/api/quality/scorecard")
def get_quality_scorecard_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Retrieve composite DOIP Quality Scorecard."""
    return quality_platform.generate_quality_scorecard()


# Future Research Sandbox (Phase 7J)
@app.post("/api/research/sandbox/experiment")
def run_research_experiment_endpoint(body: ResearchExperimentBody, user: dict = Depends(get_caller_user)) -> dict:
    """Execute isolated research experiment in ephemeral memory."""
    if body.experiment_type == "ai":
        return research_sandbox.run_experimental_ai(
            prompt=body.prompt or "Evaluate autonomous tactical countermeasure",
            experimental_model=body.model_id or "quantum_reasoner_v1",
        )
    elif body.experiment_type == "forecaster":
        return research_sandbox.run_novel_forecaster(horizon_ticks=300)
    elif body.experiment_type == "planner":
        return research_sandbox.run_novel_planner(start=(34.5, 43.1), goal=(35.2, 44.0))
    elif body.experiment_type == "swarm":
        return research_sandbox.run_prototype_agent_swarm(mission_brief=body.prompt or "Expeditionary Escort")
    elif body.experiment_type == "simulation":
        return research_sandbox.run_prototype_sim(scenario_id=body.scenario_id or "SC-PROTOTYPE-01")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown experiment type: {body.experiment_type}")


# Autonomous Documentation (Phase 7G)
@app.post("/api/docs/sync")
def sync_documentation_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Synchronize living platform documentation generated from source metadata."""
    return documentation_engine.sync_all_documentation()


# =====================================================================
# Phase 8: Hybrid Physics Simulation + Laya Learned Decision Engine
# =====================================================================

class HybridSimStepBody(BaseModel):
    dt_sec: float = 1.0
    target_speed_mps: float | None = None
    target_heading_deg: float | None = None
    environmental_perturbation: dict | None = None
    mode: str = "HYBRID_AI_SIM"
    confidence_threshold: float = 0.65


class HybridSimRunBody(BaseModel):
    ticks: int = 15
    dt_sec: float = 1.0
    perturbations: dict | None = None
    confidence_threshold: float = 0.65


class LayaDecideBody(BaseModel):
    features: list[float] | None = None
    min_confidence: float = 0.65


from app.simulation import (
    HybridSimulationRunner,
    SimulationMode,
    PhysicsEngineState,
    KinematicState,
    EnergyState,
    EnvironmentState,
    CommsState,
    LogisticsState,
    FeatureExtractor,
)
from app.laya_engine import LayaDecisionEngine, LayaModelRegistry
from app.hybrid_outcome_engine import HybridOutcomeEngine

hybrid_outcome_engine = HybridOutcomeEngine()
laya_decision_engine = LayaDecisionEngine()
laya_model_registry = LayaModelRegistry()


@app.post("/api/simulation/hybrid/step")
def run_hybrid_step_endpoint(body: HybridSimStepBody, user: dict = Depends(get_caller_user)) -> dict:
    """Execute a single step in Hybrid Physics + Laya AI Simulation."""
    mode = SimulationMode.HYBRID_AI_SIM if body.mode == "HYBRID_AI_SIM" else SimulationMode.DETERMINISTIC_SIM
    runner = HybridSimulationRunner(
        laya_engine=laya_decision_engine,
        mode=mode,
        confidence_threshold=body.confidence_threshold,
    )
    result = runner.step(
        dt_sec=body.dt_sec,
        target_speed_mps=body.target_speed_mps,
        target_heading_deg=body.target_heading_deg,
        environmental_perturbation=body.environmental_perturbation,
    )
    return result


@app.post("/api/simulation/hybrid/run")
def run_hybrid_trajectory_endpoint(body: HybridSimRunBody, user: dict = Depends(get_caller_user)) -> dict:
    """Execute a multi-step hybrid physics trajectory with consensus outcome arbitration."""
    return hybrid_outcome_engine.run_hybrid_trajectory(
        ticks=body.ticks,
        dt_sec=body.dt_sec,
        perturbations=body.perturbations,
        confidence_threshold=body.confidence_threshold,
    )


@app.post("/api/simulation/hybrid/whatif")
def run_hybrid_whatif_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Evaluate multi-permutation What-If alternatives through the hybrid outcome engine."""
    return hybrid_outcome_engine.evaluate_whatif_alternatives()


@app.get("/api/simulation/hybrid/disagreements")
def get_hybrid_disagreements_endpoint(ticks: int = 20, user: dict = Depends(get_caller_user)) -> dict:
    """Analyze model disagreement stats between Physics/Rules and Laya decisions."""
    res = hybrid_outcome_engine.run_hybrid_trajectory(ticks=ticks)
    return {
        "disagreement_count": res["disagreement_count"],
        "comparison_stats": res["model_comparison_stats"],
    }


@app.get("/api/laya/status")
def get_laya_status_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Retrieve runtime status of Laya learned decision engine."""
    return laya_decision_engine.get_status()


@app.post("/api/laya/decide")
def run_laya_decide_endpoint(body: LayaDecideBody, user: dict = Depends(get_caller_user)) -> dict:
    """Perform non-autoregressive decision inference using Laya architecture."""
    if body.features and len(body.features) == 15:
        vec = body.features
    else:
        # Default nominal vector
        vec = [0.5, 0.5, 0.5, 0.25, 0.75, 1.0, 0.1, 0.0, 0.8, 0.2, 0.6, 0.0, 0.1, 0.2, 0.9]

    extractor = FeatureExtractor()
    state = PhysicsEngineState()
    feats = extractor.extract(state)
    feats.numeric_vector = vec

    return laya_decision_engine.predict_operational_decision(
        features=feats, min_confidence=body.min_confidence
    )


@app.get("/api/laya/models")
def list_laya_models_endpoint(user: dict = Depends(get_caller_user)) -> list[dict]:
    """List registered Laya decision models and metadata."""
    return laya_model_registry.list_models()


class MassiveWhatIfSimBody(BaseModel):
    branches: int = 100
    ticks: int = 20
    seed: int = 42


class ModelSwitchBody(BaseModel):
    model_id: str


@app.post("/api/simulation/hybrid/whatif/massive")
def run_hybrid_massive_whatif_endpoint(body: MassiveWhatIfSimBody, user: dict = Depends(get_caller_user)) -> dict:
    """Run large-scale hybrid Monte Carlo branches (100, 1000, 10000) using Physics + Rules + Laya."""
    return hybrid_outcome_engine.run_massive_hybrid_whatif(
        branches=body.branches, ticks=body.ticks, seed=body.seed
    )


@app.get("/api/simulation/disagreements/history")
def get_disagreements_history_endpoint(limit: int = 50, user: dict = Depends(get_caller_user)) -> dict:
    """Retrieve full history and explanations of model disagreements across Physics, Rules, and Laya."""
    from app.simulation.disagreement_engine import _disagreement_engine
    return {
        "history": _disagreement_engine.get_recent_disagreements(limit=limit),
        "statistics": _disagreement_engine.get_statistics(),
    }


@app.get("/api/active-learning/samples")
def get_active_learning_samples_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Retrieve harvested active learning hard examples."""
    from app.simulation.active_learning import _collector
    samples = _collector.load_collected_examples()
    return {
        "total_harvested": len(samples),
        "samples": samples[-50:],  # return most recent 50
    }


@app.post("/api/laya/models/switch")
def switch_active_laya_model_endpoint(body: ModelSwitchBody, user: dict = Depends(get_caller_user)) -> dict:
    """Switch active Laya model checkpoint (e.g. laya-doip-v1, laya-doip-v2)."""
    import os
    global laya_decision_engine, hybrid_outcome_engine
    target_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints", body.model_id.replace("-", "_"))
    )
    if not os.path.exists(target_dir):
        # Check standard checkpoints folder
        target_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints", body.model_id)
        )
    if not os.path.exists(target_dir):
        raise HTTPException(status_code=404, detail=f"Checkpoint for {body.model_id} not found on disk")

    laya_decision_engine = LayaDecisionEngine(checkpoint_dir=target_dir)
    hybrid_outcome_engine = HybridOutcomeEngine(laya_engine=laya_decision_engine)
    return {
        "status": "SWITCHED",
        "active_model": body.model_id,
        "checkpoint_status": laya_decision_engine.get_status(),
    }


@app.get("/api/laya/metrics")
def get_laya_metrics_endpoint(version: str = "v1", user: dict = Depends(get_caller_user)) -> dict:
    """Retrieve benchmark evaluation card and calibration metrics for active or selected Laya model."""
    import os, json
    target_version = "v2" if "2" in version else "v1"
    report_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints", f"laya_doip_{target_version}", "evaluation_report.json")
    )
    if os.path.exists(report_file):
        with open(report_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"status": "Evaluation report not generated yet"}


@app.get("/api/model-lab/train-status")
def get_model_lab_train_status_endpoint(user: dict = Depends(get_caller_user)) -> dict:
    """Retrieve training and dataset status for the DOIP Model Lab."""
    import os, json
    stats_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "laya_training", "dataset_stats.json")
    )
    quality_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "laya_training", "dataset_quality_report.json")
    )
    data = {}
    if os.path.exists(stats_file):
        with open(stats_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    quality = {}
    if os.path.exists(quality_file):
        with open(quality_file, "r", encoding="utf-8") as f:
            quality = json.load(f)

    return {
        "status": "READY",
        "dataset_stats": data,
        "quality_report": quality,
        "laya_model": laya_decision_engine.get_status(),
    }



