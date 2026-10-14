# DOIP Phase 1 — Database Design Specification

**Author:** DATABASE-ENGINEER Agent (ECC Orchestration Team)  
**Target:** PostgreSQL 16 + PostGIS 3.4 / SQLAlchemy 2.0 / Alembic  
**Fallback:** SQLite 3 (Zero-config local development)  
**Status:** Approved for Implementation  

---

## 1. Persistence Philosophy & Dual-Engine Strategy

DOIP requires enterprise-grade persistence for production defense simulation environments while maintaining effortless zero-dependency developer onboarding.

### Configuration Layer
Environment variables govern database and vector storage behavior:
```bash
# Production (Default when deployed in Docker)
DATABASE_URL=postgresql+psycopg://doip_user:doip_password@localhost:5432/doip
POSTGIS_ENABLED=true
VECTOR_DATABASE_URL=postgresql+psycopg://doip_user:doip_password@localhost:5432/doip

# Development / Local Fallback (Default when DATABASE_URL is unset)
# DATABASE_URL=sqlite:///./doip.db
```

### Fallback Guarantee
If `DATABASE_URL` is omitted, starts with `sqlite:///`, or connection to PostgreSQL fails during local offline runs:
- System seamlessly falls back to local SQLite database (`doip.db`).
- Spatial queries fall back to Euclidean / bounding-box calculations in Python.
- No crashes occur for developers running `pytest` without PostgreSQL.

---

## 2. Relational & Spatial Schema Design

### 2.1 Core Tables

#### `users`
User accounts, tactical roles, and authentication attributes.
- `id` (INTEGER, PK)
- `username` (VARCHAR(64), UNIQUE, NOT NULL, INDEX)
- `role` (VARCHAR(32), NOT NULL) — `analyst` | `operator` | `planner` | `admin`
- `unit` (VARCHAR(64), DEFAULT '')
- `hashed_password` (VARCHAR(255), NULLABLE)
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)
- `updated_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)

#### `runs`
Deterministic simulation run headers and frozen final states.
- `id` (VARCHAR(64), PK) — e.g. `RUN-20261001-001`
- `seed` (BIGINT, NOT NULL)
- `scenario_id` (VARCHAR(64), NOT NULL, INDEX)
- `ticks` (INTEGER, NOT NULL)
- `events_count` (INTEGER, NOT NULL)
- `log` (TEXT, NOT NULL) — JSON string of full event sequence
- `world_json` (TEXT, NULLABLE) — Snapshot of terminal world state
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)

#### `sim_events`
Normalized relational event store for high-performance indexing, replay queries, and citation validation.
- `id` (VARCHAR(64), PK) — Event ID, e.g. `EV-100-1`
- `run_id` (VARCHAR(64), FK -> `runs.id` ON DELETE CASCADE, INDEX)
- `tick` (INTEGER, NOT NULL, INDEX)
- `event_type` (VARCHAR(64), NOT NULL, INDEX) — e.g. `unit_move`, `incident_open`, `alert_raise`
- `severity` (VARCHAR(16), NOT NULL, DEFAULT 'low') — `low` | `medium` | `high` | `critical`
- `entity_id` (VARCHAR(64), NOT NULL, INDEX) — e.g. `U-UAV-1`, `INC-10`
- `payload` (JSONB / JSON, NOT NULL)
- `geom` (GEOMETRY(Point, 4326), NULLABLE) — Spatial location for map/range queries
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)

#### `whatif_results`
Monte Carlo branch evaluation results and KPI deltas.
- `id` (INTEGER, PK, AUTOINCREMENT)
- `seed` (BIGINT, NOT NULL)
- `scenario_id` (VARCHAR(64), NOT NULL, INDEX)
- `ticks` (INTEGER, NOT NULL)
- `actions_json` (TEXT, NOT NULL DEFAULT '[]')
- `baseline_kpis` (TEXT, NOT NULL DEFAULT '{}')
- `branch_kpis` (TEXT, NOT NULL DEFAULT '{}')
- `deltas_json` (TEXT, NOT NULL DEFAULT '{}')
- `score` (FLOAT, DEFAULT 0.0)
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)

#### `custom_scenarios`
Planner-authored custom scenario drafts and whitelisted DSL actions.
- `id` (INTEGER, PK, AUTOINCREMENT)
- `scenario_id` (VARCHAR(64), UNIQUE, NOT NULL)
- `name` (VARCHAR(128), NOT NULL)
- `description` (TEXT, DEFAULT '')
- `config_json` (TEXT, DEFAULT '{}')
- `actions_json` (TEXT, DEFAULT '[]')
- `status` (VARCHAR(32), DEFAULT 'draft') — `draft` | `published` | `archived`
- `author` (VARCHAR(64), DEFAULT '')
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)
- `updated_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)

