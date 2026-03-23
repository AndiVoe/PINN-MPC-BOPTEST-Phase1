# Results Coverage and Training Status

Snapshot date: 2026-03-23 (refreshed from current filesystem state)

## Training State (EU cases)

Training artifacts are complete for all five EU cases (`best_model.pt`, `metrics.json`, `training_config.json` found):

- bestest_hydronic: complete
- bestest_hydronic_heat_pump: complete
- singlezone_commercial_hydronic: complete
- twozone_apartment_hydronic: complete
- multizone_residential_hydronic: complete

## Result State (available episode JSONs)

Source roots checked:

- `results/eu_rc_vs_pinn/raw`
- `results/mpc_phase1`

### bestest_hydronic

- RC: `te_std_01`, `te_std_02`, `te_std_03`
- PINN: `te_std_01`, `te_std_02`, `te_std_03`
- Status: partial (heating/probe episodes not present)

### bestest_hydronic_heat_pump

- RC: `te_std_01`, `te_std_02`, `te_std_03`
- PINN: `te_std_01`, `te_std_02`, `te_std_03`
- Status: partial (heating-season episodes not present)

### singlezone_commercial_hydronic

- RC: `te_std_01`, `te_std_02`, `te_std_03`, `te_ext_01`, `te_ext_02`, `te_long_01`, `te_long_02`, `te_long_03`, `te_win_01`, `te_win_02`
- PINN: `te_std_01`, `te_std_02`, `te_std_03`, `te_ext_01`, `te_ext_02`, `te_long_01`, `te_long_02`, `te_long_03`, `te_win_01`, `te_win_02`
- Status: up to date for executed standard/extreme/long/winter sets; heating-season IDs not present

### twozone_apartment_hydronic

- RC: `te_std_01`, `te_std_02`, `te_std_03`
- PINN: `te_std_01`, `te_std_02`, `te_std_03`
- Status: partial (heating-season episodes not present)

### multizone_residential_hydronic

- RC: none currently available in checked result roots
- PINN: none currently available in checked result roots
- Status: not up to date (result files missing)

## Bottom Line

- Training state: updated/completed for all EU cases.
- Result state: not fully updated across all testcases; coverage is currently complete only for the singlezone campaign families listed above.
