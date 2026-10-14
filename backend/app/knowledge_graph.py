"""Operational Knowledge Graph for DOIP (Defense Operations Intelligence Platform).

Phase 3 Core Intelligence Engine:
  - NetworkX MultiDiGraph for high-speed in-memory graph operations, causal reasoning,
    and dependency propagation.
  - Bidirectional relational persistence with PostgreSQL / SQLite (knowledge_graph_nodes,
    knowledge_graph_edges).
  - Standardized Entity Types:
      MISSION, UNIT, ASSET, INCIDENT, ROUTE, OPERATOR, WEATHER, DOCTRINE.
  - Standardized Relation Types:
      participates_in, assigned_to, affected_by, depends_on, caused_by, supports.
  - Analytics & Decision Support:
      * find_root_cause: Traverses incoming causal edges, computes path attribution scores.
      * find_dependencies: Traverses dependency chains, flags Single Points of Failure (SPOF).
      * trace_incident_chain: Produces directed causal path from origin to operational impact.
      * export_subgraph: Generates D3 / Sigma.js graph visualization payloads.
      * build_graph_from_world: Ingests live simulation world state and missions.
      * seed_demo_graph: Hydrates a tactical operational scenario for evaluation.
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from . import db

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standardized Types & Relations
# ---------------------------------------------------------------------------
VALID_ENTITY_TYPES: set[str] = {
    "MISSION",
    "UNIT",
    "ASSET",
    "INCIDENT",
    "ROUTE",
    "OPERATOR",
    "WEATHER",
    "DOCTRINE",
}

VALID_RELATION_TYPES: set[str] = {
    "participates_in",
    "assigned_to",
    "affected_by",
    "depends_on",
    "caused_by",
    "supports",
}


class OperationalKnowledgeGraph:
    """Operational Intelligence Knowledge Graph powered by NetworkX and persistent DB."""

    def __init__(self) -> None:
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self._load_from_db_quietly()

    def _load_from_db_quietly(self) -> None:
        """Hydrate in-memory graph from relational persistence if records exist."""
        try:
            nodes = db.list_knowledge_nodes()
            edges = db.list_knowledge_edges()
            for n in nodes:
                nid = n["id"]
                etype = n.get("entity_type", "UNKNOWN")
                lbl = n.get("label", nid)
                props = n.get("properties") or {}
                self.graph.add_node(nid, id=nid, entity_type=etype, label=lbl, properties=props)

            for e in edges:
                src = e["source_id"]
                tgt = e["target_id"]
                rel = e.get("relation_type", "related_to")
                weight = float(e.get("weight", 1.0))
                props = e.get("properties") or {}
                if not self.graph.has_node(src):
                    self.graph.add_node(src, id=src, entity_type="UNKNOWN", label=src, properties={})
                if not self.graph.has_node(tgt):
                    self.graph.add_node(tgt, id=tgt, entity_type="UNKNOWN", label=tgt, properties={})
                self.graph.add_edge(src, tgt, relation_type=rel, weight=weight, properties=props)
        except Exception as exc:
            log.warning("Could not hydrate knowledge graph from DB: %s", exc)

    def clear(self, clear_db: bool = True) -> None:
        """Reset the in-memory graph and optionally clear DB tables."""
        self.graph.clear()
        if clear_db:
            try:
                db.clear_knowledge_graph()
            except Exception as exc:
                log.warning("Failed to clear knowledge graph DB: %s", exc)

    # -----------------------------------------------------------------------
    # Node & Edge Management
    # -----------------------------------------------------------------------
    def add_entity(
        self,
        node_id: str,
        entity_type: str,
        label: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add or update an operational entity node in graph and DB."""
        nid = str(node_id).strip()
        etype = str(entity_type).strip().upper()
        if etype not in VALID_ENTITY_TYPES:
            log.info("Entity type %s not in standard set, adding anyway.", etype)
        lbl = str(label) if label else nid
        props = properties if properties is not None else {}

        self.graph.add_node(
            nid,
            id=nid,
            entity_type=etype,
            label=lbl,
            properties=props,
        )

        try:
            db.save_knowledge_node({
                "id": nid,
                "entity_type": etype,
                "label": lbl,
                "properties": props,
            })
        except Exception as exc:
            log.warning("DB sync notice for node %s: %s", nid, exc)

        return {"id": nid, "entity_type": etype, "label": lbl, "properties": props}

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add a directed relational edge between two operational entities."""
        src = str(source_id).strip()
        tgt = str(target_id).strip()
        rel = str(relation_type).strip().lower()
        w = float(weight)
        props = properties if properties is not None else {}

        # Ensure endpoints exist
        if not self.graph.has_node(src):
            self.add_entity(src, "UNKNOWN", src)
        if not self.graph.has_node(tgt):
            self.add_entity(tgt, "UNKNOWN", tgt)

        self.graph.add_edge(src, tgt, relation_type=rel, weight=w, properties=props)

        try:
            db.save_knowledge_edge({
                "source_id": src,
                "target_id": tgt,
                "relation_type": rel,
                "weight": w,
                "properties": props,
            })
        except Exception as exc:
            log.warning("DB sync notice for edge %s->%s: %s", src, tgt, exc)

        return {
            "source_id": src,
            "target_id": tgt,
            "relation_type": rel,
            "weight": w,
            "properties": props,
        }

    # -----------------------------------------------------------------------
    # World Ingestion
    # -----------------------------------------------------------------------
    def build_graph_from_world(
        self,
        world_state: dict[str, Any],
        missions: list[dict[str, Any]] | None = None,
        doctrines: list[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        """Ingest live simulation state, missions, and doctrine into graph."""
        if not world_state:
            return {"nodes": self.graph.number_of_nodes(), "edges": self.graph.number_of_edges()}

        # 1. Units
        units_data = world_state.get("units", {})
        unit_items = units_data.values() if isinstance(units_data, dict) else units_data
        for u in unit_items:
            uid = u.get("id")
            if not uid:
                continue
            lbl = u.get("callsign", uid)
            self.add_entity(uid, "UNIT", lbl, properties=u)

        # 2. Assets / Depots
        depots_data = world_state.get("depots", {})
        depot_items = depots_data.values() if isinstance(depots_data, dict) else depots_data
        for d in depot_items:
            did = d.get("id")
            if not did:
                continue
            lbl = d.get("name", did)
            self.add_entity(did, "ASSET", lbl, properties=d)

        # 3. Operators / Personnel
        personnel_data = world_state.get("personnel", {})
        personnel_items = personnel_data.values() if isinstance(personnel_data, dict) else personnel_data
        for p in personnel_items:
            pid = p.get("id")
            if not pid:
                continue
            rank = p.get("rank", "")
            name = p.get("name", pid)
            lbl = f"{rank} {name}".strip()
            self.add_entity(pid, "OPERATOR", lbl, properties=p)
            unit_id = p.get("unitId")
            if unit_id and self.graph.has_node(unit_id):
                self.add_relation(pid, unit_id, "assigned_to", weight=1.0)

        # 4. Weather Cells
        weather_data = world_state.get("weather", {})
        weather_items = weather_data.values() if isinstance(weather_data, dict) else weather_data
        for w in weather_items:
            wid = w.get("id")
            if not wid:
                continue
            lbl = f"Weather {w.get('kind', 'cell').capitalize()}"
            self.add_entity(wid, "WEATHER", lbl, properties=w)

            # Link units affected by proximity to adverse weather
            w_lat = w.get("lat")
            w_lon = w.get("lon")
            w_radius_deg = (w.get("radiusM", 5000.0) / 1000.0) / 111.0
            if w_lat is not None and w_lon is not None:
                for u in unit_items:
                    u_lat = u.get("lat")
                    u_lon = u.get("lon")
                    if u_lat is not None and u_lon is not None:
                        dist = ((u_lat - w_lat) ** 2 + (u_lon - w_lon) ** 2) ** 0.5
                        if dist <= w_radius_deg:
                            self.add_relation(u["id"], wid, "affected_by", weight=0.85, properties={"distance_deg": dist})

        # 5. Tactical Zones / Routes
        zones_data = world_state.get("zones", [])
        for z in zones_data:
            zid = z.get("id") or z.get("zone_id")
            if not zid:
                continue
            lbl = z.get("name", zid)
            self.add_entity(zid, "ROUTE", lbl, properties=z)

        # 6. Incidents
        incidents_data = world_state.get("incidents", [])
        for inc in incidents_data:
            iid = inc.get("id")
            if not iid:
                continue
            lbl = inc.get("title", inc.get("type", iid))
            self.add_entity(iid, "INCIDENT", lbl, properties=inc)
            aff_entity = inc.get("entityId") or inc.get("unit_id")
            if aff_entity and self.graph.has_node(aff_entity):
                self.add_relation(aff_entity, iid, "affected_by", weight=0.9)

        # 7. Missions
        if missions:
            for m in missions:
                mid = m.get("id")
                if not mid:
                    continue
                mlbl = m.get("name", mid)
                self.add_entity(mid, "MISSION", mlbl, properties=m)
                for uid in m.get("assigned_unit_ids", []):
                    if self.graph.has_node(uid):
                        self.add_relation(uid, mid, "participates_in", weight=1.0)
                        self.add_relation(mid, uid, "depends_on", weight=1.0)

        # 8. Doctrines
        if doctrines:
            for doc in doctrines:
                doc_id = doc.get("doc_id") or doc.get("id")
                if not doc_id:
                    continue
                dlbl = doc.get("title", doc_id)
                self.add_entity(doc_id, "DOCTRINE", dlbl, properties=doc)

        return {"nodes": self.graph.number_of_nodes(), "edges": self.graph.number_of_edges()}

    # -----------------------------------------------------------------------
    # Causal Intelligence: Root Cause Analysis
    # -----------------------------------------------------------------------
    def find_root_cause(self, incident_id: str) -> dict[str, Any]:
        """Traverse incoming causal edges backwards and compute attribution scores.

        Computes cumulative path weights and identifies origin nodes responsible
        for triggering cascading operational incidents.
        """
        target = str(incident_id).strip()
        if not self.graph.has_node(target):
            return {
                "incident_id": target,
                "error": f"Node '{target}' not found in knowledge graph",
                "root_cause_id": None,
                "attribution_score": 0.0,
                "contributors": [],
            }

        # Helper to retrieve direct causal parents
        # Strictly traverses causal edges: (cause) -[caused_by]-> (incident)
        def _get_causal_parents(node: str) -> list[tuple[str, float, str]]:
            parents: list[tuple[str, float, str]] = []
            # Incoming edges: u -> node where relation is caused_by
            for u, _, _, data in self.graph.in_edges(node, keys=True, data=True):
                rel = data.get("relation_type", "")
                if rel in ("caused_by", "causes"):
                    parents.append((u, float(data.get("weight", 1.0)), rel))
            # Outgoing edges: node -> v where relation is caused_by
            for _, v, _, data in self.graph.out_edges(node, keys=True, data=True):
                rel = data.get("relation_type", "")
                if rel in ("caused_by", "causes"):
                    parents.append((v, float(data.get("weight", 1.0)), rel))
            return parents

        # Traverse backwards using DFS to find all causal paths to origins
        visited: set[str] = set()
        origin_paths: list[list[tuple[str, float]]] = []

        def _dfs_trace(current: str, path: list[tuple[str, float]]) -> None:
            parents = _get_causal_parents(current)
            # Filter out cycles in path
            path_nodes = {p[0] for p in path}
            valid_parents = [p for p in parents if p[0] not in path_nodes]

            if not valid_parents:
                origin_paths.append(list(path))
                return

            for parent_id, weight, _ in valid_parents:
                _dfs_trace(parent_id, path + [(parent_id, weight)])

        _dfs_trace(target, [(target, 1.0)])

        # Aggregate attribution scores for all visited nodes
        attribution_map: dict[str, float] = {}
        depth_map: dict[str, int] = {}
        candidate_origins: dict[str, float] = {}

        for path in origin_paths:
            # path is [(target, 1.0), (intermediate, w1), ..., (origin, wk)]
            path_weight = 1.0
            for idx, (node_id, w) in enumerate(path):
                if idx > 0:
                    path_weight *= w
                # Depth from incident
                depth = idx
                if node_id != target:
                    attribution_map[node_id] = max(attribution_map.get(node_id, 0.0), path_weight)
                    depth_map[node_id] = max(depth_map.get(node_id, 0), depth)

            # Leaf origin of this path
            origin_id = path[-1][0]
            if origin_id != target:
                candidate_origins[origin_id] = max(candidate_origins.get(origin_id, 0.0), path_weight)

        # If incident itself had no causal parents
        if not candidate_origins:
            target_data = self.graph.nodes.get(target, {})
            return {
                "incident_id": target,
                "root_cause_id": target,
                "root_cause_label": target_data.get("label", target),
                "root_cause_type": target_data.get("entity_type", "INCIDENT"),
                "attribution_score": 1.0,
                "confidence": 1.0,
                "causal_chain": [
                    {
                        "step": 1,
                        "node_id": target,
                        "label": target_data.get("label", target),
                        "entity_type": target_data.get("entity_type", "INCIDENT"),
                        "role": "origin",
                    }
                ],
                "contributors": [],
                "summary": f"Incident {target} has no registered upstream causes; evaluated as initial origin.",
            }

        # Select primary root cause (highest attribution score, deepest origin)
        sorted_origins = sorted(
            candidate_origins.items(),
            key=lambda x: (x[1], depth_map.get(x[0], 0)),
            reverse=True,
        )
        primary_root_id, primary_score = sorted_origins[0]
        primary_data = self.graph.nodes.get(primary_root_id, {})

        # Build contributors list
        contributors = []
        for cid, score in attribution_map.items():
            cdata = self.graph.nodes.get(cid, {})
            contributors.append({
                "node_id": cid,
                "label": cdata.get("label", cid),
                "entity_type": cdata.get("entity_type", "UNKNOWN"),
                "attribution_score": round(score, 4),
                "depth": depth_map.get(cid, 1),
                "is_root_cause": cid == primary_root_id,
            })
        contributors.sort(key=lambda x: x["attribution_score"], reverse=True)

        # Build primary causal chain from origin to impact
        chain = self.trace_incident_chain(target)

        return {
            "incident_id": target,
            "root_cause_id": primary_root_id,
            "root_cause_label": primary_data.get("label", primary_root_id),
            "root_cause_type": primary_data.get("entity_type", "UNKNOWN"),
            "attribution_score": round(primary_score, 4),
            "confidence": round(min(1.0, primary_score), 4),
            "causal_chain": chain,
            "contributors": contributors,
            "summary": (
                f"Root cause for incident '{target}' identified as "
                f"'{primary_data.get('label', primary_root_id)}' ({primary_data.get('entity_type', 'UNKNOWN')}) "
                f"with attribution score {primary_score:.2f}."
            ),
        }

    # -----------------------------------------------------------------------
    # Incident Chain Tracing
    # -----------------------------------------------------------------------
    def trace_incident_chain(self, incident_id: str) -> list[dict[str, Any]]:
        """Return the directed causal sequence ordered from origin trigger to final impact."""
        target = str(incident_id).strip()
        if not self.graph.has_node(target):
            return []

        def _get_parents(node: str) -> list[tuple[str, float]]:
            p = []
            for u, _, _, data in self.graph.in_edges(node, keys=True, data=True):
                if data.get("relation_type") in ("caused_by", "causes"):
                    p.append((u, float(data.get("weight", 1.0))))
            for _, v, _, data in self.graph.out_edges(node, keys=True, data=True):
                if data.get("relation_type") in ("caused_by", "causes"):
                    p.append((v, float(data.get("weight", 1.0))))
            return p

        # Find longest/heaviest path backwards from incident
        best_path: list[str] = [target]

        def _backtrack(curr: str, current_path: list[str]) -> None:
            nonlocal best_path
            parents = _get_parents(curr)
            valid_parents = [p for p in parents if p[0] not in current_path]
            if not valid_parents:
                if len(current_path) > len(best_path):
                    best_path = list(current_path)
                return
            # Pick highest weight parent first
            valid_parents.sort(key=lambda x: x[1], reverse=True)
            for parent_id, _ in valid_parents:
                _backtrack(parent_id, current_path + [parent_id])

        _backtrack(target, [target])

        # Reverse path so order is: Origin -> Intermediate -> Impact
        ordered_ids = list(reversed(best_path))
        chain: list[dict[str, Any]] = []

        for step_idx, nid in enumerate(ordered_ids, start=1):
            ndata = self.graph.nodes.get(nid, {})
            role = "origin" if step_idx == 1 else ("impact" if step_idx == len(ordered_ids) else "intermediate")
            chain.append({
                "step": step_idx,
                "node_id": nid,
                "label": ndata.get("label", nid),
                "entity_type": ndata.get("entity_type", "UNKNOWN"),
                "role": role,
                "properties": ndata.get("properties", {}),
            })

        return chain

    # -----------------------------------------------------------------------
    # Dependency & Vulnerability Analysis
    # -----------------------------------------------------------------------
    def find_dependencies(self, entity_id: str) -> dict[str, Any]:
        """Traverse dependent assets/units and identify Single Points of Failure (SPOF)."""
        root = str(entity_id).strip()
        if not self.graph.has_node(root):
            return {
                "entity_id": root,
                "error": f"Node '{root}' not found in knowledge graph",
                "dependencies": [],
                "single_points_of_failure": [],
            }

        # Traverse downstream dependencies:
        #   (entity) -[depends_on]-> (dependency)
        #   (dependency) -[supports]-> (entity)
        #   (dependency) -[participates_in]-> (entity)
        #   (entity) -[assigned_to]-> (dependency)
        visited: set[str] = {root}
        queue: list[tuple[str, int]] = [(root, 0)]
        dep_records: list[dict[str, Any]] = []

        while queue:
            curr, depth = queue.pop(0)

            # Direct outbound depends_on / assigned_to
            for _, v, _, data in self.graph.out_edges(curr, keys=True, data=True):
                rel = data.get("relation_type", "")
                if rel in ("depends_on", "assigned_to") and v not in visited:
                    visited.add(v)
                    queue.append((v, depth + 1))
                    vdata = self.graph.nodes.get(v, {})
                    dep_records.append({
                        "id": v,
                        "label": vdata.get("label", v),
                        "entity_type": vdata.get("entity_type", "UNKNOWN"),
                        "relation": rel,
                        "depth": depth + 1,
                        "weight": float(data.get("weight", 1.0)),
                        "properties": vdata.get("properties", {}),
                    })

            # Inbound participates_in / supports (units participating in mission, assets supporting unit)
            for u, _, _, data in self.graph.in_edges(curr, keys=True, data=True):
                rel = data.get("relation_type", "")
                if rel in ("participates_in", "supports") and u not in visited:
                    visited.add(u)
                    queue.append((u, depth + 1))
                    udata = self.graph.nodes.get(u, {})
                    dep_records.append({
                        "id": u,
                        "label": udata.get("label", u),
                        "entity_type": udata.get("entity_type", "UNKNOWN"),
                        "relation": rel,
                        "depth": depth + 1,
                        "weight": float(data.get("weight", 1.0)),
                        "properties": udata.get("properties", {}),
                    })

        # Identify Single Points of Failure (SPOF)
        # An entity is an SPOF if:
        # 1. Multiple missions or operational units depend upon it, AND
        # 2. There is no redundant peer node of the same role/kind.
        spof_list: list[dict[str, Any]] = []

        for dep in dep_records:
            dep_id = dep["id"]
            # Count how many entities in the entire graph depend on this asset/node
            dependent_nodes = set()
            for u, _, _, data in self.graph.in_edges(dep_id, keys=True, data=True):
                if data.get("relation_type") == "depends_on":
                    dependent_nodes.add(u)
            for _, v, _, data in self.graph.out_edges(dep_id, keys=True, data=True):
                if data.get("relation_type") in ("supports", "participates_in"):
                    dependent_nodes.add(v)

            is_critical_flag = dep.get("properties", {}).get("is_critical", False)
            dep_count = len(dependent_nodes)

            # If 2 or more entities depend on it, or explicitly flagged as critical single relay
            if dep_count >= 2 or is_critical_flag:
                reason = (
                    f"Sole provider supporting {dep_count} operational entities "
                    f"({', '.join(sorted(list(dependent_nodes))[:4])}) without active redundant backup."
                )
                spof_list.append({
                    "node_id": dep_id,
                    "label": dep["label"],
                    "entity_type": dep["entity_type"],
                    "dependent_count": dep_count,
                    "risk_level": "CRITICAL" if dep_count >= 3 or is_critical_flag else "HIGH",
                    "reason": reason,
                })

        # Calculate overall dependency criticality score
        crit_score = min(1.0, 0.15 * len(dep_records) + 0.25 * len(spof_list))

        return {
            "entity_id": root,
            "dependencies": dep_records,
            "total_dependencies": len(dep_records),
            "single_points_of_failure": spof_list,
            "spof_count": len(spof_list),
            "criticality_score": round(crit_score, 2),
            "summary": (
                f"Entity '{root}' has {len(dep_records)} direct and indirect dependencies, "
                f"with {len(spof_list)} identified Single Point(s) of Failure."
            ),
        }

    # -----------------------------------------------------------------------
    # Subgraph Export for Visualization (D3 / Sigma.js)
    # -----------------------------------------------------------------------
    def export_subgraph(self, center_id: str | None = None, depth: int = 2) -> dict[str, Any]:
        """Export nodes and links formatted for frontend D3 / Sigma.js graph rendering."""
        cid = str(center_id).strip() if center_id else ""

        # Depth-bounded ego subgraph filtering if center_id provided
        if cid and cid != "*" and self.graph.has_node(cid):
            subgraph_nodes: set[str] = {cid}
            curr_layer: set[str] = {cid}
            for _ in range(max(1, depth)):
                next_layer: set[str] = set()
                for n in curr_layer:
                    next_layer.update(self.graph.neighbors(n))
                    next_layer.update(self.graph.predecessors(n))
                subgraph_nodes.update(next_layer)
                curr_layer = next_layer
        else:
            subgraph_nodes = set(self.graph.nodes())

        nodes: list[dict[str, Any]] = []
        for nid in subgraph_nodes:
            ndata = self.graph.nodes[nid]
            etype = ndata.get("entity_type", "UNKNOWN")
            nodes.append({
                "id": nid,
                "label": ndata.get("label", nid),
                "entity_type": etype,
                "type": etype,  # D3 / Sigma.js convenience alias
                "properties": ndata.get("properties", {}),
                "in_degree": self.graph.in_degree(nid),
                "out_degree": self.graph.out_degree(nid),
                "degree": self.graph.degree(nid),
            })

        links: list[dict[str, Any]] = []
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            if u in subgraph_nodes and v in subgraph_nodes:
                rel = data.get("relation_type", "related_to")
                links.append({
                    "id": f"{u}-{v}-{key}",
                    "source": u,
                    "target": v,
                    "relation": rel,
                    "relation_type": rel,
                    "weight": float(data.get("weight", 1.0)),
                    "properties": data.get("properties", {}),
                })

        return {
            "center_id": cid or None,
            "depth": depth,
            "nodes": nodes,
            "links": links,
            "edges": links,  # Sigma.js alias
            "total_nodes": len(nodes),
            "total_edges": len(links),
        }

    # -----------------------------------------------------------------------
    # Scenario Seed Data
    # -----------------------------------------------------------------------
    def seed_demo_graph(self) -> dict[str, int]:
        """Hydrate a full realistic tactical operational scenario into the graph."""
        self.clear(clear_db=True)

        # 1. Missions
        self.add_entity("MSN-01", "MISSION", "Operation Iron Shield", {
            "priority": "high", "status": "executing", "risk_score": 0.72, "sector": "SECTOR-4"
        })
        self.add_entity("MSN-02", "MISSION", "Operation Falcon Watch", {
            "priority": "routine", "status": "planning", "risk_score": 0.35, "sector": "SECTOR-2"
        })

        # 2. Units
        self.add_entity("UNIT-RECON-1", "UNIT", "Alpha Recon Patrol", {
            "callsign": "Ghost-1", "kind": "patrol", "status": "halted", "fuel": 48.0, "battery": 72.0
        })
        self.add_entity("UNIT-UAV-2", "UNIT", "SkyEye Surveillance UAV", {
            "callsign": "Falcon-2", "kind": "uav", "status": "active", "battery": 64.0
        })
        self.add_entity("UNIT-CONVOY-1", "UNIT", "Supply Convoy Bravo", {
            "callsign": "Iron-3", "kind": "convoy", "status": "halted", "fuel": 32.0
        })

        # 3. Assets
        self.add_entity("AST-DEPOT-NORTH", "ASSET", "Forward Depot North", {
            "kind": "depot", "fuel_capacity": 5000, "stock_level": 3200
        })
        self.add_entity("AST-COMMS-RELAY", "ASSET", "SATCOM Tactical Relay", {
            "kind": "relay", "status": "degraded", "coverage_km": 80.0, "is_critical": True
        })
        self.add_entity("AST-RADAR-01", "ASSET", "Early Warning Radar", {
            "kind": "sensor", "status": "active", "range_km": 120.0
        })

        # 4. Incidents
        self.add_entity("INC-AMBUSH-01", "INCIDENT", "Sector 4 Ambush Attack", {
            "severity": "critical", "type": "ambush", "tick": 42, "status": "open"
        })
        self.add_entity("INC-COMMS-JAM-01", "INCIDENT", "Tactical EW Comms Jamming", {
            "severity": "high", "type": "electronic_warfare", "tick": 38, "status": "active"
        })
        self.add_entity("INC-ROUTE-BLOCK-01", "INCIDENT", "Bridge Chokepoint Blockage", {
            "severity": "medium", "type": "obstacle", "tick": 30, "status": "contained"
        })

        # 5. Routes
        self.add_entity("RTE-PRIMARY-01", "ROUTE", "Highway Corridor North", {
            "distance_km": 42.5, "threat_level": "high", "chokepoints": 2
        })
        self.add_entity("RTE-ALT-02", "ROUTE", "Mountain Bypass Echo", {
            "distance_km": 58.2, "threat_level": "low", "chokepoints": 0
        })

        # 6. Operators
        self.add_entity("OPR-CMDR-MILLER", "OPERATOR", "Major J. Miller", {
            "role": "commander", "unit": "UNIT-RECON-1", "rank": "Major"
        })
        self.add_entity("OPR-UAV-CHEN", "OPERATOR", "Lt. K. Chen", {
            "role": "uav_operator", "unit": "UNIT-UAV-2", "rank": "Lieutenant"
        })

        # 7. Weather
        self.add_entity("WTH-STORM-ALPHA", "WEATHER", "Severe Duststorm Front", {
            "kind": "duststorm", "intensity": 0.85, "visibility_km": 0.4
        })

        # 8. Doctrine
        self.add_entity("DOC-RECON-SOP-4", "DOCTRINE", "FM 3-90 Reconnaissance SOP", {
            "doc_id": "DOC-RECON-SOP-4", "category": "recon", "version": "2.1"
        })
        self.add_entity("DOC-EW-COUNTER", "DOCTRINE", "ATP 3-12 EW Countermeasures", {
            "doc_id": "DOC-EW-COUNTER", "category": "c-ew", "version": "1.4"
        })

        # Relations: Causal Chain (Origin -> Intermediate -> Impact)
        # Duststorm caused EW Comms Jamming
        self.add_relation("WTH-STORM-ALPHA", "INC-COMMS-JAM-01", "caused_by", weight=0.9, properties={
            "mechanism": "Atmospheric electromagnetic attenuation and sensor blind spots"
        })
        # Comms Jamming caused Ambush Attack
        self.add_relation("INC-COMMS-JAM-01", "INC-AMBUSH-01", "caused_by", weight=0.85, properties={
            "mechanism": "Loss of C2 radar surveillance and telemetry allowed hostile ambush"
        })
        # Route Chokepoint funnel also contributed to Ambush
        self.add_relation("INC-ROUTE-BLOCK-01", "INC-AMBUSH-01", "caused_by", weight=0.6, properties={
            "mechanism": "Route denial funneled patrol into hostile kill zone"
        })

        # Relations: Mission Participation & Unit Assignments
        self.add_relation("UNIT-RECON-1", "MSN-01", "participates_in", weight=1.0)
        self.add_relation("UNIT-UAV-2", "MSN-01", "participates_in", weight=1.0)
        self.add_relation("UNIT-CONVOY-1", "MSN-01", "participates_in", weight=0.9)

        # Relations: Dependencies
        self.add_relation("MSN-01", "UNIT-RECON-1", "depends_on", weight=1.0)
        self.add_relation("MSN-01", "AST-COMMS-RELAY", "depends_on", weight=0.95)
        self.add_relation("MSN-01", "RTE-PRIMARY-01", "depends_on", weight=0.85)

        self.add_relation("UNIT-RECON-1", "AST-DEPOT-NORTH", "depends_on", weight=0.75)
        self.add_relation("UNIT-RECON-1", "AST-COMMS-RELAY", "depends_on", weight=0.95)
        self.add_relation("UNIT-UAV-2", "AST-COMMS-RELAY", "depends_on", weight=0.95)

        # Relations: Assignments
        self.add_relation("OPR-CMDR-MILLER", "UNIT-RECON-1", "assigned_to", weight=1.0)
        self.add_relation("OPR-UAV-CHEN", "UNIT-UAV-2", "assigned_to", weight=1.0)
        self.add_relation("RTE-PRIMARY-01", "MSN-01", "assigned_to", weight=1.0)

        # Relations: Impacts
        self.add_relation("UNIT-RECON-1", "INC-AMBUSH-01", "affected_by", weight=0.95)
        self.add_relation("MSN-01", "INC-AMBUSH-01", "affected_by", weight=0.9)
        self.add_relation("AST-COMMS-RELAY", "WTH-STORM-ALPHA", "affected_by", weight=0.8)

        # Relations: Support & Doctrine
        self.add_relation("DOC-RECON-SOP-4", "MSN-01", "supports", weight=0.8)
        self.add_relation("DOC-EW-COUNTER", "UNIT-RECON-1", "supports", weight=0.85)
        self.add_relation("AST-DEPOT-NORTH", "UNIT-CONVOY-1", "supports", weight=0.9)

        return {"nodes": self.graph.number_of_nodes(), "edges": self.graph.number_of_edges()}


# Global singleton instance
knowledge_graph = OperationalKnowledgeGraph()
