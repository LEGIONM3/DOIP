"""Platform Unification Engine (Phase 7A).

Provides central architectural unification across all DOIP subsystems:
- PlatformRegistry: Unified service catalog and dependency registry.
- PlatformService: Standard base class and decorator for all subsystem services.
- PlatformConfiguration: Centralized runtime configuration and feature governance.
- PlatformLifecycleManager: Controlled startup, shutdown, health verification, and orchestrator.
Eliminates architectural fragmentation and orphan services.
"""

from __future__ import annotations

import enum
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Type

from app.time_utils import utc_iso, utc_now

logger = logging.getLogger("doip.platform_unification")


class ServiceStatus(str, enum.Enum):
    UNREGISTERED = "UNREGISTERED"
    INITIALIZING = "INITIALIZING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class PlatformService:
    """Standard base class for all DOIP platform services."""

    def __init__(
        self,
        name: str,
        version: str = "7.0.0",
        subsystem: str = "core",
        dependencies: Optional[List[str]] = None,
        description: str = "",
    ):
        self.name = name
        self.version = version
        self.subsystem = subsystem
        self.dependencies = dependencies or []
        self.description = description
        self.status: ServiceStatus = ServiceStatus.INITIALIZING
        self.metadata: Dict[str, Any] = {}
        self.last_health_check: Optional[str] = None
        self.health_details: Dict[str, Any] = {}

    def start(self) -> None:
        """Start or initialize the service."""
        self.status = ServiceStatus.HEALTHY
        self.last_health_check = utc_iso()

    def stop(self) -> None:
        """Gracefully stop the service."""
        self.status = ServiceStatus.STOPPED

    def health_check(self) -> Dict[str, Any]:
        """Perform health assessment."""
        self.last_health_check = utc_iso()
        return {
            "status": self.status.value,
            "subsystem": self.subsystem,
            "version": self.version,
            "healthy": self.status in (ServiceStatus.HEALTHY, ServiceStatus.INITIALIZING),
            "checked_at": self.last_health_check,
            "details": self.health_details,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "subsystem": self.subsystem,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "description": self.description,
            "last_health_check": self.last_health_check,
            "metadata": self.metadata,
        }


