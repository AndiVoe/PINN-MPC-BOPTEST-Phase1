#!/usr/bin/env python3
"""
Generate comparison plots: RC vs PINN vs RBC.

Creates figures showing energy, comfort, and peak power across all three control strategies.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


CANONICAL_OUT_DIR = Path("results/mpc_phase1/plots_3way_refresh")


def _to_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def load_results(raw_root: Path, predictors: list[str]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Load all episode results: (case, predictor, episode) -> payload."""
    results = {}
    for case_dir in sorted(raw_root.glob("*")):
        if not case_dir.is_dir():
            continue
        for predictor in predictors:
            pred_dir = case_dir / predictor
            if not pred_dir.exists():
                continue
            for ep_file in sorted(pred_dir.glob("te_*.json")):
                if ep_file.name.endswith(".live.json"):
                    continue
                try:
                    payload = json.loads(ep_file.read_text(encoding="utf-8"))
                    episode_id = str(payload.get("episode_id", ep_file.stem))
                    results[(case_dir.name, predictor, episode_id)] = payload
                except Exception:
                    pass
    return results


def extract_kpi_dict(payload: dict[str, Any], case_name: str = "") -> dict[str, float | None]:
    """Extract KPIs from episode payload."""
    diag = payload.get("diagnostic_kpis", {})
    
    area_m2_map = {
        "bestest_hydronic": 48.0,
        "bestest_hydronic_heat_pump": 48.0,
        "singlezone_commercial_hydronic": 8500.0,
        "twozone_apartment_hydronic": 44.5,
    }
    
    area_m2 = 1000.0
    for key, area in area_m2_map.items():
        if key in case_name:
            area_m2 = area
            break
    
    energy_wh = _to_float(diag.get("total_energy_Wh"))
    peak_w = _to_float(diag.get("peak_power_W"))
    comfort_kh = _to_float(diag.get("comfort_Kh"))
    solve_time_ms = _to_float(diag.get("mpc_solve_time_mean_ms"))
    
    return {
        "energy_Wh": energy_wh,
        "energy_kWh_m2": (energy_wh / 1000.0 / area_m2) if energy_wh else None,
        "peak_W": peak_w,
        "peak_W_m2": (peak_w / area_m2) if peak_w else None,
        "comfort_Kh": comfort_kh,
        "solve_time_ms": solve_time_ms,
        "area_m2": area_m2,
    }


