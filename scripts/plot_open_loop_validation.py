import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

def generate_validation_plots(csv_path, output_dir):
    csv_path = Path(csv_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not csv_path.exists():
        print(f"Open-loop check file not found at: {csv_path}")
        return
        
    print(f"Generating publication validation plots from {csv_path.name}...")
    df = pd.read_csv(csv_path)
    
    # 1. Convert time_s to days
    t_start = df["time_s"].iloc[0]
    df["days"] = (df["time_s"] - t_start) / (24 * 3600)
    
    # Calculate residuals
    df["res_rc"] = df["t_open_loop_rc"] - df["t_actual"]
    df["res_pinn"] = df["t_open_loop_pinn"] - df["t_actual"]
    
    # Configure beautiful publication styling
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14,
        "grid.alpha": 0.3
    })
    
    # -------------------------------------------------------------------------
    # PLOT 1: Full 30-Day Open-Loop Rollout Trajectory Comparison
    # -------------------------------------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True, gridspec_kw={"height_ratios": [1, 2, 1]})
    
    # Ambient Weather Context (Top Panel)
    axes[0].plot(df["days"], df["t_outdoor"], label="Outdoor Temp", color="#7f8c8d", linewidth=1)
    axes[0].set_ylabel("Outdoor (°C)")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")
    axes[0].set_title("30-Day Open-Loop Trajectory Validation (BOPTEST Environment)")
    
    # Trajectories (Middle Panel)
    axes[1].plot(df["days"], df["t_actual"], label="Ground-Truth (BOPTEST)", color="#2c3e50", linewidth=1.8)
    axes[1].plot(df["days"], df["t_open_loop_rc"], label="Calibrated 1R1C RC", color="#e74c3c", linewidth=1.2, linestyle="--")
    axes[1].plot(df["days"], df["t_open_loop_pinn"], label="Physics-Guided NN", color="#27ae60", linewidth=1.2, linestyle="-.")
    axes[1].set_ylabel("Zone Temp (°C)")
    axes[1].grid(True)
    axes[1].legend(loc="lower left")
    
    # Residuals (Bottom Panel)
    axes[2].plot(df["days"], df["res_rc"], label="RC Residual", color="#e74c3c", linewidth=0.8, alpha=0.7)
    axes[2].plot(df["days"], df["res_pinn"], label="Physics-Guided NN Residual", color="#27ae60", linewidth=0.8, alpha=0.7)
    axes[2].axhline(0, color="black", linestyle=":", linewidth=1)
    axes[2].set_ylabel("Error (°C)")
    axes[2].set_xlabel("Time (Days)")
    axes[2].grid(True)
    axes[2].legend(loc="upper right")
    
    plt.tight_layout()
    plot1_path = output_dir / "open_loop_30d_comparison.png"
    plt.savefig(plot1_path, dpi=300)
    plt.close()
    print(f"  Saved -> {plot1_path.name}")
    
    # -------------------------------------------------------------------------
    # PLOT 2: Focused 7-Day Zoom Plot (Days 0 to 7) for detailed look
    # -------------------------------------------------------------------------
    zoom_df = df[df["days"] <= 7.0]
    
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True, gridspec_kw={"height_ratios": [1, 2, 1]})
    
    # Ambient Weather Context (Top Panel)
    axes[0].plot(zoom_df["days"], zoom_df["t_outdoor"], label="Outdoor Temp", color="#7f8c8d", linewidth=1.2)
    axes[0].set_ylabel("Outdoor (°C)")
    axes[0].grid(True)
    axes[0].legend(loc="upper right")
    axes[0].set_title("First 7 Days: Open-Loop Rollout Detail")
    
    # Trajectories (Middle Panel)
    axes[1].plot(zoom_df["days"], zoom_df["t_actual"], label="Ground-Truth (BOPTEST)", color="#2c3e50", linewidth=2.0)
    axes[1].plot(zoom_df["days"], zoom_df["t_open_loop_rc"], label="Calibrated 1R1C RC", color="#e74c3c", linewidth=1.5, linestyle="--")
    axes[1].plot(zoom_df["days"], zoom_df["t_open_loop_pinn"], label="Physics-Guided NN", color="#27ae60", linewidth=1.5, linestyle="-.")
    axes[1].set_ylabel("Zone Temp (°C)")
    axes[1].grid(True)
    axes[1].legend(loc="lower left")
    
    # Residuals (Bottom Panel)
    axes[2].plot(zoom_df["days"], zoom_df["res_rc"], label="RC Residual", color="#e74c3c", linewidth=1.0)
    axes[2].plot(zoom_df["days"], zoom_df["res_pinn"], label="PGNN Residual", color="#27ae60", linewidth=1.0)
    axes[2].axhline(0, color="black", linestyle=":", linewidth=1)
    axes[2].set_ylabel("Error (°C)")
    axes[2].set_xlabel("Time (Days)")
    axes[2].grid(True)
    axes[2].legend(loc="upper right")
    
    plt.tight_layout()
    plot2_path = output_dir / "open_loop_7d_zoom.png"
    plt.savefig(plot2_path, dpi=300)
    plt.close()
    print(f"  Saved -> {plot2_path.name}")
    
    # -------------------------------------------------------------------------
    # PLOT 3: Residual Distribution Histogram
    # -------------------------------------------------------------------------
    plt.figure(figsize=(7, 5))
    plt.hist(df["res_rc"], bins=50, alpha=0.5, label=f"RC Residuals (RMSE: {np.sqrt(np.mean(df['res_rc']**2)):.3f}°C)", color="#e74c3c", edgecolor="none")
    plt.hist(df["res_pinn"], bins=50, alpha=0.5, label=f"PGNN Residuals (RMSE: {np.sqrt(np.mean(df['res_pinn']**2)):.3f}°C)", color="#27ae60", edgecolor="none")
    plt.axvline(0, color="black", linestyle="--", linewidth=1)
    plt.xlabel("Prediction Error (°C)")
    plt.ylabel("Frequency (Steps)")
    plt.title("Error Distribution Over 30-Day Rollout")
    plt.legend(loc="upper right")
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plot3_path = output_dir / "open_loop_error_distribution.png"
    plt.savefig(plot3_path, dpi=300)
    plt.close()
    print(f"  Saved -> {plot3_path.name}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Plot open loop validation results.")
    parser.add_argument("--episode", default="te_exc_aut_rw", help="Episode stem name.")
    parser.add_argument("--output-dir", default="results/figures", help="Output directory for plots.")
    parser.add_argument("--results-dir", default="results/mpc_phase1", help="Directory containing results.")
    args = parser.parse_args()

    csv_path = Path(args.results_dir)
    if not csv_path.is_absolute():
        csv_path = BASE / csv_path
    csv_file = csv_path / f"open_loop_{args.episode}_check.csv"
    
    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = BASE / out_dir

    generate_validation_plots(csv_file, out_dir)
    print("Validation plotting complete!")
