#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


@dataclass
class EpisodeRun:
    case: str
    predictor: str
    episode_id: str
    path: Path
    payload: dict[str, Any]


def _to_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def infer_floor_area_m2(payload: dict[str, Any]) -> float | None:
    diag = payload.get("diagnostic_kpis", {})
    chall = payload.get("challenge_kpis", {})
    summary = payload.get("kpi_summary", {})
    boptest = payload.get("boptest_kpis", {})

    peak_heating_w = _to_float(diag.get("peak_heating_power_W"))
    if peak_heating_w is None:
        peak_heating_w = _to_float(diag.get("peak_power_W"))
    if peak_heating_w is None or peak_heating_w <= 0.0:
        return None

    pdih_kw_per_m2 = None
    for container in (chall, summary):
        item = container.get("pdih_tot")
        if isinstance(item, dict):
            pdih_kw_per_m2 = _to_float(item.get("value"))
            if pdih_kw_per_m2 is not None:
                break
    if pdih_kw_per_m2 is None:
        pdih_kw_per_m2 = _to_float(boptest.get("pdih_tot"))

    if pdih_kw_per_m2 is None or pdih_kw_per_m2 <= 0.0:
        return None

    # area = peak_heating_power / (peak_heating_power_density)
    area_m2 = peak_heating_w / (pdih_kw_per_m2 * 1000.0)
    # Several BESTEST-style cases use normalized reference areas (~1 m2),
    # which are not suitable for absolute W/m2 plausibility limits.
    if area_m2 < 10.0:
        return None
    return area_m2


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def load_runs(raw_root: Path) -> list[EpisodeRun]:
    runs: list[EpisodeRun] = []
    for case_dir in sorted(raw_root.glob("*")):
        if not case_dir.is_dir():
            continue
        for predictor in ("rc", "pinn"):
            pred_dir = case_dir / predictor
            if not pred_dir.exists():
                continue
            for ep_file in sorted(pred_dir.glob("te_*.json")):
                payload = json.loads(ep_file.read_text(encoding="utf-8"))
                runs.append(
                    EpisodeRun(
                        case=case_dir.name,
                        predictor=predictor,
                        episode_id=str(payload.get("episode_id", ep_file.stem)),
                        path=ep_file,
                        payload=payload,
                    )
                )
    return runs


def run_plausibility_checks(run: EpisodeRun) -> list[str]:
    issues: list[str] = []
    data = run.payload
    records = data.get("step_records", [])
    declared_steps = int(data.get("n_steps", -1))
    control_interval_s = int(data.get("control_interval_s", 0))
    resolved_signals = data.get("resolved_signals", {}) if isinstance(data.get("resolved_signals", {}), dict) else {}
    mpc_config = data.get("mpc_config", {}) if isinstance(data.get("mpc_config", {}), dict) else {}

    if not isinstance(records, list) or not records:
        return ["missing_or_empty_step_records"]

    for warning in data.get("mapping_warnings", []):
        if isinstance(warning, str):
            issues.append(warning)

    if declared_steps != len(records):
        issues.append(f"n_steps_mismatch:declared={declared_steps},actual={len(records)}")

    times = np.asarray([float(r.get("time_s", np.nan)) for r in records], dtype=float)
    if np.any(~np.isfinite(times)):
        issues.append("non_finite_time_s")
    else:
        dts = np.diff(times)
        if np.any(dts <= 0.0):
            issues.append("non_increasing_time_s")
        if control_interval_s > 0 and np.any(np.abs(dts - control_interval_s) > 1e-6):
            issues.append("time_step_inconsistency")

    def _check_series(name: str, lower: float, upper: float) -> np.ndarray:
        values = np.asarray([float(r.get(name, np.nan)) for r in records], dtype=float)
        if np.any(~np.isfinite(values)):
            issues.append(f"non_finite_{name}")
            return values
        if np.any(values < lower) or np.any(values > upper):
            issues.append(f"out_of_range_{name}:[{lower},{upper}]")
        return values

    t_zone = _check_series("t_zone", -30.0, 60.0)
    u_heat = _check_series("u_heating", 5.0, 40.0)
    power = _check_series("power_w", -1000.0, 1_000_000.0)
    solve = _check_series("solve_time_ms", 0.0, 60000.0)
    floor_area_m2 = infer_floor_area_m2(data)

    if np.all(np.isfinite(t_zone)):
        if np.any(np.abs(np.diff(t_zone)) > 4.0):
            issues.append("large_t_zone_jump_gt_4C_per_step")
    if np.all(np.isfinite(u_heat)):
        if np.any(np.abs(np.diff(u_heat)) > 8.0):
            issues.append("large_control_jump_gt_8C_per_step")
        u_min = _to_float(mpc_config.get("u_min_degC"))
        u_max = _to_float(mpc_config.get("u_max_degC"))
        if u_min is not None and len(u_heat) > 0:
            sat_min = float(np.mean(np.abs(u_heat - u_min) < 1e-6))
            if sat_min > 0.25:
                issues.append("high_control_saturation_at_u_min_gt_25pct")
        if u_max is not None and len(u_heat) > 0:
            sat_max = float(np.mean(np.abs(u_heat - u_max) < 1e-6))
            if sat_max > 0.25:
                issues.append("high_control_saturation_at_u_max_gt_25pct")
    if np.all(np.isfinite(power)):
        if floor_area_m2 is not None and floor_area_m2 > 1e-9:
            power_density = power / floor_area_m2
            if np.any(power_density < -5.0) or np.any(power_density > 500.0):
                issues.append("out_of_range_power_density_w_per_m2:[-5.0,500.0]")
            if np.max(power_density) > 300.0:
                issues.append("very_high_power_density_peak_gt_300W_per_m2")
        elif np.max(power) > 120000.0:
            issues.append("very_high_power_peak_gt_120kW_no_area_norm")
    if np.all(np.isfinite(solve)):
        if np.percentile(solve, 99) > 10000.0:
            issues.append("very_slow_solver_p99_gt_10s")

    for i, rec in enumerate(records):
        lo = rec.get("t_lower")
        hi = rec.get("t_upper")
        if _is_finite(lo) and _is_finite(hi) and float(lo) > float(hi):
            issues.append(f"invalid_comfort_band_at_step_{i}")
            break

    if not resolved_signals.get("outdoor_temp_signal"):
        issues.append("missing_outdoor_temp_signal")
    if not resolved_signals.get("solar_signal"):
        issues.append("missing_solar_signal")

    return sorted(set(issues))


