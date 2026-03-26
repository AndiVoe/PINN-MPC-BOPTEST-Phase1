#!/usr/bin/env python3
"""
Publication-quality plot generator for PINN-MPC vs RC comparison.
Extends qc_eu_results.py with enhanced visualizations for journal articles.
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
from matplotlib.patches import Patch

import generate_rc_pinn_rbc_plots as three_way


CANONICAL_OUT_DIR = Path("results/mpc_phase1/plots_3way_refresh")


def _to_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def load_results(raw_root: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Load all episode results: (case, predictor, episode) -> payload."""
    results = {}
    for case_dir in sorted(raw_root.glob("*")):
        if not case_dir.is_dir():
            continue
        for predictor in ("rc", "pinn"):
            pred_dir = case_dir / predictor
            if not pred_dir.exists():
                continue
            for ep_file in sorted(pred_dir.glob("te_*.json")):
                payload = json.loads(ep_file.read_text(encoding="utf-8"))
                episode_id = str(payload.get("episode_id", ep_file.stem))
                results[(case_dir.name, predictor, episode_id)] = payload
    return results


def extract_kpi_dict(payload: dict[str, Any], case_name: str = "") -> dict[str, float | None]:
    """Extract KPIs from episode payload."""
    diag = payload.get("diagnostic_kpis", {})
    chall = payload.get("challenge_kpis", {})
    
    # Get building floor area (user-validated values)
    # Source: BOPTEST testcase documentation
    # https://github.com/ibpsa/project1-boptest/wiki/Testcase-List
    area_m2_map = {
        "bestest_hydronic": 48.0,
        "bestest_hydronic_heat_pump": 48.0,
        "bestest_hydronic_heat_pump_air": 48.0,
        "singlezone_commercial_hydronic": 8500.0,
        "singlezone_commercial_radiant": 8500.0,
        "singlezone_commercial_air": 8500.0,
        "twozone_apartment_hydronic": 44.5,
        "twozone_apartment_air": 44.5,
    }
    
    # Find case name in mapping
    area_m2 = 1000.0  # Safe default
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
        "energy_kWh_m2": (energy_wh / 1000.0 / area_m2) if energy_wh and area_m2 else None,
        "peak_W": peak_w,
        "peak_W_m2": (peak_w / area_m2) if peak_w and area_m2 else None,
        "comfort_Kh": comfort_kh,
        "solve_time_ms": solve_time_ms,
        "area_m2": area_m2,
    }