class PlatformRegistry:
    """Central registry and service locator for all DOIP subsystems."""

    _instance: Optional[PlatformRegistry] = None

    def __init__(self):
        self._services: Dict[str, PlatformService] = {}
        self._initialized_at = utc_iso()

    @classmethod
    def get_instance(cls) -> PlatformRegistry:
        if cls._instance is None:
            cls._instance = PlatformRegistry()
        return cls._instance

    def register(self, service: PlatformService) -> PlatformService:
        """Register a platform service."""
        if service.name in self._services:
            logger.info("Service %s already registered, updating instance", service.name)
        self._services[service.name] = service
        logger.info("Registered platform service: %s (%s)", service.name, service.subsystem)
        return service

    def unregister(self, name: str) -> Optional[PlatformService]:
        """Unregister a service by name."""
        return self._services.pop(name, None)

    def get(self, name: str) -> Optional[PlatformService]:
        """Retrieve a registered service."""
        return self._services.get(name)

    def list_services(self, subsystem: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered services, optionally filtered by subsystem."""
        if not self._services:
            PlatformLifecycleManager.get_instance().bootstrap_platform()
        services = list(self._services.values())
        if subsystem:
            services = [s for s in services if s.subsystem == subsystem]
        return [s.to_dict() for s in services]

    def get_subsystems(self) -> List[str]:
        """Return list of distinct subsystem categories."""
        if not self._services:
            PlatformLifecycleManager.get_instance().bootstrap_platform()
        return sorted(list({s.subsystem for s in self._services.values()}))

    def check_all_health(self) -> Dict[str, Any]:
        """Check health of all registered services."""
        if not self._services:
            PlatformLifecycleManager.get_instance().bootstrap_platform()
        results: Dict[str, Any] = {}
        healthy_count = 0
        total_count = len(self._services)

        for name, service in self._services.items():
            h = service.health_check()
            results[name] = h
            if h.get("healthy"):
                healthy_count += 1

        overall_status = "HEALTHY" if healthy_count == total_count else "DEGRADED"
        if healthy_count == 0 and total_count > 0:
            overall_status = "FAILED"

        return {
            "overall_status": overall_status,
            "total_services": total_count,
            "healthy_services": healthy_count,
            "services": results,
            "evaluated_at": utc_iso(),
        }


class PlatformConfiguration:
    """Unified configuration manager for global DOIP operational parameters."""

    _instance: Optional[PlatformConfiguration] = None

    def __init__(self):
        self._config: Dict[str, Any] = {
            "platform_name": "DOIP - Defense Operations Intelligence Platform",
            "version": "7.0.0",
            "environment": "production",
            "air_gapped_mode": True,
            "golden_run_verification_enforced": True,
            "human_in_the_loop_mandatory": True,
            "live_state_immutability_enforced": True,
            "circuit_breakers_enabled": True,
            "caching_enabled": True,
            "default_cache_ttl": 300,
            "telemetry_batch_size": 250,
            "multi_theater_enabled": True,
            "governance_mode": "STRICT",
            "self_healing_enabled": True,
            "research_sandbox_isolated": True,
        }

    @classmethod
    def get_instance(cls) -> PlatformConfiguration:
        if cls._instance is None:
            cls._instance = PlatformConfiguration()
        return cls._instance

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._config)


class PlatformLifecycleManager:
    """Orchestrates platform lifecycle, initialization sequence, and graceful shutdowns."""

    _instance: Optional[PlatformLifecycleManager] = None

    def __init__(self):
        self.registry = PlatformRegistry.get_instance()
        self.config = PlatformConfiguration.get_instance()
        self.is_booted = False
        self.boot_time: Optional[str] = None

    @classmethod
    def get_instance(cls) -> PlatformLifecycleManager:
        if cls._instance is None:
            cls._instance = PlatformLifecycleManager()
        return cls._instance

    def bootstrap_platform(self) -> Dict[str, Any]:
        """Bootstrap and register all canonical DOIP services."""
        if self.is_booted:
            return {"status": "ALREADY_BOOTSTRAPPED", "boot_time": self.boot_time}

        # 1. Deterministic Simulation Core
        self.registry.register(
            PlatformService(
                name="deterministic_sim_engine",
                version="7.0.0",
                subsystem="simulation",
                description="Fixed-step discrete-event deterministic simulator with golden run verification",
            )
        )

        # 2. Tactical Routing & Pathfinding
        self.registry.register(
            PlatformService(
                name="tactical_routing_engine",
                version="7.0.0",
                subsystem="routing",
                dependencies=["deterministic_sim_engine"],
                description="Grid A* multi-factor tactical route optimization with threat cost evaluation",
            )
        )

        # 3. Mission Planning & Lifecycle
        self.registry.register(
            PlatformService(
                name="mission_planning_engine",
                version="7.0.0",
                subsystem="planning",
                dependencies=["tactical_routing_engine"],
                description="Task DAG mission planner with strict human-in-the-loop authorization gates",
            )
        )

        # 4. War Room Real-Time Collaboration
        self.registry.register(
            PlatformService(
                name="warroom_collaboration_hub",
                version="7.0.0",
                subsystem="collaboration",
                description="Multi-operator WebSocket collaboration, presence tracking, and incident triage",
            )
        )

        # 5. Unified Knowledge Platform
        self.registry.register(
            PlatformService(
                name="unified_knowledge_platform",
                version="7.0.0",
                subsystem="knowledge",
                description="Harmonized cognitive layer uniting Knowledge Graph, RAG, Memory, and Risk",
            )
        )

        # 6. Digital Twin Forecaster
        self.registry.register(
            PlatformService(
                name="digital_twin_forecaster",
                version="7.0.0",
                subsystem="forecasting",
                dependencies=["deterministic_sim_engine"],
                description="Predictive forward lookahead for fuel, RF silence, and threat intersections",
            )
        )

        # 7. Multi-Tier Command Federation
        self.registry.register(
            PlatformService(
                name="command_federation_engine",
                version="7.0.0",
                subsystem="federation",
                description="Decentralized hierarchical federation with staged directive cascading",
            )
        )

        # 8. Agent Swarm & Runtime
        self.registry.register(
            PlatformService(
                name="agent_runtime_platform",
                version="7.0.0",
                subsystem="autonomy",
                dependencies=["unified_knowledge_platform"],
                description="Centralized agent lifecycle directory, prioritized task queue, and swarm coordinator",
            )
        )

        # 9. Operational Workflow Engine
        self.registry.register(
            PlatformService(
                name="operational_workflow_engine",
                version="7.0.0",
                subsystem="workflows",
                dependencies=["mission_planning_engine"],
                description="Deterministic FSM governing mission dispatch and approval transitions",
            )
        )

        # 10. Observability & Resilience
        self.registry.register(
            PlatformService(
                name="observability_and_resilience",
                version="7.0.0",
                subsystem="operations",
                description="Circuit breakers, telemetry metrics, OpenTelemetry traces, and monotonic LRU cache",
            )
        )

        # 11. Autonomous Governance Engine (Phase 7)
        self.registry.register(
            PlatformService(
                name="autonomous_governance_engine",
                version="7.0.0",
                subsystem="governance",
                description="Pre-execution compliance, human-in-the-loop gatekeeper, and determinism verifier",
            )
        )

        # 12. Self-Healing Operational Layer (Phase 7)
        self.registry.register(
            PlatformService(
                name="self_healing_operational_layer",
                version="7.0.0",
                subsystem="reliability",
                dependencies=["observability_and_resilience"],
                description="Autonomous circuit reset, cache rebuild, index repair, and workflow recovery",
            )
        )

        # 13. Data Governance Framework (Phase 7)
        self.registry.register(
            PlatformService(
                name="data_governance_framework",
                version="7.0.0",
                subsystem="data",
                description="Lineage tracking, schema registry, audit compliance, and retention policy manager",
            )
        )

        # 14. Quality Assurance Platform (Phase 7)
        self.registry.register(
            PlatformService(
                name="quality_assurance_platform",
                version="7.0.0",
                subsystem="quality",
                description="Continuous metric scoring, test coverage tracking, and DOIP Quality Index",
            )
        )

        # 15. Research Sandbox (Phase 7)
        self.registry.register(
            PlatformService(
                name="future_research_sandbox",
                version="7.0.0",
                subsystem="research",
                description="Isolated ephemeral sandbox for prototype AI, novel planning, and experimental sims",
            )
        )

        # Start all services
        for s in self.registry._services.values():
            s.start()

        self.is_booted = True
        self.boot_time = utc_iso()
        logger.info("Platform bootstrap complete. %d services active.", len(self.registry._services))

        return {
            "status": "BOOTSTRAP_COMPLETE",
            "services_registered": len(self.registry._services),
            "subsystems": self.registry.get_subsystems(),
            "boot_time": self.boot_time,
        }

    def shutdown_platform(self) -> Dict[str, Any]:
        """Gracefully stop all platform services."""
        for s in self.registry._services.values():
            s.stop()
        self.is_booted = False
        return {
            "status": "SHUTDOWN_COMPLETE",
            "timestamp": utc_iso(),
        }


# Singletons
platform_registry = PlatformRegistry.get_instance()
platform_config = PlatformConfiguration.get_instance()
platform_lifecycle = PlatformLifecycleManager.get_instance()
platform_lifecycle.bootstrap_platform()
