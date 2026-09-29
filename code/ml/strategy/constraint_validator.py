# -*- coding: utf-8 -*-
"""
Main Constraint Validator Orchestrator Module for G.4.5.4 Strategy Constraint Validator.
Provides read-only, deterministic evaluation of G.4.5.3 SimulationResult objects against physical & regulatory rules.
"""

import copy
from typing import Optional, List, Tuple
from ml.strategy.race_config import RaceConfig
from ml.strategy.scenario_constraints import ScenarioConstraints
from ml.strategy.simulator import SimulationResult
from ml.strategy.validation_result import ValidationResult, Violation
from ml.strategy.constraint_checks import (
    check_fuel_constraints,
    check_tire_constraints,
    check_stint_constraints,
    check_pit_stop_constraints,
    check_compound_constraints,
    check_race_distance_constraints,
    check_lap_record_constraints,
    check_simulation_consistency,
)


class ConstraintValidator:
    """
    Engine for executing comprehensive, deterministic, read-only strategy constraint validations.
    """

    def __init__(self,
                 config: Optional[RaceConfig] = None,
                 constraints: Optional[ScenarioConstraints] = None):
        self.config = config or RaceConfig()
        self.constraints = constraints or ScenarioConstraints()

    def validate(self, simulation_result: SimulationResult, scenario_id: Optional[str] = None) -> ValidationResult:
        """
        Executes a complete pass of constraint checks against a G.4.5.3 SimulationResult.

        Args:
            simulation_result: G.4.5.3 SimulationResult instance.
            scenario_id: Optional canonical scenario ID string override.

        Returns:
            ValidationResult containing valid status, violation list, and warnings.
        """
        if simulation_result is None:
            raise ValueError("simulation_result cannot be None")

        if not hasattr(simulation_result, "lap_records"):
            raise ValueError("Invalid simulation_result object: missing required 'lap_records' attribute")

        scen_id = scenario_id or getattr(simulation_result, "scenario_id", getattr(simulation_result, "race_id", "UNKNOWN"))

        violations: List[Violation] = []
        warnings: List[str] = []

        # Execute 8 modular checker passes
        checker_functions = [
            check_fuel_constraints,
            check_tire_constraints,
            check_stint_constraints,
            check_pit_stop_constraints,
            check_compound_constraints,
            check_race_distance_constraints,
            check_lap_record_constraints,
            check_simulation_consistency,
        ]

        checked_count = 0
        for checker in checker_functions:
            try:
                v_list, w_list = checker(simulation_result, self.config, self.constraints)
                violations.extend(v_list)
                warnings.extend(w_list)
                checked_count += 1
            except Exception as e:
                # Failure handling: convert unhandled checker exception into structured Violation
                violations.append(Violation(
                    constraint_id="CHECKER_EXECUTION_ERROR",
                    category="CONSISTENCY",
                    severity="CRITICAL",
                    message=f"Constraint checker {checker.__name__} failed with error: {str(e)}",
                    actual_value=type(e).__name__,
                    expected_value="Clean checker execution",
                ))

        # Check simulation feasibility flag from G.4.5.3
        if not getattr(simulation_result, "is_feasible", True) and not violations:
            violations.append(Violation(
                constraint_id="SIMULATION_INFEASIBLE",
                category="CONSISTENCY",
                severity="CRITICAL",
                message="G.4.5.3 simulator flagged strategy as infeasible.",
                actual_value=False,
                expected_value=True,
            ))

        # Include warnings emitted during G.4.5.3 simulation run
        sim_warnings = getattr(simulation_result, "warnings", [])
        for sw in sim_warnings:
            if sw not in warnings:
                warnings.append(sw)

        # Overall validity determination
        is_valid = (len(violations) == 0)

        # Severity determination
        if not is_valid:
            overall_severity = "CRITICAL_VIOLATION"
        elif len(warnings) > 0:
            overall_severity = "WARNING"
        else:
            overall_severity = "NONE"

        # Construct and return immutable ValidationResult
        return ValidationResult(
            scenario_id=scen_id,
            race_id=self.config.race_id,
            valid=is_valid,
            severity=overall_severity,
            violations=tuple(violations),
            warnings=tuple(warnings),
            checked_constraints_count=checked_count,
            validator_version="1.0.0",
        )
