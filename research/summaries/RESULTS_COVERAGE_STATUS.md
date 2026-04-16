# Results Coverage Status

Snapshot date: 2026-04-02

## Scope of this status file

This status tracks the publication-facing full-validation package under:

- `results/mpc_tuning_eval/autotune_v1_10cand/full_validation`
- `results/mpc_tuning_eval/baseline`
- `artifacts/audit`

## Baseline coverage (singlezone_commercial_hydronic)

Required baseline episodes for fairness checks are present for all three controllers in top-level baseline folders:

- `te_ext_01`
- `te_ext_02`
- `te_std_01`
- `te_std_02`

Controllers verified:

- `results/mpc_tuning_eval/baseline/rc`
- `results/mpc_tuning_eval/baseline/pinn`
- `results/mpc_tuning_eval/baseline/rbc`

## Candidate coverage (full validation)

Candidates in scope:

- `cand_001`
- `cand_005`
- `cand_008`

Episodes included in the refreshed full-validation summary:

- `te_ext_01`
- `te_ext_02`
- `te_std_01`
- `te_std_02`

## Audit result

Latest end-to-end audit reports complete pass:

- total checks: 697
- failed checks: 0
- failed errors: 0
- failed warnings: 0

Reference files:

- `artifacts/audit/end_to_end_validity_checks.csv`
- `artifacts/audit/end_to_end_validity_report.md`

## Status

Publication-facing full-validation coverage is complete and consistent as of 2026-04-02.
