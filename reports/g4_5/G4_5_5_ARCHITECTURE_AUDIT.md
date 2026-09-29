# G.4.5.5 — OPTIMIZATION / RANKING
## PRE-IMPLEMENTATION ARCHITECTURE & FEASIBILITY AUDIT

**Project:** F1 Digital Twin — Race Engineering Platform  
**Target Module:** Phase G.4.5.5 — Optimization / Ranking  
**Audit Date:** September 2026  
**Status:** ARCHITECTURE AUDIT ONLY (Zero Code / Test Implementation Executed)

---

## 1. EXECUTIVE SUMMARY

This pre-implementation architecture audit establishes the technical design, data contracts, algorithm selection, tie-breaking policies, computational scalability, and test strategy for **Phase G.4.5.5 (Optimization / Ranking)** in the F1 Digital Twin strategy engine.

### Final Verdict: `GREEN — READY FOR IMPLEMENTATION`

The design leverages the validated outputs of Phase G.4.5.1 (Data Foundation), Phase G.4.5.2 (Scenario Builder), Phase G.4.5.3 (Race Pace Simulator), and Phase G.4.5.4 (Constraint Validator). G.4.5.5 strictly operates downstream of G.4.5.4 as an $O(M \log M)$ deterministic lexicographic multi-objective ranking layer without recomputing simulation physics or invalidating constraint ownership.

---

## 2. EXISTING ARCHITECTURE INSPECTION