def plot_kpi_bars_per_case(results: dict, out_dir: Path) -> None:
    """Create side-by-side bar charts for each case comparing RC vs PINN."""
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Group by case
    cases_data = defaultdict(lambda: {"rc": [], "pinn": []})
    for (case, pred, episode), payload in results.items():
        kpis = extract_kpi_dict(payload, case_name=case)
        cases_data[case][pred].append(kpis)
    
    cases = sorted(cases_data.keys())
    n_cases = len(cases)
    
    # Plot 1: Energy consumption per m2
    fig, axes = plt.subplots(1, n_cases, figsize=(14, 4), sharey=True)
    if n_cases == 1:
        axes = [axes]
    
    colors = {"rc": "#1f77b4", "pinn": "#d62728"}
    
    for idx, case in enumerate(cases):
        ax = axes[idx]
        x_pos = np.arange(2)
        
        rc_vals = [k["energy_kWh_m2"] for k in cases_data[case]["rc"] if k["energy_kWh_m2"] is not None]
        pinn_vals = [k["energy_kWh_m2"] for k in cases_data[case]["pinn"] if k["energy_kWh_m2"] is not None]
        
        rc_mean = np.mean(rc_vals) if rc_vals else 0
        pinn_mean = np.mean(pinn_vals) if pinn_vals else 0
        
        bars = ax.bar([0, 1], [rc_mean, pinn_mean], color=[colors["rc"], colors["pinn"]], 
                       edgecolor="black", linewidth=1.2, alpha=0.7)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_ylabel("Energy [kWh/m²]" if idx == 0 else "")
        ax.set_title(case.replace("_", " "), fontsize=11, fontweight='bold')
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["RC", "PINN"])
        ax.grid(axis="y", alpha=0.3)
    
    fig.suptitle("Energy Consumption per Case", fontsize=13, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "01_energy_per_case.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    # Plot 2: Comfort violations per case
    fig, axes = plt.subplots(1, n_cases, figsize=(14, 4), sharey=True)
    if n_cases == 1:
        axes = [axes]
    
    for idx, case in enumerate(cases):
        ax = axes[idx]
        
        rc_vals = [k["comfort_Kh"] for k in cases_data[case]["rc"] if k["comfort_Kh"] is not None]
        pinn_vals = [k["comfort_Kh"] for k in cases_data[case]["pinn"] if k["comfort_Kh"] is not None]
        
        rc_mean = np.mean(rc_vals) if rc_vals else 0
        pinn_mean = np.mean(pinn_vals) if pinn_vals else 0
        
        bars = ax.bar([0, 1], [rc_mean, pinn_mean], color=[colors["rc"], colors["pinn"]], 
                       edgecolor="black", linewidth=1.2, alpha=0.7)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_ylabel("Comfort Deviation [K·h]" if idx == 0 else "")
        ax.set_title(case.replace("_", " "), fontsize=11, fontweight='bold')
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["RC", "PINN"])
        ax.grid(axis="y", alpha=0.3)
    
    fig.suptitle("Thermal Comfort Violations per Case", fontsize=13, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "02_comfort_per_case.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    # Plot 3: Peak power per case
    fig, axes = plt.subplots(1, n_cases, figsize=(14, 4), sharey=True)
    if n_cases == 1:
        axes = [axes]
    
    for idx, case in enumerate(cases):
        ax = axes[idx]
        
        rc_vals = [k["peak_W_m2"] for k in cases_data[case]["rc"] if k["peak_W_m2"] is not None]
        pinn_vals = [k["peak_W_m2"] for k in cases_data[case]["pinn"] if k["peak_W_m2"] is not None]
        
        rc_mean = np.mean(rc_vals) if rc_vals else 0
        pinn_mean = np.mean(pinn_vals) if pinn_vals else 0
        
        bars = ax.bar([0, 1], [rc_mean, pinn_mean], color=[colors["rc"], colors["pinn"]], 
                       edgecolor="black", linewidth=1.2, alpha=0.7)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_ylabel("Peak Power [W/m²]" if idx == 0 else "")
        ax.set_title(case.replace("_", " "), fontsize=11, fontweight='bold')
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["RC", "PINN"])
        ax.grid(axis="y", alpha=0.3)
    
    fig.suptitle("Peak Power per Case", fontsize=13, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "03_peak_power_per_case.png", dpi=300, bbox_inches='tight')
    plt.close(fig)


