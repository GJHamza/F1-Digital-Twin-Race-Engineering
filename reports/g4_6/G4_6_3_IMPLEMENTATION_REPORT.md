# G.4.6.3 — STRATEGY COMPARISON / TRADE-OFF ANALYSIS IMPLEMENTATION REPORT

## 1. Objective
Implement **G.4.6.3 — Strategy Comparison / Trade-off Analysis** as a presentation-only Streamlit UI layer for evaluating side-by-side trade-offs between up to 4 strategies from **G.4.5.5** via **G.4.6.1** `StrategyDashboardAdapter`.

---

## 2. Architecture Audit
The pre-implementation audit documented:
- Upstream `RankingResult` and `StrategyDashboardAdapter` metrics.
- Exposing stint details (`stint_dataframe`) and lap telemetry (`lap_dataframe`).
- Explicit non-existence of tire surface/carcass temperature telemetry in the G.4.5 strategy domain.
- Pure view-model transformation guarantees without domain re-ranking or score re-computation.

---

## 3. Comparison Contract & Data Model
Data preparation is handled by `prepare_comparison_view_data(adapter, scenario_ids, max_compare=4)`.

Returned view model dictionary:
- `comparison_df`: DataFrame of metrics (`rank`, `scenario_id`, `canonical_key`, `total_race_time_sec`, `delta_to_leader_sec`, `pit_stop_count`, `final_fuel_kg`, `avg_final_tire_wear_pct`, `warning_count`).
- `stint_df_map`: Dict mapping `scenario_id` to its stint breakdown DataFrame.
- `lap_df_map`: Dict mapping `scenario_id` to its lap telemetry DataFrame.
- `leader_scenario_id`: Authoritative leader ID string.
- `leader_included`: Boolean indicating if leader is present in the comparison selection.
- `selected_scenario_ids`: Ordered list of selected strategy IDs.

---

## 4. Selection Model
- Interactive multi-select widget in Streamlit (`render_strategy_comparison`).
- Selection bounded to **4 strategies maximum** (default: Leader + top strategies up to 4).
- State persisted in `st.session_state["comparison_scenario_ids"]`.
- Selection changes update view rendering without triggering domain simulation or re-optimization.

---

## 5. Trade-off Metrics & Formatting
Formatted columns preserve exact numerical precision:
- **Race Time**: 3 decimals
- **Delta to Leader**: 3 decimals
- **Fuel Remaining**: 2 decimals
- **Tire Wear**: 2 decimals
- **Pit Stops**: Integer
- **Warnings**: Integer

---

## 6. Trade-Off Charts
Visualizations implemented using Streamlit chart components:
1. **Race Time vs. Final Fuel**: Scatter plot exposing trade-off between fuel safety margin and race duration.
2. **Race Time vs. Average Tire Wear**: Scatter plot showing degradation impact on race time.
3. **Race Time vs. Pit Stops**: Bar chart comparing pit stop strategy counts.

---

## 7. Stint / Compound Representation
Exposes stint breakdowns using `stint_dataframe(scenario_id)`:
- `stint_number`, `compound`, `start_lap`, `end_lap`, `stint_laps`, `starting_fuel`, `ending_fuel`, `fuel_consumed`, `starting_wear`, `ending_wear`, `avg_wear`.

---

## 8. Fuel Trajectory
Lap-by-lap line plot of remaining fuel mass (`lap_number` vs `fuel_kg`) across selected strategies.

---

## 9. Tire Wear Trajectory
Lap-by-lap line plot of average tire degradation (`lap_number` vs `avg_tire_wear` / 4-wheel wear) across selected strategies.
*Note: Tire temperatures are not fabricated.*

---

## 10. Normalization Rules
No composite normalization score is computed. Visual scaling is handled purely by chart axes to prevent any alteration of strategy ranking semantics.

---

## 11. Leader Preservation
- `ranking_result.leader_scenario_id` is preserved as authoritative leader.
- If the user excludes the leader from the comparison set, the UI displays:
  `"ℹ️ Authoritative leader (SCN_...) is not included in current comparison selection."`
- The leader is NOT re-assigned.

---

## 12. Filtering Behavior
Filters operate at the presentation view level only without altering upstream `RankingResult` objects.

---

## 13. Immutability
All upstream objects (`RankingResult`, `RankedStrategy`, `SimulationResult`, `ValidationResult`) remain strictly read-only.
Verified via `test_mandatory_no_mutation` (`assert original == copy.deepcopy(original)`).

---

## 14. Performance Strategy
- Telemetry (`stint_dataframe`, `lap_dataframe`) is requested ONLY for the selected comparison set (≤ 4 strategies).
- Keeps memory footprint bounded at $O(K_{\text{selected}})$ instead of $O(N_{\text{total}})$.

---

## 15. Unit & Integration Test Results
File: `tests/test_strategy_comparison.py`
- **17 passed / 0 failed**

Coverage highlights:
- Acceptance of valid scenario IDs.
- Error handling for unknown scenario IDs.
- Leader preservation.
- Exact metric value preservation.
- Maximum comparison count enforcement (capped at 4).
- Deduplication of scenario IDs.
- Empty and single-strategy edge cases.
- Missing optional stint/lap telemetry handling.
- Mandatory No-Reranking test.
- Mandatory No-Mutation test.
- End-to-end pipeline integration test (G.4.5.2 → G.4.5.3 → G.4.5.4 → G.4.5.5 → G.4.6.1 → G.4.6.2 → G.4.6.3).

---

## 16. Integration
Combined test run with `tests/test_strategy_leaderboard.py`:
- **33 passed / 0 failed**

---

## 17. Limitations
- Maximum comparison set capped at 4 strategies to avoid visual clutter and unnecessary telemetry loading.
- Lap-level trajectories display aggregate/4-wheel wear without tire temperature data.

---

## 18. Scope Isolation
- No modification to G.4.5.1–G.4.5.5 domain logic.
- G.4.6.4 (Sensitivity Analysis) has NOT been started.

---

## 19. Final Status
**GREEN — READY FOR G.4.6.4**
