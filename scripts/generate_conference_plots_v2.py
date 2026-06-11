#!/usr/bin/env python3
"""
Generate publication-ready plots for the BSA 2026 conference paper.
v2: Uses identical-objective run (eu_rc_vs_pinn_stage2_identical).

Plots:
  1. Temperature trajectories (3-panel: full episode + 3-day zoom + comfort histogram)
  2. Control power trajectories (full episode with rolling mean overlay)
  3. Cumulative cost comparison
  4. KPI comparison bar chart (cost, comfort_Kh, solve time)
"""

import json
import argparse
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

# ── house style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "grid.color": "#e0e0e0",
    "grid.linestyle": "-",
    "grid.linewidth": 0.6,
    "figure.dpi": 150,
})

C_RC   = "#d62728"   # red  – RC baseline
C_PINN = "#1f77b4"   # blue – Physics-guided NN
C_RBC  = "#2ca02c"   # green – RBC thermostat
C_BAND = "#aec6cf"   # comfort-band fill

LABEL_RC   = "RC Baseline"
LABEL_PINN = "Physics-guided NN"
LABEL_RBC  = "RBC Thermostat"

# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)

def extract_ts(results: dict) -> dict:
    """Extract aligned time-series arrays from a step_records result file."""
    recs = results["step_records"]
    times_s  = np.array([r["time_s"] for r in recs])
    t_zone   = np.array([r["t_zone"] for r in recs])
    t_out    = np.array([r.get("t_out", np.nan) for r in recs])
    t_lower  = np.array([r.get("t_lower", 21.0) for r in recs])
    t_upper  = np.array([r.get("t_upper", 24.0) for r in recs])
    power_w  = np.array([r.get("power_heating_w", r.get("power_w", 0)) for r in recs])

    # Normalise time to hours from episode start
    t_h = (times_s - times_s[0]) / 3600.0
    dt_h = results["control_interval_s"] / 3600.0

    # Cumulative cost – preserve temporal shape, scale to official end-KPI
    price = 0.15         # €/kWh
    cost_step = (power_w / 1000.0) * dt_h * price   # €/m² already (BOPTEST normalises)
    cum_proxy = np.cumsum(cost_step)
    official  = results["kpi_summary"]["cost_tot"]["value"]
    scale     = official / max(cum_proxy[-1], 1e-12)
    cum_cost  = cum_proxy * scale

    return dict(t_h=t_h, t_zone=t_zone, t_out=t_out,
                t_lower=t_lower, t_upper=t_upper,
                power_w=power_w, cum_cost=cum_cost, dt_h=dt_h)

# ─── Plot 1: Temperature overview (3-panel) ──────────────────────────────────

