# Performance Metrics and KPI Standards

## Overview

This document defines the performance metrics and key performance indicators (KPIs) used throughout the PINN-based model predictive control project. The project adopts **BOPTEST's native challenge KPI framework** rather than classical ASHRAE Guideline 14 calibration standards (NMBE, CVRMSE, R²).

---

## Key Finding

**NMBE and CVRMSE are NOT used in this project.**

This project uses BOPTEST's native KPI framework rather than ASHRAE Guideline 14:

- ✅ **What is used:** BOPTEST challenge KPIs (`cost_tot`, `tdis_tot`, `idis_tot`, peak power)  
- ❌ **What is NOT used for MPC campaign scoring:** NMBE, CVRMSE  
- ✅ **What is additionally used for PINN surrogate validation:** RMSE, MAE, MAPE, R², physics residual loss, and noise robustness checks  
- ✅ **Why:** BOPTEST is a building simulation testbed; its KPIs align with MPC objectives (cost + comfort trade-off), not classical steady-state calibration metrics.

---

## KPIs from BOPTEST (Challenge KPIs)

| **Source** | **Metric ID** | **Name** | **Unit** | **Interpretation** | **Context** |
|---|---|---|---|---|---|
| **BOPTEST** | `cost_tot` | Operational HVAC Cost | EUR/m² | Total operational cost over the episode (energy × time-varying price) | Primary objective in MPC |
| **BOPTEST** | `tdis_tot` | Thermal Discomfort | K·h per zone | Sum of temperature deviations outside comfort bounds [T_low, T_high] weighted by duration | Primary objective in MPC |
| **BOPTEST** | `idis_tot` | Indoor Air Quality Discomfort | ppm·h per zone | CO₂ concentration violations above bounds | Secondary metric |
| **BOPTEST** | `pele_tot` | Peak Electrical Demand | kW/m² | Maximum instantaneous power in 15-min window | Constraint in MPC |
| **BOPTEST** | `pdih_tot` | Peak District Heating | kW/m² | Maximum instantaneous heating power in 15-min window | Constraint in MPC |
| **BOPTEST** | `ener_tot` | Total Energy | kWh | Cumulative energy consumption (note: can be unreliable for some models) | Reference only |
| **BOPTEST** | `emis_tot` | Total Emissions | kg CO₂ | Carbon footprint proxy | Secondary metric |
| **BOPTEST** | `time_rat` | Time Ratio | dimensionless | Simulation speed relative to real-time (diagnostic) | Performance check |

---

## Diagnostic KPIs (Computed Locally)

These are computed from the step-by-step simulation data **within this project**:

| **Metric ID** | **Name** | **Unit** | **Formula** | **Purpose** |
|---|---|---|---|---|
| `comfort_Kh` | Local Thermal Comfort | K·h | Sum of time-steps where T is outside [15, 30]°C | Local validation (may differ from BOPTEST definition) |
| `comfort_violation_steps` | Comfort Violation Count | steps | Count of steps where T < 15°C or T > 30°C | Frequency-based analysis |
| `total_energy_Wh` | **Canonical Energy** | Wh | Sum of power_W × dt_s / 3600 from step data | **Preferred over `ener_tot`** (more reliable) |
| `peak_power_W` | Peak Total Power | W | max(power_W) across all steps | Electrical load signature |
| `peak_heating_power_W` | Peak Heating Power | W | max(power_heating_W) across all steps | Heating capacity requirement |
| `control_smoothness` | Control Actuation Smoothness | dimensionless | Sum(abs(u[k] − u[k−1])) / n_steps | MPC control quality (lower = smoother) |
| `mpc_solve_time_mean_ms` | MPC Solve Time (Mean) | ms | mean(solve_time_ms) per episode | Computational burden |
| `mpc_solve_time_p95_ms` | MPC Solve Time (p95) | ms | 95th percentile of solve_time_ms | Worst-case solver performance |
| `mpc_solve_time_max_ms` | MPC Solve Time (Max) | ms | max(solve_time_ms) | Peak solver time |
| `episode_wall_time_s` | Episode Execution Time | seconds | wall_clock_end − wall_clock_start | Real-world runtime |

---

## Training & Calibration Metrics (PINN Model)

For the PINN **surrogate validation**, model quality is verified across data accuracy, physical consistency, and robustness:

