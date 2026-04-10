#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES = [
    "bestest_hydronic",
    "bestest_hydronic_heat_pump",
    "singlezone_commercial_hydronic",
    "twozone_apartment_hydronic",
]


@dataclass
class AuditThresholds:
    expected_dt_s: int = 900
    zone_min_degC: float = -30.0
    zone_max_degC: float = 60.0
    outdoor_min_degC: float = -50.0
    outdoor_max_degC: float = 60.0
    solar_min_wm2: float = 0.0
    solar_max_wm2: float = 1500.0
    max_outside_train_frac: float = 0.25
    rollout_ratio_warn: float = 10.0


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _split_series(records: list[dict[str, Any]]) -> tuple[list[float], list[float], list[float], list[int]]:
    zone = [float(r.get("T_zone_degC", float("nan"))) for r in records]
    outdoor = [float(r.get("T_outdoor_degC", float("nan"))) for r in records]
    solar = [float(r.get("H_global_Wm2", float("nan"))) for r in records]
    times = [int(r.get("time_s", -1)) for r in records]
    return zone, outdoor, solar, times


def _fraction_outside(values: list[float], lower: float, upper: float) -> float:
    if not values:
        return 0.0
    n_bad = sum(1 for v in values if (v < lower or v > upper))
    return n_bad / len(values)


def _outside_train_frac(values: list[float], train_values: list[float]) -> float:
    if not values or not train_values:
        return 0.0
    lower, upper = min(train_values), max(train_values)
    n_out = sum(1 for v in values if (v < lower or v > upper))
    return n_out / len(values)


def _bool_to_status(value: bool) -> str:
    return "PASS" if value else "FAIL"