def plot_relative_improvements(results: dict, out_dir: Path) -> None:
    """Create relative improvement plots (PINN vs RC)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Group by case and aggregate
    improvement_by_case = {}
    
    rc_by_case = defaultdict(list)
    pinn_by_case = defaultdict(list)
    
    for (case, pred, episode), payload in results.items():
        kpis = extract_kpi_dict(payload, case_name=case)
        if kpis["energy_kWh_m2"] is not None:
            if pred == "rc":
                rc_by_case[case].append(kpis["energy_kWh_m2"])
            else:
                pinn_by_case[case].append(kpis["energy_kWh_m2"])
    
    cases = sorted(set(rc_by_case.keys()) & set(pinn_by_case.keys()))
    improvements = []
    
    for case in cases:
        rc_mean = np.mean(rc_by_case[case])
        pinn_mean = np.mean(pinn_by_case[case])
        # Negative = PINN uses less energy (improvement)
        improvement_pct = ((pinn_mean - rc_mean) / rc_mean) * 100
        improvements.append(improvement_pct)
    
    # Plot: Relative energy improvement
    fig, ax = plt.subplots(figsize=(10, 5))
    colors_list = ["#2ca02c" if x < 0 else "#ff7f0e" for x in improvements]
    bars = ax.barh(cases, improvements, color=colors_list, edgecolor="black", linewidth=1.2, alpha=0.75)
    
    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, improvements)):
        label = f"{abs(val):.1f}%"
        x_pos = val + (2 if val > 0 else -2)
        ax.text(x_pos, bar.get_y() + bar.get_height()/2, label,
               va='center', ha='left' if val > 0 else 'right', fontweight='bold', fontsize=10)
    
    ax.axvline(0, color='black', linestyle='-', linewidth=1.5)
    ax.set_xlabel("Energy Difference [%] (← PINN saves energy | RC saves →)", fontsize=11, fontweight='bold')
    ax.set_title("Relative Energy Performance: PINN vs RC (Negative = PINN Better)", fontsize=12, fontweight='bold')
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "04_relative_energy_improvement.png", dpi=300, bbox_inches='tight')
    plt.close(fig)


def plot_aggregated_kpi_boxplots(results: dict, out_dir: Path) -> None:
    """Create aggregated KPI comparison box plots."""
    out_dir.mkdir(parents=True, exist_ok=True)
    
    rc_energy = []
    pinn_energy = []
    rc_comfort = []
    pinn_comfort = []
    rc_peak = []
    pinn_peak = []
    rc_time = []
    pinn_time = []
    
    for (case, pred, episode), payload in results.items():
        kpis = extract_kpi_dict(payload, case_name=case)
        if pred == "rc":
            if kpis["energy_kWh_m2"] is not None:
                rc_energy.append(kpis["energy_kWh_m2"])
            if kpis["comfort_Kh"] is not None:
                rc_comfort.append(kpis["comfort_Kh"])
            if kpis["peak_W_m2"] is not None:
                rc_peak.append(kpis["peak_W_m2"])
            if kpis["solve_time_ms"] is not None:
                rc_time.append(kpis["solve_time_ms"])
        else:
            if kpis["energy_kWh_m2"] is not None:
                pinn_energy.append(kpis["energy_kWh_m2"])
            if kpis["comfort_Kh"] is not None:
                pinn_comfort.append(kpis["comfort_Kh"])
            if kpis["peak_W_m2"] is not None:
                pinn_peak.append(kpis["peak_W_m2"])
            if kpis["solve_time_ms"] is not None:
                pinn_time.append(kpis["solve_time_ms"])
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    colors_list = ["#1f77b4", "#d62728"]
    
    # Energy
    ax = axes[0, 0]
    bp = ax.boxplot([rc_energy, pinn_energy], tick_labels=["RC", "PINN"], patch_artist=True)
    for patch, color in zip(bp["boxes"], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel("Energy [kWh/m²]", fontweight='bold')
    ax.set_title("Total Energy Consumption", fontweight='bold')
    ax.grid(axis="y", alpha=0.3)
    
    # Comfort
    ax = axes[0, 1]
    bp = ax.boxplot([rc_comfort, pinn_comfort], tick_labels=["RC", "PINN"], patch_artist=True)
    for patch, color in zip(bp["boxes"], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel("Comfort Deviation [K·h]", fontweight='bold')
    ax.set_title("Thermal Comfort Violations", fontweight='bold')
    ax.grid(axis="y", alpha=0.3)
    
    # Peak Power
    ax = axes[1, 0]
    bp = ax.boxplot([rc_peak, pinn_peak], tick_labels=["RC", "PINN"], patch_artist=True)
    for patch, color in zip(bp["boxes"], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel("Peak Power [W/m²]", fontweight='bold')
    ax.set_title("Peak Power Demand", fontweight='bold')
    ax.grid(axis="y", alpha=0.3)
    
    # Solve time
    ax = axes[1, 1]
    bp = ax.boxplot([rc_time, pinn_time], tick_labels=["RC", "PINN"], patch_artist=True)
    for patch, color in zip(bp["boxes"], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel("Mean Solve Time [ms]", fontweight='bold')
    ax.set_title("MPC Solver Runtime", fontweight='bold')
    ax.grid(axis="y", alpha=0.3)
    
    fig.suptitle("Aggregated KPI Comparison (All Episodes)", fontsize=13, fontweight='bold', y=0.995)
    fig.tight_layout()
    fig.savefig(out_dir / "05_aggregated_kpi_boxplots.png", dpi=300, bbox_inches='tight')
    plt.close(fig)


def plot_enhanced_pareto_frontier(results: dict, out_dir: Path) -> None:
    """Enhanced Pareto frontier plot with case labels and trends."""
    out_dir.mkdir(parents=True, exist_ok=True)
    
    rc_points = []
    pinn_points = []
    
    for (case, pred, episode), payload in results.items():
        kpis = extract_kpi_dict(payload, case_name=case)
        if kpis["energy_kWh_m2"] is not None and kpis["comfort_Kh"] is not None:
            point = (kpis["energy_kWh_m2"], kpis["comfort_Kh"])
            if pred == "rc":
                rc_points.append(point)
            else:
                pinn_points.append(point)
    
    fig, ax = plt.subplots(figsize=(10, 7))
    
    rc_x = [p[0] for p in rc_points]
    rc_y = [p[1] for p in rc_points]
    pinn_x = [p[0] for p in pinn_points]
    pinn_y = [p[1] for p in pinn_points]
    
    # Scatter
    ax.scatter(rc_x, rc_y, s=120, alpha=0.7, label="RC Baseline", 
              color="#1f77b4", edgecolors="black", linewidth=1.2, marker="o")
    ax.scatter(pinn_x, pinn_y, s=120, alpha=0.7, label="PINN-MPC", 
              color="#d62728", edgecolors="black", linewidth=1.2, marker="s")
    
    # Add trend lines
    if rc_x and rc_y:
        z_rc = np.polyfit(rc_x, rc_y, 1)
        p_rc = np.poly1d(z_rc)
        x_range = np.linspace(min(rc_x), max(rc_x), 100)
        ax.plot(x_range, p_rc(x_range), "--", color="#1f77b4", alpha=0.5, linewidth=2, label="RC trend")
    
    if pinn_x and pinn_y:
        z_pinn = np.polyfit(pinn_x, pinn_y, 1)
        p_pinn = np.poly1d(z_pinn)
        x_range = np.linspace(min(pinn_x), max(pinn_x), 100)
        ax.plot(x_range, p_pinn(x_range), "--", color="#d62728", alpha=0.5, linewidth=2, label="PINN trend")
    
    ax.set_xlabel("Total Energy [kWh/m²]", fontsize=12, fontweight='bold')
    ax.set_ylabel("Comfort Violation [K·h]", fontsize=12, fontweight='bold')
    ax.set_title("Energy-Comfort Trade-off: RC vs PINN-MPC", fontsize=13, fontweight='bold')
    ax.legend(loc="upper right", fontsize=11, framealpha=0.95)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "06_pareto_frontier_enhanced.png", dpi=300, bbox_inches='tight')
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate publication-quality plots (delegates to standardized 3-way style)."
    )
    parser.add_argument("--raw-root", default="results/eu_rc_vs_pinn/raw", help="Path to raw results directory")
    parser.add_argument("--out-dir", default=str(three_way.CANONICAL_OUT_DIR), help="Output directory for plots")
    args = parser.parse_args()

    raw_root = Path(args.raw_root).resolve()
    out_dir = three_way.CANONICAL_OUT_DIR.resolve()
    requested_out_dir = Path(args.out_dir).resolve()
    if requested_out_dir != out_dir:
        print(f"Note: enforcing canonical output directory: {out_dir.as_posix()}")

    if not raw_root.exists():
        print(f"Error: Raw results directory not found: {raw_root}")
        return 1

    print(f"Loading results from: {raw_root}")
    results = three_way.load_results(raw_root, ["rc", "pinn", "rbc"])
    if not results:
        print(f"Error: No results found in {raw_root}")
        return 1

    print(f"Found {len(results)} episode results")
    print("Generating standardized 3-way publication plots...")
    three_way.plot_three_way_bars(results, out_dir)
    three_way.plot_aggregated_boxplots(results, out_dir)
    three_way.plot_timeseries_per_case_episode(results, out_dir)
    three_way.plot_refreshed_episode_bars(Path("results/mpc_phase1"), out_dir)
    print(f"[OK] All plots saved to: {out_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    exit(main())
