# FMU/Model Diagnostics for Heat-Pump and Multizone Cases

## Heat-Pump FMU (`bestest_hydronic_heat_pump`)

### Control Signal
- **Channel**: `oveTSet_u` (zone setpoint override)
- **Units**: Kelvin
- **Bounds**: 278.15 K (5Â°C) to 308.15 K (35Â°C)
- **Status**: âœ“ Valid and correctly mapped in manifest

### Dynamic Response (Sanity Check)
Probe: Two runs with low (19.66Â°C mean) vs high (22.53Â°C mean) setpoints

| Metric | Low | High | Delta |
|--------|-----|------|-------|
| Zone T (end) | 19.66Â°C | 23.74Â°C | +4.08Â°C |
| Zone T (mean) | 20.34Â°C | 22.53Â°C | +2.19Â°C |
| HP Power (mean) | 0 W | 3347.8 W | +3347.8 W |
| Pump Power | 0 W | 0 W | â€” |

**Conclusion**: FMU signal is **physically correct**. Higher setpoint â†’ higher zone T â†’ heat pump activates with meaningful power output.

### Current MPC Issues
- **Problem**: PINN controller locks to `u_min` (19Â°C) in fixcheck, causing QC warning.
- **Root cause**: NOT signal/FMU bug. Likely model-side: PINN predictor confidence loss (very high solve times, solver struggle) â†’ optimizer defaults to safe lower bound.
- **Recommended action**: Tune PINN-specific weights or add anti-saturation term, not signal fixes.

---


### Available Control Channels

#### Setpoint-Based (Currently Used)
- **Channels**: `conHeaLiv_oveTSetHea_u`, `conHeaRo1_oveTSetHea_u`, etc. (5 zones)
- **Units**: Kelvin
- **Bounds**: 283.15 K (10Â°C) to 368.15 K (95Â°C)
- **Activation**: 5 corresponding `_activate` channels

#### Direct Actuation (Available but Not Used)
- **Channels**: `conHeaLiv_oveActHea_u`, `conHeaRo1_oveActHea_u`, etc. (5 zones)
- **Units**: 0â€“1 (fraction)
- **Activation**: 5 corresponding `_activate` channels

#### System-Level Controls
- `oveEmiPum_u`: Emission pump (0â€“1)
- `oveMixValSup_u`: Mixing valve (0â€“1)
- `oveTSetPumBoi_u`: Boiler pump setpoint (283.15â€“368.15 K)
- `oveTSetSup_u`: Supply temperature (283.15â€“368.15 K)

### Coupling Probes (Results)

#### Probe 1: Setpoint Variation (Standard Conditions)
Command: Living zone +2 K higher than other zones
```
All zones: delta_end_C = 0.0
Pump power: delta_mean = 0 W
HP power: delta_mean = 0 W
```
**Interpretation**: No observable coupling response to zone setpoint differences alone.

#### Probe 2: Direct Actuation (Standard Conditions)
Command: Living zone fully actuated (u=1.0); other zones off (u=0)
```
All zones: delta_end_C = 0.0
Boiler: delta_mean = 0 W
Total power: delta_mean = 0 W
```
**Interpretation**: Even direct actuation shows no coupling. Likely indicates:
- Zone loop is thermally isolated in FMU
- OR emissions/pump not responding to individual zone signals
- OR boiler/supply not modulated by zone demands

### Multizone Architecture Implications

1. **Zones are Decoupled Thermally**
   - Each zone does not affect other zones directly.
   - Changing one zone's setpoint/actuation does not alter neighboring zone temperatures.

2. **Shared Infrastructure Not Modulated**
   - Boiler, pump, supply temp do not respond to individual zone demand changes.
   - Suggests system-level controls (`oveTSetSup_u`, `oveTSetPumBoi_u`) must be driven separately.
   - Current MPC only drives zone setpoints; it ignores system-level orchestration.

3. **Why Multizone RC Saturates at u_max**
   - With decoupled zones, each zone tries to maximize its own comfort independently.
   - All zones converge to high setpoints (u_max â‰ˆ 368 K / 95Â°C) trying to heat simultaneously.
   - No cooperative control strategy; no system-level balancing.

