# PINN Variant Training (A & B)

## Overview

This document describes two PINN training variants designed to address **upper-bound comfort violations** in heating-only systems. Both variants recognize the fundamental constraint: **you cannot maintain upper comfort bounds with a heating-only system when internal gains + solar irradiation exceed the outdoor heat loss capacity.**

Rather than fighting physics, both variants use different loss weighting strategies to help the PINN gracefully accept and learn in infeasible regions.

## Variant A: Gradient-Balanced Loss Weighting

**Strategy:** Automatically balance the magnitude of data-fitting and physics gradients during training.

**How it works:**
- During each training step, the loss weighter computes the gradient norm for the data loss (MSE) and the physics loss separately
- It then adjusts `lambda_physics` (the physics loss scaling factor) using exponential moving average (EMA) to keep the gradient magnitudes in balance
- This prevents the physics term from over-constraining the model and forces it to learn comfort-critical patterns even when they conflict with learned physics

**Configuration:**
```yaml
loss_weighting:
  mode: gradient_balance
  gradient_balance:
    ema_beta: 0.95          # EMA smoothing (higher = slower adaptation)
    lambda_min: 1.0e-6      # Prevent zero weighting
    lambda_max: 1.0e2       # Prevent extreme scaling
    target_ratio: 1.0       # Target ratio of data grad / physics grad magnitude
```

**Benefits:**
- Fully automatic; no manual tuning of lambda needed
- Prevents one loss term from dominating
- PINN learns to prioritize comfort where physically feasible

## Variant B: Uncertainty-Weighted Loss

**Strategy:** Let the model learn its own prediction uncertainty (aleatoric + epistemic) and use it to weight loss terms.

**How it works:**
- The model learns two additional parameters: `log_sigma_data` and `log_sigma_physics`
- These log-variance terms are optimized jointly with the model weights
- The loss becomes: `w_data * data_loss + w_physics * physics_loss + (log_sigma_data + log_sigma_physics)`
  - where `w_data = exp(-2 * log_sigma_data)` and `w_physics = exp(-2 * log_sigma_physics)`
- Regions with high uncertainty get naturally de-weighted (low loss contribution)
- The model learns to **increase uncertainty near infeasible regions**, effectively learning confidence bounds

**Configuration:**
```yaml
loss_weighting:
  mode: uncertainty
  uncertainty:
    init_log_sigma_data: 0.0      # Initial log-std for data likelihood
    init_log_sigma_physics: 0.0   # Initial log-std for physics likelihood
```

**Benefits:**
- Model learns where it's confident vs. uncertain
- Natural de-weighting of infeasible regions
- Provides calibrated confidence bounds for deployment
- Follows principled Bayesian uncertainty weighting (Kendall et al., 2018)

## Running the Variants

### Train both variants:
```bash
python scripts/train_pinn_variants.py --variants AB --artifact-dir artifacts --configs-dir configs
```

### Train only Variant A:
```bash
python scripts/train_pinn_variants.py --variants A --artifact-dir artifacts --configs-dir configs
```

### Train only Variant B:
```bash
python scripts/train_pinn_variants.py --variants B --artifact-dir artifacts --configs-dir configs
```

## Output Structure

Each variant training creates:
- `artifacts/pinn_phase1_variant_[AB]/best_model.pt` – Best model checkpoint
- `artifacts/pinn_phase1_variant_[AB]/history.json` – Training history (loss, RMSE per epoch)
- `artifacts/pinn_phase1_variant_[AB]/metrics.json` – Final validation/test metrics + learned physics parameters
- `artifacts/pinn_phase1_variant_[AB]/training_config.json` – Config used for training
- `artifacts/pinn_phase1_variant_[AB]/variant_metadata.json` – Variant info
- `artifacts/variant_training_summary.json` – Summary of all variants trained

## Comparison Checklist

To interpret results:

| Metric | What It Means |
|--------|---------------|
| `best_val_loss` | Overall fit quality (lower is better) |
| `validation.rmse_degC` | Temperature prediction error |
| `validation.rollout_rmse_degC` | Multi-step rollout error (more realistic) |
| `test.rmse_degC` | Generalization to unseen test data |
| `discomfort_comparison.csv` | Comfort violations (upper/lower bound)  |

**Expected outcome:**
- Both variants should have **similar or identical test performance** (same data, same model)
- **Variant A:** `lambda_physics_eff` will adapt during training, visible in history
- **Variant B:** `log_sigma_data` and `log_sigma_physics` will learn, showing model confidence
- **Key finding:** PINN discomfort violations should be very similar to RC model, showing the problem is **feasibility**, not training

## Current Trained Variant Results (March 19, 2026)

| Variant | Best epoch | Best val loss | Validation RMSE (degC) | Test RMSE (degC) | Validation rollout RMSE (degC) | Test rollout RMSE (degC) | Loss weighting mode |
|---|---:|---:|---:|---:|---:|---:|---|
| A_gradient_balance | 148 | 0.004258 | 0.0659 | 0.0809 | 0.3122 | 0.3141 | gradient_balance |
| B_uncertainty | 143 | -6.416616 | 0.0725 | 0.0884 | 0.3315 | 0.3364 | uncertainty |

Observed ranking on the phase1_singlezone test split:

1. Variant A has the lower test RMSE.
2. Variant B remains competitive but slightly weaker on this split.
3. Both variants show similar rollout error scale, supporting feasibility-limited behavior rather than catastrophic model mismatch.

## Future Improvements (Out of Current Scope)

To truly fix upper-bound violations:
- Enable natural ventilation (window opening)
- Add infiltration/damper controls
- Implement active cooling (chiller or heat pump cooling mode)
- These require new BOPTEST case definitions and control signal availability

## References

- Gradient balance loss: Custom approach based on multi-task learning
- Kendall et al., 2018: "Multi-Task Learning Using Uncertainty to Weigh Losses" (arXiv:1802.07335)
