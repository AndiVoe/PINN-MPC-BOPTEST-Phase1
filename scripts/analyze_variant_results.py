#!/usr/bin/env python3
"""
Diagnostic report generator for comfort feasibility analysis.
Analyzes variant training results and MPC benchmark discomfort metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


def analyze_variant_metrics(variant_dir: Path) -> dict[str, Any]:
    """Analyze metrics from a trained variant."""
    metrics_file = variant_dir / "metrics.json"
    history_file = variant_dir / "history.json"

    if not metrics_file.exists():
        return {"error": f"metrics.json not found in {variant_dir}"}

    metrics = json.load(open(metrics_file))
    history = json.load(open(history_file)) if history_file.exists() else []

    analysis = {
        "variant_dir": str(variant_dir),
        "best_epoch": metrics.get("best_epoch"),
        "best_val_loss": metrics.get("best_val_loss"),
        "test_rmse_degC": metrics.get("test", {}).get("rmse_degC"),
        "test_rollout_rmse_degC": metrics.get("test", {}).get("rollout_rmse_degC"),
        "val_rmse_degC": metrics.get("validation", {}).get("rmse_degC"),
    }

    # Extract loss weighting info
    lw = metrics.get("loss_weighting", {})
    if "lambda_physics_eff" in lw:
        # Variant A
        analysis["mode"] = "gradient_balance"
        analysis["final_lambda_physics"] = lw.get("lambda_physics_eff")
    elif "log_sigma_data" in lw:
        # Variant B
        analysis["mode"] = "uncertainty"
        analysis["log_sigma_data"] = lw.get("log_sigma_data")
        analysis["log_sigma_physics"] = lw.get("log_sigma_physics")
        analysis["weight_data"] = lw.get("weight_data")
        analysis["weight_physics"] = lw.get("weight_physics")

    # Convergence info
    if history:
        analysis["total_epochs"] = len(history)
        analysis["train_loss_trajectory"] = [h.get("train_loss") for h in history[-5:]]
        analysis["val_loss_trajectory"] = [h.get("val_loss") for h in history[-5:]]

    return analysis


def compare_variants(artifact_dir: Path) -> dict[str, Any]:
    """Compare two trained variants."""
    variant_a = artifact_dir / "pinn_phase1_variant_a_gradient_balance"
    variant_b = artifact_dir / "pinn_phase1_variant_b_uncertainty"

    analysis_a = analyze_variant_metrics(variant_a)
    analysis_b = analyze_variant_metrics(variant_b)

    comparison = {
        "variant_a": analysis_a,
        "variant_b": analysis_b,
    }

    # Calculate differences
    if "error" not in analysis_a and "error" not in analysis_b:
        rmse_diff = (analysis_a.get("test_rmse_degC", 0) - analysis_b.get("test_rmse_degC", 0))
        comparison["rmse_difference_degC"] = round(rmse_diff, 4)

        if abs(rmse_diff) < 0.01:
            comparison["interpretation"] = "Variants have equivalent performance (EXPECTED)"
        elif rmse_diff > 0:
            comparison["interpretation"] = "Variant B slightly better than Variant A"
        else:
            comparison["interpretation"] = "Variant A slightly better than Variant B"

    return comparison


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnostic report for comfort feasibility analysis results."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts"),
        help="Artifact directory containing variant results",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Save report to JSON file (if provided)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("COMFORT FEASIBILITY ANALYSIS - DIAGNOSTIC REPORT")
    print("=" * 70)

    artifact_dir = args.artifact_dir
    if not artifact_dir.exists():
        print(f"ERROR: Artifact directory not found: {artifact_dir}")
        return 1

    comparison = compare_variants(artifact_dir)

    # Print Variant A
    if "error" not in comparison["variant_a"]:
        va = comparison["variant_a"]
        print(f"\nVariant A (Gradient-Balanced Weighting):")
        print(f"  Mode: {va.get('mode')}")
        print(f"  Best epoch: {va.get('best_epoch')}")
        print(f"  Test RMSE: {va.get('test_rmse_degC'):.4f} °C")
        print(f"  Final λ_physics: {va.get('final_lambda_physics', 'N/A')}")
        if va.get("train_loss_trajectory"):
            print(f"  Recent val losses: {[f'{v:.4f}' for v in va['val_loss_trajectory'][-3:]]}")
    else:
        print(f"\nVariant A: ERROR - {comparison['variant_a'].get('error')}")

    # Print Variant B
    if "error" not in comparison["variant_b"]:
        vb = comparison["variant_b"]
        print(f"\nVariant B (Uncertainty Weighting):")
        print(f"  Mode: {vb.get('mode')}")
        print(f"  Best epoch: {vb.get('best_epoch')}")
        print(f"  Test RMSE: {vb.get('test_rmse_degC'):.4f} °C")
        if vb.get("log_sigma_physics") is not None:
            print(f"  Learned log_σ_physics: {vb.get('log_sigma_physics'):.4f}")
            print(f"  Weight_physics: {vb.get('weight_physics'):.4f}")
        if vb.get("train_loss_trajectory"):
            print(f"  Recent val losses: {[f'{v:.4f}' for v in vb['val_loss_trajectory'][-3:]]}")
    else:
        print(f"\nVariant B: ERROR - {comparison['variant_b'].get('error')}")

    # Print comparison
    if "rmse_difference_degC" in comparison:
        print(f"\nComparison:")
        print(f"  RMSE difference: {comparison['rmse_difference_degC']:.4f} °C")
        print(f"  Interpretation: {comparison['interpretation']}")

    # Save report if requested
    if args.output_file:
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_file, "w") as f:
            json.dump(comparison, f, indent=2)
        print(f"\nReport saved to: {args.output_file}")

    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
