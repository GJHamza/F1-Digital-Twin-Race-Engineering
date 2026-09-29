# G.4.6.5 — FUEL & TIRE ANALYTICS ARCHITECTURE AUDIT

## 1. Executive Summary

Phase **G.4.6.5 — Fuel & Tire Analytics** provides single-strategy micro-analytics for fuel burn efficiency, fuel reserve margins, 4-corner wheel tire wear breakdown (FL, FR, RL, RR), wear asymmetry/balance, and remaining tire life projections.

This audit evaluates the exact scope of G.4.6.5, distinguishes its unique engineering value from already validated presentation components (G.4.6.2 Leaderboard, G.4.6.3 Comparison, G.4.6.4 Stint Timeline), and establishes strict boundaries preventing duplicate charting or illegal physics additions.

---

## 2. Current G.4.6 Dashboard Architecture & Lineage

```
G.4.5.5 Strategy Optimizer ──────── (Authoritative RankingResult)
       │
G.4.6.1 StrategyDashboardAdapter ── (DataFrames: leaderboard, stint, lap, pit, validation)
       │
       ├──► G.4.6.2 Strategy Leaderboard ──── (Global Top-K Leaderboard & Filtering)
       │
       ├──► G.4.6.3 Strategy Comparison ───── (Multi-strategy Trade-off Scatters & Trajectories)
       │
       ├──► G.4.6.4 Stint / Compound Timeline (Gantt Stint Execution & Pit Transitions)
       │
       └──► G.4.6.5 Fuel & Tire Analytics ── (Single-strategy Micro-Analytics & 4-Corner Health)
```

---

## 3. Original G.4.6.5 Roadmap Scope

- **Intended Objective**: In-depth telemetry analysis of fuel depletion dynamics and tire degradation health for a selected race strategy.
- **Target Audience**: Race engineers evaluating fuel reserve safety, fuel burn consistency, and wheel-level tire wear imbalance.
- **Input Data**: `StrategyDashboardAdapter` (`lap_dataframe`, `stint_dataframe`, `selected_strategy_dataframe`, `validation_dataframe`).
- **Output Artifacts**: Engineering KPI cards, 4-corner wheel wear curves, wear balance metrics, fuel burn rate trends, and threshold alerts.

---

## 4. Existing Fuel Functionality Inventory

| Feature | Location / Phase | Inputs | Outputs | Status |
| :--- | :--- | :--- | :--- | :--- |
| `final_fuel_kg` | G.4.6.1, G.4.6.2, G.4.6.3, G.4.6.4 | `RankedStrategy` / `SimulationResult` | Numeric metric | Implemented |
| Stint Fuel Consumption | G.4.6.1 (`stint_dataframe`), G.4.6.3, G.4.6.4 | `stint_summary` | Starting / Ending fuel | Implemented |
| Lap Fuel Trajectory | G.4.6.1 (`lap_dataframe`), G.4.6.3 | `lap_records` | Multi-strategy line plot | Implemented |
| Race Time vs Fuel Scatter | G.4.6.3 | `comparison_dataframe` | Scatter plot | Implemented |
| **Fuel Burn Rate ($\text{kg/lap}$)** | G.4.6.1 (`lap_dataframe` raw) | `fuel_consumed_kg` | None (Unvisualized) | **G.4.6.5 Unique** |
| **Fuel Reserve / Safety Margin** | G.4.6.1 (`selected_strategy_dataframe`) | `final_fuel_kg` - reserve | None (Unvisualized) | **G.4.6.5 Unique** |

---

## 5. Existing Tire Functionality Inventory

| Feature | Location / Phase | Inputs | Outputs | Status |
| :--- | :--- | :--- | :--- | :--- |
| `avg_final_tire_wear_pct` | G.4.6.1, G.4.6.2, G.4.6.3, G.4.6.4 | `RankedStrategy` / `SimulationResult` | Numeric metric | Implemented |
| Stint Tire Wear | G.4.6.1 (`stint_dataframe`), G.4.6.3, G.4.6.4 | `stint_summary` | Starting / Ending wear | Implemented |
| Lap Avg Wear Trajectory | G.4.6.1 (`lap_dataframe`), G.4.6.3 | `lap_records` | Multi-strategy line plot | Implemented |
| Race Time vs Wear Scatter | G.4.6.3 | `comparison_dataframe` | Scatter plot | Implemented |
| **4-Corner Wear (FL, FR, RL, RR)** | G.4.6.1 (`lap_dataframe` raw) | `lap_records` | None (Unvisualized) | **G.4.6.5 Unique** |
| **Axle / Side Wear Balance** | G.4.6.1 (`lap_dataframe` raw) | `tire_wear_fl..rr` | None (Unvisualized) | **G.4.6.5 Unique** |
| **Tire Degradation Rate ($\%/\text{lap}$)** | G.4.6.1 (`stint_dataframe` raw) | Wear / Stint Laps | None (Unvisualized) | **G.4.6.5 Unique** |
| **Remaining Tire Life (Laps)** | G.4.6.1 (`lap_dataframe` raw) | Max wear - Current wear | None (Unvisualized) | **G.4.6.5 Unique** |

