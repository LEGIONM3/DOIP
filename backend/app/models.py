"""SQLAlchemy 2.0 ORM Models for DOIP (Defense Operations Intelligence Platform).

Defines relational, spatial, and vector schemas:
  - users
  - runs
  - sim_events (with spatial point coordinates)
  - whatif_results
  - custom_scenarios
  - audit_events
  - warroom_messages
  - doctrine_documents
  - doctrine_chunks (with vector embedding support)
  - tactical_zones (with spatial polygon geometries)
  - knowledge_graph_nodes & knowledge_graph_edges
  - vision_detections & vision_tracks
  - forecast_runs
  - copilot_sessions
  - replay_reports
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import (
    BIGINT,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TypeDecorator

Base = declarative_base()

try:
    from geoalchemy2 import Geometry
    HAS_GEOALCHEMY = True
except ImportError:
    HAS_GEOALCHEMY = False

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class SpatialPoint(TypeDecorator):
    """PostGIS Point in PostgreSQL, JSON [lon, lat] in SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql" and HAS_GEOALCHEMY:
            return dialect.type_descriptor(Geometry("POINT", srid=4326))
        return dialect.type_descriptor(JSON())


class SpatialPolygon(TypeDecorator):
    """PostGIS Polygon in PostgreSQL, JSON coordinate list in SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql" and HAS_GEOALCHEMY:
            return dialect.type_descriptor(Geometry("POLYGON", srid=4326))
        return dialect.type_descriptor(JSON())


class SpatialLineString(TypeDecorator):
    """PostGIS LineString in PostgreSQL, JSON coordinates list in SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql" and HAS_GEOALCHEMY:
            return dialect.type_descriptor(Geometry("LINESTRING", srid=4326))
        return dialect.type_descriptor(JSON())


class VectorType(TypeDecorator):
    """pgvector in PostgreSQL, JSON float list in SQLite."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 384, **kwargs: Any) -> None:
        self.dim = dim
        super().__init__(**kwargs)

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql" and HAS_PGVECTOR:
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())


class User(Base):
    """User accounts, tactical roles, and authentication attributes."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(64), nullable=True)
    role = Column(String(32), nullable=False, default="operator")  # analyst, operator, planner, admin
    unit = Column(String(64), nullable=False, default="")
    hashed_password = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), onupdate=datetime.datetime.utcnow, nullable=False)


class Run(Base):
    """Deterministic simulation run headers and frozen states."""

    __tablename__ = "runs"

    id = Column(String(64), primary_key=True)
    seed = Column(BigInteger, nullable=False)
    scenario_id = Column(String(64), nullable=False, index=True)
    ticks = Column(Integer, nullable=False)
    events_count = Column(Integer, nullable=False, default=0)
    log = Column(Text, nullable=False)  # JSON-serialized event sequence
    world_json = Column(Text, nullable=True)  # Snapshot of world state
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)

    events = relationship("SimEvent", back_populates="run", cascade="all, delete-orphan")


class SimEvent(Base):
    """Normalized simulation event records for replay, audit, and spatial indexing."""

    __tablename__ = "sim_events"

    id = Column(String(64), primary_key=True)
    run_id = Column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    tick = Column(Integer, nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default="low")
    entity_id = Column(String(64), nullable=False, index=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    geom = Column(SpatialPoint(), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)

    run = relationship("Run", back_populates="events")

    __table_args__ = (
        Index("idx_sim_events_run_tick", "run_id", "tick"),
        Index("idx_sim_events_type_sev", "event_type", "severity"),
    )


class WhatIfResult(Base):
    """Persisted Monte Carlo branch execution results and delta KPIs."""

    __tablename__ = "whatif_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seed = Column(BigInteger, nullable=False)
    scenario_id = Column(String(64), nullable=False, index=True)
    ticks = Column(Integer, nullable=False)
    actions_json = Column(Text, nullable=False, default="[]")
    baseline_kpis = Column(Text, nullable=False, default="{}")
    branch_kpis = Column(Text, nullable=False, default="{}")
    deltas_json = Column(Text, nullable=False, default="{}")
    score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class CustomScenario(Base):
    """Planner-authored custom scenarios and injected DSL actions."""

    __tablename__ = "custom_scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=False, default="")
    config_json = Column(Text, nullable=False, default="{}")
    actions_json = Column(Text, nullable=False, default="[]")
    status = Column(String(32), nullable=False, default="draft")  # draft, published, archived
    author = Column(String(64), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), onupdate=datetime.datetime.utcnow, nullable=False)


