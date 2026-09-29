# -*- coding: utf-8 -*-
"""
Deterministic Scenario Deduplication for G.4.5.2 Strategy Scenario Builder.
"""

from typing import List, Set, Tuple, Dict, Any
from ml.strategy.scenario import Scenario


class ScenarioDeduplicator:
    """
    Tracks seen canonical keys and deduplicates candidate scenarios deterministically.
    """

    def __init__(self):
        self._seen_keys: Set[str] = set()
        self.generated_before_deduplication: int = 0
        self.duplicates_removed: int = 0

    def reset(self):
        """Resets seen key cache and counter state."""
        self._seen_keys.clear()
        self.generated_before_deduplication = 0
        self.duplicates_removed = 0

    def is_duplicate(self, canonical_key: str) -> bool:
        """Check if a canonical key has already been seen."""
        return canonical_key in self._seen_keys

    def process_scenario(self, scenario: Scenario) -> bool:
        """
        Registers a scenario if unique.

        Returns:
            True if scenario is unique (added), False if duplicate (rejected).
        """
        self.generated_before_deduplication += 1
        key = scenario.canonical_key
        if key in self._seen_keys:
            self.duplicates_removed += 1
            return False

        self._seen_keys.add(key)
        return True

    def deduplicate(self, scenarios: List[Scenario]) -> List[Scenario]:
        """
        Deduplicates a list of scenarios deterministically while preserving order.

        Args:
            scenarios: Input scenario list.

        Returns:
            Deduplicated list of unique scenarios.
        """
        unique_scenarios: List[Scenario] = []
        for s in scenarios:
            if self.process_scenario(s):
                unique_scenarios.append(s)

        return unique_scenarios

    def get_metrics(self) -> Dict[str, int]:
        """Return deduplication audit metrics dictionary."""
        return {
            "generated_before_deduplication": self.generated_before_deduplication,
            "duplicates_removed": self.duplicates_removed,
            "final_unique_scenarios": len(self._seen_keys),
        }