def save_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_kpi_rows(runs: list[EpisodeRun]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        diag = run.payload.get("diagnostic_kpis", {})
        chall = run.payload.get("challenge_kpis", {})
        area_m2 = infer_floor_area_m2(run.payload)
        total_energy_wh = _to_float(diag.get("total_energy_Wh"))
        peak_power_w = _to_float(diag.get("peak_power_W"))
        rows.append(
            {
                "case": run.case,
                "predictor": run.predictor,
                "episode_id": run.episode_id,
                "comfort_Kh": diag.get("comfort_Kh"),
                "comfort_violation_steps": diag.get("comfort_violation_steps"),
                "total_energy_Wh": total_energy_wh,
                "peak_power_W": peak_power_w,
                "floor_area_m2": area_m2,
                "total_energy_Wh_per_m2": (total_energy_wh / area_m2) if area_m2 and total_energy_wh is not None else None,
                "peak_power_W_per_m2": (peak_power_w / area_m2) if area_m2 and peak_power_w is not None else None,
                "mpc_solve_time_mean_ms": diag.get("mpc_solve_time_mean_ms"),
                "mpc_solve_time_p95_ms": diag.get("mpc_solve_time_p95_ms"),
                "zone_signal_count": len((run.payload.get("resolved_signals", {}) or {}).get("zone_temp_signals", [])),
                "control_signal_count": len((run.payload.get("resolved_signals", {}) or {}).get("control_value_signals", [])),
                "outdoor_temp_signal": (run.payload.get("resolved_signals", {}) or {}).get("outdoor_temp_signal"),
                "solar_signal": (run.payload.get("resolved_signals", {}) or {}).get("solar_signal"),
                "tdis_tot": (chall.get("tdis_tot") or {}).get("value") if isinstance(chall.get("tdis_tot"), dict) else None,
                "cost_tot": (chall.get("cost_tot") or {}).get("value") if isinstance(chall.get("cost_tot"), dict) else None,
            }
        )
    return rows


def plot_timeseries_per_case_episode(runs: list[EpisodeRun], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[tuple[str, str], dict[str, EpisodeRun]] = {}
    for run in runs:
        grouped.setdefault((run.case, run.episode_id), {})[run.predictor] = run

    for (case, episode_id), by_pred in sorted(grouped.items()):
        rc = by_pred.get("rc")
        pinn = by_pred.get("pinn")
        if rc is None and pinn is None:
            continue

        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        fig.suptitle(f"{case} | {episode_id} | RC vs PINN", fontsize=12)

        for label, run in (("RC", rc), ("PINN", pinn)):
            if run is None:
                continue
            records = run.payload.get("step_records", [])
            t = np.asarray([float(r["time_s"]) for r in records], dtype=float)
            t_h = (t - t[0]) / 3600.0
            tz = np.asarray([float(r.get("t_zone", np.nan)) for r in records], dtype=float)
            uh = np.asarray([float(r.get("u_heating", np.nan)) for r in records], dtype=float)
            tl = np.asarray([float(r.get("t_lower", np.nan)) for r in records], dtype=float)
            tu = np.asarray([float(r.get("t_upper", np.nan)) for r in records], dtype=float)

            axes[0].plot(t_h, tz, label=f"{label} T_zone", linewidth=1.5)
            axes[1].plot(t_h, uh, label=f"{label} u_heating", linewidth=1.3)
            axes[0].plot(t_h, tl, linestyle="--", linewidth=0.8, alpha=0.7, label=f"{label} lower")
            axes[0].plot(t_h, tu, linestyle="--", linewidth=0.8, alpha=0.7, label=f"{label} upper")

        axes[0].set_ylabel("Temperature [degC]")
        axes[1].set_ylabel("Setpoint [degC]")
        axes[1].set_xlabel("Episode time [h]")
        axes[0].grid(alpha=0.3)
        axes[1].grid(alpha=0.3)
        axes[0].legend(ncol=2, fontsize=8)
        axes[1].legend(ncol=2, fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / f"{case}__{episode_id}.png", dpi=200)
        plt.close(fig)


def plot_overview(runs: list[EpisodeRun], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    kpis = build_kpi_rows(runs)
    predictors = ["rc", "pinn"]
    colors = {"rc": "#1f77b4", "pinn": "#d62728"}

    # Scatter: energy vs comfort.
    fig, ax = plt.subplots(figsize=(8, 6))
    for pred in predictors:
        xs = [float(r["total_energy_Wh"]) for r in kpis if r["predictor"] == pred and r["total_energy_Wh"] is not None]
        ys = [float(r["comfort_Kh"]) for r in kpis if r["predictor"] == pred and r["comfort_Kh"] is not None]
        ax.scatter(xs, ys, label=pred.upper(), alpha=0.8, c=colors[pred], edgecolors="black", linewidth=0.3)
    ax.set_xlabel("Total energy [Wh]")
    ax.set_ylabel("Comfort violation [Kh]")
    ax.set_title("Comfort-Energy Tradeoff Across Episodes")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "comfort_vs_energy.png", dpi=220)
    plt.close(fig)

    # Solver time distribution.
    fig, ax = plt.subplots(figsize=(8, 6))
    data = []
    labels = []
    for pred in predictors:
        vals = [float(r["mpc_solve_time_mean_ms"]) for r in kpis if r["predictor"] == pred and r["mpc_solve_time_mean_ms"] is not None]
        if vals:
            data.append(vals)
            labels.append(pred.upper())
    if data:
        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True)
        for patch, pred in zip(bp["boxes"], predictors[: len(data)]):
            patch.set_facecolor(colors[pred])
            patch.set_alpha(0.35)
    ax.set_ylabel("Mean MPC solve time [ms]")
    ax.set_title("Solver Runtime Distribution")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "solve_time_distribution.png", dpi=220)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="QC and plotting for EU RC vs PINN result episodes.")
    parser.add_argument("--raw-root", default="results/eu_rc_vs_pinn/raw")
    parser.add_argument("--out-dir", default="results/eu_rc_vs_pinn/qc")
    args = parser.parse_args()

    raw_root = Path(args.raw_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = load_runs(raw_root)
    if not runs:
        raise RuntimeError(f"No te_*.json files found in {raw_root}")

    plausibility_rows: list[dict[str, Any]] = []
    report: dict[str, Any] = {"total_runs": len(runs), "runs": []}
    for run in runs:
        issues = run_plausibility_checks(run)
        status = "PASS" if not issues else "WARN"
        plausibility_rows.append(
            {
                "case": run.case,
                "predictor": run.predictor,
                "episode_id": run.episode_id,
                "status": status,
                "issue_count": len(issues),
                "issues": " | ".join(issues),
                "file": str(run.path).replace("\\", "/"),
            }
        )
        report["runs"].append(
            {
                "case": run.case,
                "predictor": run.predictor,
                "episode_id": run.episode_id,
                "status": status,
                "issues": issues,
                "file": str(run.path).replace("\\", "/"),
            }
        )

    save_csv(
        out_dir / "plausibility_summary.csv",
        plausibility_rows,
        ["case", "predictor", "episode_id", "status", "issue_count", "issues", "file"],
    )

    kpi_rows = build_kpi_rows(runs)
    save_csv(
        out_dir / "kpi_table.csv",
        kpi_rows,
        [
            "case",
            "predictor",
            "episode_id",
            "comfort_Kh",
            "comfort_violation_steps",
            "total_energy_Wh",
            "peak_power_W",
            "floor_area_m2",
            "total_energy_Wh_per_m2",
            "peak_power_W_per_m2",
            "mpc_solve_time_mean_ms",
            "mpc_solve_time_p95_ms",
            "zone_signal_count",
            "control_signal_count",
            "outdoor_temp_signal",
            "solar_signal",
            "tdis_tot",
            "cost_tot",
        ],
    )

    report_path = out_dir / "plausibility_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    plot_timeseries_per_case_episode(runs, out_dir / "timeseries")
    plot_overview(runs, out_dir / "overview")

    n_warn = sum(1 for row in plausibility_rows if row["status"] == "WARN")
    print(f"QC completed. Runs: {len(runs)} | WARN: {n_warn}")
    print(f"Summary CSV: {(out_dir / 'plausibility_summary.csv').as_posix()}")
    print(f"KPI CSV: {(out_dir / 'kpi_table.csv').as_posix()}")
    print(f"Report JSON: {report_path.as_posix()}")
    print(f"Figures: {(out_dir / 'timeseries').as_posix()} and {(out_dir / 'overview').as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
