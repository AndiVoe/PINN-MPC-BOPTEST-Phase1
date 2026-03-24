# Phase-1 Paper Outline: RC-MPC vs PINN-MPC

## 1) Proposed Scope

### Recommended cases for the first article
1. `bestest_hydronic` (core case, lowest risk, already producing stable outputs)
2. `bestest_hydronic_heat_pump` (different plant behavior, strong extension)
3. `singlezone_commercial_hydronic` (optional third case for application realism)

### Cases to postpone for later work
1. `twozone_apartment_hydronic`

Reason: multizone and apartment setups add pipeline complexity and runtime risk before the baseline comparison is fully stabilized.

## 2) Working Title Options

1. Physics-Informed Neural Surrogate vs RC Model in MPC for Building Heating Control: A Reproducible BOPTEST Benchmark
2. When Does a PINN Surrogate Help MPC? Evidence from Hydronic Building Control Cases
3. RC-MPC vs PINN-MPC Under Operational Constraints: A Focused Multi-Case Study

## 3) Core Research Questions

1. Does replacing the RC predictor with a PINN surrogate inside MPC improve comfort-energy performance under identical control settings?
2. How does this replacement affect runtime cost and operational robustness?

## 4) Main Contributions

1. A reproducible framework where only the internal predictor is changed (RC vs PINN), with fixed MPC setup.
2. A focused benchmark on 2 to 3 representative hydronic cases for early publishable evidence.
3. Joint evaluation of comfort, energy, computational overhead, and pipeline stability.

## 5) Paper Structure

1. Introduction
2. Related Work
3. Methods
4. Experimental Design
5. Results
6. Discussion
7. Threats to Validity
8. Conclusion and Future Work

## 6) Section-by-Section Content

### 6.1 Introduction
- Motivate why expressive surrogates do not automatically yield better control.
- Highlight the need for fair, controlled comparison in MPC.
- State the hypothesis and practical relevance.

### 6.2 Related Work
- RC-based MPC for buildings.
- PINN surrogates for thermal dynamics.
- Learning-based control alternatives and safety constraints.
- Position this study as an applied reproducible benchmark.

### 6.3 Methods
- Architecture: same MPC, same constraints/objective, predictor swapped (RC vs PINN).
- PINN training target and physics regularization summary.
- KPI definitions (comfort, energy/cost proxy, peak demand, runtime).
- Analysis upgrade package (no dynamic pricing): horizon sweep, comfort-tightening sweep, objective-form ablation, weight-grid/Pareto analysis, sensitivity statistics, and runtime decomposition.
- Provenance note: these analysis blocks are adapted from Zheng et al. (2024) methodological structure (ablation-centric RC vs learned-model comparison), transferred to this RC-vs-PINN study with tariff terms intentionally excluded at this stage.

### 6.4 Experimental Design
- Case descriptions and rationale.
- Episode protocol (test episodes, horizon, initialization, settings).
- Reproducibility controls (fixed config, resume logic, failure accounting).

### 6.5 Results
- Per-case RC vs PINN KPI comparison.
- Aggregated results across selected cases.
- Runtime and robustness analysis (wall time, retries, failures).

### 6.6 Discussion
- Explain observed performance differences:
  - one-step training vs multi-step rollout behavior,
  - distribution shift,
  - objective-proxy mismatch,
  - optimizer sensitivity.
- Clarify where PINN already helps and where RC remains stronger.

### 6.7 Threats to Validity
- Limited case count.
- Fixed objective weights.
- Environment-specific runtime effects.
- Training dataset representativeness.

### 6.8 Conclusion and Future Work
- Main takeaway for current scope.
- Next steps: longer horizons, richer exogenous features, multi-step training improvements, robust direct-policy variants with safeguards.

## 7) Recommended Figures

1. System architecture diagram: identical MPC with swapped predictor.
2. Time series per episode: zone temperature, comfort bounds, setpoint.
3. KPI bars per case: RC vs PINN.
4. Runtime comparison (episode wall time, solve time).
5. Robustness chart (failures/retries/timeouts).

## 8) Recommended Tables

1. Case summary table (building type, climate, complexity).
2. Main KPI table per case and cross-case average.
3. Runtime and robustness table.

### Current Main KPI Table (4 completed cases)

| Case | RC Comfort (Kh) | PINN Comfort (Kh) | Delta (PINN - RC) | Relative Change | Better |
|---|---:|---:|---:|---:|---|
| bestest_hydronic | 71.1 | 65.6 | -5.6 | -7.9% | PINN |
| bestest_hydronic_heat_pump | 18.9 | 91.1 | +72.2 | +381.9% | RC |
| singlezone_commercial_hydronic | 12.8 | 5.3 | -7.5 | -58.5% | PINN |
| twozone_apartment_hydronic | 190.6 | 105.0 | -85.6 | -44.9% | PINN |

### Current Runtime and Robustness Snapshot

| Case | RC mean wall time (s) | PINN mean wall time (s) | RC mean solve time (ms) | PINN mean solve time (ms) | Completed episodes |
|---|---:|---:|---:|---:|---|
| bestest_hydronic | 26.70 | 430.04 | 2.496 | 604.040 | 3/3 each |
| bestest_hydronic_heat_pump | 35.97 | 506.16 | 3.335 | 706.056 | 3/3 each |
| singlezone_commercial_hydronic | 50.20 | 195.39 | 3.172 | 225.505 | 3/3 each |
| twozone_apartment_hydronic | 72.43 | 421.13 | 3.269 | 506.062 | 3/3 each |

### Cross-Case Summary

| Predictor | Cases included | Mean comfort (Kh) | Mean energy (Wh) | Mean challenge cost (cost_tot) | Mean peak power (W) | Mean wall time (s) |
|---|---:|---:|---:|---:|---:|---:|
| RC | 4 | 73.37 | 1677987.60 | 0.097347 | 32787.62 | 46.33 |
| PINN | 4 | 66.76 | 888679.60 | 0.077169 | 30192.75 | 388.18 |

## 9) Claim Discipline for First Publication

1. Make strong claims only on selected cases.
2. Separate control-performance conclusions from runtime/stability conclusions.
3. Avoid broad superiority claims; state conditional findings.

## 10) Practical Writing Plan

### Immediate manuscript package
1. Methods section draft from the fixed pipeline.
2. Results table template populated with currently completed episodes (24/24 for the 4 main cases).
3. One figure script for RC vs PINN time-series overlay.
4. Discussion focused on why PINN may underperform despite higher model flexibility.

### Suggested narrative arc
1. Fair comparison setup.
2. Empirical findings (comfort, energy, runtime).
3. Interpretation and limits.
4. Clear roadmap for scaling to additional cases.
