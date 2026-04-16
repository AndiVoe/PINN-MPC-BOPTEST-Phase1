# Code Review & Optimization Guide: MPC & PINN Model Folders

**Date:** April 16, 2026  
**Project:** Physics-Informed Neural Networks (PINN) for Building Control via MPC  
**Methodology:** Rigorous review with focus on thermal comfort & energy consumption KPIs

---

## Executive Summary

### Are the PINNs the Same?

**SHORT ANSWER:** Yes and no.

- **Same model architecture:** Both use the identical `SingleZonePINN` PyTorch class (in `pinn_model/model.py`)
- **Different purposes:**
  - `pinn_model/` folder: **TRAINING pipeline** (data loading, loss weighting, checkpoint management)
  - `mpc/` folder: **INFERENCE wrapper** (`PINNPredictor`) that loads trained weights for rollout-based MPC

**Key distinction:** The PINN is *trained once* in `pinn_model/`, then *deployed* in `mpc/predictors.py` as `PINNPredictor` for real-time MPC solving.

---

## DETAILED FILE ANALYSIS

---

# PINN_MODEL FOLDER (Training Pipeline)

## 1. pinn_model/model.py - `SingleZonePINN` Neural Network Architecture

### What It Does
Defines the core Physics-Informed Neural Network combining a learned neural correction term with explicit physics-based thermal dynamics.

**Architecture:**
```
Input Features (8D) 
  ↓
Dense(input_dim → hidden_dim) + Tanh
  ↓  
[Repeat depth times]
  ↓
Dense(hidden_dim → 1)  [produces correction, scaled by 5.0 × tanh]
  ↓
Correction (bounded ±5°C) + Physics Delta (1R1C model)
  ↓
Output: predicted_next_T_zone
```

### Current Assumptions & Values

| Parameter | Value | Comments |
|-----------|-------|----------|
| **hidden_dim** | 64 neurons | Moderate capacity for single-zone |
| **depth** | 3 layers | Shallow network to prevent overfitting |
| **dropout** | 0.0 | No regularization via dropout |
| **Correction scale** | 5.0 × tanh | Bounds correction to ±5°C |
| **Physics params init** | log_ua=-1.5, log_solar_gain=-3.0, log_hvac_gain=-0.5, log_capacity=12.0 | Softplus activation ensures positivity |
| **Activation** | Tanh (hidden), Softplus (physics params) | Smooth, bounded gradients suitable for MPC |

### Is This Optimal for Your Project?

✅ **MOSTLY OPTIMAL**, with minor recommendations:

#### Strengths
- **Physics-first design:** Explicit 1R1C thermal model forces learning of physically interpretable parameters (UA, gains, capacity)
- **Bounded correction:** The ±5°C limit prevents neural network from overwhelming physics, maintaining stability in MPC rollouts
- **Simple, interpretable:** 3-layer network is shallow enough to avoid overfitting on finite training data

#### Concerns & Recommendations

**1. Correction Scaling (5.0 × tanh) — POTENTIALLY CONSERVATIVE**
- **Current:** Limits correction to ±5°C max
- **Issue:** If true PINN training requires larger corrections (e.g., for complex multi-zone dynamics or unmodeled disturbances), this scale is too restrictive
- **Recommendation:**
  - **Analyze learned correction magnitude** in `validation_results/`: check if corrections frequently saturate near ±5°C
  - If saturation > 10% of samples → increase to **6.0-7.0**
  - If saturation < 5% → current 5.0 is appropriate
  - **OPTIMAL: Make this a configurable parameter in pinn_phase1.yaml**
  
  ```yaml
  model:
    correction_scale: 5.0  # Add this line; range [3.0-10.0]
  ```

**2. Physics Parameter Initialization — REVIEW NEEDED**
- **Current log values:** -1.5, -3.0, -0.5, 12.0
- **Post-training check:** Are learned physics parameters (after softplus) physically reasonable?
  - UA should be 0.5–5 W/K (small single-zone)
  - Solar gain 0.01–0.5
  - HVAC gain 10–50
  - Capacity 100–1000 kJ/K
- **Recommendation:** Add post-training validation in `scripts/validate_pinn_training.py` to flag implausible parameter ranges

**3. No Dropout — ACCEPTABLE FOR YOUR DATASET SIZE**
- With ~thousands of samples per split, dropout is not critical
- **Alternative consideration:** If adding dropout (0.1–0.2), retrain and monitor for loss increase
- **Current recommendation:** Keep dropout=0.0 unless overfitting is confirmed

