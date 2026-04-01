#!/usr/bin/env python3
import json
from pathlib import Path
import math

ROOT = Path("results/mpc_tuning_eval/autotune_v1_10cand/full_validation")
SUMMARY = ROOT / "summary_full_validation.json"
OUT = ROOT / "execution_report_fixed.md"
BASELINE_ROOT = Path("results/mpc_tuning_eval/baseline")
CONTROLLERS = ["rc", "pinn", "rbc"]

if not SUMMARY.exists():
    print(f"Summary JSON not found: {SUMMARY}")
    raise SystemExit(1)

summary_raw = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
summary = {k: v for k, v in summary_raw.items() if k.startswith("cand_") and isinstance(v, dict)}

# collect episodes
episodes = set()
for cand, cd in summary.items():
    for ep in cd.get("episodes", {}).keys():
        episodes.add(ep)
episodes = sorted(episodes)

lines = []
lines.append(f"# Full validation report (generated from summary_full_validation.json)")
lines.append("")
lines.append("## Candidates checked")
for cand in sorted(summary.keys()):
    lines.append(f"- {cand}")
lines.append("")
lines.append("## Baseline sources")
for c in CONTROLLERS:
    p = BASELINE_ROOT / c
    lines.append(f"- {c}: {p}")
lines.append("")

lines.append("## Results by Controller/Episode")
lines.append("| Controller | Episode | baseline | candidate | delta % (candidate vs baseline) |")
lines.append("|---|---|---|---|---:|")

def get_vals_from_payload(payload):
    if not payload:
        return None
    b = payload.get("challenge_kpis", {})
    d = payload.get("diagnostic_kpis", {})
    def gv(key, src):
        x = src.get(key)
        if isinstance(x, dict):
            return x.get("value")
        return x
    return {
        "cost_tot": gv("cost_tot", b),
        "tdis_tot": gv("tdis_tot", b),
        "solve_ms": d.get("mpc_solve_time_mean_ms"),
    }

for ctrl in CONTROLLERS:
    for ep in episodes:
        # baseline
        bp = BASELINE_ROOT / ctrl / f"{ep}.json"
        baseline_vals = None
        if bp.exists():
            try:
                payload = json.loads(bp.read_text(encoding="utf-8-sig"))
                baseline_vals = get_vals_from_payload(payload)
            except Exception:
                baseline_vals = None
        # candidate - aggregated JSON has per-episode per-controller values
        # find first candidate that contains an entry for this ctrl/ep (we'll print per-candidate afterwards)
        # but here we'll print one row per controller/episode per candidate
        for cand in sorted(summary.keys()):
            cand_ep_map = summary[cand].get("episodes", {})
            cand_ctrl = cand_ep_map.get(ep, {}).get(ctrl)
            if cand_ctrl:
                cand_vals = {
                    "cost_tot": cand_ctrl.get("cost_tot"),
                    "tdis_tot": cand_ctrl.get("tdis_tot"),
                    "solve_ms": cand_ctrl.get("mpc_solve_time_mean_ms"),
                }
            else:
                cand_vals = None

            if baseline_vals is None and cand_vals is None:
                baseline_str = "missing baseline"
                cand_str = "missing candidate"
                delta_str = "-"
            elif baseline_vals is None and cand_vals is not None:
                baseline_str = "missing baseline"
                cand_str = f"cost={cand_vals.get('cost_tot')}, tdis={cand_vals.get('tdis_tot')}, solve_ms={cand_vals.get('solve_ms')}"
                delta_str = "-"
            elif baseline_vals is not None and cand_vals is None:
                baseline_str = f"cost={baseline_vals.get('cost_tot')}, tdis={baseline_vals.get('tdis_tot')}, solve_ms={baseline_vals.get('solve_ms')}"
                cand_str = "missing candidate"
                delta_str = "-"
            else:
                # compute percent delta on cost_tot as example (candidate - baseline)/baseline*100
                def pct(new, old):
                    try:
                        if new is None or old is None:
                            return None
                        if abs(old) < 1e-12:
                            return None
                        return 100.0 * (new - old) / old
                    except Exception:
                        return None
                d_cost = pct(cand_vals.get('cost_tot'), baseline_vals.get('cost_tot'))
                d_tdis = pct(cand_vals.get('tdis_tot'), baseline_vals.get('tdis_tot'))
                d_solve = None
                try:
                    if cand_vals.get('solve_ms') is not None and baseline_vals.get('solve_ms') is not None:
                        d_solve = cand_vals.get('solve_ms') - baseline_vals.get('solve_ms')
                except Exception:
                    d_solve = None
                baseline_str = f"cost={baseline_vals.get('cost_tot')}, tdis={baseline_vals.get('tdis_tot')}, solve_ms={baseline_vals.get('solve_ms')}"
                cand_str = f"cost={cand_vals.get('cost_tot')}, tdis={cand_vals.get('tdis_tot')}, solve_ms={cand_vals.get('solve_ms')}"
                # show composite delta
                pieces = []
                if d_cost is not None:
                    pieces.append(f"cost {d_cost:.2f}%")
                if d_tdis is not None:
                    pieces.append(f"tdis {d_tdis:.2f}%")
                if d_solve is not None:
                    pieces.append(f"solve_ms {d_solve:.2f} ms")
                delta_str = "; ".join(pieces) if pieces else "-"

            lines.append(f"| {ctrl} | {ep} | {baseline_str} | {cand_str} | {delta_str} |")

# Aggregates per candidate and controller - use summary's aggregates
lines.append("")
lines.append("## Aggregates per candidate (from summary_full_validation.json)")
lines.append("| Candidate | Controller | cost_mean | tdis_mean | solve_mean_ms | wall_time_s_mean | smoothness_mean |")
lines.append("|---|---|---:|---:|---:|---:|---:|")
for cand in sorted(summary.keys()):
    ag = summary[cand].get("aggregates", {})
    for ctrl, vals in ag.items():
        lines.append(
            f"| {cand} | {ctrl} | {vals.get('cost_tot_mean')} | {vals.get('tdis_tot_mean')} | {vals.get('mpc_solve_time_mean_ms_mean')} | {vals.get('episode_wall_time_s_mean')} | {vals.get('control_smoothness_mean')} |"
        )

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote fixed report to {OUT}")