class AuditEvent(Base):
    """Append-only operational audit trail."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    detail = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class WarroomMessage(Base):
    """War-room collaboration and tactical task messages."""

    __tablename__ = "warroom_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(32), nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class DoctrineDocument(Base):
    """Parsed doctrine corpus documents (POL, REF, SOP)."""

    __tablename__ = "doctrine_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(32), unique=True, nullable=False, index=True)  # SOP-04, POL-01
    category = Column(String(32), nullable=False, index=True)  # POL, REF, SOP
    title = Column(String(255), nullable=False)
    tags = Column(JSON, nullable=False, default=list)
    version = Column(String(16), nullable=False, default="1.0")
    source_file = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)

    chunks = relationship("DoctrineChunk", back_populates="document", cascade="all, delete-orphan")


class DoctrineChunk(Base):
    """Deterministic section chunks for dense vector RAG."""

    __tablename__ = "doctrine_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(String(64), unique=True, nullable=False, index=True)  # SOP-04-SEC-01-composition
    document_id = Column(String(32), ForeignKey("doctrine_documents.doc_id", ondelete="CASCADE"), nullable=False, index=True)
    document_type = Column(String(16), nullable=False)
    section = Column(String(128), nullable=False)
    source = Column(String(255), nullable=False)
    citation = Column(String(64), nullable=False)
    text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False, default=0)
    embedding = Column(VectorType(384), nullable=True)  # VectorType handles pgvector or JSON
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)

    document = relationship("DoctrineDocument", back_populates="chunks")


class TacticalZone(Base):
    """PostGIS geofenced tactical zones (Restricted airspace, threat corridors)."""

    __tablename__ = "tactical_zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    zone_type = Column(String(32), nullable=False)  # RESTRICTED, THREAT, CORRIDOR, OBJECTIVE
    min_alt_m = Column(Float, nullable=False, default=0.0)
    max_alt_m = Column(Float, nullable=False, default=10000.0)
    active = Column(Boolean, nullable=False, default=True)
    coordinates_json = Column(JSON, nullable=False, default=list)  # GeoJSON / list of [lat, lon]
    geom = Column(SpatialPolygon(), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Phase 2: Tactical Operations & Decision Support Models
# ---------------------------------------------------------------------------
class Mission(Base):
    """Operational mission record with lifecycle management and risk telemetry."""

    __tablename__ = "missions"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=False, default="")
    priority = Column(String(32), nullable=False, default="routine")  # critical, high, routine, low
    status = Column(String(32), nullable=False, default="draft")  # draft, review, approved, executing, completed, cancelled
    author = Column(String(64), nullable=False, default="")
    approved_by = Column(String(64), nullable=True)
    assigned_unit_ids = Column(JSON, nullable=False, default=list)
    risk_score = Column(Float, nullable=False, default=0.0)
    estimated_duration_s = Column(Integer, nullable=False, default=0)
    estimated_fuel_l = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), onupdate=datetime.datetime.utcnow, nullable=False)

    tasks = relationship("MissionTask", back_populates="mission", cascade="all, delete-orphan")
    waypoints = relationship("Waypoint", back_populates="mission", cascade="all, delete-orphan")
    routes = relationship("Route", back_populates="mission")


class MissionTask(Base):
    """Ordered tactical task belonging to a mission."""

    __tablename__ = "mission_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mission_id = Column(String(64), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False, default=1)
    title = Column(String(128), nullable=False)
    task_type = Column(String(32), nullable=False)  # ESCORT, PATROL, RECON, REFUEL, SURVEILLANCE
    target_entity = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="pending")  # pending, in_progress, completed, failed
    duration_s = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)

    mission = relationship("Mission", back_populates="tasks")


class Waypoint(Base):
    """Tactical coordinate waypoint with PostGIS spatial point."""

    __tablename__ = "waypoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mission_id = Column(String(64), ForeignKey("missions.id", ondelete="CASCADE"), nullable=True, index=True)
    sequence = Column(Integer, nullable=False, default=1)
    name = Column(String(64), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    alt_m = Column(Float, nullable=False, default=0.0)
    geom = Column(SpatialPoint(), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)

    mission = relationship("Mission", back_populates="waypoints")


class Route(Base):
    """A* optimal route calculated across multi-layer terrain, weather, and threat cost grids."""

    __tablename__ = "routes"

    id = Column(String(64), primary_key=True)
    mission_id = Column(String(64), ForeignKey("missions.id", ondelete="SET NULL"), nullable=True, index=True)
    unit_id = Column(String(64), nullable=False, index=True)
    strategy = Column(String(32), nullable=False, default="shortest")  # shortest, safest, fuel_efficient, fastest
    distance_km = Column(Float, nullable=False)
    estimated_duration_s = Column(Integer, nullable=False)
    fuel_l = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False, default=0.0)
    waypoints_json = Column(JSON, nullable=False, default=list)  # [[lat, lon], ...]
    explanation = Column(Text, nullable=False, default="")
    geom = Column(SpatialLineString(), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)

    mission = relationship("Mission", back_populates="routes")
    segments = relationship("RouteSegment", back_populates="route", cascade="all, delete-orphan")


class RouteSegment(Base):
    """Granular segment of a tactical route with localized cost attribution."""

    __tablename__ = "route_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(String(64), ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_idx = Column(Integer, nullable=False)
    start_lat = Column(Float, nullable=False)
    start_lon = Column(Float, nullable=False)
    end_lat = Column(Float, nullable=False)
    end_lon = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=False)
    terrain_cost = Column(Float, nullable=False, default=1.0)
    threat_cost = Column(Float, nullable=False, default=0.0)
    weather_cost = Column(Float, nullable=False, default=0.0)

    route = relationship("Route", back_populates="segments")


class WarRoomPresence(Base):
    """Real-time collaborative operator presence state."""

    __tablename__ = "warroom_presence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(64), nullable=False)
    role = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="online")  # online, away, busy, offline
    current_screen = Column(String(64), nullable=False, default="map")
    cursor_lat = Column(Float, nullable=True)
    cursor_lon = Column(Float, nullable=True)
    last_heartbeat = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class WarRoomTask(Base):
    """Operations center tactical tasks and incident assignments."""

    __tablename__ = "warroom_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=False, default="")
    incident_id = Column(String(64), nullable=True, index=True)
    assigned_to = Column(String(64), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="TODO")  # TODO, IN_PROGRESS, DONE, BLOCKED
    priority = Column(String(32), nullable=False, default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), onupdate=datetime.datetime.utcnow, nullable=False)

    assignments = relationship("WarRoomAssignment", back_populates="task", cascade="all, delete-orphan")


class WarRoomAssignment(Base):
    """Handoff and ownership log for incident assignments."""

    __tablename__ = "warroom_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("warroom_tasks.id", ondelete="CASCADE"), nullable=True)
    incident_id = Column(String(64), nullable=True, index=True)
    from_user = Column(String(64), nullable=False)
    to_user = Column(String(64), nullable=False)
    reason = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)

    task = relationship("WarRoomTask", back_populates="assignments")


class OptimizerRun(Base):
    """Investment optimization runs and trade-off results."""

    __tablename__ = "optimizer_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    budget = Column(Float, nullable=False)
    priorities_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="completed")
    score = Column(Float, nullable=False, default=0.0)
    recommendations_json = Column(JSON, nullable=False, default=list)
    tradeoffs_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class RedTeamScenario(Base):
    """Adversarial stress-test scenarios and proposed DSL injects."""

    __tablename__ = "redteam_scenarios"

    id = Column(String(64), primary_key=True)
    mission_id = Column(String(64), nullable=True, index=True)
    title = Column(String(128), nullable=False)
    risk_rating = Column(String(32), nullable=False, default="HIGH")  # CRITICAL, HIGH, MEDIUM
    vulnerability_summary = Column(Text, nullable=False, default="")
    injects_json = Column(JSON, nullable=False, default=list)  # List of proposed DSL injects
    status = Column(String(32), nullable=False, default="staged")  # staged, approved, executed, rejected
    approved_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Phase 3: Digital Twin, Knowledge Graph, Vision & Copilot Models
# ---------------------------------------------------------------------------
class KnowledgeGraphNode(Base):
    """Operational Knowledge Graph Entity Node."""

    __tablename__ = "knowledge_graph_nodes"

    id = Column(String(64), primary_key=True)
    entity_type = Column(String(32), nullable=False, index=True)
    label = Column(String(128), nullable=False)
    properties_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), onupdate=datetime.datetime.utcnow, nullable=True)


class KnowledgeGraphEdge(Base):
    """Operational Knowledge Graph Directed Edge."""

    __tablename__ = "knowledge_graph_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(64), nullable=False, index=True)
    target_id = Column(String(64), nullable=False, index=True)
    relation_type = Column(String(32), nullable=False, index=True)
    weight = Column(Float, nullable=False, default=1.0)
    properties_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class VisionDetection(Base):
    """Real-time computer vision frame detection telemetry."""

    __tablename__ = "vision_detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    frame_id = Column(String(64), nullable=False, index=True)
    tick = Column(Integer, nullable=False, index=True)
    class_name = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    bbox_json = Column(JSON, nullable=False, default=list)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class VisionTrack(Base):
    """Persistent multi-frame object track identified by visual tracker."""

    __tablename__ = "vision_tracks"

    id = Column(String(64), primary_key=True)
    class_name = Column(String(32), nullable=False)
    first_tick = Column(Integer, nullable=False)
    last_tick = Column(Integer, nullable=False)
    trajectory_json = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class ForecastRun(Base):
    """Predictive simulation and operational lookahead forecasting run."""

    __tablename__ = "forecast_runs"

    id = Column(String(64), primary_key=True)
    scenario_id = Column(String(64), nullable=False, index=True)
    tick = Column(Integer, nullable=False, default=0)
    horizon_ticks = Column(Integer, nullable=False, default=120)
    predictions_json = Column(JSON, nullable=False, default=list)
    confidence = Column(Float, nullable=False, default=0.95)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class MissionCopilotSession(Base):
    """Interactive LLM copilot session for tactical mission authoring and advisory."""

    __tablename__ = "copilot_sessions"

    id = Column(String(64), primary_key=True)
    mission_id = Column(String(64), nullable=True)
    title = Column(String(128), nullable=False)
    messages_json = Column(JSON, nullable=False, default=list)
    proposals_json = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="active")
    approved_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class ReplayReport(Base):
    """Comparative after-action review (AAR) and simulation turning point report."""

    __tablename__ = "replay_reports"

    id = Column(String(64), primary_key=True)
    run_id = Column(String(64), nullable=False, index=True)
    comparison_run_id = Column(String(64), nullable=True)
    summary = Column(Text, nullable=False, default="")
    turning_points_json = Column(JSON, nullable=False, default=list)
    kpi_deltas_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Phase 4: Distributed Autonomous Defense Ecosystem Models
# ---------------------------------------------------------------------------
class FederationNodeRecord(Base):
    """Federated command hierarchy node (Regional, Operational, Tactical)."""

    __tablename__ = "federation_nodes"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    tier = Column(String(32), nullable=False, default="tactical", index=True)  # regional, operational, tactical
    region = Column(String(64), nullable=False, default="GLOBAL", index=True)
    endpoint = Column(String(256), nullable=False, default="")
    status = Column(String(32), nullable=False, default="online")
    heartbeat_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class TheaterRecord(Base):
    """Geographic operational theater overseeing multiple battle spaces."""

    __tablename__ = "theaters"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    code = Column(String(32), nullable=False, unique=True, index=True)
    bounds_json = Column(JSON, nullable=False, default=list)
    active_world_id = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class WorldRecord(Base):
    """Isolated multi-theater simulation world instance with independent entities."""

    __tablename__ = "worlds"

    id = Column(String(64), primary_key=True)
    theater_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    tick = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="running")
    state_snapshot_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class CampaignRecord(Base):
    """High-level multi-theater strategic campaign with objectives and timeline."""

    __tablename__ = "campaigns"

    id = Column(String(64), primary_key=True)
    title = Column(String(128), nullable=False)
    theater_ids_json = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="draft")  # draft, active, paused, completed
    objectives_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)


class StrategicReportRecord(Base):
    """Macro-level strategic brief, readiness outlook, and risk assessment."""

    __tablename__ = "strategic_reports"

    id = Column(String(64), primary_key=True)
    campaign_id = Column(String(64), nullable=True, index=True)
    title = Column(String(128), nullable=False)
    brief_text = Column(Text, nullable=False, default="")
    readiness_score = Column(Float, nullable=False, default=85.0)
    risk_score = Column(Float, nullable=False, default=25.0)
    outlook_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class FutureBranchRecord(Base):
    """Autonomous Monte Carlo simulation future branch with outcome ranking."""

    __tablename__ = "future_branches"

    id = Column(String(64), primary_key=True)
    baseline_world_id = Column(String(64), nullable=False, index=True)
    branch_seed = Column(Integer, nullable=False)
    ticks = Column(Integer, nullable=False, default=120)
    outcome_rank = Column(Integer, nullable=False, default=1)
    outcome_json = Column(JSON, nullable=False, default=dict)
    risk_band = Column(String(32), nullable=False, default="P50")  # P10, P50, P90, WORST
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class EventStreamRecord(Base):
    """Enterprise event stream buffer entry for real-time telemetry and replaying."""

    __tablename__ = "event_streams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_name = Column(String(64), nullable=False, index=True)
    offset = Column(Integer, nullable=False, index=True)
    partition = Column(Integer, nullable=False, default=0)
    event_type = Column(String(64), nullable=False)
    payload_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class DataLakeObjectRecord(Base):
    """Operational Data Lake object metadata for simulation archives and tensor frames."""

    __tablename__ = "data_lake_objects"

    id = Column(String(64), primary_key=True)
    bucket = Column(String(64), nullable=False, index=True)
    key = Column(String(256), nullable=False, index=True)
    content_type = Column(String(64), nullable=False, default="application/json")
    size_bytes = Column(Integer, nullable=False, default=0)
    etag = Column(String(64), nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# Phase 5: Unified Enterprise Platform Models
# ---------------------------------------------------------------------------
class AgentRecord(Base):
    """Unified agent runtime registration and operational state."""

    __tablename__ = "agents"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    role = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="idle")  # idle, active, busy, offline
    capabilities_json = Column(JSON, nullable=False, default=list)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)


class AgentTaskRecord(Base):
    """Queue and execution telemetry for unified agent tasks."""

    __tablename__ = "agent_tasks"

    id = Column(String(64), primary_key=True)
    agent_id = Column(String(64), nullable=True, index=True)
    task_type = Column(String(64), nullable=False, index=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    result_json = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="pending")  # pending, in_progress, completed, failed
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class AgentMemoryRecord(Base):
    """Long-term persistent memory (semantic, episodic, operational)."""

    __tablename__ = "agent_memories"

    id = Column(String(64), primary_key=True)
    agent_id = Column(String(64), nullable=True, index=True)
    memory_type = Column(String(32), nullable=False, index=True)  # semantic, episodic, operational
    content = Column(Text, nullable=False)
    tags_json = Column(JSON, nullable=False, default=list)
    embedding = Column(VectorType(384), nullable=True)
    importance = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class AnalysisFindingRecord(Base):
    """Autonomous intelligence findings, bottlenecks, and anomalies."""

    __tablename__ = "analysis_findings"

    id = Column(String(64), primary_key=True)
    category = Column(String(32), nullable=False, index=True)  # anomaly, bottleneck, trend, failure, readiness
    severity = Column(String(32), nullable=False, default="medium")  # low, medium, high, critical
    title = Column(String(256), nullable=False)
    details_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class ForecastMatrixRecord(Base):
    """Multi-theater, multi-dimensional forecast matrices and risk tensors."""

    __tablename__ = "forecast_matrices"

    id = Column(String(64), primary_key=True)
    horizon_hours = Column(Float, nullable=False, default=4.0)
    matrix_json = Column(JSON, nullable=False, default=dict)
    risk_tensor_json = Column(JSON, nullable=False, default=dict)
    summary = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class ScenarioOutcomeRecord(Base):
    """Massive What-If scenario execution results and rankings."""

    __tablename__ = "scenario_outcomes"

    id = Column(String(64), primary_key=True)
    batch_id = Column(String(64), nullable=False, index=True)
    scenario_seed = Column(Integer, nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    rank = Column(Integer, nullable=False, default=1)
    outcome_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class ModelGovernanceRecord(Base):
    """Model registry, routing specifications, and governance."""

    __tablename__ = "model_registry"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    provider = Column(String(64), nullable=False)  # ollama, openai, local_vllm, yolov8, nomic
    model_type = Column(String(32), nullable=False)  # llm, vision, embedding, classifier
    endpoint = Column(String(256), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class WorkflowInstanceRecord(Base):
    """State machine instances for mission, approval, and audit workflows."""

    __tablename__ = "workflow_instances"

    id = Column(String(64), primary_key=True)
    workflow_type = Column(String(64), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    current_step = Column(String(64), nullable=False)
    steps_json = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="staged")  # staged, running, approved, completed, rejected
    requires_human_confirmation = Column(Boolean, nullable=False, default=True)
    approved_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)


class OperationalReportRecord(Base):
    """Automated operational reports (daily, mission, forecast, readiness)."""

    __tablename__ = "operational_reports"

    id = Column(String(64), primary_key=True)
    report_type = Column(String(64), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    content_md = Column(Text, nullable=False, default="")
    data_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class UnitRecord(Base):
    """Persistent unit identity and run-scoped tactical configuration."""

    __tablename__ = "units"

    id = Column(String(64), primary_key=True)
    run_id = Column(String(64), nullable=True, index=True)
    callsign = Column(String(64), nullable=False)
    kind = Column(String(32), nullable=False)  # patrol, uav, convoy, depot
    status = Column(String(32), nullable=False, default="active")
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    heading = Column(Float, nullable=False, default=0.0)
    speed_kph = Column(Float, nullable=False, default=0.0)
    fuel = Column(Float, nullable=False, default=100.0)
    battery = Column(Float, nullable=False, default=100.0)
    sector = Column(String(16), nullable=False, default="A")
    route_json = Column(JSON, nullable=False, default=list)
    active_mission_id = Column(String(64), nullable=True, index=True)
    last_seen_tick = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class UnitPositionHistoryRecord(Base):
    """Timestamped historical trajectory samples for replay and forecasting."""

    __tablename__ = "unit_position_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True)
    unit_id = Column(String(64), nullable=False, index=True)
    tick = Column(Integer, nullable=False, index=True)
    sim_time = Column(Integer, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    heading = Column(Float, nullable=False, default=0.0)
    speed_kph = Column(Float, nullable=False, default=0.0)
    in_weather = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_unit_pos_run_tick", "run_id", "tick"),
        Index("idx_unit_pos_unit_tick", "unit_id", "tick"),
    )


class PersonnelRecord(Base):
    """Persistent personnel identity, rank, unit assignment, and condition."""

    __tablename__ = "personnel"

    id = Column(String(64), primary_key=True)
    run_id = Column(String(64), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    rank = Column(String(32), nullable=False)
    unit_id = Column(String(64), nullable=False, index=True)
    condition = Column(String(32), nullable=False, default="fit")  # fit, fatigue, strained, injured, medevac
    heart_rate = Column(Float, nullable=False, default=72.0)
    fatigue = Column(Float, nullable=False, default=0.20)
    active_mission_id = Column(String(64), nullable=True, index=True)
    mission_history_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)


class PersonnelVitalsRecord(Base):
    """Timestamped biometric vitals samples tied to simulation clock and mission exertion."""

    __tablename__ = "personnel_vitals_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True)
    person_id = Column(String(64), nullable=False, index=True)
    tick = Column(Integer, nullable=False, index=True)
    sim_time = Column(Integer, nullable=False)
    heart_rate = Column(Float, nullable=False)
    fatigue = Column(Float, nullable=False)
    activity_type = Column(String(32), nullable=False, default="patrol")
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_vitals_run_tick", "run_id", "tick"),
        Index("idx_vitals_person_tick", "person_id", "tick"),
    )


class PersonnelAssignmentRecord(Base):
    """Audit of personnel assignments across units and tactical missions."""

    __tablename__ = "personnel_assignments"

    id = Column(String(64), primary_key=True)
    run_id = Column(String(64), nullable=False, index=True)
    person_id = Column(String(64), nullable=False, index=True)
    unit_id = Column(String(64), nullable=False, index=True)
    mission_id = Column(String(64), nullable=True, index=True)
    role = Column(String(64), nullable=False, default="operator")
    assigned_at_tick = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, server_default=func.now(), nullable=False)





