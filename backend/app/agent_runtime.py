"""Unified Agent Runtime for Defense Operations Intelligence Platform (DOIP).

Provides centralized lifecycle management, task scheduling, routing,
and coordination for all operational AI agents (Copilot, Strategic Copilot,
Red Team, Forecaster, Knowledge Agents, Swarm Agents).
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from app import db
from app.time_utils import utc_iso

logger = logging.getLogger("doip.agent_runtime")


class AgentRegistry:
    """Central directory of active and staged agents in the platform."""

    def __init__(self) -> None:
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._load_from_db()

    def _load_from_db(self) -> None:
        try:
            persisted = db.list_agents()
            for a in persisted:
                self._agents[a["id"]] = a
        except Exception as e:
            logger.warning("Could not pre-load agents from database: %s", e)

    def register(
        self,
        agent_id: str,
        name: str,
        role: str,
        capabilities: List[str] | None = None,
        status: str = "idle",
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        record = {
            "id": agent_id,
            "name": name,
            "role": role,
            "status": status,
            "capabilities": capabilities or [],
            "metadata": metadata or {},
            "updated_at": utc_iso(),
        }
        self._agents[agent_id] = record
        try:
            db.save_agent(record)
        except Exception as e:
            logger.warning("Failed to persist agent %s: %s", agent_id, e)
        return record

    def deregister(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            self._agents[agent_id]["status"] = "offline"
            try:
                db.save_agent(self._agents[agent_id])
            except Exception:
                pass
            del self._agents[agent_id]
            return True
        return False

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        if agent_id in self._agents:
            return self._agents[agent_id]
        persisted = db.get_agent(agent_id)
        if persisted:
            self._agents[agent_id] = persisted
            return persisted
        return None

    def list_all(
        self, status: Optional[str] = None, role: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        agents = list(self._agents.values())
        if status:
            agents = [a for a in agents if a.get("status") == status]
        if role:
            agents = [a for a in agents if a.get("role") == role]
        return agents

    list_agents = list_all

    def find_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        return [
            a
            for a in self._agents.values()
            if capability in a.get("capabilities", [])
        ]


class AgentTaskQueue:
    """Prioritized queue and execution tracker for agent tasks."""

    def __init__(self) -> None:
        self._queue: List[Dict[str, Any]] = []

    def enqueue(
        self,
        task_type: str,
        payload: Dict[str, Any],
        agent_id: Optional[str] = None,
        priority: int = 1,
    ) -> Dict[str, Any]:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = {
            "id": task_id,
            "agent_id": agent_id,
            "task_type": task_type,
            "payload": payload,
            "priority": priority,
            "status": "pending",
            "result": None,
            "created_at": utc_iso(),
        }
        self._queue.append(task)
        # Sort queue descending by priority
        self._queue.sort(key=lambda t: t.get("priority", 1), reverse=True)
        try:
            db.save_agent_task(task)
        except Exception as e:
            logger.warning("Could not persist agent task %s: %s", task_id, e)
        return task

    def dequeue(self, agent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        for i, task in enumerate(self._queue):
            if task.get("status") == "pending":
                if agent_id is None or task.get("agent_id") in (None, agent_id):
                    task["status"] = "in_progress"
                    if agent_id:
                        task["agent_id"] = agent_id
                    try:
                        db.update_agent_task_status(task["id"], "in_progress")
                    except Exception:
                        pass
                    return self._queue.pop(i)
        return None

    def complete(self, task_id: str, result: Dict[str, Any]) -> bool:
        try:
            db.update_agent_task_status(task_id, "completed", result=result)
            return True
        except Exception as e:
            logger.warning("Failed to complete task %s: %s", task_id, e)
            return False

    def fail(self, task_id: str, error_msg: str) -> bool:
        try:
            db.update_agent_task_status(
                task_id, "failed", result={"error": error_msg}
            )
            return True
        except Exception as e:
            logger.warning("Failed to fail task %s: %s", task_id, e)
            return False

    def list_tasks(
        self, agent_id: Optional[str] = None, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        return db.list_agent_tasks(agent_id=agent_id, status=status, limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        pending = sum(1 for t in self._queue if t.get("status") == "pending")
        in_progress = sum(1 for t in self._queue if t.get("status") == "in_progress")
        return {
            "total_queued": len(self._queue),
            "pending": pending,
            "in_progress": in_progress,
        }


class AgentCoordinator:
    """Coordinates task routing and execution across registered agents."""

    def __init__(self, registry: AgentRegistry, task_queue: AgentTaskQueue) -> None:
        self.registry = registry
        self.task_queue = task_queue
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    def register_handler(
        self, task_type: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        self._handlers[task_type] = handler

    def execute_task(
        self, task_type: str, payload: Dict[str, Any], agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        # Enqueue task
        task = self.task_queue.enqueue(task_type, payload, agent_id=agent_id)
        task_id = task["id"]

        # If a direct handler exists, execute synchronously
        if task_type in self._handlers:
            handler = self._handlers[task_type]
            try:
                result = handler(payload)
                self.task_queue.complete(task_id, result)
                task["status"] = "completed"
                task["result"] = result
                return task
            except Exception as e:
                self.task_queue.fail(task_id, str(e))
                task["status"] = "failed"
                task["result"] = {"error": str(e)}
                return task

        # Fallback default simulation handler
        result = {
            "ack": True,
            "task_type": task_type,
            "dispatched_to": agent_id or "autonomous_swarm",
            "message": f"Task {task_id} processed by unified coordinator.",
            "timestamp": utc_iso(),
        }
        self.task_queue.complete(task_id, result)
        task["status"] = "completed"
        task["result"] = result
        return task


class AgentRuntime:
    """Master Unified Agent Runtime for all DOIP operational agents."""

    _instance: Optional[AgentRuntime] = None

    def __init__(self) -> None:
        self.registry = AgentRegistry()
        self.task_queue = AgentTaskQueue()
        self.coordinator = AgentCoordinator(self.registry, self.task_queue)
        self._bootstrap_core_agents()

    @classmethod
    def get_instance(cls) -> AgentRuntime:
        if cls._instance is None:
            cls._instance = AgentRuntime()
        return cls._instance

    def _bootstrap_core_agents(self) -> None:
        """Register the platform's core operational agents."""
        core_agents = [
            (
                "agent-copilot-01",
                "Mission Copilot",
                "copilot",
                ["mission_planning", "tactical_advisory", "route_review"],
            ),
            (
                "agent-strat-01",
                "Strategic Copilot",
                "strategic_copilot",
                ["theater_strategy", "multi_campaign_sync", "resource_allocation"],
            ),
            (
                "agent-redteam-01",
                "Red Team Adversary",
                "red_team",
                ["stress_testing", "vulnerability_discovery", "scenario_injection"],
            ),
            (
                "agent-forecast-01",
                "Predictive Forecaster",
                "forecaster",
                ["temporal_lookahead", "risk_tensor_generation", "pnr_evaluation"],
            ),
            (
                "agent-knowledge-01",
                "Knowledge Synthesizer",
                "knowledge_agent",
                ["graph_causal_reasoning", "cross_source_synthesis", "doctrine_rag"],
            ),
            (
                "agent-analysis-01",
                "Autonomous Analyst",
                "analyst",
                ["anomaly_detection", "bottleneck_analysis", "readiness_tracking"],
            ),
            (
                "agent-swarm-lead",
                "Autonomous Swarm Lead",
                "swarm_lead",
                ["distributed_planning", "multi_agent_consensus", "parallel_execution"],
            ),
        ]
        for aid, name, role, caps in core_agents:
            if not self.registry.get(aid):
                self.registry.register(aid, name, role, caps, status="idle")

    def submit_task(
        self, task_type: str, payload: Dict[str, Any], agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dispatch a task to the unified agent coordinator."""
        return self.coordinator.execute_task(task_type, payload, agent_id=agent_id)

    def get_status(self) -> Dict[str, Any]:
        """Get aggregate operational runtime status."""
        agents = self.registry.list_all()
        tasks = self.task_queue.list_tasks(limit=50)
        return {
            "status": "operational",
            "runtime_version": "5.0.0-unified",
            "active_agents_count": len(agents),
            "agents": agents,
            "recent_tasks_count": len(tasks),
            "recent_tasks": tasks[:10],
        }


# Singleton accessor
agent_runtime = AgentRuntime.get_instance()
agent_registry = agent_runtime.registry
agent_task_queue = agent_runtime.task_queue
