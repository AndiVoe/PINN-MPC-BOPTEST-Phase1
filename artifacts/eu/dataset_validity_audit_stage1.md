# EU Stage-1 Dataset Validity Audit

Legend: `OK` = pass, `FLAG` = requires review.

| case | split_leakage | time_monotonic | dt_900s | finite_values | value_ranges | distribution_shift | rollout_stability_rmse | rollout_stability_mae | rollout_rmse_ratio | rollout_mae_ratio | test_rmse | test_mae |
|---|---|---|---|---|---|---|---|---|---:|---:|---:|---:|
| bestest_hydronic | OK | OK | OK | OK | OK | OK | OK | OK | 6.0629 | 5.8375 | 0.357557 | 0.294659 |
| bestest_hydronic_heat_pump | OK | OK | OK | OK | OK | OK | FLAG | FLAG | 16.9114 | 18.2745 | 0.043534 | 0.034052 |
| singlezone_commercial_hydronic | OK | OK | OK | OK | OK | OK | OK | OK | 7.5472 | 8.2285 | 0.071086 | 0.054597 |
| twozone_apartment_hydronic | OK | OK | OK | OK | OK | OK | FLAG | FLAG | 52.7331 | 55.6315 | 0.058662 | 0.043038 |