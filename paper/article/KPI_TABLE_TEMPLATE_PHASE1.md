# KPI Results Table Template (Phase 1)

## Study Scope

- Primary cases:
  - bestest_hydronic
  - bestest_hydronic_heat_pump
- Optional third case:
  - singlezone_commercial_hydronic
- Predictors compared under identical MPC setup:
  - RC predictor inside MPC
  - PINN predictor inside MPC

## Table 1. Per-Episode KPI Comparison (RC vs PINN)

| Case | Episode | Predictor | Thermal discomfort (Kh) | Challenge discomfort (tdis_tot) | Energy (Wh) | Challenge cost (cost_tot) | Peak power (W) | MPC solve time mean (ms) | Episode wall time (s) | Success (yes/no) | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| bestest_hydronic | te_std_01 | RC | 29.88 | 5.73 | 215505.40 | 0.232779 | 3264.10 | 2.659 | 27.05 | yes | stable baseline |
| bestest_hydronic | te_std_01 | PINN | 18.91 | 9.81 | 185284.06 | 0.203128 | 5637.04 | 294.596 | 223.12 | yes | recovered run |
| bestest_hydronic | te_std_02 | RC | 61.69 | 75.71 | 39933.49 | 0.047468 | 2119.18 | 2.358 | 26.07 | yes | baseline |
| bestest_hydronic | te_std_02 | PINN | 52.08 | 67.45 | 29987.52 | 0.040123 | 5601.13 | 608.730 | 432.99 | yes | recovered run |
| bestest_hydronic | te_std_03 | RC | 121.84 | 101.65 | 2337.26 | 0.003608 | 552.37 | 2.471 | 26.99 | yes | baseline |
| bestest_hydronic | te_std_03 | PINN | 125.68 | 105.45 | 3933.13 | 0.006700 | 2316.44 | 908.794 | 634.01 | yes | recovered run |
| bestest_hydronic_heat_pump | te_std_01 | RC | 21.34 | 2.30 | 1676525.49 | 0.415133 | 27102.76 | 3.260 | 37.17 | yes | complete |
| bestest_hydronic_heat_pump | te_std_01 | PINN | 80.36 | 130.79 | 906680.24 | 0.188534 | 29038.77 | 1217.492 | 849.03 | yes | complete |
| bestest_hydronic_heat_pump | te_std_02 | RC | 22.01 | 26.02 | 509161.00 | 0.149415 | 19017.96 | 3.735 | 38.80 | yes | complete |
| bestest_hydronic_heat_pump | te_std_02 | PINN | 96.39 | 101.31 | 755302.22 | 0.186687 | 33845.06 | 533.791 | 390.90 | yes | complete |
| bestest_hydronic_heat_pump | te_std_03 | RC | 13.39 | 6.85 | 80560.08 | 0.032219 | 9938.22 | 3.011 | 31.95 | yes | complete |
| bestest_hydronic_heat_pump | te_std_03 | PINN | 96.69 | 83.92 | 415680.01 | 0.131758 | 30246.07 | 366.884 | 278.54 | yes | complete |
| singlezone_commercial_hydronic | te_std_01 | RC | 20.45 | 0.00 | 15429014.52 | 0.147317 | 226011.28 | 3.372 | 50.26 | yes | complete |
| singlezone_commercial_hydronic | te_std_01 | PINN | 0.00 | 0.00 | 7475019.53 | 0.069955 | 226013.16 | 60.071 | 83.53 | yes | complete |
| singlezone_commercial_hydronic | te_std_02 | RC | 4.79 | 0.00 | 1419546.62 | 0.011420 | 91926.13 | 3.092 | 55.18 | yes | complete |
| singlezone_commercial_hydronic | te_std_02 | PINN | 2.76 | 0.00 | 392201.81 | 0.001407 | 7175.13 | 294.506 | 243.96 | yes | complete |
| singlezone_commercial_hydronic | te_std_03 | RC | 13.19 | 0.00 | 312994.39 | 0.000859 | 2779.33 | 3.051 | 45.16 | yes | complete |
| singlezone_commercial_hydronic | te_std_03 | PINN | 13.19 | 0.00 | 312994.43 | 0.000859 | 2779.32 | 321.937 | 258.68 | yes | complete |
| twozone_apartment_hydronic | te_std_01 | RC | 153.18 | 201.85 | 233889.00 | 0.127941 | 9452.15 | 3.639 | 79.43 | yes | complete |
| twozone_apartment_hydronic | te_std_01 | PINN | 30.88 | 52.43 | 104803.02 | 0.080196 | 9552.38 | 394.729 | 345.53 | yes | complete |
| twozone_apartment_hydronic | te_std_02 | RC | 102.66 | 176.64 | 108192.00 | 0.000000 | 644.00 | 3.098 | 68.62 | yes | complete |
| twozone_apartment_hydronic | te_std_02 | PINN | 67.96 | 90.79 | 50351.61 | 0.014624 | 6982.91 | 537.482 | 456.49 | yes | complete |
| twozone_apartment_hydronic | te_std_03 | RC | 315.99 | 663.92 | 108192.00 | -0.000000 | 644.00 | 3.069 | 69.24 | yes | complete |
| twozone_apartment_hydronic | te_std_03 | PINN | 216.25 | 434.41 | 31917.58 | 0.002057 | 3125.62 | 585.975 | 461.36 | yes | complete |

