# G.4.6.1 Dashboard Adapter — Architecture Audit

**Status:** ARCHITECTURE AUDIT COMPLETE  
**Phase:** G.4.6.1 — Strategy Dashboard Adapter  
**Date:** 2026-09-24  
**Author:** Antigravity AI  

---

## 1. Objective & Scope Boundaries

Phase **G.4.6.1** implements a lightweight, deterministic, read-only **Strategy Dashboard Adapter** (`StrategyDashboardAdapter`) inside `code/ml/strategy/dashboard_adapter.py`.

The adapter serves as the **exclusive data view-model layer** between the validated G.4.5 strategy intelligence engine (G.4.5.1 $\rightarrow$ G.4.5.5) and future G.4.6 UI components.

### Scope Boundaries:
- **IN SCOPE:** Transforming immutable domain objects (`RankingResult`, `RankedStrategy`, `SimulationResult`, `ValidationResult`, `Scenario`) into dashboard-friendly Pandas DataFrames and dictionary view-models.
- **OUT OF SCOPE:** Race simulation, physics recomputation, tire degradation equations, fuel model calculations, constraint validation, re-ranking/scoring, ML model training, dynamic LLM commentary, database access, REST endpoints, and Streamlit UI layout code.

---

## 2. Upstream Domain Classes & Attributes Inspected

The following exact Python dataclasses and attributes were inspected in `code/ml/strategy/`:

### A. `RankingResult` (`code/ml/strategy/ranking_result.py`)
- `ranked_strategies: Tuple[RankedStrategy, ...]`
- `total_candidates: int`
- `valid_candidates: int`
- `excluded_candidates: int`
- `top_k: int`
- `ranking_version: str`
- `leader_scenario_id: Optional[str]`
- `leader_race_time_sec: Optional[float]`
- `.is_empty: bool` (property)
- `.to_dict() -> Dict[str, Any]`

### B. `RankedStrategy` (`code/ml/strategy/ranking_candidate.py`)
- `rank: int` (1-based ordinal rank)
- `scenario_id: str` (Canonical deterministic ID: `SCN_<SHA256[:12]>`)
- `canonical_key: str` (Stint sequence string: `SOFT:1-20|MEDIUM:21-50`)
- `total_race_time_sec: float` (Cumulative race time in seconds)
- `pit_stop_count: int` (Total completed pit stops)
- `final_fuel_kg: float` (Fuel remaining at finish line in kg)
- `avg_final_tire_wear_pct: float` (Average 4-wheel tire wear at finish line in %)
- `warning_count: int` (Total non-invalidating soft warnings)
- `delta_to_leader_sec: float` (Race time gap to Rank 1 leader in seconds)
- `ranking_explanation: str` (Static deterministic rationale string)
- `.to_dict() -> Dict[str, Any]`

### C. `SimulationResult` (`code/ml/strategy/simulator.py`)
- `race_id: str`
- `total_laps: int`
- `total_race_time_sec: float`
- `pit_stop_count: int`
- `total_pit_time_sec: float`
- `final_fuel_kg: float`
- `total_fuel_consumed_kg: float`
- `final_tire_wear: Dict[str, float]` (e.g. `{"FL": 12.3, "FR": 14.2, "RL": 10.1, "RR": 11.5}`)
- `stint_summary: List[Dict[str, Any]]` (`stint_number`, `compound`, `start_lap`, `end_lap`, `stint_laps`, `starting_fuel`, `ending_fuel`, `fuel_consumed`, `starting_wear`, `ending_wear`, `avg_wear`)
- `pit_summary: List[Dict[str, Any]]` (`pit_stop_number`, `pit_lap`, `compound_in`, `compound_out`, `pit_duration_sec`)
- `lap_records: List[Dict[str, Any]]` (`lap_number`, `stint_number`, `compound`, `tire_age_laps`, `fuel_kg`, `fuel_consumed_kg`, `tire_wear_fl`, `tire_wear_fr`, `tire_wear_rl`, `tire_wear_rr`, `avg_tire_wear`, `lap_time_sec`, `pit_loss_sec`, `cum_time_sec`)
- `is_feasible: bool`
- `warnings: List[str]`

### D. `ValidationResult` & `Violation` (`code/ml/strategy/validation_result.py`)
- `ValidationResult`: `scenario_id`, `race_id`, `valid`, `severity`, `violations` (Tuple[`Violation`]), `warnings` (Tuple[str]), `checked_constraints_count`, `validator_version`, `.violation_count`, `.warning_count`
- `Violation`: `constraint_id`, `category`, `severity`, `message`, `actual_value`, `expected_value`, `lap_number`, `stint_id`

### E. `Scenario` (`code/ml/strategy/scenario.py`)
- `scenario_id: str`
- `race_id: str`
- `total_laps: int`
- `starting_compound: str`
- `compound_sequence: List[str]`
- `stints: List[Stint]`
- `pit_stops: List[PitStop]`
- `number_of_stops: int`
- `number_of_stints: int`
- `canonical_key: str`

---

## 3. Data Field Audit & Classification

