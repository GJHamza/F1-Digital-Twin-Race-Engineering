# -*- coding: utf-8 -*-
"""
Deterministic Strategy Optimizer and Ranking Engine for G.4.5.5.
Filters invalid candidates, ranks valid candidates using a 6-tier lexicographic key,
calculates time delta to leader, and produces an auditable RankingResult.
"""

import heapq
import math
from typing import List, Sequence, Tuple, Union, Optional, Set
from ml.strategy.ranking_config import OptimizationConfig
from ml.strategy.ranking_candidate import OptimizationCandidate, RankedStrategy
from ml.strategy.ranking_result import RankingResult
from ml.strategy.simulator import SimulationResult
from ml.strategy.validation_result import ValidationResult
from ml.strategy.scenario import Scenario

# Threshold for using heapq.nsmallest vs full in-memory list sort
HEAPQ_THRESHOLD = 100_000


def get_ranking_key(candidate: OptimizationCandidate) -> Tuple[float, int, float, float, str, str]:
    """
    Single authoritative 6-tier deterministic lexicographic sort key definition.

    1. total_race_time_sec ASC (Primary)
    2. pit_stop_count ASC (Secondary)
    3. final_fuel_kg DESC (Tertiary, implemented via -final_fuel_kg ASC)
    4. avg_final_tire_wear_pct ASC (Quaternary)
    5. canonical_key ASC (Alphabetical tie-breaker)
    6. scenario_id ASC (Final deterministic fallback)

    Args:
        candidate: OptimizationCandidate instance.

    Returns:
        Comparable tuple for Python sort / heapq.
    """
    return (
        candidate.total_race_time_sec,
        candidate.pit_stop_count,
        -candidate.final_fuel_kg,
        candidate.avg_final_tire_wear_pct,
        candidate.canonical_key,
        candidate.scenario_id,
    )


class StrategyOptimizer:
    """
    Deterministic optimization engine for filtering, ranking, and selecting Top-K race strategies.
    """

    def __init__(self, config: Optional[OptimizationConfig] = None):
        """
        Initialize optimizer with optional configuration.
        """
        self.config = config if config is not None else OptimizationConfig()

    def optimize(
        self,
        inputs: Sequence[Union[OptimizationCandidate, Tuple[SimulationResult, ValidationResult], Tuple[SimulationResult, ValidationResult, Scenario]]],
        override_top_k: Optional[int] = None,
    ) -> RankingResult:
        """
        Filters invalid candidates, ranks valid strategies, and returns Top-K results.

        Args:
            inputs: Sequence of OptimizationCandidate objects or (sim_result, val_result) tuples.
            override_top_k: Optional top_k parameter overriding configured value for this run.

        Returns:
            Immutable RankingResult.
        """
        # Determine effective top_k
        top_k = self.config.top_k if override_top_k is None else override_top_k
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"top_k must be an integer > 0, got {top_k}")

        if inputs is None:
            raise ValueError("inputs sequence cannot be None")

        # Normalize and validate all input elements into OptimizationCandidate objects
        candidates: List[OptimizationCandidate] = []
        for idx, item in enumerate(inputs):
            if item is None:
                raise ValueError(f"Input element at index {idx} is None")

            if isinstance(item, OptimizationCandidate):
                candidates.append(item)
            elif isinstance(item, tuple):
                if len(item) == 2:
                    sim_res, val_res = item
                    scen = None
                elif len(item) == 3:
                    sim_res, val_res, scen = item
                else:
                    raise ValueError(f"Tuple input at index {idx} must have 2 or 3 elements, got {len(item)}")

                candidate = OptimizationCandidate.from_simulation_and_validation(
                    sim_result=sim_res,
                    val_result=val_res,
                    scenario=scen,
                )
                candidates.append(candidate)
            else:
                raise ValueError(f"Unsupported input type at index {idx}: {type(item).__name__}")

        total_candidates = len(candidates)

        # Check for duplicate scenario IDs across all input candidates
        seen_ids: Set[str] = set()
        for cand in candidates:
            if cand.scenario_id in seen_ids:
                raise ValueError(f"Duplicate scenario_id detected: '{cand.scenario_id}'")
            seen_ids.add(cand.scenario_id)

        # Hard filtering: keep candidates where valid is True
        valid_pool: List[OptimizationCandidate] = [c for c in candidates if c.valid is True]
        valid_candidates_count = len(valid_pool)
        excluded_candidates_count = total_candidates - valid_candidates_count

        # If zero valid candidates, return empty RankingResult
        if valid_candidates_count == 0:
            return RankingResult(
                ranked_strategies=(),
                total_candidates=total_candidates,
                valid_candidates=0,
                excluded_candidates=excluded_candidates_count,
                top_k=top_k,
                ranking_version=self.config.ranking_version,
                leader_scenario_id=None,
                leader_race_time_sec=None,
            )

        # Rank valid candidates: dual path depending on dataset size
        if valid_candidates_count > HEAPQ_THRESHOLD:
            # Use heapq.nsmallest for large candidate sets
            top_selected = heapq.nsmallest(top_k, valid_pool, key=get_ranking_key)
        else:
            # Full deterministic sort for standard candidate sets
            sorted_all = sorted(valid_pool, key=get_ranking_key)
            top_selected = sorted_all[:top_k]

        # Leader metrics (from rank 1 candidate)
        leader = top_selected[0]
        leader_time = leader.total_race_time_sec
        leader_id = leader.scenario_id

        # Build immutable RankedStrategy outputs
        ranked_list: List[RankedStrategy] = []
        for rank_idx, cand in enumerate(top_selected, start=1):
            ranked_strat = RankedStrategy.from_candidate(
                candidate=cand,
                rank=rank_idx,
                leader_race_time_sec=leader_time,
            )
            ranked_list.append(ranked_strat)

        return RankingResult(
            ranked_strategies=tuple(ranked_list),
            total_candidates=total_candidates,
            valid_candidates=valid_candidates_count,
            excluded_candidates=excluded_candidates_count,
            top_k=top_k,
            ranking_version=self.config.ranking_version,
            leader_scenario_id=leader_id,
            leader_race_time_sec=leader_time,
        )