def audit_case(case_id: str, t: AuditThresholds) -> dict[str, Any]:
    index_path = ROOT / f"datasets/eu/{case_id}/index.json"
    metrics_path = ROOT / f"artifacts/eu/{case_id}/metrics.json"
    index = _load_json(index_path)
    metrics = _load_json(metrics_path)

    split_to_entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ids_seen: dict[str, set[str]] = defaultdict(set)
    duplicate_id_across_splits = False

    for entry in index:
        if not isinstance(entry, dict):
            continue
        split = str(entry.get("split", ""))
        dataset_id = str(entry.get("dataset_id", ""))
        split_to_entries[split].append(entry)
        for existing_split, ids in ids_seen.items():
            if existing_split != split and dataset_id in ids:
                duplicate_id_across_splits = True
        ids_seen[split].add(dataset_id)

    records_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    episode_has_bad_dt = False
    episode_has_non_monotonic = False
    episode_has_missing = False
    episode_has_invalid_range = False
    all_dts: list[int] = []

    for split, entries in split_to_entries.items():
        for entry in entries:
            rel = str(entry.get("path", ""))
            if not rel:
                continue
            episode = _load_json(ROOT / rel)
            records = episode.get("records", []) or []
            zone, outdoor, solar, times = _split_series(records)

            # Missing / non-finite checks
            if not all(_is_finite(v) for v in zone + outdoor + solar):
                episode_has_missing = True

            # Range checks
            if any(v < t.zone_min_degC or v > t.zone_max_degC for v in zone):
                episode_has_invalid_range = True
            if any(v < t.outdoor_min_degC or v > t.outdoor_max_degC for v in outdoor):
                episode_has_invalid_range = True
            if any(v < t.solar_min_wm2 or v > t.solar_max_wm2 for v in solar):
                episode_has_invalid_range = True

            # Time checks
            for idx in range(1, len(times)):
                dt = times[idx] - times[idx - 1]
                all_dts.append(dt)
                if dt != t.expected_dt_s:
                    episode_has_bad_dt = True
                if dt <= 0:
                    episode_has_non_monotonic = True

            if split in records_by_split:
                records_by_split[split].extend(records)

    train_zone, train_outdoor, train_solar, _ = _split_series(records_by_split["train"])
    val_zone, val_outdoor, val_solar, _ = _split_series(records_by_split["val"])
    test_zone, test_outdoor, test_solar, _ = _split_series(records_by_split["test"])

    val_outside_train_outdoor = _outside_train_frac(val_outdoor, train_outdoor)
    test_outside_train_outdoor = _outside_train_frac(test_outdoor, train_outdoor)
    val_outside_train_solar = _outside_train_frac(val_solar, train_solar)
    test_outside_train_solar = _outside_train_frac(test_solar, train_solar)

    distribution_ok = (
        val_outside_train_outdoor <= t.max_outside_train_frac
        and test_outside_train_outdoor <= t.max_outside_train_frac
        and val_outside_train_solar <= t.max_outside_train_frac
        and test_outside_train_solar <= t.max_outside_train_frac
    )

    val_metrics = (metrics.get("validation", {}) or {})
    test_metrics = (metrics.get("test", {}) or {})
    val_rmse = float(val_metrics.get("rmse_degC", 0.0))
    val_mae = float(val_metrics.get("mae_degC", 0.0))
    val_rollout_rmse = float(val_metrics.get("rollout_rmse_degC", 0.0))
    val_rollout_mae = float(val_metrics.get("rollout_mae_degC", 0.0))
    test_rmse = float(test_metrics.get("rmse_degC", 0.0))
    test_mae = float(test_metrics.get("mae_degC", 0.0))
    test_rollout_rmse = float(test_metrics.get("rollout_rmse_degC", 0.0))
    test_rollout_mae = float(test_metrics.get("rollout_mae_degC", 0.0))
    rollout_ratio = test_rollout_rmse / max(test_rmse, 1.0e-12)
    rollout_mae_ratio = test_rollout_mae / max(test_mae, 1.0e-12)
    rollout_stability_ok = rollout_ratio <= t.rollout_ratio_warn
    rollout_stability_mae_ok = rollout_mae_ratio <= t.rollout_ratio_warn

    dt_mode = 0
    if all_dts:
        dt_mode = max(set(all_dts), key=all_dts.count)

    return {
        "case_id": case_id,
        "n_train_episodes": len(split_to_entries.get("train", [])),
        "n_val_episodes": len(split_to_entries.get("val", [])),
        "n_test_episodes": len(split_to_entries.get("test", [])),
        "split_leakage": _bool_to_status(not duplicate_id_across_splits),
        "time_monotonic": _bool_to_status(not episode_has_non_monotonic),
        "dt_consistent_900s": _bool_to_status(not episode_has_bad_dt),
        "dt_mode_s": dt_mode,
        "finite_values": _bool_to_status(not episode_has_missing),
        "value_ranges": _bool_to_status(not episode_has_invalid_range),
        "distribution_shift_ok": _bool_to_status(distribution_ok),
        "val_outside_train_outdoor_frac": round(val_outside_train_outdoor, 6),
        "test_outside_train_outdoor_frac": round(test_outside_train_outdoor, 6),
        "val_outside_train_solar_frac": round(val_outside_train_solar, 6),
        "test_outside_train_solar_frac": round(test_outside_train_solar, 6),
        "val_rmse_degC": round(val_rmse, 6),
        "val_mae_degC": round(val_mae, 6),
        "val_rollout_rmse_degC": round(val_rollout_rmse, 6),
        "val_rollout_mae_degC": round(val_rollout_mae, 6),
        "test_rmse_degC": round(test_rmse, 6),
        "test_mae_degC": round(test_mae, 6),
        "test_rollout_rmse_degC": round(test_rollout_rmse, 6),
        "test_rollout_mae_degC": round(test_rollout_mae, 6),
        "rollout_ratio": round(rollout_ratio, 4),
        "rollout_mae_ratio": round(rollout_mae_ratio, 4),
        "rollout_stability": _bool_to_status(rollout_stability_ok),
        "rollout_stability_mae": _bool_to_status(rollout_stability_mae_ok),
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status_cols = [
        "split_leakage",
        "time_monotonic",
        "dt_consistent_900s",
        "finite_values",
        "value_ranges",
        "distribution_shift_ok",
        "rollout_stability",
        "rollout_stability_mae",
    ]

    def emoji(v: str) -> str:
        return "OK" if v == "PASS" else "FLAG"

    lines = [
        "# EU Stage-1 Dataset Validity Audit",
        "",
        "Legend: `OK` = pass, `FLAG` = requires review.",
        "",
        "| case | split_leakage | time_monotonic | dt_900s | finite_values | value_ranges | distribution_shift | rollout_stability_rmse | rollout_stability_mae | rollout_rmse_ratio | rollout_mae_ratio | test_rmse | test_mae |",
        "|---|---|---|---|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| "
            + f"{row['case_id']} | "
            + f"{emoji(str(row['split_leakage']))} | "
            + f"{emoji(str(row['time_monotonic']))} | "
            + f"{emoji(str(row['dt_consistent_900s']))} | "
            + f"{emoji(str(row['finite_values']))} | "
            + f"{emoji(str(row['value_ranges']))} | "
            + f"{emoji(str(row['distribution_shift_ok']))} | "
            + f"{emoji(str(row['rollout_stability']))} | "
            + f"{emoji(str(row['rollout_stability_mae']))} | "
            + f"{row['rollout_ratio']} | "
            + f"{row['rollout_mae_ratio']} | "
            + f"{row['test_rmse_degC']} | "
            + f"{row['test_mae_degC']} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    t = AuditThresholds()
    rows = [audit_case(case_id, t) for case_id in CASES]

    csv_path = ROOT / "artifacts/eu/dataset_validity_audit_stage1.csv"
    md_path = ROOT / "artifacts/eu/dataset_validity_audit_stage1.md"
    write_csv(rows, csv_path)
    write_markdown(rows, md_path)

    print(json.dumps({"csv": str(csv_path), "markdown": str(md_path)}, indent=2))


if __name__ == "__main__":
    main()