def plot_three_way_bars(results: dict, out_dir: Path) -> None:
    """Create side-by-side bar charts comparing RC, PINN, and RBC."""
    out_dir.mkdir(parents=True, exist_ok=True)
    
    predictors = ["rc", "pinn", "rbc"]
    cases_data = defaultdict(lambda: {p: [] for p in predictors})
    
    for (case, pred, episode), payload in results.items():
        if pred not in predictors:
            continue
        kpis = extract_kpi_dict(payload, case_name=case)
        if kpis.get("energy_kWh_m2") is not None:
            cases_data[case][pred].append(kpis)
    
    cases = sorted(cases_data.keys())
    colors = {"rc": "#1f77b4", "pinn": "#d62728", "rbc": "#2ca02c"}
    
    # === Energy plot ===
    fig, axes = plt.subplots(1, len(cases), figsize=(14, 5))
    if len(cases) == 1:
        axes = [axes]
    
    for idx, case in enumerate(cases):
        ax = axes[idx]
        
        means = []
        for pred in predictors:
            vals = [k["energy_kWh_m2"] for k in cases_data[case][pred] if k["energy_kWh_m2"] is not None]
            means.append(np.mean(vals) if vals else 0)
        
        bars = ax.bar(range(len(predictors)), means, color=[colors[p] for p in predictors], 
                      edgecolor="black", linewidth=1.2, alpha=0.7)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}',
                   ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_ylabel("Energy [kWh/m²]" if idx == 0 else "")
        ax.set_title(case.replace("_", " "), fontweight='bold')
        ax.set_xticks(range(len(predictors)))
        ax.set_xticklabels([p.upper() for p in predictors])
        ax.grid(axis="y", alpha=0.3)
    
    fig.suptitle("Energy Consumption by Case and Controller", fontsize=12, fontweight='bold', y=1.00)
    fig.tight_layout()
    fig.savefig(out_dir / "01_energy_comparison.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    # === Comfort plot ===
    fig, axes = plt.subplots(1, len(cases), figsize=(14, 5))
    if len(cases) == 1:
        axes = [axes]
    
    for idx, case in enumerate(cases):
        ax = axes[idx]
        
        means = []
        for pred in predictors:
            vals = [k["comfort_Kh"] for k in cases_data[case][pred] if k["comfort_Kh"] is not None]
            means.append(np.mean(vals) if vals else 0)
        
        bars = ax.bar(range(len(predictors)), means, color=[colors[p] for p in predictors], 
                      edgecolor="black", linewidth=1.2, alpha=0.7)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.2f}',
                   ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_ylabel("Comfort Violation [K·h]" if idx == 0 else "")
        ax.set_title(case.replace("_", " "), fontweight='bold')
        ax.set_xticks(range(len(predictors)))
        ax.set_xticklabels([p.upper() for p in predictors])
        ax.grid(axis="y", alpha=0.3)
    
    fig.suptitle("Thermal Comfort Violations by Case and Controller", fontsize=12, fontweight='bold', y=1.00)
    fig.tight_layout()
    fig.savefig(out_dir / "02_comfort_comparison.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    # === Peak power plot ===
    fig, axes = plt.subplots(1, len(cases), figsize=(14, 5))
    if len(cases) == 1:
        axes = [axes]
    
    for idx, case in enumerate(cases):
        ax = axes[idx]
        
        means = []
        for pred in predictors:
            vals = [k["peak_W_m2"] for k in cases_data[case][pred] if k["peak_W_m2"] is not None]
            means.append(np.mean(vals) if vals else 0)
        
        bars = ax.bar(range(len(predictors)), means, color=[colors[p] for p in predictors], 
                      edgecolor="black", linewidth=1.2, alpha=0.7)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}',
                   ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_ylabel("Peak Power [W/m²]" if idx == 0 else "")
        ax.set_title(case.replace("_", " "), fontweight='bold')
        ax.set_xticks(range(len(predictors)))
        ax.set_xticklabels([p.upper() for p in predictors])
        ax.grid(axis="y", alpha=0.3)
    
    fig.suptitle("Peak Power by Case and Controller", fontsize=12, fontweight='bold', y=1.00)
    fig.tight_layout()
    fig.savefig(out_dir / "03_peak_power_comparison.png", dpi=300, bbox_inches='tight')
    plt.close(fig)


