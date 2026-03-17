# PINN Building Control Simulation

This repository contains the Phase 1-3 workflow for training a Physics-Informed Neural Network (PINN) surrogate and benchmarking MPC performance against an RC predictor using BOPTEST test cases.

## Main Components

- `pinn_model/`: PINN data pipeline, model definition, and training loop.
- `mpc/`: MPC client, predictors, solver, occupancy, and KPI utilities.
- `scripts/`: dataset generation, training, MPC execution, validation, and campaign automation.
- `configs/`: YAML configurations for PINN training, MPC setup, and campaign runs.
- `manifests/`: episode split and case-specific manifest files.
- `datasets/`, `artifacts/`, `results/`: generated inputs, trained model artifacts, and benchmark outputs.

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Validate contracts and dataset files:
	- `python scripts/validate_contract.py`
	- `python scripts/validate_dataset_files.py`
4. Train PINN:
	- `python scripts/train_pinn.py --config configs/pinn_phase1.yaml`
5. Run MPC benchmarks:
	- `python scripts/run_mpc_episode.py --predictor rc --episode all-test`
	- `python scripts/run_mpc_episode.py --predictor pinn --episode all-test --checkpoint artifacts/pinn_phase1/best_model.pt`

## Additional Documentation

- `README_WP1.md`: data and contract-related workflow notes.
- `README_WP2.md`: PINN modeling and training workflow notes.
- `README_WP3.md`: MPC benchmark and campaign workflow notes.
- `execution_plan_pinn_vs_eplus.md`: detailed execution plan.
