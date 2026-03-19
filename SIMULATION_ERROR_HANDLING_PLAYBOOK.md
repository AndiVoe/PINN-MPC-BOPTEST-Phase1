# Simulation Error-Handling Playbook (BOPTEST + Campaign Runner)

This playbook captures recurring failure modes and proven recovery steps observed during EU RC vs PINN campaign execution.

## 1) Typical Failure Modes

1. **BOPTEST startup stuck in `Queued`**
- Symptom: startup polling stays in `Queued` until timeout.
- Impact: dataset generation or benchmark run fails before first step.

2. **Stale `Running/Queued` tests in Redis**
- Symptom: API appears alive, but new tests never start, queue growth or blocked execution.
- Impact: false stalls and repeated retries.

3. **Signal resolution failures**
- Symptom: `Could not resolve T_zone signal for episode` or control signal unresolved.
- Impact: episodes fail, partial/empty datasets, downstream training failure.

4. **Fractional completion masking missing outputs**
- Symptom: campaign marks case complete while not all `te_std_*` files exist.
- Impact: false-positive completion statistics.

5. **Duplicate orchestrator / benchmark processes**
- Symptom: multiple `run_eu_campaign_stage1.py` or `run_mpc_episode.py` instances.
- Impact: race conditions, confusing logs, unstable queue behavior.

6. **Training fails after dataset generation**
- Symptom: loader errors such as missing expected fields in index/episode references.
- Impact: benchmark stage blocked.

## 2) Quick Triage Sequence

Run these checks in order before restarting long jobs.

1. **API liveness**
```powershell
curl.exe -s -o NUL -w "code=%{http_code} time=%{time_total}\n" http://127.0.0.1:8000/version
curl.exe -s -o NUL -w "code=%{http_code} time=%{time_total}\n" http://127.0.0.1:8000/testcases
```

2. **Queue and active tests**
```powershell
$redis='project1-boptest-redis-1'
docker exec $redis redis-cli LLEN jobs
docker exec $redis redis-cli --raw EVAL "local q=0; local r=0; local t=0; for _,k in ipairs(redis.call('keys','tests:*')) do t=t+1; local s=redis.call('hget',k,'status'); if s=='Queued' then q=q+1 elseif s=='Running' then r=r+1 end; end; return {t,q,r}" 0
```

3. **Duplicate process check**
```powershell
Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match 'python(\.exe)?' -and $_.CommandLine -match 'run_eu_campaign_stage1.py|run_mpc_episode.py'
} | Select-Object ProcessId,CommandLine
```

## 3) Safe Recovery Actions

1. **Stop active BOPTEST tests**
```powershell
$redis='project1-boptest-redis-1'
$active=docker exec $redis redis-cli --raw EVAL "local out={}; for _,k in ipairs(redis.call('keys','tests:*')) do local s=redis.call('hget',k,'status'); if s=='Queued' or s=='Running' then table.insert(out,k..'='..s) end end; return out" 0
foreach($line in $active){
  if($line -match '^tests:([^=]+)='){
    $id=$Matches[1]
    Invoke-RestMethod -Method Put -Uri ("http://127.0.0.1:8000/stop/{0}" -f $id) -TimeoutSec 30 | Out-Null
  }
}
```

2. **Ensure single orchestrator instance**
- Keep exactly one runner process.
- Kill duplicate runner/episode processes only (not unrelated Python jobs).

3. **Rerun with resume**
```powershell
& ".venv/Scripts/python.exe" -u scripts/run_eu_campaign_stage1.py --url http://127.0.0.1:8000 --resume
```

4. **Case-level clean recovery (if one case keeps failing)**
- Remove only failing case dataset/artifact/output directories.
- Regenerate dataset for that case.
- Retrain case PINN.
- Rerun case RC and PINN all-test episodes.

## 4) Hardening Practices That Worked

1. **Use strict completion criteria**
- Treat a case as complete only if all expected test episode outputs exist for both predictors.

2. **Preserve curated manifests/configs**
- Avoid auto-overwriting corrected per-case signal mappings.

3. **Probe real BOPTEST signals when mapping fails**
- Validate candidate zone/control signals from live `/measurements` and `/inputs` payloads.

4. **Prefer incremental recovery**
- Fix one failing case at a time.
- Revalidate queue/process health between retries.

5. **Separate data plausibility QC from runtime health checks**
- Runtime health: API, queue, process uniqueness.
- Data QC: schema integrity, physical bounds, timeseries plausibility.

## 5) Post-Run Validation Checklist

1. Confirm per-case completeness: `rc=3` and `pinn=3` test files.
2. Run QC plots/checks:
```powershell
& ".venv/Scripts/python.exe" -u scripts/qc_eu_results.py
```
3. Inspect `results/eu_rc_vs_pinn/qc/plausibility_summary.csv` for WARN cases.
4. Inspect corresponding timeseries figures for paper-quality interpretation.

## 6) Notes for Future Incidents

- `Queued` loops are usually infrastructure/state issues, not model logic issues.
- Signal resolution errors are usually manifest mapping issues, not optimizer instability.
- Incomplete or malformed datasets propagate into training errors; always validate dataset index before retraining.
- Duplicate orchestrator processes can create misleading progress signals and should be eliminated early.

## 7) 2026-03-19 Incident Update (Applied Fixes)

1. **Heat-pump control mapping hardening in dataset generation**
- Issue observed: heat-pump datasets were generated with `meta.control_signal = null`, forcing fallback to heating proxy and weakening retraining quality.
- Fix applied: generator now prioritizes explicit manifest control mapping before candidate auto-resolution for control value/activate signals.
- Verification command:
```powershell
$hp = Get-ChildItem 'datasets/eu/bestest_hydronic_heat_pump/json/*.json'
foreach($f in $hp){
  $j = Get-Content $f.FullName -Raw | ConvertFrom-Json
  "{0}: control_signal={1}; activate_signal={2}; heating_proxy={3}" -f $f.Name, $j.meta.control_signal, $j.meta.activate_signal, $j.meta.heating_proxy_signal
}
```

2. **Heat-pump case manifest alignment for control candidates**
- Issue observed: auto-generated manifest variants could omit or mis-prioritize the intended heat-pump control channel.
- Fix applied: ensured heat-pump case mapping keeps the correct control path (`oveTSet_u` + `oveTSet_activate`) and candidate list includes these first.

3. **Strict fairness validation path (Protocol A) executed**
- Issue observed: predictor-specific overrides can mask root-cause diagnosis.
- Fix applied: use Protocol A manifests (no predictor-specific overrides) for confirmation runs before broader campaign conclusions.

4. **Live status interpretation for operational decisions**
- Rule used today: treat `finished_with_failures` as terminal for campaign bookkeeping, and treat `running` as active for partial-result checkpoint pushes.
- Check command:
```powershell
Get-Content results/eu_rc_vs_pinn_heating/runtime_discovery/campaign_live_status.json -Raw
```

5. **PowerShell invocation reliability for Python commands**
- Use call operator form to avoid command parsing edge cases:
```powershell
& ".venv/Scripts/python.exe" -m py_compile scripts/run_eu_campaign_stage1.py
```
