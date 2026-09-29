# -*- coding: utf-8 -*-
"""
Immutable Ranking Result Container for G.4.5.5 Strategy Optimizer.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional
from ml.strategy.ranking_candidate import RankedStrategy


@dataclass(frozen=True)
class RankingResult:
    """
    Immutable container holding full auditable strategy optimization results.

    Attributes:
        ranked_strategies: Tuple of Top-K RankedStrategy instances ordered from rank 1..K.
        total_candidates: Total number of evaluated strategy candidates (valid + invalid).
        valid_candidates: Number of candidates satisfying hard validation constraints.
        excluded_candidates: Number of invalid candidates filtered out of ranking.
        top_k: Configured Top-K parameter.
        ranking_version: Optimizer engine version string.
        leader_scenario_id: Scenario ID of the rank 1 winner (or None if zero valid strategies).
        leader_race_time_sec: Total race time of the rank 1 winner (or None if zero valid strategies).
    """
    ranked_strategies: Tuple[RankedStrategy, ...]
    total_candidates: int
    valid_candidates: int
    excluded_candidates: int
    top_k: int
    ranking_version: str = "1.0.0"
    leader_scenario_id: Optional[str] = None
    leader_race_time_sec: Optional[float] = None

    def __post_init__(self):
        """Ensure lists are stored as immutable tuples and metrics are consistent."""
        if isinstance(self.ranked_strategies, list):
            object.__setattr__(self, 'ranked_strategies', tuple(self.ranked_strategies))

        if self.total_candidates < 0:
            raise ValueError(f"total_candidates cannot be negative, got {self.total_candidates}")
        if self.valid_candidates < 0:
            raise ValueError(f"valid_candidates cannot be negative, got {self.valid_candidates}")
        if self.excluded_candidates < 0:
            raise ValueError(f"excluded_candidates cannot be negative, got {self.excluded_candidates}")
        if self.total_candidates != self.valid_candidates + self.excluded_candidates:
            raise ValueError(
                f"Candidate count mismatch: total ({self.total_candidates}) != "
                f"valid ({self.valid_candidates}) + excluded ({self.excluded_candidates})"
            )

        if len(self.ranked_strategies) > 0:
            leader = self.ranked_strategies[0]
            if self.leader_scenario_id is None:
                object.__setattr__(self, 'leader_scenario_id', leader.scenario_id)
            if self.leader_race_time_sec is None:
                object.__setattr__(self, 'leader_race_time_sec', leader.total_race_time_sec)

    @property
    def is_empty(self) -> bool:
        """Returns True if no valid strategies were ranked."""
        return len(self.ranked_strategies) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert ranking result to dictionary representation."""
        return {
            "total_candidates": self.total_candidates,
            "valid_candidates": self.valid_candidates,
            "excluded_candidates": self.excluded_candidates,
            "top_k": self.top_k,
            "ranked_count": len(self.ranked_strategies),
            "leader_scenario_id": self.leader_scenario_id,
            "leader_race_time_sec": round(self.leader_race_time_sec, 3) if self.leader_race_time_sec is not None else None,
            "ranking_version": self.ranking_version,
            "ranked_strategies": [s.to_dict() for s in self.ranked_strategies],
        }
