# Stage2 RC Variant Utilities

This folder contains RC-variant benchmarking helpers for the EU campaign.

## Run RC Variant Campaign

From repository root:

```powershell
& ".venv/Scripts/python.exe" -u scripts/stage2/run_eu_rc_variant_campaign.py --episode te_std_01 --url http://127.0.0.1:8000 --max-cases 5 --startup-timeout-s 1200
```

## Analyze Best RC vs PINN

```powershell
& ".venv/Scripts/python.exe" -u scripts/stage2/analyze_rc_variants_vs_pinn.py --rc-root results/eu_rc_vs_pinn_stage2/raw --pinn-root results/eu_rc_vs_pinn/raw --episode te_std_01 --out-json results/eu_rc_vs_pinn_stage2/best_rc_vs_pinn_summary.json
```

## Stage2 Config

RC variant definitions are stored in:

- `configs/eu/stage2/rc_variants.yaml`