---

## 6. G.4.6.3 / G.4.6.4 Overlap & Non-Duplication Analysis

- **G.4.6.3 Comparison Focus**: Macro comparison across multiple strategies (up to 4) with aggregated metrics (Race Time, Total Fuel, Average Tire Wear) and scatter plots.
- **G.4.6.4 Timeline Focus**: Macro stint execution timeline (Gantt chart of start/end laps and pit stop transitions).
- **G.4.6.5 Analytics Focus**: **Single-strategy micro-analytics** inspecting raw 4-corner wheel telemetry (`tire_wear_fl`, `tire_wear_fr`, `tire_wear_rl`, `tire_wear_rr`), fuel burn rate per lap, axle/lateral wear balance ratios, and remaining tire life projections.

---

## 7. Duplication Matrix

| Feature | G.4.6.1 | G.4.6.2 | G.4.6.3 | G.4.6.4 | G.4.6.5 (Proposed) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| 1. Fuel Trajectory (Multi-strategy) | ✓ | — | ✓ | — | — |
| 2. Final Fuel | ✓ | ✓ | ✓ | ✓ | ✓ (Summary) |
| 3. Stint Fuel Consumed | ✓ | — | ✓ | ✓ | ✓ |
| 4. Fuel vs Race Time Scatter | — | — | ✓ | — | — |
| 5. Tire Wear Trajectory (Aggregate) | ✓ | — | ✓ | — | — |
| 6. Final Tire Wear | ✓ | ✓ | ✓ | ✓ | ✓ (Summary) |
| 7. Average Tire Wear per Lap | ✓ | — | ✓ | — | — |
| 8. Tire Wear vs Race Time Scatter | — | — | ✓ | — | — |
| 9. Compound/Stint Tire Context | ✓ | — | ✓ | ✓ | ✓ |
| 10. Tire & Fuel Warnings | ✓ | ✓ | ✓ | ✓ | ✓ |
| 11. **4-Corner Wheel Wear (FL, FR, RL, RR)** | ✓ (Raw) | — | — | — | **✓ (UNIQUE)** |
| 12. **Fuel Burn Rate per Lap ($\text{kg/lap}$)** | ✓ (Raw) | — | — | — | **✓ (UNIQUE)** |
| 13. **Axle & Lateral Wear Balance Ratios** | — | — | — | — | **✓ (UNIQUE)** |
| 14. **Fuel Safety Margin / Reserve Analysis** | — | — | — | — | **✓ (UNIQUE)** |
| 15. **Tire Degradation Rate ($\%/\text{lap}$)** | — | — | — | — | **✓ (UNIQUE)** |
| 16. **Remaining Tire Life (Laps to limit)** | — | — | — | — | **✓ (UNIQUE)** |
| 17. **Engineering Alert Badges (Wear/Fuel)** | — | — | — | — | **✓ (UNIQUE)** |

---

## 8. Available Data Contract Audit

### Directly Available (via `StrategyDashboardAdapter.lap_dataframe`)
- `fuel_kg`, `fuel_consumed_kg`, `tire_wear_fl`, `tire_wear_fr`, `tire_wear_rl`, `tire_wear_rr`, `avg_tire_wear`, `lap_number`, `stint_number`, `compound`.

### Directly Available (via `StrategyDashboardAdapter.stint_dataframe`)
- `stint_number`, `compound`, `start_lap`, `end_lap`, `starting_fuel`, `ending_fuel`, `fuel_consumed`, `starting_wear`, `ending_wear`, `avg_wear`.

### Presentation-Derivable Data (Read-Only Computations)
- `avg_fuel_burn_rate`: `total_fuel_consumed_kg / total_laps`.
- `fuel_safety_margin`: `final_fuel_kg - 1.0` (where 1.0 kg is default FIA regulation reserve).
- `axle_wear_balance_front_vs_rear`: `avg(FL, FR) - avg(RL, RR)`.
- `lateral_wear_balance_left_vs_right`: `avg(FL, RL) - avg(FR, RR)`.
- `stint_degradation_rate`: `(ending_wear - starting_wear) / stint_laps`.
- `remaining_tire_life_laps`: `max(0, (max_tire_wear - avg_tire_wear) / stint_degradation_rate)`.

### Missing / Unavailable Data (DO NOT FABRICATE)
- **Tire Surface / Carcass Temperatures**: Not modeled in G.4.5 strategy domain.
- **Dynamic Track Rubbering / Ambient Weather Drift**: Strategy domain assumes static weather per scenario.
- **Real-Time Fuel Flow Sensor Telemetry**: Simulated consumption is used.

