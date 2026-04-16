# Paper Workflow: 30-Day 1R1C RC vs PINN

This note defines the minimal workflow for the conference paper.

## Scope

- Use the simple 1R1C RC baseline only.
- Use the trained PINN surrogate from `pinn_model/` through the MPC wrapper in `mpc/`.
- Use 30-day evaluation episodes only for the paper comparison.
- Keep the larger RC-network variants and research-only diagnostics outside the paper path.

## What To Use

- Training: `python scripts/train_pinn.py --config configs/pinn_phase1.yaml`
- MPC comparison: `python scripts/run_mpc_episode.py --predictor rc --episode te_std_01 --manifest manifests/eu/stage2/singlezone_commercial_hydronic_stage2.yaml --mpc-config configs/mpc_phase1.yaml`
- PINN comparison: `python scripts/run_mpc_episode.py --predictor pinn --episode te_std_01 --manifest manifests/eu/stage2/singlezone_commercial_hydronic_stage2.yaml --mpc-config configs/mpc_phase1.yaml --checkpoint artifacts/pinn_phase1/best_model.pt`

## Why 30 Days

- The stage-1 7-day runs are screening runs.
- The paper result should be based on the 30-day robustness protocol.
- For the single-zone case, the 30-day manifest is stored at `manifests/eu/stage2/singlezone_commercial_hydronic_stage2.yaml`.

## Keep Out Of The Paper Path

- RC topology sweeps beyond 1R1C.
- Research-only training modes that are not part of the final comparison.
- Extra campaign diagnostics unless they are needed to explain a result.

## Output Expectations

- Final training weights and physics parameters should be written by the training pipeline.
- MPC episode outputs should include the solver trace and final solver solution for auditability.
- KPI reporting should focus on thermal comfort and energy consumption.
