# G.4.6.5 — Fuel & Tire Analytics Implementation Report

## 1. Objective

Phase **G.4.6.5 — Fuel & Tire Analytics** implements a single-strategy micro-analytics cockpit for the F1 Digital Twin Race Engineering Platform. It exposes detailed, presentation-layer micro-analytics on fuel burn efficiency, fuel safety reserve margins, 4-corner wheel tire wear breakdown (FL, FR, RL, RR), axle/lateral tire wear balance ratios, stint degradation rates (% / lap), estimated remaining tire life projections, and engineering alert cards.

This module acts exclusively as a **read-only presentation and visualization layer**. It consumes existing simulation and ranking outputs without modifying domain physics, running simulations, re-ranking strategies, or executing optimization routines.

---

## 2. Architecture Used

G.4.6.5 sits downstream of `StrategyDashboardAdapter` (G.4.6.1) and operates strictly on the single selected strategy identified by `scenario_id`:

```
RankingResult (G.4.5.5)
       │
       ▼
StrategyDashboardAdapter (G.4.6.1)
       │
       ▼
Selected Strategy View (scenario_id)
       │
       ▼
prepare_fuel_tire_analytics_view_data (G.4.6.5)
       ├── Section A: Fuel Burn Efficiency & Reserve
       ├── Section B: 4-Corner Tire Wear Breakdown (FL, FR, RL, RR)
       ├── Section C: Axle & Lateral Wear Balance
       ├── Section D: Stint Degradation Rate
       ├── Section E: Remaining Tire Life Projections
       └── Section F: Engineering Threshold Alert Cards
       │
       ▼
render_fuel_tire_analytics (Streamlit / Plotly UI)
```

---

## 3. Data Sources

All telemetry and metadata are sourced directly from authoritative upstream objects exposed via `StrategyDashboardAdapter`:
- `selected_strategy_dataframe`: High-level summary of the selected strategy (`start_laps_fuel_kg`, `final_fuel_kg`, `total_fuel_consumed_kg`).
- `stint_dataframe`: Detailed stint breakdown (`stint_index`, `compound`, `start_lap`, `end_lap`, `stint_length`).
- `lap_dataframe`: Per-lap telemetry curves (`lap_number`, `fuel_remaining_kg`, `tire_wear_fl`, `tire_wear_fr`, `tire_wear_rl`, `tire_wear_rr`, `tire_wear_avg_pct`).

No values are fabricated, re-simulated, or mock-generated.

---

## 4. Fuel Analytics

Fuel analytics evaluate starting fuel load, cumulative consumption, final remaining fuel, average fuel burn rate, and fuel safety reserve margin:
- **Starting Fuel**: Sourced from `start_laps_fuel_kg` or initial lap telemetry.
- **Final Remaining Fuel**: Sourced from `final_fuel_kg` or final lap telemetry.
- **Total Consumed Fuel**: `starting_fuel - final_fuel_kg`.
- **Average Burn Rate per Lap**: `total_fuel_consumed_kg / total_laps`.
- **Fuel Safety Margin**: `final_fuel_kg - minimum_fuel_reserve_kg` (default reserve = 1.0 kg).

---

## 5. Tire Analytics (4-Corner Breakdown)

4-corner tire degradation curves track wear percentage ($0\%$ brand new to $100\%$ completely worn) for each wheel corner:
- **FL (Front Left)**
- **FR (Front Right)**
- **RL (Rear Left)**
- **RR (Rear Right)**
- **Average Wear**: $(FL + FR + RL + RR) / 4.0$.

Visualization is provided via line charts showing per-lap wear progression across all 4 wheels for the selected strategy.

---

## 6. Balance Analytics (Axle & Lateral Wear Balance)

Balance ratios and deltas provide presentation-level indicators of chassis/tire wear bias:
- **Front Axle Average**: `(FL + FR) / 2.0`
- **Rear Axle Average**: `(RL + RR) / 2.0`
- **Left Side Average**: `(FL + RL) / 2.0`
- **Right Side Average**: `(FR + RR) / 2.0`
- **Axle Difference**: `front_axle_avg - rear_axle_avg`
- **Lateral Difference**: `left_side_avg - right_side_avg`
- **Front / Rear Ratio**: `front_axle_avg / rear_axle_avg` (returns NaN if denominator is zero).

---

## 7. Stint Degradation

For each stint in the selected strategy, degradation is computed as wear accumulation per lap:
- **Stint Wear Delta**: `wear_at_end_of_stint - wear_at_start_of_stint`
- **Degradation Rate (% / lap)**: `stint_wear_delta / stint_length`
- Per-corner stint degradation is also evaluated for FL, FR, RL, and RR.

---

## 8. Remaining Tire Life Projections

Linear presentation-level projection estimating remaining lap capacity before reaching the hard wear limit ($85\%$ maximum allowable tire wear):
- **Wear Limit**: $85\%$ (authoritative G.4.5.4 constraint threshold).
- **Remaining Capacity**: $85.0 - \text{current\_wear}$.
- **Estimated Remaining Laps**: $\text{remaining\_capacity} / \text{degradation\_rate\_pct\_per\_lap}$.
- **Safeguard**: If degradation rate $\le 0$ or remaining capacity $\le 0$, the projection displays `"Projection unavailable"`.

