# -*- coding: utf-8 -*-
"""
Validation Result and Violation Data Structures for G.4.5.4 Constraint Validator.
Implements immutable/frozen data containers with deterministic violation ordering.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class Violation:
    """
    Immutable representation of a hard constraint violation during race strategy validation.

    Attributes:
        constraint_id: Unique string identifier for the violated constraint rule (e.g. 'FUEL_DEPLETED').
        category: Functional rule category ('FUEL', 'TIRE', 'STINT', 'PIT_STOP', 'COMPOUND', 'DISTANCE', 'LAP', 'CONSISTENCY').
        severity: Rule severity level ('CRITICAL', 'HIGH', 'MEDIUM').
        message: Human-readable detailed explanation of the violation.
        actual_value: Empirical value recorded in simulation result.
        expected_value: Configured boundary or rule condition.
        lap_number: Optional 1-based lap number where violation occurred.
        stint_id: Optional stint identifier associated with violation.
    """
    constraint_id: str
    category: str
    severity: str
    message: str
    actual_value: Any
    expected_value: Any
    lap_number: Optional[int] = None
    stint_id: Optional[str] = None

    def __post_init__(self):
        """Validate Violation attributes."""
        if not self.constraint_id:
            raise ValueError("constraint_id cannot be empty")
        if not self.category:
            raise ValueError("category cannot be empty")
        if self.severity not in ["CRITICAL", "HIGH", "MEDIUM"]:
            raise ValueError(f"Invalid severity '{self.severity}'. Must be CRITICAL, HIGH, or MEDIUM.")

    def to_dict(self) -> Dict[str, Any]:
        """Convert Violation to dictionary representation."""
        return {
            "constraint_id": self.constraint_id,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "actual_value": str(self.actual_value),
            "expected_value": str(self.expected_value),
            "lap_number": self.lap_number,
            "stint_id": self.stint_id,
        }


@dataclass(frozen=True)
class ValidationResult:
    """
    Complete immutable container for strategy constraint validation results.

    Attributes:
        scenario_id: Canonical identifier of the evaluated strategy scenario.
        race_id: Race configuration identifier.
        valid: Boolean flag indicating if strategy satisfies all hard constraints.
        severity: Overall validation severity ('NONE', 'WARNING', 'CRITICAL_VIOLATION').
        violations: Tuple of sorted Violation objects.
        warnings: Tuple of non-invalidating alert strings.
        checked_constraints_count: Total number of individual constraint rules evaluated.
        validator_version: Version tag of the validator engine.
    """
    scenario_id: str
    race_id: str
    valid: bool
    severity: str
    violations: Tuple[Violation, ...] = field(default_factory=tuple)
    warnings: Tuple[str, ...] = field(default_factory=tuple)
    checked_constraints_count: int = 0
    validator_version: str = "1.0.0"

    def __post_init__(self):
        """Ensure violations and warnings are stored as tuples and deterministically ordered."""
        # Convert lists to tuples if necessary to preserve frozen immutability
        if isinstance(self.violations, list):
            object.__setattr__(self, 'violations', tuple(self.violations))
        if isinstance(self.warnings, list):
            object.__setattr__(self, 'warnings', tuple(self.warnings))

        # Deterministic sorting of violations: (lap_number or -1, category, constraint_id)
        sorted_violations = tuple(sorted(
            self.violations,
            key=lambda v: (v.lap_number if v.lap_number is not None else -1, v.category, v.constraint_id)
        ))
        object.__setattr__(self, 'violations', sorted_violations)

        # Enforce consistency between valid flag and violations
        has_critical = len(self.violations) > 0
        if has_critical and self.valid:
            object.__setattr__(self, 'valid', False)

    @property
    def violation_count(self) -> int:
        """Total number of hard violations."""
        return len(self.violations)

    @property
    def warning_count(self) -> int:
        """Total number of soft warnings."""
        return len(self.warnings)

    def to_dict(self) -> Dict[str, Any]:
        """Convert ValidationResult to dictionary representation."""
        return {
            "scenario_id": self.scenario_id,
            "race_id": self.race_id,
            "valid": self.valid,
            "severity": self.severity,
            "violation_count": self.violation_count,
            "warning_count": self.warning_count,
            "checked_constraints_count": self.checked_constraints_count,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": list(self.warnings),
            "validator_version": self.validator_version,
        }