---

## 9. Domain vs. Presentation Boundary

- **Domain Models (`G.4.5.x`)**: Immutable source of truth. No source modifications permitted.
- **Dashboard Adapter (`G.4.6.1`)**: Exposes raw DataFrames (`lap_dataframe`, `stint_dataframe`). Can be extended cleanly if additional helper view-models are needed.
- **Dashboard Presentation (`G.4.6.5`)**: Reads DataFrames, computes read-only derived analytics, and renders Streamlit visualizations. Zero physics re-computation.

---

## 10. Proposed Unique G.4.6.5 Responsibility

G.4.6.5 should deliver a **Single-Strategy Engineering Telemetry & Degradation Cockpit**:
1. **Fuel Efficiency & Safety Margin Card Header**: Displays total fuel burned, average burn rate ($\text{kg/lap}$), final fuel reserve margin, and fuel depletion risk badge.
2. **4-Corner Wheel Degradation Breakdown**: 4-line plot (`FL`, `FR`, `RL`, `RR` wear over race laps) revealing wheel-specific wear progression.
3. **Tire Wear Balance Ratios**: Front vs Rear axle wear delta and Left vs Right lateral wear delta.
4. **Stint Degradation Rates & Remaining Life Table**: Per-stint degradation rate ($\%/\text{lap}$), peak wear wheel, and projected remaining laps before hitting 85% wear limit.
5. **Engineering Threshold Alert Cards**: Highlight high degradation rates, front/rear imbalance ($> 5\%$), or low fuel reserve ($< 2.0\text{ kg}$).

---

## 11. Proposed Data Contract & Visualizations

### Data Contract (`prepare_fuel_tire_analytics_view_data`)
```python
{
    "summary": {
        "scenario_id": str,
        "rank": int,
        "final_fuel_kg": float,
        "avg_fuel_burn_rate_kg_lap": float,
        "fuel_safety_margin_kg": float,
        "avg_final_tire_wear_pct": float,
        "max_corner_wear_pct": float,
        "most_worn_wheel": str,
        "front_rear_bias_pct": float,
        "left_right_bias_pct": float,
        "is_leader": bool,
    },
    "corner_wear_df": pd.DataFrame, # lap_number, FL, FR, RL, RR
    "stint_analytics_df": pd.DataFrame, # stint, compound, laps, wear_rate, remaining_life
    "alerts": List[Dict[str, str]], # severity, category, message
    "scenario_id": str,
}
```

---

## 12. Proposed Test Strategy

Minimum 18 test cases identified for `tests/test_fuel_tire_analytics.py`:
1. Valid strategy produces fuel & tire analytics view data.
2. Fuel burn rate calculation is accurate.
3. Fuel safety margin calculation is correct.
4. 4-corner wheel wear metrics (FL, FR, RL, RR) are preserved.
5. Axle wear balance (Front vs Rear) is derived accurately.
6. Lateral wear balance (Left vs Right) is derived accurately.
7. Tire degradation rate per stint is derived accurately.
8. Remaining tire life projection handles zero degradation rate safely.
9. Scenario ID and rank are preserved.
10. Leader identification uses authoritative `leader_scenario_id`.
11. Zero re-ranking of strategies.
12. Upstream objects deep-copy immutability.
13. Empty ranking handled safely.
14. Unknown scenario_id handled safely.
15. No fabricated tire temperature data.
16. Deterministic presentation output.
17. Bounded materialization (single selected strategy).
18. E2E integration test (G.4.5.2 $\rightarrow$ ... $\rightarrow$ G.4.6.5).

---

## 13. Performance Strategy

- Selected-strategy materialization: Telemetry is loaded **only for the active `selected_scenario_id`** ($O(N_{\text{laps}})$, $\sim 50\text{--}70$ rows).
- Memory footprint: $< 1$ MB.
- No database, REST API, or full-dataset loops.

---

## 14. Explicit Non-Goals

- **NO Monte Carlo Analysis**
- **NO Sensitivity Analysis**
- **NO Strategy Re-Optimization or Re-Ranking**
- **NO Race Simulation Rerun**
- **NO Machine Learning Training / Inference**
- **NO Database or REST API Integration**
- **NO Fabricated Tire Temperature Telemetry**

---

## 15. Scope Decision

**OPTION A: SCOPE CONFIRMED — READY FOR IMPLEMENTATION**

*Justification*: The G.4.5 domain telemetry contains raw 4-corner wheel wear data (`tire_wear_fl`, `tire_wear_fr`, `tire_wear_rl`, `tire_wear_rr`) and lap-by-lap fuel consumption (`fuel_consumed_kg`) that are currently unvisualized in G.4.6.2, G.4.6.3, and G.4.6.4. Implementing G.4.6.5 as a single-strategy 4-corner tire health & fuel reserve cockpit provides high unique engineering value with zero duplication of previous phases.
