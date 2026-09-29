# G.4.6.6 — STRATEGY DETAILS & VALIDATION
## ARCHITECTURE AUDIT

---

## 1. Executive Summary

Phase **G.4.6.6 — Strategy Details & Validation** is the final presentation component of the G.4.6 Strategy Dashboard series. This architecture audit defines the exact scope, data contracts, duplication boundaries, and implementation strategy for G.4.6.6.

The purpose of G.4.6.6 is to provide a single-strategy **Engineering Details & Constraint Audit Inspector**. While previous phases (G.4.6.2–G.4.6.5) focus on high-level ranking, trade-offs, timelines, and micro-analytics curves, G.4.6.6 delivers deep transparency into:
1. Authoritative G.4.5.4 constraint validation violations, soft warnings, and rule compliance breakdowns.
2. Complete scenario configuration and race session parameters (`RaceConfig`, `Scenario` metadata).
3. Authoritative simulation assumptions (pit loss, tire wear limits, fuel thresholds).
4. An interactive lap-by-lap execution audit trace table.

G.4.6.6 is **STRICTLY READ-ONLY PRESENTATION**. It consumes existing outputs from `StrategyDashboardAdapter` and `ValidationResult` without running constraint checks, simulating physics, re-ranking strategies, or executing optimization routines.

---

## 2. Current G.4.6 Architecture

The current G.4.6 dashboard architecture consists of five validated presentation components operating on `StrategyDashboardAdapter`:

```
RankingResult (G.4.5.5) + ValidationResult (G.4.5.4) + SimulationResult (G.4.5.3)
                                  │
                                  ▼
                    StrategyDashboardAdapter (G.4.6.1)
                                  │
      ┌───────────────────────────┼───────────────────────────┬───────────────────────────┐
      ▼                           ▼                           ▼                           ▼
Leaderboard (G.4.6.2)     Comparison (G.4.6.3)        Timeline (G.4.6.4)        Fuel & Tire (G.4.6.5)
- Top-K Ranking Table     - Multi-strategy trade-off   - Gantt stint bars        - 4-wheel wear curves
- Stop & search filter    - Delta line charts          - Pit transitions         - Fuel burn efficiency
- Metric comparison       - Strategic balance          - Sequence timeline       - Axle/lateral balance
                                                                                  - Remaining tire life
```

**Missing Capabilities Addressed by G.4.6.6**:
- Comprehensive inspection of G.4.5.4 hard violations and soft warnings.
- Explicit audit of scenario parameters, race session configuration, and simulation assumptions.
- Granular lap-by-lap telemetry execution audit table with range filtering and highlighting.

---

## 3. Authoritative Validation Contract

G.4.5.4 owns the authoritative validation logic implemented in `code/ml/strategy/validation_result.py` and `constraint_validator.py`.

### A. Directly Available Validation Data
- `ValidationResult`:
  - `scenario_id`: Canonical strategy ID string.
  - `race_id`: Session ID.
  - `valid`: Boolean status flag (`True` = satisfies all hard constraints).
  - `severity`: Overall severity level (`NONE`, `WARNING`, `CRITICAL_VIOLATION`).
  - `violations`: Tuple of sorted `Violation` objects.
  - `warnings`: Tuple of soft warning strings.
  - `checked_constraints_count`: Total evaluated rules count.
  - `validator_version`: Version string.
- `Violation`:
  - `constraint_id`: Unique rule string (e.g., `FUEL_DEPLETED`, `MAX_WEAR_EXCEEDED`).
  - `category`: Functional area (`FUEL`, `TIRE`, `STINT`, `PIT_STOP`, `COMPOUND`, `DISTANCE`, `LAP`, `CONSISTENCY`).
  - `severity`: Rule level (`CRITICAL`, `HIGH`, `MEDIUM`).
  - `message`: Explanatory description.
  - `actual_value`: Empirical simulation value.
  - `expected_value`: Rule boundary threshold.
  - `lap_number`: Optional 1-based lap number where violation occurred.
  - `stint_id`: Optional stint identifier.

### B. Safely Derivable for Presentation
- Compliance pass rate percentage: `(1.0 - (violation_count / checked_constraints_count)) * 100`.
- Category compliance breakdown: Grouping violations and warnings by `category`.
- Affected lap highlighting list: Unique set of `lap_number` attributes extracted from `violations`.

### C. Not Available
- Real-time FIA telemetry stream.
- Dynamic telemetry re-simulations.

### D. Must Not Be Recomputed
- Hard constraint rules must NOT be re-evaluated.
- Violation severities must NOT be modified.
- Soft warnings must NOT be re-filtered or re-classified.

---

## 4. Strategy Detail Contract