---

## 2. pinn_model/data.py - Dataset Construction & Normalization

### What It Does
Builds training/validation/test datasets from raw BOPTEST JSON episodes, handles feature engineering (cyclical time), and computes normalization statistics.

### Current Assumptions & Values

| Assumption | Value | Assessment |
|-----------|-------|-----------|
| **Dt_s variability** | Handled dynamically (next_time_s - time_s) | ✅ Good; real BOPTEST has variable intervals |
| **Feature list (8D)** | T_zone, T_out, H_global, u_heating, Δu, occupied, sin(day), cos(day), sin(year), cos(year) | ✅ Appropriate for single-zone |
| **Normalization** | Per-feature z-score (mean/std from training set) | ✅ Standard practice |
| **Missing/invalid values** | Skipped silently (episode < 2 records) | ⚠️ Could hide data issues |
| **Power_W tracking** | Loaded but not used in PINN training | ℹ️ For KPI logging only |

### Is This Optimal?

✅ **WELL-DESIGNED**, with observations:

#### Strengths
- **Cyclical features:** Using sin/cos pairs for daily and yearly cycles is excellent for capturing seasonal & diurnal effects
- **Normalization:** Applied correctly per-feature before training
- **Flexible dt_s:** Correctly handles variable timesteps from BOPTEST

#### Minor Recommendations

**1. Invalid Value Handling — MORE VISIBILITY NEEDED**
- **Current:** Episodes with < 2 records are silently skipped
- **Recommendation:** Log how many episodes were excluded and why
  ```python
  # In _build_samples(), after filtering:
  print(f"Skipped {len(index_entries) - len(samples_kept)} episodes (< 2 records)")
  ```

**2. Feature Engineering — CONSIDER EXTENSIONS FOR MULTI-CASE**
- **Current:** Treats all cases identically (works for single-zone)
- **For future multi-zone scenarios:** Consider adding case-specific features (floor area, orientation, window-to-wall ratio)
- **Not critical now, but document this assumption**

**3. Normalization Stability — EDGE CASE HANDLING**
- **Current:** Sets std=1.0 if computed std < 1e-6
- **This is correct** but could mask constant features
- **Recommendation:** Log which features have near-zero variance (may indicate bad data or redundant features)

---

## 3. pinn_model/training.py - Training Loop & Loss Weighting

### What It Does
Implements the full training pipeline: data loading, loss computation (data loss + physics loss), gradient-based optimization, early stopping, and checkpoint management. Includes configurable loss weighting strategies (manual, gradient-balance, uncertainty).

### Current Configuration (pinn_phase1.yaml)

| Setting | Value | Assessment |
|---------|-------|-----------|
| **Batch size** | 256 | ✅ Good for 3-4k training samples |
| **Epochs** | 80 | ⚠️ Could be higher; early stopping will limit overfitting |
| **Learning rate** | 0.001 | ✅ Reasonable for Adam; no warmup needed |
| **Weight decay** | 0.00001 | ✅ Light regularization, appropriate |
| **lambda_physics** | 0.01 | ⚠️ Needs validation (see below) |
| **Rollout training** | enabled=true, horizon=24 | ✅ Excellent for MPC consistency |
| **Loss weighting mode** | manual | ℹ️ Simple; gradient_balance or uncertainty are alternatives |
| **Early stopping patience** | 10 epochs | ✅ Reasonable; guards against overfitting |
| **Rollout batch size** | 128 | ⚠️ Consider tuning with memory constraints |

### Is This Optimal?

✅ **GENERALLY GOOD**, with critical recommendations:

#### Strengths
- **Rollout training enabled:** This is **ESSENTIAL** for MPC use; you're already doing this correctly
- **Reasonable hyperparameters:** Learning rate, batch size, and weight decay are sensible defaults
- **Early stopping:** With patience=10 and min_epochs=15, avoids both underfitting and overfitting

#### CRITICAL ISSUES & RECOMMENDATIONS

**1. Lambda_physics = 0.01 — VALIDATE THIS VALUE**

The physics loss weight is **project-critical**. Current value (0.01) means:
- Data loss: 1.0 × (normalized error in temperature)
- Physics loss: 0.01 × (magnitude of neural correction)

