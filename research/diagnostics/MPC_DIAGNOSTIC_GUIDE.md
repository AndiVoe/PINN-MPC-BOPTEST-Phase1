# MPC System Diagnostic Guide

This guide helps you evaluate whether your MPC system is working correctly and whether PINN brings real value over RC baseline.

## Quick Start

Run all diagnostics in sequence:

```powershell
cd "c:\Users\AVoelser\OneDrive - Scientific Network South Tyrol\3_PhD\Simulation\PINN"

# 1. Validate PINN training quality
.venv\Scripts\python.exe -u scripts/validate_pinn_training.py

# 2. Diagnose MPC system configuration and convergence
.venv\Scripts\python.exe -u scripts/diagnose_mpc_system.py --output logs/mpc_diagnostics.json

# 3. Compare RC vs PINN MPC results (after campaigns complete)
.venv\Scripts\python.exe -u scripts/compare_rc_vs_pinn_results.py --output logs/rc_vs_pinn_comparison.csv
```

---

## Diagnostic 1: PINN Training Quality (`validate_pinn_training.py`)

**What it checks:** Whether PINN learned meaningful patterns from your data or just memorized it.

### Key Metrics

| Metric | What It Means | Good Range | Red Flag |
|--------|---------------|-----------|----------|
| **Convergence Status** | Training loss progression | Smooth decay | Spikes, divergence, no improvement |
| **Epochs since best val loss** | Early stopping effectiveness | <15 | >20 (overfitting, no early stopping) |
| **Val RMSE** | One-step prediction error | 0.1-0.5 °C | <0.01 °C (suspicious) or >1.0 °C |
| **Rollout RMSE amplification** | Error growth over 24h | 2-5x | >10x (severe error accumulation) |
| **Physics parameters (UA, gains)** | Learned building properties | Within 10% of physical estimates | Physically implausible (UA > 10 W/K) |
| **λ_physics** | Physics regularization weight | 0.001-0.1 | <0.0001 (no regularization) or >1.0 (over-constrained) |

### What to Do If...

**Problem:** Validation loss diverging from training loss after epoch 30
- **Cause:** Overfitting
- **Solution:** Add more training data, increase dropout/weight decay, or reduce λ_physics

**Problem:** Rollout RMSE 20x higher than one-step
- **Cause:** Prediction errors compound exponentially over horizon
- **Solution:** Increase training data diversity, reduce network size, improve feature engineering

**Problem:** Physics parameters (UA, capacity) are wildly implausible
- **Cause:** Data mismatch or insufficient physics regularization
- **Solution:** Increase λ_physics, inspect training data for anomalies, verify BOPTEST config

---

## Diagnostic 2: MPC System Configuration (`diagnose_mpc_system.py`)

**What it checks:** Whether MPC is configured appropriately and whether data is leaking between train/val/test.

### Key Checks

#### 2.1 Data Leakage
Ensures training, validation, and test episodes are completely disjoint.

**Red Flag:** ANY overlap in episode names between splits
- Invalidates all results
- Causes artificially good performance metrics
- **Fix:** Regenerate manifests with strict episode separation

#### 2.2 Prediction Horizon
Default: 24 steps × 900s = 6 hours lookahead

**Is it reasonable?**
- 6 hours: typical for building HVAC (captures morning/afternoon variations)
- Too short (<2h): insufficient to optimize energy pre-cooling
- Too long (>12h): weather forecast uncertainty dominates

#### 2.3 Predictor Behavior
Compares PINN and RC on synthetic test cases:

| Test Case | RC Output | PINN Output | Interpretation |
|-----------|-----------|------------|-----------------|
| Low setpoint (18°C) | Cold zone | Cold zone | Normal |
| High setpoint (26°C) | Warm zone | Warm zone | Normal |
| Same setpoint | Same temps | **Slightly different** | PINN learning something |
| Varying setpoint | Gradual response | **Sharp or different response** | PINN capturing complex dynamics |

**Red Flag:** RMSE < 0.1 °C across all test cases
- PINN nearly identical to RC
- Not learning meaningful deviations
- Reason: underfitting, insufficient training data variance, or weak physics regularization
- **Fix:** Increase training episodes, collect more diverse weather scenarios, reduce regularization

---

## Diagnostic 3: RC vs PINN Results Comparison (`compare_rc_vs_pinn_results.py`)

**What it checks:** Whether PINN MPC achieves better comfort/energy tradeoffs than RC MPC in actual episodes.

### Key Metrics (comparing final results)

| Metric | Interpretation | Target |
|--------|-----------------|--------|
| **Energy delta (%)** | PINN energy vs RC energy | ±2% (similar) or <-5% (PINN saves) |
| **Comfort delta (%)** | PINN comfort vs RC comfort | ±2% (similar) or <-10% (PINN improves) |
| **Peak power delta (%)** | PINN peak load vs RC peak | ±3% (similar) |

### What to Do If...

**Problem:** Energy delta ±0.5%, Comfort delta ±1% (very similar)
- **Cause:** PINN hasn't learned anything beyond RC
- **Reason:** Training data == test data, too weak physics departure, or RC already optimal
- **Solution:** 
  - Verify data leakage check passed ✓
  - Increase PINN capacity (more hidden layers) or change activation
  - Reduce λ_physics to allow more neural correction
  - Inspect training data quality (weather diversity, control variety)

**Problem:** PINN uses more energy but violates comfort more
- **Cause:** PINN learning wrong patterns or test/train mismatch
- **Solution:** Retrain with higher λ_physics, check episode weather coverage

