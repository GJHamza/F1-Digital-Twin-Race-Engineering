# G.4.6.2 Strategy Leaderboard — Architecture Audit

**Status:** ARCHITECTURE AUDIT COMPLETE  
**Phase:** G.4.6.2 — Strategy Leaderboard  
**Date:** 2026-09-24  
**Author:** Antigravity AI  

---

## 1. Objective & Scope Boundaries

Phase **G.4.6.2** implements the **Strategy Leaderboard** presentation component for the F1 Digital Twin Strategy Analytics Dashboard using Streamlit.

The leaderboard is a **pure presentation UI layer** consuming output from `StrategyDashboardAdapter` (G.4.6.1) and `RankingResult` (G.4.5.5).

### Scope Boundaries:
- **IN SCOPE:** Streamlit leaderboard UI rendering, compact leader KPI cards, view-level filtering (rank limit, scenario search, pit stop count filter, warning filter, status filter), scenario selection storing `selected_scenario_id` in `st.session_state`, and presentation formatting.
- **OUT OF SCOPE:** Re-ranking strategies, computing new scores, modifying ranking criteria, running simulations, re-validating constraints, re-optimizing scenarios, mutating domain objects, ML/LLM/database integrations, or starting G.4.6.3 (Trade-off Analysis).

---

## 2. Upstream Data Contracts & Source of Truth

### A. Authoritative Source of Truth
- **G.4.5.5 `RankingResult`:** Holds the single authoritative, 6-tier lexicographically sorted list of `RankedStrategy` objects.
- **Lexicographic Key:** `(total_race_time_sec ASC, pit_stop_count ASC, -final_fuel_kg ASC, avg_final_tire_wear_pct ASC, canonical_key ASC, scenario_id ASC)`.
- **UI Policy:** The UI **MUST NEVER** sort or re-rank the strategies. It displays the strategies in the exact ordinal sequence returned by G.4.5.5.

### B. `StrategyDashboardAdapter` API (`code/ml/strategy/dashboard_adapter.py`)
- `adapter.leaderboard_dataframe() -> pd.DataFrame`
  - Returns DataFrame containing `rank`, `scenario_id`, `canonical_key`, `total_race_time_sec`, `pit_stop_count`, `final_fuel_kg`, `avg_final_tire_wear_pct`, `warning_count`, `delta_to_leader_sec`, `ranking_explanation`.
- `adapter.ranking_result -> RankingResult`
  - Accesses `leader_scenario_id`, `leader_race_time_sec`, `total_candidates`, `valid_candidates`, `excluded_candidates`, `top_k`, `.is_empty`.

---

## 3. Existing Integration Point & Architecture

- **Existing Dashboard:** [`code/partie3/analytics_dashboard.py`](file:///c:/Users/Hamza/OneDrive/Desktop/F1_Data_Project/code/partie3/analytics_dashboard.py) contains the project's primary Streamlit analytics application.
- **Target Integration Location:**
  - Dedicated modular implementation: `code/ml/strategy/strategy_dashboard.py` exposing helper functions `render_strategy_leaderboard(adapter, ...)` and `render_leaderboard_ui(...)`.
  - Reusable CSS & layout cards matching `analytics_dashboard.py` styling (`.metric-card-custom`, `Inter` font, modern light theme).

---

## 4. Leaderboard UI Design & Display Fields

### A. Compact Leader KPI Cards (Top Banner)
Displays top-level race summary metrics derived directly from `RankingResult`:
- **Leader Scenario ID:** `ranking_result.leader_scenario_id` (or `"N/A"`)
- **Leader Race Time:** `f"{ranking_result.leader_race_time_sec:.3f} s"` (or `"N/A"`)
- **Total Candidates:** `ranking_result.total_candidates`
- **Valid Candidates:** `ranking_result.valid_candidates`
- **Excluded Candidates:** `ranking_result.excluded_candidates`
- **Top-K Limit:** `ranking_result.top_k`

### B. Primary Leaderboard Table
Renders `st.dataframe` or formatted Streamlit table with exact column labels:

| Display Label | Data Source Field | Format |
| :--- | :--- | :--- |
| **Rank** | `rank` | Integer (`1`, `2`, ...) |
| **Scenario** | `scenario_id` | String (`SCN_a8f3b9c1d2e4`) |
| **Strategy Key** | `canonical_key` | String (`SOFT:1-25\|MEDIUM:26-50`) |
| **Race Time (s)** | `total_race_time_sec` | 3 Decimals (`5000.123`) |
| **Δ Leader (s)** | `delta_to_leader_sec` | 3 Decimals (`+15.345` or `0.000`) |
| **Pit Stops** | `pit_stop_count` | Integer (`1`, `2`) |
| **Fuel Remaining (kg)** | `final_fuel_kg` | 2 Decimals (`5.25`) |
| **Avg Tire Wear (%)** | `avg_final_tire_wear_pct` | 2 Decimals (`32.40%`) |
| **Warnings** | `warning_count` | Integer (`0`, `1`) |

> [!NOTE]
> `tire_temperatures` and `vehicle_setup` are **MISSING** upstream and will **NOT** be displayed.

---

## 5. View-Level Filtering & Selection Responsibilities

1. **Filtering Policy:**
   - Filters (rank slider, scenario ID search box, pit stop filter, warning filter) operate strictly on the **displayed DataFrame view**.
   - Filters **NEVER** alter `RankingResult` or modify ordinal ranks.
   - If the Rank 1 leader is filtered out of display, `leader_scenario_id` in the top KPI banner remains the authoritative Rank 1 leader.
2. **Scenario Selection Policy:**
   - User scenario selection stores `selected_scenario_id` in `st.session_state["selected_scenario_id"]`.
   - Selection changes do **NOT** execute simulation, validation, or optimization.

---

## 6. Immutability & Performance Strategy

- **Immutability:** Upstream domain objects (`RankingResult`, `RankedStrategy`, DataFrames) are deep-copy verified to remain 100% unmutated.
- **Performance:** Consumes Top-K ($K \le 100$) leaderboard DataFrames in $O(K)$ time without loading full lap-by-lap telemetry.

---

## 7. Test Strategy

`tests/test_strategy_leaderboard.py` will validate:
1. Leaderboard rendering data structures with valid `RankingResult`.
2. Graceful empty ranking result handling ($0$ valid strategies).
3. Exact preservation of ranking order, ranks, scenario IDs, completion times, time deltas, pit stop counts, fuel margins, tire wear percentages, warnings, and leader metadata.
4. View filtering does not rerank or mutate `RankingResult`.
5. Filtering out leader does not create a new leader in summary metrics.
6. Scenario selection stores `scenario_id` in `st.session_state`.
7. **Mandatory No-Reranking Test:** Verifies custom non-trivial input order is strictly preserved.
8. **Mandatory No-Mutation Test:** Verifies `original == deep_copy` after UI processing.
9. **Full Integration Test:** End-to-end flow from G.4.5.2 $\rightarrow$ G.4.5.3 $\rightarrow$ G.4.5.4 $\rightarrow$ G.4.5.5 $\rightarrow$ G.4.6.1 $\rightarrow$ G.4.6.2.
