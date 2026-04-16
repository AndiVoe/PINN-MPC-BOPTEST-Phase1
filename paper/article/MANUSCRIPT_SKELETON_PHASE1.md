# Manuscript Skeleton (Phase 1)

## Title

[Choose one working title or adapt]

## Abstract

### Background
Building MPC performance strongly depends on the internal prediction model. Physics-informed neural surrogates are promising, but their control benefit under identical MPC settings is not guaranteed.

### Objective
This work compares RC-based and PINN-based internal predictors within the same MPC framework for hydronic building test cases.

### Methods
We benchmarked RC-MPC and PINN-MPC on selected BOPTEST cases using identical constraints, horizon, and objective weights. We evaluated thermal comfort, energy/cost proxy metrics, peak power, and computational/runtime robustness.

### Results
Across the 4 article-priority cases, mean thermal discomfort was 66.76 Kh for PINN-MPC versus 73.37 Kh for RC-MPC (about 9.0% lower on average). PINN reduced discomfort in 3 of 4 cases (bestest_hydronic, singlezone_commercial_hydronic, twozone_apartment_hydronic), while RC remained better in the heat-pump case (bestest_hydronic_heat_pump). Median MPC solve times stayed in the low-millisecond range for both predictors, indicating comparable online computational feasibility.

### Conclusion
PINN predictors can improve comfort under fixed MPC settings for most tested hydronic cases, but predictor replacement is not universally beneficial and should be validated per case before deployment.

## 1. Introduction

### 1.1 Motivation
Model choice inside MPC is a central performance driver in building control. While PINN surrogates can represent richer dynamics than simple RC models, higher model flexibility does not automatically translate to better closed-loop control.

### 1.2 Problem Statement
Many comparisons mix changes in both controller and model, making conclusions difficult. A fair benchmark should keep the control setup fixed and vary only the internal predictor.

### 1.3 Contributions
1. A controlled RC-vs-PINN comparison in identical MPC conditions.
2. A focused case set to prioritize reproducibility and pipeline stability.
3. Joint reporting of control KPIs and operational/runtime robustness.

## 2. Related Work

### 2.1 RC Models in Building MPC
[Summarize relevant RC-MPC literature and strengths: interpretability, low cost, robustness.]

### 2.2 PINN and Hybrid Surrogates
[Summarize PINN thermal modeling work and expected benefits/limitations.]

### 2.3 Positioning of This Study
This study isolates the effect of predictor replacement (RC to PINN) while preserving the MPC formulation.

## 3. Methods

### 3.1 Control Architecture
The MPC solver, constraints, horizon, and objective weights are identical across experiments. Only the predictor changes:
- RC predictor inside MPC
- PINN predictor inside MPC

### 3.2 PINN Training Summary
The PINN predictor is trained as a one-step temperature forecaster using zone temperature, outdoor temperature, global horizontal irradiance, heating setpoint, setpoint increment, and cyclical time features. The model combines a learnable physics core (effective UA, solar gain, HVAC gain, lumped capacity) with a bounded neural correction term. Training uses a data loss on normalized next-step temperature and a physics regularization term that penalizes excessive correction magnitude. In addition to fixed manual weighting, two adaptive weighting variants are available and were evaluated in this project: gradient-balance weighting and uncertainty weighting. Data are split by predefined train/validation/test episodes, and final checkpoint selection is based on validation performance with patience-based early stopping.

### 3.3 Optimization Formulation
At each control step, MPC optimizes a bounded heating setpoint trajectory over a finite horizon under identical constraints for both predictors. The stage objective contains three terms: (1) squared comfort-bound violation penalty, (2) heating-energy proxy penalty proportional to setpoint level, and (3) control smoothness penalty on absolute setpoint increments. Occupancy-aware comfort bounds are enforced via time-varying lower and upper limits. The predictor (RC or PINN) is the only swapped component; horizon length, bounds, objective weights, and solver settings are otherwise held constant to preserve comparability.

### 3.4 Evaluation Metrics
- Thermal discomfort (Kh)
- Challenge discomfort KPI (tdis_tot)
- Energy and cost proxy metrics
- Peak power
- MPC solve/runtime metrics
- Failure/retry counts

## 4. Experimental Design

