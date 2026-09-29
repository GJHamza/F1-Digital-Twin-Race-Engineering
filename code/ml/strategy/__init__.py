# -*- coding: utf-8 -*-
"""
G.4.5 & G.4.6 Strategy Intelligence Package (Foundation, Scenario Builder, Simulator, Validator, Optimizer, Adapter, Dashboard).
"""

from ml.strategy.config import (
    DEFAULT_PIT_STOP_LOSS_SEC,
    DEFAULT_TOTAL_LAPS,
    DEFAULT_STARTING_FUEL_KG,
    DEFAULT_MAX_TIRE_WEAR_PCT,
    DEFAULT_MIN_STINT_LAPS,
)
from ml.strategy.compounds import (
    TireCompound,
    CompoundModel,
    get_compound_model,
    validate_compound_transition,
)
from ml.strategy.race_config import RaceConfig
from ml.strategy.stint import Stint, validate_stint_sequence
from ml.strategy.pit_stop import PitStop
from ml.strategy.fuel_model import FuelModel, FuelState
from ml.strategy.strategy_state import StrategyState, VehicleStatus
from ml.strategy.simulator import StrategySimulator, SimulationResult
from ml.strategy.validation import (
    StrategyValidationError,
    validate_race_config,
    validate_stint,
    validate_pit_stop,
    validate_fuel_state,
    validate_strategy_state,
    validate_simulation_inputs,
)

# G.4.5.2 Scenario Builder Exports
from ml.strategy.scenario_id import generate_canonical_key, generate_deterministic_scenario_id
from ml.strategy.scenario import Scenario
from ml.strategy.scenario_deduplication import ScenarioDeduplicator
from ml.strategy.scenario_constraints import (
    ScenarioConstraints,
    DEFAULT_WEATHER_COMPOUND_MAP,
    get_allowed_compounds_for_weather,
    validate_scenario_hard_constraints,
)
from ml.strategy.scenario_generator import (
    ScenarioGenerator,
    ScenarioGenerationLimitError,
    GenerationResult,
    determine_bounded_grid_step,
)
from ml.strategy.scenario_serializer import ScenarioSerializer

# G.4.5.4 Constraint Validator Exports
from ml.strategy.validation_result import Violation, ValidationResult
from ml.strategy.constraint_validator import ConstraintValidator

# G.4.5.5 Strategy Optimizer Exports
from ml.strategy.ranking_config import OptimizationConfig
from ml.strategy.ranking_candidate import (
    OptimizationCandidate,
    RankedStrategy,
    DEFAULT_RANKING_EXPLANATION,
)
from ml.strategy.ranking_result import RankingResult
from ml.strategy.strategy_optimizer import StrategyOptimizer, get_ranking_key

# G.4.6.1 Dashboard Adapter Exports
from ml.strategy.dashboard_adapter import StrategyDashboardAdapter

# G.4.6.2, G.4.6.3, G.4.6.4, G.4.6.5 & G.4.6.6 Dashboard Presentation Exports
from ml.strategy.strategy_dashboard import (
    prepare_leaderboard_view_data,
    render_strategy_leaderboard,
    prepare_comparison_view_data,
    render_strategy_comparison,
    prepare_stint_timeline_data,
    render_stint_timeline,
    prepare_fuel_tire_analytics_view_data,
    render_fuel_tire_analytics,
    prepare_strategy_details_view_data,
    render_strategy_details,
    render_strategy_dashboard_tab,
)

__all__ = [
    # G.4.5.1 Data Foundation
    "DEFAULT_PIT_STOP_LOSS_SEC",
    "DEFAULT_TOTAL_LAPS",
    "DEFAULT_STARTING_FUEL_KG",
    "DEFAULT_MAX_TIRE_WEAR_PCT",
    "DEFAULT_MIN_STINT_LAPS",
    "TireCompound",
    "CompoundModel",
    "get_compound_model",
    "validate_compound_transition",
    "RaceConfig",
    "Stint",
    "validate_stint_sequence",
    "PitStop",
    "FuelModel",
    "FuelState",
    "StrategyState",
    "VehicleStatus",
    "StrategySimulator",
    "SimulationResult",
    "StrategyValidationError",
    "validate_race_config",
    "validate_stint",
    "validate_pit_stop",
    "validate_fuel_state",
    "validate_strategy_state",
    "validate_simulation_inputs",
    # G.4.5.2 Scenario Builder
    "generate_canonical_key",
    "generate_deterministic_scenario_id",
    "Scenario",
    "ScenarioDeduplicator",
    "ScenarioConstraints",
    "DEFAULT_WEATHER_COMPOUND_MAP",
    "get_allowed_compounds_for_weather",
    "validate_scenario_hard_constraints",
    "ScenarioGenerator",
    "ScenarioGenerationLimitError",
    "GenerationResult",
    "determine_bounded_grid_step",
    "ScenarioSerializer",
    # G.4.5.4 Constraint Validator
    "Violation",
    "ValidationResult",
    "ConstraintValidator",
    # G.4.5.5 Strategy Optimizer
    "OptimizationConfig",
    "OptimizationCandidate",
    "RankedStrategy",
    "DEFAULT_RANKING_EXPLANATION",
    "RankingResult",
    "StrategyOptimizer",
    "get_ranking_key",
    # G.4.6.1 Dashboard Adapter
    "StrategyDashboardAdapter",
    # G.4.6.2, G.4.6.3, G.4.6.4, G.4.6.5 & G.4.6.6 Dashboard Presentation
    "prepare_leaderboard_view_data",
    "render_strategy_leaderboard",
    "prepare_comparison_view_data",
    "render_strategy_comparison",
    "prepare_stint_timeline_data",
    "render_stint_timeline",
    "prepare_fuel_tire_analytics_view_data",
    "render_fuel_tire_analytics",
    "prepare_strategy_details_view_data",
    "render_strategy_details",
    "render_strategy_dashboard_tab",
]
