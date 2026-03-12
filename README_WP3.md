# WP3 Deliverables (PINN Training)

This stage trains a physics-regularized single-zone surrogate on the Phase 1 BOPTEST datasets.

## New Files

- `configs/pinn_phase1.yaml`
  - Training hyperparameters and dataset location.
- `pinn_model/data.py`
  - Dataset ingestion, feature engineering, and train-only normalization.
- `pinn_model/model.py`
  - Single-zone PyTorch PINN with RC-inspired physics term.
- `pinn_model/training.py`
  - Training loop, early stopping, one-step metrics, and rollout evaluation.
- `scripts/train_pinn.py`
  - Reproducible training entry point.

## Feature Set

The current supervised transition model uses:

- Current zone temperature.
- Outdoor air temperature.
- Global horizontal solar irradiance.
- Heating command converted to degC when stored in Kelvin.
- Control move `delta_u`.
- Time-of-day and day-of-year sine/cosine encodings.

Target:

- Next-step zone air temperature at the 15-minute control interval.

## Physics Regularization

The model predicts next temperature as:

- Current temperature.
- Plus a first-order RC-style physics increment.
- Plus a learned neural correction.

Training penalizes the magnitude of the neural correction so the network only departs from the simple thermal balance model when data support it.

## Train

```powershell
"C:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe" scripts/train_pinn.py --config configs/pinn_phase1.yaml --artifact-dir artifacts/pinn_phase1
```

## Outputs

- `artifacts/pinn_phase1/best_model.pt`
- `artifacts/pinn_phase1/history.json`
- `artifacts/pinn_phase1/metrics.json`
- `artifacts/pinn_phase1/training_config.json`

## Notes

- The current setup is a one-step surrogate with closed-loop rollout evaluation.
- The predictor intentionally excludes plant outputs such as `power_W` so the trained interface remains usable inside MPC.