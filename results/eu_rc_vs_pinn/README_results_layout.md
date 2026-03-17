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
