# Top-3 Full Validation Setup (Prepared, Not Executed)

This setup was prepared after autotune run `results/mpc_tuning_eval/autotune_v1_10cand`.
No full-validation commands have been executed yet.

## Selected candidates
- `cand_005`
- `cand_008`
- `cand_001`

## Plan file
- `configs/autotune_top3_full_validation.yaml`

## Launcher script
- `scripts/run_top3_full_validation.ps1`

The launcher script behavior:
- Default: dry-run only (prints all commands, executes none)
- Execution mode: requires explicit `-Execute`

## Dry-run preview (safe)

```powershell
./scripts/run_top3_full_validation.ps1
```

## Execute later (when approved)

```powershell
./scripts/run_top3_full_validation.ps1 -Execute
```

## Notes
- Python executable default is `.venv/Scripts/python.exe`.
- Startup recovery flags are included for BOPTEST queue instability:
  - `--recover-from-queued`
  - `--startup-timeout-s 1800`
- Output root (from plan) is:
  - `results/mpc_tuning_eval/autotune_v1_10cand/full_validation`
