# Occupancy-Aware Control Tuning Guide

## **Problem Summary**

From singlezone_commercial_hydronic analysis (te_std_01):

| Metric | RC | PINN | RBC |
|--------|----|----|-----|
| **Occupied violations (21-24°C)** | **259** | **219** | **0** ✓ |
| **Unoccupied violations (15-30°C)** | 0 ✓ | 0 ✓ | 0 ✓ |
| **Mean setpoint** | 23.24°C | 21.86°C | 22.0°C ✓ |
| **Setpoint range** | 22.0-23.84°C | 19.44-24.31°C | 22.0°C |
| **During occupied mean** | 26.1°C | 25.2°C | 22.2°C ✓ |

**Root cause:** Both RC and PINN maintain high setpoints regardless of occupancy, causing overshoot when people are present and comfort matters.

---

## **Tuning Knobs**

### **1. MPC Objective Weights** (in `run_mpc_episode.py` or solver initialization)

Current defaults (check `run_mpc_episode.py` line ~350):
```python
w_comfort = 100.0   # Penalty for T outside comfort bounds
w_energy = 0.0001   # Penalty for energy (heating)
w_smooth = 0.1      # Penalty for setpoint changes
```

**Recommended tuning for occupancy-aware:**

```python
# OPTION A: Strong energy penalty (reduce heating cost)
w_comfort = 100.0       # Keep comfort as primary objective
w_energy = 0.001        # 10x increase → strongly penalize heating
w_smooth = 0.1          # Keep smoothness constraint

# OPTION B: Asymmetric occupancy weights (different during occupied/unoccupied)
# Would require modifying solver to apply different weights per step
# (more complex but more effective)
if occupied:
    w_comfort = 200.0   # Strict during occupied
    w_energy = 0.0001   # Tolerate more energy
else:
    w_comfort = 50.0    # Relax comfort during unoccupied
    w_energy = 0.001    # Penalize heating more
```

**Impact:** Increasing `w_energy` forces the optimizer to choose lower setpoints → reduces overshoot.

---

### **2. Setpoint Bounds by Occupancy** (in `run_mpc_episode.py`)

Currently uses global `u_min=18°C, u_max=26°C` for all periods.

**Change to occupancy-aware bounds:**

```python
# In run_mpc_episode.py, around line 220-240
if occupancy_schedule:
    occupied_bounds = (21.0, 24.0)      # Keep tight during occupied
    unoccupied_bounds = (15.0, 30.0)    # Wide during unoccupied
    solver = MPCSolver(
        predictor,
        ...,
        occupied_bounds=occupied_bounds,
        unoccupied_bounds=unoccupied_bounds,
        occupancy_schedule=occupancy_schedule
    )
```

**Even more aggressive:**
```python
# Restrict max setpoint during occupied
occupied_bounds = (21.0, 22.5)  # Prevent overshoot
unoccupied_bounds = (15.0, 25.0)
```

**Impact:** Hard constraint on setpoint ranges → physically prevents overshooting.

---

### **3. Comfort Bounds Definition** (already implemented, confirm usage)

Check `mpc/occupancy.py`:
```python
def comfort_bounds(time_s: int, schedule=None) -> tuple[float, float]:
    """Return (T_lower, T_upper) based on occupancy."""
    if schedule and is_occupied(time_s, schedule):
        return (21.0, 24.0)  # Occupied bounds
    else:
        return (15.0, 30.0)  # Unoccupied bounds (relaxed)
```

**Confirmation:** Is this being passed to the solver? 
- Search for `comfort_bounds_sequence()` calls in `run_mpc_episode.py`
- Verify it's being used in the objective function

---

## **RC-Specific Tuning**

RC is an MPC solver using RC thermal model. Current behavior:

**Issue:** Mean setpoint 23.24°C (too high during occupied)

