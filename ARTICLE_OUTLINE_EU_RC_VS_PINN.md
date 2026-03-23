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

### 2.2.1 RC Baseline Used in the MPC Runs (Implementation-Exact)

For the closed-loop benchmark runs in this repository, the deployed RC baseline inside MPC is a 1R1C lumped model (white-box), implemented as a discrete Euler update:

$$T_{k+1} = T_k + \frac{\Delta t}{3600}\frac{UA\,(T_{out,k}-T_k)+g_{sol}\,(H_k/1000)+g_{hvac}\,\max(u_k-T_k,0)}{C}$$

Model properties:

1. State dimension: single indoor temperature state.
2. Inputs/disturbances: outdoor temperature, global irradiance, heating setpoint/action.
3. Nonlinearity: piecewise heating drive term $\max(u_k-T_k,0)$.
4. Numerical integration: explicit forward Euler at control step $\Delta t$.
5. Safety clamp in rollout: predicted $T$ bounded to [-20, 60] °C in the predictor.
6. Gradient handling in MPC: objective gradient is not analytical; the solver uses finite differences for RC.

Parameterization detail for fair comparison:

1. RC parameters $(UA, g_{sol}, g_{hvac}, C)$ are loaded from the same trained checkpoint physics parameters used by the PINN benchmark pipeline.
2. This keeps the thermal coefficients aligned across predictors and isolates the effect of residual learning vs pure-physics rollout.

Interpretation for the paper:

1. This RC baseline is interpretable, low-variance, and computationally lightweight.
2. Its main limitation is reduced expressiveness for unmodeled dynamics and long-horizon mismatch under complex operating regimes.

### 2.3 Data Generation and Splitting

1. BOPTEST scenario selection and episode construction.
2. Training/validation/test splits per testcase.
3. Feature/target definitions and normalization.

### 2.4 Training and Calibration

1. PINN training objective (data + physics regularization).
2. RC parameter estimation procedure.
3. Hyperparameter policy and reproducibility controls (seeding, config snapshots).

### 2.4.1 PINN Formulation Used in This Study (Implementation-Exact)

This work uses a residual-corrected grey-box PINN (single-zone, discrete-time, one-step-ahead):

1. Base physics: a lumped RC-like temperature increment is computed from outdoor temperature, global irradiance, heating input, and timestep.
2. Learned residual: a neural correction term is added to the physical increment.
3. Positivity constraints: physical parameters are trainable but constrained positive via softplus.
4. Final predictor:

	$$\hat{T}_{k+1} = T_k + \Delta T_{\mathrm{phys}}(T_k, T_{\mathrm{out},k}, H_k, u_k, \Delta t) + \Delta T_{\mathrm{nn}}(x_k)$$

where:

- $\Delta T_{\mathrm{phys}}$ is the RC-inspired increment with learned $(UA, g_{sol}, g_{hvac}, C)$.
- $\Delta T_{\mathrm{nn}}$ is the output of a 3-layer MLP (hidden size 64, tanh activations), bounded by construction through $5\tanh(\cdot)$.
- $x_k$ contains $[T_{zone}, T_{outdoor}, H_{global}, u_{heating}, \Delta u_{heating}, \sin/\cos(\mathrm{day}), \sin/\cos(\mathrm{year})]$.

Training objective is rollout-consistent and combines one-step and multi-step terms:

$$\mathcal{L}_{total} = \mathcal{L}_{1step} + w_{roll}\,\mathcal{L}_{roll} + \lambda_{phys}\,\mathcal{L}_{phys}, \quad \mathcal{L}_{phys}=\mathbb{E}[\Delta T_{\mathrm{nn}}^2]$$

with a default rollout horizon of 24 steps in the current implementation. The physics term regularizes correction magnitude rather than enforcing a PDE residual. In taxonomy terms, this is a trajectory-consistent hybrid residual PINN / physics-regularized neural state-transition model.

### 2.4.2 Properties of the Current PINN

Strengths:

1. Physically anchored extrapolation versus pure black-box one-step models.
2. Very compact model and fast training on CPU.
3. Stable MPC integration due to bounded corrective term and explicit thermal state update.

Limitations observed in current experiments:

1. Physics penalty is soft and indirect; it does not enforce full trajectory-consistent dynamics.
2. One-step training objective can look good while rollout error remains nontrivial.
3. Validation-loss stagnation/noise after early epochs indicates limited optimization headroom with current architecture and objective.

### 2.4.3 Stronger PINN Upgrade (Now Implemented)

The first upgrade step is now implemented in the training pipeline: 24-step rollout-consistent training in addition to one-step supervision. Remaining candidate upgrades are ranked by implementation risk versus expected benefit:

1. Multi-step rollout-consistent training (implemented):
	Pipeline now trains with truncated-horizon rollout loss (default 24 steps) in addition to one-step loss.
	Expected benefit: directly reduces compounding rollout drift, which is critical for MPC.
2. Adaptive loss balancing (low-medium risk):
	Use existing gradient-balance or uncertainty weighting mode instead of fixed $\lambda_{phys}$.
	Expected benefit: reduces manual tuning and improves stability across testcases/seasons.