### Current MPC Limitation
- **Single-zone PINN predictor** cannot represent inter-zone coupling (even if weak).
- **No system-level control**: boiler/pump/supply setpoints are never touched in current setup.
- **Zone averaging hides structure**: Averaging zone temperatures masks the fact that zones don't interact through the model.

---

## Recommendations

### Heat-Pump (`bestest_hydronic_heat_pump`)
1. **Keep current signal mapping** (it's correct).
2. **Diagnose PINN solver strain**:
   - Why does PINN take 800â€“5000 ms per step vs RC at 2â€“3 ms?
   - Is it due to PINN prediction uncertainty or objective stiffness?
3. **Consider**:
   - Increase regularization/smoothing weight in PINN-specific MPC config.
   - OR add explicit anti-saturation penalty (penalize u too near bounds).
   - Rerun te_std_01..03 with tuned PINN-specific weights.

### PINN Loss Weighting Comparison (new)

Three training weighting strategies are now implemented in the training stack and configurable via `training.loss_weighting.mode`:
- `manual`
- `gradient_balance`
- `uncertainty`

Quick smoke benchmark (3 epochs, same seed/data/model):

| Mode | Val RMSE (degC) | Val rollout RMSE (degC) | Test RMSE (degC) | Test rollout RMSE (degC) |
|------|------------------|-------------------------|------------------|--------------------------|
| manual | 0.0717 | 0.5269 | 0.0850 | 0.8771 |
| gradient_balance | 0.0979 | 4.0472 | 0.1243 | 4.9132 |
| uncertainty | 0.0860 | 3.1522 | 0.1113 | 4.1580 |

Interim conclusion:
- For the current data regime, **manual weighting is strongest** on one-step and rollout metrics.
- Keep manual as default for production retraining.
- Gradient/uncertainty modes remain available for later use if dataset noise profile changes.

1. **Acknowledge architectural limitation**: Zones are thermally independent in FMU.
2. **Current MPC approach is not optimal** for a lack of true multizone coupling.
3. **Options**:
   - **A (Easy, Risky)**: Treat each zone independently; apply PINN predictor per zone â†’ 5 separate PINN models (or extend single PINN).
   - **B (Rigorous)**: Extend MPC to include system-level controls (`oveTSetSup_u`, `oveTSetPumBoi_u`); define objective that avoids simultaneous all-zones-high-demand saturation.
   - **C (Current Status)**: Accept that multizone control is not meaningful for inter-zone optimization; focus on within-zone comfort trade-offs (energy vs comfort per zone).
4. **Next action**: If pursuing **B**, redesign MPC 
   - Define per-zone or aggregate comfort metrics.
   - Add system-level supply control to modulate available power.
   - Retrain/extend PINN to predict zone temps given (system setpoint, zone setpoint, boiler state).

---

## Summary Table

| Aspect | Heat-Pump | Multizone |
|--------|-----------|-----------|
| **Signal Validity** | âœ“ Correct | âœ“ Correct |
| **FMU Dynamics** | âœ“ Responsive | âš  Decoupled zones |
| **Coupling Strength** | N/A | None (zones independent) |
| **Current MPC Fit** | Reasonable | Poor (no inter-zone optimization) |
| **Saturation Root Cause** | PINN solver/model uncertainty | Decoupled zone control â†’ simultaneous high demand |
| **Recommended Action** | Tune PINN regularization | Extend MPC to system controls or accept zone-independent control |

## BOPTEST/Docker Error Handling Guide

### Overview
BOPTEST infrastructure has multiple independent failure modes affecting episode startup and execution:
1. **Web container crash** (API unavailable, test selection fails)
2. **Redis job queue saturation** (tests stuck in `Queued` state indefinitely)
3. **Worker pool exhaustion** (`advance()` calls timeout waiting for FMU response)
4. **Stale test lingering** (previous runs leave zombie tests blocking new selections)

**Key principle**: BOPTEST can appear healthy on basic health checks while episodes fail. Always verify **both API status AND Redis state AND active test count** before assuming infrastructure is ready.

---

### Failure Mode 1: Web Container Down

**Symptoms:**
- `curl http://127.0.0.1:8000/version` returns HTTP 000 (connection refused)
- `curl http://127.0.0.1:8000/testcases` returns HTTP 000
- Test selection fails immediately with "Connection refused" or HTTP timeout

**Diagnosis:**
```powershell
# Check if web container is running
docker ps | grep boptest-web

# If not listed, container is down
# Check logs for startup errors
docker logs project1-boptest-web-1
```

**Recovery:**
```powershell
# Option A: Restart single container (fast)
docker restart project1-boptest-web-1

# Option B: Full stack redeploy (thorough, slower)
docker compose -f path/to/docker-compose.yml down
docker compose -f path/to/docker-compose.yml up -d web worker provision
```

**Validation:**
```powershell
# Probe API recovery (repeat 5â€“10 times with 3s delay)
for($i=0; $i -lt 10; $i++) {
  Start-Sleep -Seconds 3
  $code = curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8000/version
  "probe=$i code=$code"
}
# Expected: 200 (not 000, not 500)
```

---

### Failure Mode 2: Redis Queue Saturation

**Symptoms:**
- Test startup hangs in `Queued` state for >120 seconds
- `redis LLEN jobs` shows 10+ pending tasks
- `tests:*:status` shows many entries with `Queued` state
- Worker logs show inactivity despite non-empty queue

**Root causes:**
- Previous episode runs left tests in `Queued` limbo (never reached `Running`)
- Worker process crashed or hung while processing a test
- Redis persistence exceeded capacity

**Diagnosis:**
```powershell
$redis = 'project1-boptest-redis-1'

# Check queue depth
docker exec $redis redis-cli LLEN jobs
# Expected: 0 (empty) or <5 (light load)

# Check test state distribution
docker exec $redis redis-cli --raw EVAL @"
local q=0; local r=0; local d=0; local t=0
for _,k in ipairs(redis.call('keys','tests:*')) do
  t=t+1
  local s=redis.call('hget',k,'status')
  if s=='Queued' then q=q+1
  elseif s=='Running' then r=r+1
  elseif s=='Done' then d=d+1 end
end
return {t,q,r,d}
"@ 0

# Returns: [total_tests, queued_count, running_count, done_count]
# Expected: Queued should be 0, Running at most 1
```

**Recovery (Sequential Steps):**

**Step 1: Stop all active tests (graceful)**
```powershell
$redis = 'project1-boptest-redis-1'
$active = docker exec $redis redis-cli --raw EVAL @"
local out={}
for _,k in ipairs(redis.call('keys','tests:*')) do
  local s=redis.call('hget',k,'status')
  if s=='Queued' or s=='Running' then
    table.insert(out, k..'='..s)
  end
end
return out
"@ 0

foreach($line in $active) {
  if($line -match '^tests:([^=]+)=') {
    $id = $Matches[1]
    try {
      $resp = Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8000/stop/$id" -TimeoutSec 30
      "stopped $id => ok"
    } catch {
      "stop failed $id (already terminated?)"
    }
  }
}
```

**Step 2: Verify queue is clean (wait 5s, then check)**
```powershell
Start-Sleep -Seconds 5
docker exec project1-boptest-redis-1 redis-cli LLEN jobs
# Expected: 0
```

**Step 3: If queue not empty, manual Redis flush (last resort)**
```powershell
$redis = 'project1-boptest-redis-1'

# WARNING: This deletes all pending jobs
docker exec $redis redis-cli DEL jobs

# Confirm clean
docker exec $redis redis-cli LLEN jobs
# Expected: 0
```

---

### Failure Mode 3: Worker Pool Timeout on `advance()`

**Symptoms:**
- Episode startup succeeds (reaches `Running` state)
- Test initialization completes
- First or early `advance()` call times out (read timeout 300s+)
- Error: `HTTPConnectionPool... Read timed out. (read timeout=300)`
- Worker logs show slow or stalled FMU simulation

**Root causes:**
- Worker is CPU-bound or I/O-bound (FMU simulation is slow on heavy cases)
- Worker process is hung (deadlock in FMU library)
- System resources (memory/disk) exhausted

**Diagnosis:**
```powershell
# Check worker container stats
docker stats project1-boptest-worker-1 --no-stream
# Look for: CPU % near 100%, memory % high (>80%), or no updates

# Check worker logs for errors
docker logs project1-boptest-worker-1 | Select-Object -Last 50

# Check system resources (host machine)
powershell -Command "Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory,TotalVisibleMemorySize"
# Verify free memory is >20% of total
```

**Recovery (Priority Order):**

**Option 1: Increase timeout and retry (safest)**
- Multizone and heat-pump cases are compute-intensive (boiler dynamics, thermophysics)
- Current defaults: startup_timeout_s=420, advance_timeout=300
- For multizone: increase to startup_timeout_s=1200, advance_timeout=600
- Retry episode with longer timeout
- Example: `scripts/run_mpc_episode.py --startup-timeout-s 1200 ... --mpc-config ... (contains advance_timeout)`

**Option 2: Restart worker (medium)**
```powershell
docker restart project1-boptest-worker-1

# Wait for worker to re-initialize (30â€“60s)
Start-Sleep -Seconds 60

# Re-probe API to confirm readiness
curl.exe -s http://127.0.0.1:8000/version | ConvertFrom-Json
```

**Option 3: Sequential episodes (workaround)**
- Current: Runner spawns multiple episodes in parallel (background processes)
- Problem: Worker pool servicing all in parallel; queue saturation + timeout
- Solution: Run episodes sequentially (one at a time) instead
- Modify `run_eu_campaign_stage1.py` or `run_mpc_episode.py` to serialize execution
  - Set `isBackground=false` in terminal runner (blocks on each episode completion)
  - OR: Add sleep/polling between spawns to ensure prior episode completes before next starts

**Option 4: Full stack redeploy (last resort)**
```powershell
# Cleanly reset BOPTEST (destroys all test state)
docker compose -f path/to/docker-compose.yml down
docker compose -f path/to/docker-compose.yml up -d
```

---

### Failure Mode 4: Stale Tests Blocking New Selections

**Symptoms:**
- New test selection succeeds BUT returns old test ID (from prior run)
- Episode startup logs show "Selecting test case 'X'" but test ID in URLs is from yesterday's run
- Control signals or initial conditions are mismatched (previous run's state lingering)

**Root cause:**
- BOPTEST case names are shared across invocations
- Redis persists test metadata across restarts
- No explicit cleanup between campaign runs

**Diagnosis:**
```powershell
$redis = 'project1-boptest-redis-1'

# List all test IDs for a given case
docker exec $redis redis-cli --raw EVAL @"
local out={}
for _,k in ipairs(redis.call('keys','tests:*')) do
  local case=redis.call('hget',k,'case')
  if case=='bestest_hydronic_heat_pump' then
    local s=redis.call('hget',k,'status')
    table.insert(out, k..' => '..s)
  end
end
table.sort(out)
return out
"@ 0

# Expected: Should only see 1â€“2 recent tests, not 10+ from prior runs
```

**Recovery:**
```powershell
$redis = 'project1-boptest-redis-1'

# Option A: Redis key cleanup (targeted)
# Delete all test entries (Redis persists but in-memory cached)
docker exec $redis redis-cli EVAL @"
for _,k in ipairs(redis.call('keys','tests:*')) do
  redis.call('DEL', k)
end
return redis.call('keys','tests:*')
"@ 0

# Option B: Full container restart (cleaner)
docker restart project1-boptest-redis-1
docker restart project1-boptest-web-1
# Then confirm queue is empty (LLEN jobs = 0)
```

---

### Failure Mode 5: Long first `advance()` looks stalled (Multizone)

**Symptoms:**
- Episode reaches `Running` and prints initialization, then appears frozen.
- No step-completion output for several minutes.
- Worker container stays near 100% CPU.
- Redis queue is usually 0 or 1 (not overloaded).

**Observed root cause (2026-03-24):**
- The first multizone `advance()` is very expensive and can run far longer than typical single-zone calls.
- Without heartbeat logging, this looks like a dead process.
- Web-side message timeout can kill long worker requests if set too low.

**Diagnosis:**
```powershell
# 1) Confirm active test is still Running
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/status/<testid>" -TimeoutSec 30

# 2) Confirm worker is busy (not idle)
docker stats --no-stream project1-boptest-worker-1 project1-boptest-web-1

# 3) Check whether current testid appears in timeout lines
docker logs project1-boptest-web-1 2>&1 | Select-String -Pattern '<testid>|Timeout for request' | Select-Object -Last 20
```

**Recovery and hardening:**
```powershell
# Stop stale test and restart worker if queue consumer is stuck
Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8000/stop/<testid>" -TimeoutSec 60 | Out-Null
docker restart project1-boptest-worker-1

# Run with long timeout and heartbeat output
& ".venv/Scripts/python.exe" scripts/run_mpc_episode.py \
  --predictor pinn \
  --episode all-test \
  --mpc-config configs/mpc_phase1.yaml \
  --url http://127.0.0.1:8000 \
  --startup-timeout-s 1200 \
  --advance-timeout-s 7200 \
  --advance-heartbeat-s 30
```

**Persistent setting (recommended):**
- Set `BOPTEST_MESSAGE_TIMEOUT=7200000` for the web service and recreate the container.
- Keep runner heartbeat enabled for operations.

**Interpretation rule:**
- Heartbeat continues + worker CPU near 100%: active long compute.
- No heartbeat >5 minutes + no new worker/web line for active test ID: likely true stall.

---

### Composite Recovery Procedure

When one or more failure modes are suspected, follow this checklist in order:

1. **Stop all active tests** (handle Queued/Running cleanup)
2. **Wait 5s**
3. **Check queue depth** â†’ if not 0, flush manually
4. **Check API health** (HTTP 200 on /version, /testcases)
5. **If API down**: `docker restart project1-boptest-web-1` + wait 30s
6. **Check Redis state** (no stale test*: entries)
7. **If stale tests**: `docker restart project1-boptest-redis-1`
8. **Check worker stats** (CPU/memory not saturated)
9. **If worker slow**: Increase timeout on next episode attempt
10. **If still failing**: Full redeploy (`docker compose down && docker compose up`)

---

### Instrumentation for Future Diagnostics

To make it faster to debug next time, add these to your pre-episode checks:

```powershell
# Snippet for campaign runner startup or diagnostic script
$redis = 'project1-boptest-redis-1'
$timestamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')

Write-Output "[$timestamp] BOPTEST Health Check:"

# 1. API health
$api_version = curl.exe -s -w "%{http_code}" http://127.0.0.1:8000/version
Write-Output "  API /version: $api_version"

# 2. Queue state
$queue_len = docker exec $redis redis-cli LLEN jobs
Write-Output "  Redis queue length: $queue_len"

# 3. Test state counts
$counts = docker exec $redis redis-cli --raw EVAL @"
local q=0; local r=0; local d=0; local t=0
for _,k in ipairs(redis.call('keys','tests:*')) do
  t=t+1
  local s=redis.call('hget',k,'status')
  if s=='Queued' then q=q+1
  elseif s=='Running' then r=r+1
  elseif s=='Done' then d=d+1 end
end
return {t,q,r,d}
"@ 0
Write-Output "  Test counts: total=$($counts[0]), queued=$($counts[1]), running=$($counts[2]), done=$($counts[3])"

# 4. System resources
$mem = Get-CimInstance Win32_OperatingSystem | Select-Object @{n='FreePercent';e={[math]::Round(100*$_.FreePhysicalMemory/$_.TotalVisibleMemorySize)}}
Write-Output "  Free memory: $($mem.FreePercent)%"

if($queue_len -gt 5 -or $counts[1] -gt 2) {
  Write-Output "  WARNING: Elevated queue/Queued counts detected; recommend cleanup before episode"
}
```

---

## Documentation Update Protocol

**When to update this file:**
- After diagnosing and fixing any BOPTEST or Docker issue
- After discovering a new failure mode not documented above
- After testing/validating a recovery procedure in production

**How to update:**
1. Add new failure mode under "Failure Mode N" or update existing section
2. Include: symptoms, diagnosis commands, recovery steps, validation check
3. Re-run the failing scenario to confirm fix works
4. Document result (did it work? how long? any edge cases?)
5. Include timestamp and case name for traceability

**Example commit message:**
```
docs: Add Failure Mode 4 (stale tests) + increase multizone timeout to 1200s

Discovered that Redis test entries persist across restarts, blocking fresh
selections. Added cleanup procedures. Multizone episodes now use 1200s startup
timeout to avoid Queued saturation on heavy thermal simulation.
```