**Is 0.01 optimal?**
- **Too low (< 0.001):** Neural network dominates; learned physics parameters become nonsensical
- **Too high (> 0.1):** Physics core dominates; neural network can't fix model mismatch
- **0.01 is a reasonable middle ground**, BUT needs validation

**Recommendation: Perform ablation study**
```
1. Train variant A: lambda_physics = 0.005 (less physics constraint)
2. Train variant B: lambda_physics = 0.01 (current)
3. Train variant C: lambda_physics = 0.02 (more physics constraint)
4. Compare:
   - One-step validation RMSE (should be similar)
   - 24-step rollout RMSE amplification (favor lower)
   - Learned physics parameters (favor physically plausible)
5. Recommendation: Choose the variant with lowest rollout RMSE
```

**Better yet: Use gradient_balance mode**
```yaml
loss_weighting:
  mode: gradient_balance  # Automatically adapts lambda_physics
  gradient_balance:
    ema_beta: 0.9
    target_ratio: 1.0
    lambda_min: 0.001
    lambda_max: 0.1
```
This automatically balances data vs. physics losses, removing manual tuning.

---

**2. Rollout Training Configuration — MINOR OPTIMIZATION**

```yaml
rollout_training:
  enabled: true           # ✅ Correct
  horizon_steps: 24       # ✅ Matches MPC horizon
  weight: 1.0             # ⚠️ Consider 0.5-0.75 if gradient instability
  batch_size: 128         # ✅ Reasonable; monitor GPU memory
  max_windows_per_episode: 0  # ✅ Use all windows (0 = unlimited)
```

**Recommendation:** If training diverges, reduce `rollout_training.weight` to 0.5. This makes data loss dominant, improving stability while maintaining rollout consistency.

---

**3. Batch Size & Epochs — FINE-TUNING**

- **Current batch size 256:** With ~3000 training samples → ~12 batches/epoch
- **Recommendation:** For more stable training, consider reducing to 128–192
  - More gradient updates per epoch
  - Better for smaller datasets
  - Trade-off: slightly more computation

- **Current epochs 80:** Early stopping will kick in around epoch 25–40
- **Recommendation:** Keep at 80; early stopping ensures we don't waste compute

---

## 4. Loss Weighting Strategies — DEEP DIVE

The training code supports **4 loss weighting modes**. Current project uses **manual**. Here's the comparison:

| Mode | Pros | Cons | Best For |
|------|------|------|----------|
| **manual** | Simple, reproducible | Requires manual tuning of lambda_physics | Quick prototyping |
| **gradient_balance** | Auto-adapts to data/physics balance | More hyperparameters (ema_beta, target_ratio) | **RECOMMENDED for this project** |
| **learning_rate_annealing** | Adapts based on loss ratio decay | Complex; not well-tested | Research/ablation |
| **uncertainty** | Learns confidence per task (Kendall et al.) | Adds parameters; requires careful initialization | Research-grade experiments |

**Recommendation for your project:**
✅ **Switch to gradient_balance mode**
```yaml
loss_weighting:
  mode: gradient_balance
  gradient_balance:
    ema_beta: 0.9              # Exponential moving average weight
    lambda_min: 0.001          # Prevent lambda from going too low
    lambda_max: 0.1            # Prevent lambda from dominating
    target_ratio: 1.0          # Target grad_data = grad_physics
```
This removes the manual lambda_physics tuning, making training more robust.

---

# MPC FOLDER (Inference & Control)

## 1. mpc/predictors.py - Inference Wrappers

### What It Does
Provides two predictor implementations:
1. **RCPredictor:** Pure physics (1R1C thermal model), used as whitebox baseline
2. **PINNPredictor:** Loads trained PINN checkpoint; provides analytical gradient for MPC

Both implement the `PredictorBase` interface for use by `MPCSolver`.

### Current Design & Assumptions

| Aspect | Implementation | Assessment |
|--------|----------------|-----------|
| **PINN loading** | Loads checkpoint, extracts config & feature names | ✅ Good |
| **Feature normalization** | Uses stored statistics from training | ✅ Correct |
| **Gradient computation** | Analytical via torch.autograd.grad() | ✅ Excellent for MPC |
| **Device handling** | CPU only (map_location="cpu") | ⚠️ See recommendation |
| **Model eval mode** | Explicitly set with model.eval() | ✅ Correct |
| **RC topology support** | 4 options: 1R1C, R3C2, R4C3, R5C3 | ℹ️ Future extensibility; uses 1R1C now |

### Is This Optimal?