| Dashboard Field | Classification | Source Attribute | Notes |
| :--- | :--- | :--- | :--- |
| `rank` | **AVAILABLE** | `RankedStrategy.rank` | Ordinal rank position 1..K |
| `scenario_id` | **AVAILABLE** | `RankedStrategy.scenario_id` | Canonical ID |
| `canonical_key` | **AVAILABLE** | `RankedStrategy.canonical_key` | Stint sequence string |
| `total_race_time_sec` | **AVAILABLE** | `RankedStrategy.total_race_time_sec` | Total completion time |
| `pit_stop_count` | **AVAILABLE** | `RankedStrategy.pit_stop_count` | Completed stops count |
| `final_fuel_kg` | **AVAILABLE** | `RankedStrategy.final_fuel_kg` | Remaining fuel mass |
| `avg_final_tire_wear_pct` | **AVAILABLE** | `RankedStrategy.avg_final_tire_wear_pct` | Average wear % |
| `warning_count` | **AVAILABLE** | `RankedStrategy.warning_count` | Count of soft warnings |
| `delta_to_leader_sec` | **AVAILABLE** | `RankedStrategy.delta_to_leader_sec` | Time gap to leader |
| `ranking_explanation` | **AVAILABLE** | `RankedStrategy.ranking_explanation` | Static explanation string |
| `stint_summary` | **AVAILABLE** | `SimulationResult.stint_summary` | Per-stint breakdown dicts |
| `pit_summary` | **AVAILABLE** | `SimulationResult.pit_summary` | Per-pit stop breakdown dicts |
| `lap_records` | **AVAILABLE** | `SimulationResult.lap_records` | Lap-by-lap time, fuel, wear telemetry |
| `valid` | **AVAILABLE** | `ValidationResult.valid` | Hard validation flag |
| `severity` | **AVAILABLE** | `ValidationResult.severity` | Validation severity tag |
| `violations` | **AVAILABLE** | `ValidationResult.violations` | Detailed violation objects |
| `pit_timestamps` | **DERIVABLE** | `SimulationResult.pit_summary` | Pit lap $\times$ cumulative time |
| `track_id` | **DERIVABLE** | `SimulationResult.race_id` | Derived from `race_id` prefix |
| `tire_temperatures` | **FORBIDDEN / MISSING** | N/A | **Tire surface/bulk temperatures do NOT exist upstream.** |
| `vehicle_setup` | **FORBIDDEN / MISSING** | N/A | **Car mechanical/aerodynamic setup params do NOT exist upstream.** |
| `re_ranked_scores` | **FORBIDDEN** | N/A | **Modifying optimizer ranks in UI is strictly forbidden.** |

---

## 4. Adapter Public API Contract

The `StrategyDashboardAdapter` class in `code/ml/strategy/dashboard_adapter.py` exposes 6 primary view-model methods:

```python
class StrategyDashboardAdapter:
    def __init__(
        self,
        ranking_result: RankingResult,
        simulation_results: Optional[Union[Dict[str, SimulationResult], Sequence[SimulationResult]]] = None,
        validation_results: Optional[Union[Dict[str, ValidationResult], Sequence[ValidationResult]]] = None,
        scenarios: Optional[Union[Dict[str, Scenario], Sequence[Scenario]]] = None,
    ): ...

    def leaderboard_dataframe(self) -> pd.DataFrame: ...
    def comparison_dataframe(self, scenario_ids: Optional[List[str]] = None) -> pd.DataFrame: ...
    def selected_strategy_dataframe(self, scenario_id: str) -> pd.DataFrame: ...
    def stint_dataframe(self, scenario_id: str) -> pd.DataFrame: ...
    def lap_dataframe(self, scenario_id: str) -> pd.DataFrame: ...
    def validation_dataframe(self, scenario_id: str) -> pd.DataFrame: ...
```

---

## 5. Immutability & Read-Only Strategy

1. **Zero Input Mutation:** Input objects (`RankingResult`, `RankedStrategy`, `SimulationResult`, `ValidationResult`, `Scenario`) are treated as read-only. No in-place modifications (`.sort()`, `.pop()`, property assignments) will occur.
2. **Fresh DataFrames:** All DataFrame methods return new `pd.DataFrame` instances.
3. **Deterministic Output:** No non-deterministic random operations or dynamic runtime timestamps will be generated by the adapter.

---

## 6. Performance & Memory Characteristics

- **Initialization Overhead:** $O(K)$ indexing of Top-K `RankedStrategy` items and $O(M)$ hash mapping of optional detail objects.
- **Lazy Materialization:** Heavy lap-by-lap telemetry DataFrames (`lap_dataframe`) are materialized **only on demand** when requested for a specific `scenario_id`.
- **Memory Footprint:** Avoids pre-expanding telemetry DataFrames for all candidates.

---

## 7. Test Strategy

`tests/test_dashboard_adapter.py` will validate:
1. `RankingResult` acceptance & empty result handling.
2. Exact column and row matching for `leaderboard_dataframe`.
3. Preservation of exact values and ordering without re-ranking.
4. Immutability of input objects.
5. Determinism across repeated calls.
6. `scenario_id` lookup and `ValueError` handling for unknown IDs.
7. Real stint, lap, and validation DataFrame materialization.
8. Explicit absence of fabricated `tire_temperatures` or `vehicle_setup` columns.
9. End-to-end integration test from `ScenarioGenerator` $\rightarrow$ `StrategySimulator` $\rightarrow$ `ConstraintValidator` $\rightarrow$ `StrategyOptimizer` $\rightarrow$ `StrategyDashboardAdapter`.
