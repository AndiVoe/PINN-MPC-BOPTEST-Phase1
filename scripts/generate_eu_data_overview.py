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
SPLITS = ["train", "val", "test"]
REPR_EPS = {"train": "tr_std_01", "val": "val_std_01", "test": "te_std_01"}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _episode_path(case_id: str, episode_id: str) -> Path:
    return ROOT / f"datasets/eu/{case_id}/json/{episode_id}.json"


def _hours_from_seconds(seconds: int | float) -> float:
    return float(seconds) / 3600.0


def _summary_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "min": 0.0, "max": 0.0, "first": 0.0, "last": 0.0}
    return {
        "mean": float(sum(values) / len(values)),
        "min": float(min(values)),
        "max": float(max(values)),
        "first": float(values[0]),
        "last": float(values[-1]),
    }


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_id in CASES:
        index = _load_json(ROOT / f"datasets/eu/{case_id}/index.json")
        index_map = {str(entry["dataset_id"]): entry for entry in index if isinstance(entry, dict)}

        for episode_id, meta in index_map.items():
            episode = _load_json(_episode_path(case_id, episode_id))
            records = episode.get("records", []) or []
            if not records:
                continue

            times = [int(record["time_s"]) for record in records]
            zone = [float(record.get("T_zone_degC", 0.0)) for record in records]
            outdoor = [float(record.get("T_outdoor_degC", 0.0)) for record in records]
            solar = [float(record.get("H_global_Wm2", 0.0)) for record in records]

            zone_stats = _summary_stats(zone)
            outdoor_stats = _summary_stats(outdoor)
            solar_stats = _summary_stats(solar)

            row = {
                "case_id": case_id,
                "episode_id": episode_id,
                "split": str(meta.get("split", "")),
                "weather_class": str(meta.get("weather_class", "")),
                "n_records": int(meta.get("n_records", len(records))),
                "control_interval_s": int(episode.get("control_interval_s", 0)),
                "start_day": _hours_from_seconds(times[0]) / 24.0,
                "end_day": _hours_from_seconds(times[-1]) / 24.0,
                "duration_days": (_hours_from_seconds(times[-1] - times[0]) / 24.0) + (_hours_from_seconds(int(episode.get("control_interval_s", 0))) / 24.0),
                "zone_mean_degC": zone_stats["mean"],
                "zone_min_degC": zone_stats["min"],
                "zone_max_degC": zone_stats["max"],
                "outdoor_mean_degC": outdoor_stats["mean"],
                "outdoor_min_degC": outdoor_stats["min"],
                "outdoor_max_degC": outdoor_stats["max"],
                "solar_mean_Wm2": solar_stats["mean"],
                "solar_min_Wm2": solar_stats["min"],
                "solar_max_Wm2": solar_stats["max"],
                "zone_first_degC": zone_stats["first"],
                "zone_last_degC": zone_stats["last"],
                "outdoor_first_degC": outdoor_stats["first"],
                "outdoor_last_degC": outdoor_stats["last"],
                "solar_first_Wm2": solar_stats["first"],
                "solar_last_Wm2": solar_stats["last"],
                "path": str(_episode_path(case_id, episode_id).relative_to(ROOT)).replace("\\", "/"),
            }
            rows.append(row)
    return rows


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_plot(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(len(CASES), len(SPLITS), figsize=(18, 14), sharex=True, constrained_layout=True)

    for row_idx, case_id in enumerate(CASES):
        for col_idx, split in enumerate(SPLITS):
            ax = axes[row_idx, col_idx]
            episode_id = REPR_EPS[split]
            episode_path = _episode_path(case_id, episode_id)
            episode = _load_json(episode_path)
            records = episode.get("records", []) or []
            times = [float(record["time_s"]) for record in records]
            hours = [(_time - times[0]) / 3600.0 for _time in times]
            zone = [float(record.get("T_zone_degC", 0.0)) for record in records]
            outdoor = [float(record.get("T_outdoor_degC", 0.0)) for record in records]
            solar = [float(record.get("H_global_Wm2", 0.0)) for record in records]

            color_zone = "tab:red"
            color_outdoor = "tab:blue"
            color_solar = "tab:orange"

            ax.plot(hours, zone, color=color_zone, linewidth=1.8, label="T_zone")
            ax.plot(hours, outdoor, color=color_outdoor, linewidth=1.4, linestyle="--", label="T_outdoor")
            ax.set_ylabel(f"{case_id}\nTemp [degC]", fontsize=9)
            ax.grid(True, alpha=0.25)
            ax.set_title(f"{split} :: {episode_id}", fontsize=10)

            ax2 = ax.twinx()
            ax2.fill_between(hours, solar, color=color_solar, alpha=0.18, label="H_global")
            ax2.plot(hours, solar, color=color_solar, linewidth=1.0)
            ax2.set_ylabel("Irradiation [W/m2]", fontsize=9)
            ax2.set_ylim(bottom=0)

            if row_idx == len(CASES) - 1:
                ax.set_xlabel("Hours since episode start")

            if row_idx == 0 and col_idx == 0:
                ax.legend(loc="upper left", fontsize=8)
                ax2.legend(loc="upper right", fontsize=8)

    fig.suptitle("EU Stage-1 Training Data Overview: Temperatures and Irradiation", fontsize=14)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    rows = build_rows()
    csv_path = ROOT / "artifacts/eu/data_overview_stage1.csv"
    plot_path = ROOT / "artifacts/eu/data_overview_stage1.png"
    write_csv(rows, csv_path)
    write_plot(rows, plot_path)
    print(json.dumps({"csv": str(csv_path), "plot": str(plot_path)}, indent=2))


if __name__ == "__main__":
    main()
