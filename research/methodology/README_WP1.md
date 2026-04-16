# WP1 Deliverables (Signal Contract and Experiment Manifest)

This folder contains the locked interfaces for the PINN vs white-box MPC study.

## Files

- `data_contract/signal_contract.yaml`: Canonical variable definitions and fairness constraints.
- `data_contract/dataset_schema.json`: Data schema for train/val/test episodes.
- `manifests/phase1_singlezone.yaml`: Phase 1 experiment settings.
- `configs/metrics_catalog.yaml`: KPI and runtime metric definitions.
- `scripts/validate_contract.py`: Basic consistency checks.

## Validate

1. Ensure Python environment has `pyyaml`.
2. Run:

```powershell
python scripts/validate_contract.py
```

## Next (WP2)

- Implement episode generator from BOPTEST using this schema.
- Build split manifest with explicit train/val/test episode IDs.
- Add weather class tags (`standard` or `extreme`) per episode.