The authoritative strategy detail sources exposed via `StrategyDashboardAdapter` consist of:
1. `RankedStrategy` / `OptimizationCandidate`: `scenario_id`, `canonical_key`, `rank`, `total_race_time_sec`, `delta_to_leader_sec`, `pit_stop_count`, `final_fuel_kg`, `avg_final_tire_wear_pct`, `warning_count`.
2. `Scenario`: `starting_compound`, `compound_sequence`, `stints`, `pit_stops`, `number_of_stops`, `number_of_stints`, `generation_method`, `generation_metadata`.
3. `RaceConfig`: `race_id`, `total_laps`, `starting_fuel`, `initial_compound`, `pit_stop_loss_sec`, `max_tire_wear`, `min_stint_laps`.
4. `SimulationResult`: `total_race_time_sec`, `pit_stop_count`, `final_fuel_kg`, `final_tire_wear`, `stint_summary`, `pit_summary`, `lap_records`, `is_feasible`, `warnings`.

---

## 5. Available Data Categorization

| Domain Category | Specific Fields | Source Object | Status |
|---|---|---|---|
| **Identity** | `scenario_id`, `canonical_key`, `rank`, `generation_method` | `RankedStrategy`, `Scenario` | Directly Available |
| **Performance** | `total_race_time_sec`, `delta_to_leader_sec`, `pit_stop_count`, `lap_times` | `RankedStrategy`, `SimulationResult` | Directly Available |
| **Race Config** | `race_id`, `total_laps`, `starting_fuel`, `pit_stop_loss_sec`, `max_tire_wear`, `min_stint_laps` | `RaceConfig`, `Scenario` | Directly Available |
| **Validation** | `valid`, `severity`, `violations`, `warnings`, `checked_constraints_count` | `ValidationResult` | Directly Available |
| **Stints & Pits** | `stint_number`, `compound`, `start_lap`, `end_lap`, `pit_lap`, `duration_sec` | `stint_summary`, `pit_summary` | Directly Available |
| **Lap Telemetry** | `lap_number`, `fuel_kg`, `tire_wear_fl/fr/rl/rr`, `lap_time_sec`, `cum_time_sec` | `lap_records` | Directly Available |

---

## 6. Existing Validation Data

Validation data is produced during G.4.5.4 and formatted into a pandas DataFrame by `StrategyDashboardAdapter.validation_dataframe(scenario_id)`:
- Returns columns: `scenario_id`, `valid`, `severity`, `constraint_id`, `category`, `message`, `actual_value`, `expected_value`, `lap_number`, `stint_id`.
- If no violations exist, returns a 1-row DataFrame summarizing `valid=True`, `severity="NONE"`, and soft warning strings.

---

## 7. Existing Lap Trace Data

Lap trace data is available via `StrategyDashboardAdapter.lap_dataframe(scenario_id)`:
- Returns columns: `lap_number`, `stint_number`, `compound`, `tire_age_laps`, `fuel_kg`, `fuel_consumed_kg`, `tire_wear_fl`, `tire_wear_fr`, `tire_wear_rl`, `tire_wear_rr`, `avg_tire_wear`, `lap_time_sec`, `pit_loss_sec`, `cum_time_sec`.

---

## 8. Duplication Matrix

| Feature | G.4.6.2 | G.4.6.3 | G.4.6.4 | G.4.6.5 | G.4.6.6 Scope |
|---|:---:|:---:|:---:|:---:|:---:|
| Scenario Identity & Rank | ✓ | ✓ | — | — | PARTIAL (Header summary) |
| Multi-Strategy Comparison | — | ✓ | — | — | — (Exclusively G.4.6.3) |
| Stint Gantt Timeline | — | — | ✓ | — | — (Exclusively G.4.6.4) |
| Fuel/Tire Micro-Curves | — | — | — | ✓ | — (Exclusively G.4.6.5) |
| 4-Corner Axle/Lateral Balance | — | — | — | ✓ | — (Exclusively G.4.6.5) |
| Remaining Tire Life Projection | — | — | — | ✓ | — (Exclusively G.4.6.5) |
| **Authoritative Violations List** | — | — | — | — | **UNIQUE (G.4.6.6)** |
| **Rule Compliance Breakdown** | — | — | — | — | **UNIQUE (G.4.6.6)** |
| **Race Session & Config Audit** | — | — | — | — | **UNIQUE (G.4.6.6)** |
| **Simulation Assumptions Audit** | — | — | — | — | **UNIQUE (G.4.6.6)** |
| **Interactive Lap Execution Trace Table** | — | — | — | — | **UNIQUE (G.4.6.6)** |

---

## 9. Unique G.4.6.6 Responsibility