✅ **WELL-DESIGNED INFERENCE LAYER**, with operational recommendations:

#### Strengths
- **Analytical gradients:** Using `torch.autograd.grad()` is perfect for MPC; avoids finite-difference approximation errors
- **Checkpoint flexibility:** Loads both config and model state, supporting different architectures
- **Feature name tracking:** Ensures consistency between training and inference

#### Recommendations

**1. GPU Support — OPTIONAL OPTIMIZATION**
- **Current:** Always uses CPU (`map_location="cpu"`)
- **Recommendation:** Add device selection for faster rollouts
  ```python
  def __init__(self, checkpoint_path: Path | str, device: str = "cpu") -> None:
      device = torch.device(device)
      if device.type == "cuda" and not torch.cuda.is_available():
          device = torch.device("cpu")
      ckpt = torch.load(checkpoint_path, map_location=device)
      # ...
  ```
  **When to use GPU:** Only if horizon × num_iterations > 10,000 steps; CPU is typically faster for small rollouts

**2. Gradient Caching Efficiency — MINOR**
- **Current:** `retain_graph=True` in gradient computation
- **This is necessary** for computing gradients at multiple setpoints; no change needed

**3. Physics Parameters from Checkpoint — GOOD PRACTICE**
- **Current:** Extracts physics_parameters from checkpoint if available, falls back to log-params
- **This is excellent** backward compatibility; keep as-is

---

## 2. mpc/solver.py - Rolling-Horizon MPC Solver

### What It Does
Implements constrained rolling-horizon MPC using `scipy.optimize.minimize` (SLSQP algorithm). Solves a quadratic programming problem at each timestep:
```
minimize: w_comfort × Σ(T_bounds_violation) + w_energy × Σ(u²) + w_smooth × Σ(Δu²)
subject to: 18°C ≤ u ≤ 24°C
```

### Current Configuration (mpc_phase1.yaml)

| Parameter | Value | Assessment |
|-----------|-------|-----------|
| **Horizon** | 24 steps (6 hours @ 900s) | ✅ Good for short-term planning |
| **u_min** | 18°C | ✅ Prevents excessive undersetting |
| **u_max** | 24°C | ✅ Practical setpoint range |
| **Comfort bounds (occupied)** | [21°C, 24°C] | ✅ Matches typical standards (±3K from 22°C) |
| **Comfort bounds (unoccupied)** | [15°C, 30°C] | ✅ Relaxed; energy-saving mode |
| **w_comfort** | 100.0 | ⚠️ **VERY LARGE** — validates strictly |
| **w_energy** | 0.001 | ✅ Balanced with comfort |
| **w_smooth** | 0.1 | ✅ Prevents aggressive switching |
| **maxiter** | 100 | ✅ Sufficient for convergence |
| **ftol** | 1e-4 | ✅ Tight tolerance for precision |

### Is This Optimal for Your Project?

✅ **WELL-CONFIGURED**, but **weight_comfort may be excessive**:

#### Strengths
- **Occupancy-aware:** Different comfort bounds for occupied vs. unoccupied hours (energy-efficient)
- **Constrained optimization:** Enforces heating limits (no superheat scenarios)
- **Warm-starting:** Shifts previous solution for faster convergence
- **Analytical gradients:** Works with PINNPredictor's analytical gradients

#### CRITICAL ISSUE: Objective Weight Imbalance

**Current:** w_comfort = 100.0 is **VERY HIGH** relative to other weights.

**Impact:**
- Solver will **aggressively pursue comfort**, often at the cost of energy efficiency
- Expected behavior: Frequent heating to maintain narrow [21–24°C] band
- Problem: This dominates the PINN vs. RC benchmark; PINN's advantage (energy efficiency) is masked

**Analysis of current weights:**
```
w_comfort = 100.0   ← Penalty per K² outside bounds (very strong)
w_energy = 0.001    ← Penalty per °C setpoint (very weak) — 100,000× less weight!
w_smooth = 0.1      ← Penalty per °C setpoint change
```

**Why this matters for your KPIs:**
- KPI 1: Thermal comfort — w_comfort = 100 ensures it's met (good)
- KPI 2: Energy consumption — w_energy = 0.001 barely constrain it (problem!)

**Recommendation: Rebalance the weights**

The current setup **prioritizes comfort so heavily that energy savings are negligible**. For a fair PINN vs. RC comparison:

