#!/usr/bin/env python3
"""
PINN Training Quality Validation.

Checks:
1. Validation loss progression (smooth convergence?)
2. Training data variation (enough diversity for generalization?)
3. Physics loss contribution (is physics regularization active?)
4. Learned parameter bounds (are physics params staying reasonable?)
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pinn_model import SingleZonePINN, build_datasets, load_training_config


def _extract_loss_arrays(history: Any) -> tuple[np.ndarray, np.ndarray]:
    """Support both history formats: dict-of-lists and list-of-epoch-records."""
    if isinstance(history, dict):
        train = np.asarray(history.get("train_loss", []), dtype=float)
        val = np.asarray(history.get("val_loss", []), dtype=float)
        return train, val
    if isinstance(history, list):
        train_vals: list[float] = []
        val_vals: list[float] = []
        for row in history:
            if not isinstance(row, dict):
                continue
            tr = row.get("train_loss")
            va = row.get("val_loss")
            if tr is None or va is None:
                continue
            train_vals.append(float(tr))
            val_vals.append(float(va))
        return np.asarray(train_vals, dtype=float), np.asarray(val_vals, dtype=float)
    return np.asarray([], dtype=float), np.asarray([], dtype=float)


def _safe_pearson(x: np.ndarray, y: np.ndarray) -> float:
    if x.size == 0 or y.size == 0 or x.shape[0] != y.shape[0]:
        return 0.0
    x_std = float(np.std(x))
    y_std = float(np.std(y))
    if x_std < 1e-12 or y_std < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _evaluate_residual_input_correlation(
    *,
    checkpoint_path: Path,
    config_path: Path,
) -> dict[str, Any]:
    if not checkpoint_path.exists():
        return {"status": "skip", "reason": f"Checkpoint not found: {checkpoint_path}"}
    if not config_path.exists():
        return {"status": "skip", "reason": f"Config not found: {config_path}"}

    config = load_training_config(config_path)
    datasets = build_datasets(config, ROOT)
    val_samples = datasets.get("val_samples", [])
    if not val_samples:
        return {"status": "skip", "reason": "No validation samples available"}

    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    ckpt_config = ckpt.get("config", config)
    model_cfg = ckpt_config.get("model", {}) if isinstance(ckpt_config, dict) else {}
    model = SingleZonePINN(
        input_dim=len(datasets["feature_names"]),
        hidden_dim=int(model_cfg.get("hidden_dim", config["model"]["hidden_dim"])),
        depth=int(model_cfg.get("depth", config["model"]["depth"])),
        dropout=float(model_cfg.get("dropout", config["model"].get("dropout", 0.0))),
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    norm = ckpt.get("normalization", datasets["stats"].to_dict())
    feature_mean = torch.tensor(norm["feature_mean"], dtype=torch.float32)
    feature_std = torch.tensor(norm["feature_std"], dtype=torch.float32)

    feature_matrix = np.asarray([sample.features for sample in val_samples], dtype=np.float32)
    t_zone = torch.tensor([sample.t_zone for sample in val_samples], dtype=torch.float32)
    t_outdoor = torch.tensor([sample.t_outdoor for sample in val_samples], dtype=torch.float32)
    h_global = torch.tensor([sample.h_global for sample in val_samples], dtype=torch.float32)
    u_heating = torch.tensor([sample.u_heating for sample in val_samples], dtype=torch.float32)
    dt_s = torch.tensor([sample.dt_s for sample in val_samples], dtype=torch.float32)
    target = np.asarray([sample.target_next_t_zone for sample in val_samples], dtype=np.float32)

    features_t = torch.tensor(feature_matrix, dtype=torch.float32)
    features_n = (features_t - feature_mean) / feature_std

    with torch.no_grad():
        pred = model(features_n, t_zone, t_outdoor, h_global, u_heating, dt_s)["predicted_next"].cpu().numpy()
    residuals = target - pred

    feature_names = datasets["feature_names"]
    corrs: dict[str, float] = {}
    for idx, name in enumerate(feature_names):
        corrs[name] = _safe_pearson(feature_matrix[:, idx], residuals)

    abs_corrs = {name: abs(value) for name, value in corrs.items()}
    max_feature = max(abs_corrs, key=abs_corrs.get)
    max_abs_corr = float(abs_corrs[max_feature])
    mean_abs_corr = float(np.mean(list(abs_corrs.values())))

    # Rule-of-thumb thresholds for practical whiteness diagnostics.
    status = "OK"
    interpretation = "Residuals are weakly correlated with inputs (close to white-noise behavior)."
    if max_abs_corr > 0.30 or mean_abs_corr > 0.15:
        status = "WARN"
        interpretation = (
            "Residuals are correlated with inputs; likely unmodeled dynamics remain. "
            "Consider richer features/model capacity or additional training data diversity."
        )
    elif max_abs_corr > 0.20 or mean_abs_corr > 0.10:
        status = "WARN"
        interpretation = "Residual-input correlation is moderate; monitor for missed structure."

    return {
        "status": status,
        "n_validation_samples": int(len(val_samples)),
        "residual_rmse_degC": float(math.sqrt(float(np.mean(residuals**2)))),
        "residual_mae_degC": float(np.mean(np.abs(residuals))),
        "max_abs_feature_correlation": max_abs_corr,
        "max_corr_feature": max_feature,
        "mean_abs_feature_correlation": mean_abs_corr,
        "feature_correlations": corrs,
        "interpretation": interpretation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PINN training quality")
    parser.add_argument(
        "--checkpoint",
        default="artifacts/pinn_phase1/best_model.pt",
        help="Path to checkpoint file",
    )
    parser.add_argument(
        "--history",
        default="artifacts/pinn_phase1/history.json",
        help="Path to training history JSON",
    )
    parser.add_argument(
        "--metrics",
        default="artifacts/pinn_phase1/metrics.json",
        help="Path to metrics JSON",
    )
    parser.add_argument(
        "--config",
        default="configs/pinn_phase1.yaml",
        help="Path to training config YAML",
    )
    args = parser.parse_args()
    
    checkpoint_path = Path(args.checkpoint)
    history_path = Path(args.history)
    metrics_path = Path(args.metrics)
    config_path = Path(args.config)
    
    print("\n" + "="*100)
    print("PINN TRAINING QUALITY VALIDATION")
    print("="*100 + "\n")
    
    results = {
        "timestamp": str(__import__("datetime").datetime.now().isoformat()),
        "checks": {},
    }
    
    # ========================================================================
    # CHECK 1: Training History Convergence
    # ========================================================================
    print("[1] Training History Convergence")
    
    if history_path.exists():
        with history_path.open() as f:
            history = json.load(f)

        train_loss, val_loss = _extract_loss_arrays(history)
        
        if len(train_loss) > 0 and len(val_loss) > 0:
            # Check for smooth convergence (no spikes)
            train_diffs = np.diff(train_loss)
            train_increasing = np.sum(train_diffs > 0)
            
            # Check if best validation loss is at the end (no early stopping improvement)
            best_val_idx = np.argmin(val_loss)
            epochs_since_best = len(val_loss) - 1 - best_val_idx
            
            # Smoothness metric: coefficient of variation of loss differences
            train_smoothness = np.std(np.abs(train_diffs)) / np.mean(np.abs(train_diffs)) if len(train_diffs) > 0 else 0.0
            
            status = "OK"
            msg = "Smooth convergence observed"
            
            if train_increasing > 0.5 * len(train_diffs):
                status = "WARN"
                msg = "Training loss increasing frequently (possible instability)"
            
            if epochs_since_best > 20:
                status = "WARN"
                msg = f"Best validation loss at epoch {best_val_idx}, but trained to epoch {len(val_loss)-1} (overfitting or no early stopping)"
            
            if train_smoothness > 2.0:
                status = "WARN"
                msg = "High loss spike variability (possible numerical issues)"
            
            print(f"  Status: {status}")
            print(f"  Epochs: {len(train_loss)}")
            print(f"  Final train loss: {train_loss[-1]:.6f}")
            print(f"  Final val loss: {val_loss[-1]:.6f}")
            print(f"  Best val loss epoch: {best_val_idx} (current epoch {len(val_loss)-1})")
            print(f"  → {msg}")
            print()
            
            results["checks"]["convergence"] = {
                "status": status,
                "epochs": int(len(train_loss)),
                "final_train_loss": float(train_loss[-1]),
                "final_val_loss": float(val_loss[-1]),
                "best_val_epoch": int(best_val_idx),
                "epochs_since_best": int(epochs_since_best),
                "message": msg,
            }
        else:
            print("  ⚠ Empty training history")
            results["checks"]["convergence"] = {"status": "skip", "reason": "Empty history"}
    else:
        print(f"  ⚠ No history file found at {history_path}")
        results["checks"]["convergence"] = {"status": "skip", "reason": "File not found"}
    
    # ========================================================================
    # CHECK 2: Metrics Sanity
    # ========================================================================
    print("[2] Metrics Sanity")
    
    if metrics_path.exists():
        with metrics_path.open() as f:
            metrics = json.load(f)

        val_rmse = metrics.get("val_rmse_degC")
        val_mae = metrics.get("val_mae_degC")
        rollout_rmse = metrics.get("rollout_rmse_degC")

        # Support current nested metrics structure under "validation".
        validation = metrics.get("validation", {}) if isinstance(metrics, dict) else {}
        if val_rmse is None and isinstance(validation, dict):
            val_rmse = validation.get("rmse_degC")
        if val_mae is None and isinstance(validation, dict):
            val_mae = validation.get("mae_degC")
        if rollout_rmse is None and isinstance(validation, dict):
            rollout_rmse = validation.get("rollout_rmse_degC")
        
        if all(x is not None for x in [val_rmse, val_mae, rollout_rmse]):
            # Check if metrics are reasonable
            status = "OK"
            issues = []
            
            if val_rmse < 0.01:
                status = "WARN"
                issues.append(f"Validation RMSE unrealistically low ({val_rmse:.6f} degC)")
            
            if rollout_rmse < val_rmse:
                status = "WARN"
                issues.append("Rollout RMSE lower than one-step RMSE (impossible, error should accumulate)")
            
            amplification = rollout_rmse / max(val_rmse, 1e-9)
            if amplification > 20.0:
                status = "WARN"
                issues.append(f"Error amplification >20x in rollout (severe degradation over horizon)")
            
            print(f"  Status: {status}")
            print(f"  One-step validation RMSE: {val_rmse:.4f} degC")
            print(f"  One-step validation MAE: {val_mae:.4f} degC")
            print(f"  Multi-step rollout RMSE: {rollout_rmse:.4f} degC")
            print(f"  Error amplification: {amplification:.2f}x")
            
            if issues:
                for issue in issues:
                    print(f"  ⚠ {issue}")
            print()
            
            results["checks"]["metrics"] = {
                "status": status,
                "val_rmse_degC": float(val_rmse),
                "val_mae_degC": float(val_mae),
                "rollout_rmse_degC": float(rollout_rmse),
                "amplification_factor": float(amplification),
                "issues": issues,
            }
        else:
            print("  ⚠ Incomplete metrics")
            results["checks"]["metrics"] = {"status": "skip", "reason": "Incomplete metrics"}
    else:
        print(f"  ⚠ No metrics file found at {metrics_path}")
        results["checks"]["metrics"] = {"status": "skip", "reason": "File not found"}
    
    # ========================================================================
    # CHECK 3: Physics Parameters
    # ========================================================================
    print("[3] Learned Physics Parameters")
    
    if checkpoint_path.exists():
        try:
            ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
            physics_params = ckpt.get("physics_parameters", {})

            # Fallback for checkpoints without embedded physics_parameters.
            if not physics_params and metrics_path.exists():
                with metrics_path.open() as f:
                    metrics = json.load(f)
                maybe_pp = metrics.get("physics_parameters", {}) if isinstance(metrics, dict) else {}
                if isinstance(maybe_pp, dict):
                    physics_params = maybe_pp
            
            if physics_params:
                ua = float(physics_params.get("ua", 0.0))
                solar_gain = float(physics_params.get("solar_gain", 0.0))
                hvac_gain = float(physics_params.get("hvac_gain", 0.0))
                capacity = float(physics_params.get("capacity", 0.0))
                
                status = "OK"
                issues = []
                
                # Check bounds for single-zone building (~50-100 m2)
                # UA typical range: 0.1-1.0 W/K for small residential
                if ua < 0.01 or ua > 10.0:
                    status = "WARN"
                    issues.append(f"UA out of typical range: {ua:.4f} W/K")
                
                # Solar gain: typical 0.1-1.0 W/(W/m2) for small buildings
                if solar_gain < 0.01 or solar_gain > 5.0:
                    status = "WARN"
                    issues.append(f"Solar gain out of range: {solar_gain:.4f}")
                
                # HVAC gain: typical 0.1-2.0 for small buildings
                if hvac_gain < 0.01 or hvac_gain > 10.0:
                    status = "WARN"
                    issues.append(f"HVAC gain out of range: {hvac_gain:.4f}")
                
                # Capacity: typical 1-50 kJ/K for small zone
                if capacity < 0.1 or capacity > 100.0:
                    status = "WARN"
                    issues.append(f"Capacity out of range: {capacity:.4f} kJ/K")
                
                print(f"  Status: {status}")
                print(f"  UA (envelope conductance): {ua:.4f} W/K")
                print(f"  Solar gain (0-1): {solar_gain:.4f}")
                print(f"  HVAC gain (0-2): {hvac_gain:.4f}")
                print(f"  Capacity (thermal mass): {capacity:.4f} kJ/K")
                
                if issues:
                    for issue in issues:
                        print(f"  ⚠ {issue}")
                print()
                
                results["checks"]["physics_params"] = {
                    "status": status,
                    "ua": float(ua),
                    "solar_gain": float(solar_gain),
                    "hvac_gain": float(hvac_gain),
                    "capacity": float(capacity),
                    "issues": issues,
                }
            else:
                print("  ⚠ No physics parameters in checkpoint")
                results["checks"]["physics_params"] = {"status": "skip", "reason": "Missing in checkpoint"}
        except Exception as e:
            print(f"  ✗ Error loading checkpoint: {e}")
            results["checks"]["physics_params"] = {"status": "error", "reason": str(e)}
    else:
        print(f"  ⚠ No checkpoint found at {checkpoint_path}")
        results["checks"]["physics_params"] = {"status": "skip", "reason": "File not found"}
    
    # ========================================================================
    # CHECK 4: Training Configuration
    # ========================================================================
    print("[4] Training Configuration Review")
    
    if config_path.exists():
        try:
            import yaml
            with config_path.open() as f:
                config = yaml.safe_load(f)
            
            epochs = config.get("epochs", 150)
            batch_size = config.get("batch_size", 256)
            learning_rate = config.get("learning_rate", 0.001)
            loss_weighting_mode = config.get("loss_weighting", {}).get("mode", "unknown")
            lambda_physics = config.get("loss_weighting", {}).get("lambda_physics", 0.01)
            
            status = "OK"
            msgs = []
            
            if epochs < 50:
                status = "WARN"
                msgs.append(f"Low epoch count ({epochs}, typical ≥100)")
            
            if batch_size > 512:
                msgs.append(f"Large batch size ({batch_size}, may reduce gradient noise)")
            
            if learning_rate > 0.01:
                status = "WARN"
                msgs.append(f"High learning rate ({learning_rate}, may cause instability)")
            
            if lambda_physics < 0.001:
                msgs.append(f"Very low physics weight ({lambda_physics}, physics regularization weak)")
            elif lambda_physics > 1.0:
                status = "WARN"
                msgs.append(f"Very high physics weight ({lambda_physics}, may over-constrain learning)")
            
            print(f"  Status: {status}")
            print(f"  Epochs: {epochs}")
            print(f"  Batch size: {batch_size}")
            print(f"  Learning rate: {learning_rate}")
            print(f"  Loss weighting mode: {loss_weighting_mode}")
            print(f"  λ_physics (physics weight): {lambda_physics}")
            
            if msgs:
                for msg in msgs:
                    print(f"  → {msg}")
            print()
            
            results["checks"]["config"] = {
                "status": status,
                "epochs": int(epochs),
                "batch_size": int(batch_size),
                "learning_rate": float(learning_rate),
                "loss_weighting_mode": str(loss_weighting_mode),
                "lambda_physics": float(lambda_physics),
                "notes": msgs,
            }
        except Exception as e:
            print(f"  ✗ Error reading config: {e}\n")
            results["checks"]["config"] = {"status": "error", "reason": str(e)}
    else:
        print(f"  ⚠ No config found at {config_path}\n")
        results["checks"]["config"] = {"status": "skip", "reason": "File not found"}

    # ========================================================================
    # CHECK 5: Residual Whiteness (Residual vs Input Correlation)
    # ========================================================================
    print("[5] Residual Whiteness vs Inputs")
    residual_check = _evaluate_residual_input_correlation(
        checkpoint_path=checkpoint_path,
        config_path=config_path,
    )
    results["checks"]["residual_whiteness"] = residual_check

    status = residual_check.get("status", "skip")
    if status == "skip":
        print(f"  ⚠ Skipped: {residual_check.get('reason', 'insufficient data')}\n")
    elif status == "error":
        print(f"  ✗ Error: {residual_check.get('reason', 'unknown error')}\n")
    else:
        print(f"  Status: {status}")
        print(f"  Validation samples: {residual_check['n_validation_samples']}")
        print(f"  Residual RMSE: {residual_check['residual_rmse_degC']:.4f} degC")
        print(f"  Max |corr(residual, feature)|: {residual_check['max_abs_feature_correlation']:.3f} "
              f"({residual_check['max_corr_feature']})")
        print(f"  Mean |corr(residual, feature)|: {residual_check['mean_abs_feature_correlation']:.3f}")
        print(f"  → {residual_check['interpretation']}")
        print()
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("="*100)
    print("VALIDATION SUMMARY")
    print("="*100 + "\n")
    
    issue_count = 0
    for check_name, check_result in results["checks"].items():
        status = check_result.get("status", "unknown")
        if status in ("WARN", "ERROR"):
            if status == "WARN":
                print(f"⚠ {check_name}: {status}")
            else:
                print(f"✗ {check_name}: {status}")
            issue_count += 1
        elif status == "OK":
            print(f"✓ {check_name}: {status}")
    
    print()
    if issue_count == 0:
        print("✓ All training quality checks passed!")
    else:
        print(f"⚠ {issue_count} warning(s) or error(s) detected")
    
    print("\n" + "="*100)


if __name__ == "__main__":
    main()
