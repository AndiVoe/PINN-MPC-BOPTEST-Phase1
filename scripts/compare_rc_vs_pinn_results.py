#!/usr/bin/env python3
"""
Compare RC vs PINN MPC benchmark results.

Analyzes whether PINN-based MPC achieves meaningfully better comfort/energy
tradeoffs compared to RC-based MPC. This is the final validation that PINN
brings real value to the control problem.
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
    challenges = episode.get("challenge_kpis", {})
    
    return {
        "energy_Wh": float(diag.get("total_energy_Wh") or 0.0),
        "peak_power_W": float(diag.get("peak_power_W") or 0.0),
        "comfort_Kh": float(diag.get("comfort_Kh") or 0.0),
        "n_steps": int(episode.get("n_steps") or 0),
        "tdis_tot": challenges.get("tdis_tot", {}).get("value"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare RC vs PINN MPC results")
    parser.add_argument(
        "--results-root",
        default="results/eu_rc_vs_pinn/raw",
        help="Root directory with case/predictor/episode.json structure",
    )
    parser.add_argument(
        "--output",
        default="logs/mpc_comparison_report.csv",
        help="Output CSV report path",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=["bestest_hydronic", "singlezone_commercial_hydronic"],
        help="Case names to compare",
    )
    args = parser.parse_args()
    
    results_root = Path(args.results_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*100)
    print("RC vs PINN MPC COMPARISON")
    print("="*100 + "\n")
    
    # Collect results
    comparison: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {})
    
    for case_name in args.cases:
        case_dir = results_root / case_name
        
        if not case_dir.exists():
            print(f"⚠ Case not found: {case_name}")
            continue
        
        print(f"[{case_name}]")
        
        rc_dir = case_dir / "rc"
        pinn_dir = case_dir / "pinn"
        
        rc_files = sorted(rc_dir.glob("*.json")) if rc_dir.exists() else []
        pinn_files = sorted(pinn_dir.glob("*.json")) if pinn_dir.exists() else []
        
        # Match episodes by stem
        rc_by_stem = {f.stem: f for f in rc_files}
        pinn_by_stem = {f.stem: f for f in pinn_files}
        
        common_episodes = set(rc_by_stem.keys()) & set(pinn_by_stem.keys())
        
        print(f"  RC episodes: {len(rc_files)}")
        print(f"  PINN episodes: {len(pinn_files)}")
        print(f"  Common episodes: {len(common_episodes)}")
        
        for episode_stem in sorted(common_episodes):
            rc_kpis = extract_kpis(load_episode(rc_by_stem[episode_stem]))
            pinn_kpis = extract_kpis(load_episode(pinn_by_stem[episode_stem]))
            
            comparison[(case_name, episode_stem)] = {
                "rc": rc_kpis,
                "pinn": pinn_kpis,
            }
    
    # Generate comparison CSV
    print("\n" + "="*100)
    print("DETAILED COMPARISON")
    print("="*100 + "\n")
    
    with output.open("w", newline="") as csv_file:
        fieldnames = [
            "case",
            "episode",
            "rc_energy_Wh",
            "pinn_energy_Wh",
            "energy_delta_pct",
            "rc_comfort_Kh",
            "pinn_comfort_Kh",
            "comfort_delta_pct",
            "rc_peak_W",
            "pinn_peak_W",
            "peak_delta_pct",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        
        energy_deltas = []
        comfort_deltas = []
        peak_deltas = []
        unstable_delta_rows = 0
        
        for (case, episode), data in sorted(comparison.items()):
            rc = data["rc"]
            pinn = data["pinn"]
            
            if not rc or not pinn:
                continue
            
            energy_rc = rc.get("energy_Wh", 0.0)
            energy_pinn = pinn.get("energy_Wh", 0.0)
            comfort_rc = rc.get("comfort_Kh", 0.0)
            comfort_pinn = pinn.get("comfort_Kh", 0.0)
            peak_rc = rc.get("peak_power_W", 0.0)
            peak_pinn = pinn.get("peak_power_W", 0.0)

            energy_delta = safe_pct_delta(energy_pinn, energy_rc)
            comfort_delta = safe_pct_delta(comfort_pinn, comfort_rc)
            peak_delta = safe_pct_delta(peak_pinn, peak_rc)

            if energy_delta is None or comfort_delta is None or peak_delta is None:
                unstable_delta_rows += 1

            if energy_delta is not None:
                energy_deltas.append(energy_delta)
            if comfort_delta is not None:
                comfort_deltas.append(comfort_delta)
            if peak_delta is not None:
                peak_deltas.append(peak_delta)
            
            writer.writerow({
                "case": case,
                "episode": episode,
                "rc_energy_Wh": f"{energy_rc:.1f}",
                "pinn_energy_Wh": f"{energy_pinn:.1f}",
                "energy_delta_pct": f"{energy_delta:+.2f}" if energy_delta is not None else "NA",
                "rc_comfort_Kh": f"{comfort_rc:.2f}",
                "pinn_comfort_Kh": f"{comfort_pinn:.2f}",
                "comfort_delta_pct": f"{comfort_delta:+.2f}" if comfort_delta is not None else "NA",
                "rc_peak_W": f"{peak_rc:.1f}",
                "pinn_peak_W": f"{peak_pinn:.1f}",
                "peak_delta_pct": f"{peak_delta:+.2f}" if peak_delta is not None else "NA",
            })

    if unstable_delta_rows:
        print(f"⚠ {unstable_delta_rows} row(s) had near-zero RC baseline; percentage deltas set to NA")
    
    # Summary statistics
    if energy_deltas:
        print(f"ENERGY CONSUMPTION (PINN vs RC):")
        print(f"  Mean delta: {np.mean(energy_deltas):+.2f}%")
        print(f"  Median delta: {np.median(energy_deltas):+.2f}%")
        print(f"  Std dev: {np.std(energy_deltas):.2f}%")
        print(f"  Min/Max: {np.min(energy_deltas):+.2f}% / {np.max(energy_deltas):+.2f}%")
        
        if abs(np.mean(energy_deltas)) < 2.0:
            print(f"  ⚠ CONCERN: PINN energy very similar to RC (<2% mean difference)")
        elif np.mean(energy_deltas) < 0:
            print(f"  ✓ PINN saves energy on average")
        else:
            print(f"  ✗ PINN uses more energy on average")
        print()
    
    if comfort_deltas:
        print(f"COMFORT (PINN vs RC):")
        print(f"  Mean delta: {np.mean(comfort_deltas):+.2f}%")
        print(f"  Median delta: {np.median(comfort_deltas):+.2f}%")
        print(f"  Std dev: {np.std(comfort_deltas):.2f}%")
        print(f"  Min/Max: {np.min(comfort_deltas):+.2f}% / {np.max(comfort_deltas):+.2f}%")
        
        if abs(np.mean(comfort_deltas)) < 2.0:
            print(f"  ⚠ CONCERN: PINN comfort very similar to RC (<2% mean difference)")
        elif np.mean(comfort_deltas) < 0:
            print(f"  ✓ PINN improves comfort on average")
        else:
            print(f"  ✗ PINN reduces comfort on average")
        print()
    
    if peak_deltas:
        print(f"PEAK POWER (PINN vs RC):")
        print(f"  Mean delta: {np.mean(peak_deltas):+.2f}%")
        print(f"  Median delta: {np.median(peak_deltas):+.2f}%")
        print(f"  Std dev: {np.std(peak_deltas):.2f}%")
        print(f"  Min/Max: {np.min(peak_deltas):+.2f}% / {np.max(peak_deltas):+.2f}%")
        print()
    
    print(f"✓ Detailed comparison written to: {output}")


if __name__ == "__main__":
    main()
