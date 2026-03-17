# Article Outline: European BOPTEST RC vs PINN Benchmark

## Working Title

Physics-Informed Neural Surrogates versus Reduced-Order RC Models for European BOPTEST Building Control Benchmarks

## Abstract (Draft Structure)

1. Context: why surrogate modeling is needed for MPC in buildings.
2. Gap: limited standardized cross-case comparison between RC and PINN on European testbeds.
3. Method: per-testcase PINN vs three pure RC candidates, staged 7-day and 30-day protocol.
4. Results: comfort, energy/cost, and computational tradeoffs.
5. Impact: guidance on model selection for deployable MPC workflows.

## 1. Introduction

1. Motivation for fast and reliable predictive models in building control.
2. Role of BOPTEST as reproducible benchmark environment.
3. Contributions of this study.

## 2. Methods

### 2.1 Benchmark Scope and Case Selection

1. European-only testcase inclusion rule.
2. Final testcase list and climate/building characteristics.
3. Exclusion criteria (non-European and under-development cases).

### 2.2 Model Families Under Comparison

1. PINN model: one model trained per testcase.
2. RC models: pure-physics candidates only (R3C2, R4C3, R5C3).
3. Explicit exclusion of hybrid RC-neural from baseline set.

### 2.3 Data Generation and Splitting

1. BOPTEST scenario selection and episode construction.
2. Training/validation/test splits per testcase.
3. Feature/target definitions and normalization.

### 2.4 Training and Calibration

1. PINN training objective (data + physics regularization).
2. RC parameter estimation procedure.
3. Hyperparameter policy and reproducibility controls (seeding, config snapshots).

### 2.5 MPC Experiment Protocol

1. Shared controller setup across models.
2. Predictor swap only (RC candidate or PINN).
3. Stage 1: 7-day screen for all 3 RC candidates + PINN.
4. Stage 2: 30-day final run for best RC + PINN.

### 2.6 Metrics and Ranking

1. Primary KPIs: cost_tot, tdis_tot, idis_tot, solve_time.
2. Secondary diagnostics: local discomfort measures and parity flags.
3. Weighted RC model selection rule and sensitivity note.

### 2.7 Comparability and Integrity Checks

1. Pairwise comparability constraints (testcase, split, start, dt, horizon).
2. Discomfort parity analysis between challenge and local diagnostic definitions.
3. Publication bundle generation with file index and SHA256 checksums.

## 3. Results

1. Stage-1 screening results by testcase and RC candidate.
2. Selected RC architecture distribution across testcases.
3. Stage-2 long-horizon RC vs PINN comparison.
4. Runtime-performance vs control-quality tradeoff plots.

## 4. Discussion

1. Where PINN provides clear value over RC.
2. Cases where RC remains competitive.
3. Interpretation of challenge-vs-local discomfort divergences.
4. Threats to validity and generalization limits.

## 5. Conclusion

1. Main findings and practical recommendations.
2. Suggested deployment pathway for MPC practitioners.
3. Future work: multi-objective robust MPC and broader testcase expansion.

## Appendix Plan

1. Full testcase metadata table.
2. Hyperparameter tables for PINN and RC calibration.
3. Extended per-episode KPI tables.
4. Reproducibility artifacts index and checksum manifest references.
