# Phase 1 Full Campaign Execution Guide

## Campaign Overview
- **Total episodes**: 30 (5 cases × 2 predictors × 3 episodes)
- **Estimated runtime**: 18-24 hours
- **Start time**: 2026-03-18 (auto-populated)
- **Expected completion**: ~2026-03-19 (18:00-00:00 UTC)

## Real-Time Monitoring

### Primary Monitor (Live Progress)
Open a **new PowerShell window** and run:

```powershell
cd "c:\Users\AVoelser\OneDrive - Scientific Network South Tyrol\3_PhD\Simulation\PINN"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/monitor_campaign.ps1
```

**Shows**:
- Current state (running/completed/stopped)
- Cases completed/total
- Current case and step being executed
- Elapsed time and estimated remaining time
- Any errors encountered

### Detailed Campaign Log
Current execution log: `logs/eu_campaign_stage1/campaign.log`

Per-case detailed logs:
```
logs/eu_campaign_stage1/[case_name].log
```

### Live Status JSON
For programmatic access: `results/eu_rc_vs_pinn/runtime_discovery/campaign_live_status.json`

Contains:
- `state`: "starting" | "preflight" | "running" | "completed" | "stopped"
- `completed_cases` / `total_cases`: progress counter
- `current_case`: case name currently executing
- `current_step`: ("dataset_generation", "rc_episode", "pinn_episode")
- `step_elapsed_s`: seconds spent on current step

## Pausing the Campaign

### Graceful Pause (Recommended)
If you need to stop the campaign:

```powershell
# 1. Ctrl+C in the runner terminal (gracefully stops)
# 2. Wait ~30 seconds for cleanup

# 3. Check status:
Get-Content "results/eu_rc_vs_pinn/runtime_discovery/campaign_live_status.json" -Raw | ConvertFrom-Json | Select-Object state, completed_cases, total_cases, current_case
```

### Resume from Checkpoint
After pausing, resume with **automatic checkpoint detection**:

```powershell
cd "c:\Users\AVoelser\OneDrive - Scientific Network South Tyrol\3_PhD\Simulation\PINN"
& ".venv/Scripts/python.exe" -u scripts/run_eu_campaign_stage1.py --url http://127.0.0.1:8000 --resume
```

The runner will automatically:
- Skip already-completed cases
- Skip already-generated datasets
- Resume from the next incomplete case/step

### Force Stop (if needed)
If graceful shutdown fails:

```powershell
# Kill all Python runners
$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match "python(\.exe)?" -and $_.CommandLine -match "run_eu_campaign_stage1.py|run_mpc_episode.py"
}
$procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Clean up BOPTEST queue (optional)
$redis = 'project1-boptest-redis-1'
docker exec $redis redis-cli DEL jobs
docker exec $redis redis-cli EVAL "for _,k in ipairs(redis.call('keys','tests:*')) do redis.call('del',k) end" 0
```

## Expected Results Structure

After completion, you'll have:
```
results/eu_rc_vs_pinn/
├── raw/                                    # Raw MPC episode outputs
│   ├── singlezone_commercial_hydronic/
│   │   ├── rc/         (te_std_01.json, te_std_02.json, te_std_03.json)
│   │   └── pinn/
│   ├── bestest_hydronic/
│   │   ├── rc/
│   │   └── pinn/
│   ├── bestest_hydronic_heat_pump/
│   │   ├── rc/
│   │   └── pinn/
│   ├── multizone_residential_hydronic/
│   │   ├── rc/
│   │   └── pinn/
│   └── twozone_apartment_hydronic/
│       ├── rc/
│       └── pinn/
├── qc/                                   # Quality assurance reports
│   ├── plausibility_summary.csv           # Status per run (PASS/WARN)
│   ├── plausibility_report.json           # Detailed issues
│   ├── kpi_table.csv                      # Performance metrics
│   ├── overview/                          # Summary plots
│   └── timeseries/                        # Per-episode time-series plots
└── runtime_discovery/
    └── campaign_live_status.json          # Current progress (live)
```

## Post-Completion Steps

1. **Review QC Report**:
   ```powershell
   Get-Content "results/eu_rc_vs_pinn/qc/plausibility_summary.csv" | head -20
   ```

2. **Inspect WARN Episodes** (if any):
   Check the 3 singlezone_commercial episodes in detail:
   ```powershell
   Get-Content "results/eu_rc_vs_pinn/raw/singlezone_commercial_hydronic/rc/te_std_01.json" | ConvertFrom-Json | Select-Object -ExpandProperty power_W | Measure-Object -Maximum
   ```

3. **Generate Detailed Analysis**:
   ```powershell
   python.exe -u scripts/qc_eu_results.py
   ```

## Troubleshooting

**Campaign won't start**:
- Check BOPTEST is running: `curl http://127.0.0.1:8000/version`
- Check Docker: `docker ps | grep boptest`

**Campaign stuck on a case**:
- Check case log: `tail -f logs/eu_campaign_stage1/[case_name].log`
- Check BOPTEST queue: `docker exec project1-boptest-redis-1 redis-cli LLEN jobs`
- If queue > 10, may need to restart workers

**Monitor shows "calculating..." for estimated time**:
- This is normal in first ~30 minutes; average per-case time will stabilize

## Notes
- All trained PINN models are in `artifacts/eu/[case_name]/best_model.pt` (preserved)
- Campaign is checkpoint-resumable at case/step granularity
- QC analysis auto-generates after all cases are complete