---

## 9. Engineering Alert System

Status cards provide real-time indicators based on predefined engineering thresholds:
- **Fuel Reserve**:
  - `SAFE`: Reserve $\ge 2.0\text{ kg}$
  - `CAUTION`: $0.5\text{ kg} \le \text{Reserve} < 2.0\text{ kg}$
  - `CRITICAL`: Reserve $< 0.5\text{ kg}$
- **Tire Wear Status**:
  - `NORMAL`: Max Wear $< 70\%$
  - `WARNING`: $70\% \le \text{Max Wear} < 85\%$
  - `CRITICAL`: Max Wear $\ge 85\%$
- **Chassis Wear Balance**:
  - `NORMAL`: $|\text{Axle Diff}| \le 10\%$ and $|\text{Lateral Diff}| \le 10\%$
  - `IMBALANCE DETECTED`: Otherwise.
- **Degradation Status**:
  - `NORMAL`: Deg Rate $< 3.5\%/\text{lap}$
  - `HIGH DEGRADATION`: Deg Rate $\ge 3.5\%/\text{lap}$.

---

## 10. Formulas Summary

| Metric | Formula |
|---|---|
| **Fuel Consumed** | $F_{\text{start}} - F_{\text{final}}$ |
| **Avg Fuel Burn Rate** | $\Delta F / N_{\text{laps}}$ |
| **Fuel Reserve Margin** | $F_{\text{final}} - F_{\text{min\_reserve}}$ |
| **Axle Wear Diff** | $\bar{W}_{\text{front}} - \bar{W}_{\text{rear}}$ |
| **Lateral Wear Diff** | $\bar{W}_{\text{left}} - \bar{W}_{\text{right}}$ |
| **Stint Deg Rate** | $(W_{\text{end}} - W_{\text{start}}) / N_{\text{stint\_laps}}$ |
| **Est. Remaining Laps** | $(85.0 - W_{\text{current}}) / \text{DegRate}$ |

---

## 11. Threshold Sources & Assumptions

1. **Max Allowable Tire Wear (85%)**: Reused directly from G.4.5.4 domain constraints.
2. **Min Fuel Reserve (1.0 kg)**: Reused directly from FIA / G.4.5.4 fuel reserve rules.
3. **Alert Thresholds**: Explicitly documented dashboard presentation assumptions.

---

## 12. Future Leakage Prevention

Per-lap and stint analytics consume lap records strictly in forward chronological order up to lap $N$. Cumulative telemetry at lap $i$ depends only on laps $1 \dots i$.

---

## 13. Immutability

Analytics data extraction receives read-only views or deep copies of inputs. Verification tests confirm that `RankingResult`, `RankedStrategy`, `SimulationResult`, and dataframes are identical before and after analytics processing.

---

## 14. Determinism

For any given input strategy, `prepare_fuel_tire_analytics_view_data` produces bitwise-identical output dictionaries without random sampling, dynamic timestamps, or non-deterministic ordering.

---

## 15. Performance

Execution complexity is $\mathcal{O}(\text{laps} + \text{stints})$ for the selected strategy only. Unselected strategies are ignored.

---

## 16. Unit & Integration Tests

A comprehensive suite of 18 focused tests was created in `tests/test_fuel_tire_analytics.py`:
1. `test_fuel_data_extraction_and_consumption`
2. `test_fuel_reserve_and_safety_status`
3. `test_4_corner_tire_wear_preservation_and_averages`
4. `test_axle_and_lateral_wear_balance_and_ratio_zero_division`
5. `test_stint_degradation_rate_calculation`
6. `test_remaining_tire_life_projection`
7. `test_remaining_tire_life_zero_or_negative_deg_handling`
8. `test_tire_wear_alert_status`
9. `test_fuel_alert_status`
10. `test_missing_optional_fields_fallback`
11. `test_unknown_scenario_id_handling`
12. `test_selected_strategy_only_processing`
13. `test_no_reranking_or_simulation_rerun`
14. `test_source_immutability`
15. `test_deterministic_output`
16. `test_no_future_leakage`
17. `test_no_fabricated_telemetry_fields`
18. `test_e2e_fuel_tire_analytics_integration`

---

## 17. E2E Pipeline Integration

E2E pipeline execution verified flawless end-to-end integration:
$$\text{G.4.5.2} \to \text{G.4.5.3} \to \text{G.4.5.4} \to \text{G.4.5.5} \to \text{G.4.6.1} \to \text{G.4.6.2} \to \text{G.4.6.3} \to \text{G.4.6.4} \to \text{G.4.6.5}$$

---

## 18. Separation of Concerns

- **G.4.6.3 Separation**: G.4.6.3 handles multi-strategy comparative trade-offs; G.4.6.5 focuses exclusively on single-strategy micro-telemetry breakdown.
- **G.4.6.4 Separation**: G.4.6.4 provides Gantt stint timelines; G.4.6.5 provides tire degradation rates, corner balance, and remaining tire life projections.

---

## 19. Limitations

- Remaining tire life projection is a linear presentation estimation based on observed stint degradation, not a physics-based dynamic tire wear prediction.

---

## 20. Final Verdict

**GREEN — READY FOR G.4.6.6**
