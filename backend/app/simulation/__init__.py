"""DOIP Hybrid Physics Simulation & Learned Decision Engine Package.

Provides:
- PhysicsEngine: Deterministic synthetic physics (kinematics, energy, environment, comms, logistics)
- RuleEngine: Deterministic rule verification, physical bounds enforcement, and rule-based state transitions
- FeatureExtractor: Numeric vectorization and textual state prompt generation for Laya
- StateTransitionValidator: Enforces invariant gates preventing illegal neural transitions
- ConsensusOutcomeEngine: Resolves multi-modal decisions between Physics, Rules, and Laya
- HybridSimulationRunner: Coordinated simulator running DETERMINISTIC_SIM and HYBRID_AI_SIM
"""

from .physics_engine import (
    KinematicState,
    EnergyState,
    EnvironmentState,
    CommsState,
    LogisticsState,
    PhysicsEngineState,
    PhysicsEngine,
)
from .rule_engine import RuleEngine, RuleEvaluationResult, TransitionRule
from .feature_extractor import FeatureExtractor, SimulationFeatures
from .state_transition import StateTransitionValidator, TransitionValidationResult
from .outcome_engine import ConsensusOutcomeEngine, DecisionOutcome
from .simulation_runner import HybridSimulationRunner, SimulationMode

__all__ = [
    "KinematicState",
    "EnergyState",
    "EnvironmentState",
    "CommsState",
    "LogisticsState",
    "PhysicsEngineState",
    "PhysicsEngine",
    "RuleEngine",
    "RuleEvaluationResult",
    "TransitionRule",
    "FeatureExtractor",
    "SimulationFeatures",
    "StateTransitionValidator",
    "TransitionValidationResult",
    "ConsensusOutcomeEngine",
    "DecisionOutcome",
    "HybridSimulationRunner",
    "SimulationMode",
]
