# Operational Knowledge Graph & Causal Analysis Specification (Phase 3D)

**Program:** Defense Operations Intelligence Platform (DOIP)  
**Subsystem:** Knowledge Graph & Causal Reasoning Engine  
**Author:** KNOWLEDGE_GRAPH_ENGINEER  

---

## 1. Graph Model & Schema

The operational knowledge graph models tactical defense relationships using NetworkX with dual-mode PostgreSQL/SQLite persistence.

### Entity Types (Nodes)
- `MISSION`: Tactical operations, convoy escorts, reconnaissance sweeps.
- `UNIT`: Physical tactical units (recon vehicles, UAVs, supply convoys).
- `ASSET`: Operational equipment, fuel pods, comms masts, sensors.
- `INCIDENT`: Ambush contacts, weather squalls, mechanical failures, comms blackout.
- `ROUTE`: A* calculated navigation trajectories and waypoints.
- `OPERATOR`: Watch officers, planners, commanders.
- `WEATHER`: Storm cells, turbulence, cloud cover regions.
- `DOCTRINE`: Formal defense regulations (SOP-01..08, POL-01..03, REF-01..04).

### Relation Types (Edges)
- `participates_in`: (UNIT -> MISSION)
- `assigned_to`: (ASSET -> UNIT), (MISSION -> OPERATOR)
- `affected_by`: (UNIT -> WEATHER), (MISSION -> INCIDENT)
- `depends_on`: (MISSION -> ROUTE), (UNIT -> ASSET)
- `caused_by`: (INCIDENT -> WEATHER), (INCIDENT -> ASSET)
- `supports`: (DOCTRINE -> MISSION), (ASSET -> MISSION)

---

## 2. Core Graph Algorithms & Causal Reasoning

1. **Root Cause Analysis (`find_root_cause`)**:
   - Backward traversal over incoming `caused_by` and `affected_by` directed edges from an incident node.
   - Computes causal attribution confidence scores based on edge weights and temporal proximity.
2. **Dependency Tracing (`find_dependencies`)**:
   - Forward and backward traversal over `depends_on` and `supports` edges.
   - Identifies critical single points of failure (assets or units with high betweenness centrality whose failure impairs multiple missions).
3. **Incident Chain Analysis (`trace_incident_chain`)**:
   - Directed acyclic path finding tracing the cascading failure chain from root trigger to high-severity operational impact.

---

## 3. Database Schema

- `knowledge_graph_nodes`:
  - `id`: String(64) Primary Key
  - `entity_type`: String(32)
  - `label`: String(128)
  - `properties_json`: Text / JSON
  - `created_at`: DateTime
- `knowledge_graph_edges`:
  - `id`: Integer Primary Key
  - `source_id`: String(64) ForeignKey
  - `target_id`: String(64) ForeignKey
  - `relation_type`: String(32)
  - `weight`: Float
  - `properties_json`: Text / JSON
  - `created_at`: DateTime
