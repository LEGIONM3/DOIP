"""Persistence Layer for DOIP (Defense Operations Intelligence Platform).

Supports dual-mode execution:
  - Primary Production: PostgreSQL 16 + PostGIS via SQLAlchemy 2.0 ORM & Alembic.
  - Development Fallback: Zero-dependency SQLite persistence (doip.db).

Provides backward-compatible signatures for all existing routes in main.py, session.py,
whatif.py, aar.py, and new Phase 1 RAG/spatial querying.
"""

from __future__ import annotations

import datetime
import json
import logging
import math
import os
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

try:
    from .models import (
        AuditEvent,
        Base,
        CustomScenario,
        DoctrineChunk,
        DoctrineDocument,
        Mission,
        MissionTask,
        OptimizerRun,
        RedTeamScenario,
        Route,
        RouteSegment,
        Run,
        SimEvent,
        TacticalZone,
        User,
        WarRoomAssignment,
        WarRoomPresence,
        WarRoomTask,
        WarroomMessage,
        Waypoint,
        WhatIfResult,
        KnowledgeGraphNode,
        KnowledgeGraphEdge,
        ForecastRun,
        VisionDetection,
        VisionTrack,
        MissionCopilotSession,
        ReplayReport,
    )
except ImportError:
    from app.models import (
        AuditEvent,
        Base,
        CustomScenario,
        DoctrineChunk,
        DoctrineDocument,
        Mission,
        MissionTask,
        OptimizerRun,
        RedTeamScenario,
        Route,
        RouteSegment,
        Run,
        SimEvent,
        TacticalZone,
        User,
        WarRoomAssignment,
        WarRoomPresence,
        WarRoomTask,
        WarroomMessage,
        Waypoint,
        WhatIfResult,
        KnowledgeGraphNode,
        KnowledgeGraphEdge,
        ForecastRun,
        VisionDetection,
        VisionTrack,
        MissionCopilotSession,
        ReplayReport,
    )

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "doip.db"
_lock = threading.Lock()

# Environment settings
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")

_engine: Any = None
_SessionFactory: Any = None


def get_database_url() -> str:
    """Return effective database connection URL."""
    if DATABASE_URL:
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    return f"sqlite:///{DB_PATH}"


def get_engine() -> Any:
    """Return singleton SQLAlchemy Engine."""
    global _engine
    if _engine is None:
        url = get_database_url()
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    return _engine


def get_session() -> Session:
    """Provide a new SQLAlchemy session."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory()


def _sqlite_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        pass
    return conn


# ---------------------------------------------------------------------------
# Schema Initialization
# ---------------------------------------------------------------------------
def init() -> None:
    """Initialize database schemas and seed initial data.

    Idempotent and safe across reloads.
    """
    engine = get_engine()
    # Create all tables through SQLAlchemy metadata
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        log.warning("SQLAlchemy create_all notice: %s. Using SQLite fallback DDL.", exc)

    # Maintain SQLite backward-compatibility for raw queries
    with _lock, _sqlite_connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
              id          TEXT PRIMARY KEY,
              seed        INTEGER NOT NULL,
              scenario_id TEXT NOT NULL,
              ticks       INTEGER NOT NULL,
              events      INTEGER NOT NULL,
              log         TEXT NOT NULL,
              world_json  TEXT,
              created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS audit (
              id         INTEGER PRIMARY KEY AUTOINCREMENT,
              actor      TEXT NOT NULL,
              action     TEXT NOT NULL,
              detail     TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS audit_events (
              id         INTEGER PRIMARY KEY AUTOINCREMENT,
              actor      TEXT NOT NULL,
              action     TEXT NOT NULL,
              detail     TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS whatif_results (
              id              INTEGER PRIMARY KEY AUTOINCREMENT,
              seed            INTEGER NOT NULL,
              scenario_id     TEXT NOT NULL,
              ticks           INTEGER NOT NULL,
              actions_json    TEXT NOT NULL DEFAULT '[]',
              baseline_kpis   TEXT NOT NULL DEFAULT '{}',
              branch_kpis     TEXT NOT NULL DEFAULT '{}',
              deltas_json     TEXT NOT NULL DEFAULT '{}',
              score           REAL NOT NULL DEFAULT 0.0,
              created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS warroom_messages (
              id         INTEGER PRIMARY KEY AUTOINCREMENT,
              type       TEXT NOT NULL,
              payload    TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS users (
              id         INTEGER PRIMARY KEY AUTOINCREMENT,
              username   TEXT NOT NULL UNIQUE,
              name       TEXT,
              role       TEXT NOT NULL,
              unit       TEXT NOT NULL DEFAULT '',
              hashed_password TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS custom_scenarios (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              scenario_id TEXT NOT NULL UNIQUE,
              name        TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              config_json TEXT NOT NULL DEFAULT '{}',
              actions_json TEXT NOT NULL DEFAULT '[]',
              status      TEXT NOT NULL DEFAULT 'draft',
              author      TEXT NOT NULL DEFAULT '',
              created_at  TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS doctrine_documents (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              doc_id      TEXT NOT NULL UNIQUE,
              category    TEXT NOT NULL,
              title       TEXT NOT NULL,
              tags        TEXT NOT NULL DEFAULT '[]',
              version     TEXT NOT NULL DEFAULT '1.0',
              source_file TEXT NOT NULL,
              content     TEXT NOT NULL,
              created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS doctrine_chunks (
              id            INTEGER PRIMARY KEY AUTOINCREMENT,
              chunk_id      TEXT NOT NULL UNIQUE,
              document_id   TEXT NOT NULL,
              document_type TEXT NOT NULL,
              section       TEXT NOT NULL,
              source        TEXT NOT NULL,
              citation      TEXT NOT NULL,
              text          TEXT NOT NULL,
              token_count   INTEGER NOT NULL DEFAULT 0,
              embedding     TEXT,
              created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sim_events (
              id          TEXT PRIMARY KEY,
              run_id      TEXT NOT NULL,
              tick        INTEGER NOT NULL,
              event_type  TEXT NOT NULL,
              severity    TEXT NOT NULL DEFAULT 'low',
              entity_id   TEXT NOT NULL,
              lat         REAL,
              lon         REAL,
              payload     TEXT NOT NULL DEFAULT '{}',
              geom        TEXT,
              created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tactical_zones (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              zone_id     TEXT NOT NULL UNIQUE,
              name        TEXT NOT NULL,
              zone_type   TEXT NOT NULL,
              min_alt_m   REAL NOT NULL DEFAULT 0.0,
              max_alt_m   REAL NOT NULL DEFAULT 10000.0,
              active      INTEGER NOT NULL DEFAULT 1,
              coordinates_json TEXT NOT NULL DEFAULT '[]',
              geom        TEXT,
              created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
              id              TEXT PRIMARY KEY,
              entity_type     TEXT NOT NULL,
              label           TEXT NOT NULL,
              properties_json TEXT NOT NULL DEFAULT '{}',
              created_at      TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
              id              INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id       TEXT NOT NULL,
              target_id       TEXT NOT NULL,
              relation_type   TEXT NOT NULL,
              weight          REAL NOT NULL DEFAULT 1.0,
              properties_json TEXT NOT NULL DEFAULT '{}',
              created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS forecast_runs (
              id               TEXT PRIMARY KEY,
              scenario_id      TEXT NOT NULL,
              horizon_hours    REAL NOT NULL DEFAULT 2.0,
              confidence       REAL NOT NULL DEFAULT 0.95,
              ticks            INTEGER NOT NULL DEFAULT 120,
              predictions_json TEXT NOT NULL DEFAULT '{}',
              summary          TEXT NOT NULL DEFAULT '',
              created_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS vision_detections (
              id          TEXT PRIMARY KEY,
              frame_id    TEXT,
              tick        INTEGER NOT NULL DEFAULT 0,
              entity_id   TEXT NOT NULL DEFAULT '',
              class_label TEXT NOT NULL,
              confidence  REAL NOT NULL,
              box_x       REAL,
              box_y       REAL,
              box_w       REAL,
              box_h       REAL,
              lat         REAL,
              lon         REAL,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS vision_tracks (
              id             INTEGER PRIMARY KEY AUTOINCREMENT,
              track_id       TEXT NOT NULL,
              class_label    TEXT NOT NULL,
              frame_id       TEXT,
              tick           INTEGER NOT NULL DEFAULT 0,
              lat            REAL,
              lon            REAL,
              velocity_mps   REAL NOT NULL DEFAULT 0.0,
              heading_deg    REAL NOT NULL DEFAULT 0.0,
              activity_state TEXT NOT NULL DEFAULT 'nominal',
              history_json   TEXT NOT NULL DEFAULT '[]',
              metadata_json  TEXT NOT NULL DEFAULT '{}',
              created_at     TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS copilot_sessions (
              id             TEXT PRIMARY KEY,
              mission_id     TEXT,
              title          TEXT NOT NULL,
              messages_json  TEXT NOT NULL DEFAULT '[]',
              proposals_json TEXT NOT NULL DEFAULT '[]',
              status         TEXT NOT NULL DEFAULT 'active',
              approved_by    TEXT,
              created_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS replay_reports (
              id                  TEXT PRIMARY KEY,
              run_id              TEXT NOT NULL,
              comparison_run_id   TEXT,
              summary             TEXT NOT NULL DEFAULT '',
              turning_points_json TEXT NOT NULL DEFAULT '[]',
              kpi_deltas_json     TEXT NOT NULL DEFAULT '{}',
              created_at          TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS federation_nodes (
              id             TEXT PRIMARY KEY,
              name           TEXT NOT NULL,
              tier           TEXT NOT NULL DEFAULT 'tactical',
              region         TEXT NOT NULL DEFAULT 'GLOBAL',
              endpoint       TEXT NOT NULL DEFAULT '',
              status         TEXT NOT NULL DEFAULT 'online',
              heartbeat_at   TEXT NOT NULL DEFAULT (datetime('now')),
              metadata_json  TEXT NOT NULL DEFAULT '{}',
              created_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS theaters (
              id              TEXT PRIMARY KEY,
              name            TEXT NOT NULL,
              code            TEXT NOT NULL UNIQUE,
              bounds_json     TEXT NOT NULL DEFAULT '[]',
              active_world_id TEXT,
              status          TEXT NOT NULL DEFAULT 'active',
              created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS worlds (
              id                  TEXT PRIMARY KEY,
              theater_id          TEXT NOT NULL,
              name                TEXT NOT NULL,
              tick                INTEGER NOT NULL DEFAULT 0,
              status              TEXT NOT NULL DEFAULT 'running',
              state_snapshot_json TEXT NOT NULL DEFAULT '{}',
              created_at          TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS campaigns (
              id               TEXT PRIMARY KEY,
              title            TEXT NOT NULL,
              theater_ids_json TEXT NOT NULL DEFAULT '[]',
              status           TEXT NOT NULL DEFAULT 'draft',
              objectives_json  TEXT NOT NULL DEFAULT '[]',
              created_at       TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS strategic_reports (
              id              TEXT PRIMARY KEY,
              campaign_id     TEXT,
              title           TEXT NOT NULL,
              brief_text      TEXT NOT NULL DEFAULT '',
              readiness_score REAL NOT NULL DEFAULT 85.0,
              risk_score      REAL NOT NULL DEFAULT 25.0,
              outlook_json    TEXT NOT NULL DEFAULT '{}',
              created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS future_branches (
              id                TEXT PRIMARY KEY,
              baseline_world_id TEXT NOT NULL,
              branch_seed       INTEGER NOT NULL,
              ticks             INTEGER NOT NULL DEFAULT 120,
              outcome_rank      INTEGER NOT NULL DEFAULT 1,
              outcome_json      TEXT NOT NULL DEFAULT '{}',
              risk_band         TEXT NOT NULL DEFAULT 'P50',
              created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS event_streams (
              id           INTEGER PRIMARY KEY AUTOINCREMENT,
              stream_name  TEXT NOT NULL,
              offset       INTEGER NOT NULL,
              partition    INTEGER NOT NULL DEFAULT 0,
              event_type   TEXT NOT NULL,
              payload_json TEXT NOT NULL DEFAULT '{}',
              created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS data_lake_objects (
              id            TEXT PRIMARY KEY,
              bucket        TEXT NOT NULL,
              key           TEXT NOT NULL,
              content_type  TEXT NOT NULL DEFAULT 'application/json',
              size_bytes    INTEGER NOT NULL DEFAULT 0,
              etag          TEXT,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS agents (
              id                TEXT PRIMARY KEY,
              name              TEXT NOT NULL,
              role              TEXT NOT NULL,
              status            TEXT NOT NULL DEFAULT 'idle',
              capabilities_json TEXT NOT NULL DEFAULT '[]',
              metadata_json     TEXT NOT NULL DEFAULT '{}',
              created_at        TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS agent_tasks (
              id           TEXT PRIMARY KEY,
              agent_id     TEXT,
              task_type    TEXT NOT NULL,
              payload_json TEXT NOT NULL DEFAULT '{}',
              result_json  TEXT,
              status       TEXT NOT NULL DEFAULT 'pending',
              created_at   TEXT NOT NULL DEFAULT (datetime('now')),
              completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS agent_memories (
              id             TEXT PRIMARY KEY,
              agent_id       TEXT,
              memory_type    TEXT NOT NULL,
              content        TEXT NOT NULL,
              tags_json      TEXT NOT NULL DEFAULT '[]',
              embedding_json TEXT,
              importance     REAL NOT NULL DEFAULT 1.0,
              created_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS analysis_findings (
              id           TEXT PRIMARY KEY,
              category     TEXT NOT NULL,
              severity     TEXT NOT NULL DEFAULT 'medium',
              title        TEXT NOT NULL,
              details_json TEXT NOT NULL DEFAULT '{}',
              created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS forecast_matrices (
              id                TEXT PRIMARY KEY,
              horizon_hours     REAL NOT NULL DEFAULT 4.0,
              matrix_json       TEXT NOT NULL DEFAULT '{}',
              risk_tensor_json  TEXT NOT NULL DEFAULT '{}',
              summary           TEXT NOT NULL DEFAULT '',
              created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS scenario_outcomes (
              id            TEXT PRIMARY KEY,
              batch_id      TEXT NOT NULL,
              scenario_seed INTEGER NOT NULL,
              score         REAL NOT NULL DEFAULT 0.0,
              rank          INTEGER NOT NULL DEFAULT 1,
              outcome_json  TEXT NOT NULL DEFAULT '{}',
              created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS model_registry (
              id            TEXT PRIMARY KEY,
              name          TEXT NOT NULL,
              provider      TEXT NOT NULL,
              model_type    TEXT NOT NULL,
              endpoint      TEXT,
              is_active     INTEGER NOT NULL DEFAULT 1,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS workflow_instances (
              id                          TEXT PRIMARY KEY,
              workflow_type               TEXT NOT NULL,
              title                       TEXT NOT NULL,
              current_step                TEXT NOT NULL,
              steps_json                  TEXT NOT NULL DEFAULT '[]',
              status                      TEXT NOT NULL DEFAULT 'staged',
              requires_human_confirmation INTEGER NOT NULL DEFAULT 1,
              approved_by                 TEXT,
              created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at                  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS operational_reports (
              id           TEXT PRIMARY KEY,
              report_type  TEXT NOT NULL,
              title        TEXT NOT NULL,
              content_md   TEXT NOT NULL DEFAULT '',
              data_json    TEXT NOT NULL DEFAULT '{}',
              created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS units (
              id                TEXT PRIMARY KEY,
              run_id            TEXT,
              callsign          TEXT NOT NULL,
              kind              TEXT NOT NULL,
              status            TEXT NOT NULL DEFAULT 'active',
              lat               REAL NOT NULL,
              lon               REAL NOT NULL,
              heading           REAL NOT NULL DEFAULT 0.0,
              speed_kph         REAL NOT NULL DEFAULT 0.0,
              fuel              REAL NOT NULL DEFAULT 100.0,
              battery           REAL NOT NULL DEFAULT 100.0,
              sector            TEXT NOT NULL DEFAULT 'A',
              route_json        TEXT NOT NULL DEFAULT '[]',
              active_mission_id TEXT,
              last_seen_tick    INTEGER NOT NULL DEFAULT 0,
              created_at        TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS unit_position_history (
              id         INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id     TEXT NOT NULL,
              unit_id    TEXT NOT NULL,
              tick       INTEGER NOT NULL,
              sim_time   INTEGER NOT NULL,
              lat        REAL NOT NULL,
              lon        REAL NOT NULL,
              heading    REAL NOT NULL DEFAULT 0.0,
              speed_kph  REAL NOT NULL DEFAULT 0.0,
              in_weather INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_uph_run_tick ON unit_position_history(run_id, tick);
            CREATE INDEX IF NOT EXISTS idx_uph_unit ON unit_position_history(unit_id);

            CREATE TABLE IF NOT EXISTS personnel (
              id                   TEXT PRIMARY KEY,
              run_id               TEXT,
              name                 TEXT NOT NULL,
              rank                 TEXT NOT NULL,
              unit_id              TEXT NOT NULL,
              condition            TEXT NOT NULL DEFAULT 'fit',
              heart_rate           REAL NOT NULL DEFAULT 72.0,
              fatigue              REAL NOT NULL DEFAULT 0.20,
              active_mission_id    TEXT,
              mission_history_json TEXT NOT NULL DEFAULT '[]',
              created_at           TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS personnel_vitals_history (
              id            INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id        TEXT NOT NULL,
              person_id     TEXT NOT NULL,
              tick          INTEGER NOT NULL,
              sim_time      INTEGER NOT NULL,
              heart_rate    REAL NOT NULL,
              fatigue       REAL NOT NULL,
              activity_type TEXT NOT NULL DEFAULT 'patrol',
              created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_pvh_run_tick ON personnel_vitals_history(run_id, tick);
            CREATE INDEX IF NOT EXISTS idx_pvh_person ON personnel_vitals_history(person_id);

            CREATE TABLE IF NOT EXISTS personnel_assignments (
              id               TEXT PRIMARY KEY,
              run_id           TEXT NOT NULL,
              person_id        TEXT NOT NULL,
              unit_id          TEXT NOT NULL,
              mission_id       TEXT,
              role             TEXT NOT NULL DEFAULT 'operator',
              assigned_at_tick INTEGER NOT NULL DEFAULT 0,
              status           TEXT NOT NULL DEFAULT 'active',
              created_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        for alter_sql in [
            "ALTER TABLE runs ADD COLUMN world_json TEXT",
            "ALTER TABLE forecast_runs ADD COLUMN tick INTEGER DEFAULT 0",
            "ALTER TABLE forecast_runs ADD COLUMN horizon_ticks INTEGER DEFAULT 120",
            "ALTER TABLE vision_detections ADD COLUMN class_name TEXT",
            "ALTER TABLE vision_detections ADD COLUMN bbox_json TEXT DEFAULT '[]'",
            "ALTER TABLE vision_tracks ADD COLUMN class_name TEXT",
            "ALTER TABLE vision_tracks ADD COLUMN first_tick INTEGER DEFAULT 0",
            "ALTER TABLE vision_tracks ADD COLUMN last_tick INTEGER DEFAULT 0",
            "ALTER TABLE vision_tracks ADD COLUMN trajectory_json TEXT DEFAULT '[]'",
            "ALTER TABLE vision_tracks ADD COLUMN status TEXT DEFAULT 'active'",
        ]:
            try:
                conn.execute(alter_sql)
            except sqlite3.OperationalError:
                pass

    seed_users()


def get_database_status() -> dict[str, Any]:
    """Return health and provider telemetry for persistence engine."""
    url = get_database_url()
    db_type = "postgresql" if "postgresql" in url else "sqlite"
    connected = False
    error = None
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
            connected = True
    except Exception as exc:
        error = str(exc)

    return {
        "status": "online" if connected else "degraded",
        "type": db_type,
        "is_postgres": IS_POSTGRES,
        "url_masked": url.split("@")[-1] if "@" in url else "local/sqlite",
        "connected": connected,
        "postgis_enabled": bool(IS_POSTGRES and "postgis" in url.lower()),
        "error": error,
    }


# ---------------------------------------------------------------------------
# Run Persistence
# ---------------------------------------------------------------------------
def save_run(run: dict[str, Any]) -> None:
    """Save or update a simulation run."""
    with _lock, _sqlite_connect() as conn:
        cols = [col[1] for col in conn.execute("PRAGMA table_info(runs)").fetchall()]
        ev_col = "events_count" if "events_count" in cols else "events"
        has_created = "created_at" in cols
        q = (
            f"INSERT OR REPLACE INTO runs (id, seed, scenario_id, ticks, {ev_col}, log, created_at) "
            "VALUES (?,?,?,?,?,?, datetime('now'))"
            if has_created
            else f"INSERT OR REPLACE INTO runs (id, seed, scenario_id, ticks, {ev_col}, log) VALUES (?,?,?,?,?,?)"
        )
        conn.execute(
            q,
            (
                run["id"],
                run["seed"],
                run.get("scenarioId") or run.get("scenario_id", "SC-1"),
                run["ticks"],
                run.get("events") or run.get("events_count") or len(run.get("log", [])),
                json.dumps(run["log"]),
            ),
        )
        conn.commit()


def list_runs(limit: int = 8) -> list[dict[str, Any]]:
    """Return recorded runs, oldest-first for UI timeline consumption."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        {
            "id": r["id"],
            "seed": r["seed"],
            "scenarioId": r["scenario_id"],
            "ticks": r["ticks"],
            "events": r["events_count"] if "events_count" in r.keys() else r.get("events", 0),
            "log": json.loads(r["log"]) if isinstance(r["log"], str) else r["log"],
        }
        for r in reversed(rows)
    ]