**Problem:** PINN saves energy but hurts comfort
- **Cause:** PINN optimizing for energy, not comfort
- **Note:** This is a feature, not a bug—MPC weight tuning
- **Check:** Are weights balanced? `w_comfort=100.0, w_energy=0.0001` in mpc_config

---

## Interpreting the Full Picture

### Scenario 1: PINN Slightly Better (2-5% energy, 5-10% comfort)
```
Data leakage?       ✓ No
Training converged? ✓ Yes
PINN vs RC similar? Slightly different (0.3-0.5°C)
Energy improvement: 3-5%
→ SUCCESS: PINN learning meaningful corrections
```

### Scenario 2: PINN Nearly Identical to RC
```
Data leakage?       ✓ No
Training converged? ✓ Yes
PINN vs RC similar? Identical (<0.1°C difference)
Energy improvement: <0.5%
→ UNDERFITTING: PINN not departing from RC physics
   Actions:
   - Increase training diversity (more weather patterns)
   - Reduce λ_physics (allow more neural correction)
   - Verify training data quality
```

### Scenario 3: PINN Worse Than RC
```
Data leakage?       ✗ YES or ✓ No
Training converged? ✗ No (diverging loss)
PINN vs RC similar? Very different (>1.0°C)
Energy improvement: Negative
→ TRAINING FAILURE: PINN learned bad patterns
   Actions:
   - Debug data leakage immediately
   - Check training loss curves for spikes
   - Verify BOPTEST forecast points are available
   - Inspect episode-specific weather anomalies
```

### Scenario 4: PINN Crashes on Test Data
```
MPC convergence:    Low success rate (<95%)
Solver iterations:  Frequent timeouts or divergence
→ MPC FAILURE: Ill-posed optimization
   Actions:
   - Tighten SLSQP tolerances (ftol)
   - Reduce horizon length
   - Check comfort bounds (too tight?)
   - Verify predictor gradient (analytical vs finite diff)
```

---

## Common Pitfalls and Fixes

| Issue | Symptom | Root Cause | Fix |
|-------|---------|-----------|-----|
| **Data Leakage** | Train episodes in test set | Careless episode split | Regenerate manifests strictly |
| **Overfitting** | Val loss rises after epoch 50 | Too few epochs with early stopping | Reduce patience parameter |
| **Underfitting** | PINN ≈ RC, very low val RMSE | Weak training signal | Increase λ_physics or training data |
| **Horizon Too Long** | Forecast errors dominate | 6h lookahead beyond weather skill | Reduce to 3-4h (horizon_steps=12-16) |
| **Horizon Too Short** | No energy pre-cooling benefit | Can't see tomorrow's weather | Increase to 8-12h |
| **Solver Slow** | Solve time > 500ms | Dense horizon, inefficient gradient | Use RC (no gradient, FD faster) or reduce horizon |
| **Solver Fails** | Success rate < 95% | Infeasible or ill-conditioned problem | Relax comfort bounds, reduce weights |

---

## Data Quality Checklist

Before blaming PINN, verify your training data:

- [ ] **Diversity:** At least 2 different weather scenarios (hot, cold, neutral, rainy)
- [ ] **Duration:** ≥7 days per episode (captures daily cycles)
- [ ] **Control variety:** Setpoints range from 18-26°C, not stuck at one value
- [ ] **No NaNs/Infs:** All time series complete and finite
- [ ] **Physical bounds:** Outdoor temp -10 to +40°C, solar 0-1200 W/m², power 0-5kW
- [ ] **Episode independence:** No temporal overlaps between train/val/test

---

## File Structure for Diagnostics

```
Results expected:
logs/
├── mpc_diagnostics.json          ← Main diagnostic report
├── mpc_comparison_report.csv     ← RC vs PINN episode-by-episode
└── rc_vs_pinn_comparison.csv     ← Aggregated comparison

Inputs required:
configs/
├── pinn_phase1.yaml              ← Training hyperparameters
└── mpc_phase1.yaml               ← MPC settings (horizon, weights)

manifests/
└── phase1_singlezone.yaml        ← Episode splits (check no leakage)

artifacts/
└── pinn_phase1/
    ├── best_model.pt             ← Trained model
    ├── history.json              ← Loss curves
    └── metrics.json              ← RMSE, MAE

results/
└── mpc_phase1/
    └── *.json                    ← Episode result files
```

---

## Next Steps

After running diagnostics:

1. **If all PASS:** Your PINN is ready for publication comparison
   - Proceed to full campaign with confidence
   - Document discrepancies in publication notes

2. **If WARN/FAIL on training:** Retrain PINN
   - Adjust hyperparameters based on recommendations
   - Check data quality
   - Re-validate training quality

3. **If WARN/FAIL on comparison:** Debug MPC
   - Check episode-specific logs in `logs/eu_campaign_stage1/`
   - Verify forecast points match BOPTEST testcase
   - Test with shorter horizon locally

---

## Questions to Answer from Diagnostics

### Is MPC working correctly?
✓ See: **MPC System Diagnostics** → Convergence, Horizon, Leakage checks

### Is PINN training quality acceptable?
✓ See: **PINN Training Quality** → Convergence, Metrics, Physics params

### Is PINN learning something different from RC?
✓ See: **Predictor Comparison** section + **RC vs PINN Results**
- RMSE in synthetic tests
- Mean energy/comfort deltas in results

### Is training data bleeding into test?
✓ See: **Data Leakage Check** → No overlaps = safe

### Why is PINN not better than RC?
→ Run through checklist in "Scenario 2" above
→ Most likely: weak training signal, insufficient diversity, or RC already near-optimal

### Why is MPC failing on some episodes?
→ Check **MPC Convergence** and **Solver** diagnostics
→ Likely: forecast points unavailable, comfort bounds too tight, or horizon too long

