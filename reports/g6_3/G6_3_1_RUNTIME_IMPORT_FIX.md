# G.6.3.1 Streamlit Runtime Import Fix

## 1. Observed Error
- **Error Message**: `Error loading strategy engine: No module named 'ml'` followed by `No strategy optimization payload available.`
- **Context**: Occurred during execution of `streamlit run code/partie3/analytics_dashboard.py`. Streamlit set `sys.path[0]` to `code/partie3`, leaving `code/` off Python's module search path when executed directly outside pytest.

## 2. Root Cause
1. **Module Import Path Mismatch**: `analytics_dashboard.py` imported strategy engine modules using `from ml.strategy import ...`. When executed via Streamlit CLI (`streamlit run code/partie3/analytics_dashboard.py`), Streamlit set the script's directory (`code/partie3`) as `sys.path[0]`, causing Python to fail to locate top-level package `ml` located in `code/ml`.
2. **Pytest Masking**: Test files in `tests/` explicitly added `code/` to `sys.path`, masking the missing `sys.path` initialization when executing `analytics_dashboard.py` directly under Streamlit.
3. **Initialization Fallback**: `get_strategy_adapter()` caught the `ModuleNotFoundError` and returned `None`, displaying `No strategy optimization payload available.` on the dashboard UI.

## 3. Fix Applied
1. **`code/partie3/analytics_dashboard.py`**:
   - Added explicit `sys.path` initialization at top of file resolving `CODE_DIR` (`.../code`) and `PROJECT_ROOT` (`.../F1_Data_Project`), ensuring Streamlit runtime always locates `ml` and `ml.strategy` regardless of invocation directory.
   - Refined `get_strategy_adapter()` to instantiate `OptimizationCandidate` objects and optimize them through `StrategyOptimizer` and `StrategyDashboardAdapter`.
2. **`tests/test_dashboard_import_runtime.py`**:
   - Created a dedicated regression test (`test_streamlit_runtime_import_resolution`) that explicitly simulates Streamlit execution context (setting `sys.path[0]` to `code/partie3`) to guarantee `ml.strategy` and `StrategyDashboardAdapter` load and initialize cleanly.

## 4. Why the Previous Tests Did Not Catch It
Automated test scripts in `tests/` explicitly inserted `code/` into `sys.path` at the top of every test file before importing modules. As a result, running `pytest` directly loaded `ml.strategy` seamlessly, hiding the runtime execution behavior of Streamlit CLI (`streamlit run ...`).

## 5. Data Integrity Verification
- Verified that `OptimizationCandidate`, `StrategyOptimizer`, and `StrategyDashboardAdapter` construct exact immutable `RankingResult` objects.
- Preserved all numerical outputs (`scenario_id`, `rank`, `total_race_time_sec`, `delta_to_leader_sec`, `pit_stop_count`, `final_fuel_kg`, `avg_final_tire_wear_pct`, `warning_count`, `validation status`).

## 6. Regression Tests
- Added `tests/test_dashboard_import_runtime.py` (Passed).
- Verified full non-regression baseline across test suite.

## 7. Manual Streamlit Validation
- Launched `streamlit run code/partie3/analytics_dashboard.py`.
- Verified UI loaded without red error banners.
- Verified `RACE STRATEGY ENGINEERING` tab renders populated strategy leaderboard, trade-off scatter plots, stint Gantt timeline, 4-corner tire breakdown, and validation details.

## 8. Files Modified / Created
- **Created**: `tests/test_dashboard_import_runtime.py`
- **Created**: `reports/g6_3/G6_3_1_RUNTIME_IMPORT_FIX.md`
- **Modified**: `code/partie3/analytics_dashboard.py`

## 9. Final Status
**GREEN** — The Streamlit runtime import issue is fixed, verified, and protected by dedicated regression tests.