**Solution 1: Reduce energy weight** ← Simplest
```python
# In run_mpc_episode.py, set for RC:
w_energy = 0.001      # Was 0.0001, increase 10x
```
This tells optimizer: heating is expensive, choose lower setpoints.

**Solution 2: Tighten unoccupied bounds**
```python
occupied_bounds = (21.0, 24.0)
unoccupied_bounds = (15.0, 24.0)  # Cap even during unoccupied (was 30)
```
Prevents optimizer from "learning" that high setpoints are OK.

**Solution 3: Add ramp limit** (like RBC)
```python
# Limit u change per step during RC solve
max_ramp_degC = 1.5
```

---

## **PINN-Specific Tuning**

PINN is a neural network trained on MPC trajectories. Current issue:

**Problem:** Minimal occupancy response (occupied mean 21.70°C vs unoccupied 21.97°C)

**Root causes:**
1. Occupancy may not be included as model input
2. Loss function doesn't emphasize occupancy-aware control

**Solution 1: Feature engineering (if not already done)**

Check `pinn_model/data.py` to see if `occupied` flag is included:
```python
# Should have something like:
input_features = [
    't_zone',
    'h_global',
    't_outdoor',
    'occupied',  # ← Is this here?
    'time_sin', 'time_cos',  # Cyclical time
]
```

If missing, add it:
```python
if metadata.get('occupied'):
    features.append(1.0)
else:
    features.append(0.0)
```

**Solution 2: Retrain with occupancy-weighted loss**

```python
# In pinn_model/training.py
def loss_occupancy_aware(predictions, targets, occupancy_mask, w_occupied=2.0, w_unoccupied=0.5):
    """
    Heavier penalty for violations during occupied periods.
    """
    occupied_loss = w_occupied * mean_squared_error(
        predictions[occupancy_mask], 
        targets[occupancy_mask]
    )
    unoccupied_loss = w_unoccupied * mean_squared_error(
        predictions[~occupancy_mask], 
        targets[~occupancy_mask]
    )
    return occupied_loss + unoccupied_loss
```

**Solution 3: Two-phase training or conditional head**

Train PINN with two branches:
```python
class SingleZonePINN(nn.Module):
    def forward(self, features):
        # features includes 'occupied' flag
        base = self.physics_layer(features)
        
        # Conditional branch
        if features['occupied']:
            u_heating = self.occupied_head(base)  # More aggressive
        else:
            u_heating = self.unoccupied_head(base)  # Conservative
        
        return u_heating
```

---

## **Implementation Priority**

### **Quick wins (< 1 hour):**
1. ✅ Increase RC `w_energy` from 0.0001 → 0.001
2. ✅ Check if PINN has occupancy as input feature
3. ✅ Tighten unoccupied setpoint max from 26°C → 24°C

### **Medium effort (1-3 hours):**
4. Implement asymmetric MPC weights (occupied vs unoccupied)
5. Add ramp limit to RC control
6. Retrain PINN with occupancy-weighted loss

### **Longer term:**
7. Implement two-phase PINN training
8. Fine-tune comfort bound values per building type
9. Compare occupancy-aware tuning across all 4 test cases

---

## **Testing Protocol**

After tuning, run comparison:
```bash
python scripts/compare_rc_pinn_rbc_results.py
```

Key metrics to check:
- **Occupied period violations** (should drop to ~0 like RBC)
- **Unoccupied period energy** (should stay low or improve)
- **Mean setpoint** (should converge toward RBC's 22.0°C during occupied)

---

## **Files to Modify**

| File | Change | Impact |
|------|--------|--------|
| `scripts/run_mpc_episode.py` | Increase `w_energy`, set occupancy-aware bounds | RC mean setpoint ↓ |
| `pinn_model/data.py` | Add `occupied` feature if missing | PINN input richness ↑ |
| `pinn_model/training.py` | Occupancy-weighted loss | PINN occupancy response ↑ |
| `mpc/solver.py` | Asymmetric weights per occupancy | Both controllers ↑ |

