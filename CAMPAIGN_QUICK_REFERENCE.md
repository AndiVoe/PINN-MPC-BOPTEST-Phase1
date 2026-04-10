# Campaign Monitoring & Control - Quick Reference

**Status**: Campaign running (launched 2026-03-18 14:05)  
**Est. Completion**: 2026-03-19 08:00-12:00 UTC  
**Duration**: 18-24 hours (30 episodes total)

---

## ðŸŸ¢ Real-Time Monitoring

### Live Progress Monitor (Recommended)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/monitor_campaign.ps1
```
**Shows**: Cases completed/total, current step, elapsed time, estimated time remaining

### Poll Every 10 Seconds
```powershell
while($true){ 
  $s=Get-Content results/eu_rc_vs_pinn/runtime_discovery/campaign_live_status.json -Raw | ConvertFrom-Json; 
  $elapsed=[int]((Get-Date)-[DateTime]$s.started_utc).TotalSeconds;
  Write-Host "`r[$([DateTime]::Now.ToString('HH:mm:ss'))] $($s.completed_cases)/$($s.total_cases) cases | $($s.current_case) [$($s.current_step)] | Elapsed: $('{0:D2}:{1:D2}:{2:D2}' -f [int]($elapsed/3600), [int](($elapsed%3600)/60), $elapsed%60)" -NoNewline;
  Start-Sleep -Seconds 10
}
```

### Tail Live Log
```powershell
tail -f logs/eu_campaign_stage1/campaign.log
```

### Check Status Once
```powershell
Get-Content results/eu_rc_vs_pinn/runtime_discovery/campaign_live_status.json -Raw | ConvertFrom-Json | Select-Object completed_cases, total_cases, current_case, current_step, state
```

---

## â¸ Pausing the Campaign

### Graceful Stop
1. **Find runner window** and press **Ctrl+C** (recommended)
2. **Wait 30 seconds** for cleanup
3. **Verify stopped**:
```powershell
Get-Content results/eu_rc_vs_pinn/runtime_discovery/campaign_live_status.json -Raw | ConvertFrom-Json | Select-Object state, completed_cases, current_case
```

### Resume From Checkpoint
All progress is preserved. Resume with:
```powershell
cd "c:\Users\AVoelser\OneDrive - Scientific Network South Tyrol\3_PhD\Simulation\PINN"
& ".venv/Scripts/python.exe" -u scripts/run_eu_campaign_stage1.py --url http://127.0.0.1:8000 --resume
```

---

## ðŸ”´ Force Stop (Emergency Only)

```powershell
# Kill all Python runners
Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -match "run_eu_campaign_stage1.py|run_mpc_episode.py"} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force}

# Optional: Clean BOPTEST queue
$redis = 'project1-boptest-redis-1'
docker exec $redis redis-cli DEL jobs
docker exec $redis redis-cli EVAL "for _,k in ipairs(redis.call('keys','tests:*')) do redis.call('del',k) end" 0
```

### BOPTEST Reset Helper

Use this when the API is alive but the queue or worker is stuck:

```powershell
# Soft reset: stop active tests, then restart web/worker/redis containers
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/reset_boptest.ps1

# Hard reset: clean compose redeploy after stopping active tests
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/reset_boptest.ps1 -Hard -ComposeFile "path/to/docker-compose.yml"
```

Order of preference:
1. Use the soft reset first.
2. Use the hard reset if stale queue state survives the soft restart.
3. Resume the campaign only after `/version` responds and `LLEN jobs` is back to 0.

---

## ðŸ“Š Per-Case Log Files

Check detailed logs for any specific case:
```powershell
# View case log (replace with case name)
tail -f logs/eu_campaign_stage1/singlezone_commercial_hydronic.log
tail -f logs/eu_campaign_stage1/bestest_hydronic.log
tail -f logs/eu_campaign_stage1/bestest_hydronic_heat_pump.log
tail -f logs/eu_campaign_stage1/twozone_apartment_hydronic.log
```

---

## ðŸ“ˆ Timeline

| Case                 | Est. Duration | Est. Window       |
|----------------------------|---------|-------------------|
| singlezone_commercial      | 4-5 hrs | 14:08 - 18:00 Wed |
| bestest_hydronic           | 3-4 hrs | 18:00 - 22:00 Wed |
| bestest_hydronic_heat_pump | 4-5 hrs | 22:00 - 03:00 Thu |
| multizone_residential      | 4-5 hrs | 03:00 - 08:00 Thu |
| twozone_apartment          | 3-4 hrs | 08:00 - 12:00 Thu |

---

## ðŸ“‚ Results After Completion

```
results/eu_rc_vs_pinn/
â”œâ”€â”€ raw/                           # 30 episode outputs (JSON)
â”‚   â”œâ”€â”€ [case_name]/
â”‚   â”‚   â”œâ”€â”€ rc/     (te_std_01.json, te_std_02.json, te_std_03.json)
â”‚   â”‚   â””â”€â”€ pinn/
â”‚   â””â”€â”€ ...
â”œâ”€â”€ qc/                            # Quality assurance reports
â”‚   â”œâ”€â”€ plausibility_summary.csv    # PASS/WARN per run
â”‚   â”œâ”€â”€ kpi_table.csv              # Performance metrics
â”‚   â”œâ”€â”€ overview/                  # Summary plots
â”‚   â””â”€â”€ timeseries/                # Episode plots
â””â”€â”€ runtime_discovery/
    â””â”€â”€ campaign_live_status.json   # Live progress (updated during run)
