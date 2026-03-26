# MPC tuned_v2: Plan and Step-by-Step Execution Report

## Plan
1. Define a small, representative tuning subset (te_std_01, te_ext_01).
2. Create lag-aware tuning candidate config with stronger smoothness penalty.
3. Run baseline RC/PINN/RBC on subset.
4. Run tuned_v2 RC/PINN/RBC on the same subset.
5. Compare KPI + lag + solve-time deltas and decide next tuning move.

## Tuned Config
- File: configs/mpc_phase1_tuned_v2.yaml
- objective_weights: comfort 100.000 -> 95.000, energy 0.0010 -> 0.0015, control_smoothness 0.100 -> 0.300
- solver_maxiter: 100 -> 90

## Results by Controller/Episode
| Controller | Episode | comfort_Kh delta % | energy_Wh delta % | smoothness delta % | mean abs du delta % | xcorr lag delta [steps] | solve mean delta [ms] |
|---|---|---:|---:|---:|---:|---:|---:|
| RC | te_std_01 | 0.0 | 0.0 | 0.6 | 0.6 | -18.00 | -0.4 |
| RC | te_ext_01 | -0.0 | -0.0 | 0.6 | 0.6 | 0.00 | -0.0 |
| PINN | te_std_01 | 0.0 | 0.0 | nan | nan | nan | -1.1 |
| PINN | te_ext_01 | 20.6 | -0.2 | -59.8 | -59.8 | 0.00 | -38.3 |
| RBC | te_std_01 | 0.0 | 0.0 | nan | nan | nan | 0.0 |
| RBC | te_ext_01 | 0.0 | 0.0 | nan | nan | nan | 0.0 |

## Aggregate Delays and Side Effects
- RC avg deltas: comfort 0.0%, energy 0.0%, smoothness 0.6%, mean |du| 0.6%, solve_mean -0.2 ms.
- PINN avg deltas: comfort 10.3%, energy -0.1%, smoothness -59.8%, mean |du| -59.8%, solve_mean -19.7 ms.
- RBC avg deltas: comfort 0.0%, energy 0.0%, smoothness nan%, mean |du| nan%, solve_mean 0.0 ms.

## Interpretation
- RBC is unchanged (as expected), confirming comparison integrity.
- RC changed slightly but did not show a clean smoothness-energy-comfort improvement tradeoff on this subset.
- PINN summary: comfort delta 10.3% and optimizer runtime improved (-19.7 ms mean delta).

## Decision
- Keep the step-by-step pipeline, but reject tuned_v2 as a production candidate.
- Next candidate should preserve PINN comfort parity while keeping solve-time overhead low.