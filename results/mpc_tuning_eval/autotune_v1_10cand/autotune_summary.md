# Automated MPC Weight Tuning Summary

- Predictor: pinn
- Episodes: te_std_01, te_ext_01
- Samples: 10
- Baseline means: comfort_Kh=0.3928, energy_Wh=9478170.36, solve_ms=81.656

## Top 5 by normalized score
| cand | comfort_w | energy_w | smooth_w | maxiter | comfort_Kh | energy_Wh | solve_ms | score |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 104.026 | 0.00130 | 0.212 | 88 | 0.4033 | 9468634.60 | 72.834 | 1.0049 |
| 8 | 92.044 | 0.00126 | 0.190 | 91 | 0.4204 | 9462694.81 | 59.394 | 1.0142 |
| 1 | 102.789 | 0.00083 | 0.169 | 87 | 0.3989 | 9463381.54 | 101.070 | 1.0326 |
| 9 | 102.075 | 0.00177 | 0.282 | 97 | 0.4384 | 9458427.74 | 63.610 | 1.0468 |
| 6 | 106.189 | 0.00081 | 0.301 | 93 | 0.4351 | 9458881.07 | 73.069 | 1.0534 |

## Pareto Front (comfort, energy, solve) size
- 8 candidates

Use pareto_front.csv to pick candidates based on your priority (comfort-first vs energy-first).