# WP3 Deliverables (MPC Benchmark and Tuning)

This stage covers closed-loop MPC execution, RC vs PINN comparison, and automated tuning support.

## Core Files

- `configs/mpc_phase1.yaml`
  - Baseline MPC configuration used for fair RC/PINN comparison runs.
- `scripts/run_mpc_episode.py`
  - Main episode runner for RC and PINN predictors.
- `scripts/summarize_tuning_eval.py`
  - Produces concise baseline-vs-candidate tuning reports.
- `scripts/autotune_mpc_weights.py`
  - Random-search tuner over MPC weights with score and Pareto outputs.
- `configs/mpc_phase1_tuned_v1.yaml`
- `configs/mpc_phase1_tuned_v2.yaml`
- `configs/mpc_phase1_tuned_v3.yaml`
  - Versioned manual tuning candidates kept for traceability.

## Setup-Only Full Validation Assets

- `configs/autotune_top3_full_validation.yaml`
  - Selected top-3 candidates and target episodes for expanded validation.
- `scripts/run_top3_full_validation.ps1`
  - Batch launcher for top-3 validation.
  - Dry-run by default; requires explicit `-Execute` to run commands.
- `results/mpc_tuning_eval/autotune_v1_10cand/TOP3_FULL_VALIDATION_SETUP.md`
  - Handoff note with prepared commands and safety behavior.

## Typical Commands

Run one MPC episode:

```powershell
"C:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe" scripts/run_mpc_episode.py --predictor pinn --episode te_std_01 --mpc-config configs/mpc_phase1.yaml --output-dir results/mpc_phase1/pinn
```

Run autotune campaign (example):

```powershell
"C:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe" scripts/autotune_mpc_weights.py --baseline-dir results/mpc_tuning_eval/baseline --episodes te_std_01 te_ext_01 --samples 10 --output-dir results/mpc_tuning_eval/autotune_v1_10cand
```

Dry-run top-3 full validation batch:

```powershell
./scripts/run_top3_full_validation.ps1
```

## Outputs

- `results/mpc_phase1/`: episode-level RC/PINN run outputs.
- `results/mpc_tuning_eval/*/autotune_results.csv`: per-candidate metrics.
- `results/mpc_tuning_eval/*/pareto_front.csv`: Pareto subset for comfort-energy-time tradeoff.
- `results/mpc_tuning_eval/*/autotune_summary.md`: ranked summary by normalized score.

## Notes

- BOPTEST startup can enter a queued state on longer batches.
- Recovery flags (`--recover-from-queued`, larger `--startup-timeout-s`) are included in prepared batch commands.
- Keep Protocol A (fixed settings) and Protocol B (tuned settings) conclusions separate in reports.