G.4.6.6 provides a **Single-Strategy Engineering Details & Validation Audit Cockpit**. Its unique capabilities are:
1. **Rule Compliance & Validation Audit**: Detailed presentation of hard constraint violations (`Violation` objects), soft warnings, and category-wise rule compliance checks.
2. **Race Session & Scenario Specification Audit**: Deep dive into session parameters (`RaceConfig`, total laps, initial fuel, pit loss penalty) and scenario generation context.
3. **Simulation Assumptions Inspection**: Transparent audit of configured domain boundaries (tire wear limits, minimum stint lengths, fuel burn baseline).
4. **Granular Lap Execution Trace**: Full interactive table of lap-by-lap telemetry for the selected strategy with range filtering and pit/violation lap highlighting.

---

## 10. Proposed UI Structure

The UI for G.4.6.6 will be rendered cleanly within `strategy_dashboard.py`:

```
--------------------------------------------------------------------------------
🔍 STRATEGY DETAILS & VALIDATION AUDIT
Selected Strategy: <scenario_id>
--------------------------------------------------------------------------------

SECTION 1 — VALIDATION & CONSTRAINT AUDIT PANEL
[ Status Badge: VALID / INVALID ]  [ Severity: NONE / WARNING / CRITICAL ]
[ Checked Rules: N ]               [ Rule Pass Rate: 100% ]

- Hard Constraint Violations Table (Constraint ID, Category, Severity, Lap #, Message, Actual vs Expected)
- Soft Warnings & Alert Messages List

--------------------------------------------------------------------------------

SECTION 2 — STRATEGY & RACE CONFIGURATION AUDIT
KPIs:
- Total Laps: 57
- Starting Fuel: 110.0 kg
- Initial Compound: MEDIUM
- Pit Stop Loss Penalty: 22.50 s
- Max Wear Boundary: 85.0 %
- Min Stint Length: 5 Laps

--------------------------------------------------------------------------------

SECTION 3 — SIMULATION ASSUMPTIONS AUDIT
Table / Metrics:
- Fuel Consumption Base Rate: Configured G.4.5.1 model
- Tire Degradation Baseline: Authoritative compound models (SOFT/MEDIUM/HARD)
- Mandatory Compound Change Rule: Enforced (Multi-compound requirement)
- Minimum Fuel Reserve Margin: 1.0 kg (FIA minimum)

--------------------------------------------------------------------------------

SECTION 4 — INTERACTIVE LAP EXECUTION AUDIT TRACE
Controls:
- Filter Lap Range (Slider: Lap 1 to N)
- Highlight Pit Laps Checkbox

Table Columns:
[Lap #] [Stint #] [Compound] [Tire Age] [Fuel (kg)] [FL Wear] [FR Wear] [RL Wear] [RR Wear] [Avg Wear] [Lap Time (s)] [Pit Loss (s)] [Cum Time (s)]
```

---

## 11. Validation Presentation Contract

- Validation status is rendered via Streamlit status cards (`st.success`, `st.warning`, `st.error`).
- Violation fields displayed: `constraint_id`, `category`, `severity`, `lap_number`, `stint_id`, `actual_value`, `expected_value`, `message`.
- No validation rules are re-evaluated. The UI strictly renders the DataFrame generated by `StrategyDashboardAdapter.validation_dataframe(scenario_id)`.

---

## 12. Scenario / Race Configuration Contract

- Parameters read directly from `RaceConfig` and `Scenario` attributes exposed by adapter lookups `self._scenarios.get(scenario_id)`.
- If `Scenario` or `RaceConfig` objects are missing from the adapter initialization, graceful fallbacks pull configuration metrics from `stint_dataframe` and `selected_strategy_dataframe`.

---

## 13. Assumptions Contract

The dashboard presents domain assumptions clearly labeled as **AUTHORITATIVE SIMULATION ASSUMPTIONS**:
- Pit stop time loss penalty = $22.5\text{ s}$ (or `RaceConfig.pit_stop_loss_sec`).
- Max allowable tire wear = $85.0\%$ (or `RaceConfig.max_tire_wear`).
- Minimum stint length = $5\text{ laps}$ (or `RaceConfig.min_stint_laps`).
- Fuel reserve safety baseline = $1.0\text{ kg}$ (FIA regulatory constraint).

---

## 14. Lap Trace Contract

- Lap telemetry records are sourced from `StrategyDashboardAdapter.lap_dataframe(scenario_id)`.
- Features range filtering via `st.slider` for lap ranges `(1, total_laps)`.
- Features conditional highlighting for pit laps (`pit_loss_sec > 0`).

---

## 15. Data Volume & Performance Strategy

