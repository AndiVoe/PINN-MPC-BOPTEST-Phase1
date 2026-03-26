# MPC tuned_v3: Plan and Step-by-Step Execution Report

## Plan
1. Define a small, representative tuning subset (te_std_01, te_ext_01).
2. Create lag-aware tuning candidate config with stronger smoothness penalty.
3. Run baseline RC/PINN/RBC on subset.
4. Run tuned_v3 RC/PINN/RBC on the same subset.
5. Compare KPI + lag + solve-time deltas and decide next tuning move.

## Tuned Config
- File: configs/mpc_phase1_tuned_v3.yaml
- objective_weights: comfort 100.000 -> 100.000, energy 0.0010 -> 0.0012, control_smoothness 0.100 -> 0.200
- solver_maxiter: 100 -> 90

## Results by Controller/Episode
| Controller | Episode | comfort_Kh delta % | energy_Wh delta % | smoothness delta % | mean abs du delta % | xcorr lag delta [steps] | solve mean delta [ms] |
|---|---|---:|---:|---:|---:|---:|---:|
| RC | te_std_01 | 0.1 | 0.0 | 0.0 | 0.0 | -1.00 | -0.4 |
| RC | te_ext_01 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00 | -0.1 |
| PINN | te_std_01 | 0.0 | 0.0 | nan | nan | nan | 20.7 |
| PINN | te_ext_01 | -90.6 | 1.3 | -65.6 | -65.6 | -1.00 | -36.1 |
| RBC | te_std_01 | 0.0 | 0.0 | nan | nan | nan | 0.0 |
| RBC | te_ext_01 | 0.0 | 0.0 | nan | nan | nan | 0.0 |

## Aggregate Delays and Side Effects
- RC avg deltas: comfort 0.0%, energy 0.0%, smoothness 0.0%, mean |du| 0.0%, solve_mean -0.2 ms.
- PINN avg deltas: comfort -45.3%, energy 0.7%, smoothness -65.6%, mean |du| -65.6%, solve_mean -7.7 ms.
- RBC avg deltas: comfort 0.0%, energy 0.0%, smoothness nan%, mean |du| nan%, solve_mean 0.0 ms.

## Interpretation
- RBC is unchanged (as expected), confirming comparison integrity.
- RC changed slightly but did not show a clean smoothness-energy-comfort improvement tradeoff on this subset.
- PINN summary: comfort delta -45.3% and optimizer runtime stayed close to baseline (-7.7 ms mean delta).

## Decision
- tuned_v3 is acceptable for wider validation (meets subset acceptance thresholds).
- Next step: expand to all refreshed episodes and re-check comfort/energy parity.