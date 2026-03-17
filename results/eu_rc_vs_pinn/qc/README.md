# EU RC vs PINN Quality-Control Package

This folder is generated to support scientific reporting and manual plausibility validation.

## Generate QC Artifacts

From repository root:

```powershell
& ".venv/Scripts/python.exe" -u scripts/qc_eu_results.py
```

Optional custom paths:

```powershell
& ".venv/Scripts/python.exe" -u scripts/qc_eu_results.py --raw-root results/eu_rc_vs_pinn/raw --out-dir results/eu_rc_vs_pinn/qc
```

## Output Files

- `plausibility_summary.csv`: one row per run (`case`, `predictor`, `episode`) with PASS/WARN status.
- `plausibility_report.json`: machine-readable issue list per run.
- `kpi_table.csv`: compact KPI table used for figure/table generation.
- `timeseries/*.png`: per-case/per-episode RC vs PINN trajectories.
- `overview/comfort_vs_energy.png`: comfort-energy tradeoff scatter.
- `overview/solve_time_distribution.png`: solver runtime distribution.

## Manual Validation Checklist (for paper figures)

1. **Completeness**:
   - Ensure each case has both predictors and all three test episodes (`te_std_01..03`).
2. **Time Integrity**:
   - Time axis is monotonic and increments by exactly `control_interval_s=900` s.
3. **Physical Bounds**:
   - `t_zone` mostly in realistic building range (no implausible spikes).
   - `u_heating` remains within actuator bounds.
   - Power values are finite and non-pathological.
   - For cases with inferable physical floor area, power checks are performed on normalized density (`W/m2`).
4. **Comfort Consistency**:
   - Compare `t_zone` against `t_lower`/`t_upper` in time-series figures.
   - Large reported discomfort should match visible band violations.
5. **Cross-Predictor Sanity**:
   - RC and PINN trends should be directionally consistent for each episode.
   - Flag any abrupt divergence without corresponding setpoint/occupancy context.
6. **Runtime Plausibility**:
   - Inspect solve-time distribution for outliers before reporting computational cost.

## Interpretation of WARN Status

`WARN` does **not** always indicate invalid simulation output; it marks runs that need human inspection. Typical WARN reasons:

- unusually large per-step temperature jumps,
- control discontinuities,
- unusually high solve-time tails,
- schema/time-step inconsistencies.

Note on floor-area normalization: some BESTEST-style cases expose normalized KPI references that imply a unit reference area. For these cases, absolute `W/m2` plausibility checks are skipped to avoid false alarms from non-physical reference scaling.