- Telemetry trace processing is restricted strictly to the single user-selected strategy (`scenario_id`).
- Pandas operations run in $\mathcal{O}(\text{laps})$ time for the selected strategy ($N \le 70$ laps).
- Memory footprint is negligible ($< 100\text{ KB}$ per view data payload).

---

## 16. Immutability

- `prepare_strategy_details_view_data` and `render_strategy_details` receive read-only references or views.
- Deep-copy equality testing will confirm that `RankingResult`, `ValidationResult`, `SimulationResult`, `Scenario`, and `RaceConfig` remain 100% identical before and after rendering.

---

## 17. Determinism

Given identical `StrategyDashboardAdapter` input objects and `scenario_id`, `prepare_strategy_details_view_data` produces bitwise-identical dictionary outputs without random state or non-deterministic key ordering.

---

## 18. Proposed Tests (Target: 18+ Focused Tests)

A dedicated test suite `tests/test_strategy_details.py` will be created during implementation, covering:
1. `test_validation_status_and_severity_extraction`
2. `test_hard_violation_details_formatting`
3. `test_soft_warnings_formatting`
4. `test_race_config_metadata_extraction`
5. `test_scenario_metadata_extraction`
6. `test_simulation_assumptions_extraction`
7. `test_lap_trace_dataframe_extraction`
8. `test_lap_trace_range_filtering`
9. `test_pit_lap_highlighting_detection`
10. `test_missing_validation_results_fallback`
11. `test_missing_scenario_object_fallback`
12. `test_empty_ranking_result_handling`
13. `test_unknown_scenario_id_handling`
14. `test_selected_strategy_only_processing`
15. `test_source_immutability`
16. `test_deterministic_view_data_generation`
17. `test_no_validation_or_simulation_rerun`
18. `test_e2e_strategy_details_integration`

---

## 19. Explicit Non-Goals

G.4.6.6 MUST NOT implement:
- NO re-validation of constraint rules.
- NO re-simulation of race physics or telemetry generation.
- NO re-ranking or optimization scoring.
- NO Monte Carlo simulation or probabilistic modeling.
- NO Sensitivity analysis.
- NO ML model training or inference.
- NO database queries or API endpoints.
- NO modification of upstream domain modules (G.4.5.1–G.4.6.1).

---

## 20. Risks & Mitigation

| Risk | Mitigation |
|---|---|
| Missing `ValidationResult` in adapter | Provide clean fallback using `RankedStrategy.warning_count` and `valid` flag. |
| Missing `Scenario` object in adapter | Extract configuration metrics from `stint_dataframe` and `selected_strategy_dataframe`. |
| Large lap-record tables causing UI clutter | Provide interactive lap range slider and paginated/compact dataframe views. |
| Overlap with G.4.6.5 micro-analytics | Scope G.4.6.6 strictly to tabular execution trace and rule compliance audits, excluding micro-telemetry curves. |

---

## 21. Recommended Architecture

The recommended architecture adds two pure presentation functions to `code/ml/strategy/strategy_dashboard.py`:
1. `prepare_strategy_details_view_data(adapter: StrategyDashboardAdapter, scenario_id: Optional[str] = None, lap_range: Optional[Tuple[int, int]] = None) -> Dict[str, Any]`
2. `render_strategy_details(adapter: StrategyDashboardAdapter, scenario_id: Optional[str] = None)`

These functions will be exported via `code/ml/strategy/__init__.py` and integrated as the final section of `render_strategy_dashboard_tab`.

---

## 22. Scope Decision

- **G.4.6.2 Overlap**: LOW (Header summary only).
- **G.4.6.3 Overlap**: LOW (No multi-strategy trade-offs).
- **G.4.6.4 Overlap**: LOW (No Gantt stint charts).
- **G.4.6.5 Overlap**: LOW (No 4-wheel wear micro-curves or axle balance ratios).
- **Unique Value**: HIGH (Authoritative constraint violation audit, rule pass rates, session parameter audit, and lap-by-lap execution table).

---

## 23. Implementation Plan (For Implementation Phase)

1. Extend `code/ml/strategy/strategy_dashboard.py` with `prepare_strategy_details_view_data` and `render_strategy_details`.
2. Update `code/ml/strategy/__init__.py` package exports.
3. Create `tests/test_strategy_details.py` with 18+ unit and integration tests.
4. Run complete repository regression suite (`python -m pytest -o pythonpath=code`).
5. Produce `reports/g4_6/G4_6_6_IMPLEMENTATION_REPORT.md`.
6. Output final validation report and lock G.4.6.6 as GREEN.

---

## Final Verdict

**SCOPE CONFIRMED — READY FOR IMPLEMENTATION**
