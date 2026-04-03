#!/usr/bin/env python3
"""
Generate publication-ready plots and reports from Stage 2 RC variant vs PINN summary.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def load_summary(path: Path) -> dict[str, Any]:
    """Load the best_rc_vs_pinn_summary.json."""
    return json.loads(path.read_text(encoding="utf-8"))


def generate_comparison_plots(summary: dict[str, Any], out_dir: Path) -> None:
    """Generate comparison plots."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_data = summary.get("cases", [])
    
    if not cases_data:
        print("No case data found in summary.")
        return
    
    case_names = [c["case"] for c in cases_data]
    
    # Plot 1: Energy comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    rc_energy = [c["best_rc_metrics"]["total_energy_Wh"] / 1000 for c in cases_data]  # Convert to kWh
    pinn_energy = [c["pinn_metrics"]["total_energy_Wh"] / 1000 for c in cases_data]
    x = np.arange(len(case_names))
    width = 0.35
    ax.bar(x - width/2, rc_energy, width, label="Best RC Variant", alpha=0.8)
    ax.bar(x + width/2, pinn_energy, width, label="PINN", alpha=0.8)
    ax.set_ylabel("Total Energy [kWh]", fontsize=11)
    ax.set_title("Energy Consumption Comparison (Stage 2: 30-day episodes)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(case_names, rotation=45, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "01_stage2_energy_comparison.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✓ Generated: 01_stage2_energy_comparison.png")
    
    # Plot 2: Comfort comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    rc_comfort = [c["best_rc_metrics"]["comfort_Kh"] for c in cases_data]
    pinn_comfort = [c["pinn_metrics"]["comfort_Kh"] for c in cases_data]
    ax.bar(x - width/2, rc_comfort, width, label="Best RC Variant", alpha=0.8)
    ax.bar(x + width/2, pinn_comfort, width, label="PINN", alpha=0.8)
    ax.set_ylabel("Thermal Discomfort [K·h]", fontsize=11)
    ax.set_title("Comfort Comparison (Stage 2: 30-day episodes)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(case_names, rotation=45, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "02_stage2_comfort_comparison.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✓ Generated: 02_stage2_comfort_comparison.png")
    
    # Plot 3: Solver time comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    rc_solve = [c["best_rc_metrics"]["solve_ms"] for c in cases_data]
    pinn_solve = [c["pinn_metrics"]["solve_ms"] for c in cases_data]
    ax.bar(x - width/2, rc_solve, width, label="Best RC Variant", alpha=0.8)
    ax.bar(x + width/2, pinn_solve, width, label="PINN", alpha=0.8)
    ax.set_ylabel("Mean MPC Solve Time [ms]", fontsize=11)
    ax.set_title("Computational Performance Comparison (Stage 2)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(case_names, rotation=45, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "03_stage2_solve_time_comparison.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✓ Generated: 03_stage2_solve_time_comparison.png")
    
    # Plot 4: Relative energy improvement (% difference)
    fig, ax = plt.subplots(figsize=(10, 6))
    delta_energy_pct = [
        100.0 * (c["delta_energy_Wh_pinn_minus_best_rc"] / c["best_rc_metrics"]["total_energy_Wh"])
        for c in cases_data
    ]
    colors = ["green" if d < 0 else "red" for d in delta_energy_pct]
    ax.barh(case_names, delta_energy_pct, color=colors, alpha=0.7)
    ax.set_xlabel("Energy Change (%)", fontsize=11)
    ax.axvline(x=0, color="black", linestyle="-", linewidth=0.8)
    ax.set_title("Relative Energy Difference (PINN vs Best RC) [negative = PINN saves energy]", 
                 fontsize=12, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "04_stage2_relative_energy_improvement.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✓ Generated: 04_stage2_relative_energy_improvement.png")
    
    # Plot 5: Cost comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    rc_cost = [c["best_rc_metrics"]["cost_tot"] for c in cases_data]
    pinn_cost = [c["pinn_metrics"]["cost_tot"] for c in cases_data]
    ax.bar(x - width/2, rc_cost, width, label="Best RC Variant", alpha=0.8)
    ax.bar(x + width/2, pinn_cost, width, label="PINN", alpha=0.8)
    ax.set_ylabel("Total Operating Cost [€]", fontsize=11)
    ax.set_title("Operating Cost Comparison (Stage 2)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(case_names, rotation=45, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "05_stage2_cost_comparison.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✓ Generated: 05_stage2_cost_comparison.png")


def generate_markdown_report(summary: dict[str, Any], out_path: Path) -> None:
    """Generate a detailed markdown report."""
    cases_data = summary.get("cases", [])
    aggregate = summary.get("aggregate", {})
    episode = summary.get("episode", "te_std_01")
    
    lines = [
        "# Stage 2: RC Variant Selection & PINN Comparison Report",
        "",
        f"**Generated**: {Path(__file__).stat()}",
        f"**Episode**: {episode}",
        f"**Date**: April 3, 2026",
        "",
        "## Executive Summary",
        "",
        f"This report presents the final RC variant selection based on Stage 2 benchmarking (30-day episodes)",
        f"and compares the best RC variant against the PINN model for each of the 4 European BOPTEST testcases.",
        "",
        "### Key Findings",
        "",
    ]
    
    # Aggregate stats
    if aggregate:
        mean_cost_delta = aggregate.get("mean_delta_cost_tot")
        mean_comfort_delta = aggregate.get("mean_delta_comfort_Kh")
        mean_energy_delta = aggregate.get("mean_delta_energy_Wh")
        
        lines.append(f"- **Average Cost Difference (PINN vs RC)**: {mean_cost_delta:+.4f} €")
        lines.append(f"  - Negative = PINN is more cost-effective on average")
        lines.append(f"- **Average Comfort Difference**: {mean_comfort_delta:+.2f} K·h")
        lines.append(f"  - Negative = PINN achieves better comfort")
        lines.append(f"- **Average Energy Difference**: {mean_energy_delta:+.0f} Wh")
        lines.append(f"  - Negative = PINN consumes less energy")
        lines.append("")
    
    lines.extend([
        "## Case-by-Case Analysis",
        "",
    ])
    
    for i, case in enumerate(cases_data, 1):
        case_name = case["case"]
        best_variant = case["best_rc_variant"]
        
        rc_metrics = case["best_rc_metrics"]
        pinn_metrics = case["pinn_metrics"]
        
        lines.extend([
            f"### Case {i}: {case_name}",
            "",
            f"**Best RC Variant Selected**: `{best_variant}`",
            f"**Selection Score**: {case['best_rc_score']:.2f}",
            "",
            "#### Best RC Variant Performance",
            "",
            f"- **Energy**: {rc_metrics['total_energy_Wh']/1000:.2f} kWh",
            f"- **Comfort**: {rc_metrics['comfort_Kh']:.2f} K·h",
            f"- **Cost**: €{rc_metrics['cost_tot']:.4f}",
            f"- **MPC Solve Time**: {rc_metrics['solve_ms']:.3f} ms",
            "",
            "#### PINN Performance",
            "",
            f"- **Energy**: {pinn_metrics['total_energy_Wh']/1000:.2f} kWh",
            f"- **Comfort**: {pinn_metrics['comfort_Kh']:.2f} K·h",
            f"- **Cost**: €{pinn_metrics['cost_tot']:.4f}",
            f"- **MPC Solve Time**: {pinn_metrics['solve_ms']:.3f} ms",
            "",
            "#### Deltas (PINN minus Best RC)",
            "",
        ])
        
        energy_delta = case["delta_energy_Wh_pinn_minus_best_rc"]
        energy_pct = 100.0 * energy_delta / rc_metrics["total_energy_Wh"]
        cost_delta = case["delta_cost_tot_pinn_minus_best_rc"]
        comfort_delta = case["delta_comfort_Kh_pinn_minus_best_rc"]
        solve_delta = case["delta_solve_ms_pinn_minus_best_rc"]
        
        lines.extend([
            f"- **Energy**: {energy_delta:+.0f} Wh ({energy_pct:+.2f}%)",
            f"  - {'✓ PINN saves energy' if energy_delta < 0 else '✗ RC saves energy'}",
            f"- **Cost**: €{cost_delta:+.4f}",
            f"  - {'✓ PINN is cheaper' if cost_delta < 0 else '✗ RC is cheaper'}",
            f"- **Comfort**: {comfort_delta:+.2f} K·h",
            f"  - {'✓ PINN better comfort' if comfort_delta < 0 else '✗ RC better comfort'}",
            f"- **Solver Time**: {solve_delta:+.3f} ms",
            f"  - {'✓ PINN faster' if solve_delta < 0 else '✗ RC faster'} ({solve_delta/rc_metrics['solve_ms']*100:+.1f}% relative)",
            "",
        ])
    
    lines.extend([
        "## Methodology Notes",
        "",
        "- **Stage 1**: Screened 3 RC candidates (R3C2, R4C3, R5C3) on 7-day episodes",
        "- **Stage 2**: Ran best RC variant + PINN on 30-day episodes for robustness validation",
        "- **Scoring**: RC selection used weighted score: 10×cost + 2×comfort + 0.01×energy_kWh",
        "- **Episode**: All 30-day runs use scenario `te_std_01` (standard conditions)",
        "",
        "## Data Files",
        "",
        f"- Summary JSON: `results/eu_rc_vs_pinn_stage2/best_rc_vs_pinn_summary.json`",
        f"- Stage 1 (7-day PINN results): `results/eu_rc_vs_pinn/raw/[case]/pinn/`",
        f"- Stage 2 (30-day RC variants): `results/eu_rc_vs_pinn_stage2/raw/[case]/[variant]/`",
        f"- Stage 2 (30-day PINN results): `results/eu_rc_vs_pinn/raw/[case]/pinn/`",
        "",
    ])
    
    report_text = "\n".join(lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_text, encoding="utf-8")
    print(f"✓ Generated: {out_path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Stage 2 plots and report.")
    parser.add_argument("--summary", default="results/eu_rc_vs_pinn_stage2/best_rc_vs_pinn_summary.json")
    parser.add_argument("--out-plots", default="results/eu_rc_vs_pinn_stage2/publication_plots")
    parser.add_argument("--out-report", default="results/eu_rc_vs_pinn_stage2/STAGE2_SUMMARY_REPORT.md")
    args = parser.parse_args()
    
    summary_path = Path(args.summary)
    if not summary_path.exists():
        print(f"Error: Summary file not found: {summary_path}")
        return 1
    
    print(f"Loading summary from: {summary_path}")
    summary = load_summary(summary_path)
    
    n_cases = summary.get("n_cases", 0)
    print(f"Found {n_cases} cases in summary.")
    
    print("\n--- Generating Plots ---")
    generate_comparison_plots(summary, Path(args.out_plots))
    
    print("\n--- Generating Report ---")
    generate_markdown_report(summary, Path(args.out_report))
    
    print("\n✓ All outputs generated successfully!")
    return 0


if __name__ == "__main__":
    exit(main())
