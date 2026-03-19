# Protocol A Readiness Status

Date: 2026-03-19

## Scope
Case checked: bestest_hydronic_heat_pump
Protocol: A (fixed-weight fairness)
Manifest used: manifests/eu/bestest_hydronic_heat_pump_stage1_protocol_a.yaml

## Completed (no further Docker action needed)
- Protocol A fairness manifest exists and has no predictor-specific MPC overrides.
- RC reference episode completed successfully:
  - results/eu_rc_vs_pinn/protocol_a_fixed/raw/bestest_hydronic_heat_pump/rc/te_std_01.json

## Blocked by shared Docker queue load
- PINN counterpart episode could not start (BOPTEST stayed in Queued until timeout).
- This occurred even with extended startup timeout and one-time queued recovery logic.

## Resume Command (when Docker is free)
Use exactly this command to finish the paired check:

c:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe -u scripts/run_mpc_episode.py --predictor pinn --episode te_std_01 --manifest manifests/eu/bestest_hydronic_heat_pump_stage1_protocol_a.yaml --mpc-config configs/mpc_phase1.yaml --checkpoint artifacts/eu/bestest_hydronic_heat_pump/best_model.pt --output-dir results/eu_rc_vs_pinn/protocol_a_fixed/raw/bestest_hydronic_heat_pump --url http://127.0.0.1:8000 --case bestest_hydronic_heat_pump --startup-timeout-s 1200 --recover-from-queued --resume-existing

## After PINN finishes
Run parity check for this case folder:

c:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe -u scripts/validate_discomfort_parity.py --results-root results/eu_rc_vs_pinn/protocol_a_fixed/raw/bestest_hydronic_heat_pump --output results/eu_rc_vs_pinn/protocol_a_fixed/discomfort_parity_report_bestest_hydronic_heat_pump.csv