3. Monotone/structure-constrained residual block (medium risk):
	Constrain selected sensitivities (e.g., heating effect sign) or use Lipschitz-bounded layers.
	Expected benefit: better closed-loop robustness and fewer unphysical responses.
4. Multi-zone graph PINN (higher risk, high impact for larger buildings):
	Replace single-zone residual MLP with graph-coupled thermal states.
	Expected benefit: improved fidelity for multizone cases where current single-zone abstraction is limiting.
5. Neural ODE / latent ODE grey-box variant (higher risk):
	Continuous-time dynamics with differentiable integration and physics priors.
	Expected benefit: better handling of varying timesteps and long-horizon consistency, at higher computational cost.

Current recommended model setting for this project (best rigor/effort tradeoff):

1. Keep the current grey-box state update.
2. Keep 24-step rollout loss enabled in training objective.
3. Switch to adaptive loss weighting (gradient-balance mode).
4. Keep architecture width/depth modest; prioritize trajectory-consistent objective over larger network size.

This model should be described in the paper as a trajectory-consistent grey-box PINN and compared fairly against the one-step-only baseline.

### 2.4.4 Training and Validation Behavior (Empirical Summary)

What can be concluded from the current runs:

1. Convergence and early stopping worked as intended.
2. One-step validation accuracy is strong and stable across variants.
3. Rollout validation error remains the main limitation for control-oriented use.

Quantitative summary from saved artifacts:

1. Baseline PINN (`artifacts/pinn_phase1`):
	epochs run = 110, best epoch = 90, best validation loss = 0.0032506,
	validation RMSE = 0.06029 degC, test RMSE = 0.07651 degC,
	validation rollout RMSE = 0.35094 degC,
	validation-loss volatility (std over epochs) = 0.0007201.
2. Improved regularized run (`artifacts/pinn_phase1_improved`):
	epochs run = 80, best epoch = 79, best validation loss = 0.0034335,
	validation RMSE = 0.06047 degC, test RMSE = 0.07664 degC,
	validation rollout RMSE = 0.51418 degC,
	validation-loss volatility (std over epochs) = 0.0005181.

Interpretation to report in the manuscript:

1. The regularized run reduced validation-loss oscillation (smoother optimization), which supports improved training stability.
2. One-step generalization stayed nearly unchanged between runs (similar RMSE on validation/test splits).
3. Better one-step smoothness did not automatically improve rollout fidelity; this supports the need for trajectory-consistent (multi-step) training objectives when the end use is MPC.

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

### Current quantitative snapshot (4 completed benchmark cases)

| Case | RC Comfort (Kh) | PINN Comfort (Kh) | Delta (PINN - RC) | Relative Change | Better |
|---|---:|---:|---:|---:|---|
| bestest_hydronic | 71.1 | 65.6 | -5.6 | -7.9% | PINN |
| bestest_hydronic_heat_pump | 18.9 | 91.1 | +72.2 | +381.9% | RC |
| singlezone_commercial_hydronic | 12.8 | 5.3 | -7.5 | -58.5% | PINN |
| twozone_apartment_hydronic | 190.6 | 105.0 | -85.6 | -44.9% | PINN |

| Predictor | Cases included | Mean comfort (Kh) | Mean challenge discomfort (tdis_tot) | Mean energy (Wh) | Mean challenge cost (cost_tot) | Mean peak power (W) | Mean wall time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| RC | 4 | 73.37 | 105.06 | 1677987.60 | 0.097347 | 32787.62 | 46.33 |
| PINN | 4 | 66.76 | 89.70 | 888679.60 | 0.077169 | 30192.75 | 388.18 |

Note: `multizone_residential_hydronic` is still excluded from these headline values pending separate recovery/debug completion.

### Phase-1 singlezone 7-day all-test (executed)

The 7-day all-test campaign for `singlezone_commercial_hydronic` was completed for both predictors (`te_std_01`, `te_std_02`, `te_ext_01`, `te_ext_02`) with identical episode timing metadata and successful run completion.

| Metric | RC | PINN | Delta (PINN - RC) |
|---|---:|---:|---:|
| Mean cost_tot | 0.180410 | 0.133102 | -0.047308 |
| Mean comfort (Kh) | 6.9410 | 0.0000 | -6.9410 |
| Mean challenge discomfort (tdis_tot) | 0.0000 | 0.0000 | 0.0000 |
| Mean MPC solve time (ms) | 3.335 | 31.324 | +27.989 |
| Total episode wall time over 4 episodes (s) | 192.00 | 251.38 | +59.38 |

Interpretation for manuscript draft:

1. In this completed all-test set, PINN improves mean operational cost by about 26.2% versus RC.
2. PINN removes local comfort violations reported in RC for `te_std_02`, `te_ext_01`, and `te_ext_02`.
3. The runtime tradeoff remains favorable for deployment: PINN is about 9.4x slower per solve on average, but still far below the 900 s control interval.

Reproducibility pointers:

1. Run logs: `logs/run_alltest_rc_7d.log`, `logs/run_alltest_pinn_7d.log`.
2. Outputs: `results/mpc_phase1/rc/te_*.json`, `results/mpc_phase1/pinn/te_*.json`.

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
