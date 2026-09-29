# Strategy Intelligence Package (G.4.5)
## Data Foundation (G.4.5.1), Scenario Builder (G.4.5.2), Validator (G.4.5.4) & Optimizer (G.4.5.5)

The `code/ml/strategy` package provides a deterministic, high-performance simulation foundation, scenario generation engine, constraint validator, and strategy optimization ranking engine for Formula 1 race engineering strategy analysis.

---

## 1. Real Data vs Simulation Assumptions vs Generation & Ranking Policies

| Domain | Attribute | Nature | Description |
| :--- | :--- | :--- | :--- |
| **Telemetry** | Speed, RPM, Lap Progress | **REAL DATA** | Ingested via Kafka / Bronze / Silver / Gold streaming layers. |
| **Pit Stops** | `22.5s` Pit Stop Time Loss | **SIMULATION ASSUMPTION** | Configurable stationary and pit lane delta time loss per pit stop. |
| **Compounds** | SOFT, MEDIUM, HARD Multipliers | **SIMULATION ASSUMPTION** | Wear factors (`1.4`, `1.0`, `0.7`) derived from physics model specifications. |
| **Fuel Burn** | `2.0 kg/lap` Burn Rate | **SIMULATION ASSUMPTION** | Linear fuel depletion model per lap. |
| **Dry Rule** | `require_distinct_dry_compounds` | **GENERATION POLICY** | Configurable policy requiring $\ge 2$ distinct dry compounds in dry sessions. |
| **Weather** | `DRY`, `WET`, `MIXED` | **GENERATION POLICY** | Compound compatibility mapping (`SOFT/MEDIUM/HARD` vs `INTER/WET`). |
| **Search Space**| Bounded Grid Step (`1`, `2`, `5`) | **GENERATION POLICY** | Pit lap candidate grid step policy capping scenario explosion. |
| **Hard Filter**| `validation_result.valid is True` | **RANKING POLICY** | Hard constraint validator exclusion gate for ranking candidates. |
| **Ranking Key**| 6-Tier Lexicographic Key | **RANKING POLICY** | `total_race_time_sec ASC` -> `pit_stop_count ASC` -> `final_fuel_kg DESC` -> `avg_final_tire_wear_pct ASC` -> `canonical_key ASC` -> `scenario_id ASC`. |

---

## 2. Package Architecture

```
code/ml/strategy/
├── __init__.py                  # Public exports (G.4.5.1 + G.4.5.2 + G.4.5.4 + G.4.5.5)
├── config.py                    # Constants & compound properties
├── compounds.py                 # Compound enum & properties model
├── race_config.py               # Race parameters & physical constraint config
├── stint.py                     # Stint model & sequence validation
├── pit_stop.py                  # Pit stop model & transition validator
├── fuel_model.py                # Fuel depletion state machine
├── strategy_state.py            # Strategy state & V1 Telemetry serializer
├── simulator.py                 # Deterministic strategy simulator engine
├── validation.py                # Foundation validators
├── scenario.py                  # [G.4.5.2] Scenario model & G.4.5.1 simulator adapter
├── scenario_id.py               # [G.4.5.2] Canonical key & SHA-256 ID generator
├── scenario_deduplication.py    # [G.4.5.2] O(1) scenario deduplication engine
├── scenario_constraints.py      # [G.4.5.2] Hard constraint engine & weather rules
├── scenario_generator.py        # [G.4.5.2] Bounded candidate scenario generator
├── scenario_serializer.py       # [G.4.5.2] JSON / Parquet dataset exporters
├── validation_result.py         # [G.4.5.4] Immutable ValidationResult & Violation schemas
├── constraint_checks.py         # [G.4.5.4] O(N) modular constraint checker functions
├── constraint_validator.py      # [G.4.5.4] Deterministic ConstraintValidator engine
├── ranking_config.py            # [G.4.5.5] OptimizationConfig dataclass
├── ranking_candidate.py         # [G.4.5.5] OptimizationCandidate & RankedStrategy dataclasses
├── ranking_result.py            # [G.4.5.5] Immutable RankingResult container
├── strategy_optimizer.py        # [G.4.5.5] Deterministic StrategyOptimizer engine
└── README.md                    # Module documentation
```

---

## 3. End-to-End Quick Start Example (G.4.5.2 -> G.4.5.3 -> G.4.5.4 -> G.4.5.5)

```python
from ml.strategy import (
    RaceConfig, ScenarioConstraints, ScenarioGenerator,
    StrategySimulator, ConstraintValidator, OptimizationConfig, StrategyOptimizer
)

# 1. Configure 50-lap race scenario
race_config = RaceConfig(race_id="RACE_MONZA_50", total_laps=50, starting_fuel=100.0)

# 2. Generate candidate scenarios
constraints = ScenarioConstraints(max_stops=2, min_stint_laps=3, weather_mode="DRY")
generator = ScenarioGenerator(race_config, constraints)
gen_result = generator.generate_scenarios()

# 3. Simulate & validate all candidate scenarios
simulator = StrategySimulator(race_config)
validator = ConstraintValidator(race_config)

candidate_pairs = []
for scenario in gen_result.scenarios:
    stints, pit_stops, _ = scenario.to_g451_payload()
    sim_result = simulator.simulate_strategy(stints, pit_stops)
    val_result = validator.validate(sim_result, scenario.scenario_id)
    candidate_pairs.append((sim_result, val_result, scenario))

# 4. Filter and Rank Top 5 Strategies via G.4.5.5 StrategyOptimizer
optimizer = StrategyOptimizer(OptimizationConfig(top_k=5))
ranking_result = optimizer.optimize(candidate_pairs)

print(f"Total Candidates: {ranking_result.total_candidates}")
print(f"Valid Ranked: {ranking_result.valid_candidates}")
print(f"Leader Scenario ID: {ranking_result.leader_scenario_id}")

for strat in ranking_result.ranked_strategies:
    print(f"Rank {strat.rank}: {strat.scenario_id} | Time: {strat.total_race_time_sec:.2f}s | Delta: +{strat.delta_to_leader_sec:.2f}s")
```

---

## 4. Determinism & Canonical Representation

- **Canonical Key Format**: `COMPOUND_1:START_1-END_1|COMPOUND_2:START_2-END_2` (e.g. `SOFT:1-20|MEDIUM:21-50`).
- **Deterministic ID**: `SCN_<SHA256(race_id + "::" + canonical_key)[:12]>`.
- **Lexicographic Ranking Key**:
  1. `total_race_time_sec ASC`
  2. `pit_stop_count ASC`
  3. `final_fuel_kg DESC`
  4. `avg_final_tire_wear_pct ASC`
  5. `canonical_key ASC`
  6. `scenario_id ASC`
- **Reproducibility**: Identical simulation and validation inputs produce 100% byte-for-byte identical strategy ranking results across all execution runs.