```

---

## ðŸ”§ Troubleshooting

### Startup Reliability (Updated)

- `scripts/run_eu_campaign_stage1.py` now auto-discovers testcase mapping when
  `results/eu_rc_vs_pinn/runtime_discovery/eu_testcases_resolved_mapping.json`
  is missing.
- Discovery output and errors are logged to:
  `logs/eu_campaign_stage1/discover_mapping.log`

**Recommended launch command**
```powershell
& ".venv/Scripts/python.exe" -u scripts/run_eu_campaign_stage1.py --url http://127.0.0.1:8000 --resume
```

**Startup hardening defaults (enabled automatically)**
- Queue fail-fast guard: `--max-queue-jobs 12 --max-queued-tests 6`
- Step retries with exponential backoff: `--step-max-retries 2 --step-retry-backoff-s 20`

**Disable auto-discovery only for debugging**
```powershell
& ".venv/Scripts/python.exe" -u scripts/run_eu_campaign_stage1.py --url http://127.0.0.1:8000 --no-auto-discover-mapping
```

**Tune reliability behavior (optional)**
```powershell
# Stricter queue guard (abort earlier under contention)
& ".venv/Scripts/python.exe" -u scripts/run_eu_campaign_stage1.py --url http://127.0.0.1:8000 --resume --max-queue-jobs 8 --max-queued-tests 4

# More tolerant retries for unstable infrastructure
& ".venv/Scripts/python.exe" -u scripts/run_eu_campaign_stage1.py --url http://127.0.0.1:8000 --resume --step-max-retries 3 --step-retry-backoff-s 30
```

**Campaign won't start?**
```powershell
# Check BOPTEST
curl http://127.0.0.1:8000/version

# Check Docker
docker ps | grep boptest

# Check queue
docker exec project1-boptest-redis-1 redis-cli LLEN jobs
```

**Stuck on a case?**
```powershell
# Check case log
tail logs/eu_campaign_stage1/[case_name].log

# Check BOPTEST queue size (if > 10, may need restart)
docker exec project1-boptest-redis-1 redis-cli LLEN jobs
```

**Campaign stops with `blocked_queue` state?**
```powershell
# Inspect last status (state, error, case)
Get-Content results/eu_rc_vs_pinn/runtime_discovery/campaign_live_status.json -Raw | ConvertFrom-Json | Select-Object state, last_error, current_case, current_step

# Inspect queue pressure
docker exec project1-boptest-redis-1 redis-cli LLEN jobs
docker exec project1-boptest-redis-1 redis-cli --raw EVAL "local q=0; local r=0; local t=0; for _,k in ipairs(redis.call('keys','tests:*')) do t=t+1; local s=redis.call('hget',k,'status'); if s=='Queued' then q=q+1 elseif s=='Running' then r=r+1 end; end; return {t,q,r}" 0
```

---

## ðŸ“ See Also

- **Full documentation**: [CAMPAIGN_EXECUTION_GUIDE.md](CAMPAIGN_EXECUTION_GUIDE.md)
- **Campaign runner**: [scripts/run_eu_campaign_stage1.py](scripts/run_eu_campaign_stage1.py)
- **Monitor script**: [scripts/monitor_campaign.ps1](scripts/monitor_campaign.ps1)
