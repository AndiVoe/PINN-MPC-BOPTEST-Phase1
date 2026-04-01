# Full validation report (generated from summary_full_validation.json)

## Candidates checked
- cand_001
- cand_005
- cand_008

## Baseline sources
- rc: results/mpc_tuning_eval/baseline/rc
- pinn: results/mpc_tuning_eval/baseline/pinn
- rbc: results/mpc_tuning_eval/baseline/rbc

## Results by Controller/Episode
| Controller | Episode | baseline | candidate | delta % (candidate vs baseline) |
|---|---|---:|---:|---:|
| rc | te_ext_01 | cost=0.208965, tdis=0.000, solve_ms=2.5 | N/A | N/A |
| rc | te_ext_01 | cost=0.208965, tdis=0.000, solve_ms=2.5 | N/A | N/A |
| rc | te_ext_01 | cost=0.208965, tdis=0.000, solve_ms=2.5 | N/A | N/A |
| rc | te_ext_02 | N/A | N/A | N/A |
| rc | te_ext_02 | N/A | N/A | N/A |
| rc | te_ext_02 | N/A | N/A | N/A |
| rc | te_std_01 | cost=0.136018, tdis=0.000, solve_ms=2.9 | N/A | N/A |
| rc | te_std_01 | cost=0.136018, tdis=0.000, solve_ms=2.9 | N/A | N/A |
| rc | te_std_01 | cost=0.136018, tdis=0.000, solve_ms=2.9 | N/A | N/A |
| rc | te_std_02 | N/A | N/A | N/A |
| rc | te_std_02 | N/A | N/A | N/A |
| rc | te_std_02 | N/A | N/A | N/A |
| pinn | te_ext_01 | cost=0.128848, tdis=0.690, solve_ms=127.6 | cost=0.128556, tdis=0.670, solve_ms=69.5 | cost -0.23%; tdis -3.03%; solve_ms -58.03 ms |
| pinn | te_ext_01 | cost=0.128848, tdis=0.690, solve_ms=127.6 | cost=0.128656, tdis=0.687, solve_ms=72.5 | cost -0.15%; tdis -0.51%; solve_ms -55.08 ms |
| pinn | te_ext_01 | cost=0.128848, tdis=0.690, solve_ms=127.6 | cost=0.128542, tdis=0.720, solve_ms=72.7 | cost -0.24%; tdis 4.30%; solve_ms -54.83 ms |
| pinn | te_ext_02 | N/A | cost=0.128627, tdis=0.670, solve_ms=68.8 | N/A |
| pinn | te_ext_02 | N/A | cost=0.128727, tdis=0.687, solve_ms=71.5 | N/A |
| pinn | te_ext_02 | N/A | cost=0.128613, tdis=0.720, solve_ms=71.4 | N/A |
| pinn | te_std_01 | cost=0.048357, tdis=0.207, solve_ms=35.7 | cost=0.048357, tdis=0.207, solve_ms=29.8 | cost 0.00%; tdis 0.00%; solve_ms -5.95 ms |
| pinn | te_std_01 | cost=0.048357, tdis=0.207, solve_ms=35.7 | cost=0.048357, tdis=0.207, solve_ms=28.6 | cost 0.00%; tdis 0.00%; solve_ms -7.14 ms |
| pinn | te_std_01 | cost=0.048357, tdis=0.207, solve_ms=35.7 | cost=0.048357, tdis=0.207, solve_ms=28.1 | cost 0.00%; tdis 0.00%; solve_ms -7.68 ms |
| pinn | te_std_02 | N/A | cost=0.113122, tdis=1.374, solve_ms=28.9 | N/A |
| pinn | te_std_02 | N/A | cost=0.113122, tdis=1.374, solve_ms=29.4 | N/A |
| pinn | te_std_02 | N/A | cost=0.113122, tdis=1.374, solve_ms=29.0 | N/A |
| rbc | te_ext_01 | cost=0.127993, tdis=0.918, solve_ms=0.0 | N/A | N/A |
| rbc | te_ext_01 | cost=0.127993, tdis=0.918, solve_ms=0.0 | N/A | N/A |
| rbc | te_ext_01 | cost=0.127993, tdis=0.918, solve_ms=0.0 | N/A | N/A |
| rbc | te_ext_02 | N/A | N/A | N/A |
| rbc | te_ext_02 | N/A | N/A | N/A |
| rbc | te_ext_02 | N/A | N/A | N/A |
| rbc | te_std_01 | cost=0.048357, tdis=0.207, solve_ms=0.0 | N/A | N/A |
| rbc | te_std_01 | cost=0.048357, tdis=0.207, solve_ms=0.0 | N/A | N/A |
| rbc | te_std_01 | cost=0.048357, tdis=0.207, solve_ms=0.0 | N/A | N/A |
| rbc | te_std_02 | N/A | N/A | N/A |
| rbc | te_std_02 | N/A | N/A | N/A |
| rbc | te_std_02 | N/A | N/A | N/A |

## Aggregates per candidate (from summary_full_validation.json)
| Candidate | Controller | cost_mean | tdis_mean | solve_mean_ms | wall_time_s_mean | smoothness_mean |
|---|---|---:|---:|---:|---:|---:|
| cand_001 | pinn | 0.104666 | 0.730 | 49.2 | 71.6 | 0.9092 |
| cand_005 | pinn | 0.104716 | 0.739 | 50.5 | 72.2 | 0.6922 |
| cand_008 | pinn | 0.104658 | 0.755 | 50.3 | 72.1 | 0.7637 |