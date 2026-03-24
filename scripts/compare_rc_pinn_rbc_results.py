#!/usr/bin/env python3
"""
Three-way comparison: RC vs PINN vs RBC MPC results.

Analyzes performance across all three control strategies to evaluate:
1. Energy consumption
2. Thermal comfort
3. Peak power demand
4. Computational efficiency (solver time)
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


def safe_pct_delta(value_new: float, value_ref: float, min_abs_ref: float = 1e-6) -> float | None:
    """Return percent delta if reference is well-defined; otherwise None."""
    if abs(float(value_ref)) < min_abs_ref:
        return None
    return 100.0 * (float(value_new) - float(value_ref)) / float(value_ref)


def load_episode(json_path: Path) -> dict[str, Any] | None:
    """Load single episode result."""
    try:
        with json_path.open() as f:
            return json.load(f)
    except Exception:
        return None


def extract_kpis(episode: dict[str, Any]) -> dict[str, float | None]:
    """Extract key metrics from episode result."""
    if not episode:
        return {}
    
    diag = episode.get("diagnostic_kpis", {})
    
    return {
        "energy_Wh": float(diag.get("total_energy_Wh") or 0.0),
        "peak_power_W": float(diag.get("peak_power_W") or 0.0),
        "comfort_Kh": float(diag.get("comfort_Kh") or 0.0),
        "solve_time_ms": float(diag.get("mpc_solve_time_mean_ms") or 0.0),
        "n_steps": int(episode.get("n_steps") or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Three-way comparison: RC vs PINN vs RBC MPC results")
    parser.add_argument(
        "--results-root",
        default="results/eu_rc_vs_pinn/raw",
        help="Root directory with case/predictor/episode.json structure",
    )
    parser.add_argument(
        "--output",
        default="logs/rc_pinn_rbc_comparison.csv",
        help="Output CSV report path",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=[
            "bestest_hydronic",
            "singlezone_commercial_hydronic",
            "twozone_apartment_hydronic",
            "bestest_hydronic_heat_pump",
        ],
        help="Case names to compare",
    )
    args = parser.parse_args()
    
    results_root = Path(args.results_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*120)
    print("RC vs PINN vs RBC THREE-WAY COMPARISON")
    print("="*120 + "\n")
    
    # Collect results: (case, episode) -> {rc, pinn, rbc}
    comparison: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(lambda: {})
    
    for case_name in args.cases:
        case_dir = results_root / case_name
        
        if not case_dir.exists():
            print(f"⚠ Case not found: {case_name}")
            continue
        
        print(f"[{case_name}]")
        
        predictors = {
            "rc": case_dir / "rc",
            "pinn": case_dir / "pinn",
            "rbc": case_dir / "rbc",
        }
        
        pred_files = {
            name: sorted((path.glob("*.json") if path.exists() else []))
            for name, path in predictors.items()
        }
        
        # Find common episodes across all three
        stems_by_pred = {
            name: {f.stem for f in files}
            for name, files in pred_files.items()
        }
        
        common_episodes = (
            stems_by_pred.get("rc", set())
            & stems_by_pred.get("pinn", set())
            & stems_by_pred.get("rbc", set())
        )
        
        print(f"  RC episodes: {len(pred_files['rc'])}")
        print(f"  PINN episodes: {len(pred_files['pinn'])}")
        print(f"  RBC episodes: {len(pred_files['rbc'])}")
        print(f"  Common episodes: {len(common_episodes)}")
        
        # Build file maps
        files_by_pred = {
            name: {f.stem: f for f in pred_files[name]}
            for name in predictors.keys()
        }
        
        for episode_stem in sorted(common_episodes):
            row_data = {}
            for pred_name in ["rc", "pinn", "rbc"]:
                ep_file = files_by_pred[pred_name].get(episode_stem)
                kpis = extract_kpis(load_episode(ep_file)) if ep_file else {}
                row_data[pred_name] = kpis
            
            comparison[(case_name, episode_stem)] = row_data
    
    # Generate comparison CSV
    print("\n" + "="*120)
    print("DETAILED COMPARISON")
    print("="*120 + "\n")
    
    with output.open("w", newline="") as csv_file:
        fieldnames = [
            "case",
            "episode",
            "rc_energy_Wh",
            "pinn_energy_Wh",
            "rbc_energy_Wh",
            "pinn_vs_rc_energy_pct",
            "rbc_vs_rc_energy_pct",
            "rc_comfort_Kh",
            "pinn_comfort_Kh",
            "rbc_comfort_Kh",
            "pinn_vs_rc_comfort_pct",
            "rbc_vs_rc_comfort_pct",
            "rc_peak_W",
            "pinn_peak_W",
            "rbc_peak_W",
            "pinn_vs_rc_peak_pct",
            "rbc_vs_rc_peak_pct",
            "rc_solve_time_ms",
            "pinn_solve_time_ms",
            "rbc_solve_time_ms",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        
        # Aggregated statistics
        stats = {
            "pinn_vs_rc": {"energy": [], "comfort": [], "peak": []},
            "rbc_vs_rc": {"energy": [], "comfort": [], "peak": []},
        }
        
        for (case, episode), data in sorted(comparison.items()):
            rc = data.get("rc", {})
            pinn = data.get("pinn", {})
            rbc = data.get("rbc", {})
            
            if not all([rc, pinn, rbc]):
                continue
            
            energy_rc = rc.get("energy_Wh", 0.0)
            energy_pinn = pinn.get("energy_Wh", 0.0)
            energy_rbc = rbc.get("energy_Wh", 0.0)
            comfort_rc = rc.get("comfort_Kh", 0.0)
            comfort_pinn = pinn.get("comfort_Kh", 0.0)
            comfort_rbc = rbc.get("comfort_Kh", 0.0)
            peak_rc = rc.get("peak_power_W", 0.0)
            peak_pinn = pinn.get("peak_power_W", 0.0)
            peak_rbc = rbc.get("peak_power_W", 0.0)
            solve_rc = rc.get("solve_time_ms", 0.0)
            solve_pinn = pinn.get("solve_time_ms", 0.0)
            solve_rbc = rbc.get("solve_time_ms", 0.0)

            # Compute deltas
            pinn_vs_rc_energy = safe_pct_delta(energy_pinn, energy_rc)
            rbc_vs_rc_energy = safe_pct_delta(energy_rbc, energy_rc)
            pinn_vs_rc_comfort = safe_pct_delta(comfort_pinn, comfort_rc)
            rbc_vs_rc_comfort = safe_pct_delta(comfort_rbc, comfort_rc)
            pinn_vs_rc_peak = safe_pct_delta(peak_pinn, peak_rc)
            rbc_vs_rc_peak = safe_pct_delta(peak_rbc, peak_rc)

            # Accumulate stats
            if pinn_vs_rc_energy is not None:
                stats["pinn_vs_rc"]["energy"].append(pinn_vs_rc_energy)
            if rbc_vs_rc_energy is not None:
                stats["rbc_vs_rc"]["energy"].append(rbc_vs_rc_energy)
            if pinn_vs_rc_comfort is not None:
                stats["pinn_vs_rc"]["comfort"].append(pinn_vs_rc_comfort)
            if rbc_vs_rc_comfort is not None:
                stats["rbc_vs_rc"]["comfort"].append(rbc_vs_rc_comfort)
            if pinn_vs_rc_peak is not None:
                stats["pinn_vs_rc"]["peak"].append(pinn_vs_rc_peak)
            if rbc_vs_rc_peak is not None:
                stats["rbc_vs_rc"]["peak"].append(rbc_vs_rc_peak)
            
            writer.writerow({
                "case": case,
                "episode": episode,
                "rc_energy_Wh": f"{energy_rc:.1f}",
                "pinn_energy_Wh": f"{energy_pinn:.1f}",
                "rbc_energy_Wh": f"{energy_rbc:.1f}",
                "pinn_vs_rc_energy_pct": f"{pinn_vs_rc_energy:+.2f}" if pinn_vs_rc_energy is not None else "NA",
                "rbc_vs_rc_energy_pct": f"{rbc_vs_rc_energy:+.2f}" if rbc_vs_rc_energy is not None else "NA",
                "rc_comfort_Kh": f"{comfort_rc:.2f}",
                "pinn_comfort_Kh": f"{comfort_pinn:.2f}",
                "rbc_comfort_Kh": f"{comfort_rbc:.2f}",
                "pinn_vs_rc_comfort_pct": f"{pinn_vs_rc_comfort:+.2f}" if pinn_vs_rc_comfort is not None else "NA",
                "rbc_vs_rc_comfort_pct": f"{rbc_vs_rc_comfort:+.2f}" if rbc_vs_rc_comfort is not None else "NA",
                "rc_peak_W": f"{peak_rc:.1f}",
                "pinn_peak_W": f"{peak_pinn:.1f}",
                "rbc_peak_W": f"{peak_rbc:.1f}",
                "pinn_vs_rc_peak_pct": f"{pinn_vs_rc_peak:+.2f}" if pinn_vs_rc_peak is not None else "NA",
                "rbc_vs_rc_peak_pct": f"{rbc_vs_rc_peak:+.2f}" if rbc_vs_rc_peak is not None else "NA",
                "rc_solve_time_ms": f"{solve_rc:.1f}",
                "pinn_solve_time_ms": f"{solve_pinn:.1f}",
                "rbc_solve_time_ms": f"{solve_rbc:.1f}",
            })
    
    # Print summary statistics
    print("\n" + "="*120)
    print("SUMMARY STATISTICS")
    print("="*120 + "\n")
    
    _print_stat_group("PINN vs RC", stats["pinn_vs_rc"])
    _print_stat_group("RBC vs RC", stats["rbc_vs_rc"])
    
    print(f"\n✓ Detailed comparison written to: {output}")


def _print_stat_group(label: str, metrics: dict[str, list[float]]) -> None:
    """Print summary stats for a comparison group."""
    print(f"{label}:")
    print("-" * 100)
    
    for metric_name, values in [("ENERGY", "energy"), ("COMFORT", "comfort"), ("PEAK POWER", "peak")]:
        data = np.array(metrics.get(values, []))
        if len(data) == 0:
            print(f"  {metric_name}: (no data)")
            continue
        
        mean_val = float(np.mean(data))
        median_val = float(np.median(data))
        std_val = float(np.std(data))
        min_val = float(np.min(data))
        max_val = float(np.max(data))
        
        print(f"  {metric_name}:")
        print(f"    Mean:   {mean_val:+.2f}%")
        print(f"    Median: {median_val:+.2f}%")
        print(f"    Std:    {std_val:.2f}%")
        print(f"    Range:  [{min_val:+.2f}%, {max_val:+.2f}%]")
        
        # Interpretation
        if values == "energy":
            if mean_val < -2:
                interpret = "✓ Saves energy on average"
            elif mean_val > 2:
                interpret = "✗ Uses more energy on average"
            else:
                interpret = "≈ Similar energy consumption"
        elif values == "comfort":
            if mean_val < -2:
                interpret = "✓ Improves comfort on average"
            elif mean_val > 2:
                interpret = "✗ Reduces comfort on average"
            else:
                interpret = "≈ Similar comfort on average"
        else:  # peak power
            if mean_val < -2:
                interpret = "✓ Lower peak power on average"
            elif mean_val > 2:
                interpret = "✗ Higher peak power on average"
            else:
                interpret = "≈ Similar peak power on average"
        
        print(f"    → {interpret}")
    
    print()


if __name__ == "__main__":
    main()