Direct code inspection of [`code/ml/strategy/`](file:///c:/Users/Hamza/OneDrive/Desktop/F1_Data_Project/code/ml/strategy/) identified the exact existing structures:

```
G.4.5.1 Data Foundation (RaceConfig, Stint, PitStop, FuelModel, StrategySimulator)
        ↓
G.4.5.2 Scenario Builder (Scenario, ScenarioConstraints, ScenarioGenerator)
        ↓
G.4.5.3 Race Pace Simulator (StrategySimulator -> SimulationResult)
        ↓
G.4.5.4 Constraint Validator (ConstraintValidator -> ValidationResult)
        ↓
G.4.5.5 Optimization / Ranking (StrategyOptimizer -> RankingResult)
```

### Exact Reusable Structs & Field Schemas:
- **`Scenario`** ([`code/ml/strategy/scenario.py`](file:///c:/Users/Hamza/OneDrive/Desktop/F1_Data_Project/code/ml/strategy/scenario.py)): `scenario_id: str`, `race_id: str`, `total_laps: int`, `starting_compound: str`, `compound_sequence: List[str]`, `stints: List[Stint]`, `pit_stops: List[PitStop]`, `canonical_key: str`.
- **`SimulationResult`** ([`code/ml/strategy/simulator.py`](file:///c:/Users/Hamza/OneDrive/Desktop/F1_Data_Project/code/ml/strategy/simulator.py)): `race_id: str`, `total_laps: int`, `total_race_time_sec: float`, `pit_stop_count: int`, `total_pit_time_sec: float`, `final_fuel_kg: float`, `total_fuel_consumed_kg: float`, `final_tire_wear: Dict[str, float]`, `stint_summary: List[Dict]`, `pit_summary: List[Dict]`, `lap_records: List[Dict]`, `is_feasible: bool`, `warnings: List[str]`.
- **`ValidationResult`** ([`code/ml/strategy/validation_result.py`](file:///c:/Users/Hamza/OneDrive/Desktop/F1_Data_Project/code/ml/strategy/validation_result.py)): `scenario_id: str`, `race_id: str`, `valid: bool`, `severity: str`, `violations: Tuple[Violation, ...]`, `warnings: Tuple[str, ...]`, `checked_constraints_count: int`.
- **`Violation`** ([`code/ml/strategy/validation_result.py`](file:///c:/Users/Hamza/OneDrive/Desktop/F1_Data_Project/code/ml/strategy/validation_result.py)): `constraint_id: str`, `category: str`, `severity: str`, `message: str`, `actual_value: Any`, `expected_value: Any`, `lap_number: Optional[int]`.

G.4.5.5 consumes these objects directly and **DOES NOT** reimplement simulation, lap time prediction, tire wear models, fuel depletion, or constraint validation.

---

## 3. INPUT CONTRACT

G.4.5.5 consumes lightweight `OptimizationCandidate` representations built from G.4.5.2, G.4.5.3, and G.4.5.4 outputs:

```python
@dataclass(frozen=True)
class OptimizationCandidate:
    scenario_id: str
    race_id: str
    canonical_key: str
    total_race_time_sec: float        # from SimulationResult
    pit_stop_count: int               # from SimulationResult
    final_fuel_kg: float              # from SimulationResult
    avg_final_tire_wear_pct: float    # mean(SimulationResult.final_tire_wear.values())
    valid: bool                       # from ValidationResult.valid
    warning_count: int                # len(ValidationResult.warnings)
    stint_count: int                  # len(SimulationResult.stint_summary)
    simulation_result: Optional[SimulationResult] = None
    validation_result: Optional[ValidationResult] = None
```

### Survival Requirements:
- **For Ranking:** `valid`, `total_race_time_sec`, `pit_stop_count`, `final_fuel_kg`, `avg_final_tire_wear_pct`, `canonical_key`.
- **For Tie-Breaking:** `canonical_key`, `scenario_id`.
- **For Auditability:** `warning_count`, `stint_count`, `simulation_result`, `validation_result`.

---

## 4. HARD FILTERING

### Ownership & Filtering Rules:
1. **Ownership:** G.4.5.4 (`ConstraintValidator`) is the **sole, authoritative validator** of strategy constraints. G.4.5.5 does NOT reinterpret hard constraint rules.
2. **Filtering Logic:**
   - `IF validation_result.valid == False` $\implies$ Candidate is **EXCLUDED** from entering ranking.
   - `IF validation_result.valid == True` $\implies$ Candidate enters the ranking pool.
3. **Soft Warnings:** Candidates with `valid == True` containing warnings (`len(warnings) > 0`) **MUST NOT** be excluded from ranking.

---

## 5. PRIMARY OBJECTIVE

- **Primary Optimization Objective:** **MINIMIZE TOTAL RACE TIME** (`total_race_time_sec`).
- **Mathematical Definition:**
  $$\text{total\_race\_time\_sec} = \sum_{t=1}^{N_{\text{laps}}} \text{lap\_time\_sec}(t) + \sum_{k=1}^{N_{\text{stops}}} \text{pit\_stop\_duration\_sec}(k)$$
- **Source:** Consumes `SimulationResult.total_race_time_sec` produced by G.4.5.3 without recomputing.

---

## 6. SECONDARY OBJECTIVES

Secondary physical criteria evaluated when primary race times are identical or within specified tolerances:

1. **Pit Stop Count (`pit_stop_count`):** Fewer pit stops reduce pit lane collision/traffic risk.
2. **Final Fuel Margin (`final_fuel_kg`):** Higher remaining fuel mass provides safety against unexpected Safety Cars or lift-and-coast requirements.
3. **Final Tire Wear (`avg_final_tire_wear_pct`):** Lower average tire wear at the checkered flag reduces puncture risk.

---

## 7. RANKING STRATEGY (ARCHITECTURE SELECTION & JUSTIFICATION)

### Evaluated Alternatives:
- **Option A: Lexicographic Multi-Objective Ranking** (Selected)
- **Option B: Weighted Composite Score** ($S = w_1 T + w_2 P + w_3 W$)
- **Option C: Pareto Frontier Ranking**

### Technical Justification for Lexicographic Ranking (Option A):
1. **100% Deterministic & Reproducible:** Eliminates arbitrary weighting coefficients ($w_1, w_2$) that distort physical units (seconds vs. kg vs. %).
2. **Pure Physical Interpretability:** Race outcome in Formula 1 is strictly determined by track position and total time. Ties are resolved using clear physical fallbacks (pit count, fuel margin, tire wear).
3. **Dashboard Clarity:** Race engineers can easily understand why Strategy A ranks above Strategy B without needing to decipher synthetic mathematical scores.

---

## 8. TIE-BREAKING RULES

To guarantee 100% bit-for-bit deterministic ranking across runs, ties are broken using the following strict priority sequence:

1. `total_race_time_sec` **ASCENDING** (Primary)
2. `pit_stop_count` **ASCENDING** (Secondary)
3. `final_fuel_kg` **DESCENDING** (Tertiary)
4. `avg_final_tire_wear_pct` **ASCENDING** (Quaternary)
5. `canonical_key` **ASCENDING** (Alphabetical tie-breaker — e.g. `HARD:1-50` < `MEDIUM:1-50`)
6. `scenario_id` **ASCENDING** (Final deterministic fallback)

---

## 9. TOP-K STRATEGY

- **Configurable K:** `top_k: int = 10` (supports Top-1, Top-5, Top-10, or custom $K$).
- **Algorithm Choice:**
  - For $M \le 100,000$ candidates: Standard full sort ($O(M \log M)$ via Python's Timsort).
  - For $M > 100,000$ candidates: Min-heap selection via `heapq.nsmallest` ($O(M \log K)$).
- **Boundary Behavior:** If valid candidate count $M < K$, returns all $M$ valid strategies without error.
- **Uniqueness:** Guaranteed zero duplicate `scenario_id`s in Top-K output.

---

## 10. LARGE DATASET STRATEGY & COMPLEXITY

G.4.5.5 is designed to scale across large search spaces generated by G.4.5.2:

- **Time Complexity:** $O(M \log M)$ for candidate sorting, where $M$ is the count of valid candidates ($M \le N_{\text{generated}}$).
- **Space Complexity:** $O(M)$ for lightweight `OptimizationCandidate` objects.
- **Memory Optimization:** Heavy telemetry arrays (`lap_records`) are detached during initial candidate sorting and re-attached only for Top-K results.

---

## 11. DEDUPLICATION POLICY

- G.4.5.2 `ScenarioGenerator` already guarantees unique `scenario_id`s using SHA-256 hashes of canonical keys.
- G.4.5.5 enforces $O(1)$ set checking on `scenario_id` during candidate ingestion. Any duplicate `scenario_id` is rejected cleanly as `DUPLICATE_CANDIDATE`.

---

## 12. INVALID / EMPTY INPUT HANDLING

- **Zero Candidates Input:** Returns `RankingResult` with empty `ranked_strategies` list and `status = "EMPTY_INPUT"`.
- **All Candidates Invalid:** Returns `RankingResult` with empty `ranked_strategies` list and `status = "ALL_CANDIDATES_INVALID"`.
- **$K > M$ Valid Candidates:** Returns available $M$ ranked strategies cleanly.
- **Malformed / NaN / Inf Objective Fields:** Filtered out as invalid during G.4.5.4 or caught before sorting, triggering `INVALID_OBJECTIVE_VALUE` alert.

---

## 13. DETERMINISM & REPRODUCIBILITY

$$\text{Same Candidates Pool } C + \text{Same OptimizationConfig } O \implies \text{Identical RankingResult } R$$

- No dependence on object memory addresses, unseeded random calls, dictionary iteration order, or system clock timestamps in equality fields.

---

## 14. IMMUTABILITY & READ-ONLY GUARANTEE

G.4.5.5 is strictly **READ-ONLY**:
- Does not mutate `Scenario`, `SimulationResult`, or `ValidationResult`.
- Produces frozen `RankedStrategy` and `RankingResult` output objects.

---

## 15. AUDITABILITY & RANKING EXPLANATION

Every `RankedStrategy` includes an explicit explanation payload:

```python
@dataclass(frozen=True)
class RankedStrategy:
    rank: int                             # 1-based rank (1 = Winner)
    scenario_id: str
    canonical_key: str
    total_race_time_sec: float
    delta_to_leader_sec: float            # time - rank_1.time (0.0s for Rank 1)
    pit_stop_count: int
    final_fuel_kg: float
    avg_final_tire_wear_pct: float
    warning_count: int
    ranking_explanation: str              # e.g., "Rank 2: +4.250s behind leader | 1 stop | 12.4kg fuel margin"
    candidate: OptimizationCandidate
```

---

## 16. REPRODUCIBILITY & CONFIGURATION SCHEMA

G.4.5.5 configuration is managed via `OptimizationConfig`:

```python
@dataclass(frozen=True)
class OptimizationConfig:
    top_k: int = 10
    primary_objective: str = "total_race_time_sec"
    secondary_objectives: Tuple[str, ...] = ("pit_stop_count", "final_fuel_kg", "avg_final_tire_wear_pct")
    require_valid_candidate: bool = True
    config_version: str = "1.0.0"
```

---

## 17. COMPLEXITY ANALYSIS

- **Filtering Complexity:** $O(N)$ pass over $N$ total candidates.
- **Ranking Complexity:** $O(M \log M)$ over $M$ valid candidates.
- **Top-K Extraction:** $O(K)$ slice.
- **Total Time Complexity:** $O(N + M \log M) \approx O(N \log N)$.

---

## 18. PERFORMANCE TARGETS

Target execution benchmarks for G.4.5.5 (excluding simulation runtime):

| Candidate Scale | Target Execution Time | Throughput Target |
| :--- | :--- | :--- |
| **1,000 Candidates** | $< 0.1\text{ ms}$ | $> 10,000\text{ candidates/sec}$ |
| **10,000 Candidates** | $< 1.5\text{ ms}$ | $> 6,600\text{ candidates/sec}$ |
| **100,000 Candidates** | $< 20.0\text{ ms}$ | $> 5,000\text{ candidates/sec}$ |
| **1,000,000 Candidates** | $< 250.0\text{ ms}$ | $> 4,000\text{ candidates/sec}$ |

---

## 19. PROPOSED MODULE ARCHITECTURE

Proposed modular structure for implementation under `code/ml/strategy/`:

```
code/ml/strategy/
├── ranking_config.py      # [G.4.5.5] OptimizationConfig dataclass
├── ranking_candidate.py   # [G.4.5.5] OptimizationCandidate & RankedStrategy dataclasses
├── ranking_result.py      # [G.4.5.5] RankingResult container & serializer
└── strategy_optimizer.py  # [G.4.5.5] StrategyOptimizer engine class
```

---

## 20. TEST STRATEGY (21 PLANNED TEST CATEGORIES)

1. `test_empty_candidate_input`
2. `test_single_candidate_ranking`
3. `test_all_valid_candidates_ranking`
4. `test_all_invalid_candidates_rejection`
5. `test_mixed_valid_invalid_filtering`
6. `test_soft_warnings_retained_in_ranking`
7. `test_race_time_primary_ascending_order`
8. `test_pit_stop_secondary_tie_breaker`
9. `test_fuel_margin_tertiary_tie_breaker`
10. `test_tire_wear_quaternary_tie_breaker`
11. `test_canonical_key_final_alphabetical_tie_breaker`
12. `test_top_k_limiting`
13. `test_k_greater_than_candidate_count`
14. `test_duplicate_scenario_id_rejection`
15. `test_nan_race_time_handling`
16. `test_inf_race_time_handling`
17. `test_read_only_input_immutability`
18. `test_deterministic_ranking_replay_5x`
19. `test_large_candidate_space_10k_benchmark`
20. `test_g452_g453_g454_g455_e2e_integration`
21. `test_delta_to_leader_calculation`

---

## 21. REGRESSION SAFETY

The design preserves all previous phase green statuses:
- G.4.1 Feature Engineering: **GREEN**
- G.4.2 Anomaly Detection: **GREEN**
- G.4.3 Lap Time Prediction: **GREEN**
- G.4.4 Tire Degradation: **GREEN**
- G.4.5.1 Strategy Foundation: **GREEN**
- G.4.5.2 Scenario Builder: **GREEN**
- G.4.5.3 Race Pace Simulator: **GREEN**
- G.4.5.4 Constraint Validator: **GREEN**

Zero modifications to existing production code or test files.

---

## 22. SCOPE BOUNDARIES

G.4.5.5 contains **NO**:
- ML model training or re-training.
- Telemetry ingestion / streaming code (Kafka / Spark / MinIO).
- Physical simulation code (fuel burn, tire wear, lap times).
- Constraint definition or validation logic.
- Web UI / Dashboard API rendering.

---

## 23. PLANTUML ARCHITECTURE PROPOSAL

PlantUML diagram saved to:  
[`reports/g4_5/g4_5_5_optimization_ranking_architecture.puml`](file:///c:/Users/Hamza/OneDrive/Desktop/F1_Data_Project/reports/g4_5/g4_5_5_optimization_ranking_architecture.puml)

---

## 24. RISKS / OPEN QUESTIONS

- **Risk 1: Identical Performance Strategies:** In large scenario pools, two distinct strategies may yield identical total race times down to $0.001\text{s}$.  
  *Mitigation:* The 6-tier lexicographic sorting hierarchy (including `canonical_key` and `scenario_id` tie-breakers) guarantees 100% deterministic tie resolution.
- **Risk 2: Memory Footprint for $M > 100,000$ Candidates:** Storing full `SimulationResult` objects in memory for 100,000 strategies can consume $> 500\text{ MB}$.  
  *Mitigation:* `OptimizationCandidate` stores lightweight primitive scalars for sorting, detaching heavy `lap_records` arrays until Top-K extraction.

---

## 25. FINAL VERDICT

```
==============================================================================
FINAL AUDIT VERDICT: GREEN — READY FOR IMPLEMENTATION
==============================================================================
- Upstream Pipeline Integration: Clean consumption of G.4.5.2, G.4.5.3, G.4.5.4
- Hard Filtering Ownership: Strictly enforced via ValidationResult.valid
- Ranking Strategy: Deterministic Lexicographic Multi-Objective (Race Time Primary)
- Tie-Breaking: 6-tier hierarchy guaranteeing 100% bit-for-bit reproducibility
- Performance Complexity: O(M log M) scaling smoothly to 100,000+ candidates
- Immutability & Read-Only: Guaranteed side-effect-free execution
- Test Strategy: 21 comprehensive test categories defined
==============================================================================
```