def plot_temperature(rc: dict, pinn: dict, episode_stem: str, out: Path,
                     rbc: dict | None = None):
    """
    3-panel figure:
      Top:    Full 30-day temperature traces
      Bottom-left:  3-day detail zoom (first 72 h)
      Bottom-right: Comfort-violation histogram
    Optional rbc dict adds a third (green) thermostat baseline.
    """
    fig = plt.figure(figsize=(16, 9))
    gs  = gridspec.GridSpec(2, 2, figure=fig, height_ratios=[1.4, 1],
                            hspace=0.38, wspace=0.32)
    ax_full  = fig.add_subplot(gs[0, :])
    ax_zoom  = fig.add_subplot(gs[1, 0])
    ax_hist  = fig.add_subplot(gs[1, 1])

    t = rc["t_h"]

    # ── Full episode ──────────────────────────────────────────────────────
    ax_full.fill_between(t, rc["t_lower"], rc["t_upper"],
                         color=C_BAND, alpha=0.35, label="Comfort band (occ.)")
    if rbc is not None:
        ax_full.plot(rbc["t_h"], rbc["t_zone"],
                     color=C_RBC, lw=1.0, alpha=0.80, label=LABEL_RBC, ls="--")
    ax_full.plot(pinn["t_h"], pinn["t_zone"],
                 color=C_PINN, lw=1.2, alpha=0.85, label=LABEL_PINN)
    ax_full.plot(t, rc["t_zone"],
                 color=C_RC, lw=1.2, alpha=0.85, label=LABEL_RC)

    ax_full.set_xlabel("Time (hours)", labelpad=4)
    ax_full.set_ylabel("Zone Temperature (°C)")
    ax_full.set_title(f"Closed-Loop Zone Temperature — 30-Day Episode ({episode_stem})")
    ax_full.legend(loc="lower right", fontsize=10, framealpha=0.9)
    ax_full.set_ylim(16, 28)
    ax_full.set_xlim(0, t[-1])
    day_ticks = np.arange(0, t[-1] + 1, 24 * 5)   # every 5 days
    ax_full.set_xticks(day_ticks)
    ax_full.set_xticklabels([f"Day {int(x/24)}" for x in day_ticks], fontsize=9)
    ax_full.grid(True)

    # ── 3-day zoom ───────────────────────────────────────────────────────
    mask = t <= 72
    pm   = pinn["t_h"] <= 72
    ax_zoom.fill_between(t[mask], rc["t_lower"][mask], rc["t_upper"][mask],
                         color=C_BAND, alpha=0.35)
    if rbc is not None:
        rm = rbc["t_h"] <= 72
        ax_zoom.plot(rbc["t_h"][rm], rbc["t_zone"][rm],
                     color=C_RBC, lw=1.3, label=LABEL_RBC, ls="--")
    ax_zoom.plot(pinn["t_h"][pm], pinn["t_zone"][pm], color=C_PINN, lw=1.5, label=LABEL_PINN)
    ax_zoom.plot(t[mask], rc["t_zone"][mask], color=C_RC, lw=1.5, label=LABEL_RC)
    ax_zoom.set_xlabel("Time (hours)")
    ax_zoom.set_ylabel("Zone Temperature (°C)")
    ax_zoom.set_title("First 3 Days — Detail View")
    ax_zoom.legend(fontsize=9, framealpha=0.9)
    ax_zoom.set_ylim(16, 28)
    ax_zoom.grid(True)

    # ── Histogram of temperature deviations from comfort centre ───────────
    centre = (rc["t_lower"].mean() + rc["t_upper"].mean()) / 2
    dev_rc   = rc["t_zone"]   - centre
    dev_pinn = pinn["t_zone"] - centre
    bins = np.linspace(-5, 5, 30)
    if rbc is not None:
        dev_rbc = rbc["t_zone"] - centre
        ax_hist.hist(dev_rbc,  bins=bins, color=C_RBC,  alpha=0.45, label=LABEL_RBC,  density=True)
    ax_hist.hist(dev_rc,   bins=bins, color=C_RC,   alpha=0.50, label=LABEL_RC,   density=True)
    ax_hist.hist(dev_pinn, bins=bins, color=C_PINN, alpha=0.50, label=LABEL_PINN, density=True)
    ax_hist.axvline(0, color="gray", lw=0.8, ls="--")
    half = (rc["t_upper"].mean() - rc["t_lower"].mean()) / 2
    ax_hist.axvspan(-half, half, color=C_BAND, alpha=0.25, label="Comfort band")
    ax_hist.set_xlabel("Deviation from set-point centre (°C)")
    ax_hist.set_ylabel("Probability density")
    ax_hist.set_title("Temperature Distribution")
    ax_hist.legend(fontsize=9, framealpha=0.9)
    ax_hist.grid(True)

    fig.suptitle("Figure 1  ·  Thermal Performance Comparison", fontsize=13,
                 fontweight="bold", y=0.99)
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[OK] Saved: {out}")


# ─── Plot 2: Control effort ───────────────────────────────────────────────────

