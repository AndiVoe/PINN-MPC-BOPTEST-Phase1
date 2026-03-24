# Results Layout for Publication Audit

This folder is organized so all intermediate and final outputs can be manually inspected.

## Expected Key Artifacts

1. Stage 1 screening summaries:
   - results/eu_rc_vs_pinn/summary_stage1.csv
2. Stage 2 long-horizon summaries:
   - results/eu_rc_vs_pinn/summary_stage2.csv
3. RC selection table:
   - results/eu_rc_vs_pinn/model_selection.csv
4. Discomfort parity report:
   - results/mpc_phase1/discomfort_parity_report.csv
5. Publication bundle metadata:
   - results/eu_rc_vs_pinn/publication_bundle/bundle_manifest.json
   - results/eu_rc_vs_pinn/publication_bundle/file_index.csv

## Manual Validation Checklist

1. Confirm paired RC/PINN runs use identical testcase, split, start time, dt, and step count.
2. Inspect KPI columns for each episode and verify no missing values.
3. Review discomfort parity flags and annotate interpretation in manuscript notes.
4. Verify SHA256 checksums in file_index.csv for all files used in publication tables.

## Retention Policy

Keep all raw episode JSON files, aggregate CSV files, and bundle metadata for the full publication lifecycle.

## Current Article Table Snapshot (March 19, 2026)

The following values are derived from `results/eu_rc_vs_pinn/raw/*/*/*.json` and are synchronized with the manuscript/outline tables.

### Case-level comfort comparison

| Case | RC Comfort (Kh) | PINN Comfort (Kh) | Delta (PINN - RC) | Relative Change | Better |
|---|---:|---:|---:|---:|---|
| bestest_hydronic | 71.1 | 65.6 | -5.6 | -7.9% | PINN |
| bestest_hydronic_heat_pump | 18.9 | 91.1 | +72.2 | +381.9% | RC |
| singlezone_commercial_hydronic | 12.8 | 5.3 | -7.5 | -58.5% | PINN |
| twozone_apartment_hydronic | 190.6 | 105.0 | -85.6 | -44.9% | PINN |

### Cross-case aggregate summary

| Predictor | Cases included | Mean comfort (Kh) | Mean challenge discomfort (tdis_tot) | Mean energy (Wh) | Mean challenge cost (cost_tot) | Mean peak power (W) | Mean wall time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| RC | 4 | 73.37 | 105.06 | 1677987.60 | 0.097347 | 32787.62 | 46.33 |
| PINN | 4 | 66.76 | 89.70 | 888679.60 | 0.077169 | 30192.75 | 388.18 |

### Completion note

- Completed in article set: `bestest_hydronic`, `bestest_hydronic_heat_pump`, `singlezone_commercial_hydronic`, `twozone_apartment_hydronic` (all 3 RC + 3 PINN episodes each).
