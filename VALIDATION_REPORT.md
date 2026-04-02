# Validation Report - Full Validation Refresh (2026-04-02)

## Summary

The publication-facing full-validation package has been refreshed and revalidated after baseline coverage completion.

## Validation outcomes

1. Baseline completion
- Added and verified missing baseline coverage for `te_ext_02` and `te_std_02` for `rc`, `pinn`, and `rbc` in top-level baseline folders.

2. Full-validation artifact regeneration
- Refreshed summary JSON:
   - `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/summary_full_validation.json`
- Refreshed report markdown:
   - `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/execution_report_fixed.md`
- Refreshed aggregated CSV:
   - `artifacts/full_validation_all_controllers_aggregated.csv`
- Refreshed comparison plots:
   - `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/plots/comparison_all_controllers_cost.png`
   - `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/plots/comparison_all_controllers_tdis.png`
   - `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/plots/comparison_all_controllers_solve_time.png`
   - `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/plots/comparison_all_controllers_combined.png`

3. End-to-end validity audit
- Total checks: 697
- Failed checks: 0
- Failed errors: 0
- Failed warnings: 0
- References:
   - `artifacts/audit/end_to_end_validity_checks.csv`
   - `artifacts/audit/end_to_end_validity_report.md`

4. Runtime compatibility fix applied
- PINN predictor runtime now aligns feature assembly with checkpoint feature names to support both 9-feature and 10-feature checkpoints.
- Code location:
   - `mpc/predictors.py`

## Status

Validated and ready for publication-facing handoff as of 2026-04-02.
