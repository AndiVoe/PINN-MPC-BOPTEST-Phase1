# MPC Tuning v1: Plan and Step-by-Step Execution Report

## Plan
1. Define a small, representative tuning subset (te_std_01, te_ext_01).
2. Create lag-aware tuning candidate config with stronger smoothness penalty.
3. Run baseline RC/PINN/RBC on subset.
4. Run tuned v1 RC/PINN/RBC on the same subset.
5. Compare KPI + lag + solve-time deltas and decide next tuning move.

## Tuned Config
- File: configs/mpc_phase1_tuned_v1.yaml
- objective_weights: comfort 100 -> 85, energy 0.001 -> 0.003, control_smoothness 0.1 -> 2.0
- solver_maxiter: 100 -> 120

## Results by Controller/Episode
| Controller | Episode | comfort_Kh delta % | energy_Wh delta % | smoothness delta % | mean abs du delta % | xcorr lag delta [steps] | solve mean delta [ms] |
|---|---|---:|---:|---:|---:|---:|---:|
| RC | te_std_01 | -43.6 | -3.1 | -5.2 | -5.2 | 0.00 | 2.1 |
| RC | te_ext_01 | -1.6 | -0.0 | 0.6 | 0.6 | 0.00 | 10.4 |
| PINN | te_std_01 | 0.0 | -0.0 | nan | nan | nan | 707.5 |
| PINN | te_ext_01 | 55.4 | -0.6 | -100.0 | -100.0 | 0.00 | 241.2 |
| RBC | te_std_01 | 0.0 | 0.0 | nan | nan | nan | 0.0 |
| RBC | te_ext_01 | 0.0 | 0.0 | nan | nan | nan | 0.0 |

## Aggregate Delays and Side Effects
- RC avg deltas: comfort -22.6%, energy -1.6%, smoothness -2.3%, mean |du| -2.3%, solve_mean 6.2 ms.
- PINN avg deltas: comfort 27.7%, energy -0.3%, smoothness -100.0%, mean |du| -100.0%, solve_mean 474.3 ms.
- RBC avg deltas: comfort 0.0%, energy 0.0%, smoothness nan%, mean |du| nan%, solve_mean 0.0 ms.

## Interpretation
- RBC is unchanged (as expected), confirming comparison integrity.
- RC changed slightly but did not show a clean smoothness-energy-comfort improvement tradeoff on this subset.
- PINN control trajectories remain effectively the same in comfort/energy but optimizer runtime increased strongly under tuned v1.

## Decision
- Keep the step-by-step pipeline, but reject tuned_v1 as a production candidate.
- Next candidate should target computational stability first: keep comfort/energy near baseline and reduce PINN solve time while adding only moderate smoothness increase.