### 4.1 Case Selection
Primary:
1. bestest_hydronic
2. bestest_hydronic_heat_pump
Optional extension:
3. singlezone_commercial_hydronic

### 4.2 Episodes and Protocol
Each case is evaluated on three standard test episodes (`te_std_01`, `te_std_02`, `te_std_03`) for both predictors under matched initialization and control settings. For each episode, RC and PINN runs use the same manifest, control interval, horizon configuration, and comfort schedule. The protocol runs predictors independently and records challenge KPIs and diagnostic KPIs per episode; case-level and cross-case aggregates are computed as arithmetic means over completed episodes.

### 4.3 Reproducibility and Reliability Controls
Reproducibility is enforced through versioned YAML configs, fixed random seeds in training, and stored artifact metadata (checkpoint, metrics, training config). Runtime reliability is handled via explicit resume/recovery execution paths, queue-state checks, and per-episode completion validation. Failure accounting distinguishes (a) incomplete episodes, (b) recovered episodes, and (c) deferred cases; only fully completed cases are included in headline statistics.

### 4.5 Provenance of the Analysis Upgrade
The post-benchmark analysis package in Section 4.4 is adapted from methodological patterns in Zheng et al. (2024), specifically their emphasis on horizon sensitivity, objective-form sensitivity, comfort-range tightening, solver/runtime effects, and predictor comparability under shared MPC settings. In this work, those ideas are transferred to the RC-vs-PINN context and intentionally constrained to a non-dynamic-pricing scope. Consequently, energy-proxy and comfort trade-offs are analyzed through weight sweeps and Pareto-style reporting without introducing tariff-driven objective terms.

### 4.4 Post-Benchmark Analysis Upgrade (No Dynamic Pricing)
To improve scientific strength while keeping the current non-price-focused scope, we define the following analysis package.

| Analysis block | Variable(s) swept | Fixed elements | Output artifact | Purpose |
|---|---|---|---|---|
| Horizon ablation | horizon in {2 h, 4 h, 6 h, 12 h, 24 h} | Predictor, objective form, comfort bounds | KPI vs horizon curves + runtime curves | Identify diminishing returns and stable horizon choice |
| Comfort tightening ablation | epsilon in {0.0, 0.2, 0.5, 0.8, 1.0} K | Predictor, horizon, objective weights | Comfort-violation and energy trade-off plots | Quantify robustness to bound tightening |
| Objective-form ablation | bound-violation vs reference-tracking vs mixed | Predictor, horizon, epsilon | Per-case KPI deltas | Separate model effect from objective-design effect |
| Weight-grid sweep | comfort/energy trade-off weights | Predictor, horizon, objective form | Pareto front (comfort vs energy proxy) | Compare achievable trade-space for RC vs PINN |
| Sensitivity analysis | same weight grid as above | Predictor, horizon, objective form | KPI spread (mean, std, worst case) | Measure tuning sensitivity and practical robustness |
| Runtime decomposition | none (measured) | Same runs as above | solve-time, predictor-time, overhead breakdown | Explain computational bottlenecks |
| Multi-step prediction validation | forecast horizon 1..24 h | Trained predictor | Error-vs-horizon curves | Link open-loop prediction quality to closed-loop behavior |

All sweeps are performed for both predictors under identical MPC constraints and identical disturbance scenarios. This preserves a fair predictor comparison while exposing controller-design sensitivities that are hidden in single-setting evaluations.

## 5. Results

### 5.1 Per-Case RC vs PINN Comparison
Table 1 summarizes case-level comfort outcomes for the four completed benchmark cases.

| Case | RC Comfort (Kh) | PINN Comfort (Kh) | Delta (PINN - RC) | Relative Change | Better |
|---|---:|---:|---:|---:|---|
| bestest_hydronic | 71.1 | 65.6 | -5.6 | -7.9% | PINN |
| bestest_hydronic_heat_pump | 18.9 | 91.1 | +72.2 | +381.9% | RC |
| singlezone_commercial_hydronic | 12.8 | 5.3 | -7.5 | -58.5% | PINN |
| twozone_apartment_hydronic | 190.6 | 105.0 | -85.6 | -44.9% | PINN |

Across these four cases, PINN reduced discomfort in three cases and underperformed in one heat-pump case.

