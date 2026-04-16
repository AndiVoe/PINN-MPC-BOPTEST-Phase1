# Paper Results Checklist

Use this checklist for each 30-day 1R1C RC vs PINN run.

## Run Selection

- [ ] Manifest is `manifests/eu/stage2/singlezone_commercial_hydronic_stage2.yaml`
- [ ] Episode is `te_std_01` or the intended 30-day stage-2 test episode
- [ ] Predictor is `rc` or `pinn`
- [ ] RC baseline is restricted to `1R1C`
- [ ] No stage-1 7-day screening assets are used for the paper result

## Training Outputs

- [ ] `best_model.pt` exists in `artifacts/pinn_phase1/`
- [ ] Final loss weighting is written in the training result output
- [ ] Final physics parameters are written in the training result output
- [ ] Training config is archived with the artifact

## MPC Outputs

- [ ] Episode JSON exists in the results folder
- [ ] `solver_trace_summary` is present
- [ ] `final_solver_solution` is present
- [ ] `solver_trace` is present if enabled
- [ ] `challenge_kpis` are present
- [ ] `diagnostic_kpis` are present

## Metrics To Report

- [ ] `tdis_tot`
- [ ] `cost_tot`
- [ ] `pele_tot`
- [ ] `pdih_tot`
- [ ] Mean MPC solve time
- [ ] Comfort and energy comparison against RC baseline

## Sanity Checks

- [ ] Comfort bounds match the configured occupied/unoccupied schedule
- [ ] 30-day run length is used, not the 7-day screening run
- [ ] The same horizon, control interval, and case mapping are used for RC and PINN
- [ ] Outputs are reproducible with the same checkpoint and manifest