## Table 2. Case-Level Aggregates (mean across test episodes)

| Case | Predictor | Mean thermal discomfort (Kh) | Mean challenge discomfort (tdis_tot) | Mean energy (Wh) | Mean challenge cost (cost_tot) | Mean peak power (W) | Mean wall time (s) | Completed episodes / expected | Failures |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| bestest_hydronic | RC | 71.14 | 61.03 | 85925.38 | 0.094618 | 1978.55 | 26.70 | 3/3 | 0 |
| bestest_hydronic | PINN | 65.55 | 60.90 | 73068.24 | 0.083317 | 4518.20 | 430.04 | 3/3 | 0 |
| bestest_hydronic_heat_pump | RC | 18.92 | 11.72 | 755415.52 | 0.198922 | 18686.31 | 35.97 | 3/3 | 0 |
| bestest_hydronic_heat_pump | PINN | 91.14 | 105.34 | 692554.16 | 0.168993 | 31043.30 | 506.16 | 3/3 | 0 |
| singlezone_commercial_hydronic | RC | 12.81 | 0.00 | 5720518.51 | 0.053199 | 106905.58 | 50.20 | 3/3 | 0 |
| singlezone_commercial_hydronic | PINN | 5.32 | 0.00 | 2726738.59 | 0.024074 | 78655.87 | 195.39 | 3/3 | 0 |
| twozone_apartment_hydronic | RC | 190.61 | 347.47 | 150091.00 | 0.042647 | 3580.05 | 72.43 | 3/3 | 0 |
| twozone_apartment_hydronic | PINN | 105.03 | 192.55 | 62357.40 | 0.032292 | 6553.64 | 421.13 | 3/3 | 0 |

## Table 3. Cross-Case Summary

| Predictor | Cases included | Mean thermal discomfort (Kh) | Mean energy (Wh) | Mean challenge cost (cost_tot) | Mean peak power (W) | Mean wall time (s) | Total failures |
|---|---:|---:|---:|---:|---:|---:|---:|
| RC | 4 | 73.37 | 1677987.60 | 0.097347 | 32787.62 | 46.33 | 0 |
| PINN | 4 | 66.76 | 888679.60 | 0.077169 | 30192.75 | 388.18 | 0 |

## Reporting Notes

1. Keep RC and PINN objective weights identical for fair comparison.
2. Report runtime separately from comfort/energy so performance and computational cost are not conflated.
3. Mark partial runs explicitly in the Success and Failures columns.
4. Include the exact commit/config hash in the paper appendix for reproducibility.