def plot_aggregated_boxplots(results: dict, out_dir: Path) -> None:
    """Create aggregated KPI comparison box plots across all cases."""
    out_dir.mkdir(parents=True, exist_ok=True)
    
    predictors = ["rc", "pinn", "rbc"]
    
    energy_data = {p: [] for p in predictors}
    comfort_data = {p: [] for p in predictors}
    peak_data = {p: [] for p in predictors}
    
    for (case, pred, episode), payload in results.items():
        if pred not in predictors:
            continue
        kpis = extract_kpi_dict(payload, case_name=case)
        
        if kpis.get("energy_kWh_m2") is not None and kpis["energy_kWh_m2"] > 0:
            energy_data[pred].append(kpis["energy_kWh_m2"])
        if kpis.get("comfort_Kh") is not None and kpis["comfort_Kh"] >= 0:
            comfort_data[pred].append(kpis["comfort_Kh"])
        if kpis.get("peak_W_m2") is not None and kpis["peak_W_m2"] > 0:
            peak_data[pred].append(kpis["peak_W_m2"])
    
    colors = ["#1f77b4", "#d62728", "#2ca02c"]
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    
    # Energy boxplot
    ax = axes[0, 0]
    bp = ax.boxplot([energy_data[p] for p in predictors], tick_labels=[p.upper() for p in predictors], patch_artist=True)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel("Energy [kWh/m²]", fontweight='bold')
    ax.set_title("Total Energy Consumption", fontweight='bold')
    ax.grid(axis="y", alpha=0.3)
    
    # Comfort boxplot
    ax = axes[0, 1]
    bp = ax.boxplot([comfort_data[p] for p in predictors], tick_labels=[p.upper() for p in predictors], patch_artist=True)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel("Comfort Violation [K·h]", fontweight='bold')
    ax.set_title("Thermal Comfort", fontweight='bold')
    ax.grid(axis="y", alpha=0.3)
    
    # Peak power boxplot
    ax = axes[1, 0]
    bp = ax.boxplot([peak_data[p] for p in predictors], tick_labels=[p.upper() for p in predictors], patch_artist=True)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel("Peak Power [W/m²]", fontweight='bold')
    ax.set_title("Peak Power Demand", fontweight='bold')
    ax.grid(axis="y", alpha=0.3)
    
    # Data count info
    ax = axes[1, 1]
    ax.axis('off')
    info_text = "Dataset Summary:\n\n"
    for pred in predictors:
        n_energy = len(energy_data[pred])
        n_comfort = len(comfort_data[pred])
        n_peak = len(peak_data[pred])
        info_text += f"{pred.upper()}:\n  Energy: {n_energy} samples\n  Comfort: {n_comfort} samples\n  Peak: {n_peak} samples\n\n"
    ax.text(0.1, 0.5, info_text, fontsize=10, verticalalignment='center', family='monospace')
    
    fig.suptitle("Aggregated KPI Comparison (All Episodes, Filtered Valid Values)", fontsize=13, fontweight='bold', y=0.995)
    fig.tight_layout()
    fig.savefig(out_dir / "04_boxplot_aggregated.png", dpi=300, bbox_inches='tight')
    plt.close(fig)


def plot_timeseries_per_case_episode(results: dict, out_dir: Path) -> None:
    """Create T_zone and setpoint trajectories per case+episode for RC, PINN, and RBC."""
    ts_dir = out_dir / "timeseries_case_episode"
    ts_dir.mkdir(parents=True, exist_ok=True)

    predictors = ["rc", "pinn", "rbc"]
    labels = {"rc": "RC", "pinn": "PINN", "rbc": "RBC"}
    colors = {"rc": "#1f77b4", "pinn": "#d62728", "rbc": "#2ca02c"}
    linestyles = {"rc": "-", "pinn": "--", "rbc": "-."}

    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for (case, pred, episode), payload in results.items():
        if pred in predictors:
            grouped[(case, episode)][pred] = payload

    for (case, episode_id), by_pred in sorted(grouped.items()):
        if not by_pred:
            continue

        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        fig.suptitle(f"{case} | {episode_id} | RC vs PINN vs RBC", fontsize=12)

        band_drawn = False
        for pred in predictors:
            payload = by_pred.get(pred)
            if payload is None:
                continue

            records = payload.get("step_records", [])
            if not records:
                continue

            t = np.asarray([float(r.get("time_s", idx)) for idx, r in enumerate(records)], dtype=float)
            t_h = (t - t[0]) / 3600.0
            tz = np.asarray([float(r.get("t_zone", np.nan)) for r in records], dtype=float)
            uh = np.asarray([float(r.get("u_heating", np.nan)) for r in records], dtype=float)

            axes[0].plot(
                t_h,
                tz,
                label=f"{labels[pred]} T_zone",
                linewidth=1.8,
                color=colors[pred],
                linestyle=linestyles[pred],
                alpha=0.95,
            )
            axes[1].plot(
                t_h,
                uh,
                label=f"{labels[pred]} u_heating",
                linewidth=1.8,
                color=colors[pred],
                linestyle=linestyles[pred],
                alpha=0.95,
            )

            if not band_drawn:
                tl = np.asarray([float(r.get("t_lower", np.nan)) for r in records], dtype=float)
                tu = np.asarray([float(r.get("t_upper", np.nan)) for r in records], dtype=float)
                axes[0].plot(
                    t_h,
                    tl,
                    linestyle=":",
                    linewidth=1.0,
                    alpha=0.9,
                    color="#4d4d4d",
                    label="Comfort lower",
                )
                axes[0].plot(
                    t_h,
                    tu,
                    linestyle=":",
                    linewidth=1.0,
                    alpha=0.9,
                    color="#1f1f1f",
                    label="Comfort upper",
                )
                band_drawn = True

        axes[0].set_ylabel("Temperature [degC]")
        axes[1].set_ylabel("Setpoint [degC]")
        axes[1].set_xlabel("Episode time [h]")
        axes[0].grid(axis="y", alpha=0.3)
        axes[1].grid(axis="y", alpha=0.3)
        axes[0].legend(ncol=3, fontsize=8, framealpha=0.9)
        axes[1].legend(ncol=3, fontsize=8, framealpha=0.9)
        fig.tight_layout()
        fig.savefig(ts_dir / f"{case}__{episode_id}.png", dpi=220, bbox_inches="tight")
        plt.close(fig)


