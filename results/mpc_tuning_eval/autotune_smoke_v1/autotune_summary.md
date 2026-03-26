# Automated MPC Weight Tuning Summary

- Predictor: pinn
- Episodes: te_std_01, te_ext_01
- Samples: 1
- Baseline means: comfort_Kh=0.3928, energy_Wh=9478170.36, solve_ms=81.656

## Top 5 by normalized score
| cand | comfort_w | energy_w | smooth_w | maxiter | comfort_Kh | energy_Wh | solve_ms | score |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 102.789 | 0.00083 | 0.169 | 87 | 0.3989 | 9463381.54 | 107.124 | 1.0400 |

## Pareto Front (comfort, energy, solve) size
- 1 candidates

Use pareto_front.csv to pick candidates based on your priority (comfort-first vs energy-first).