#### `audit_events` (audit)
Append-only tamper-resistant operational audit trail.
- `id` (INTEGER, PK, AUTOINCREMENT)
- `actor` (VARCHAR(64), NOT NULL, INDEX)
- `action` (VARCHAR(64), NOT NULL, INDEX)
- `detail` (TEXT, DEFAULT '')
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)

#### `warroom_messages`
Multi-operator synchronized chat and task board messages.
- `id` (INTEGER, PK, AUTOINCREMENT)
- `type` (VARCHAR(32), NOT NULL)
- `payload` (TEXT, NOT NULL)
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)

### 2.2 Doctrine & RAG Tables

#### `doctrine_documents`
Master registry of parsed doctrine documents (POL, REF, SOP).
- `id` (INTEGER, PK, AUTOINCREMENT)
- `doc_id` (VARCHAR(32), UNIQUE, NOT NULL, INDEX) — e.g. `SOP-04`
- `category` (VARCHAR(32), NOT NULL, INDEX) — `POL` | `REF` | `SOP`
- `title` (VARCHAR(255), NOT NULL)
- `tags` (JSONB / JSON, DEFAULT '[]')
- `version` (VARCHAR(16), DEFAULT '1.0')
- `source_file` (VARCHAR(255), NOT NULL)
- `content` (TEXT, NOT NULL)
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)

#### `doctrine_chunks`
Deterministic semantic sections with embeddings for dense vector retrieval.
- `id` (INTEGER, PK, AUTOINCREMENT)
- `chunk_id` (VARCHAR(64), UNIQUE, NOT NULL, INDEX) — e.g. `SOP-04-SEC-01-composition`
- `document_id` (VARCHAR(32), FK -> `doctrine_documents.doc_id` ON DELETE CASCADE, INDEX)
- `document_type` (VARCHAR(16), NOT NULL) — `POL` | `REF` | `SOP`
- `section` (VARCHAR(128), NOT NULL)
- `source` (VARCHAR(255), NOT NULL)
- `citation` (VARCHAR(64), NOT NULL) — e.g. `SOP-04 §1`
- `text` (TEXT, NOT NULL)
- `token_count` (INTEGER, NOT NULL)
- `embedding` (VECTOR(384) / BYTEA / JSON, NULLABLE) — pgvector embedding column or serialized vector
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW)

### 2.3 Spatial Tables & Geometries (PostGIS)

#### `tactical_zones`
Geofenced restricted zones, engagement corridors, and threat boundaries.
- `id` (INTEGER, PK, AUTOINCREMENT)
- `zone_id` (VARCHAR(64), UNIQUE, NOT NULL)
- `name` (VARCHAR(128), NOT NULL)
- `zone_type` (VARCHAR(32), NOT NULL) — `RESTRICTED` | `THREAT` | `CORRIDOR` | `OBJECTIVE`
- `geom` (GEOMETRY(Polygon, 4326), NOT NULL)
- `min_alt_m` (FLOAT, DEFAULT 0.0)
- `max_alt_m` (FLOAT, DEFAULT 10000.0)
- `active` (BOOLEAN, DEFAULT TRUE)

Spatial index: `CREATE INDEX idx_tactical_zones_geom ON tactical_zones USING GIST (geom);`

---

## 3. Spatial Queries & PostGIS Capabilities

1. **Zone Containment (`ST_Contains`)**:
   Determining if unit coordinates `(lat, lon)` violate a restricted tactical zone.
   ```sql
   SELECT zone_id, name, zone_type FROM tactical_zones
   WHERE active = true AND ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326));
   ```

2. **Proximity & Threat Radius (`ST_DWithin`)**:
   Querying units or incidents within distance `d_meters` of a waypoint:
   ```sql
   SELECT id, entity_id, severity FROM sim_events
   WHERE geom IS NOT NULL
     AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_m);
   ```

3. **Trajectory Intersection (`ST_Intersects`)**:
   Validating proposed flight/patrol path lines against weather fronts or threat polygons.

---

## 4. Alembic Migration Hierarchy

```text
backend/alembic/
├── env.py              # Environment configuration handling dynamic DB URL & PostGIS detection
├── script.py.mako      # Migration template
└── versions/
    └── 0001_phase1_initial_schema.py   # Baseline DDL for all core + doctrine + spatial tables
```