def get_run(run_id: str) -> dict[str, Any] | None:
    """Retrieve a single recorded run by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        r = dict(row)
        return {
            "id": r["id"],
            "seed": r.get("seed"),
            "scenarioId": r.get("scenario_id"),
            "ticks": r.get("ticks", 0),
            "events": r.get("events_count") if "events_count" in r else r.get("events", 0),
            "log": json.loads(r["log"]) if isinstance(r.get("log"), str) else (r.get("log") or []),
            "world_json": json.loads(r["world_json"]) if isinstance(r.get("world_json"), str) else r.get("world_json"),
        }


def save_world_snapshot(run_id: str, world: dict[str, Any]) -> None:
    """Upsert live world state snapshot for an active run."""
    with _lock, _sqlite_connect() as conn:
        cols = [col[1] for col in conn.execute("PRAGMA table_info(runs)").fetchall()]
        ev_col = "events_count" if "events_count" in cols else "events"
        has_created = "created_at" in cols
        q = (
            f"INSERT OR IGNORE INTO runs (id, seed, scenario_id, ticks, {ev_col}, log, world_json, created_at) "
            "VALUES (?,?,?,0,0,'[]',?, datetime('now'))"
            if has_created
            else f"INSERT OR IGNORE INTO runs (id, seed, scenario_id, ticks, {ev_col}, log, world_json) VALUES (?,?,?,0,0,'[]',?)"
        )
        conn.execute(
            q,
            (run_id, world.get("seed", 0), world.get("scenarioId", "SC-1"), json.dumps(world)),
        )
        conn.execute(
            "UPDATE runs SET world_json = ? WHERE id = ?",
            (json.dumps(world), run_id),
        )
        conn.commit()


def load_world_snapshot(run_id: str) -> dict[str, Any] | None:
    """Return the terminal or current world state snapshot for `run_id`."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute(
            "SELECT world_json FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
    if row and row["world_json"]:
        try:
            return json.loads(row["world_json"])
        except (json.JSONDecodeError, TypeError):
            return None
    return None


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------
def add_audit(actor: str, action: str, detail: str = "") -> None:
    """Record an operational action to the append-only audit trail."""
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            "INSERT INTO audit_events (actor, action, detail, created_at) VALUES (?,?,?, datetime('now'))",
            (actor, action, detail),
        )
        try:
            conn.execute(
                "INSERT INTO audit (actor, action, detail, created_at) VALUES (?,?,?, datetime('now'))",
                (actor, action, detail),
            )
        except Exception:
            pass
        conn.commit()


def record_audit(actor: str, action: str, detail: str = "") -> None:
    """Alias for add_audit."""
    add_audit(actor, action, detail)


def list_audit(limit: int = 100) -> list[dict[str, Any]]:
    """Return recent audit rows, newest-first."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def list_audit_page(page: int = 1, per_page: int = 50) -> tuple[list[dict[str, Any]], int]:
    """Return paginated slice of audit log."""
    page = max(1, page)
    offset = (page - 1) * per_page
    with _lock, _sqlite_connect() as conn:
        total: int = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
    return [dict(r) for r in rows], total


# ---------------------------------------------------------------------------
# What-If Monte Carlo Persistence
# ---------------------------------------------------------------------------
def save_whatif_result(
    seed: int,
    scenario_id: str,
    ticks: int,
    actions: list[Any],
    deltas: dict[str, Any],
    score: float = 0.0,
) -> int:
    """Persist a what-if branch result."""
    baseline_kpis = {k: v.get("baseline") for k, v in deltas.items()}
    branch_kpis = {k: v.get("branch") for k, v in deltas.items()}
    with _lock, _sqlite_connect() as conn:
        cur = conn.execute(
            "INSERT INTO whatif_results "
            "(seed, scenario_id, ticks, actions_json, baseline_kpis, branch_kpis, deltas_json, score, created_at) "
            "VALUES (?,?,?,?,?,?,?,?, datetime('now'))",
            (
                seed,
                scenario_id,
                ticks,
                json.dumps(actions),
                json.dumps(baseline_kpis),
                json.dumps(branch_kpis),
                json.dumps(deltas),
                score,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_whatif_results(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent what-if branch execution results."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(
            "SELECT id, seed, scenario_id, ticks, actions_json, "
            "baseline_kpis, branch_kpis, deltas_json, created_at "
            "FROM whatif_results ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "seed": r["seed"],
            "scenarioId": r["scenario_id"],
            "ticks": r["ticks"],
            "actions": json.loads(r["actions_json"]),
            "baselineKpis": json.loads(r["baseline_kpis"]),
            "branchKpis": json.loads(r["branch_kpis"]),
            "deltas": json.loads(r["deltas_json"]),
            "createdAt": r["created_at"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# War-Room Messages
# ---------------------------------------------------------------------------
def save_warroom_message(type_: str, payload: dict[str, Any]) -> int:
    """Persist war-room chat or task item."""
    with _lock, _sqlite_connect() as conn:
        cur = conn.execute(
            "INSERT INTO warroom_messages (type, payload) VALUES (?,?)",
            (type_, json.dumps(payload)),
        )
        return int(cur.lastrowid or 0)


def list_warroom_messages(limit: int = 200) -> list[dict[str, Any]]:
    """Return war-room messages, oldest-first for playback."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(
            "SELECT id, type, payload, created_at FROM warroom_messages "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "type": r["type"],
            "payload": json.loads(r["payload"]),
            "created_at": r["created_at"],
        }
        for r in reversed(rows)
    ]


def delete_warroom_message(msg_id: int) -> bool:
    with _lock, _sqlite_connect() as conn:
        cur = conn.execute("DELETE FROM warroom_messages WHERE id = ?", (msg_id,))
        return bool(cur.rowcount > 0)


# ---------------------------------------------------------------------------
# User Roster Persistence
# ---------------------------------------------------------------------------
_SEED_USERS = [
    {"name": "Col. A. Verma", "username": "verma", "role": "admin", "unit": "HQ"},
    {"name": "Maj. R. Sethi", "username": "sethi", "role": "planner", "unit": "Ops Cell"},
    {"name": "Sgt. P. Kulkarni", "username": "kulkarni", "role": "operator", "unit": "Watch Floor"},
    {"name": "Obs. L. Fernandes", "username": "fernandes", "role": "viewer", "unit": "Evaluation"},
]


def seed_users() -> None:
    """Ensure baseline user roster exists."""
    with _lock, _sqlite_connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            for u in _SEED_USERS:
                conn.execute(
                    "INSERT OR IGNORE INTO users (username, name, role, unit, created_at, updated_at) "
                    "VALUES (?,?,?,?, datetime('now'), datetime('now'))",
                    (u["username"], u["name"], u["role"], u["unit"]),
                )
            conn.commit()


def list_users() -> list[dict[str, Any]]:
    """Return all tactical operators."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(
            "SELECT COALESCE(name, username) as name, role, unit FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def add_user(name: str, role: str, unit: str) -> dict[str, str]:
    username = name.lower().replace(" ", "_").replace(".", "")
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            "INSERT INTO users (username, name, role, unit, created_at, updated_at) "
            "VALUES (?,?,?,?, datetime('now'), datetime('now'))",
            (username, name, role, unit),
        )
        conn.commit()
    return {"name": name, "role": role, "unit": unit}


def remove_user(name: str) -> bool:
    with _lock, _sqlite_connect() as conn:
        cur = conn.execute("DELETE FROM users WHERE name = ? OR username = ?", (name, name))
        return bool(cur.rowcount > 0)


# ---------------------------------------------------------------------------
# Custom Scenarios
# ---------------------------------------------------------------------------
def list_custom_scenarios() -> list[dict[str, Any]]:
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(
            "SELECT id, scenario_id, name, description, config_json, actions_json, "
            "status, author, created_at, updated_at "
            "FROM custom_scenarios ORDER BY id DESC"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "scenarioId": r["scenario_id"],
            "name": r["name"],
            "description": r["description"],
            "config": json.loads(r["config_json"]),
            "actions": json.loads(r["actions_json"]),
            "status": r["status"],
            "author": r["author"],
            "createdAt": r["created_at"],
            "updatedAt": r["updated_at"],
        }
        for r in rows
    ]


def save_custom_scenario(
    scenario_id: str,
    name: str,
    description: str,
    config: dict[str, Any],
    actions: list[Any],
    status: str = "draft",
    author: str = "",
) -> dict[str, Any]:
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO custom_scenarios
              (scenario_id, name, description, config_json, actions_json, status, author, updated_at)
            VALUES (?,?,?,?,?,?,?, datetime('now'))
            ON CONFLICT(scenario_id) DO UPDATE SET
              name        = excluded.name,
              description = excluded.description,
              config_json = excluded.config_json,
              actions_json= excluded.actions_json,
              status      = excluded.status,
              author      = excluded.author,
              updated_at  = excluded.updated_at
            """,
            (
                scenario_id,
                name,
                description,
                json.dumps(config),
                json.dumps(actions),
                status,
                author,
            ),
        )
    return {
        "scenarioId": scenario_id,
        "name": name,
        "description": description,
        "config": config,
        "actions": actions,
        "status": status,
        "author": author,
    }


def delete_custom_scenario(scenario_id: str) -> bool:
    with _lock, _sqlite_connect() as conn:
        cur = conn.execute(
            "DELETE FROM custom_scenarios WHERE scenario_id = ?", (scenario_id,)
        )
        return bool(cur.rowcount > 0)


