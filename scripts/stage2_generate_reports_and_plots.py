#!/usr/bin/env python3
"""
Generate publication-ready plots and reports from Stage 2 RC variant vs PINN summary.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def load_summary(path: Path) -> dict[str, Any]:
    """Load the best_rc_vs_pinn_summary.json."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    """Load an arbitrary JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_stage2_rc_variant(variant: str) -> str:
    """Map summary variant names to stage2 raw folder names."""
    variant_map = {
        "rc": "rc_base",
        "rc_base": "rc_base",
        "rc_envelope_plus": "rc_envelope_plus",
        "rc_mass_plus": "rc_mass_plus",
    }
    return variant_map.get(variant, variant)


def _find_episode_file(root: Path, episode: str) -> Path | None:
    """Find an episode JSON file, allowing for nested output folders."""
    direct = root / f"{episode}.json"
    if direct.exists():
        return direct
    matches = sorted(root.rglob(f"{episode}.json"))
    return matches[0] if matches else None


def compute_cumulative_metrics(step_records: list[dict[str, Any]], dt_s: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute cumulative energy [kWh] and discomfort [K.h] over time in days."""
    n = len(step_records)
    time_days = np.arange(1, n + 1) * (dt_s / 86400.0)

    power_w = np.array([float(r.get("power_w", 0.0)) for r in step_records], dtype=float)
    energy_step_kwh = power_w * (dt_s / 3600.0) / 1000.0
    cum_energy_kwh = np.cumsum(energy_step_kwh)

    t_zone = np.array([float(r.get("t_zone", 0.0)) for r in step_records], dtype=float)
    t_lower = np.array([float(r.get("t_lower", 0.0)) for r in step_records], dtype=float)
    t_upper = np.array([float(r.get("t_upper", 0.0)) for r in step_records], dtype=float)
    discomfort_step = np.maximum(0.0, t_lower - t_zone) + np.maximum(0.0, t_zone - t_upper)
    discomfort_step_kh = discomfort_step * (dt_s / 3600.0)
    cum_discomfort_kh = np.cumsum(discomfort_step_kh)

    return time_days, cum_energy_kwh, cum_discomfort_kh


def generate_training_convergence_plot(repo_root: Path, out_dir: Path) -> None:
    """Plot train/val loss and RMSE convergence for all PINN case models."""
    case_to_config = {
        "bestest_hydronic": "pinn_bestest_hydronic.yaml",
        "bestest_hydronic_heat_pump": "pinn_bestest_hydronic_heat_pump.yaml",
        "singlezone_commercial_hydronic": "pinn_singlezone_commercial_hydronic.yaml",
        "twozone_apartment_hydronic": "pinn_twozone_apartment_hydronic.yaml",
    }
    case_names = list(case_to_config.keys())

    # Use a common x-axis limit so epoch ranges are visually comparable.
    max_config_epochs = 0
    for case, cfg_name in case_to_config.items():
        cfg_path = repo_root / "configs" / "eu" / cfg_name
        if not cfg_path.exists():
            continue
        cfg_text = cfg_path.read_text(encoding="utf-8")
        for line in cfg_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("epochs:"):
                try:
                    max_config_epochs = max(max_config_epochs, int(stripped.split(":", 1)[1].strip()))
                except ValueError:
                    pass
                break
    if max_config_epochs <= 0:
        max_config_epochs = 80

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
    axes = axes.ravel()

    for i, case in enumerate(case_names):
        history_path = repo_root / "artifacts" / "eu" / case / "history.json"
        ax = axes[i]
        if not history_path.exists():
            ax.set_title(f"{case} (history missing)")
            ax.axis("off")
            continue

        history = load_json(history_path)
        epochs = np.array([float(h.get("epoch", 0.0)) for h in history], dtype=float)
        train_loss = np.array([float(h.get("train_loss", np.nan)) for h in history], dtype=float)
        val_loss = np.array([float(h.get("val_loss", np.nan)) for h in history], dtype=float)
        train_rmse = np.array([float(h.get("train_rmse_degC", np.nan)) for h in history], dtype=float)
        val_rmse = np.array([float(h.get("val_rmse_degC", np.nan)) for h in history], dtype=float)

        ax.plot(epochs, train_loss, label="Train loss", color="tab:blue", linewidth=1.6)
        ax.plot(epochs, val_loss, label="Val loss", color="tab:orange", linewidth=1.6)
        last_epoch = int(epochs[-1]) if len(epochs) > 0 else 0
        ax.axvline(last_epoch, color="black", linestyle=":", linewidth=0.9, alpha=0.7)
        ax.set_title(case)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Loss")
        ax.set_xlim(1, max_config_epochs)
        ax.grid(alpha=0.25)

        ax2 = ax.twinx()
        ax2.plot(epochs, train_rmse, label="Train RMSE", color="tab:green", linestyle="--", linewidth=1.3)
        ax2.plot(epochs, val_rmse, label="Val RMSE", color="tab:red", linestyle="--", linewidth=1.3)
        ax2.set_ylabel("RMSE [degC]")

        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, fontsize=8, loc="upper right")
        ax.text(
            0.02,
            0.04,
            f"stop epoch: {last_epoch}",
            transform=ax.transAxes,
            fontsize=8,
            bbox={"facecolor": "white", "alpha": 0.6, "edgecolor": "none"},
        )

    fig.suptitle("PINN Training Convergence by Case (Common Epoch Axis)", fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(out_dir / "06_pinn_training_convergence_by_case.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("✓ Generated: 06_pinn_training_convergence_by_case.png")


def generate_cumulative_performance_plot(summary: dict[str, Any], repo_root: Path, out_dir: Path) -> None:
    """Plot cumulative energy and discomfort trajectories (RC vs PINN) over 30 days."""
    cases_data = summary.get("cases", [])
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
    axes = axes.ravel()

    for i, case_data in enumerate(cases_data):
        case = case_data["case"]
        rc_variant = _resolve_stage2_rc_variant(case_data["best_rc_variant"])
        episode = case_data.get("episode", "te_std_01")

        rc_path = repo_root / "results" / "eu_rc_vs_pinn_stage2" / "raw" / case / rc_variant / f"{episode}.json"
        pinn_path = _find_episode_file(repo_root / "results" / "eu_rc_vs_pinn_stage2" / "raw" / case / "pinn", episode)

        ax = axes[i]
        if not rc_path.exists() or pinn_path is None:
            ax.set_title(f"{case} (trajectory missing)")
            ax.axis("off")
            continue

        rc_ep = load_json(rc_path)
        pinn_ep = load_json(pinn_path)

        dt_rc = int(rc_ep.get("control_interval_s", 900))
        dt_pinn = int(pinn_ep.get("control_interval_s", 900))
        t_rc, e_rc, d_rc = compute_cumulative_metrics(rc_ep["step_records"], dt_rc)
        t_p, e_p, d_p = compute_cumulative_metrics(pinn_ep["step_records"], dt_pinn)

        ax.plot(t_rc, e_rc, color="tab:blue", linewidth=1.8, label="RC cum. energy")
        ax.plot(t_p, e_p, color="tab:orange", linewidth=1.8, label="PINN cum. energy")
        ax.set_title(case)
        ax.set_xlabel("Day")
        ax.set_ylabel("Cumulative energy [kWh]")
        ax.grid(alpha=0.25)

        ax2 = ax.twinx()
        ax2.plot(t_rc, d_rc, color="tab:blue", linestyle="--", linewidth=1.3, label="RC cum. discomfort")
        ax2.plot(t_p, d_p, color="tab:orange", linestyle="--", linewidth=1.3, label="PINN cum. discomfort")
        ax2.set_ylabel("Cumulative discomfort [K.h]")

        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, fontsize=8, loc="upper left")

    fig.suptitle("30-day Cumulative Performance Trajectories (RC vs PINN)", fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(out_dir / "07_stage2_cumulative_energy_discomfort_trajectories.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("✓ Generated: 07_stage2_cumulative_energy_discomfort_trajectories.png")


def generate_all_cases_dynamics_plot(summary: dict[str, Any], repo_root: Path, out_dir: Path) -> None:
    """All-cases 30-day thermal dynamics: zone temperature vs comfort bounds."""
    cases_data = summary.get("cases", [])
    if not cases_data:
        return

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True, sharey=False)
    axes = axes.ravel()

    for i, case_data in enumerate(cases_data):
        case = case_data["case"]
        rc_variant = _resolve_stage2_rc_variant(case_data["best_rc_variant"])
        episode = case_data.get("episode", "te_std_01")

        rc_path = repo_root / "results" / "eu_rc_vs_pinn_stage2" / "raw" / case / rc_variant / f"{episode}.json"
        pinn_path = _find_episode_file(repo_root / "results" / "eu_rc_vs_pinn_stage2" / "raw" / case / "pinn", episode)

        ax = axes[i]
        if not rc_path.exists() or pinn_path is None:
            ax.set_title(f"{case} (data missing)")
            ax.axis("off")
            continue

        rc_ep = load_json(rc_path)
        pinn_ep = load_json(pinn_path)
        dt = int(rc_ep.get("control_interval_s", 900))

        rc_steps = rc_ep["step_records"]
        pinn_steps = pinn_ep["step_records"]
        n = min(len(rc_steps), len(pinn_steps))
        t_days = np.arange(1, n + 1) * (dt / 86400.0)

        rc_t = np.array([float(r.get("t_zone", 0.0)) for r in rc_steps[:n]], dtype=float)
        pinn_t = np.array([float(r.get("t_zone", 0.0)) for r in pinn_steps[:n]], dtype=float)
        t_lower = np.array([float(r.get("t_lower", 0.0)) for r in rc_steps[:n]], dtype=float)
        t_upper = np.array([float(r.get("t_upper", 0.0)) for r in rc_steps[:n]], dtype=float)

        ax.plot(t_days, rc_t, color="tab:blue", linewidth=1.2, label="RC")
        ax.plot(t_days, pinn_t, color="tab:orange", linewidth=1.2, label="PINN")
        ax.plot(t_days, t_lower, color="gray", linestyle="--", linewidth=0.9, label="Lower bound")
        ax.plot(t_days, t_upper, color="gray", linestyle=":", linewidth=0.9, label="Upper bound")
        ax.set_title(case)
        ax.set_xlabel("Day")
        ax.set_ylabel("Zone temp [degC]")
        ax.grid(alpha=0.25)

        if i == 0:
            ax.legend(ncol=4, fontsize=8, loc="upper right")

    fig.suptitle("30-day Thermal Dynamics by Case (RC vs PINN)", fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(out_dir / "08_all_cases_30day_temperature_dynamics.png", dpi=300, bbox_inches="tight")
    plt.close()
    print("✓ Generated: 08_all_cases_30day_temperature_dynamics.png")


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
    
    generated_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    generated_date = datetime.now().strftime("%B %d, %Y")

    lines = [
        "# Stage 2: RC Variant Selection & PINN Comparison Report",
        "",
        f"**Generated**: {generated_ts}",
        f"**Episode**: {episode}",
        f"**Date**: {generated_date}",
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
        f"- Stage 2 (30-day PINN results): `results/eu_rc_vs_pinn_stage2/raw/[case]/pinn/`",
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
    parser.add_argument(
        "--include-comparison-plots",
        action="store_true",
        help="Also generate bar-chart comparison plots 01-05 (tables already cover these in the manuscript).",
    )
    args = parser.parse_args()
    
    summary_path = Path(args.summary)
    if not summary_path.exists():
        print(f"Error: Summary file not found: {summary_path}")
        return 1
    
    print(f"Loading summary from: {summary_path}")
    summary = load_summary(summary_path)
    
    n_cases = summary.get("n_cases", 0)
    print(f"Found {n_cases} cases in summary.")
    
    out_plots = Path(args.out_plots)
    if args.include_comparison_plots:
        print("\n--- Generating Comparison Plots (01-05) ---")
        generate_comparison_plots(summary, out_plots)

    repo_root = Path(__file__).resolve().parents[1]
    print("\n--- Generating Core Publication Plots (06-08) ---")
    generate_training_convergence_plot(repo_root, out_plots)
    generate_cumulative_performance_plot(summary, repo_root, out_plots)
    generate_all_cases_dynamics_plot(summary, repo_root, out_plots)
    
    print("\n--- Generating Report ---")
    generate_markdown_report(summary, Path(args.out_report))
    
    print("\n✓ All outputs generated successfully!")
    return 0


if __name__ == "__main__":
    exit(main())
