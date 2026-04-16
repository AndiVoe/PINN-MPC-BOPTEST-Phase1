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

## PINN Surrogate Validation Addendum (2026-04-10)

PINN training outputs now include expanded validation and verification metrics to support model-quality claims beyond RMSE only.

Validation axes:
1. Data accuracy: `rmse_degC`, `mae_degC`, `mape_pct`, `r2_score`
2. Physical consistency: `physics_loss` on unseen validation/test split
3. Robustness testing: input-noise reevaluation with
   - `robustness_test.noise_5pct.*`
   - `robustness_test.noise_10pct.*`

Primary output locations:
1. `artifacts/pinn_phase1_variant_*/metrics.json`
2. `artifacts/pinn_phase1_variant_*/history.json`
3. `artifacts/variant_training_summary.json` (now includes validation/test/robustness summary fields)

Reference documentation:
1. `docs/pinn_variant_training.md`
2. `docs/METRICS_AND_KPI_STANDARDS.md`