# ---------------------------------------------------------------------------
# Phase 1: Doctrine Documents & Chunks Persistence
# ---------------------------------------------------------------------------
def save_doctrine_document(
    doc_id: str,
    category: str,
    title: str,
    tags: list[str],
    version: str,
    source_file: str,
    content: str,
) -> None:
    """Upsert parsed doctrine document."""
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO doctrine_documents (doc_id, category, title, tags, version, source_file, content, created_at)
            VALUES (?,?,?,?,?,?,?, datetime('now'))
            ON CONFLICT(doc_id) DO UPDATE SET
              category    = excluded.category,
              title       = excluded.title,
              tags        = excluded.tags,
              version     = excluded.version,
              source_file = excluded.source_file,
              content     = excluded.content
            """,
            (doc_id, category, title, json.dumps(tags), version, source_file, content),
        )
        conn.commit()


def get_doctrine_document(doc_id: str) -> dict[str, Any] | None:
    with _lock, _sqlite_connect() as conn:
        row = conn.execute(
            "SELECT * FROM doctrine_documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["tags"] = json.loads(d["tags"]) if isinstance(d["tags"], str) else d["tags"]
    return d


def list_doctrine_documents() -> list[dict[str, Any]]:
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute("SELECT * FROM doctrine_documents ORDER BY doc_id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags"]) if isinstance(d["tags"], str) else d["tags"]
        out.append(d)
    return out


def save_doctrine_chunks(chunks: list[dict[str, Any]]) -> int:
    """Batch upsert semantic doctrine chunks with vector embeddings."""
    count = 0
    with _lock, _sqlite_connect() as conn:
        for c in chunks:
            emb = c.get("embedding")
            emb_str = json.dumps(emb) if emb is not None else None
            conn.execute(
                """
                INSERT INTO doctrine_chunks
                  (chunk_id, document_id, document_type, section, source, citation, text, token_count, embedding, created_at)
                VALUES (?,?,?,?,?,?,?,?,?, datetime('now'))
                ON CONFLICT(chunk_id) DO UPDATE SET
                  document_id   = excluded.document_id,
                  document_type = excluded.document_type,
                  section       = excluded.section,
                  source        = excluded.source,
                  citation      = excluded.citation,
                  text          = excluded.text,
                  token_count   = excluded.token_count,
                  embedding     = excluded.embedding
                """,
                (
                    c["chunk_id"],
                    c["document_id"],
                    c["document_type"],
                    c["section"],
                    c["source"],
                    c["citation"],
                    c["text"],
                    c.get("token_count", 0),
                    emb_str,
                ),
            )
            count += 1
        conn.commit()
    return count


def get_doctrine_chunks(document_id: str | None = None) -> list[dict[str, Any]]:
    """Retrieve persisted doctrine chunks."""
    with _lock, _sqlite_connect() as conn:
        if document_id:
            rows = conn.execute(
                "SELECT * FROM doctrine_chunks WHERE document_id = ? ORDER BY id",
                (document_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM doctrine_chunks ORDER BY id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("embedding") and isinstance(d["embedding"], str):
            try:
                d["embedding"] = json.loads(d["embedding"])
            except Exception:
                pass
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 1: Sim Events Persistence & Spatial Queries
# ---------------------------------------------------------------------------
def save_sim_events(events: list[dict[str, Any]], run_id: str = "") -> int:
    """Insert simulation events into the indexed relational store."""
    count = 0
    with _lock, _sqlite_connect() as conn:
        for idx, ev in enumerate(events, start=1):
            r_id = ev.get("run_id") or run_id
            ev_id = ev.get("id") or idx
            ev_type = ev.get("type") or ev.get("event_type", "event")
            entity_id = ev.get("entityId") or ev.get("entity_id", "")
            payload = ev.get("payload", {})
            lat = ev.get("lat") or payload.get("lat")
            lon = ev.get("lon") or payload.get("lon")
            geom_str = json.dumps([lon, lat]) if (lat is not None and lon is not None) else None
            conn.execute(
                """
                INSERT OR REPLACE INTO sim_events
                  (id, run_id, tick, event_type, severity, entity_id, lat, lon, payload, geom, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'))
                """,
                (
                    ev_id,
                    r_id,
                    ev.get("tick", 0),
                    ev_type,
                    ev.get("severity", "low"),
                    entity_id,
                    lat,
                    lon,
                    json.dumps(payload),
                    geom_str,
                ),
            )
            count += 1
        conn.commit()
    return count


save_events_batch = save_sim_events


def get_sim_events(run_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Query recent events for a run."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sim_events WHERE run_id = ? ORDER BY tick DESC, id DESC LIMIT ?",
            (run_id, limit),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"]) if isinstance(d["payload"], str) else d["payload"]
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 1: PostGIS / Spatial Queries
# ---------------------------------------------------------------------------
def save_tactical_zone(
    zone_id: str,
    name: str,
    zone_type: str,
    coordinates: list[Any],  # [[lat, lon], ...] or [{"lat": ..., "lon": ...}, ...]
    min_alt_m: float = 0.0,
    max_alt_m: float = 10000.0,
    active: bool = True,
) -> None:
    """Upsert a geofenced tactical polygon zone."""
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO tactical_zones (zone_id, name, zone_type, min_alt_m, max_alt_m, active, coordinates_json, created_at)
            VALUES (?,?,?,?,?,?,?, datetime('now'))
            ON CONFLICT(zone_id) DO UPDATE SET
              name        = excluded.name,
              zone_type   = excluded.zone_type,
              min_alt_m   = excluded.min_alt_m,
              max_alt_m   = excluded.max_alt_m,
              active      = excluded.active,
              coordinates_json = excluded.coordinates_json
            """,
            (zone_id, name, zone_type, min_alt_m, max_alt_m, 1 if active else 0, json.dumps(coordinates)),
        )
        conn.commit()


def list_tactical_zones() -> list[dict[str, Any]]:
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute("SELECT * FROM tactical_zones WHERE active = 1").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["coordinates"] = json.loads(d["coordinates_json"]) if isinstance(d["coordinates_json"], str) else d["coordinates_json"]
        out.append(d)
    return out


def _point_in_polygon(lat: float, lon: float, poly: list[Any]) -> bool:
    """Ray-casting algorithm for 2D point-in-polygon check in fallback mode."""
    if not poly or len(poly) < 3:
        return False

    norm_poly: list[tuple[float, float]] = []
    for pt in poly:
        if isinstance(pt, dict):
            norm_poly.append((float(pt.get("lat", 0.0)), float(pt.get("lon", 0.0))))
        elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
            norm_poly.append((float(pt[0]), float(pt[1])))

    if len(norm_poly) < 3:
        return False

    inside = False
    n = len(norm_poly)
    p1y, p1x = norm_poly[0][0], norm_poly[0][1]  # lat, lon
    for i in range(n + 1):
        p2y, p2x = norm_poly[i % n][0], norm_poly[i % n][1]
        if lat > min(p1y, p2y):
            if lat <= max(p1y, p2y):
                if lon <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lon <= xinters:
                        inside = not inside
        p1y, p1x = p2y, p2x
    return inside


def spatial_query_zones_containing(lat: float, lon: float) -> list[dict[str, Any]]:
    """Determine which tactical zones contain the given coordinate.

    Uses PostGIS ST_Contains when connected to PostgreSQL+PostGIS;
    falls back to ray-casting algorithm on SQLite.
    """
    if IS_POSTGRES:
        try:
            with get_session() as session:
                q = text(
                    """
                    SELECT zone_id, name, zone_type, min_alt_m, max_alt_m
                    FROM tactical_zones
                    WHERE active = true
                      AND geom IS NOT NULL
                      AND ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                    """
                )
                res = session.execute(q, {"lon": lon, "lat": lat}).fetchall()
                return [dict(r._mapping) for r in res]
        except Exception as exc:
            log.warning("PostGIS ST_Contains failed: %s, falling back to local math", exc)

    # Local Fallback
    zones = list_tactical_zones()
    containing = []
    for z in zones:
        coords = z.get("coordinates", [])
        if _point_in_polygon(lat, lon, coords):
            containing.append({
                "zone_id": z["zone_id"],
                "name": z["name"],
                "zone_type": z["zone_type"],
                "min_alt_m": z["min_alt_m"],
                "max_alt_m": z["max_alt_m"],
            })
    return containing


