# G.4.6.4 — STINT / COMPOUND TIMELINE ARCHITECTURE AUDIT

## 1. Specification Lock & Executive Overview

Phase **G.4.6.4 Strategy Stint / Compound Timeline** is officially defined as an interactive visual representation of the stint sequence, tire compound usage, stint boundaries, and pit-stop transitions for a user-selected strategy from **G.4.5.5** (`StrategyOptimizer` / `RankingResult`) via **G.4.6.1** (`StrategyDashboardAdapter`).

### Mandatory Scope Boundaries
- **SCOPE**: Pure read-only presentation and visual analytics of stint timelines and pit-stop events.
- **NOT IN SCOPE**: Sensitivity Analysis, Monte Carlo simulation, probabilistic simulation, scenario re-generation, strategy re-optimization, or constraint re-validation.

---

## 2. Upstream Data Contract Inspection

### Stint Contract (`Stint` & `SimulationResult.stint_summary`)
| Field | Type | Availability | Source |
| :--- | :--- | :--- | :--- |
| `stint_number` | `int` | Mandatory | `Stint.stint_number` / `stint_summary` |
| `compound` | `str` | Mandatory | `Stint.compound` (`SOFT`, `MEDIUM`, `HARD`, `INTERMEDIATE`, `WET`) |
| `start_lap` | `int` | Mandatory | `Stint.start_lap` (1-based inclusive) |
| `end_lap` | `int` | Mandatory | `Stint.end_lap` (1-based inclusive) |
| `stint_laps` | `int` | Mandatory / Derivable | `Stint.stint_laps` or `(end_lap - start_lap) + 1` |
| `starting_fuel` | `float` | Optional | `Stint.starting_fuel` (kg) |
| `ending_fuel` | `float` | Optional | `Stint.ending_fuel` (kg) |
| `starting_tire_wear` | `float` | Optional | `Stint.starting_tire_wear` (%) |
| `ending_tire_wear` | `float` | Optional | `Stint.ending_tire_wear` (%) |

### Pit Stop Contract (`PitStop` & `SimulationResult.pit_summary`)
| Field | Type | Availability | Source |
| :--- | :--- | :--- | :--- |
| `pit_stop_id` | `str` | Optional | `PitStop.pit_stop_id` / `pit_summary` |
| `pit_lap` | `int` | Mandatory (if pit stops > 0) | `PitStop.pit_lap` |
| `duration_sec` | `float` | Mandatory (if pit stops > 0) | `PitStop.duration_sec` |
| `compound_before` | `str` | Mandatory (if pit stops > 0) | `PitStop.compound_before` |
| `compound_after` | `str` | Mandatory (if pit stops > 0) | `PitStop.compound_after` |
| `stint_before` | `int` | Mandatory (if pit stops > 0) | `PitStop.stint_before` |
| `stint_after` | `int` | Mandatory (if pit stops > 0) | `PitStop.stint_after` |

### Strategy Summary Contract (`RankedStrategy` & `RankingResult`)
| Field | Type | Source |
| :--- | :--- | :--- |
| `scenario_id` | `str` | `RankedStrategy.scenario_id` |
| `rank` | `int` | `RankedStrategy.rank` |
| `total_race_time_sec` | `float` | `RankedStrategy.total_race_time_sec` |
| `delta_to_leader_sec` | `float` | `RankedStrategy.delta_to_leader_sec` |
| `pit_stop_count` | `int` | `RankedStrategy.pit_stop_count` |
| `final_fuel_kg` | `float` | `RankedStrategy.final_fuel_kg` |
| `avg_final_tire_wear_pct` | `float` | `RankedStrategy.avg_final_tire_wear_pct` |
| `warning_count` | `int` | `RankedStrategy.warning_count` |
| `leader_scenario_id` | `str` | `RankingResult.leader_scenario_id` |

### Explicitly Unavailable Telemetry (DO NOT FABRICATE)
- **Weather Track Conditions**: Not explicitly part of `RankedStrategy` output. If missing, displays as `"N/A"` or `"DRY (Default)"`.
- **Tire Temperatures**: Not present in G.4.5 domain objects.
- **Vehicle Setup Parameters**: Aero wing angles or suspension geometry.

---

## 3. Derivable Presentation Fields

- **`stint_length`**: Derived as `(end_lap - start_lap) + 1` if not explicitly present in raw dictionary.
- **`pit_transition`**: Presentation string representing pit stop timing (e.g. `"Lap 20 (22.5s)"` or `"N/A"` for final stint).
- **`is_leader`**: Derived boolean `(scenario_id == ranking_result.leader_scenario_id)`.

---

## 4. UI Visualization Design

1. **Compact Summary Card Header**: Displays Scenario ID, Rank, Leader Status, Total Race Time, Delta to Leader, Pit Stops, Fuel Left, Tire Wear, and Warning Count.
2. **Gantt-Style Stint Timeline Visual**: Horizontal bar display using Streamlit/Plotly timeline showing stints mapped from `start_lap` to `end_lap`, color-coded consistently by compound (`SOFT` = Red, `MEDIUM` = Yellow, `HARD` = White/Light Slate, `INTERMEDIATE` = Green, `WET` = Blue).
3. **Compound Transition & Stint Breakdown Table**:
   - Columns: `Stint`, `Compound`, `Start Lap`, `End Lap`, `Stint Laps`, `Fuel Start (kg)`, `Fuel End (kg)`, `Tire Wear Start (%)`, `Tire Wear End (%)`, `Pit Transition`.

---

## 5. Governance & Immutability Strategy

- **Zero Re-ranking**: Upstream `RankingResult` order is inviolable.
- **Zero Re-simulation**: Modifying the selected strategy updates view rendering only; no simulator execution is triggered.
- **Immutability Enforcement**: Tested via deep-copy equality checks (`assert original == copy.deepcopy(original)`).

---

## 6. Performance Strategy

- Timeline data is materialized **only for the single selected strategy** ($O(\text{stints})$ space and time complexity, where $\text{stints} \le 10$).
- No bulk iteration over all ranked candidates.

---

## 7. Audit Verdict

**GREEN — READY FOR G.4.6.4 IMPLEMENTATION**