def plot_control(rc: dict, pinn: dict, out: Path, rbc: dict | None = None):
    """
    2-panel figure:
      Top:    Full heating-power trajectories (downsampled) + 24-h rolling mean
      Bottom: Scatter: PGNN power vs RC power (step-by-step correlation)
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [2, 1]},
                             constrained_layout=True)
    ax_traj, ax_scat = axes

    t   = rc["t_h"]
    prc = rc["power_w"] / 1000      # → kW
    ppinn = pinn["power_w"] / 1000

    stride = max(len(t) // 1440, 1)
    # rolling 24-h mean (96 steps at 15 min)
    win = 96
    def roll_mean(x):
        return np.convolve(x, np.ones(win)/win, mode="same")

    if rbc is not None:
        prbc = rbc["power_w"] / 1000
        ax_traj.plot(t[::stride], prbc[::stride],  color=C_RBC,  lw=0.8, alpha=0.35, ls="--")

    ax_traj.plot(t[::stride], prc[::stride],    color=C_RC,   lw=0.9, alpha=0.5)
    ax_traj.plot(t[::stride], ppinn[::stride],  color=C_PINN, lw=0.9, alpha=0.5)

    if rbc is not None:
        ax_traj.plot(t, roll_mean(prbc), color=C_RBC, lw=1.8, label=f"{LABEL_RBC} (24-h mean)", ls="--")
    ax_traj.plot(t, roll_mean(prc),   color=C_RC,   lw=2.0, label=f"{LABEL_RC} (24-h mean)")
    ax_traj.plot(t, roll_mean(ppinn), color=C_PINN, lw=2.0, label=f"{LABEL_PINN} (24-h mean)")

    ax_traj.set_ylabel("Heating Power (kW)")
    ax_traj.set_title("Figure 2  ·  Control Effort — Heating Power Over Episode")
    day_ticks = np.arange(0, t[-1] + 1, 24 * 5)
    ax_traj.set_xticks(day_ticks)
    ax_traj.set_xticklabels([f"Day {int(x/24)}" for x in day_ticks], fontsize=9)
    ax_traj.set_xlabel("Time (hours)")
    ax_traj.legend(fontsize=10, framealpha=0.9)
    ax_traj.grid(True)
    ax_traj.set_xlim(0, t[-1])

    # Scatter: step-by-step power correlation
    # Sub-sample to keep scatter readable
    ss = max(len(prc) // 500, 1)
    ax_scat.scatter(prc[::ss], ppinn[::ss], s=8, alpha=0.4, color="#555555")
    diag_max = max(prc.max(), ppinn.max()) * 1.05
    ax_scat.plot([0, diag_max], [0, diag_max], "k--", lw=1, label="1:1 line")
    ax_scat.set_xlabel(f"RC Power (kW)")
    ax_scat.set_ylabel(f"PGNN Power (kW)")
    ax_scat.set_title("Step-by-Step Power Correlation (RC vs PGNN)")
    ax_scat.legend(fontsize=9)
    ax_scat.grid(True)
    ax_scat.set_aspect("equal", adjustable="box")

    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[OK] Saved: {out}")


# ─── Plot 3: Cumulative cost ──────────────────────────────────────────────────

def plot_cumulative_cost(rc: dict, pinn: dict, episode_stem: str, out: Path,
                         rbc: dict | None = None):
    fig, ax = plt.subplots(figsize=(12, 5))

    t = rc["t_h"]
    if rbc is not None:
        ax.plot(rbc["t_h"], rbc["cum_cost"], color=C_RBC, lw=2.0, label=LABEL_RBC, ls="--")
    ax.plot(t, pinn["cum_cost"], color=C_PINN, lw=2.2, label=LABEL_PINN)
    ax.plot(t, rc["cum_cost"],   color=C_RC,   lw=2.2, label=LABEL_RC)

    final_rc   = rc["cum_cost"][-1]
    final_pinn = pinn["cum_cost"][-1]

    use_rbc = rbc is not None
    if use_rbc:
        final_rbc = rbc["cum_cost"][-1]
        # PGNN vs RBC
        chg_pinn = (final_pinn / final_rbc - 1) * 100
        sign_pinn = "+" if chg_pinn >= 0 else ""
        lbl_pinn = f"({sign_pinn}{chg_pinn:.1f}% vs RBC)"

        # RC vs RBC
        chg_rc = (final_rc / final_rbc - 1) * 100
        sign_rc = "+" if chg_rc >= 0 else ""
        lbl_rc = f"({sign_rc}{chg_rc:.1f}% vs RBC)"
    else:
        reduction  = (1 - final_pinn / final_rc) * 100 if final_rc > 0 else 0
        lbl_pinn = f"(-{reduction:.1f}% vs RC)"
        lbl_rc = ""

    ax.annotate(f"\u20ac{final_rc:.4f}/m\u00b2" + (f"\n{lbl_rc}" if use_rbc else ""),
                xy=(t[-1], final_rc), xytext=(-90, 15),
                textcoords="offset points", fontsize=10,
                arrowprops=dict(arrowstyle="->", color=C_RC),
                color=C_RC, fontweight="bold")
    ax.annotate(f"\u20ac{final_pinn:.4f}/m\u00b2\n{lbl_pinn}",
                xy=(t[-1], final_pinn), xytext=(-150, -35),
                textcoords="offset points", fontsize=10,
                arrowprops=dict(arrowstyle="->", color=C_PINN),
                color=C_PINN, fontweight="bold")
    if use_rbc:
        ax.annotate(f"\u20ac{final_rbc:.4f}/m\u00b2",
                    xy=(rbc["t_h"][-1], final_rbc), xytext=(-160, 5),
                    textcoords="offset points", fontsize=10,
                    arrowprops=dict(arrowstyle="->", color=C_RBC),
                    color=C_RBC, fontweight="bold")

    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Cumulative Cost (EUR/m\u00b2)")
    ax.set_title(f"Figure 3  \u00b7  Operational Cost Accumulation \u2014 30-Day Episode ({episode_stem})")
    ax.legend(fontsize=11, framealpha=0.9)
    day_ticks = np.arange(0, t[-1] + 1, 24 * 5)
    ax.set_xticks(day_ticks)
    ax.set_xticklabels([f"Day {int(x/24)}" for x in day_ticks], fontsize=9)
    ax.set_xlim(0, t[-1])
    ax.grid(True)

    plt.tight_layout()
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[OK] Saved: {out}")


# ─── Plot 4: KPI summary bar chart ───────────────────────────────────────────

def plot_kpi_bar(rc_full: dict, pinn_full: dict, episode_stem: str, out: Path,
                 rbc_full: dict | None = None):
    """
    4-panel bar chart: operational cost, comfort_Kh, solve time (log scale), energy.
    Supports 2-controller (RC vs PINN) or 3-controller (+ RBC) comparison.
    """
    def safe_get(d, k1, k2, default=0.0):
        try:
            return d[k1][k2]
        except KeyError:
            return default

    def safe_get_val(d, k1, k2, default=0.0):
        try:
            return d[k1][k2]["value"]
        except KeyError:
            return default

    ck_rc   = safe_get(rc_full,   "diagnostic_kpis", "comfort_Kh")
    ck_pinn = safe_get(pinn_full, "diagnostic_kpis", "comfort_Kh")
    cost_rc   = safe_get_val(rc_full,   "challenge_kpis", "cost_tot")
    cost_pinn = safe_get_val(pinn_full, "challenge_kpis", "cost_tot")
    eng_rc    = safe_get(rc_full,   "diagnostic_kpis", "total_energy_Wh") / 1000
    eng_pinn  = safe_get(pinn_full, "diagnostic_kpis", "total_energy_Wh") / 1000
    ms_rc     = safe_get(rc_full,   "diagnostic_kpis", "mpc_solve_time_mean_ms")
    ms_pinn   = safe_get(pinn_full, "diagnostic_kpis", "mpc_solve_time_mean_ms")

    use_rbc = rbc_full is not None
    if use_rbc:
        ck_rbc   = safe_get(rbc_full, "diagnostic_kpis", "comfort_Kh")
        cost_rbc = safe_get_val(rbc_full, "challenge_kpis", "cost_tot")
        eng_rbc  = safe_get(rbc_full, "diagnostic_kpis", "total_energy_Wh") / 1000
        ms_rbc   = 0.0  # RBC has no solve time

    panels = [
        ("Operational Cost\n(EUR/m\u00b2)",
         [cost_rc, cost_pinn] + ([cost_rbc] if use_rbc else []), False, ".4f"),
        ("Comfort Integral\n(K\u00b7h/zone)",
         [ck_rc,   ck_pinn]   + ([ck_rbc]   if use_rbc else []), False, ".2f"),
        ("Mean MPC Solve Time\n(ms, log scale)",
         [ms_rc,   ms_pinn]   + ([ms_rbc+0.001] if use_rbc else []), True,  ".1f"),
        ("Total HVAC Energy\n(kWh)",
         [eng_rc,  eng_pinn]  + ([eng_rbc]  if use_rbc else []), False, ".0f"),
    ]

    all_labels = [LABEL_RC, LABEL_PINN] + ([LABEL_RBC] if use_rbc else [])
    all_colors = [C_RC,     C_PINN]     + ([C_RBC]     if use_rbc else [])
    n_ctrl = len(all_labels)
    bar_w  = 0.55 if n_ctrl == 2 else 0.45
    x_pos  = list(range(n_ctrl))

    fig, axes = plt.subplots(1, 4, figsize=(16, 5), constrained_layout=True)

    for ax, (ylabel, vals, use_log, fmt) in zip(axes, panels):
        bars = ax.bar(x_pos, vals, color=all_colors, alpha=0.85,
                      edgecolor="white", linewidth=1.5, width=bar_w)
        for bar, v in zip(bars, vals):
            label_val = v if not use_log else max(v, 1e-3)
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * (1.02 if not use_log else 1.5),
                    format(label_val, fmt),
                    ha="center", va="bottom", fontsize=9, fontweight="bold")

        if use_log:
            ax.set_yscale("log")

        # Improvement comparison
        if use_rbc and ylabel != "Mean MPC Solve Time\n(ms, log scale)":
            v_base = vals[2] # RBC is index 2
            base_lbl = "RBC"
        else:
            v_base = vals[0] # RC is index 0
            base_lbl = "RC"

        v_pinn = vals[1]
        if v_base > 0:
            imp = (1 - v_pinn / v_base) * 100
        else:
            imp = 0.0

        if imp >= 0:
            sign = "\u25bc"
            color = "#2ca02c"
            lbl = f"{sign}{abs(imp):.1f}% (PGNN vs {base_lbl})"
        else:
            sign = "\u25b2"
            color = "#d62728"
            lbl = f"{sign}{abs(imp):.1f}% (PGNN vs {base_lbl})"

        ax.text(0.5, 0.92, lbl,
                transform=ax.transAxes, ha="center", fontsize=9, fontweight="bold",
                color=color,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                          edgecolor="#cccccc", alpha=0.8))
        ax.set_ylabel(ylabel, labelpad=4)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(all_labels, fontsize=8 if n_ctrl == 3 else 9)
        ax.grid(True, axis="y", alpha=0.5)
        ax.set_axisbelow(True)

    fig.suptitle(
        f"Figure 4  \u00b7  KPI Comparison (singlezone_commercial_hydronic, {episode_stem})",
        fontsize=12, fontweight="bold")

    legend_elements = [Patch(facecolor=c, label=l, alpha=0.85)
                       for c, l in zip(all_colors, all_labels)]
    fig.legend(handles=legend_elements, loc="lower center",
               ncol=n_ctrl, fontsize=10,
               bbox_to_anchor=(0.5, -0.03), framealpha=0.9)

    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[OK] Saved: {out}")


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Generate BSA-2026 paper plots (v2, identical objectives).")
    ap.add_argument("--episode-stem", default="te_exc_aut_rw")
    ap.add_argument("--rc-json",   default=None)
    ap.add_argument("--pinn-json", default=None)
    ap.add_argument("--rbc-json",  default=None,
                    help="Optional path to RBC result JSON for three-way comparison.")
    ap.add_argument("--rc-live",   default=None)
    ap.add_argument("--pinn-live", default=None)
    ap.add_argument("--output-dir", default="results/figures")
    args = ap.parse_args()

    rc_json   = args.rc_json   or f"results/mpc_phase1/rc/{args.episode_stem}.json"
    pinn_json = args.pinn_json or f"results/mpc_phase1/pinn/{args.episode_stem}.json"
    rc_live   = args.rc_live   or f"results/mpc_phase1/rc/{args.episode_stem}.live.json"
    pinn_live = args.pinn_live or f"results/mpc_phase1/pinn/{args.episode_stem}.live.json"
    # RBC result lives in rbc/rbc/ subdirectory (predictor-label subdir from runner)
    rbc_json  = args.rbc_json  or f"results/mpc_phase1/rbc/rbc/{args.episode_stem}.json"

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading results ...")
    rc_full   = load_json(Path(rc_json))
    pinn_full = load_json(Path(pinn_json))

    rbc_full = None
    rbc_ts   = None
    rbc_path = Path(rbc_json)
    if rbc_path.exists():
        print(f"Loading RBC baseline from {rbc_path} ...")
        rbc_full = load_json(rbc_path)
        rbc_ts   = extract_ts(rbc_full)
    else:
        print(f"[INFO] RBC result not found at {rbc_path} — plotting without RBC baseline.")

    print("Extracting time series ...")
    rc_ts   = extract_ts(rc_full)
    pinn_ts = extract_ts(pinn_full)

    print("\nGenerating plots ...")
    plot_temperature(rc_ts, pinn_ts, args.episode_stem,
                     out_dir / "closed_loop_temperature2.png", rbc=rbc_ts)
    plot_control(rc_ts, pinn_ts, out_dir / "closed_loop_control_effort2.png", rbc=rbc_ts)
    plot_cumulative_cost(rc_ts, pinn_ts, args.episode_stem,
                         out_dir / "closed_loop_cumulative_cost2.png", rbc=rbc_ts)
    plot_kpi_bar(rc_full, pinn_full, args.episode_stem,
                 out_dir / "kpi_comparison_bar2.png", rbc_full=rbc_full)

    print(f"\n[OK] All 4 figures written to {out_dir}/")


if __name__ == "__main__":
    main()
