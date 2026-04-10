#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
CASES = [
    "bestest_hydronic",
    "bestest_hydronic_heat_pump",
    "singlezone_commercial_hydronic",
    "twozone_apartment_hydronic",
]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_history(case_id: str) -> list[dict[str, Any]]:
    path = ROOT / f"artifacts/eu/{case_id}/history.json"
    history = _load_json(path)
    if not isinstance(history, list):
        raise ValueError(f"Unexpected history format: {path}")
    return [entry for entry in history if isinstance(entry, dict)]


def _load_metrics(case_id: str) -> dict[str, Any]:
    path = ROOT / f"artifacts/eu/{case_id}/metrics.json"
    metrics = _load_json(path)
    if not isinstance(metrics, dict):
        raise ValueError(f"Unexpected metrics format: {path}")
    return metrics


def build_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    curve_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for case_id in CASES:
        history = _load_history(case_id)
        metrics = _load_metrics(case_id)
        best_epoch = int(metrics.get("best_epoch", 0))

        for entry in history:
            curve_rows.append(
                {
                    "case_id": case_id,
                    "epoch": int(float(entry.get("epoch", 0))),
                    "train_loss": float(entry.get("train_loss", 0.0)),
                    "val_loss": float(entry.get("val_loss", 0.0)),
                    "train_rmse_degC": float(entry.get("train_rmse_degC", 0.0)),
                    "val_rmse_degC": float(entry.get("val_rmse_degC", 0.0)),
                    "loss_weight_mode": str(entry.get("loss_weight_mode", "")),
                    "lambda_physics_eff": float(entry.get("lambda_physics_eff", 0.0)),
                }
            )

        first = history[0]
        best = next((entry for entry in history if int(float(entry.get("epoch", 0))) == best_epoch), history[-1])

        summary_rows.append(
            {
                "case_id": case_id,
                "best_epoch": best_epoch,
                "first_epoch": int(float(first.get("epoch", 0))),
                "first_train_loss": float(first.get("train_loss", 0.0)),
                "first_val_loss": float(first.get("val_loss", 0.0)),
                "first_train_rmse_degC": float(first.get("train_rmse_degC", 0.0)),
                "first_val_rmse_degC": float(first.get("val_rmse_degC", 0.0)),
                "best_train_loss": float(best.get("train_loss", 0.0)),
                "best_val_loss": float(best.get("val_loss", 0.0)),
                "best_train_rmse_degC": float(best.get("train_rmse_degC", 0.0)),
                "best_val_rmse_degC": float(best.get("val_rmse_degC", 0.0)),
                "val_loss_improvement_pct": 100.0 * (float(first.get("val_loss", 0.0)) - float(best.get("val_loss", 0.0))) / max(float(first.get("val_loss", 0.0)), 1e-12),
                "val_rmse_improvement_pct": 100.0 * (float(first.get("val_rmse_degC", 0.0)) - float(best.get("val_rmse_degC", 0.0))) / max(float(first.get("val_rmse_degC", 0.0)), 1e-12),
                "final_test_rmse_degC": float(metrics.get("test", {}).get("rmse_degC", 0.0)),
                "final_test_loss": float(metrics.get("test", {}).get("loss", 0.0)),
            }
        )

    return curve_rows, summary_rows


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_plot(curve_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    case_order = [row["case_id"] for row in summary_rows]
    palette = plt.get_cmap("tab10")

    fig, axes = plt.subplots(1, 2, figsize=(15, 6), constrained_layout=True)

    for idx, case_id in enumerate(case_order):
        series = [row for row in curve_rows if row["case_id"] == case_id]
        epochs = [row["epoch"] for row in series]
        val_loss = [row["val_loss"] for row in series]
        train_loss = [row["train_loss"] for row in series]
        best_epoch = next(row["best_epoch"] for row in summary_rows if row["case_id"] == case_id)

        color = palette(idx % 10)
        axes[0].plot(epochs, train_loss, color=color, alpha=0.35, linewidth=1.5, label=f"{case_id} train")
        axes[0].plot(epochs, val_loss, color=color, linewidth=2.2, label=f"{case_id} val")
        best_row = next(row for row in series if row["epoch"] == best_epoch)
        axes[0].scatter([best_epoch], [best_row["val_loss"]], color=color, edgecolor="black", zorder=5, s=40)

        val_rmse = [row["val_rmse_degC"] for row in series]
        axes[1].plot(epochs, val_rmse, color=color, linewidth=2.2, label=case_id)
        axes[1].scatter([best_epoch], [best_row["val_rmse_degC"]], color=color, edgecolor="black", zorder=5, s=40)

    axes[0].set_title("Training and Validation Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].set_yscale("log")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(fontsize=8, ncol=2)

    axes[1].set_title("Validation RMSE During Training")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("RMSE [degC]")
    axes[1].set_yscale("log")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(fontsize=8)

    fig.suptitle("EU Stage-1 PINN Training Curves", fontsize=13)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    curve_rows, summary_rows = build_rows()
    curves_csv = ROOT / "artifacts/eu/training_curves_stage1.csv"
    summary_csv = ROOT / "artifacts/eu/training_improvement_summary_stage1.csv"
    plot_path = ROOT / "artifacts/eu/training_curves_stage1.png"

    write_csv(curve_rows, curves_csv)
    write_csv(summary_rows, summary_csv)
    write_plot(curve_rows, summary_rows, plot_path)

    print(json.dumps({"curves_csv": str(curves_csv), "summary_csv": str(summary_csv), "plot": str(plot_path)}, indent=2))


if __name__ == "__main__":
    main()
