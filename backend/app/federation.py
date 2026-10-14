"""Federated Command Architecture for DOIP (Phase 4A).

Implements decentralized multi-node command hierarchy:
1. RegionalNode: Top-level strategic authority overseeing multi-theater commands.
2. OperationalNode: Regional operational controller coordinating active missions & worlds.
3. TacticalNode: Battle-space tactical unit node executing localized operations.

Supports:
- Command hierarchy: Orders cascade down; telemetry & incidents bubble up.
- Synchronized intelligence: Cross-node doctrine & threat replication.
- Replicated state & health heartbeats.
- Strict human approval boundaries preserved across all federation tiers.
"""

from __future__ import annotations

import datetime
import json
import logging
import uuid
from typing import Any, Literal

try:
    from . import db
except ImportError:
    from app import db

log = logging.getLogger(__name__)

TierType = Literal["regional", "operational", "tactical"]


class FederationNode:
    """Base class representing a node in the federated command network."""

    def __init__(
        self,
        node_id: str,
        name: str,
        tier: TierType = "tactical",
        region: str = "GLOBAL",
        endpoint: str = "",
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.node_id = node_id
        self.name = name
        self.tier = tier
        self.region = region
        self.endpoint = endpoint
        self.parent_id = parent_id
        self.metadata = metadata or {}
        self.status = "online"
        self.last_heartbeat = datetime.datetime.now(datetime.timezone.utc)
        self.replicated_intelligence: list[dict[str, Any]] = []
        self.active_directives: list[dict[str, Any]] = []

    def heartbeat(self) -> dict[str, Any]:
        """Record node liveness and update persistence."""
        self.last_heartbeat = datetime.datetime.now(datetime.timezone.utc)
        record = {
            "id": self.node_id,
            "name": self.name,
            "tier": self.tier,
            "region": self.region,
            "endpoint": self.endpoint,
            "status": self.status,
            "metadata": {
                **self.metadata,
                "parent_id": self.parent_id,
                "directives_count": len(self.active_directives),
            },
        }
        return db.save_federation_node(record)

    def receive_directive(self, directive: dict[str, Any]) -> dict[str, Any]:
        """Receive command directive from upstream node."""
        staged_directive = {
            "id": directive.get("id") or f"DIR-{uuid.uuid4().hex[:6].upper()}",
            "origin_node_id": directive.get("origin_node_id", "REGIONAL-HQ"),
            "target_tier": self.tier,
            "title": directive.get("title", "Operational Directive"),
            "content": directive.get("content", ""),
            "requires_human_confirmation": True,  # Mandatory safety gate
            "status": "staged",
            "received_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.active_directives.append(staged_directive)
        return staged_directive

    def share_intelligence(self, intel_item: dict[str, Any]) -> dict[str, Any]:
        """Ingest synchronized intelligence package."""
        entry = {
            "id": intel_item.get("id") or f"INTEL-{uuid.uuid4().hex[:6].upper()}",
            "source_node": intel_item.get("source_node", self.node_id),
            "kind": intel_item.get("kind", "THREAT_ALERT"),
            "payload": intel_item.get("payload", {}),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.replicated_intelligence.append(entry)
        return entry

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "name": self.name,
            "tier": self.tier,
            "region": self.region,
            "endpoint": self.endpoint,
            "parent_id": self.parent_id,
            "status": self.status,
            "heartbeat_at": self.last_heartbeat.isoformat(),
            "metadata": self.metadata,
            "directives_count": len(self.active_directives),
            "intelligence_count": len(self.replicated_intelligence),
        }


class RegionalNode(FederationNode):
    """Top-level strategic regional authority."""

    def __init__(self, node_id: str, name: str, region: str = "GLOBAL", endpoint: str = "") -> None:
        super().__init__(node_id=node_id, name=name, tier="regional", region=region, endpoint=endpoint)
        self.operational_nodes: list[str] = []

    def register_subordinate(self, node_id: str) -> None:
        if node_id not in self.operational_nodes:
            self.operational_nodes.append(node_id)


class TheaterNode(FederationNode):
    """Theater-level operational command node."""

    def __init__(self, node_id: str, name: str, theater_code: str, region: str = "GLOBAL", endpoint: str = "") -> None:
        super().__init__(
            node_id=node_id,
            name=name,
            tier="operational",
            region=region,
            endpoint=endpoint,
            metadata={"theater_code": theater_code},
        )
        self.theater_code = theater_code
        self.tactical_nodes: list[str] = []

    def register_tactical_unit(self, unit_node_id: str) -> None:
        if unit_node_id not in self.tactical_nodes:
            self.tactical_nodes.append(unit_node_id)


class FederationManager:
    """Orchestrator for the distributed federated command mesh."""

    def __init__(self) -> None:
        self.nodes: dict[str, FederationNode] = {}
        self._initialize_default_topology()

    def _initialize_default_topology(self) -> None:
        """Seed initial federated command hierarchy."""
        # 1. Regional Strategic HQ
        hq = RegionalNode(
            node_id="NODE-REGIONAL-HQ",
            name="Joint Regional Defense Command",
            region="CENTRAL-ASIA-PACIFIC",
            endpoint="https://fed-hq.doip.mil:8443",
        )
        # 2. Theater Operational Nodes
        theater_north = TheaterNode(
            node_id="NODE-THEATER-NORTH",
            name="Northern Mountain Theater Command",
            theater_code="THEATER-NORTH",
            region="NORTH-SECTOR",
            endpoint="https://fed-north.doip.mil:8443",
        )
        theater_east = TheaterNode(
            node_id="NODE-THEATER-EAST",
            name="Eastern Maritime Theater Command",
            theater_code="THEATER-EAST",
            region="EAST-LITTORAL",
            endpoint="https://fed-east.doip.mil:8443",
        )
        # 3. Tactical Nodes
        tactical_recon = FederationNode(
            node_id="NODE-TACTICAL-RECON-1",
            name="1st Tactical Reconnaissance Wing",
            tier="tactical",
            region="NORTH-SECTOR",
            parent_id="NODE-THEATER-NORTH",
        )

        hq.register_subordinate(theater_north.node_id)
        hq.register_subordinate(theater_east.node_id)
        theater_north.register_tactical_unit(tactical_recon.node_id)

        for n in [hq, theater_north, theater_east, tactical_recon]:
            self.register_node(n)

    def register_node(self, node: FederationNode) -> dict[str, Any]:
        """Register node in memory and persistent database."""
        self.nodes[node.node_id] = node
        return node.heartbeat()

    def get_node(self, node_id: str) -> FederationNode | None:
        return self.nodes.get(node_id)

    def list_nodes(self, tier: str | None = None) -> list[dict[str, Any]]:
        """List active nodes in federation network."""
        res = []
        for n in self.nodes.values():
            if tier and n.tier != tier:
                continue
            res.append(n.to_dict())
        return res

    def broadcast_directive(
        self,
        origin_id: str,
        directive_title: str,
        content: str,
        target_tier: str = "operational",
    ) -> list[dict[str, Any]]:
        """Cascade strategic directive down through the hierarchy."""
        results = []
        directive_payload = {
            "id": f"DIR-{uuid.uuid4().hex[:6].upper()}",
            "origin_node_id": origin_id,
            "title": directive_title,
            "content": content,
        }
        for n in self.nodes.values():
            if n.tier == target_tier or target_tier == "all":
                res = n.receive_directive(directive_payload)
                n.heartbeat()
                results.append({"node_id": n.node_id, "directive": res})
        return results

    def synchronize_intelligence(self, source_node_id: str, intel_type: str, payload: dict[str, Any]) -> int:
        """Propagate tactical intelligence horizontally and vertically."""
        count = 0
        pkg = {
            "source_node": source_node_id,
            "kind": intel_type,
            "payload": payload,
        }
        for nid, n in self.nodes.items():
            if nid != source_node_id:
                n.share_intelligence(pkg)
                n.heartbeat()
                count += 1
        return count


# Singleton instance
federation_manager = FederationManager()
