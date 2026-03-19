#!/usr/bin/env python3
"""
Results aggregation and comparison tool.
Summarizes MPC benchmark results across all cases and predictors.
Generates comparative metrics: comfort, energy, cost.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


def load_episode_results(episode_file: Path) -> dict[str, Any]:
    """Load a single episode result file."""
    if not episode_file.exists():
        return {}
    
    try:
        return json.loads(episode_file.read_text())
    except:
        return {}


def aggregate_case_results(case_dir: Path) -> dict[str, Any]:
    """Aggregate all episodes for a single case and predictor."""
    if not case_dir.exists():
        return {"error": "Directory not found"}
    
    episodes = {}
    for episode_file in sorted(case_dir.glob("*.json")):
        episode_id = episode_file.stem
        data = load_episode_results(episode_file)
        
        # Extract key KPIs
        if "diagnostic_kpis" in data:
            diag = data["diagnostic_kpis"]
            episodes[episode_id] = {
                "comfort_Kh": diag.get("comfort_Kh"),
                "comfort_violation_steps": diag.get("comfort_violation_steps"),
                "total_energy_Wh": diag.get("total_energy_Wh"),
                "heating_energy_Wh": diag.get("heating_energy_Wh"),
                "control_smoothness": diag.get("control_smoothness"),
                "mpc_solve_time_mean_ms": diag.get("mpc_solve_time_mean_ms"),
            }
        elif "step_records" in data:
            # Fallback to computing from step records
            records = data.get("step_records", [])
            if records:
                comfort_violation = sum(1 for r in records if r.get("comfort_violation", False))
                total_energy = sum(r.get("u_heating", 0) * 0.25 for r in records)  # Assume 15-min steps
                
                episodes[episode_id] = {
                    "comfort_Kh": None,
                    "comfort_violation_steps": comfort_violation,
                    "total_energy_Wh": total_energy,
                    "n_steps": len(records),
                }
    
    # Compute aggregates
    if not episodes:
        return {"error": "No episodes found"}
    
    agg = {
        "n_episodes": len(episodes),
        "episodes": episodes,
    }
    
    # Aggregate comfort
    comfort_values = [e.get("comfort_Kh") for e in episodes.values() if e.get("comfort_Kh") is not None]
    if comfort_values:
        agg["comfort_Kh_mean"] = np.mean(comfort_values)
        agg["comfort_Kh_std"] = np.std(comfort_values)
        agg["comfort_Kh_max"] = max(comfort_values)
    
    # Aggregate energy
    energy_values = [e.get("total_energy_Wh") for e in episodes.values() if e.get("total_energy_Wh") is not None]
    if energy_values:
        agg["energy_Wh_mean"] = np.mean(energy_values)
        agg["energy_Wh_std"] = np.std(energy_values)
    
    # Aggregate violations
    violations = [e.get("comfort_violation_steps", 0) for e in episodes.values()]
    if violations:
        agg["violation_steps_total"] = sum(violations)
        agg["violation_steps_mean"] = np.mean(violations)
    
    return agg


def analyze_all_results() -> dict[str, Any]:
    """Analyze all case results."""
    base_dir = Path("results/eu_rc_vs_pinn/raw")
    
    if not base_dir.exists():
        return {"error": "Results directory not found"}
    
    all_results = {}
    
    for case_dir in sorted(base_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        
        case_name = case_dir.name
        case_results = {}
        
        # RC results
        rc_dir = case_dir / "rc"
        rc_agg = aggregate_case_results(rc_dir) if rc_dir.exists() else {"error": "RC dir not found"}
        case_results["rc"] = rc_agg
        
        # PINN results
        pinn_dir = case_dir / "pinn"
        pinn_agg = aggregate_case_results(pinn_dir) if pinn_dir.exists() else {"error": "PINN dir not found"}
        case_results["pinn"] = pinn_agg
        
        # Comparison
        if "error" not in rc_agg and "error" not in pinn_agg:
            rc_comfort = rc_agg.get("comfort_Kh_mean", 0)
            pinn_comfort = pinn_agg.get("comfort_Kh_mean", 0)
            
            if rc_comfort and pinn_comfort:
                comfort_diff_pct = ((pinn_comfort - rc_comfort) / rc_comfort) * 100
                case_results["comparison"] = {
                    "rc_comfort_Kh": round(rc_comfort, 2),
                    "pinn_comfort_Kh": round(pinn_comfort, 2),
                    "comfort_improvement_pct": round(comfort_diff_pct, 1),
                    "pinn_better": pinn_comfort < rc_comfort,
                }
        
        all_results[case_name] = case_results
    
    return all_results


def main() -> int:
    print("=" * 90)
    print("MPC BENCHMARK RESULTS AGGREGATION")
    print("=" * 90)
    
    results = analyze_all_results()
    
    if "error" in results:
        print(f"ERROR: {results['error']}")
        return 1
    
    print("\nBENCHMARK CASE SUMMARY")
    print("-" * 90)
    
    # Summary table
    format_str = "{:<35} {:>12} {:>12} {:>12} {:>12}"
    print(format_str.format("Case", "RC Comfort", "PINN Comfort", "Difference", "PINN Better?"))
    print("-" * 90)
    
    for case_name, case_data in sorted(results.items()):
        rc_comfort = case_data.get("rc", {}).get("comfort_Kh_mean")
        pinn_comfort = case_data.get("pinn", {}).get("comfort_Kh_mean")
        
        if rc_comfort and pinn_comfort:
            diff = pinn_comfort - rc_comfort
            better = "YES" if diff < 0 else "NO"
            print(format_str.format(
                case_name[:35],
                f"{rc_comfort:.1f} Kh",
                f"{pinn_comfort:.1f} Kh",
                f"{diff:+.1f} Kh",
                better
            ))
        else:
            status = ""
            if not rc_comfort:
                status += " [RC missing]"
            if not pinn_comfort:
                status += " [PINN missing]"
            print(format_str.format(case_name[:35], "-", "-", "-", "-") + status)
    
    # Detailed metrics
    print("\n" + "=" * 90)
    print("DETAILED METRICS BY CASE")
    print("=" * 90)
    
    for case_name, case_data in sorted(results.items()):
        print(f"\n{case_name}")
        print("-" * 90)
        
        for predictor in ["rc", "pinn"]:
            pred_data = case_data.get(predictor, {})
            if "error" in pred_data:
                print(f"  {predictor.upper()}: {pred_data['error']}")
                continue
            
            print(f"  {predictor.upper()}:")
            print(f"    Episodes: {pred_data.get('n_episodes', 0)}")
            print(f"    Comfort: {pred_data.get('comfort_Kh_mean', '-'):.1f} ± {pred_data.get('comfort_Kh_std', '-'):.1f} Kh" 
                  if pred_data.get('comfort_Kh_mean') else f"    Comfort: -")
            print(f"    Energy: {pred_data.get('energy_Wh_mean', '-'):.0f} ± {pred_data.get('energy_Wh_std', '-'):.0f} Wh"
                  if pred_data.get('energy_Wh_mean') else f"    Energy: -")
            print(f"    Violations: {pred_data.get('violation_steps_mean', '-'):.0f} steps/episode"
                  if pred_data.get('violation_steps_mean') is not None else f"    Violations: -")
        
        # Show comparison if available
        if "comparison" in case_data:
            comp = case_data["comparison"]
            improvement = comp["comfort_improvement_pct"]
            status = "✓ PINN BETTER" if comp["pinn_better"] else "✗ RC BETTER"
            print(f"  {status}: {improvement:+.1f}%")
    
    print("\n" + "=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
