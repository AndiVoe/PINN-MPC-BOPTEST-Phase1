#!/usr/bin/env python3
"""
Train PINN variants (A and B) with different loss weighting strategies.

Variant A: Gradient-balanced weighting (automatic balance of comfort vs physics)
Variant B: Uncertainty weighting (model learns confidence bounds)

Both variants use the same architecture and dataset but differ in loss weighting.
Results are saved to separate checkpoint directories for ablation comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pinn_model import SingleZonePINN, build_datasets, load_training_config, train_model
from pinn_model.training import set_seed


def train_variant(variant: str, config_path: Path, root: Path, artifact_dir: Path) -> dict:
    """
    Train a single PINN variant and return metrics.

    Parameters
    ----------
    variant : str
        Variant name ('A' or 'B').
    config_path : Path
        Path to config YAML file (absolute).
    root : Path
        Project root directory.
    artifact_dir : Path
        Base artifact directory.

    Returns
    -------
    result : dict
        Training result with metrics and checkpoint path.
    """

    config = load_training_config(config_path)
    study_id = config["study_id"]

    output_dir = artifact_dir / study_id
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"Training Variant {variant}: {study_id}")
    print(f"Config: {config_path}")
    print(f"Output: {output_dir}")
    print(f"Loss weighting mode: {config['training'].get('loss_weighting', {}).get('mode', 'manual')}")
    print(f"{'='*70}\n")

    try:
        set_seed(int(config["training"]["seed"]))
        datasets = build_datasets(config, root)
        model = SingleZonePINN(
            input_dim=len(datasets["feature_names"]),
            hidden_dim=int(config["model"]["hidden_dim"]),
            depth=int(config["model"]["depth"]),
            dropout=float(config["model"].get("dropout", 0.0)),
        )

        result = train_model(
            model,
            datasets,
            config,
            output_dir,
            resume_checkpoint=False,
        )

        metrics_path = output_dir / "metrics.json"
        metrics_payload: dict = {}
        if metrics_path.exists():
            metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))

        validation = metrics_payload.get("validation", {}) if isinstance(metrics_payload, dict) else {}
        test = metrics_payload.get("test", {}) if isinstance(metrics_payload, dict) else {}
        robustness = metrics_payload.get("robustness_test", {}) if isinstance(metrics_payload, dict) else {}
        noise_5 = robustness.get("noise_5pct", {}) if isinstance(robustness, dict) else {}
        noise_10 = robustness.get("noise_10pct", {}) if isinstance(robustness, dict) else {}

        # Save variant metadata
        metadata = {
            "variant": variant,
            "study_id": study_id,
            "config_path": str(config_path),
            "output_dir": str(output_dir),
            "best_epoch": result["best_epoch"],
            "best_val_loss": result["best_val_loss"],
            "training_config": config["training"],
            "model_config": config["model"],
            "loss_weighting_mode": config["training"].get("loss_weighting", {}).get("mode", "manual"),
            "validation": validation,
            "test": test,
            "robustness_test": robustness,
        }

        metadata_file = output_dir / "variant_metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))

        return {
            "variant": variant,
            "status": "SUCCESS",
            "study_id": study_id,
            "output_dir": str(output_dir),
            "best_epoch": result["best_epoch"],
            "best_val_loss": result["best_val_loss"],
            "validation_rmse_degC": float(validation.get("rmse_degC", 0.0)),
            "validation_mape_pct": float(validation.get("mape_pct", 0.0)),
            "validation_r2_score": float(validation.get("r2_score", 0.0)),
            "test_rmse_degC": float(test.get("rmse_degC", 0.0)),
            "test_mape_pct": float(test.get("mape_pct", 0.0)),
            "test_r2_score": float(test.get("r2_score", 0.0)),
            "test_physics_loss": float(test.get("physics_loss", 0.0)),
            "robust_noise_5pct_rmse_degC": float(noise_5.get("rmse_degC", 0.0)),
            "robust_noise_10pct_rmse_degC": float(noise_10.get("rmse_degC", 0.0)),
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "variant": variant,
            "status": "FAILED",
            "study_id": study_id,
            "error": str(e),
            "output_dir": str(output_dir),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train PINN variants with different loss weighting.")
    parser.add_argument(
        "--variants",
        choices=["A", "B", "AB"],
        default="AB",
        help="Which variants to train (A, B, or both AB)",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts"),
        help="Base artifact directory",
    )
    parser.add_argument(
        "--configs-dir",
        type=Path,
        default=Path("configs"),
        help="Configs directory",
    )

    args = parser.parse_args()

    root = ROOT
    configs_dir = root / args.configs_dir
    artifact_dir = root / args.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    if "A" in args.variants:
        config_a = configs_dir / "pinn_phase1_variant_a.yaml"
        if not config_a.exists():
            print(f"ERROR: Config not found: {config_a}")
            return 1
        results["A"] = train_variant("A", config_a, root, artifact_dir)

    if "B" in args.variants:
        config_b = configs_dir / "pinn_phase1_variant_b.yaml"
        if not config_b.exists():
            print(f"ERROR: Config not found: {config_b}")
            return 1
        results["B"] = train_variant("B", config_b, root, artifact_dir)

    # Summary
    print(f"\n{'='*70}")
    print("TRAINING SUMMARY")
    print(f"{'='*70}")
    for variant, result in results.items():
        status = result["status"]
        study_id = result.get("study_id", "?")
        if status == "SUCCESS":
            best_epoch = result.get("best_epoch", "?")
            best_loss = result.get("best_val_loss", "?")
            print(f"Variant {variant}: OK {study_id}")
            print(f"  Best epoch: {best_epoch},  best val loss: {best_loss:.6f}")
            print(
                "  Validation: "
                f"RMSE={result.get('validation_rmse_degC', 0.0):.4f} degC, "
                f"MAPE={result.get('validation_mape_pct', 0.0):.2f}%, "
                f"R2={result.get('validation_r2_score', 0.0):.4f}"
            )
            print(
                "  Test: "
                f"RMSE={result.get('test_rmse_degC', 0.0):.4f} degC, "
                f"MAPE={result.get('test_mape_pct', 0.0):.2f}%, "
                f"R2={result.get('test_r2_score', 0.0):.4f}, "
                f"physics_loss={result.get('test_physics_loss', 0.0):.6f}"
            )
            print(
                "  Robustness (test split): "
                f"noise_5pct_RMSE={result.get('robust_noise_5pct_rmse_degC', 0.0):.4f} degC, "
                f"noise_10pct_RMSE={result.get('robust_noise_10pct_rmse_degC', 0.0):.4f} degC"
            )
        else:
            error = result.get("error", "Unknown error")
            print(f"Variant {variant}: FAILED")
            print(f"  Error: {error}")

    # Save summary
    summary_file = artifact_dir / "variant_training_summary.json"
    summary_file.write_text(json.dumps(results, indent=2))
    print(f"\nSummary saved to: {summary_file}")

    all_success = all(r["status"] == "SUCCESS" for r in results.values())
    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
