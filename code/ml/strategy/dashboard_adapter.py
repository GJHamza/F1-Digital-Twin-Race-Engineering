# -*- coding: utf-8 -*-
"""
Strategy Dashboard Adapter for G.4.6.1.
Transforms immutable G.4.5 domain objects (RankingResult, SimulationResult, ValidationResult)
into read-only, presentation-friendly Pandas DataFrames for dashboard visualization.
"""

from typing import Dict, List, Optional, Sequence, Union, Any
import pandas as pd

from ml.strategy.ranking_result import RankingResult
from ml.strategy.ranking_candidate import RankedStrategy
from ml.strategy.simulator import SimulationResult
from ml.strategy.validation_result import ValidationResult
from ml.strategy.scenario import Scenario

# Mandatory standard column schemas for adapter DataFrames
LEADERBOARD_COLUMNS = [
    "rank",
    "scenario_id",
    "canonical_key",
    "total_race_time_sec",
    "pit_stop_count",
    "final_fuel_kg",
    "avg_final_tire_wear_pct",
    "warning_count",
    "delta_to_leader_sec",
    "ranking_explanation",
]

COMPARISON_COLUMNS = [
    "rank",
    "scenario_id",
    "canonical_key",
    "total_race_time_sec",
    "delta_to_leader_sec",
    "pit_stop_count",
    "final_fuel_kg",
    "avg_final_tire_wear_pct",
    "warning_count",
]

STINT_COLUMNS_FULL = [
    "stint_number",
    "compound",
    "start_lap",
    "end_lap",
    "stint_laps",
    "starting_fuel",
    "ending_fuel",
    "fuel_consumed",
    "starting_wear",
    "ending_wear",
    "avg_wear",
]

PIT_STOP_COLUMNS = [
    "pit_stop_id",
    "pit_lap",
    "duration_sec",
    "compound_before",
    "compound_after",
    "stint_before",
    "stint_after",
]

LAP_TELEMETRY_COLUMNS = [
    "lap_number",
    "stint_number",
    "compound",
    "tire_age_laps",
    "fuel_kg",
    "fuel_consumed_kg",
    "tire_wear_fl",
    "tire_wear_fr",
    "tire_wear_rl",
    "tire_wear_rr",
    "avg_tire_wear",
    "lap_time_sec",
    "pit_loss_sec",
    "cum_time_sec",
]


