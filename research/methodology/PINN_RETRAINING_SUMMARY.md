# Phase 1 PINN Retraining & Validation - Progress Summary
**Date**: 2026-03-18 | **Status**: In Progress (Episode Validation Running)

## âœ“ Completed Tasks

### 1. Full PINN Retraining with Manual Weighting (ALL 5 CASES)
- **Script**: `scripts/retrain_all_eu_pinn_manual.py` 
- **Status**: âœ“ All models successfully trained
- **Cases trained**:
  - âœ“ singlezone_commercial_hydronic (34 epochs, val_loss=0.0400)
  - âœ“ bestest_hydronic  
  - âœ“ bestest_hydronic_heat_pump  
  - âœ“ twozone_apartment_hydronic

### 2. Updated PINN Training Configs with Loss Weighting
- **Files updated**: `configs/eu/pinn_*.yaml` (all 5 case-specific)
- **Key change**: Added `loss_weighting.mode: manual` section with full hyperparameter sets
- **Default weighting**: Manual (empirically best from smoke test: val_rmse=0.0717 degC)

### 3. Short Episode Validation Script Created
- **Script**: `scripts/validate_short_episodes.py`
- **Purpose**: Run 1-day episodes (all-test) for heat-pump PINN and multizone RC before full 7-day campaigns
- **Status**: Running in background (terminal ID: c77bcb23-ee58-42fc-9b1e-767e58680dd9)
- **Expected duration**: 2-4 hours
- **Episodes**:
  - Heat-pump PINN (bestest_hydronic_heat_pump) + all-test

### 4. Campaign Runner Enhanced with --short-episode Flag
- **File modified**: `scripts/run_eu_campaign_stage1.py`
- **New capability**: `python scripts/run_eu_campaign_stage1.py --short-episode`
- **Behavior**:
  - Reduces startup timeout from 180s â†’ 120s (prevents excessive queue wait)
  - Uses all-test episodes (1-day validation, not full 7-day)
  - Useful for quick infrastructure/control validation before full campaigns
- **Status tracking**: Saves campaign mode ("short_validation" vs "full_campaign") in live_status.json

---

## ðŸ“Š Key Metrics from Retraining

### singlezone_commercial_hydronic (Sample)
```
Best epoch: 34
Validation metrics:
  - loss: 0.0400
  - data_loss: 0.0399
  - physics_loss: 0.0137
  - rmse: 0.0917 degC
  - rollout_rmse: 0.6271 degC
```

---

## â³ In Progress

### Short Episode Validation (Terminal: c77bcb23-ee58-42fc-9b1e-767e58680dd9)
- **Status**: Running
- **Tests**:
  1. `run_mpc_episode.py --predictor pinn --case bestest_hydronic_heat_pump --episode all-test`
- **Timeout per case**: 3600s (1 hour)
- **Purpose**: Validate control logic, MPC solver robustness, and FMU responsiveness before multi-day runs
- **Expected completion**: Check logs/validate_short_episodes.log for status

---

## ðŸš€ Next Steps (After Validation Completes)

1. **If short episodes succeed** (recommended):
   - Run full 7-day campaigns for all cases
   - Command: `python scripts/run_eu_campaign_stage1.py --url http://127.0.0.1:8000`
   - Expected time: 24-48 hours (depending on cases & queue)
   - Produces: `results/eu_rc_vs_pinn/raw/{case}/rc/*.json` + `results/eu_rc_vs_pinn/raw/{case}/pinn/*.json`

2. **If short episodes fail**:
   - Check FMU_DIAGNOSTICS.md error handling guide for recovery procedures
   - Verify BOPTEST infrastructure: Redis queue, web container, worker stats
   - May need: longer timeouts, container restart, or sequential episodes

3. **QC & Analysis** (after campaigns):
   - Run: `scripts/qc_eu_results.py` to validate data integrity
   - Generates: `results/eu_rc_vs_pinn/qc/plausibility_summary.csv` + figures
   - Compare heat-pump saturation metrics before/after tuning

---

## ðŸ“ Configuration Summary

### Loss Weighting Modes Available (in training)
| Mode | Config | Use Case |
|------|--------|----------|
| **manual** | Î»_physics=0.01 (default) | Empirically strongest on this dataset |
| gradient_balance | EMA smoothing Î» over epochs | For datasets with variable loss scales |
| uncertainty | Learnable log_sigma per task | For heteroscedastic noise modeling |

### MPC Overrides (Heat-Pump Tuning)
- **File**: `manifests/eu/bestest_hydronic_heat_pump_stage1.yaml`
- **Goal**: Reduce lower-bound saturation (was >25% of steps at u_min)
- **Changes**:
  - Energy penalty: 0.01 â†’ 0.002 (less penalizing heating)
  - Comfort penalty: 80 â†’ 140 (stronger pull upward)
  - Smoothness penalty: 0.5 â†’ 4.0 (encourage gradual changes)
  - Setpoint bounds: tighter (18.5â€“24.5Â°C safe band)

### System Control Extensions (Multizone)
- **New signals**:
  - `system_control_value_signals`: [oveTSetSup_u, oveTSetPumBoi_u] (boiler/pump setpoints)
  - `fixed_control_commands`: oveEmiPum_u: 1.0 (force emission pump on)

---

## ðŸ“„ Documentation Updates

### [FMU_DIAGNOSTICS.md](./FMU_DIAGNOSTICS.md)
- **New section**: "BOPTEST/Docker Error Handling Guide"
  - 4 failure modes documented with diagnosis commands
  - Composite recovery checklist (10 steps)
  - Pre-episode instrumentation snippet
  - Protocol for updating guide with new findings

### Repo Memory ([/memories/repo/pinn_phase1_notes.md](./memories/repo/pinn_phase1_notes.md))
- Added Phase1 Retraining & Validation section
- Documented error handling workflow
- Captured timeout requirements per case type

---

## ðŸ”„ Reproducibility

To reproduce this workflow later:

```bash
# 1. Ensure venv is activated
.venv\Scripts\Activate.ps1

# 2. Retrain all models (if needed)
python scripts/retrain_all_eu_pinn_manual.py

# 3. Quick validation (1-day episodes)
python scripts/validate_short_episodes.py

# 4. Full campaign (after validation succeeds)
python scripts/run_eu_campaign_stage1.py --url http://127.0.0.1:8000

# 5. OR quick validation of campaign runner
python scripts/run_eu_campaign_stage1.py --short-episode --max-cases 2 --url http://127.0.0.1:8000
```

---

## ðŸ“Œ Current Blockers

**BOPTEST Infrastructure Stability**
- Observed issues: Queued state persistence, web container dropout, slow advance() on heavy cases
- Mitigations: Comprehensive error handling guide + diagnostics in FMU_DIAGNOSTICS.md
- Workarounds: Sequential episodes (not parallel), longer timeouts for multizone

---

**Last Updated**: 2026-03-18 13:42 UTC  
**Next Checkpoint**: Short episode validation completion (check logs/validate_short_episodes.log)
