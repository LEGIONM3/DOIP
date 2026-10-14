"""Unit tests for DOIP Phase 3 Operational Knowledge Graph."""

import pytest
from app.knowledge_graph import (
    OperationalKnowledgeGraph,
    VALID_ENTITY_TYPES,
    VALID_RELATION_TYPES,
    knowledge_graph,
)


def test_standard_types_and_relations():
    assert "MISSION" in VALID_ENTITY_TYPES
    assert "UNIT" in VALID_ENTITY_TYPES
    assert "ASSET" in VALID_ENTITY_TYPES
    assert "INCIDENT" in VALID_ENTITY_TYPES
    assert "ROUTE" in VALID_ENTITY_TYPES
    assert "OPERATOR" in VALID_ENTITY_TYPES
    assert "WEATHER" in VALID_ENTITY_TYPES
    assert "DOCTRINE" in VALID_ENTITY_TYPES

    assert "participates_in" in VALID_RELATION_TYPES
    assert "assigned_to" in VALID_RELATION_TYPES
    assert "affected_by" in VALID_RELATION_TYPES
    assert "depends_on" in VALID_RELATION_TYPES
    assert "caused_by" in VALID_RELATION_TYPES
    assert "supports" in VALID_RELATION_TYPES


def test_entity_and_relation_addition():
    kg = OperationalKnowledgeGraph()
    kg.clear(clear_db=False)

    node = kg.add_entity("TEST-UAV-1", "unit", "Test UAV 1", {"battery": 90.0})
    assert node["id"] == "TEST-UAV-1"
    assert node["entity_type"] == "UNIT"
    assert node["label"] == "Test UAV 1"
    assert node["properties"]["battery"] == 90.0
    assert kg.graph.has_node("TEST-UAV-1")

    node_m = kg.add_entity("TEST-MSN-1", "mission", "Test Mission 1")
    edge = kg.add_relation("TEST-UAV-1", "TEST-MSN-1", "participates_in", weight=0.95)
    assert edge["source_id"] == "TEST-UAV-1"
    assert edge["target_id"] == "TEST-MSN-1"
    assert edge["relation_type"] == "participates_in"
    assert edge["weight"] == 0.95
    assert kg.graph.has_edge("TEST-UAV-1", "TEST-MSN-1")


def test_seed_demo_graph_and_queries():
    knowledge_graph.seed_demo_graph()
    assert knowledge_graph.graph.number_of_nodes() >= 18
    assert knowledge_graph.graph.number_of_edges() >= 20

    # Test root cause analysis
    rc = knowledge_graph.find_root_cause("INC-AMBUSH-01")
    assert rc["root_cause_id"] == "WTH-STORM-ALPHA"
    assert rc["attribution_score"] > 0.7
    assert len(rc["causal_chain"]) == 3
    assert rc["causal_chain"][0]["node_id"] == "WTH-STORM-ALPHA"
    assert rc["causal_chain"][-1]["node_id"] == "INC-AMBUSH-01"

    # Test dependency traversal
    deps = knowledge_graph.find_dependencies("MSN-01")
    dep_list = deps.get("dependencies", [])
    assert len(dep_list) >= 4
    dep_ids = {d["id"] for d in dep_list}
    assert "UNIT-RECON-1" in dep_ids
    assert "AST-COMMS-RELAY" in dep_ids

    # Test SPOF identification
    spofs = deps.get("single_points_of_failure", [])
    assert len(spofs) >= 1
    spof_ids = {s["node_id"] for s in spofs}
    assert "AST-COMMS-RELAY" in spof_ids

    # Test incident chain
    chain = knowledge_graph.trace_incident_chain("INC-AMBUSH-01")
    assert len(chain) == 3
    assert chain[0]["node_id"] == "WTH-STORM-ALPHA"
    assert chain[1]["node_id"] == "INC-COMMS-JAM-01"
    assert chain[2]["node_id"] == "INC-AMBUSH-01"

    # Test subgraph export
    subgraph = knowledge_graph.export_subgraph("MSN-01", depth=2)
    assert len(subgraph["nodes"]) > 5
    assert len(subgraph["links"]) > 5