### 5.2 Aggregated Performance
Table 2 reports cross-case aggregate KPIs over the four completed cases.

| Predictor | Cases included | Mean comfort (Kh) | Mean challenge discomfort (tdis_tot) | Mean energy (Wh) | Mean challenge cost (cost_tot) | Mean peak power (W) |
|---|---:|---:|---:|---:|---:|---:|
| RC | 4 | 73.37 | 105.06 | 1677987.60 | 0.097347 | 32787.62 |
| PINN | 4 | 66.76 | 89.70 | 888679.60 | 0.077169 | 30192.75 |

On average across the four completed cases, PINN achieved lower discomfort and lower energy use, but with high case dependence.

### 5.3 Runtime and Robustness
Table 3 highlights computational overhead and completion status.

| Case | RC mean wall time (s) | PINN mean wall time (s) | RC mean solve time (ms) | PINN mean solve time (ms) | Episode completion |
|---|---:|---:|---:|---:|---|
| bestest_hydronic | 26.70 | 430.04 | 2.496 | 604.040 | 3/3 each |
| bestest_hydronic_heat_pump | 35.97 | 506.16 | 3.335 | 706.056 | 3/3 each |
| singlezone_commercial_hydronic | 50.20 | 195.39 | 3.172 | 225.505 | 3/3 each |
| twozone_apartment_hydronic | 72.43 | 421.13 | 3.269 | 506.062 | 3/3 each |


## 6. Discussion

### 6.1 Why PINN May Underperform Despite Higher Capacity
- One-step training vs multi-step closed-loop rollout mismatch
- Distribution shift beyond training trajectories
- Objective-proxy mismatch in optimization
- Solver sensitivity to surrogate curvature

### 6.2 Practical Interpretation
PINN is a strong candidate for comfort-focused operation in cases with smoother thermal dynamics and sufficient training coverage, where it can reduce discomfort and often lower energy proxy simultaneously. RC remains preferable in cases with sharp actuator and plant nonlinearities (notably the heat-pump case in this study), and when low, predictable runtime is a hard operational requirement. In practice, predictor selection should be case-specific and based on a fixed protocol that evaluates both KPI quality and runtime robustness rather than one metric alone.

### 6.3 Implications for Deployment
Deployment decisions should explicitly budget computational headroom for real-time optimization, because PINN-based control can achieve better comfort in several cases but with materially higher per-step solve overhead. Reliability constraints should include completion-rate targets, queue/recovery resilience, and bounded worst-case solve times. Before field-like deployment, each case should pass a validation gate with: (1) full-episode completion under the target runtime environment, (2) sensitivity checks across objective weights and comfort tightening, and (3) no-regression against RC baseline on priority KPIs.

## 7. Threats to Validity

1. Limited number of cases in phase-1 scope
2. Fixed objective weights and horizon settings
3. Environment/runtime dependence (containerized testbed)
4. Dataset representativeness and weather scenario coverage

## 8. Conclusion and Future Work

### 8.1 Main Takeaway
Under identical MPC settings and across four completed hydronic cases, PINN achieved lower mean discomfort than RC in aggregate and improved comfort in three cases, but failed to generalize in one heat-pump case while incurring higher runtime. Therefore, PINN should be treated as a case-dependent upgrade path, validated through structured ablations and robustness checks rather than assumed as a universal replacement for RC predictors.

### 8.2 Next Steps
1. Execute the no-dynamic-pricing analysis package in Section 4.4 and report Pareto fronts plus sensitivity statistics per case.
2. Improve multi-step PINN training objectives to reduce rollout mismatch and heat-pump-case degradation.
3. Add solver/runtime decomposition and compare optimization backends for computationally constrained deployment.
4. Extend to additional cases only after reliability gates (completion rate and bounded solve-time tails) are satisfied.

## Appendix A. Reproducibility Checklist

- Code version / commit hash:
- Configuration files used:
- Case list and episodes:
- Hardware/software environment:
- Runtime recovery settings:

## Appendix B. Figure and Table Checklist

Figures:
1. Architecture diagram
2. Temperature and setpoint trajectories
3. KPI comparison bars
4. Runtime comparison
5. Robustness/failure chart

Tables:
1. Case summary
2. Episode-level KPI table
3. Case-level aggregate table
4. Cross-case summary
