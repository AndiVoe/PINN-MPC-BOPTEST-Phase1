#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
CASES = [
    "bestest_hydronic",
    "bestest_hydronic_heat_pump",
    "singlezone_commercial_hydronic",
    "twozone_apartment_hydronic",
]
SPLITS = ["train", "val", "test"]
VARS = [
    ("T_zone_degC", "Zone Temperature [degC]"),
    ("T_outdoor_degC", "Outdoor Temperature [degC]"),
    ("H_global_Wm2", "Irradiation [W/m2]"),
]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _collect_case_split_values(case_id: str) -> dict[str, dict[str, list[float]]]:
    index = _load_json(ROOT / f"datasets/eu/{case_id}/index.json")
    out: dict[str, dict[str, list[float]]] = {
        split: {var: [] for var, _ in VARS} for split in SPLITS
    }
    for entry in index:
        if not isinstance(entry, dict):
            continue
        split = str(entry.get("split", ""))
        rel_path = str(entry.get("path", ""))
        if split not in out or not rel_path:
            continue
        ep = _load_json(ROOT / rel_path)
        records = ep.get("records", []) or []
        for record in records:
            for var, _ in VARS:
                value = float(record.get(var, 0.0))
                out[split][var].append(value)
    return out


def _collect_hourly_profiles(case_id: str) -> dict[str, dict[str, list[float]]]:
    index = _load_json(ROOT / f"datasets/eu/{case_id}/index.json")
    bucket: dict[str, dict[str, dict[int, list[float]]]] = {
        split: {var: defaultdict(list) for var, _ in VARS} for split in SPLITS
    }
    for entry in index:
        if not isinstance(entry, dict):
            continue
        split = str(entry.get("split", ""))
        rel_path = str(entry.get("path", ""))
        if split not in bucket or not rel_path:
            continue
        ep = _load_json(ROOT / rel_path)
        records = ep.get("records", []) or []
        if not records:
            continue
        start = int(records[0].get("time_s", 0))
        for record in records:
            t = int(record.get("time_s", start))
            hour = int(((t - start) // 3600) % 24)
            for var, _ in VARS:
                bucket[split][var][hour].append(float(record.get(var, 0.0)))

    profiles: dict[str, dict[str, list[float]]] = {
        split: {var: [] for var, _ in VARS} for split in SPLITS
    }
    for split in SPLITS:
        for var, _ in VARS:
            for hour in range(24):
                vals = bucket[split][var].get(hour, [])
                profiles[split][var].append(median(vals) if vals else float("nan"))
    return profiles


def make_distribution_plot(output_path: Path) -> None:
    fig, axes = plt.subplots(3, 4, figsize=(18, 11), constrained_layout=True)
    split_colors = {"train": "#1f77b4", "val": "#ff7f0e", "test": "#2ca02c"}
    for col, case_id in enumerate(CASES):
        values = _collect_case_split_values(case_id)
        for row, (var, label) in enumerate(VARS):
            ax = axes[row, col]
            data = [values[split][var] for split in SPLITS]
            bp = ax.boxplot(data, tick_labels=SPLITS, patch_artist=True, showfliers=False)
            for patch, split in zip(bp["boxes"], SPLITS):
                patch.set_facecolor(split_colors[split])
                patch.set_alpha(0.35)
            ax.set_title(case_id if row == 0 else "")
            if col == 0:
                ax.set_ylabel(label)
            ax.grid(True, alpha=0.25)
    fig.suptitle("EU Stage-1 Dataset Distributions by Split", fontsize=14)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def make_hourly_profile_plot(output_path: Path) -> None:
    fig, axes = plt.subplots(3, 4, figsize=(18, 11), constrained_layout=True)
    colors = {"train": "#1f77b4", "val": "#ff7f0e", "test": "#2ca02c"}
    for col, case_id in enumerate(CASES):
        profiles = _collect_hourly_profiles(case_id)
        for row, (var, label) in enumerate(VARS):
            ax = axes[row, col]
            for split in SPLITS:
                ax.plot(range(24), profiles[split][var], label=split, color=colors[split], linewidth=2)
            ax.set_title(case_id if row == 0 else "")
            ax.set_xlabel("Hour of day")
            if col == 0:
                ax.set_ylabel(label + " (median)")
            ax.grid(True, alpha=0.25)
            if row == 0 and col == 0:
                ax.legend()
    fig.suptitle("EU Stage-1 Split Comparison: Hourly Median Profiles", fontsize=14)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    dist_path = ROOT / "artifacts/eu/dataset_split_distributions_stage1.png"
    prof_path = ROOT / "artifacts/eu/dataset_split_hourly_profiles_stage1.png"
    make_distribution_plot(dist_path)
    make_hourly_profile_plot(prof_path)
    print(json.dumps({"distributions": str(dist_path), "profiles": str(prof_path)}, indent=2))


if __name__ == "__main__":
    main()
