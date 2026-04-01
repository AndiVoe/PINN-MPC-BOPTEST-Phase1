#!/usr/bin/env python3
import json
from pathlib import Path
from statistics import mean

root = Path("results/mpc_tuning_eval/autotune_v1_10cand/full_validation")
out = root / "summary_full_validation.json"
summary = {}

if not root.exists():
    print(f"No full_validation folder at {root}, exiting")
    raise SystemExit(1)

for cand in sorted(p for p in root.iterdir() if p.is_dir()):
    cand_id = cand.name
    summary[cand_id] = {"episodes": {}, "aggregates": {}}
    # find controllers under candidate (e.g., pinn)
    controllers = [d for d in cand.iterdir() if d.is_dir()]
    for ctrl in controllers:
        ctrl_name = ctrl.name
        for j in sorted(ctrl.glob("*.json")):
            ep = j.stem
            try:
                payload = json.loads(j.read_text(encoding="utf-8-sig"))
            except Exception as e:
                print(f"Failed to read {j}: {e}")
                continue
            b = payload.get("challenge_kpis", {})
            d = payload.get("diagnostic_kpis", {})
            cost = b.get("cost_tot", {}).get("value")
            tdis = b.get("tdis_tot", {}).get("value")
            solve = d.get("mpc_solve_time_mean_ms")
            wall = d.get("episode_wall_time_s")
            smooth = d.get("control_smoothness")
            summary[cand_id]["episodes"].setdefault(ep, {})[ctrl_name] = {
                "cost_tot": cost,
                "tdis_tot": tdis,
                "mpc_solve_time_mean_ms": solve,
                "episode_wall_time_s": wall,
                "control_smoothness": smooth,
            }
    # aggregates
    per_ctrl = {}
    for ctrl in controllers:
        ctrl_name = ctrl.name
        costs = []
        tdises = []
        solves = []
        walls = []
        smooths = []
        for ep, vals in summary[cand_id]["episodes"].items():
            v = vals.get(ctrl_name)
            if not v:
                continue
            if v.get("cost_tot") is not None:
                costs.append(v.get("cost_tot"))
            if v.get("tdis_tot") is not None:
                tdises.append(v.get("tdis_tot"))
            if v.get("mpc_solve_time_mean_ms") is not None:
                solves.append(v.get("mpc_solve_time_mean_ms"))
            if v.get("episode_wall_time_s") is not None:
                walls.append(v.get("episode_wall_time_s"))
            if v.get("control_smoothness") is not None:
                smooths.append(v.get("control_smoothness"))
        per_ctrl[ctrl_name] = {
            "cost_tot_mean": mean(costs) if costs else None,
            "tdis_tot_mean": mean(tdises) if tdises else None,
            "mpc_solve_time_mean_ms_mean": mean(solves) if solves else None,
            "episode_wall_time_s_mean": mean(walls) if walls else None,
            "control_smoothness_mean": mean(smooths) if smooths else None,
        }
    summary[cand_id]["aggregates"] = per_ctrl

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(f"Wrote summary to {out}")
