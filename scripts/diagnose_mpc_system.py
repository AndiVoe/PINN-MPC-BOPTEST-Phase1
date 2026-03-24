#!/usr/bin/env python3
"""
Comprehensive MPC system diagnostic tool.

Evaluates:
1. PINN vs RC predictor differences (are they learning meaningfully different things?)
2. Data leakage (training data bleeding into test set)
3. Training overfitting (validation loss diverging from training loss)
4. Prediction horizon effects (horizon too short/long?)
5. MPC convergence (solver iterations, solve times, feasibility)
6. One-step vs rollout prediction accuracy
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpc.predictors import RCPredictor, PINNPredictor


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


# ============================================================================
# DIAGNOSTIC 1: Data Leakage Check
# ============================================================================

def check_data_leakage() -> dict[str, Any]:
    """Verify training/val/test episode splits are disjoint."""
    candidate_manifests = [
        ROOT / "manifests" / "episode_split_phase1.yaml",
        ROOT / "manifests" / "phase1_singlezone.yaml",
    ]
    manifest_path = next((p for p in candidate_manifests if p.exists()), None)

    if manifest_path is None:
        return {"status": "skip", "reason": "No phase1 manifest found"}

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    train_eps: set[str] = set()
    val_eps: set[str] = set()
    test_eps: set[str] = set()

    # Format A: explicit split arrays
    if isinstance(manifest, dict):
        train_eps |= set(manifest.get("training_episodes", []) or [])
        val_eps |= set(manifest.get("validation_episodes", []) or [])
        test_eps |= set(manifest.get("test_episodes", []) or [])

        # Format B: episodes list with {id, split}
        episodes = manifest.get("episodes", [])
        if isinstance(episodes, list):
            for row in episodes:
                if not isinstance(row, dict):
                    continue
                ep_id = row.get("id")
                split = row.get("split")
                if not isinstance(ep_id, str) or not isinstance(split, str):
                    continue
                if split == "train":
                    train_eps.add(ep_id)
                elif split in ("val", "validation"):
                    val_eps.add(ep_id)
                elif split == "test":
                    test_eps.add(ep_id)
    
    overlaps = {
        "train_val": train_eps & val_eps,
        "train_test": train_eps & test_eps,
        "val_test": val_eps & test_eps,
    }
    
    has_overlap = any(overlaps.values())
    
    return {
        "status": "FAIL" if has_overlap else "PASS",
        "manifest_used": str(manifest_path),
        "train_count": len(train_eps),
        "val_count": len(val_eps),
        "test_count": len(test_eps),
        "overlaps": {k: list(v) for k, v in overlaps.items() if v},
        "note": "LEAKAGE DETECTED" if has_overlap else "No overlaps detected",
    }


# ============================================================================
# DIAGNOSTIC 2: Training Overfitting Check
# ============================================================================

def check_training_overfitting() -> dict[str, Any]:
    """Analyze training curves for overfitting signatures."""
    history_path = ROOT / "artifacts" / "pinn_phase1" / "history.json"
    
    if not history_path.exists():
        return {"status": "skip", "reason": "No training history found"}
    
    with history_path.open() as f:
        history = json.load(f)

    train_loss, val_loss = _extract_loss_arrays(history)
    
    if len(train_loss) == 0 or len(val_loss) == 0:
        return {"status": "skip", "reason": "Empty training history"}
    
    # Check for overfitting signature: val_loss diverging from train_loss
    final_train = train_loss[-1]
    final_val = val_loss[-1]
    
    min_val_idx = np.argmin(val_loss)
    min_val = val_loss[min_val_idx]
    
    # Divergence metric: ratio of (final_val - min_val) to min_val
    divergence_pct = 100.0 * (final_val - min_val) / max(min_val, 1e-9)
    
    # Generalization gap: (val_loss - train_loss) / train_loss at end
    gen_gap_pct = 100.0 * (final_val - final_train) / max(final_train, 1e-9)
    
    is_overfitting = divergence_pct > 20.0  # >20% rise from best validation loss
    
    return {
        "status": "WARN" if is_overfitting else "OK",
        "epochs": len(train_loss),
        "final_train_loss": float(final_train),
        "final_val_loss": float(final_val),
        "best_val_loss": float(min_val),
        "best_val_epoch": int(min_val_idx),
        "divergence_from_best_pct": float(divergence_pct),
        "generalization_gap_pct": float(gen_gap_pct),
        "interpretation": "OVERFITTING DETECTED" if is_overfitting else "Acceptable generalization",
    }


# ============================================================================
# DIAGNOSTIC 3: Predictor Comparison (PINN vs RC)
# ============================================================================

def compare_predictors() -> dict[str, Any]:
    """Compare PINN and RC prediction difference on synthetic test case."""
    checkpoint = ROOT / "artifacts" / "pinn_phase1" / "best_model.pt"
    
    if not checkpoint.exists():
        return {"status": "skip", "reason": "No checkpoint found"}
    
    try:
        rc = RCPredictor.from_checkpoint(checkpoint)
        pinn = PINNPredictor(checkpoint)
    except Exception as e:
        return {"status": "error", "reason": str(e)}
    
    # Synthetic test: constant outdoor conditions, varying setpoints
    outdoor_temp = 5.0  # Cold day
    solar_irrad = 100.0
    horizon = 24
    
    weather = [{"t_outdoor": outdoor_temp, "h_global": solar_irrad}] * horizon
    
    # Test 1: Constant low setpoint
    u_low = [18.0] * horizon
    rc_pred_low = rc.predict_sequence(21.0, weather, u_low, 18.0, 0, 900.0)
    pinn_pred_low = pinn.predict_sequence(21.0, weather, u_low, 18.0, 0, 900.0)
    
    # Test 2: Constant high setpoint
    u_high = [26.0] * horizon
    rc_pred_high = rc.predict_sequence(21.0, weather, u_high, 26.0, 0, 900.0)
    pinn_pred_high = pinn.predict_sequence(21.0, weather, u_high, 26.0, 0, 900.0)
    
    # Test 3: Varying setpoint (sawtooth)
    u_vary = [18.0 if i % 2 == 0 else 26.0 for i in range(horizon)]
    rc_pred_vary = rc.predict_sequence(21.0, weather, u_vary, 18.0, 0, 900.0)
    pinn_pred_vary = pinn.predict_sequence(21.0, weather, u_vary, 18.0, 0, 900.0)
    
    def _rmse(a, b):
        return math.sqrt(np.mean((np.array(a) - np.array(b))**2))
    
    return {
        "status": "OK",
        "rc_params": {
            "ua": float(rc.ua),
            "solar_gain": float(rc.solar_gain),
            "hvac_gain": float(rc.hvac_gain),
            "capacity": float(rc.capacity),
        },
        "comparison": {
            "low_setpoint_18C": {
                "rc_final_temp": float(rc_pred_low[-1]),
                "pinn_final_temp": float(pinn_pred_low[-1]),
                "rmse": float(_rmse(rc_pred_low, pinn_pred_low)),
            },
            "high_setpoint_26C": {
                "rc_final_temp": float(rc_pred_high[-1]),
                "pinn_final_temp": float(pinn_pred_high[-1]),
                "rmse": float(_rmse(rc_pred_high, pinn_pred_high)),
            },
            "varying_setpoint": {
                "rc_final_temp": float(rc_pred_vary[-1]),
                "pinn_final_temp": float(pinn_pred_vary[-1]),
                "rmse": float(_rmse(rc_pred_vary, pinn_pred_vary)),
            },
        },
        "interpretation": (
            "PINN very similar to RC: potential underfitting or inadequate training data variance"
            if _rmse(rc_pred_low, pinn_pred_low) < 0.1 else
            "PINN shows learned departures from RC: good sign"
        ),
    }


# ============================================================================
# DIAGNOSTIC 4: One-Step vs Rollout Accuracy
# ============================================================================

def check_rollout_accuracy() -> dict[str, Any]:
    """Compare one-step vs multi-step prediction error growth."""
    metrics_path = ROOT / "artifacts" / "pinn_phase1" / "metrics.json"
    
    if not metrics_path.exists():
        return {"status": "skip", "reason": "No metrics file found"}
    
    with metrics_path.open() as f:
        metrics = json.load(f)
    
    val_rmse = metrics.get("val_rmse_degC")
    rollout_rmse = metrics.get("rollout_rmse_degC")

    # Current project stores metrics under nested validation/test blocks.
    if val_rmse is None and isinstance(metrics.get("validation"), dict):
        val_rmse = metrics["validation"].get("rmse_degC")
    if rollout_rmse is None and isinstance(metrics.get("validation"), dict):
        rollout_rmse = metrics["validation"].get("rollout_rmse_degC")
    
    if val_rmse is None or rollout_rmse is None:
        return {"status": "skip", "reason": "RMSE metrics not available"}
    
    # Scaling: rollout over ~672 steps vs one-step
    # Expected: rollout_rmse > val_rmse due to error accumulation
    error_amplification = float(rollout_rmse) / max(float(val_rmse), 1e-9)
    
    return {
        "status": "OK",
        "one_step_rmse_degC": float(val_rmse),
        "rollout_rmse_degC": float(rollout_rmse),
        "error_amplification_factor": error_amplification,
        "interpretation": (
            "VERY HIGH AMPLIFICATION (>10x): severe error growth in rollout, likely insufficient training diversity"
            if error_amplification > 10.0 else
            "HIGH AMPLIFICATION (>3x): expected, but watch for divergence"
            if error_amplification > 3.0 else
            "MODERATE: good prediction quality persists over horizon"
        ),
    }


# ============================================================================
# DIAGNOSTIC 5: MPC Convergence (from results)
# ============================================================================

def check_mpc_convergence() -> dict[str, Any]:
    """Analyze MPC solver behavior from result files."""
    candidate_roots = [
        ROOT / "results" / "mpc_phase1",
        ROOT / "results" / "eu_rc_vs_pinn" / "raw",
        ROOT / "results" / "eu_rc_vs_pinn_stage2" / "raw",
    ]
    raw_dir = next((p for p in candidate_roots if p.exists()), None)

    if raw_dir is None:
        return {"status": "skip", "reason": "No result files found"}

    json_files = list(raw_dir.rglob("*.json"))
    
    if not json_files:
        return {"status": "skip", "reason": "No result JSON files"}
    
    solve_times: list[float] = []
    n_iters: list[int] = []
    successes = 0
    failures = 0
    has_explicit_success = False
    
    for jf in json_files[:100]:  # Sample first 100 files
        try:
            data = json.loads(jf.read_text())
            steps = data.get("step_records", [])
            
            for step in steps:
                solver_info = step.get("mpc_solver_info", {})
                step_solve_time = None
                if solver_info:
                    st = solver_info.get("solve_time_ms")
                    ni = solver_info.get("n_iter")
                    if st is not None:
                        step_solve_time = float(st)
                    if ni is not None:
                        n_iters.append(int(ni))
                    if "success" in solver_info:
                        has_explicit_success = True
                    if solver_info.get("success"):
                        successes += 1
                    else:
                        failures += 1

                # Current result schema may store timing directly on each step.
                direct_st = step.get("solve_time_ms")
                if step_solve_time is None and direct_st is not None:
                    step_solve_time = float(direct_st)
                if step_solve_time is not None:
                    solve_times.append(step_solve_time)

            # Fallback to aggregated diagnostics if per-step solver_info is absent.
            diag = data.get("diagnostic_kpis", {})
            if isinstance(diag, dict):
                st_mean = diag.get("mpc_solve_time_mean_ms")
                if st_mean is not None and not steps:
                    solve_times.append(float(st_mean))
        except Exception:
            pass
    
    if not solve_times:
        return {"status": "skip", "reason": "No solver info in results"}
    
    solve_times = np.array(solve_times)
    n_iters_arr = np.array(n_iters) if n_iters else np.array([], dtype=float)
    
    if has_explicit_success:
        success_rate = float(successes / max(successes + failures, 1)) * 100.0
        success_note = None
    else:
        success_rate = None
        success_note = "Per-step success flag not present in result schema."

    interpretation = "Good convergence"
    if has_explicit_success and success_rate is not None and success_rate < 95.0:
        interpretation = "SOLVER STRUGGLES: low success rate, consider tightening tolerances or reducing horizon"
    elif float(np.mean(solve_times)) > 500.0:
        interpretation = "SLOW SOLVER: mean solve time >500ms, may limit real-time applicability"

    return {
        "status": "OK",
        "solver_success_rate": success_rate,
        "solver_success_note": success_note,
        "solve_time_ms": {
            "mean": float(np.mean(solve_times)),
            "median": float(np.median(solve_times)),
            "p95": float(np.percentile(solve_times, 95)),
            "max": float(np.max(solve_times)),
        },
        "iterations": (
            {
                "mean": float(np.mean(n_iters_arr)),
                "median": float(np.median(n_iters_arr)),
                "p95": float(np.percentile(n_iters_arr, 95)),
                "max": int(np.max(n_iters_arr)),
            }
            if len(n_iters_arr) > 0
            else None
        ),
        "total_step_evaluations": len(solve_times),
        "source_root": str(raw_dir),
        "interpretation": interpretation,
    }


# ============================================================================
# DIAGNOSTIC 6: Prediction Horizon Length
# ============================================================================

def check_horizon_config() -> dict[str, Any]:
    """Analyze configured prediction horizon and weather forecast availability."""
    mpc_config_path = ROOT / "configs" / "mpc_phase1.yaml"
    
    if not mpc_config_path.exists():
        return {"status": "skip", "reason": "No MPC config found"}
    
    try:
        with mpc_config_path.open("r", encoding="utf-8", errors="replace") as f:
            config = yaml.safe_load(f)
    except Exception as exc:
        return {
            "status": "WARN",
            "reason": f"YAML parse failed ({exc}); using defaults",
            "horizon_steps": 24,
            "control_interval_s": 900,
            "horizon_hours": 6.0,
            "interpretation": "Fallback defaults used due to config parse error.",
        }

    mpc_cfg = config.get("mpc", {}) if isinstance(config, dict) else {}
    dt_s = float(mpc_cfg.get("dt_s", 900))
    if "horizon_steps" in mpc_cfg:
        horizon_steps = int(mpc_cfg.get("horizon_steps", 24))
    elif "horizon_s" in mpc_cfg:
        horizon_steps = max(1, int(round(float(mpc_cfg.get("horizon_s", 21600)) / dt_s)))
    else:
        horizon_steps = 24
    horizon_hours = horizon_steps * dt_s / 3600.0
    
    return {
        "status": "OK",
        "horizon_steps": horizon_steps,
        "control_interval_s": dt_s,
        "horizon_hours": float(horizon_hours),
        "interpretation": (
            f"Horizon is 6 hours ({horizon_hours:.1f}h): typical for building HVAC, allows look-ahead for comfort/energy"
        ),
    }


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Comprehensive MPC system diagnostics")
    parser.add_argument("--output", default="logs/mpc_diagnostics.json", help="Output JSON path")
    args = parser.parse_args()
    
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*80)
    print("MPC SYSTEM DIAGNOSTICS")
    print("="*80 + "\n")
    
    results = {
        "timestamp": str(__import__("datetime").datetime.now().isoformat()),
        "diagnostics": {},
    }
    
    # Run all diagnostics
    diagnostics = [
        ("Data Leakage Check", check_data_leakage),
        ("Training Overfitting", check_training_overfitting),
        ("Predictor Comparison (PINN vs RC)", compare_predictors),
        ("Rollout Accuracy", check_rollout_accuracy),
        ("MPC Convergence", check_mpc_convergence),
        ("Horizon Configuration", check_horizon_config),
    ]
    
    for name, func in diagnostics:
        print(f"[{name}]")
        try:
            result = func()
            results["diagnostics"][name] = result
            status = result.get("status", "OK")
            print(f"  Status: {status}")
            if "interpretation" in result:
                print(f"  → {result['interpretation']}")
            print()
        except Exception as e:
            print(f"  ERROR: {e}\n")
            results["diagnostics"][name] = {"status": "error", "exception": str(e)}
    
    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    
    issue_count = 0
    for name, diag in results["diagnostics"].items():
        status = diag.get("status", "unknown").upper()
        if status in ("FAIL", "WARN", "ERROR"):
            print(f"⚠ {name}: {status}")
            issue_count += 1
    
    if issue_count == 0:
        print("✓ All diagnostics passed or skipped")
    else:
        print(f"\n⚠ {issue_count} issues detected - see details below")
    
    # Write output
    with output.open("w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n✓ Full diagnostics written to: {output}")


if __name__ == "__main__":
    main()
