"""Persistent Long-Term Memory Store for DOIP Unified Agents.

Provides three distinct cognitive memory tiers:
1. SemanticMemory: General operational knowledge, doctrine rules, tactical concepts.
2. EpisodicMemory: Historical mission episodes, turning points, after-action events.
3. OperationalMemory: Immediate context, active telemetry window, real-time track buffers.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional

from app import db
from app.time_utils import utc_iso

logger = logging.getLogger("doip.memory_store")


class SemanticMemory:
    """Persistent factual and doctrine knowledge."""

    def __init__(self) -> None:
        self.memory_type = "semantic"

    def record(
        self,
        content: str,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance: float = 1.0,
    ) -> Dict[str, Any]:
        doc = {
            "id": f"mem-sem-{uuid.uuid4().hex[:8]}",
            "agent_id": agent_id,
            "memory_type": self.memory_type,
            "content": content,
            "tags": tags or ["doctrine", "factual"],
            "importance": importance,
        }
        return db.save_agent_memory(doc)


class EpisodicMemory:
    """Historical timeline of mission events and turning points."""

    def __init__(self) -> None:
        self.memory_type = "episodic"

    def record(
        self,
        content: str,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance: float = 1.0,
    ) -> Dict[str, Any]:
        doc = {
            "id": f"mem-epi-{uuid.uuid4().hex[:8]}",
            "agent_id": agent_id,
            "memory_type": self.memory_type,
            "content": content,
            "tags": tags or ["episode", "mission_event"],
            "importance": importance,
        }
        return db.save_agent_memory(doc)


class OperationalMemory:
    """Fast scratchpad and active working memory for running agents."""

    def __init__(self) -> None:
        self.memory_type = "operational"
        self._working_cache: Dict[str, Any] = {}

    def set_context(self, key: str, value: Any) -> None:
        self._working_cache[key] = {
            "value": value,
            "updated_at": utc_iso(),
        }

    def get_context(self, key: str) -> Optional[Any]:
        entry = self._working_cache.get(key)
        return entry["value"] if entry else None

    def record(
        self,
        content: str,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance: float = 0.8,
    ) -> Dict[str, Any]:
        doc = {
            "id": f"mem-op-{uuid.uuid4().hex[:8]}",
            "agent_id": agent_id,
            "memory_type": self.memory_type,
            "content": content,
            "tags": tags or ["telemetry", "working_state"],
            "importance": importance,
        }
        return db.save_agent_memory(doc)


class MemoryStore:
    """Unified coordinator across Semantic, Episodic, and Operational memories."""

    _instance: Optional[MemoryStore] = None

    def __init__(self) -> None:
        self.semantic = SemanticMemory()
        self.episodic = EpisodicMemory()
        self.operational = OperationalMemory()

    @classmethod
    def get_instance(cls) -> MemoryStore:
        if cls._instance is None:
            cls._instance = MemoryStore()
        return cls._instance

    def remember(
        self,
        content: str,
        agent_id: Optional[str] = None,
        memory_type: str = "semantic",
        tags: Optional[List[str]] = None,
        importance: float = 1.0,
    ) -> Dict[str, Any]:
        """Store a new memory entry into the specified memory tier."""
        mem_type = memory_type.lower()
        if mem_type == "episodic":
            return self.episodic.record(content, agent_id, tags, importance)
        elif mem_type == "operational":
            return self.operational.record(content, agent_id, tags, importance)
        else:
            return self.semantic.record(content, agent_id, tags, importance)

    def retrieve(
        self,
        query: str,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories matching query string."""
        if not query or query.strip() == "*":
            return db.list_agent_memories(
                agent_id=agent_id, memory_type=memory_type, limit=limit
            )
        # Search by substring / tags
        results = db.search_agent_memories(
            query_str=query.strip(), agent_id=agent_id, limit=limit
        )
        if memory_type:
            results = [r for r in results if r.get("memory_type") == memory_type]
        return results

    def summarize(
        self, agent_id: Optional[str] = None, memory_type: Optional[str] = None
    ) -> str:
        """Generate a concise narrative summary of stored operational memories."""
        memories = db.list_agent_memories(
            agent_id=agent_id, memory_type=memory_type, limit=20
        )
        if not memories:
            return "No operational memories recorded for the given scope."
        lines = [
            f"- [{m.get('memory_type', 'mem').upper()}] {m.get('content')}"
            for m in memories[:10]
        ]
        return "Consolidated Intelligence Summary:\n" + "\n".join(lines)

    def consolidate(self) -> Dict[str, Any]:
        """Consolidate high-importance episodic memories into permanent semantic doctrine."""
        episodic_mems = db.list_agent_memories(memory_type="episodic", limit=50)
        high_importance = [
            m for m in episodic_mems if float(m.get("importance", 1.0)) >= 1.2
        ]
        consolidated_count = 0
        for m in high_importance:
            # Transfer distilled principle
            content = f"Distilled Lesson from {m.get('id')}: {m.get('content')}"
            self.semantic.record(
                content=content,
                agent_id=m.get("agent_id"),
                tags=["consolidated", "doctrine_update"],
                importance=m.get("importance", 1.2),
            )
            consolidated_count += 1

        return {
            "status": "consolidated",
            "episodes_reviewed": len(episodic_mems),
            "consolidated_into_semantic": consolidated_count,
            "timestamp": utc_iso(),
        }


# Singleton accessor
memory_store = MemoryStore.get_instance()
