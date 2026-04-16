# Workflow: IDF -> FMU -> BOPTEST -> MPC (RC vs PINN) -> Results

## 1) Building Model Origin (IDF)

The process starts from an EnergyPlus building model in IDF format.

- The IDF defines envelope, schedules, HVAC components, and zone dynamics.
- This is the physical source model for simulation-based benchmarking.

## 2) Export to FMU

The EnergyPlus model is exported as an FMU so it can be co-simulated by external orchestration layers.

- FMU provides a standard interface for state advancement and input/output exchange.
- This makes the building model portable and controllable in automated experiments.

## 3) BOPTEST Role

BOPTEST wraps the building/testcase and provides a standardized REST API for control benchmarking.

Main responsibilities of BOPTEST in this project:

- Plant authority: true closed-loop plant evolution and KPI evaluation.
- Forecast provider: weather/solar forecasts used by MPC.
- Scenario manager: start time, period selection, and episode setup.
- KPI engine: challenge metrics such as cost and discomfort.

Test case used:

- singlezone_commercial_hydronic

## 4) Dataset and Training Path

From BOPTEST episodes, datasets are generated for model development.

- Train/validation/test episodes are split by manifest definitions.
- The PINN surrogate is trained on these sequences.
- RC baseline parameters are loaded from checkpoint physics parameters.

## 5) MPC Setup

At runtime, both controllers share the same MPC formulation; only the internal predictor changes.

- Predictor option A: RC (white-box 1R1C model)
- Predictor option B: PINN (physics-informed neural surrogate)

MPC characteristics (committed implementation):

- Rolling horizon: 6 h lookahead (24 steps at 900 s)
- Control interval: 900 s
- Control bounds: 18 to 26 degC setpoint
- Objective terms: comfort penalty + energy proxy + control smoothness
- Optimizer: SciPy SLSQP

Forecast handling in MPC:

- At each step, request horizon forecast from BOPTEST for outdoor temperature and global horizontal irradiance.
- If forecast samples are missing, pad with current measured values.
- Apply occupancy-aware comfort bounds across the horizon.

## 6) Runtime Closed-Loop Sequence

For each MPC step:

1. Read current plant measurements from BOPTEST.
2. Pull forecast for the prediction horizon.
3. Solve one MPC optimization with chosen predictor (RC or PINN).
4. Send first control move to BOPTEST.
5. Advance simulation one control interval.
6. Log diagnostics and continue until episode end.

## 7) KPIs and Interpretation

Use challenge KPIs as the main benchmark outputs:

- cost_tot
- idis_tot
- pdih_tot
- pele_tot
- tdis_tot

Diagnostic KPIs (solve time, internal comfort metrics, energy totals) are valuable for engineering analysis but can differ from challenge definitions.

Important note:

- challenge tdis_tot can remain 0 while local diagnostic comfort metrics are non-zero, due to different discomfort definitions and occupancy windows.

Parity and comparability check:

- Reproducibility script now executes a parity validator that checks RC vs PINN episode comparability and discomfort-definition mismatch risk.
- Output report: results/mpc_phase1/discomfort_parity_report.csv
- Expected interpretation pattern for current runs:
	- Comparable pairs should be True for all paired episodes.
	- Challenge discomfort (boptest tdis_tot) can remain 0 for both predictors.
	- Local discomfort from logged step bounds can still be non-zero for RC episodes.
	- This is a metric-definition divergence, not an episode comparability issue.

## 8) Current Results Summary

### Phase1 test set (te_std_01, te_std_02, te_ext_01, te_ext_02)

Executed test-set properties (from result metadata; identical structure for PINN and RC):

| Episode | split | weather_class | start_time_s | start_day | control_interval_s | n_steps | duration |
|---|---|---|---:|---:|---:|---:|---|
| te_std_01 | test | standard | 24192000 | 280 | 900 | 672 | 7 days |
| te_std_02 | test | standard | 26611200 | 308 | 900 | 672 | 7 days |
| te_ext_01 | test | extreme | 0 | 0 | 900 | 672 | 7 days |
| te_ext_02 | test | extreme | 0 | 0 | 900 | 672 | 7 days |

- PINN avg cost_tot: 0.133102
- RC avg cost_tot: 0.180410
- Relative cost reduction (PINN vs RC): about 26.2%
- Challenge tdis_tot: 0.0 for both

Per-episode compact comparison (7-day all-test, singlezone_commercial_hydronic):

| Episode | RC cost_tot | PINN cost_tot | RC comfort_Kh | PINN comfort_Kh | RC mean solve ms | PINN mean solve ms |
|---|---:|---:|---:|---:|---:|---:|
| te_std_01 | 0.101620 | 0.075954 | 0.0000 | 0.0000 | 3.259 | 31.087 |
| te_std_02 | 0.195887 | 0.141854 | 8.4943 | 0.0000 | 3.429 | 31.767 |
| te_ext_01 | 0.212026 | 0.157263 | 9.6348 | 0.0000 | 3.331 | 31.810 |
| te_ext_02 | 0.212106 | 0.157336 | 9.6348 | 0.0000 | 3.320 | 30.632 |
| Mean | 0.180410 | 0.133102 | 6.9410 | 0.0000 | 3.335 | 31.324 |

Run artifacts:

- Live execution logs: `logs/run_alltest_rc_7d.log`, `logs/run_alltest_pinn_7d.log`.
- Episode outputs: `results/mpc_phase1/rc/*.json`, `results/mpc_phase1/pinn/*.json`.

### Future test set (te_win_01, te_win_02, te_long_01, te_long_02, te_long_03)

Executed test-set properties (from result metadata; identical structure for PINN and RC):

| Episode | split | weather_class | start_time_s | start_day | control_interval_s | n_steps | duration |
|---|---|---|---:|---:|---:|---:|---|
| te_win_01 | future_test | winter | 0 | 0 | 900 | 672 | 7 days |
| te_win_02 | future_test | winter | 2419200 | 28 | 900 | 672 | 7 days |
| te_long_01 | future_test | standard_long | 0 | 0 | 900 | 2880 | 30 days |
| te_long_02 | future_test | winter_long | 0 | 0 | 900 | 2880 | 30 days |
| te_long_03 | future_test | winter_long | 0 | 0 | 900 | 2880 | 30 days |

- PINN avg cost_tot: 0.491995
- RC avg cost_tot: 0.630301
- Relative cost reduction (PINN vs RC): about 21.9%
- Challenge tdis_tot: 0.0 for both

### Computation time trend

- RC solves are faster (around 3.3 ms mean per MPC solve on this 7-day all-test).
- PINN solves are slower (around 31.3 ms mean), but still practical for 900 s control intervals.

## 9) Practical Conclusion

Within this benchmark setup, PINN improves operational cost relative to RC while preserving challenge-level comfort/discomfort KPIs.

## 10) Future Applications

- Multi-zone and larger hydronic systems.
- Disturbance-heavy regimes (winter extremes, long-horizon campaigns).
- Robust/stochastic MPC with uncertainty-aware forecasts.
- Hybrid control stacks: PINN dynamics + RL/LSTM policy warm-starts.
- Real-time deployment studies with hard compute budgets.