def spatial_query_events_within(
    lat: float,
    lon: float,
    radius_m: float = 10000.0,
    run_id: str | None = None,
    radius_km: float | None = None,
) -> list[dict[str, Any]]:
    """Find events within `radius_m` meters (or `radius_km` kilometers) of coordinates.

    Uses PostGIS ST_DWithin when PostgreSQL is active, otherwise haversine distance.
    """
    if radius_km is not None:
        radius_m = radius_km * 1000.0
    if IS_POSTGRES:
        try:
            with get_session() as session:
                sql = """
                    SELECT id, run_id, tick, event_type, severity, entity_id, lat, lon, payload
                    FROM sim_events
                    WHERE geom IS NOT NULL
                      AND (:run_id IS NULL OR run_id = :run_id)
                      AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_m)
                    ORDER BY tick DESC
                """
                res = session.execute(text(sql), {"lon": lon, "lat": lat, "radius_m": radius_m, "run_id": run_id}).fetchall()
                out = []
                for r in res:
                    m = dict(r._mapping)
                    m["payload"] = json.loads(m["payload"]) if isinstance(m["payload"], str) else m["payload"]
                    out.append(m)
                return out
        except Exception as exc:
            log.warning("PostGIS ST_DWithin failed: %s, falling back to haversine", exc)

    # Haversine distance fallback
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371000.0  # Earth radius in meters
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2.0) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c

    with _lock, _sqlite_connect() as conn:
        if run_id:
            rows = conn.execute(
                "SELECT * FROM sim_events WHERE run_id = ? AND lat IS NOT NULL AND lon IS NOT NULL",
                (run_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sim_events WHERE lat IS NOT NULL AND lon IS NOT NULL"
            ).fetchall()

    matches = []
    for r in rows:
        d = dict(r)
        dist = _haversine_m(lat, lon, d["lat"], d["lon"])
        if dist <= radius_m:
            d["distance_m"] = round(dist, 1)
            d["payload"] = json.loads(d["payload"]) if isinstance(d["payload"], str) else d["payload"]
            matches.append(d)

    matches.sort(key=lambda x: x.get("distance_m", 0.0))
    return matches


# ---------------------------------------------------------------------------
# Phase 2: Mission Planning Persistence
# ---------------------------------------------------------------------------
def save_mission(mission_data: dict[str, Any]) -> dict[str, Any]:
    """Upsert a mission with tasks and waypoints."""
    m_id = mission_data["id"]
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO missions
              (id, name, description, priority, status, author, approved_by, assigned_unit_ids,
               risk_score, estimated_duration_s, estimated_fuel_l, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?, datetime('now'), datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              name                 = excluded.name,
              description          = excluded.description,
              priority             = excluded.priority,
              status               = excluded.status,
              author               = excluded.author,
              approved_by          = excluded.approved_by,
              assigned_unit_ids    = excluded.assigned_unit_ids,
              risk_score           = excluded.risk_score,
              estimated_duration_s = excluded.estimated_duration_s,
              estimated_fuel_l     = excluded.estimated_fuel_l,
              updated_at           = datetime('now')
            """,
            (
                m_id,
                mission_data["name"],
                mission_data.get("description", ""),
                mission_data.get("priority", "routine"),
                mission_data.get("status", "draft"),
                mission_data.get("author", "operator"),
                mission_data.get("approved_by"),
                json.dumps(mission_data.get("assigned_unit_ids", [])),
                float(mission_data.get("risk_score", 0.0)),
                int(mission_data.get("estimated_duration_s", 0)),
                float(mission_data.get("estimated_fuel_l", 0.0)),
            ),
        )
        # Clear and insert tasks if provided
        if "tasks" in mission_data:
            conn.execute("DELETE FROM mission_tasks WHERE mission_id = ?", (m_id,))
            for seq, t in enumerate(mission_data["tasks"], start=1):
                conn.execute(
                    """
                    INSERT INTO mission_tasks (mission_id, sequence, title, task_type, target_entity, status, duration_s, created_at)
                    VALUES (?,?,?,?,?,?,?, datetime('now'))
                    """,
                    (
                        m_id,
                        t.get("sequence", seq),
                        t["title"],
                        t.get("task_type", "PATROL"),
                        t.get("target_entity"),
                        t.get("status", "pending"),
                        int(t.get("duration_s", 0)),
                    ),
                )
        # Clear and insert waypoints if provided
        if "waypoints" in mission_data:
            conn.execute("DELETE FROM waypoints WHERE mission_id = ?", (m_id,))
            for seq, w in enumerate(mission_data["waypoints"], start=1):
                conn.execute(
                    """
                    INSERT INTO waypoints (mission_id, sequence, name, lat, lon, alt_m, geom, created_at)
                    VALUES (?,?,?,?,?,?,?, datetime('now'))
                    """,
                    (
                        m_id,
                        w.get("sequence", seq),
                        w.get("name", f"WP-{seq}"),
                        float(w["lat"]),
                        float(w["lon"]),
                        float(w.get("alt_m", 0.0)),
                        json.dumps([float(w["lon"]), float(w["lat"])]),
                    ),
                )
        conn.commit()
    return get_mission(m_id) or mission_data


def get_mission(mission_id: str) -> dict[str, Any] | None:
    """Fetch complete mission specification with tasks and waypoints."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)).fetchone()
        if not row:
            return None
        m = dict(row)
        m["assigned_unit_ids"] = json.loads(m["assigned_unit_ids"]) if isinstance(m["assigned_unit_ids"], str) else m["assigned_unit_ids"]

        tasks = conn.execute("SELECT * FROM mission_tasks WHERE mission_id = ? ORDER BY sequence", (mission_id,)).fetchall()
        m["tasks"] = [dict(t) for t in tasks]

        waypoints = conn.execute("SELECT * FROM waypoints WHERE mission_id = ? ORDER BY sequence", (mission_id,)).fetchall()
        m["waypoints"] = [dict(w) for w in waypoints]
        m["fuel_required_l"] = float(m.get("estimated_fuel_l", 0.0))
    return m


def list_missions(limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    """List missions filtered by optional lifecycle status."""
    with _lock, _sqlite_connect() as conn:
        if status:
            rows = conn.execute("SELECT * FROM missions WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM missions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        m = dict(r)
        m["assigned_unit_ids"] = json.loads(m["assigned_unit_ids"]) if isinstance(m["assigned_unit_ids"], str) else m["assigned_unit_ids"]
        out.append(m)
    return out


def transition_mission_status(mission_id: str, new_status: str, actor: str = "") -> dict[str, Any] | None:
    """Enforce mission lifecycle transitions and audit trail."""
    valid_transitions = {
        "draft": ["review", "cancelled"],
        "review": ["approved", "draft", "cancelled"],
        "approved": ["executing", "cancelled"],
        "executing": ["completed", "cancelled"],
        "completed": [],
        "cancelled": [],
    }
    m = get_mission(mission_id)
    if not m:
        return None
    curr_status = m["status"]
    if new_status not in valid_transitions.get(curr_status, []):
        raise ValueError(f"Illegal transition from {curr_status} to {new_status}")

    with _lock, _sqlite_connect() as conn:
        approved_by = actor if new_status == "approved" else m.get("approved_by")
        conn.execute(
            "UPDATE missions SET status = ?, approved_by = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, approved_by, mission_id),
        )
        conn.commit()

    add_audit(actor or "commander", f"MISSION_{new_status.upper()}", f"Mission {mission_id} transitioned from {curr_status} to {new_status}")
    return get_mission(mission_id)


# ---------------------------------------------------------------------------
# Phase 2: Route Planning Persistence
# ---------------------------------------------------------------------------
def save_route(route_data: dict[str, Any]) -> dict[str, Any]:
    """Persist an A* multi-layer route calculation."""
    r_id = route_data["id"]
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO routes
              (id, mission_id, unit_id, strategy, distance_km, estimated_duration_s, fuel_l,
               risk_score, waypoints_json, explanation, geom, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              distance_km          = excluded.distance_km,
              estimated_duration_s = excluded.estimated_duration_s,
              fuel_l               = excluded.fuel_l,
              risk_score           = excluded.risk_score,
              waypoints_json       = excluded.waypoints_json,
              explanation          = excluded.explanation
            """,
            (
                r_id,
                route_data.get("mission_id"),
                route_data["unit_id"],
                route_data.get("strategy", "shortest"),
                float(route_data["distance_km"]),
                int(route_data["estimated_duration_s"]),
                float(route_data["fuel_l"]),
                float(route_data.get("risk_score", 0.0)),
                json.dumps(route_data.get("waypoints", [])),
                route_data.get("explanation", ""),
                json.dumps(route_data.get("waypoints", [])),
            ),
        )
        # Segments
        if "segments" in route_data:
            conn.execute("DELETE FROM route_segments WHERE route_id = ?", (r_id,))
            for idx, seg in enumerate(route_data["segments"], start=1):
                conn.execute(
                    """
                    INSERT INTO route_segments
                      (route_id, segment_idx, start_lat, start_lon, end_lat, end_lon,
                       distance_km, terrain_cost, threat_cost, weather_cost)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        r_id,
                        idx,
                        float(seg["start_lat"]),
                        float(seg["start_lon"]),
                        float(seg["end_lat"]),
                        float(seg["end_lon"]),
                        float(seg["distance_km"]),
                        float(seg.get("terrain_cost", 1.0)),
                        float(seg.get("threat_cost", 0.0)),
                        float(seg.get("weather_cost", 0.0)),
                    ),
                )
        conn.commit()
    return get_route(r_id) or route_data


def get_route(route_id: str) -> dict[str, Any] | None:
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM routes WHERE id = ?", (route_id,)).fetchone()
        if not row:
            return None
        r = dict(row)
        r["waypoints"] = json.loads(r["waypoints_json"]) if isinstance(r["waypoints_json"], str) else r["waypoints_json"]
        segs = conn.execute("SELECT * FROM route_segments WHERE route_id = ? ORDER BY segment_idx", (route_id,)).fetchall()
        r["segments"] = [dict(s) for s in segs]
    return r


def list_routes(mission_id: str | None = None, unit_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with _lock, _sqlite_connect() as conn:
        if mission_id:
            rows = conn.execute("SELECT * FROM routes WHERE mission_id = ? ORDER BY created_at DESC LIMIT ?", (mission_id, limit)).fetchall()
        elif unit_id:
            rows = conn.execute("SELECT * FROM routes WHERE unit_id = ? ORDER BY created_at DESC LIMIT ?", (unit_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM routes ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["waypoints"] = json.loads(d["waypoints_json"]) if isinstance(d["waypoints_json"], str) else d["waypoints_json"]
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 2: War Room Real-Time Collaboration Persistence
# ---------------------------------------------------------------------------
def update_warroom_presence(
    username: str,
    name: str,
    role: str,
    status: str = "online",
    current_screen: str = "map",
    cursor_lat: float | None = None,
    cursor_lon: float | None = None,
) -> dict[str, Any]:
    """Upsert operator presence state."""
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO warroom_presence (username, name, role, status, current_screen, cursor_lat, cursor_lon, last_heartbeat)
            VALUES (?,?,?,?,?,?,?, datetime('now'))
            ON CONFLICT(username) DO UPDATE SET
              name            = excluded.name,
              role            = excluded.role,
              status          = excluded.status,
              current_screen  = excluded.current_screen,
              cursor_lat      = excluded.cursor_lat,
              cursor_lon      = excluded.cursor_lon,
              last_heartbeat  = datetime('now')
            """,
            (username, name, role, status, current_screen, cursor_lat, cursor_lon),
        )
        conn.commit()
    return {
        "username": username,
        "name": name,
        "role": role,
        "status": status,
        "current_screen": current_screen,
        "cursor_lat": cursor_lat,
        "cursor_lon": cursor_lon,
    }


def list_warroom_presence() -> list[dict[str, Any]]:
    """Return all active operator presence records."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute("SELECT * FROM warroom_presence ORDER BY username").fetchall()
    return [dict(r) for r in rows]


def save_warroom_task(task_data: dict[str, Any]) -> dict[str, Any]:
    with _lock, _sqlite_connect() as conn:
        if "id" in task_data and task_data["id"]:
            t_id = task_data["id"]
            conn.execute(
                """
                UPDATE warroom_tasks
                SET title = ?, description = ?, incident_id = ?, assigned_to = ?,
                    status = ?, priority = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    task_data["title"],
                    task_data.get("description", ""),
                    task_data.get("incident_id"),
                    task_data.get("assigned_to"),
                    task_data.get("status", "TODO"),
                    task_data.get("priority", "MEDIUM"),
                    t_id,
                ),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO warroom_tasks (title, description, incident_id, assigned_to, status, priority, created_by, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?, datetime('now'), datetime('now'))
                """,
                (
                    task_data["title"],
                    task_data.get("description", ""),
                    task_data.get("incident_id"),
                    task_data.get("assigned_to"),
                    task_data.get("status", "TODO"),
                    task_data.get("priority", "MEDIUM"),
                    task_data.get("created_by", "system"),
                ),
            )
            t_id = int(cur.lastrowid or 0)
        conn.commit()
        row = conn.execute("SELECT * FROM warroom_tasks WHERE id = ?", (t_id,)).fetchone()
    return dict(row) if row else task_data


def list_warroom_tasks(incident_id: str | None = None, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with _lock, _sqlite_connect() as conn:
        query = "SELECT * FROM warroom_tasks"
        params: list[Any] = []
        conditions: list[str] = []
        if incident_id:
            conditions.append("incident_id = ?")
            params.append(incident_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def assign_warroom_task(task_id: int, to_user: str, from_user: str, reason: str = "") -> bool:
    with _lock, _sqlite_connect() as conn:
        cur = conn.execute(
            "UPDATE warroom_tasks SET assigned_to = ?, updated_at = datetime('now') WHERE id = ?",
            (to_user, task_id),
        )
        conn.execute(
            """
            INSERT INTO warroom_assignments (task_id, from_user, to_user, reason, created_at)
            VALUES (?,?,?,?, datetime('now'))
            """,
            (task_id, from_user, to_user, reason),
        )
        conn.commit()
        return bool(cur.rowcount > 0)


# ---------------------------------------------------------------------------
# Phase 2: Investment Optimization Persistence
# ---------------------------------------------------------------------------
def save_optimizer_run(
    budget: float,
    priorities: dict[str, Any],
    score: float,
    recommendations: list[Any],
    tradeoffs: dict[str, Any],
) -> int:
    with _lock, _sqlite_connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO optimizer_runs (budget, priorities_json, score, recommendations_json, tradeoffs_json, created_at)
            VALUES (?,?,?,?,?, datetime('now'))
            """,
            (budget, json.dumps(priorities), score, json.dumps(recommendations), json.dumps(tradeoffs)),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_optimizer_runs(limit: int = 10) -> list[dict[str, Any]]:
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute("SELECT * FROM optimizer_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["priorities"] = json.loads(d["priorities_json"]) if isinstance(d["priorities_json"], str) else d["priorities_json"]
        d["recommendations"] = json.loads(d["recommendations_json"]) if isinstance(d["recommendations_json"], str) else d["recommendations_json"]
        d["tradeoffs"] = json.loads(d["tradeoffs_json"]) if isinstance(d["tradeoffs_json"], str) else d["tradeoffs_json"]
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 2: Red Team Adversarial Persistence
# ---------------------------------------------------------------------------
def save_redteam_scenario(scenario_data: dict[str, Any]) -> dict[str, Any]:
    s_id = scenario_data["id"]
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO redteam_scenarios
              (id, mission_id, title, risk_rating, vulnerability_summary, injects_json, status, approved_by, created_at)
            VALUES (?,?,?,?,?,?,?,?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              title                 = excluded.title,
              risk_rating           = excluded.risk_rating,
              vulnerability_summary = excluded.vulnerability_summary,
              injects_json          = excluded.injects_json,
              status                = excluded.status,
              approved_by           = excluded.approved_by
            """,
            (
                s_id,
                scenario_data.get("mission_id"),
                scenario_data["title"],
                scenario_data.get("risk_rating", "HIGH"),
                scenario_data.get("vulnerability_summary", ""),
                json.dumps(scenario_data.get("injects", [])),
                scenario_data.get("status", "staged"),
                scenario_data.get("approved_by"),
            ),
        )
        conn.commit()
    return get_redteam_scenario(s_id) or scenario_data


def get_redteam_scenario(scenario_id: str) -> dict[str, Any] | None:
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM redteam_scenarios WHERE id = ?", (scenario_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["injects"] = json.loads(d["injects_json"]) if isinstance(d["injects_json"], str) else d["injects_json"]
    return d


def list_redteam_scenarios() -> list[dict[str, Any]]:
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute("SELECT * FROM redteam_scenarios ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["injects"] = json.loads(d["injects_json"]) if isinstance(d["injects_json"], str) else d["injects_json"]
        out.append(d)
    return out


def update_redteam_inject_status(scenario_id: str, inject_id: str, new_status: str, approved_by: str = "") -> bool:
    scenario = get_redteam_scenario(scenario_id)
    if not scenario:
        return False
    injects = scenario.get("injects", [])
    updated = False
    for inj in injects:
        if inj.get("id") == inject_id:
            inj["status"] = new_status
            if approved_by:
                inj["approved_by"] = approved_by
            updated = True
            break
    if not updated:
        return False
    with _lock, _sqlite_connect() as conn:
        conn.execute("UPDATE redteam_scenarios SET injects_json = ? WHERE id = ?", (json.dumps(injects), scenario_id))
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Phase 3: Operational Knowledge Graph Persistence
# ---------------------------------------------------------------------------
def save_graph_node(node_data: dict[str, Any]) -> dict[str, Any]:
    """Persist or update an operational knowledge graph entity node."""
    node_id = str(node_data.get("id") or f"node-{uuid.uuid4().hex[:8]}")
    entity_type = str(node_data.get("entity_type", "UNKNOWN"))
    label = str(node_data.get("label", node_id))
    props = node_data.get("properties") or node_data.get("properties_json") or {}
    props_json = json.dumps(props) if not isinstance(props, str) else props

    with _lock, _sqlite_connect() as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(knowledge_graph_nodes)").fetchall()]
        has_updated = "updated_at" in cols
        if has_updated:
            conn.execute(
                """
                INSERT INTO knowledge_graph_nodes (id, entity_type, label, properties_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    label = excluded.label,
                    properties_json = excluded.properties_json,
                    updated_at = datetime('now')
                """,
                (node_id, entity_type, label, props_json),
            )
        else:
            conn.execute(
                """
                INSERT INTO knowledge_graph_nodes (id, entity_type, label, properties_json, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    label = excluded.label,
                    properties_json = excluded.properties_json
                """,
                (node_id, entity_type, label, props_json),
            )
        conn.commit()
    parsed_props = json.loads(props_json) if isinstance(props_json, str) else props_json
    return {
        "id": node_id,
        "entity_type": entity_type,
        "label": label,
        "properties": parsed_props,
        "properties_json": parsed_props,
    }

save_knowledge_node = save_graph_node


def save_graph_edge(edge_data: dict[str, Any]) -> dict[str, Any]:
    """Persist an operational knowledge graph relation edge."""
    source_id = str(edge_data["source_id"])
    target_id = str(edge_data["target_id"])
    relation_type = str(edge_data.get("relation_type", "related_to"))
    weight = float(edge_data.get("weight", 1.0))
    props = edge_data.get("properties") or edge_data.get("properties_json") or {}
    props_json = json.dumps(props) if not isinstance(props, str) else props

    with _lock, _sqlite_connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO knowledge_graph_edges (source_id, target_id, relation_type, weight, properties_json, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (source_id, target_id, relation_type, weight, props_json),
        )
        edge_id = cursor.lastrowid
        conn.commit()
    parsed_props = json.loads(props_json) if isinstance(props_json, str) else props_json
    return {
        "id": edge_id,
        "source_id": source_id,
        "target_id": target_id,
        "relation_type": relation_type,
        "weight": weight,
        "properties": parsed_props,
        "properties_json": parsed_props,
    }

save_knowledge_edge = save_graph_edge


def list_graph_nodes(entity_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Retrieve operational knowledge graph nodes, optionally filtered by entity type."""
    with _lock, _sqlite_connect() as conn:
        if entity_type:
            rows = conn.execute(
                "SELECT * FROM knowledge_graph_nodes WHERE entity_type = ? ORDER BY created_at DESC LIMIT ?",
                (entity_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM knowledge_graph_nodes ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    nodes = []
    for r in rows:
        d = dict(r)
        d["properties"] = json.loads(d["properties_json"]) if isinstance(d["properties_json"], str) else d.get("properties_json", {})
        d["properties_json"] = d["properties"]
        nodes.append(d)
    return nodes

list_knowledge_nodes = list_graph_nodes


def list_graph_edges(
    source_id: str | None = None,
    target_id: str | None = None,
    relation_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Retrieve operational knowledge graph edges with optional endpoint/relation filters."""
    query = "SELECT * FROM knowledge_graph_edges WHERE 1=1"
    params: list[Any] = []
    if source_id:
        query += " AND source_id = ?"
        params.append(source_id)
    if target_id:
        query += " AND target_id = ?"
        params.append(target_id)
    if relation_type:
        query += " AND relation_type = ?"
        params.append(relation_type)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    edges = []
    for r in rows:
        d = dict(r)
        d["properties"] = json.loads(d["properties_json"]) if isinstance(d["properties_json"], str) else d.get("properties_json", {})
        d["properties_json"] = d["properties"]
        edges.append(d)
    return edges

list_knowledge_edges = list_graph_edges


def clear_knowledge_graph() -> None:
    """Clear all nodes and edges from the persistent database."""
    with _lock, _sqlite_connect() as conn:
        conn.execute("DELETE FROM knowledge_graph_edges")
        conn.execute("DELETE FROM knowledge_graph_nodes")
        conn.commit()


# ---------------------------------------------------------------------------
# Phase 3: Digital Twin Lookahead Forecast Persistence
# ---------------------------------------------------------------------------
def save_forecast_run(
    forecast_data: dict[str, Any] | None = None,
    *,
    id: str | None = None,
    scenario_id: str = "SC-DEFAULT",
    tick: int = 0,
    horizon_ticks: int = 120,
    horizon_hours: float = 2.0,
    confidence: float = 0.95,
    ticks: int = 120,
    predictions: Any = None,
    summary: str = "",
) -> dict[str, Any]:
    """Persist digital twin lookahead forecast run to SQLite / PostgreSQL."""
    data = dict(forecast_data) if isinstance(forecast_data, dict) else {}
    f_id = str(data.get("id") or id or f"FC-{int(datetime.datetime.utcnow().timestamp())}")
    sc_id = str(data.get("scenario_id") or scenario_id)
    t_val = int(data.get("tick", data.get("ticks", tick if tick != 0 else ticks)))
    h_ticks = int(data.get("horizon_ticks", horizon_ticks if horizon_ticks != 120 else int(data.get("horizon_hours", horizon_hours) * 60)))
    h_hours = float(data.get("horizon_hours", horizon_hours))
    conf = float(data.get("confidence", confidence))
    preds = data.get("predictions", data.get("predictions_json", predictions if predictions is not None else []))
    preds_json = json.dumps(preds) if not isinstance(preds, str) else preds
    summ = str(data.get("summary", summary))
    if not summ and isinstance(preds, dict) and "executive_summary" in preds:
        exec_s = preds["executive_summary"]
        summ = exec_s.get("headline", "") if isinstance(exec_s, dict) else str(exec_s)

    with _lock, _sqlite_connect() as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(forecast_runs)").fetchall()]
        has_horizon_hours = "horizon_hours" in cols
        has_tick = "tick" in cols
        has_horizon_ticks = "horizon_ticks" in cols
        has_summary = "summary" in cols

        insert_cols = ["id", "scenario_id", "confidence", "predictions_json", "created_at"]
        val_placeholders = ["?", "?", "?", "?", "datetime('now')"]
        val_params: list[Any] = [f_id, sc_id, conf, preds_json]

        if has_tick:
            insert_cols.insert(2, "tick")
            val_placeholders.insert(2, "?")
            val_params.insert(2, t_val)
        if "ticks" in cols:
            insert_cols.insert(3, "ticks")
            val_placeholders.insert(3, "?")
            val_params.insert(3, t_val)
        if has_horizon_ticks:
            insert_cols.append("horizon_ticks")
            val_placeholders.append("?")
            val_params.append(h_ticks)
        if has_horizon_hours:
            insert_cols.append("horizon_hours")
            val_placeholders.append("?")
            val_params.append(h_hours)
        if has_summary:
            insert_cols.append("summary")
            val_placeholders.append("?")
            val_params.append(summ)

        sql = f"""
            INSERT INTO forecast_runs ({', '.join(insert_cols)})
            VALUES ({', '.join(val_placeholders)})
            ON CONFLICT(id) DO UPDATE SET
              scenario_id      = excluded.scenario_id,
              confidence       = excluded.confidence,
              predictions_json = excluded.predictions_json
        """
        if has_tick:
            sql += ", tick = excluded.tick"
        if "ticks" in cols:
            sql += ", ticks = excluded.ticks"
        if has_horizon_ticks:
            sql += ", horizon_ticks = excluded.horizon_ticks"
        if has_horizon_hours:
            sql += ", horizon_hours = excluded.horizon_hours"
        if has_summary:
            sql += ", summary = excluded.summary"

        conn.execute(sql, tuple(val_params))
        conn.commit()

    return get_forecast_run(f_id) or {
        "id": f_id,
        "scenario_id": sc_id,
        "tick": t_val,
        "horizon_ticks": h_ticks,
        "confidence": conf,
        "predictions": json.loads(preds_json) if isinstance(preds_json, str) else preds_json,
        "predictions_json": json.loads(preds_json) if isinstance(preds_json, str) else preds_json,
        "summary": summ,
    }


def get_forecast_run(forecast_id: str) -> dict[str, Any] | None:
    """Retrieve persisted forecast run by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM forecast_runs WHERE id = ?", (forecast_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["predictions"] = json.loads(d["predictions_json"]) if isinstance(d["predictions_json"], str) else d.get("predictions_json", [])
        d["predictions_json"] = d["predictions"]
        if "tick" not in d and "ticks" in d:
            d["tick"] = d["ticks"]
        if "horizon_ticks" not in d and "horizon_hours" in d:
            d["horizon_ticks"] = int(d["horizon_hours"] * 60)
        return d


def list_forecast_runs(scenario_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve recent forecast runs ordered by creation timestamp."""
    with _lock, _sqlite_connect() as conn:
        if scenario_id:
            rows = conn.execute(
                "SELECT * FROM forecast_runs WHERE scenario_id = ? ORDER BY created_at DESC LIMIT ?",
                (scenario_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM forecast_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["predictions"] = json.loads(d["predictions_json"]) if isinstance(d["predictions_json"], str) else d.get("predictions_json", [])
        d["predictions_json"] = d["predictions"]
        if "tick" not in d and "ticks" in d:
            d["tick"] = d["ticks"]
        if "horizon_ticks" not in d and "horizon_hours" in d:
            d["horizon_ticks"] = int(d["horizon_hours"] * 60)
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 3B: Vision Detection and Multi-Frame Track Persistence
# ---------------------------------------------------------------------------
def save_vision_detection(detection: dict[str, Any]) -> dict[str, Any]:
    """Persist a vision detection observation to the database."""
    det_id = detection.get("id")
    frame_id = str(detection.get("frame_id") or detection.get("frame") or "frame_00")
    tick = int(detection.get("tick", 0))
    cls_name = str(detection.get("class_name") or detection.get("class_label") or detection.get("label") or "military_vehicle")
    conf = float(detection.get("confidence", 1.0))
    lat = float(detection["lat"]) if detection.get("lat") is not None else None
    lon = float(detection["lon"]) if detection.get("lon") is not None else None

    raw_box = detection.get("bbox_json") or detection.get("box") or {}
    if isinstance(raw_box, dict) and "x" in raw_box:
        box_x = float(raw_box.get("x", 0.0))
        box_y = float(raw_box.get("y", 0.0))
        box_w = float(raw_box.get("w", 0.0))
        box_h = float(raw_box.get("h", 0.0))
        bbox_list = [box_x, box_y, box_w, box_h]
    elif isinstance(raw_box, (list, tuple)):
        bbox_list = list(raw_box)
        box_x = float(bbox_list[0]) if len(bbox_list) > 0 else 0.0
        box_y = float(bbox_list[1]) if len(bbox_list) > 1 else 0.0
        box_w = float(bbox_list[2]) if len(bbox_list) > 2 else 0.0
        box_h = float(bbox_list[3]) if len(bbox_list) > 3 else 0.0
    else:
        box_x = float(detection["box_x"]) if detection.get("box_x") is not None else None
        box_y = float(detection["box_y"]) if detection.get("box_y") is not None else None
        box_w = float(detection["box_w"]) if detection.get("box_w") is not None else None
        box_h = float(detection["box_h"]) if detection.get("box_h") is not None else None
        bbox_list = [box_x or 0.0, box_y or 0.0, box_w or 0.0, box_h or 0.0]

    bbox_json = json.dumps(bbox_list)
    entity_id = str(detection.get("entity_id") or detection.get("entityId") or "")
    meta = detection.get("metadata") or detection.get("payload") or {}
    meta_json = json.dumps(meta) if not isinstance(meta, str) else meta

    with _lock, _sqlite_connect() as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(vision_detections)").fetchall()]
        has_entity_id = "entity_id" in cols
        has_class_label = "class_label" in cols
        has_class_name = "class_name" in cols
        has_bbox_json = "bbox_json" in cols
        has_box_coords = "box_x" in cols
        has_metadata = "metadata_json" in cols

        id_info = [c for c in conn.execute("PRAGMA table_info(vision_detections)").fetchall() if c[1] == "id"]
        is_int_pk = bool(id_info and "INT" in id_info[0][2].upper())

        fields = ["frame_id", "tick", "confidence", "lat", "lon", "created_at"]
        placeholders = ["?", "?", "?", "?", "?", "datetime('now')"]
        values = [frame_id, tick, conf, lat, lon]

        if not is_int_pk and det_id is not None:
            fields.insert(0, "id")
            placeholders.insert(0, "?")
            values.insert(0, str(det_id))
        elif not is_int_pk:
            fields.insert(0, "id")
            placeholders.insert(0, "?")
            det_id = f"DET-{tick}-{uuid.uuid4().hex[:6]}"
            values.insert(0, str(det_id))

        if has_class_name:
            fields.append("class_name")
            placeholders.append("?")
            values.append(cls_name)
        if has_class_label:
            fields.append("class_label")
            placeholders.append("?")
            values.append(cls_name)
        if has_bbox_json:
            fields.append("bbox_json")
            placeholders.append("?")
            values.append(bbox_json)
        if has_box_coords:
            fields.extend(["box_x", "box_y", "box_w", "box_h"])
            placeholders.extend(["?", "?", "?", "?"])
            values.extend([box_x, box_y, box_w, box_h])
        if has_entity_id:
            fields.append("entity_id")
            placeholders.append("?")
            values.append(entity_id)
        if has_metadata:
            fields.append("metadata_json")
            placeholders.append("?")
            values.append(meta_json)

        cursor = conn.execute(
            f"INSERT INTO vision_detections ({', '.join(fields)}) VALUES ({', '.join(placeholders)})",
            tuple(values),
        )
        if is_int_pk:
            det_id = cursor.lastrowid
        conn.commit()

    res = dict(detection)
    res["id"] = det_id
    res["frame_id"] = frame_id
    res["tick"] = tick
    res["class_name"] = cls_name
    res["class_label"] = cls_name
    res["confidence"] = conf
    res["bbox_json"] = bbox_list
    res["box"] = {"x": box_x, "y": box_y, "w": box_w, "h": box_h} if box_x is not None else bbox_list
    res["lat"] = lat
    res["lon"] = lon
    return res


def list_vision_detections(
    frame_id: str | None = None,
    tick: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Retrieve persisted vision detections."""
    query = "SELECT * FROM vision_detections WHERE 1=1"
    params: list[Any] = []
    if frame_id:
        query += " AND frame_id = ?"
        params.append(frame_id)
    if tick is not None:
        query += " AND tick = ?"
        params.append(tick)
    query += " ORDER BY tick DESC, created_at DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if "metadata_json" in d:
            d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        if "bbox_json" in d and d["bbox_json"]:
            bbox = json.loads(d["bbox_json"]) if isinstance(d["bbox_json"], str) else d["bbox_json"]
            d["bbox_json"] = bbox
            if isinstance(bbox, list) and len(bbox) >= 4 and "box" not in d:
                d["box"] = {"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]}
        elif "box_x" in d and d["box_x"] is not None and "box" not in d:
            d["box"] = {"x": d["box_x"], "y": d["box_y"], "w": d["box_w"], "h": d["box_h"]}
            d["bbox_json"] = [d["box_x"], d["box_y"], d["box_w"], d["box_h"]]
        if "class_label" in d and "class_name" not in d:
            d["class_name"] = d["class_label"]
        elif "class_name" in d and "class_label" not in d:
            d["class_label"] = d["class_name"]
        out.append(d)
    return out

get_vision_detections = list_vision_detections


def save_vision_track(track: dict[str, Any]) -> dict[str, Any]:
    """Persist or update a multi-frame vision track."""
    track_id = str(track.get("id") or track.get("track_id") or f"TRK-{uuid.uuid4().hex[:6]}")
    cls_name = str(track.get("class_name") or track.get("class_label") or track.get("label") or "military_vehicle")
    first_tick = int(track.get("first_tick", track.get("tick", 0)))
    last_tick = int(track.get("last_tick", track.get("tick", 0)))
    traj = track.get("trajectory") or track.get("trajectory_json") or track.get("history") or track.get("history_json") or []
    traj_json = json.dumps(traj) if not isinstance(traj, str) else traj
    status = str(track.get("status") or track.get("activity_state") or "active")

    frame_id = track.get("frame_id")
    lat = float(track["lat"]) if track.get("lat") is not None else None
    lon = float(track["lon"]) if track.get("lon") is not None else None
    velocity_mps = float(track.get("velocity_mps", 0.0))
    heading_deg = float(track.get("heading_deg", 0.0))
    meta = track.get("metadata", {})
    meta_json = json.dumps(meta) if not isinstance(meta, str) else meta

    with _lock, _sqlite_connect() as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(vision_tracks)").fetchall()]
        has_track_id = "track_id" in cols
        has_class_label = "class_label" in cols
        has_class_name = "class_name" in cols
        has_first_tick = "first_tick" in cols
        has_last_tick = "last_tick" in cols
        has_trajectory = "trajectory_json" in cols
        has_history = "history_json" in cols
        has_status = "status" in cols
        has_activity = "activity_state" in cols
        has_updated = "updated_at" in cols

        if has_track_id:
            existing = conn.execute("SELECT id FROM vision_tracks WHERE track_id = ? OR id = ?", (track_id, track_id)).fetchone()
        else:
            existing = conn.execute("SELECT id FROM vision_tracks WHERE id = ?", (track_id,)).fetchone()

        if existing:
            update_clauses = []
            update_vals = []
            if has_class_name:
                update_clauses.append("class_name = ?")
                update_vals.append(cls_name)
            if has_class_label:
                update_clauses.append("class_label = ?")
                update_vals.append(cls_name)
            if has_first_tick:
                update_clauses.append("first_tick = ?")
                update_vals.append(first_tick)
            if has_last_tick:
                update_clauses.append("last_tick = ?")
                update_vals.append(last_tick)
            if has_trajectory:
                update_clauses.append("trajectory_json = ?")
                update_vals.append(traj_json)
            if has_history:
                update_clauses.append("history_json = ?")
                update_vals.append(traj_json)
            if has_status:
                update_clauses.append("status = ?")
                update_vals.append(status)
            if has_activity:
                update_clauses.append("activity_state = ?")
                update_vals.append(status)
            if "frame_id" in cols:
                update_clauses.append("frame_id = ?")
                update_vals.append(frame_id)
            if "tick" in cols:
                update_clauses.append("tick = ?")
                update_vals.append(last_tick)
            if "lat" in cols:
                update_clauses.append("lat = ?")
                update_vals.append(lat)
            if "lon" in cols:
                update_clauses.append("lon = ?")
                update_vals.append(lon)
            if "velocity_mps" in cols:
                update_clauses.append("velocity_mps = ?")
                update_vals.append(velocity_mps)
            if "heading_deg" in cols:
                update_clauses.append("heading_deg = ?")
                update_vals.append(heading_deg)
            if "metadata_json" in cols:
                update_clauses.append("metadata_json = ?")
                update_vals.append(meta_json)
            if has_updated:
                update_clauses.append("updated_at = datetime('now')")

            where_clause = "track_id = ?" if has_track_id else "id = ?"
            update_vals.append(track_id)
            conn.execute(f"UPDATE vision_tracks SET {', '.join(update_clauses)} WHERE {where_clause}", tuple(update_vals))
        else:
            fields = ["created_at"]
            placeholders = ["datetime('now')"]
            values = []

            id_info = [c for c in conn.execute("PRAGMA table_info(vision_tracks)").fetchall() if c[1] == "id"]
            is_int_pk = bool(id_info and "INT" in id_info[0][2].upper())
            if not is_int_pk:
                fields.append("id")
                placeholders.append("?")
                values.append(track_id)

            if has_track_id:
                fields.append("track_id")
                placeholders.append("?")
                values.append(track_id)
            if has_class_name:
                fields.append("class_name")
                placeholders.append("?")
                values.append(cls_name)
            if has_class_label:
                fields.append("class_label")
                placeholders.append("?")
                values.append(cls_name)
            if has_first_tick:
                fields.append("first_tick")
                placeholders.append("?")
                values.append(first_tick)
            if has_last_tick:
                fields.append("last_tick")
                placeholders.append("?")
                values.append(last_tick)
            if has_trajectory:
                fields.append("trajectory_json")
                placeholders.append("?")
                values.append(traj_json)
            if has_history:
                fields.append("history_json")
                placeholders.append("?")
                values.append(traj_json)
            if has_status:
                fields.append("status")
                placeholders.append("?")
                values.append(status)
            if has_activity:
                fields.append("activity_state")
                placeholders.append("?")
                values.append(status)
            if "frame_id" in cols:
                fields.append("frame_id")
                placeholders.append("?")
                values.append(frame_id)
            if "tick" in cols:
                fields.append("tick")
                placeholders.append("?")
                values.append(last_tick)
            if "lat" in cols:
                fields.append("lat")
                placeholders.append("?")
                values.append(lat)
            if "lon" in cols:
                fields.append("lon")
                placeholders.append("?")
                values.append(lon)
            if "velocity_mps" in cols:
                fields.append("velocity_mps")
                placeholders.append("?")
                values.append(velocity_mps)
            if "heading_deg" in cols:
                fields.append("heading_deg")
                placeholders.append("?")
                values.append(heading_deg)
            if "metadata_json" in cols:
                fields.append("metadata_json")
                placeholders.append("?")
                values.append(meta_json)
            if has_updated:
                fields.append("updated_at")
                placeholders.append("datetime('now')")

            conn.execute(f"INSERT INTO vision_tracks ({', '.join(fields)}) VALUES ({', '.join(placeholders)})", tuple(values))
        conn.commit()

    track["id"] = track_id
    track["track_id"] = track_id
    track["class_name"] = cls_name
    track["class_label"] = cls_name
    track["first_tick"] = first_tick
    track["last_tick"] = last_tick
    track["trajectory_json"] = json.loads(traj_json) if isinstance(traj_json, str) else traj_json
    track["trajectory"] = track["trajectory_json"]
    track["history"] = track["trajectory_json"]
    track["status"] = status
    track["activity_state"] = status
    return track


def list_vision_tracks(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve persisted vision tracks."""
    with _lock, _sqlite_connect() as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(vision_tracks)").fetchall()]
        order_col = "updated_at" if "updated_at" in cols else "created_at"
        if status:
            status_col = "status" if "status" in cols else "activity_state"
            rows = conn.execute(
                f"SELECT * FROM vision_tracks WHERE {status_col} = ? ORDER BY {order_col} DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT * FROM vision_tracks ORDER BY {order_col} DESC LIMIT ?",
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if "history_json" in d:
            d["history"] = json.loads(d["history_json"]) if isinstance(d["history_json"], str) else d.get("history_json", [])
            d["trajectory_json"] = d["history"]
            d["trajectory"] = d["history"]
        elif "trajectory_json" in d:
            d["trajectory"] = json.loads(d["trajectory_json"]) if isinstance(d["trajectory_json"], str) else d.get("trajectory_json", [])
            d["trajectory_json"] = d["trajectory"]
            d["history"] = d["trajectory"]
        if "metadata_json" in d:
            d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        if "track_id" in d and d["track_id"]:
            if isinstance(d.get("id"), int) and isinstance(d["track_id"], str):
                d["id"] = d["track_id"]
        elif "id" in d and "track_id" not in d:
            d["track_id"] = d["id"]
        if "class_label" in d and "class_name" not in d:
            d["class_name"] = d["class_label"]
        elif "class_name" in d and "class_label" not in d:
            d["class_label"] = d["class_name"]
        if "activity_state" in d and "status" not in d:
            d["status"] = d["activity_state"]
        elif "status" in d and "activity_state" not in d:
            d["activity_state"] = d["status"]
        out.append(d)
    return out

get_vision_tracks = list_vision_tracks


def get_vision_track(track_id: str) -> dict[str, Any] | None:
    """Retrieve a single persisted vision track by its track_id or id."""
    with _lock, _sqlite_connect() as conn:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(vision_tracks)").fetchall()]
        if "track_id" in cols:
            row = conn.execute("SELECT * FROM vision_tracks WHERE track_id = ? OR id = ?", (track_id, track_id)).fetchone()
        else:
            row = conn.execute("SELECT * FROM vision_tracks WHERE id = ?", (track_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if "history_json" in d:
            d["history"] = json.loads(d["history_json"]) if isinstance(d["history_json"], str) else d.get("history_json", [])
            d["trajectory_json"] = d["history"]
            d["trajectory"] = d["history"]
        elif "trajectory_json" in d:
            d["trajectory"] = json.loads(d["trajectory_json"]) if isinstance(d["trajectory_json"], str) else d.get("trajectory_json", [])
            d["trajectory_json"] = d["trajectory"]
            d["history"] = d["trajectory"]
        if "metadata_json" in d:
            d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        if "track_id" in d and d["track_id"]:
            if isinstance(d.get("id"), int) and isinstance(d["track_id"], str):
                d["id"] = d["track_id"]
        elif "id" in d and "track_id" not in d:
            d["track_id"] = d["id"]
        if "class_label" in d and "class_name" not in d:
            d["class_name"] = d["class_label"]
        elif "class_name" in d and "class_label" not in d:
            d["class_label"] = d["class_name"]
        if "activity_state" in d and "status" not in d:
            d["status"] = d["activity_state"]
        elif "status" in d and "activity_state" not in d:
            d["activity_state"] = d["status"]
        return d


# ---------------------------------------------------------------------------
# Phase 3: Mission Copilot Sessions Persistence
# ---------------------------------------------------------------------------
def save_copilot_session(session_data: dict[str, Any]) -> dict[str, Any]:
    """Persist or update an interactive mission copilot session."""
    s_id = str(session_data.get("id") or f"copilot-{uuid.uuid4().hex[:8]}")
    mission_id = session_data.get("mission_id")
    title = str(session_data.get("title", "Tactical Copilot Session"))
    msgs = session_data.get("messages") or session_data.get("messages_json") or []
    msgs_json = json.dumps(msgs) if not isinstance(msgs, str) else msgs
    props = session_data.get("proposals") or session_data.get("proposals_json") or []
    props_json = json.dumps(props) if not isinstance(props, str) else props
    status = str(session_data.get("status", "active"))
    approved_by = session_data.get("approved_by")

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO copilot_sessions
              (id, mission_id, title, messages_json, proposals_json, status, approved_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              mission_id     = excluded.mission_id,
              title          = excluded.title,
              messages_json  = excluded.messages_json,
              proposals_json = excluded.proposals_json,
              status         = excluded.status,
              approved_by    = excluded.approved_by
            """,
            (s_id, mission_id, title, msgs_json, props_json, status, approved_by),
        )
        conn.commit()

    return get_copilot_session(s_id) or {
        "id": s_id,
        "mission_id": mission_id,
        "title": title,
        "messages": json.loads(msgs_json) if isinstance(msgs_json, str) else msgs_json,
        "messages_json": json.loads(msgs_json) if isinstance(msgs_json, str) else msgs_json,
        "proposals": json.loads(props_json) if isinstance(props_json, str) else props_json,
        "proposals_json": json.loads(props_json) if isinstance(props_json, str) else props_json,
        "status": status,
        "approved_by": approved_by,
    }


def get_copilot_session(session_id: str) -> dict[str, Any] | None:
    """Retrieve persisted copilot session by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM copilot_sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["messages"] = json.loads(d["messages_json"]) if isinstance(d["messages_json"], str) else d.get("messages_json", [])
        d["messages_json"] = d["messages"]
        d["proposals"] = json.loads(d["proposals_json"]) if isinstance(d["proposals_json"], str) else d.get("proposals_json", [])
        d["proposals_json"] = d["proposals"]
        return d


def list_copilot_sessions(mission_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve copilot sessions, optionally filtered by mission_id."""
    with _lock, _sqlite_connect() as conn:
        if mission_id:
            rows = conn.execute(
                "SELECT * FROM copilot_sessions WHERE mission_id = ? ORDER BY created_at DESC LIMIT ?",
                (mission_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM copilot_sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["messages"] = json.loads(d["messages_json"]) if isinstance(d["messages_json"], str) else d.get("messages_json", [])
        d["messages_json"] = d["messages"]
        d["proposals"] = json.loads(d["proposals_json"]) if isinstance(d["proposals_json"], str) else d.get("proposals_json", [])
        d["proposals_json"] = d["proposals"]
        out.append(d)
    return out


def update_copilot_session_status(session_id: str, new_status: str, approved_by: str | None = None) -> dict[str, Any] | None:
    """Transition copilot session status and record approver."""
    session = get_copilot_session(session_id)
    if not session:
        return None
    with _lock, _sqlite_connect() as conn:
        if approved_by:
            conn.execute(
                "UPDATE copilot_sessions SET status = ?, approved_by = ? WHERE id = ?",
                (new_status, approved_by, session_id),
            )
        else:
            conn.execute(
                "UPDATE copilot_sessions SET status = ? WHERE id = ?",
                (new_status, session_id),
            )
        conn.commit()
    return get_copilot_session(session_id)


# ---------------------------------------------------------------------------
# Phase 3: Comparative Replay & Turning Point Reports Persistence
# ---------------------------------------------------------------------------
def save_replay_report(report_data: dict[str, Any]) -> dict[str, Any]:
    """Persist or update an after-action comparative replay report."""
    r_id = str(report_data.get("id") or f"rep-{uuid.uuid4().hex[:8]}")
    run_id = str(report_data.get("run_id", "run-001"))
    comparison_run_id = report_data.get("comparison_run_id")
    summary = str(report_data.get("summary", ""))
    t_points = report_data.get("turning_points") or report_data.get("turning_points_json") or []
    t_points_json = json.dumps(t_points) if not isinstance(t_points, str) else t_points
    kpi_deltas = report_data.get("kpi_deltas") or report_data.get("kpi_deltas_json") or {}
    kpi_deltas_json = json.dumps(kpi_deltas) if not isinstance(kpi_deltas, str) else kpi_deltas

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO replay_reports
              (id, run_id, comparison_run_id, summary, turning_points_json, kpi_deltas_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              run_id              = excluded.run_id,
              comparison_run_id   = excluded.comparison_run_id,
              summary             = excluded.summary,
              turning_points_json = excluded.turning_points_json,
              kpi_deltas_json     = excluded.kpi_deltas_json
            """,
            (r_id, run_id, comparison_run_id, summary, t_points_json, kpi_deltas_json),
        )
        conn.commit()

    return get_replay_report(r_id) or {
        "id": r_id,
        "run_id": run_id,
        "comparison_run_id": comparison_run_id,
        "summary": summary,
        "turning_points": json.loads(t_points_json) if isinstance(t_points_json, str) else t_points_json,
        "turning_points_json": json.loads(t_points_json) if isinstance(t_points_json, str) else t_points_json,
        "kpi_deltas": json.loads(kpi_deltas_json) if isinstance(kpi_deltas_json, str) else kpi_deltas_json,
        "kpi_deltas_json": json.loads(kpi_deltas_json) if isinstance(kpi_deltas_json, str) else kpi_deltas_json,
    }


def get_replay_report(report_id: str) -> dict[str, Any] | None:
    """Retrieve persisted replay report by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM replay_reports WHERE id = ?", (report_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["turning_points"] = json.loads(d["turning_points_json"]) if isinstance(d["turning_points_json"], str) else d.get("turning_points_json", [])
        d["turning_points_json"] = d["turning_points"]
        d["kpi_deltas"] = json.loads(d["kpi_deltas_json"]) if isinstance(d["kpi_deltas_json"], str) else d.get("kpi_deltas_json", {})
        d["kpi_deltas_json"] = d["kpi_deltas"]
        return d


def list_replay_reports(run_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve replay reports, optionally filtered by run_id."""
    with _lock, _sqlite_connect() as conn:
        if run_id:
            rows = conn.execute(
                "SELECT * FROM replay_reports WHERE run_id = ? ORDER BY created_at DESC LIMIT ?",
                (run_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM replay_reports ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["turning_points"] = json.loads(d["turning_points_json"]) if isinstance(d["turning_points_json"], str) else d.get("turning_points_json", [])
        d["turning_points_json"] = d["turning_points"]
        d["kpi_deltas"] = json.loads(d["kpi_deltas_json"]) if isinstance(d["kpi_deltas_json"], str) else d.get("kpi_deltas_json", {})
        d["kpi_deltas_json"] = d["kpi_deltas"]
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 4: Federated Nodes Persistence
# ---------------------------------------------------------------------------
def save_federation_node(node_data: dict[str, Any]) -> dict[str, Any]:
    """Persist or heartbeat a federation command node."""
    n_id = str(node_data.get("id") or f"node-{uuid.uuid4().hex[:6]}")
    name = str(node_data.get("name", n_id))
    tier = str(node_data.get("tier", "tactical"))
    region = str(node_data.get("region", "GLOBAL"))
    endpoint = str(node_data.get("endpoint", ""))
    status = str(node_data.get("status", "online"))
    meta = node_data.get("metadata") or node_data.get("metadata_json") or {}
    meta_json = json.dumps(meta) if not isinstance(meta, str) else meta

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO federation_nodes (id, name, tier, region, endpoint, status, heartbeat_at, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              name          = excluded.name,
              tier          = excluded.tier,
              region        = excluded.region,
              endpoint      = excluded.endpoint,
              status        = excluded.status,
              heartbeat_at  = datetime('now'),
              metadata_json = excluded.metadata_json
            """,
            (n_id, name, tier, region, endpoint, status, meta_json),
        )
        conn.commit()
    return get_federation_node(n_id) or node_data


def get_federation_node(node_id: str) -> dict[str, Any] | None:
    """Retrieve federation node by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM federation_nodes WHERE id = ?", (node_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        return d


def list_federation_nodes(tier: str | None = None, region: str | None = None) -> list[dict[str, Any]]:
    """Retrieve federation nodes optionally filtered by tier or region."""
    query = "SELECT * FROM federation_nodes WHERE 1=1"
    params: list[Any] = []
    if tier:
        query += " AND tier = ?"
        params.append(tier)
    if region:
        query += " AND region = ?"
        params.append(region)
    query += " ORDER BY tier ASC, name ASC"

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 4: Operational Theaters & Worlds Persistence
# ---------------------------------------------------------------------------
def save_theater(theater_data: dict[str, Any]) -> dict[str, Any]:
    """Persist an operational geographic theater."""
    t_id = str(theater_data.get("id") or f"THEATER-{uuid.uuid4().hex[:6].upper()}")
    name = str(theater_data.get("name", t_id))
    code = str(theater_data.get("code") or t_id.replace("THEATER-", ""))
    bounds = theater_data.get("bounds") or theater_data.get("bounds_json") or []
    bounds_json = json.dumps(bounds) if not isinstance(bounds, str) else bounds
    active_world_id = theater_data.get("active_world_id")
    status = str(theater_data.get("status", "active"))

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO theaters (id, name, code, bounds_json, active_world_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              name            = excluded.name,
              code            = excluded.code,
              bounds_json     = excluded.bounds_json,
              active_world_id = excluded.active_world_id,
              status          = excluded.status
            """,
            (t_id, name, code, bounds_json, active_world_id, status),
        )
        conn.commit()
    return get_theater(t_id) or theater_data


def get_theater(theater_id: str) -> dict[str, Any] | None:
    """Retrieve operational theater by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM theaters WHERE id = ? OR code = ?", (theater_id, theater_id)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["bounds"] = json.loads(d["bounds_json"]) if isinstance(d["bounds_json"], str) else d.get("bounds_json", [])
        return d


def list_theaters() -> list[dict[str, Any]]:
    """List all registered operational theaters."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute("SELECT * FROM theaters ORDER BY code ASC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["bounds"] = json.loads(d["bounds_json"]) if isinstance(d["bounds_json"], str) else d.get("bounds_json", [])
        out.append(d)
    return out


def save_world(world_data: dict[str, Any]) -> dict[str, Any]:
    """Persist an independent simulation world."""
    w_id = str(world_data.get("id") or f"WLD-{uuid.uuid4().hex[:6].upper()}")
    theater_id = str(world_data.get("theater_id", "THEATER-NORTH"))
    name = str(world_data.get("name", w_id))
    tick = int(world_data.get("tick", 0))
    status = str(world_data.get("status", "running"))
    snap = world_data.get("state_snapshot") or world_data.get("state_snapshot_json") or {}
    snap_json = json.dumps(snap) if not isinstance(snap, str) else snap

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO worlds (id, theater_id, name, tick, status, state_snapshot_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              theater_id          = excluded.theater_id,
              name                = excluded.name,
              tick                = excluded.tick,
              status              = excluded.status,
              state_snapshot_json = excluded.state_snapshot_json
            """,
            (w_id, theater_id, name, tick, status, snap_json),
        )
        conn.commit()
    return get_world(w_id) or world_data


def get_world(world_id: str) -> dict[str, Any] | None:
    """Retrieve simulation world by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM worlds WHERE id = ?", (world_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["state_snapshot"] = json.loads(d["state_snapshot_json"]) if isinstance(d["state_snapshot_json"], str) else d.get("state_snapshot_json", {})
        return d


def list_worlds(theater_id: str | None = None) -> list[dict[str, Any]]:
    """List simulation worlds optionally filtered by theater."""
    query = "SELECT * FROM worlds WHERE 1=1"
    params: list[Any] = []
    if theater_id:
        query += " AND theater_id = ?"
        params.append(theater_id)
    query += " ORDER BY created_at DESC"

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["state_snapshot"] = json.loads(d["state_snapshot_json"]) if isinstance(d["state_snapshot_json"], str) else d.get("state_snapshot_json", {})
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 4: Strategic Campaigns & Reports Persistence
# ---------------------------------------------------------------------------
def save_campaign(campaign_data: dict[str, Any]) -> dict[str, Any]:
    """Persist strategic multi-theater campaign."""
    c_id = str(campaign_data.get("id") or f"CMP-{uuid.uuid4().hex[:6].upper()}")
    title = str(campaign_data.get("title", "Strategic Campaign"))
    t_ids = campaign_data.get("theater_ids") or campaign_data.get("theater_ids_json") or []
    t_ids_json = json.dumps(t_ids) if not isinstance(t_ids, str) else t_ids
    status = str(campaign_data.get("status", "draft"))
    objs = campaign_data.get("objectives") or campaign_data.get("objectives_json") or []
    objs_json = json.dumps(objs) if not isinstance(objs, str) else objs

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO campaigns (id, title, theater_ids_json, status, objectives_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              title            = excluded.title,
              theater_ids_json = excluded.theater_ids_json,
              status           = excluded.status,
              objectives_json  = excluded.objectives_json,
              updated_at       = datetime('now')
            """,
            (c_id, title, t_ids_json, status, objs_json),
        )
        conn.commit()
    return get_campaign(c_id) or campaign_data


def get_campaign(campaign_id: str) -> dict[str, Any] | None:
    """Retrieve strategic campaign by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["theater_ids"] = json.loads(d["theater_ids_json"]) if isinstance(d["theater_ids_json"], str) else d.get("theater_ids_json", [])
        d["objectives"] = json.loads(d["objectives_json"]) if isinstance(d["objectives_json"], str) else d.get("objectives_json", [])
        return d


def list_campaigns(limit: int = 50) -> list[dict[str, Any]]:
    """List strategic campaigns."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute("SELECT * FROM campaigns ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["theater_ids"] = json.loads(d["theater_ids_json"]) if isinstance(d["theater_ids_json"], str) else d.get("theater_ids_json", [])
        d["objectives"] = json.loads(d["objectives_json"]) if isinstance(d["objectives_json"], str) else d.get("objectives_json", [])
        out.append(d)
    return out


def update_campaign_status(campaign_id: str, new_status: str) -> dict[str, Any] | None:
    """Update campaign status."""
    with _lock, _sqlite_connect() as conn:
        conn.execute("UPDATE campaigns SET status = ?, updated_at = datetime('now') WHERE id = ?", (new_status, campaign_id))
        conn.commit()
    return get_campaign(campaign_id)


def save_strategic_report(report_data: dict[str, Any]) -> dict[str, Any]:
    """Persist strategic readiness and risk report."""
    r_id = str(report_data.get("id") or f"SRPT-{uuid.uuid4().hex[:6].upper()}")
    c_id = report_data.get("campaign_id")
    title = str(report_data.get("title", "Strategic Assessment"))
    brief = str(report_data.get("brief_text", ""))
    readiness = float(report_data.get("readiness_score", 85.0))
    risk = float(report_data.get("risk_score", 25.0))
    outlook = report_data.get("outlook") or report_data.get("outlook_json") or {}
    outlook_json = json.dumps(outlook) if not isinstance(outlook, str) else outlook

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO strategic_reports (id, campaign_id, title, brief_text, readiness_score, risk_score, outlook_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              campaign_id     = excluded.campaign_id,
              title           = excluded.title,
              brief_text      = excluded.brief_text,
              readiness_score = excluded.readiness_score,
              risk_score      = excluded.risk_score,
              outlook_json    = excluded.outlook_json
            """,
            (r_id, c_id, title, brief, readiness, risk, outlook_json),
        )
        conn.commit()
    return get_strategic_report(r_id) or report_data


def get_strategic_report(report_id: str) -> dict[str, Any] | None:
    """Retrieve strategic report by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM strategic_reports WHERE id = ?", (report_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["outlook"] = json.loads(d["outlook_json"]) if isinstance(d["outlook_json"], str) else d.get("outlook_json", {})
        return d


def list_strategic_reports(campaign_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List strategic reports."""
    query = "SELECT * FROM strategic_reports WHERE 1=1"
    params: list[Any] = []
    if campaign_id:
        query += " AND campaign_id = ?"
        params.append(campaign_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["outlook"] = json.loads(d["outlook_json"]) if isinstance(d["outlook_json"], str) else d.get("outlook_json", {})
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 4: Autonomous Future Branches Persistence
# ---------------------------------------------------------------------------
def save_future_branch(branch_data: dict[str, Any]) -> dict[str, Any]:
    """Persist an autonomous Monte Carlo future simulation branch."""
    b_id = str(branch_data.get("id") or f"FUT-{uuid.uuid4().hex[:6].upper()}")
    w_id = str(branch_data.get("baseline_world_id", "WLD-DEFAULT"))
    seed = int(branch_data.get("branch_seed", 42))
    ticks = int(branch_data.get("ticks", 120))
    rank = int(branch_data.get("outcome_rank", 1))
    outcome = branch_data.get("outcome") or branch_data.get("outcome_json") or {}
    outcome_json = json.dumps(outcome) if not isinstance(outcome, str) else outcome
    risk_band = str(branch_data.get("risk_band", "P50"))

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO future_branches (id, baseline_world_id, branch_seed, ticks, outcome_rank, outcome_json, risk_band, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              baseline_world_id = excluded.baseline_world_id,
              branch_seed       = excluded.branch_seed,
              ticks             = excluded.ticks,
              outcome_rank      = excluded.outcome_rank,
              outcome_json      = excluded.outcome_json,
              risk_band         = excluded.risk_band
            """,
            (b_id, w_id, seed, ticks, rank, outcome_json, risk_band),
        )
        conn.commit()
    branch_data["id"] = b_id
    return branch_data


def list_future_branches(baseline_world_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List generated future simulation branches."""
    query = "SELECT * FROM future_branches WHERE 1=1"
    params: list[Any] = []
    if baseline_world_id:
        query += " AND baseline_world_id = ?"
        params.append(baseline_world_id)
    query += " ORDER BY outcome_rank ASC, created_at DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["outcome"] = json.loads(d["outcome_json"]) if isinstance(d["outcome_json"], str) else d.get("outcome_json", {})
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 4: Event Streams & Data Lake Objects Persistence
# ---------------------------------------------------------------------------
def save_stream_event(stream_name: str, event_type: str, payload: dict[str, Any], offset: int | None = None, partition: int = 0) -> dict[str, Any]:
    """Append event to enterprise event stream buffer."""
    p_json = json.dumps(payload) if not isinstance(payload, str) else payload
    with _lock, _sqlite_connect() as conn:
        if offset is None:
            max_off = conn.execute("SELECT MAX(offset) FROM event_streams WHERE stream_name = ?", (stream_name,)).fetchone()[0]
            off_val = (max_off or 0) + 1
        else:
            off_val = offset
        cur = conn.execute(
            """
            INSERT INTO event_streams (stream_name, offset, partition, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (stream_name, off_val, partition, event_type, p_json),
        )
        conn.commit()
        last_id = cur.lastrowid

    return {
        "id": last_id,
        "stream_name": stream_name,
        "offset": off_val,
        "partition": partition,
        "event_type": event_type,
        "payload": payload,
    }


def list_stream_events(stream_name: str, from_offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    """Read slice of event stream ordered by offset."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(
            "SELECT * FROM event_streams WHERE stream_name = ? AND offset >= ? ORDER BY offset ASC LIMIT ?",
            (stream_name, from_offset, limit),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload_json"]) if isinstance(d["payload_json"], str) else d.get("payload_json", {})
        out.append(d)
    return out


def save_datalake_object(obj_data: dict[str, Any]) -> dict[str, Any]:
    """Record an object in the operational data lake metadata catalog."""
    o_id = str(obj_data.get("id") or f"obj-{uuid.uuid4().hex[:8]}")
    bucket = str(obj_data.get("bucket", "simulations"))
    key = str(obj_data.get("key", o_id))
    c_type = str(obj_data.get("content_type", "application/json"))
    size_b = int(obj_data.get("size_bytes", 0))
    etag = obj_data.get("etag") or uuid.uuid4().hex[:16]
    meta = obj_data.get("metadata") or obj_data.get("metadata_json") or {}
    meta_json = json.dumps(meta) if not isinstance(meta, str) else meta

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO data_lake_objects (id, bucket, key, content_type, size_bytes, etag, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              bucket        = excluded.bucket,
              key           = excluded.key,
              content_type  = excluded.content_type,
              size_bytes    = excluded.size_bytes,
              etag          = excluded.etag,
              metadata_json = excluded.metadata_json
            """,
            (o_id, bucket, key, c_type, size_b, etag, meta_json),
        )
        conn.commit()
    return get_datalake_object(o_id) or obj_data


def get_datalake_object(object_id: str) -> dict[str, Any] | None:
    """Retrieve data lake object metadata by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM data_lake_objects WHERE id = ?", (object_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        return d


def list_datalake_objects(bucket: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """List data lake objects, optionally filtered by bucket."""
    query = "SELECT * FROM data_lake_objects WHERE 1=1"
    params: list[Any] = []
    if bucket:
        query += " AND bucket = ?"
        params.append(bucket)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase 5: Unified Platform Database Operations
# ---------------------------------------------------------------------------


def save_agent(agent_data: dict[str, Any]) -> dict[str, Any]:
    """Register or update an agent in the unified runtime registry."""
    a_id = str(agent_data.get("id") or f"agent-{uuid.uuid4().hex[:8]}")
    name = str(agent_data.get("name", a_id))
    role = str(agent_data.get("role", "general"))
    status = str(agent_data.get("status", "idle"))
    caps = agent_data.get("capabilities") or agent_data.get("capabilities_json") or []
    caps_json = json.dumps(caps) if not isinstance(caps, str) else caps
    meta = agent_data.get("metadata") or agent_data.get("metadata_json") or {}
    meta_json = json.dumps(meta) if not isinstance(meta, str) else meta

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO agents (id, name, role, status, capabilities_json, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              role = excluded.role,
              status = excluded.status,
              capabilities_json = excluded.capabilities_json,
              metadata_json = excluded.metadata_json,
              updated_at = datetime('now')
            """,
            (a_id, name, role, status, caps_json, meta_json),
        )
        conn.commit()
    return get_agent(a_id) or agent_data


def get_agent(agent_id: str) -> dict[str, Any] | None:
    """Retrieve an agent record by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["capabilities"] = json.loads(d["capabilities_json"]) if isinstance(d["capabilities_json"], str) else d.get("capabilities_json", [])
        d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        return d


def list_agents(status: str | None = None, role: str | None = None) -> list[dict[str, Any]]:
    """List agents optionally filtered by status or role."""
    query = "SELECT * FROM agents WHERE 1=1"
    params: list[Any] = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if role:
        query += " AND role = ?"
        params.append(role)
    query += " ORDER BY role ASC, name ASC"

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["capabilities"] = json.loads(d["capabilities_json"]) if isinstance(d["capabilities_json"], str) else d.get("capabilities_json", [])
        d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        out.append(d)
    return out


def save_agent_task(task_data: dict[str, Any]) -> dict[str, Any]:
    """Queue or save an agent execution task."""
    t_id = str(task_data.get("id") or f"task-{uuid.uuid4().hex[:8]}")
    agent_id = task_data.get("agent_id")
    task_type = str(task_data.get("task_type", "generic"))
    payload = task_data.get("payload") or task_data.get("payload_json") or {}
    payload_json = json.dumps(payload) if not isinstance(payload, str) else payload
    result = task_data.get("result") or task_data.get("result_json")
    result_json = json.dumps(result) if result is not None and not isinstance(result, str) else result
    status = str(task_data.get("status", "pending"))

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO agent_tasks (id, agent_id, task_type, payload_json, result_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              agent_id = excluded.agent_id,
              task_type = excluded.task_type,
              payload_json = excluded.payload_json,
              result_json = excluded.result_json,
              status = excluded.status
            """,
            (t_id, agent_id, task_type, payload_json, result_json, status),
        )
        conn.commit()
    return get_agent_task(t_id) or task_data


def get_agent_task(task_id: str) -> dict[str, Any] | None:
    """Retrieve an agent task by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM agent_tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["payload"] = json.loads(d["payload_json"]) if isinstance(d["payload_json"], str) else d.get("payload_json", {})
        d["result"] = json.loads(d["result_json"]) if isinstance(d.get("result_json"), str) else d.get("result_json")
        return d


def list_agent_tasks(agent_id: str | None = None, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List agent tasks filtered by agent or status."""
    query = "SELECT * FROM agent_tasks WHERE 1=1"
    params: list[Any] = []
    if agent_id:
        query += " AND agent_id = ?"
        params.append(agent_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload_json"]) if isinstance(d["payload_json"], str) else d.get("payload_json", {})
        d["result"] = json.loads(d["result_json"]) if isinstance(d.get("result_json"), str) else d.get("result_json")
        out.append(d)
    return out


def update_agent_task_status(task_id: str, status: str, result: dict | None = None) -> bool:
    """Update agent task status and completed timestamp."""
    result_json = json.dumps(result) if result is not None and not isinstance(result, str) else result
    with _lock, _sqlite_connect() as conn:
        if status in ("completed", "failed"):
            conn.execute(
                "UPDATE agent_tasks SET status = ?, result_json = ?, completed_at = datetime('now') WHERE id = ?",
                (status, result_json, task_id),
            )
        else:
            conn.execute(
                "UPDATE agent_tasks SET status = ?, result_json = ? WHERE id = ?",
                (status, result_json, task_id),
            )
        conn.commit()
    return True


def save_agent_memory(memory_data: dict[str, Any]) -> dict[str, Any]:
    """Persist an agent memory record."""
    m_id = str(memory_data.get("id") or f"mem-{uuid.uuid4().hex[:8]}")
    agent_id = memory_data.get("agent_id")
    memory_type = str(memory_data.get("memory_type", "semantic"))
    content = str(memory_data.get("content", ""))
    tags = memory_data.get("tags") or memory_data.get("tags_json") or []
    tags_json = json.dumps(tags) if not isinstance(tags, str) else tags
    importance = float(memory_data.get("importance", 1.0))

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO agent_memories (id, agent_id, memory_type, content, tags_json, importance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              content = excluded.content,
              tags_json = excluded.tags_json,
              importance = excluded.importance
            """,
            (m_id, agent_id, memory_type, content, tags_json, importance),
        )
        conn.commit()
    memory_data["id"] = m_id
    return memory_data


def list_agent_memories(agent_id: str | None = None, memory_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List agent memory records."""
    query = "SELECT * FROM agent_memories WHERE 1=1"
    params: list[Any] = []
    if agent_id:
        query += " AND agent_id = ?"
        params.append(agent_id)
    if memory_type:
        query += " AND memory_type = ?"
        params.append(memory_type)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags_json"]) if isinstance(d["tags_json"], str) else d.get("tags_json", [])
        out.append(d)
    return out


def search_agent_memories(query_str: str, agent_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Simple keyword/substring search across agent memories."""
    sql = "SELECT * FROM agent_memories WHERE content LIKE ?"
    params: list[Any] = [f"%{query_str}%"]
    if agent_id:
        sql += " AND agent_id = ?"
        params.append(agent_id)
    sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags_json"]) if isinstance(d["tags_json"], str) else d.get("tags_json", [])
        out.append(d)
    return out


def save_analysis_finding(finding_data: dict[str, Any]) -> dict[str, Any]:
    """Record an autonomous analysis finding."""
    f_id = str(finding_data.get("id") or f"find-{uuid.uuid4().hex[:8]}")
    category = str(finding_data.get("category", "anomaly"))
    severity = str(finding_data.get("severity", "medium"))
    title = str(finding_data.get("title", "Finding"))
    details = finding_data.get("details") or finding_data.get("details_json") or {}
    details_json = json.dumps(details) if not isinstance(details, str) else details

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_findings (id, category, severity, title, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              category = excluded.category,
              severity = excluded.severity,
              title = excluded.title,
              details_json = excluded.details_json
            """,
            (f_id, category, severity, title, details_json),
        )
        conn.commit()
    finding_data["id"] = f_id
    return finding_data


def list_analysis_findings(category: str | None = None, severity: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List autonomous analysis findings."""
    query = "SELECT * FROM analysis_findings WHERE 1=1"
    params: list[Any] = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["details"] = json.loads(d["details_json"]) if isinstance(d["details_json"], str) else d.get("details_json", {})
        out.append(d)
    return out


def save_forecast_matrix(matrix_data: dict[str, Any]) -> dict[str, Any]:
    """Persist large-scale forecast matrix and risk tensors."""
    m_id = str(matrix_data.get("id") or f"fmat-{uuid.uuid4().hex[:8]}")
    horizon_hours = float(matrix_data.get("horizon_hours", 4.0))
    matrix = matrix_data.get("matrix") or matrix_data.get("matrix_json") or {}
    matrix_json = json.dumps(matrix) if not isinstance(matrix, str) else matrix
    risk = matrix_data.get("risk_tensor") or matrix_data.get("risk_tensor_json") or {}
    risk_json = json.dumps(risk) if not isinstance(risk, str) else risk
    summary = str(matrix_data.get("summary", ""))

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO forecast_matrices (id, horizon_hours, matrix_json, risk_tensor_json, summary, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              horizon_hours = excluded.horizon_hours,
              matrix_json = excluded.matrix_json,
              risk_tensor_json = excluded.risk_tensor_json,
              summary = excluded.summary
            """,
            (m_id, horizon_hours, matrix_json, risk_json, summary),
        )
        conn.commit()
    return get_forecast_matrix(m_id) or matrix_data


def get_forecast_matrix(matrix_id: str) -> dict[str, Any] | None:
    """Retrieve forecast matrix by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM forecast_matrices WHERE id = ?", (matrix_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["matrix"] = json.loads(d["matrix_json"]) if isinstance(d["matrix_json"], str) else d.get("matrix_json", {})
        d["risk_tensor"] = json.loads(d["risk_tensor_json"]) if isinstance(d["risk_tensor_json"], str) else d.get("risk_tensor_json", {})
        return d


def list_forecast_matrices(limit: int = 20) -> list[dict[str, Any]]:
    """List forecast matrices ordered by creation date."""
    with _lock, _sqlite_connect() as conn:
        rows = conn.execute("SELECT * FROM forecast_matrices ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["matrix"] = json.loads(d["matrix_json"]) if isinstance(d["matrix_json"], str) else d.get("matrix_json", {})
        d["risk_tensor"] = json.loads(d["risk_tensor_json"]) if isinstance(d["risk_tensor_json"], str) else d.get("risk_tensor_json", {})
        out.append(d)
    return out


def save_scenario_outcome(outcome_data: dict[str, Any]) -> dict[str, Any]:
    """Save an individual scenario outcome from massive what-if engine."""
    o_id = str(outcome_data.get("id") or f"out-{uuid.uuid4().hex[:8]}")
    batch_id = str(outcome_data.get("batch_id", "batch-default"))
    scenario_seed = int(outcome_data.get("scenario_seed", 0))
    score = float(outcome_data.get("score", 0.0))
    rank = int(outcome_data.get("rank", 1))
    outcome = outcome_data.get("outcome") or outcome_data.get("outcome_json") or {}
    outcome_json = json.dumps(outcome) if not isinstance(outcome, str) else outcome

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO scenario_outcomes (id, batch_id, scenario_seed, score, rank, outcome_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              score = excluded.score,
              rank = excluded.rank,
              outcome_json = excluded.outcome_json
            """,
            (o_id, batch_id, scenario_seed, score, rank, outcome_json),
        )
        conn.commit()
    outcome_data["id"] = o_id
    return outcome_data


def list_scenario_outcomes(batch_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List scenario outcomes optionally filtered by batch_id."""
    query = "SELECT * FROM scenario_outcomes WHERE 1=1"
    params: list[Any] = []
    if batch_id:
        query += " AND batch_id = ?"
        params.append(batch_id)
    query += " ORDER BY score DESC, rank ASC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["outcome"] = json.loads(d["outcome_json"]) if isinstance(d["outcome_json"], str) else d.get("outcome_json", {})
        out.append(d)
    return out


def save_model_record(model_data: dict[str, Any]) -> dict[str, Any]:
    """Register or update an AI model in model registry."""
    m_id = str(model_data.get("id") or f"model-{uuid.uuid4().hex[:8]}")
    name = str(model_data.get("name", m_id))
    provider = str(model_data.get("provider", "ollama"))
    model_type = str(model_data.get("model_type", "llm"))
    endpoint = model_data.get("endpoint")
    is_active = 1 if model_data.get("is_active", True) else 0
    meta = model_data.get("metadata") or model_data.get("metadata_json") or {}
    meta_json = json.dumps(meta) if not isinstance(meta, str) else meta

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO model_registry (id, name, provider, model_type, endpoint, is_active, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              provider = excluded.provider,
              model_type = excluded.model_type,
              endpoint = excluded.endpoint,
              is_active = excluded.is_active,
              metadata_json = excluded.metadata_json
            """,
            (m_id, name, provider, model_type, endpoint, is_active, meta_json),
        )
        conn.commit()
    return get_model_record(m_id) or model_data


def get_model_record(model_id: str) -> dict[str, Any] | None:
    """Retrieve model registry record by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM model_registry WHERE id = ?", (model_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        d["is_active"] = bool(d["is_active"])
        return d


def list_model_records(provider: str | None = None, model_type: str | None = None) -> list[dict[str, Any]]:
    """List model records in the registry."""
    query = "SELECT * FROM model_registry WHERE 1=1"
    params: list[Any] = []
    if provider:
        query += " AND provider = ?"
        params.append(provider)
    if model_type:
        query += " AND model_type = ?"
        params.append(model_type)
    query += " ORDER BY model_type ASC, name ASC"

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d["metadata_json"]) if isinstance(d["metadata_json"], str) else d.get("metadata_json", {})
        d["is_active"] = bool(d["is_active"])
        out.append(d)
    return out


def save_workflow_instance(wf_data: dict[str, Any]) -> dict[str, Any]:
    """Persist or update workflow instance."""
    w_id = str(wf_data.get("id") or f"wf-{uuid.uuid4().hex[:8]}")
    workflow_type = str(wf_data.get("workflow_type", "mission"))
    title = str(wf_data.get("title", w_id))
    current_step = str(wf_data.get("current_step", "start"))
    steps = wf_data.get("steps") or wf_data.get("steps_json") or []
    steps_json = json.dumps(steps) if not isinstance(steps, str) else steps
    status = str(wf_data.get("status", "staged"))
    req_human = 1 if wf_data.get("requires_human_confirmation", True) else 0
    approved_by = wf_data.get("approved_by")

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO workflow_instances (id, workflow_type, title, current_step, steps_json, status, requires_human_confirmation, approved_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              title = excluded.title,
              current_step = excluded.current_step,
              steps_json = excluded.steps_json,
              status = excluded.status,
              requires_human_confirmation = excluded.requires_human_confirmation,
              approved_by = excluded.approved_by,
              updated_at = datetime('now')
            """,
            (w_id, workflow_type, title, current_step, steps_json, status, req_human, approved_by),
        )
        conn.commit()
    return get_workflow_instance(w_id) or wf_data


def get_workflow_instance(workflow_id: str) -> dict[str, Any] | None:
    """Retrieve workflow instance by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM workflow_instances WHERE id = ?", (workflow_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["steps"] = json.loads(d["steps_json"]) if isinstance(d["steps_json"], str) else d.get("steps_json", [])
        d["requires_human_confirmation"] = bool(d["requires_human_confirmation"])
        return d


def list_workflow_instances(status: str | None = None, workflow_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List workflow instances."""
    query = "SELECT * FROM workflow_instances WHERE 1=1"
    params: list[Any] = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if workflow_type:
        query += " AND workflow_type = ?"
        params.append(workflow_type)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["steps"] = json.loads(d["steps_json"]) if isinstance(d["steps_json"], str) else d.get("steps_json", [])
        d["requires_human_confirmation"] = bool(d["requires_human_confirmation"])
        out.append(d)
    return out


def update_workflow_status(workflow_id: str, status: str, step: str | None = None, approved_by: str | None = None) -> bool:
    """Update workflow status, current step, and human approval."""
    with _lock, _sqlite_connect() as conn:
        if step and approved_by:
            conn.execute(
                "UPDATE workflow_instances SET status = ?, current_step = ?, approved_by = ?, updated_at = datetime('now') WHERE id = ?",
                (status, step, approved_by, workflow_id),
            )
        elif step:
            conn.execute(
                "UPDATE workflow_instances SET status = ?, current_step = ?, updated_at = datetime('now') WHERE id = ?",
                (status, step, workflow_id),
            )
        elif approved_by:
            conn.execute(
                "UPDATE workflow_instances SET status = ?, approved_by = ?, updated_at = datetime('now') WHERE id = ?",
                (status, approved_by, workflow_id),
            )
        else:
            conn.execute(
                "UPDATE workflow_instances SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, workflow_id),
            )
        conn.commit()
    return True


def save_operational_report(report_data: dict[str, Any]) -> dict[str, Any]:
    """Persist an operational report."""
    r_id = str(report_data.get("id") or f"rep-{uuid.uuid4().hex[:8]}")
    report_type = str(report_data.get("report_type", "sitrep"))
    title = str(report_data.get("title", r_id))
    content_md = str(report_data.get("content_md", ""))
    data = report_data.get("data") or report_data.get("data_json") or {}
    data_json = json.dumps(data) if not isinstance(data, str) else data

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO operational_reports (id, report_type, title, content_md, data_json, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
              title = excluded.title,
              content_md = excluded.content_md,
              data_json = excluded.data_json
            """,
            (r_id, report_type, title, content_md, data_json),
        )
        conn.commit()
    return get_operational_report(r_id) or report_data


def get_operational_report(report_id: str) -> dict[str, Any] | None:
    """Retrieve operational report by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM operational_reports WHERE id = ?", (report_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["data"] = json.loads(d["data_json"]) if isinstance(d["data_json"], str) else d.get("data_json", {})
        return d


def list_operational_reports(report_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """List operational reports."""
    query = "SELECT * FROM operational_reports WHERE 1=1"
    params: list[Any] = []
    if report_type:
        query += " AND report_type = ?"
        params.append(report_type)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["data"] = json.loads(d["data_json"]) if isinstance(d["data_json"], str) else d.get("data_json", {})
        out.append(d)
    return out


# ============================================================
# Persistent Unit and Personnel Management (Phase 9)
# ============================================================

def save_unit(unit: dict[str, Any]) -> None:
    """Save or update persistent unit configuration and state."""
    route_raw = unit.get("route", unit.get("route_json", []))
    route_str = json.dumps(route_raw) if not isinstance(route_raw, str) else route_raw

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO units (
                id, run_id, callsign, kind, status, lat, lon, heading, speed_kph,
                fuel, battery, sector, route_json, active_mission_id, last_seen_tick,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                unit["id"],
                unit.get("run_id"),
                unit.get("callsign", unit["id"]),
                unit.get("kind", "patrol"),
                unit.get("status", "active"),
                float(unit.get("lat", 0.0)),
                float(unit.get("lon", 0.0)),
                float(unit.get("heading", 0.0)),
                float(unit.get("speed_kph", unit.get("speedKph", 0.0))),
                float(unit.get("fuel", 100.0)),
                float(unit.get("battery", 100.0)),
                unit.get("sector", "A"),
                route_str,
                unit.get("active_mission_id"),
                int(unit.get("last_seen_tick", unit.get("lastSeenTick", 0))),
            ),
        )


def get_unit(unit_id: str) -> dict[str, Any] | None:
    """Retrieve unit record by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM units WHERE id = ?", (unit_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["route"] = json.loads(d["route_json"]) if isinstance(d["route_json"], str) else d.get("route_json", [])
        return d


def list_units(run_id: str | None = None) -> list[dict[str, Any]]:
    """List persistent units, optionally filtered by run."""
    query = "SELECT * FROM units"
    params: list[Any] = []
    if run_id:
        query += " WHERE run_id = ?"
        params.append(run_id)
    query += " ORDER BY id ASC"

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["route"] = json.loads(d["route_json"]) if isinstance(d["route_json"], str) else d.get("route_json", [])
        out.append(d)
    return out


def save_unit_position_sample(sample: dict[str, Any]) -> None:
    """Record an authoritative timestamped position sample for historical replay."""
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO unit_position_history (
                run_id, unit_id, tick, sim_time, lat, lon, heading, speed_kph, in_weather
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample["run_id"],
                sample["unit_id"],
                int(sample["tick"]),
                int(sample.get("sim_time", sample["tick"] * 1000)),
                float(sample["lat"]),
                float(sample["lon"]),
                float(sample.get("heading", 0.0)),
                float(sample.get("speed_kph", 0.0)),
                1 if sample.get("in_weather") else 0,
            ),
        )


def save_unit_position_samples_batch(samples: list[dict[str, Any]]) -> None:
    """Batch-record authoritative timestamped position samples in a single transaction."""
    if not samples:
        return
    rows = [
        (
            s["run_id"],
            s["unit_id"],
            int(s["tick"]),
            int(s.get("sim_time", s["tick"] * 1000)),
            float(s["lat"]),
            float(s["lon"]),
            float(s.get("heading", 0.0)),
            float(s.get("speed_kph", 0.0)),
            1 if s.get("in_weather") else 0,
        )
        for s in samples
    ]
    with _lock, _sqlite_connect() as conn:
        conn.executemany(
            """
            INSERT INTO unit_position_history (
                run_id, unit_id, tick, sim_time, lat, lon, heading, speed_kph, in_weather
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def list_unit_positions(
    unit_id: str | None = None,
    run_id: str | None = None,
    start_tick: int = 0,
    end_tick: int | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """Retrieve historical unit position samples."""
    query = "SELECT * FROM unit_position_history WHERE tick >= ?"
    params: list[Any] = [start_tick]
    if run_id:
        query += " AND run_id = ?"
        params.append(run_id)
    if unit_id:
        query += " AND unit_id = ?"
        params.append(unit_id)
    if end_tick is not None:
        query += " AND tick <= ?"
        params.append(end_tick)
    query += " ORDER BY tick ASC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def save_person(person: dict[str, Any]) -> None:
    """Save or update persistent personnel record and vitals."""
    hist_raw = person.get("mission_history", person.get("mission_history_json", []))
    hist_str = json.dumps(hist_raw) if not isinstance(hist_raw, str) else hist_raw

    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO personnel (
                id, run_id, name, rank, unit_id, condition, heart_rate, fatigue,
                active_mission_id, mission_history_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                person["id"],
                person.get("run_id"),
                person["name"],
                person.get("rank", "PVT"),
                person.get("unit_id", person.get("unitId", "")),
                person.get("condition", "fit"),
                float(person.get("heart_rate", person.get("heartRate", 72.0))),
                float(person.get("fatigue", 0.20)),
                person.get("active_mission_id", person.get("activeMissionId")),
                hist_str,
            ),
        )


def get_person(person_id: str) -> dict[str, Any] | None:
    """Retrieve personnel record by ID."""
    with _lock, _sqlite_connect() as conn:
        row = conn.execute("SELECT * FROM personnel WHERE id = ?", (person_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["mission_history"] = json.loads(d["mission_history_json"]) if isinstance(d["mission_history_json"], str) else d.get("mission_history_json", [])
        return d


def list_personnel(run_id: str | None = None, unit_id: str | None = None) -> list[dict[str, Any]]:
    """List persistent personnel records."""
    query = "SELECT * FROM personnel WHERE 1=1"
    params: list[Any] = []
    if run_id:
        query += " AND run_id = ?"
        params.append(run_id)
    if unit_id:
        query += " AND unit_id = ?"
        params.append(unit_id)
    query += " ORDER BY id ASC"

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["mission_history"] = json.loads(d["mission_history_json"]) if isinstance(d["mission_history_json"], str) else d.get("mission_history_json", [])
        out.append(d)
    return out


def save_personnel_vitals_sample(sample: dict[str, Any]) -> None:
    """Record a timestamped vitals sample tied to simulation clock."""
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT INTO personnel_vitals_history (
                run_id, person_id, tick, sim_time, heart_rate, fatigue, activity_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample["run_id"],
                sample["person_id"],
                int(sample["tick"]),
                int(sample.get("sim_time", sample["tick"] * 1000)),
                float(sample["heart_rate"]),
                float(sample["fatigue"]),
                sample.get("activity_type", "patrol"),
            ),
        )


def save_personnel_vitals_samples_batch(samples: list[dict[str, Any]]) -> None:
    """Batch-record timestamped vitals samples tied to simulation clock in a single transaction."""
    if not samples:
        return
    rows = [
        (
            s["run_id"],
            s["person_id"],
            int(s["tick"]),
            int(s.get("sim_time", s["tick"] * 1000)),
            float(s["heart_rate"]),
            float(s["fatigue"]),
            s.get("activity_type", "patrol"),
        )
        for s in samples
    ]
    with _lock, _sqlite_connect() as conn:
        conn.executemany(
            """
            INSERT INTO personnel_vitals_history (
                run_id, person_id, tick, sim_time, heart_rate, fatigue, activity_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def list_personnel_vitals(
    person_id: str | None = None,
    run_id: str | None = None,
    start_tick: int = 0,
    end_tick: int | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Retrieve historical vitals samples."""
    query = "SELECT * FROM personnel_vitals_history WHERE tick >= ?"
    params: list[Any] = [start_tick]
    if run_id:
        query += " AND run_id = ?"
        params.append(run_id)
    if person_id:
        query += " AND person_id = ?"
        params.append(person_id)
    if end_tick is not None:
        query += " AND tick <= ?"
        params.append(end_tick)
    query += " ORDER BY tick ASC LIMIT ?"
    params.append(limit)

    with _lock, _sqlite_connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def save_personnel_assignment(assignment: dict[str, Any]) -> None:
    """Record personnel assignment to unit and mission."""
    with _lock, _sqlite_connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO personnel_assignments (
                id, run_id, person_id, unit_id, mission_id, role, assigned_at_tick, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assignment["id"],
                assignment["run_id"],
                assignment["person_id"],
                assignment["unit_id"],
                assignment.get("mission_id"),
                assignment.get("role", "operator"),
                int(assignment.get("assigned_at_tick", 0)),
                assignment.get("status", "active"),
            ),
        )


def get_run_reconstructed_state(run_id: str, tick: int) -> dict[str, Any] | None:
    """Reconstruct complete authoritative world state at arbitrary simulation timestamp."""
    run = get_run(run_id)
    if not run:
        return None
    events = run.get("log", [])
    # Fold events up to tick
    state: dict[str, Any] = {
        "runId": run_id,
        "seed": run.get("seed", 20260101),
        "scenarioId": run.get("scenarioId", "SC-1"),
        "tick": tick,
        "simTime": tick * 1000,
        "units": {},
        "depots": {},
        "personnel": {},
        "weather": {},
        "incidents": {},
        "alerts": {},
        "zones": [],
    }
    for e in events:
        if e.get("tick", 0) > tick:
            break
        t = e.get("type")
        p = e.get("payload", {})
        eid = e.get("entityId", "")
        if t == "world_init":
            for u in p.get("units", []):
                state["units"][u["id"]] = dict(u)
            for d in p.get("depots", []):
                state["depots"][d["id"]] = dict(d)
            for prs in p.get("personnel", []):
                state["personnel"][prs["id"]] = dict(prs)
            state["zones"] = p.get("zones", [])
        elif t == "unit_move":
            if eid in state["units"]:
                state["units"][eid].update({
                    "lat": p.get("lat"),
                    "lon": p.get("lon"),
                    "heading": p.get("heading"),
                    "inWeather": p.get("inWeather", False),
                    "lastSeenTick": e.get("tick", 0),
                })
        elif t == "unit_status":
            if eid in state["units"]:
                state["units"][eid]["status"] = p.get("status")
        elif t == "resource_level":
            if eid in state["units"]:
                if "fuel" in p:
                    state["units"][eid]["fuel"] = p["fuel"]
                if "battery" in p:
                    state["units"][eid]["battery"] = p["battery"]
            if eid in state["depots"] and "stock" in p:
                state["depots"][eid]["stock"] = p["stock"]
        elif t == "vitals":
            if eid in state["personnel"]:
                state["personnel"][eid].update({
                    "heartRate": p.get("heartRate"),
                    "fatigue": p.get("fatigue"),
                    "condition": p.get("condition", state["personnel"][eid].get("condition", "fit")),
                })
        elif t == "weather_spawn":
            state["weather"][eid] = dict(p)
        elif t == "weather_move":
            if eid in state["weather"]:
                state["weather"][eid].update(p)
        elif t == "weather_clear":
            state["weather"].pop(eid, None)
        elif t == "incident_open":
            state["incidents"][eid] = {
                "id": eid,
                "tick": e.get("tick", 0),
                "severity": e.get("severity", "medium"),
                "kind": p.get("kind", "incident"),
                "lat": p.get("lat"),
                "lon": p.get("lon"),
                "open": True,
            }
        elif t == "incident_close":
            if eid in state["incidents"]:
                state["incidents"][eid]["open"] = False
        elif t == "alert_raise":
            aid = p.get("alertId", f"AL-{e.get('id', 0)}")
            state["alerts"][aid] = {
                "id": aid,
                "tick": e.get("tick", 0),
                "severity": e.get("severity", "low"),
                "message": p.get("message", ""),
                "acked": False,
            }
        elif t == "alert_ack":
            aid = p.get("alertId", eid)
            if aid in state["alerts"]:
                state["alerts"][aid]["acked"] = True
        elif t == "mission_assigned" or (t == "system" and p.get("mission") and p.get("route")):
            if eid in state["units"]:
                state["units"][eid]["route"] = [list(wp) for wp in p["route"]]
                mid = p.get("missionId", f"MSN-{e.get('tick', 0)}")
                state["units"][eid]["activeMissionId"] = mid
            for prs in state["personnel"].values():
                if prs.get("unitId") == eid:
                    prs["activeMissionId"] = p.get("missionId", f"MSN-{e.get('tick', 0)}")
    return state

