#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import yaml


ROOT = Path(__file__).resolve().parents[1]
CASES = [
    "bestest_hydronic",
    "bestest_hydronic_heat_pump",
    "singlezone_commercial_hydronic",
    "twozone_apartment_hydronic",
]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def _start_days(episodes: list[dict[str, Any]], split: str) -> list[float]:
    out: list[float] = []
    for episode in episodes:
        if str(episode.get("split")) != split:
            continue
        start_time_s = float(episode.get("start_time_s", 0.0))
        out.append(start_time_s / 86400.0)
    return out


def _format_days(values: list[float]) -> str:
    if not values:
        return ""
    return ";".join(f"{value:.0f}" for value in values)


def _count_key(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str) and value:
        return 1
    return 0


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_id in CASES:
        manifest = _load_yaml(ROOT / f"manifests/eu/{case_id}_stage1.yaml")
        cfg = _load_yaml(ROOT / f"configs/eu/pinn_{case_id}.yaml")
        index = json.loads((ROOT / f"datasets/eu/{case_id}/index.json").read_text(encoding="utf-8"))
        metrics = _load_json(ROOT / f"artifacts/eu/{case_id}/metrics.json")

        defaults = manifest.get("defaults", {}) or {}
        case_map = (manifest.get("case_mappings", {}) or {}).get(case_id, {}) or {}
        episodes = manifest.get("episodes", []) or []
        training = cfg.get("training", {}) or {}
        early = training.get("early_stopping", {}) or {}
        loss_weighting = training.get("loss_weighting", {}) or {}
        val = metrics.get("validation", {}) or {}
        test = metrics.get("test", {}) or {}

        split_counts = {"train": 0, "val": 0, "test": 0}
        for entry in index:
            split = str(entry.get("split"))
            if split in split_counts:
                split_counts[split] += 1

        row: dict[str, Any] = {
            "case_id": case_id,
            "dataset_root": (cfg.get("data", {}) or {}).get("dataset_root", ""),
            "control_interval_s": defaults.get("control_interval_s", ""),
            "episode_length_days": defaults.get("episode_length_days", ""),
            "warmup_period_days": float(defaults.get("warmup_period_s", 0)) / 86400.0,
            "n_train_episodes": split_counts["train"],
            "n_val_episodes": split_counts["val"],
            "n_test_episodes": split_counts["test"],
            "train_start_days": _format_days(_start_days(episodes, "train")),
            "val_start_days": _format_days(_start_days(episodes, "val")),
            "test_start_days": _format_days(_start_days(episodes, "test")),
            "zone_signal_count": _count_key(case_map.get("zone_temp_signals") or case_map.get("zone_temp_signal")),
            "control_signal_count": _count_key(case_map.get("control_value_signals") or case_map.get("control_value_signal")),
            "has_predictor_mpc_overrides": bool(case_map.get("predictor_mpc_overrides")),
            "loss_weight_mode": loss_weighting.get("mode", ""),
            "lambda_physics": training.get("lambda_physics", ""),
            "batch_size": training.get("batch_size", ""),
            "max_epochs": training.get("epochs", ""),
            "learning_rate": training.get("learning_rate", ""),
            "weight_decay": training.get("weight_decay", ""),
            "early_stopping_patience": early.get("patience", ""),
            "early_stopping_min_epochs": early.get("min_epochs", ""),
            "best_epoch": metrics.get("best_epoch", ""),
            "best_val_loss": metrics.get("best_val_loss", ""),
            "val_rmse_degC": val.get("rmse_degC", ""),
            "test_rmse_degC": test.get("rmse_degC", ""),
            "val_rollout_rmse_degC": val.get("rollout_rmse_degC", ""),
            "test_rollout_rmse_degC": test.get("rollout_rmse_degC", ""),
        }
        rows.append(row)
    return rows


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_plot(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    case_labels = [str(row["case_id"]) for row in rows]
    x = list(range(len(rows)))

    best_val = [float(row["best_val_loss"]) for row in rows]
    test_rmse = [float(row["test_rmse_degC"]) for row in rows]
    zone_counts = [int(row["zone_signal_count"]) for row in rows]
    control_counts = [int(row["control_signal_count"]) for row in rows]

    train_days = [str(row["train_start_days"]) for row in rows]
    val_days = [str(row["val_start_days"]) for row in rows]
    test_days = [str(row["test_start_days"]) for row in rows]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)

    width = 0.35
    axes[0].bar([v - width / 2 for v in x], best_val, width=width, label="best val loss")
    axes[0].bar([v + width / 2 for v in x], test_rmse, width=width, label="test RMSE [degC]")
    axes[0].set_title("Performance")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(case_labels, rotation=20, ha="right")
    axes[0].legend()

    axes[1].bar([v - width / 2 for v in x], zone_counts, width=width, label="zone signals")
    axes[1].bar([v + width / 2 for v in x], control_counts, width=width, label="control signals")
    axes[1].set_title("Signal Complexity")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(case_labels, rotation=20, ha="right")
    axes[1].legend()

    axes[2].axis("off")
    lines = ["Episode start days (simulation-relative):", ""]
    for idx, case in enumerate(case_labels):
        lines.append(f"{case}")
        lines.append(f"  train: {train_days[idx]}")
        lines.append(f"  val  : {val_days[idx]}")
        lines.append(f"  test : {test_days[idx]}")
        lines.append("")
    axes[2].text(0.0, 1.0, "\n".join(lines), va="top", fontsize=9)
    axes[2].set_title("Split Windows")

    fig.suptitle("EU Stage-1 PINN Case Overview (4 Cases)", fontsize=13)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    rows = build_rows()
    csv_path = ROOT / "artifacts/eu/case_overview_stage1.csv"
    plot_path = ROOT / "artifacts/eu/case_overview_stage1.png"
    write_csv(rows, csv_path)
    write_plot(rows, plot_path)
    print(json.dumps({"csv": str(csv_path), "plot": str(plot_path)}, indent=2))


if __name__ == "__main__":
    main()