| **Metric** | **Name** | **Unit** | **Interpretation** |
|---|---|---|---|
| `rmse_degC` | Root Mean Square Error | °C | Typical one-step prediction error; target < 0.1°C |
| `mae_degC` | Mean Absolute Error | °C | Average magnitude of deviations |
| `mape_pct` | Mean Absolute Percentage Error | % | Relative error for scale-aware comparison |
| `r2_score` | Coefficient of Determination | — | Variance explained by surrogate predictions |
| `physics_loss` | Physics Residual Loss | — | Physical consistency proxy; lower indicates better residual compliance |
| `rollout_rmse_degC` | Multi-Step Rollout RMSE | °C | 24-step prediction error; captures error accumulation |
| `val_loss` | Validation Loss (combined) | — | Data loss + physics regularization term |

### Validation Types and Acceptance Intent

| **Validation Type** | **Purpose** | **Common Metrics** |
|---|---|---|
| Data Accuracy | Ensure the model tracks observed/simulated sensor trajectories. | `rmse_degC`, `mape_pct`, `r2_score` |
| Physical Consistency | Verify thermodynamic behavior remains plausible on unseen data. | `physics_loss` on unseen validation/test split, residual trend checks |
| Robustness Testing | Check stability under corrupted/noisy sensor inputs. | `robustness_test.noise_5pct.rmse_degC`, `robustness_test.noise_10pct.rmse_degC` |

Robustness tests are run by injecting Gaussian perturbations with 5% and 10% standard-deviation scaling on key sensor/control inputs and re-evaluating prediction metrics.

---

## Metric Definitions Catalog

The authoritative metric definitions are stored in:

**File:** [`configs/metrics_catalog.yaml`](../configs/metrics_catalog.yaml)

This YAML file formally defines all KPIs, formulas, units, and descriptions used in the project.

---

## Example BOPTEST Result Structure

BOPTEST returns KPIs in the following JSON structure within each episode result:

```json
{
  "challenge_kpis": {
    "cost_tot": {
      "value": 0.2368417,
      "unit": "EUR/m2",
      "description": "Operational HVAC cost (energy * price).",
      "source": "boptest"
    },
    "tdis_tot": {
      "value": 9.998727,
      "unit": "Kh/zone",
      "description": "Thermal discomfort relative to comfort bounds.",
      "source": "boptest"
    },
    "idis_tot": {
      "value": 0.0,
      "unit": "ppm*h/zone",
      "description": "IAQ discomfort from CO2 concentration above bounds.",
      "source": "boptest"
    },
    "pele_tot": {
      "value": 0.00025517,
      "unit": "kW/m2",
      "description": "Peak electrical demand (15 min).",
      "source": "boptest"
    },
    "pdih_tot": {
      "value": 5.62496,
      "unit": "kW/m2",
      "description": "Peak district heating demand (15 min).",
      "source": "boptest"
    }
  },
  "diagnostic_kpis": {
    "comfort_Kh": 40.9887,
    "comfort_violation_steps": 228,
    "total_energy_Wh": 225980.93,
    "peak_power_W": 5637.2,
    "mpc_solve_time_mean_ms": 2.901,
    "episode_wall_time_s": 6866.5
  },
  "boptest_kpis": {
    "tdis_tot": 9.998727,
    "idis_tot": 0,
    "ener_tot": 4.607550,
    "cost_tot": 0.2368417,
    "emis_tot": 0.833825,
    "pele_tot": 0.00025517,
    "pgas_tot": 0.116086,
    "pdih_tot": null,
    "time_rat": 3.689e-05
  }
}
```

---

## Notes

### Energy Metric Selection

The `diagnostic_kpis.total_energy_Wh` (sum of step power) is **preferred over** `boptest_kpis.ener_tot` because:
- It is reconstructed directly from timestep power measurements
- It avoids numerical artifacts and machine epsilon issues in some BOPTEST models
- It remains reliable across all testcase topologies

### Comfort Definition

Comfort bounds in this project:
- **Lower bound:** 15°C
- **Upper bound:** 30°C
- **Occupied vs. unoccupied:** Both tracked, weighted by occupancy schedules in some analyses

### MPC Objectives

MPC tuning uses weighted combination:
- **Cost weight:** 0.45 (EUR/m² minimization)
- **Discomfort weight:** 0.35 (K·h minimization)
- **Peak power weight:** Constraint (not minimized directly)

---

## References

- **BOPTEST Documentation:** [https://github.com/ibpsa/project1-boptest](https://github.com/ibpsa/project1-boptest)
- **Metric Catalog:** [`configs/metrics_catalog.yaml`](../configs/metrics_catalog.yaml)
- **Example Result:** [`results/eu_rc_vs_pinn/raw/bestest_hydronic/rc_base/te_std_01.json`](../results/eu_rc_vs_pinn/raw/bestest_hydronic/rc_base/te_std_01.json)