def plot_refreshed_episode_bars(results_root: Path, out_dir: Path) -> None:
    """Create episode-level refreshed 3-way bars with consistent style/colors."""
    predictors = ["rc", "pinn", "rbc"]
    labels = {"rc": "RC", "pinn": "PINN", "rbc": "RBC"}
    colors = {"rc": "#1f77b4", "pinn": "#d62728", "rbc": "#2ca02c"}

    files_by_pred: dict[str, dict[str, Path]] = {}
    for pred in predictors:
        pred_dir = results_root / pred
        if not pred_dir.exists():
            return
        files_by_pred[pred] = {
            f.stem: f
            for f in pred_dir.glob("te_*.json")
            if not f.name.endswith(".live.json")
        }

    common_eps = sorted(set(files_by_pred["rc"]).intersection(files_by_pred["pinn"]).intersection(files_by_pred["rbc"]))
    if not common_eps:
        return

    metrics = [
        ("total_energy_Wh", "energy_3way_refreshed.png", "Energy by Episode", "Energy [MWh]", 1e6, "{:.1f}"),
        ("comfort_Kh", "comfort_3way_refreshed.png", "Comfort by Episode", "Comfort [Kh]", 1.0, "{:.2f}"),
        ("peak_power_W", "peak_3way_refreshed.png", "Peak Power by Episode", "Peak Power [kW]", 1e3, "{:.1f}"),
    ]

    x = np.arange(len(common_eps), dtype=float)
    width = 0.25

    for metric_key, file_name, title, ylabel, scale, _fmt in metrics:
        fig, ax = plt.subplots(figsize=(10, 5))
        for idx, pred in enumerate(predictors):
            vals = []
            for ep in common_eps:
                payload = json.loads(files_by_pred[pred][ep].read_text(encoding="utf-8"))
                diag = payload.get("diagnostic_kpis", {})
                v = _to_float(diag.get(metric_key))
                vals.append((v or 0.0) / scale)
            bars = ax.bar(
                x + (idx - 1) * width,
                vals,
                width=width,
                color=colors[pred],
                label=labels[pred],
                edgecolor="black",
                linewidth=1.2,
                alpha=0.7,
            )
            for b in bars:
                h = b.get_height()
                ax.text(
                    b.get_x() + b.get_width() / 2.0,
                    h,
                    f"{h:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    fontweight="bold",
                )

        ax.set_xticks(x, common_eps, rotation=20)
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)
        ax.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(out_dir / file_name, dpi=220, bbox_inches="tight")
        plt.close(fig)

    # Energy delta lines (consistent color mapping)
    rc_energy = []
    pinn_energy = []
    rbc_energy = []
    for ep in common_eps:
        rc_payload = json.loads(files_by_pred["rc"][ep].read_text(encoding="utf-8"))
        pinn_payload = json.loads(files_by_pred["pinn"][ep].read_text(encoding="utf-8"))
        rbc_payload = json.loads(files_by_pred["rbc"][ep].read_text(encoding="utf-8"))
        rc_energy.append(_to_float((rc_payload.get("diagnostic_kpis", {}) or {}).get("total_energy_Wh")) or 0.0)
        pinn_energy.append(_to_float((pinn_payload.get("diagnostic_kpis", {}) or {}).get("total_energy_Wh")) or 0.0)
        rbc_energy.append(_to_float((rbc_payload.get("diagnostic_kpis", {}) or {}).get("total_energy_Wh")) or 0.0)

    def _pct_delta(v: np.ndarray, ref: np.ndarray) -> np.ndarray:
        safe = np.where(np.abs(ref) < 1e-12, np.nan, ref)
        return 100.0 * (v - ref) / safe

    rc_arr = np.asarray(rc_energy, dtype=float)
    pinn_arr = np.asarray(pinn_energy, dtype=float)
    rbc_arr = np.asarray(rbc_energy, dtype=float)

    plt.figure(figsize=(10, 5))
    plt.axhline(0.0, color="black", linewidth=1.0)
    plt.plot(common_eps, _pct_delta(rc_arr, rbc_arr), marker="o", color=colors["rc"], label="RC vs RBC")
    plt.plot(common_eps, _pct_delta(pinn_arr, rbc_arr), marker="s", color=colors["pinn"], label="PINN vs RBC")
    plt.title("Energy Delta vs RBC")
    plt.ylabel("Delta [%]")
    plt.xticks(rotation=20)
    plt.grid(axis="y", alpha=0.3)
    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(out_dir / "energy_delta_vs_rbc_refreshed.png", dpi=220, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(10, 5))
    plt.axhline(0.0, color="black", linewidth=1.0)
    plt.plot(common_eps, _pct_delta(pinn_arr, rc_arr), marker="s", color=colors["pinn"], label="PINN vs RC")
    plt.plot(common_eps, _pct_delta(rbc_arr, rc_arr), marker="^", color=colors["rbc"], label="RBC vs RC")
    plt.title("Energy Delta vs RC")
    plt.ylabel("Delta [%]")
    plt.xticks(rotation=20)
    plt.grid(axis="y", alpha=0.3)
    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(out_dir / "energy_delta_vs_rc_refreshed.png", dpi=220, bbox_inches="tight")
    plt.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate RC vs PINN vs RBC comparison plots")
    parser.add_argument("--raw-root", default="results/eu_rc_vs_pinn/raw", help="Path to raw results directory")
    parser.add_argument("--out-dir", default=str(CANONICAL_OUT_DIR), help="Output directory for plots (kept for compatibility)")
    args = parser.parse_args()
    
    raw_root = Path(args.raw_root).resolve()
    requested_out_dir = Path(args.out_dir).resolve()
    out_dir = CANONICAL_OUT_DIR.resolve()

    if requested_out_dir != out_dir:
        print(f"Note: enforcing canonical output directory: {out_dir.as_posix()}")
    
    if not raw_root.exists():
        print(f"Error: Raw results directory not found: {raw_root}")
        return 1
    
    print(f"Loading results from: {raw_root}")
    results = load_results(raw_root, ["rc", "pinn", "rbc"])
    
    if not results:
        print(f"Error: No results found in {raw_root}")
        return 1
    
    print(f"Found {len(results)} episode results")
    print(f"Generating plots...\n")
    
    plot_three_way_bars(results, out_dir)
    print("[OK] Three-way bar charts")
    
    plot_aggregated_boxplots(results, out_dir)
    print("[OK] Aggregated boxplots")

    plot_timeseries_per_case_episode(results, out_dir)
    print("[OK] Case+episode temperature/setpoint timeseries (RC/PINN/RBC)")

    plot_refreshed_episode_bars(Path("results/mpc_phase1"), out_dir)
    print("[OK] Refreshed episode bars (RC/PINN/RBC, consistent colors)")
    
    print(f"\n✓ All plots saved to: {out_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    exit(main())