class StrategyDashboardAdapter:
    """
    Read-only adapter transforming G.4.5 strategy optimization and simulation payloads into DataFrames.
    """

    def __init__(
        self,
        ranking_result: RankingResult,
        simulation_results: Optional[Union[Dict[str, SimulationResult], Sequence[SimulationResult]]] = None,
        validation_results: Optional[Union[Dict[str, ValidationResult], Sequence[ValidationResult]]] = None,
        scenarios: Optional[Union[Dict[str, Scenario], Sequence[Scenario]]] = None,
    ):
        """
        Initialize dashboard adapter with immutable G.4.5 outputs.

        Args:
            ranking_result: Authoritative G.4.5.5 RankingResult instance (mandatory).
            simulation_results: Optional dictionary or sequence of G.4.5.3 SimulationResult objects.
            validation_results: Optional dictionary or sequence of G.4.5.4 ValidationResult objects.
            scenarios: Optional dictionary or sequence of G.4.5.2 Scenario objects.
        """
        if ranking_result is None:
            raise ValueError("ranking_result cannot be None")

        self._ranking_result = ranking_result

        # Build fast O(1) scenario_id lookups without mutating input collections
        self._ranked_map: Dict[str, RankedStrategy] = {
            s.scenario_id: s for s in ranking_result.ranked_strategies
        }

        self._sim_results: Dict[str, SimulationResult] = {}
        if simulation_results is not None:
            if isinstance(simulation_results, dict):
                self._sim_results = dict(simulation_results)
            elif isinstance(simulation_results, (list, tuple)):
                for sim in simulation_results:
                    if sim is not None and hasattr(sim, "race_id"):
                        # If sim_result has scenario_id or we match by key
                        scen_id = getattr(sim, "scenario_id", getattr(sim, "race_id", None))
                        if scen_id:
                            self._sim_results[scen_id] = sim

        self._val_results: Dict[str, ValidationResult] = {}
        if validation_results is not None:
            if isinstance(validation_results, dict):
                self._val_results = dict(validation_results)
            elif isinstance(validation_results, (list, tuple)):
                for val in validation_results:
                    if val is not None and hasattr(val, "scenario_id"):
                        self._val_results[val.scenario_id] = val

        self._scenarios: Dict[str, Scenario] = {}
        if scenarios is not None:
            if isinstance(scenarios, dict):
                self._scenarios = dict(scenarios)
            elif isinstance(scenarios, (list, tuple)):
                for scen in scenarios:
                    if scen is not None and hasattr(scen, "scenario_id"):
                        self._scenarios[scen.scenario_id] = scen

    @property
    def ranking_result(self) -> RankingResult:
        """Access underlying immutable RankingResult."""
        return self._ranking_result

    def leaderboard_dataframe(self) -> pd.DataFrame:
        """
        Builds a DataFrame representation of the Top-K strategy leaderboard.

        Returns:
            pd.DataFrame with columns: LEADERBOARD_COLUMNS.
        """
        if self._ranking_result.is_empty:
            return pd.DataFrame(columns=LEADERBOARD_COLUMNS)

        records = [s.to_dict() for s in self._ranking_result.ranked_strategies]
        df = pd.DataFrame(records)
        return df[LEADERBOARD_COLUMNS]

    def comparison_dataframe(self, scenario_ids: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Builds a multi-strategy metrics comparison DataFrame for specified or all Top-K strategies.

        Args:
            scenario_ids: Optional list of scenario IDs to compare. If None/empty, uses all ranked strategies.

        Returns:
            pd.DataFrame with comparison metric columns.
        """
        if self._ranking_result.is_empty:
            return pd.DataFrame(columns=COMPARISON_COLUMNS)

        if scenario_ids:
            selected_strats = []
            for sid in scenario_ids:
                if sid not in self._ranked_map:
                    raise ValueError(f"Scenario ID '{sid}' not found in ranking result")
                selected_strats.append(self._ranked_map[sid])
        else:
            selected_strats = list(self._ranking_result.ranked_strategies)

        records = []
        for s in selected_strats:
            records.append({
                "rank": s.rank,
                "scenario_id": s.scenario_id,
                "canonical_key": s.canonical_key,
                "total_race_time_sec": round(s.total_race_time_sec, 3),
                "delta_to_leader_sec": round(s.delta_to_leader_sec, 3),
                "pit_stop_count": s.pit_stop_count,
                "final_fuel_kg": round(s.final_fuel_kg, 3),
                "avg_final_tire_wear_pct": round(s.avg_final_tire_wear_pct, 2),
                "warning_count": s.warning_count,
            })

        df = pd.DataFrame(records)
        return df[COMPARISON_COLUMNS]

    def selected_strategy_dataframe(self, scenario_id: str) -> pd.DataFrame:
        """
        Builds a single-row summary DataFrame for a user-selected strategy ID.

        Args:
            scenario_id: Strategy canonical scenario ID.

        Returns:
            1-row pd.DataFrame matching LEADERBOARD_COLUMNS.
        """
        if not scenario_id or scenario_id not in self._ranked_map:
            raise ValueError(f"Scenario ID '{scenario_id}' not found in ranking result")

        strat = self._ranked_map[scenario_id]
        df = pd.DataFrame([strat.to_dict()])
        return df[LEADERBOARD_COLUMNS]

    def stint_dataframe(self, scenario_id: str) -> pd.DataFrame:
        """
        Builds a per-stint timeline DataFrame for the specified strategy ID.

        Args:
            scenario_id: Strategy canonical scenario ID.

        Returns:
            pd.DataFrame containing stint laps, compound, fuel burn, and wear.
        """
        if not scenario_id or scenario_id not in self._ranked_map:
            raise ValueError(f"Scenario ID '{scenario_id}' not found in ranking result")

        # 1. Try SimulationResult stint_summary
        sim_res = self._sim_results.get(scenario_id)
        if sim_res is not None and hasattr(sim_res, "stint_summary") and sim_res.stint_summary:
            df = pd.DataFrame(sim_res.stint_summary)
            # Ensure standard column subset
            available_cols = [c for c in STINT_COLUMNS_FULL if c in df.columns]
            return df[available_cols]

        # 2. Try Scenario stints fallback
        scen = self._scenarios.get(scenario_id)
        if scen is not None and hasattr(scen, "stints") and scen.stints:
            records = [
                {
                    "stint_number": s.stint_number,
                    "compound": s.compound,
                    "start_lap": s.start_lap,
                    "end_lap": s.end_lap,
                    "stint_laps": s.stint_laps,
                }
                for s in scen.stints
            ]
            return pd.DataFrame(records)

        raise ValueError(f"Stint details unavailable for scenario ID '{scenario_id}'")

    def pit_dataframe(self, scenario_id: str) -> pd.DataFrame:
        """
        Builds a pit stop event DataFrame for the specified strategy ID.

        Args:
            scenario_id: Strategy canonical scenario ID.

        Returns:
            pd.DataFrame containing pit laps, durations, and compound transitions.
        """
        if not scenario_id or scenario_id not in self._ranked_map:
            raise ValueError(f"Scenario ID '{scenario_id}' not found in ranking result")

        # 1. Try SimulationResult pit_summary
        sim_res = self._sim_results.get(scenario_id)
        if sim_res is not None and hasattr(sim_res, "pit_summary") and sim_res.pit_summary:
            df = pd.DataFrame(sim_res.pit_summary)
            available_cols = [c for c in PIT_STOP_COLUMNS if c in df.columns]
            return df[available_cols] if available_cols else df

        # 2. Try Scenario pit_stops fallback
        scen = self._scenarios.get(scenario_id)
        if scen is not None and hasattr(scen, "pit_stops") and scen.pit_stops:
            records = [p.to_dict() for p in scen.pit_stops]
            df = pd.DataFrame(records)
            available_cols = [c for c in PIT_STOP_COLUMNS if c in df.columns]
            return df[available_cols] if available_cols else df

        return pd.DataFrame(columns=PIT_STOP_COLUMNS)

    def lap_dataframe(self, scenario_id: str) -> pd.DataFrame:
        """
        Builds a lap-by-lap telemetry DataFrame for the specified strategy ID.

        Args:
            scenario_id: Strategy canonical scenario ID.

        Returns:
            pd.DataFrame with lap telemetry fields.
        """
        if not scenario_id or scenario_id not in self._ranked_map:
            raise ValueError(f"Scenario ID '{scenario_id}' not found in ranking result")

        sim_res = self._sim_results.get(scenario_id)
        if sim_res is None or not hasattr(sim_res, "lap_records") or not sim_res.lap_records:
            raise ValueError(f"Lap telemetry unavailable for scenario ID '{scenario_id}'")

        df = pd.DataFrame(sim_res.lap_records)
        # Normalize attribute aliases from G.4.5.3 simulator if needed
        if "race_lap" in df.columns and "lap_number" not in df.columns:
            df["lap_number"] = df["race_lap"]
        if "tire_compound" in df.columns and "compound" not in df.columns:
            df["compound"] = df["tire_compound"]
        if "fuel_remaining_kg" in df.columns and "fuel_kg" not in df.columns:
            df["fuel_kg"] = df["fuel_remaining_kg"]
        if "avg_tire_wear_pct" in df.columns and "avg_tire_wear" not in df.columns:
            df["avg_tire_wear"] = df["avg_tire_wear_pct"]

        available_cols = [c for c in LAP_TELEMETRY_COLUMNS if c in df.columns]
        if not available_cols:
            return df
        return df[available_cols]

    def validation_dataframe(self, scenario_id: str) -> pd.DataFrame:
        """
        Builds an authoritative validation status & violation report DataFrame for specified strategy ID.

        Args:
            scenario_id: Strategy canonical scenario ID.

        Returns:
            pd.DataFrame showing validation state, severity, and any constraint violations.
        """
        if not scenario_id or scenario_id not in self._ranked_map:
            raise ValueError(f"Scenario ID '{scenario_id}' not found in ranking result")

        val_res = self._val_results.get(scenario_id)
        if val_res is not None:
            if val_res.violations:
                records = []
                for v in val_res.violations:
                    rec = v.to_dict()
                    rec["scenario_id"] = val_res.scenario_id
                    rec["valid"] = val_res.valid
                    rec["severity"] = val_res.severity
                    records.append(rec)
                return pd.DataFrame(records)
            else:
                return pd.DataFrame([{
                    "scenario_id": val_res.scenario_id,
                    "valid": val_res.valid,
                    "severity": val_res.severity,
                    "violation_count": 0,
                    "warning_count": val_res.warning_count,
                    "warnings": ", ".join(val_res.warnings) if val_res.warnings else "None",
                }])

        # Fallback to RankedStrategy summary info if detailed ValidationResult not supplied
        strat = self._ranked_map[scenario_id]
        return pd.DataFrame([{
            "scenario_id": strat.scenario_id,
            "valid": True,
            "severity": "NONE",
            "warning_count": strat.warning_count,
            "violation_count": 0,
        }])