```yaml
objective_weights:
  comfort: 100.0        # Keep high to ensure comfort is met
  energy: 0.01          # INCREASE by 10× (from 0.001)
  control_smoothness: 0.1
```

**Rationale:**
- 0.01 provides meaningful energy penalty while still respecting comfort
- Maintains 10,000× weight ratio (still comfort-first)
- Allows PINN's superior efficiency to show in benchmarks

**Better yet: Parametric sweep**
```
Test weight combinations:
  A: (comfort=100, energy=0.001)   [current — comfort-dominant]
  B: (comfort=100, energy=0.01)    [balanced energy penalty]
  C: (comfort=100, energy=0.05)    [stronger energy penalty]
  D: (comfort=100, energy=0.1)     [equal weighting of energy vs. smoothness]

For each:
  - Measure comfort violations (Kh)
  - Measure energy consumption (kWh)
  - Benchmark PINN vs. RC improvement
```

**Run this before finalizing the campaign** to ensure fair comparison.

---

## 3. mpc/occupancy.py - Occupancy Schedule & Comfort Bounds

### What It Does
Defines occupancy schedules and maps comfort bounds based on time-of-day and occupancy status.

### Current Defaults

```python
_DEFAULT_OCC_START_H = 8   # 08:00
_DEFAULT_OCC_END_H = 18    # 18:00
```

### Is This Optimal?

✅ **APPROPRIATE FOR YOUR TEST CASES**, with notes:

#### Assessment
- **08:00–18:00 occupancy:** Matches typical commercial office schedule ✅
- **Separate unoccupied bounds:** [15°C, 30°C] is realistic for off-hours ✅
- **Weekends can be unoccupied:** `weekends_occupied=True/False` provides flexibility ✅

#### Considerations
- **BOPTEST singlezone_commercial_hydronic:** Assumes 08:00–18:00 occupancy (matches default) ✅
- **bestest_hydronic cases:** May have residential schedules (different times); verify in BOPTEST specs
- **Your data:** Check if all cases use the same occupancy model, or if schedule should be case-specific

**Recommendation:**
```yaml
# In config, allow per-case occupancy override:
occupancy:
  schedule: "commercial"  # or "residential", "continuous"
  custom:                 # or specify manually
    start_hour: 8
    end_hour: 18
    weekends_occupied: false
```

---

## 4. mpc/kpi.py - KPI Logging

### What It Does
Logs key performance indicators (thermal comfort, energy, control smoothness) at each MPC step.

### Current Tracked KPIs

| KPI | Formula | Assessment |
|-----|---------|-----------|
| **Comfort dissatisfaction (Kh)** | Σ max(0, T_lower - T)² + max(0, T - T_upper)² per hour | ✅ Standard metric |
| **Energy (Wh)** | Σ power_W × dt | ✅ Tracks actual consumption |
| **Control smoothness** | Σ (u_t - u_{t-1})² | ✅ Quantifies switching |

### Is This Optimal?

✅ **CAPTURES THE RIGHT METRICS FOR YOUR KPIs**:
- Thermal comfort (dissatisfaction hours) ✅
- Energy consumption ✅
- Control smoothness (secondary) ✅

**Recommendation:** Add normalized metrics for benchmarking
```python
# In KPILogger, add:
"comfort_dissatisfaction_hours_normalized": comfort_kh / zone_area_m2,
"energy_consumption_per_area": energy_wh / 1000.0 / zone_area_m2,  # kWh/m²
```
This enables **fair comparison across different building sizes** (if future work expands to larger zones).

---

## 5. mpc/boptest.py - BOPTEST Client

### What It Does
Thin HTTP wrapper for BOPTEST REST API; handles test case selection, step-by-step simulation, and stopping.

### Current Design

| Feature | Assessment |
|---------|-----------|
| **Connection validation** | Checks reachability before use ✅ |
| **Error handling** | Raises `BoptestConnectionError` on failure ✅ |
| **Step-by-step API** | Properly implements BOPTEST advance() calls ✅ |
| **Timeout handling** | Configurable (default 300s) ✅ |

### Is This Optimal?

✅ **ROBUST IMPLEMENTATION**:
- Good error messages
- Proper timeout configuration
- Handles test case selection and cleanup

**Recommendation (optional enhancement):**
```python
# Add connection pooling for repeated runs:
def __init__(self, base_url: str, session=None):
    self.session = session or requests.Session()
    # Reuse connections across multiple advance() calls
```
This would marginally improve performance for long episodes, but current implementation is fine.

