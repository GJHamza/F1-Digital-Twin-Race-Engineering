# G.4.6.4 — STINT / COMPOUND TIMELINE IMPLEMENTATION REPORT

## 1. Objective
Implement **G.4.6.4 — Stint / Compound Timeline** as a read-only Streamlit UI presentation layer for visualizing race stint sequences, tire compound execution, stint boundaries, and pit-stop transitions for a selected strategy from **G.4.5.5** (`StrategyOptimizer` / `RankingResult`) via **G.4.6.1** (`StrategyDashboardAdapter`).

---

## 2. Architecture Audit
The pre-implementation audit confirmed:
- Stint boundaries (`start_lap`, `end_lap`, `stint_laps`) and compound mappings are fully exposed via `StrategyDashboardAdapter.stint_dataframe(scenario_id)`.
- Pit stop timing (`pit_lap`, `duration_sec`, `compound_before`, `compound_after`) is exposed via `StrategyDashboardAdapter.pit_dataframe(scenario_id)`.
- Weather and track conditions are not explicitly part of `RankedStrategy` outputs and are safely handled without fabrication.
- Sensitivity Analysis and Monte Carlo Analysis were explicitly excluded from this phase per roadmap specification lock.

---

## 3. Upstream Data Contract & Data Model
Data preparation is performed by `prepare_stint_timeline_data(adapter, scenario_id)`.

Returned view model dictionary:
- `summary`: Strategy KPI dictionary (`scenario_id`, `rank`, `total_race_time_sec`, `delta_to_leader_sec`, `pit_stop_count`, `final_fuel_kg`, `avg_final_tire_wear_pct`, `warning_count`, `number_of_stints`, `canonical_key`, `is_leader`, `validation_status`).
- `stint_df`: DataFrame of stint details from simulator/scenario.
- `pit_df`: DataFrame of pit stop event details.
- `timeline_df`: Presentation DataFrame formatted for timeline chart rendering (`stint_number`, `stint_label`, `compound`, `start_lap`, `end_lap`, `stint_laps`, `pit_transition`, `color`).
- `compound_colors`: Color palette dictionary mapping compounds (`SOFT`, `MEDIUM`, `HARD`, `INTERMEDIATE`, `WET`).

---

## 4. Stint & Compound Representation
- Preserves exact upstream `start_lap` and `end_lap` values without re-computation.
- Derives `stint_laps` as `(end_lap - start_lap) + 1` for presentation display.
- Compound strings (`SOFT`, `MEDIUM`, `HARD`, `INTERMEDIATE`, `WET`) are displayed directly from the strategy without modification.

---

## 5. Pit-Stop Representation
- Pit stops are formatted into stint transitions (e.g. `"Lap 20 (22.5s)"` or `"—"` for final stint).
- Pit duration and pit laps are retrieved directly from `pit_summary` without re-calculation.

---

## 6. Visualization Design
1. **Summary KPI Header**: Card layout showing Scenario ID, Rank, Race Time, Delta, Pit Stops, Fuel, Wear, and Validation Status.
2. **Horizontal Timeline Chart**: Visual lap progress bar display color-coded by tire compound.
3. **Compound Transition & Stint Breakdown Table**: Detailed table showing stint numbers, mounted compounds, lap ranges, stint lengths, and pit transitions.

---

## 7. Selection Behavior & Leader Handling
- Operates on a single selected strategy via `st.session_state["selected_scenario_id"]`.
- The authoritative leader (`ranking_result.leader_scenario_id`) is strictly identified (`🥇 LEADER`). Non-leader selection preserves rank and delta without creating a new leader.

---

## 8. Immutability & Performance
- All upstream domain objects remain strictly read-only (`assert original == copy.deepcopy(original)`).
- Timeline data is materialized **only for the single selected strategy** ($O(\text{stints})$ space/time complexity).

---

## 9. Unit & Integration Test Results
File: `tests/test_stint_timeline.py`
- **17 passed / 0 failed**

Coverage highlights:
- Valid strategy timeline data generation.
- Empty strategy and unknown scenario ID handling.
- Single-stint & zero-pit strategy handling.
- Multi-stint & pit-stop strategy handling.
- Stint boundaries, length, and compound preservation.
- Pit lap and pit duration preservation.
- Stint ordering preservation.
- Zero re-ranking and zero mutation verification.
- Deterministic rendering output.
- No fabricated tire temperature or vehicle setup data.
- Full End-to-End Integration test (G.4.5.2 → G.4.5.3 → G.4.5.4 → G.4.5.5 → G.4.6.1 → G.4.6.2 → G.4.6.3 → G.4.6.4).

---

## 10. Scope Isolation & Non-Inclusion Checklist
- **Monte Carlo Analysis Added**: NO
- **Sensitivity Analysis Added**: NO

---

## 11. Final Verdict
**GREEN — READY FOR G.4.6.5**
