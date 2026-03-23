# Results Coverage and Training Status

Snapshot date: 2026-03-23

## Scope

This overview is built from:

- `manifests/**/*.yaml` (expected `test` and `future_test` episode IDs per case)
- `results/**/*.json` (available RC/PINN episode outputs by `case_name`)
- `artifacts/eu/<case>/` (training artifact completeness)

## Case Status Summary

| Case | Expected test/future episodes | RC available | PINN available | Training artifacts | Status |
|---|---:|---:|---:|---|---|
| `bestest_hydronic` | 7 | 6 | 6 | complete | Mostly up to date (missing probe `te_01` for both predictors) |
| `bestest_hydronic_heat_pump` | 6 | 6 | 6 | complete | Up to date |
| `singlezone_commercial_hydronic` | 11 | 11 | 11 | complete | Up to date |
| `twozone_apartment_hydronic` | 6 | 3 | 3 | complete | Partial (missing heating-season episodes for RC and PINN) |
| `multizone_residential_hydronic` | 6 | 1 | 0 | complete | Not up to date (only RC quickcheck `te_std_01` exists) |

Training artifacts are considered complete when all of these exist:

- `best_model.pt`
- `metrics.json`
- `training_config.json`

## Expected vs Available Episode IDs

### bestest_hydronic

- Expected: `te_01`, `te_std_01`, `te_std_02`, `te_std_03`, `te_heat_01`, `te_heat_02`, `te_heat_03`
- RC available: `te_std_01`, `te_std_02`, `te_std_03`, `te_heat_01`, `te_heat_02`, `te_heat_03`
- PINN available: `te_std_01`, `te_std_02`, `te_std_03`, `te_heat_01`, `te_heat_02`, `te_heat_03`
- Missing RC: `te_01`
- Missing PINN: `te_01`

### bestest_hydronic_heat_pump

- Expected: `te_std_01`, `te_std_02`, `te_std_03`, `te_heat_01`, `te_heat_02`, `te_heat_03`
- RC available: `te_std_01`, `te_std_02`, `te_std_03`, `te_heat_01`, `te_heat_02`, `te_heat_03`
- PINN available: `te_std_01`, `te_std_02`, `te_std_03`, `te_heat_01`, `te_heat_02`, `te_heat_03`
- Missing RC: none
- Missing PINN: none

### singlezone_commercial_hydronic

- Expected: `te_std_01`, `te_std_02`, `te_std_03`, `te_ext_01`, `te_ext_02`, `te_heat_01`, `te_heat_02`, `te_heat_03`, `te_long_01`, `te_long_02`, `te_long_03`
- RC available: all expected episodes (plus `te_win_01`, `te_win_02`)
- PINN available: all expected episodes (plus `te_win_01`, `te_win_02`)
- Missing RC: none
- Missing PINN: none

### twozone_apartment_hydronic

- Expected: `te_std_01`, `te_std_02`, `te_std_03`, `te_heat_01`, `te_heat_02`, `te_heat_03`
- RC available: `te_std_01`, `te_std_02`, `te_std_03`
- PINN available: `te_std_01`, `te_std_02`, `te_std_03`
- Missing RC: `te_heat_01`, `te_heat_02`, `te_heat_03`
- Missing PINN: `te_heat_01`, `te_heat_02`, `te_heat_03`

### multizone_residential_hydronic

- Expected: `te_std_01`, `te_std_02`, `te_std_03`, `te_heat_01`, `te_heat_02`, `te_heat_03`
- RC available: `te_std_01`
- PINN available: none
- Missing RC: `te_std_02`, `te_std_03`, `te_heat_01`, `te_heat_02`, `te_heat_03`
- Missing PINN: `te_std_01`, `te_std_02`, `te_std_03`, `te_heat_01`, `te_heat_02`, `te_heat_03`

## Manifest Sources Used

- `manifests/episode_split_phase1.yaml`
- `manifests/episode_split_phase1_long.yaml`
- `manifests/eu_probe_bestest_hydronic.yaml`
- `manifests/eu/bestest_hydronic_stage1.yaml`
- `manifests/eu/bestest_hydronic_heating_season.yaml`
- `manifests/eu/bestest_hydronic_heat_pump_stage1.yaml`
- `manifests/eu/bestest_hydronic_heat_pump_stage1_protocol_a.yaml`
- `manifests/eu/bestest_hydronic_heat_pump_heating_season.yaml`
- `manifests/eu/singlezone_commercial_hydronic_stage1.yaml`
- `manifests/eu/singlezone_commercial_hydronic_stage1_protocol_a.yaml`
- `manifests/eu/singlezone_commercial_hydronic_heating_season.yaml`
- `manifests/eu/twozone_apartment_hydronic_stage1.yaml`
- `manifests/eu/twozone_apartment_hydronic_heating_season.yaml`
- `manifests/eu/multizone_residential_hydronic_stage1.yaml`
- `manifests/eu/multizone_residential_hydronic_quickcheck.yaml`
- `manifests/eu/multizone_residential_hydronic_heating_season.yaml`