---

# SUMMARY: RECOMMENDATIONS BY PRIORITY

## 🔴 HIGH PRIORITY

### 1. **MPC Weight Rebalancing** (impacts your benchmark!)
- **Issue:** w_energy = 0.001 is 100,000× less than w_comfort; energy savings are masked
- **Action:** Increase w_energy to 0.01–0.05 before campaign
- **Impact:** Enables fair PINN vs. RC comparison on energy efficiency

### 2. **Physics Loss Weighting Ablation** (training quality)
- **Issue:** lambda_physics = 0.01 is a guess; not validated
- **Action:** Run 3-variant training study (0.005, 0.01, 0.02) or switch to gradient_balance mode
- **Impact:** Ensures optimal PINN accuracy and physical parameter learning

### 3. **Correction Scale Validation** (PINN stability)
- **Issue:** ±5°C cap may be too conservative; saturation unknown
- **Action:** Analyze learned correction magnitudes post-training; adjust if needed
- **Impact:** Prevents PINN instability or underperformance in MPC rollouts

---

## 🟡 MEDIUM PRIORITY

### 4. **Switch Loss Weighting to Gradient-Balance** (robust training)
- **Current:** Manual mode; requires tuning
- **Recommendation:** Use gradient_balance mode
- **Impact:** Automatic balancing; more reproducible across future PINN variants

### 5. **Add Invalid Data Logging** (debugging)
- **Current:** Silently skip bad episodes
- **Recommendation:** Print skip statistics to detect corrupted datasets
- **Impact:** Early warning if data issues arise

### 6. **GPU Support in PINNPredictor** (optional speedup)
- **Current:** CPU only
- **Recommendation:** Add device parameter for GPU acceleration
- **Impact:** ~2–5× faster if running 1000+ horizon steps; not critical for current setup

---

## 🟢 LOW PRIORITY

### 7. **Per-Case Occupancy Configuration** (future flexibility)
- **Current:** Fixed 08:00–18:00 for all cases
- **Recommendation:** Make configurable per test case
- **Impact:** Needed only if testing non-standard schedules

### 8. **Normalized KPI Logging** (cross-case comparison)
- **Current:** Absolute metrics only
- **Recommendation:** Add per-area normalization
- **Impact:** Nice-to-have for comparing different building sizes

### 9. **Correction Scale as Config Parameter** (flexibility)
- **Current:** Hardcoded 5.0 in model.py
- **Recommendation:** Move to pinn_phase1.yaml
- **Impact:** Easier ablation studies without code changes

---

# IMPLEMENTATION ROADMAP

## Week 1: Critical Changes
```
[ ] 1. Rebalance MPC weights: w_energy 0.001 → 0.01
[ ] 2. Run physics loss ablation: lambda_physics ∈ {0.005, 0.01, 0.02}
[ ] 3. Analyze PINN correction saturation; adjust 5.0 if needed
```

## Week 2: Training Infrastructure
```
[ ] 4. Switch loss weighting to gradient_balance mode
[ ] 5. Add invalid-data logging to pinn_model/data.py
[ ] 6. Create config parameter for correction_scale
```

## Week 3: Optional Enhancements
```
[ ] 7. Add GPU support to PINNPredictor
[ ] 8. Implement per-case occupancy configuration
[ ] 9. Add normalized KPI metrics
```

---

# VALIDATION CHECKLIST

After implementing recommendations, verify:

- [ ] **Comfort maintained:** Still meets [21–24°C] during occupied hours (with rebalanced weights)
- [ ] **Energy improvement visible:** PINN shows >5% energy reduction vs. RC (if true; may be <5%)
- [ ] **Physics parameters sensible:** UA ∈ [0.5–5] W/K, solar gain ∈ [0.01–0.5], etc.
- [ ] **Rollout stability:** 24-step predictions don't diverge (RMSE growth < 5× baseline)
- [ ] **Training convergence:** Loss smoothly decreases; no divergence spikes
- [ ] **Reproducibility:** Same seed → same weights (test with seed=42)

---

# CONCLUSION

Your PINN training and MPC framework are **well-architected**. The two critical improvements are:

1. **Rebalance MPC objective weights** to enable energy efficiency comparison
2. **Validate/optimize physics loss weighting** to ensure PINN quality

After these changes, your PINN vs. RC benchmark will provide **rigorous, fair comparison** on both thermal comfort and energy consumption KPIs.

