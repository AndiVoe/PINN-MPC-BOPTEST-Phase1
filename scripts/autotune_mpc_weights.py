#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Candidate:
    idx: int
    comfort_w: float
    energy_w: float
    smooth_w: float
    solver_maxiter: int


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be mapping: {path}")
    return data


def save_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)


def load_episode_metrics(path: Path) -> tuple[float, float, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    d = payload.get("diagnostic_kpis", {}) or {}
    comfort = float(d.get("comfort_Kh", 0.0))
    energy = float(d.get("total_energy_Wh", 0.0))
    solve_ms = float(d.get("mpc_solve_time_mean_ms", 0.0))
    return comfort, energy, solve_ms


def run_cmd(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")


def make_candidate(base_cfg: dict[str, Any], cand: Candidate) -> dict[str, Any]:
    cfg = json.loads(json.dumps(base_cfg))
    mpc = cfg.setdefault("mpc", {})
    weights = mpc.setdefault("objective_weights", {})
    weights["comfort"] = round(cand.comfort_w, 6)
    weights["energy"] = round(cand.energy_w, 6)
    weights["control_smoothness"] = round(cand.smooth_w, 6)
    mpc["solver_maxiter"] = int(cand.solver_maxiter)
    return cfg


def dominates(a: dict[str, float], b: dict[str, float]) -> bool:
    # Minimize all three dimensions.
    no_worse = (
        a["comfort_mean"] <= b["comfort_mean"]
        and a["energy_mean"] <= b["energy_mean"]
        and a["solve_mean_ms"] <= b["solve_mean_ms"]
    )
    strictly_better = (
        a["comfort_mean"] < b["comfort_mean"]
        or a["energy_mean"] < b["energy_mean"]
        or a["solve_mean_ms"] < b["solve_mean_ms"]
    )
    return no_worse and strictly_better


def pareto_front(rows: list[dict[str, float]]) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    for i, r in enumerate(rows):
        dominated = False
        for j, q in enumerate(rows):
            if i == j:
                continue
            if dominates(q, r):
                dominated = True
                break
        if not dominated:
            out.append(r)
    out.sort(key=lambda x: (x["comfort_mean"], x["energy_mean"], x["solve_mean_ms"]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Automated MPC weight tuning for PINN with Pareto reporting.")
    parser.add_argument("--base-config", default="configs/mpc_phase1.yaml")
    parser.add_argument("--predictor", default="pinn", choices=["pinn", "rc"])
    parser.add_argument("--episodes", nargs="+", default=["te_std_01", "te_ext_01"])
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--comfort-range", nargs=2, type=float, default=[90.0, 110.0])
    parser.add_argument("--energy-range", nargs=2, type=float, default=[0.0008, 0.0020])
    parser.add_argument("--smooth-range", nargs=2, type=float, default=[0.10, 0.35])
    parser.add_argument("--maxiter-range", nargs=2, type=int, default=[80, 100])
    parser.add_argument("--output-root", default="results/mpc_tuning_eval/autotune_v1")
    parser.add_argument("--reuse-existing", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)

    base_cfg_path = ROOT / args.base_config
    base_cfg = load_yaml(base_cfg_path)

    out_root = ROOT / args.output_root
    cfg_dir = out_root / "configs"
    run_root = out_root / "runs"
    out_root.mkdir(parents=True, exist_ok=True)

    # Baseline stats for normalized score.
    baseline_dir = ROOT / "results/mpc_tuning_eval/baseline" / args.predictor
    baseline = []
    for ep in args.episodes:
        p = baseline_dir / f"{ep}.json"
        if not p.exists():
            raise FileNotFoundError(f"Baseline episode missing: {p}")
        baseline.append(load_episode_metrics(p))

    b_comf = sum(x[0] for x in baseline) / len(baseline)
    b_energy = sum(x[1] for x in baseline) / len(baseline)
    b_solve = sum(x[2] for x in baseline) / len(baseline)

    rows: list[dict[str, float]] = []

    for idx in range(1, args.samples + 1):
        cand = Candidate(
            idx=idx,
            comfort_w=random.uniform(args.comfort_range[0], args.comfort_range[1]),
            energy_w=random.uniform(args.energy_range[0], args.energy_range[1]),
            smooth_w=random.uniform(args.smooth_range[0], args.smooth_range[1]),
            solver_maxiter=random.randint(args.maxiter_range[0], args.maxiter_range[1]),
        )

        cand_cfg = make_candidate(base_cfg, cand)
        cand_cfg_path = cfg_dir / f"cand_{idx:03d}.yaml"
        save_yaml(cand_cfg_path, cand_cfg)

        cand_run_dir = run_root / f"cand_{idx:03d}"
        cand_run_dir.mkdir(parents=True, exist_ok=True)

        comfort_vals: list[float] = []
        energy_vals: list[float] = []
        solve_vals: list[float] = []

        for ep in args.episodes:
            out_file = cand_run_dir / args.predictor / f"{ep}.json"
            if not (args.reuse_existing and out_file.exists()):
                cmd = [
                    str(ROOT / ".venv" / "Scripts" / "python.exe"),
                    "scripts/run_mpc_episode.py",
                    "--predictor",
                    args.predictor,
                    "--episode",
                    ep,
                    "--mpc-config",
                    str(cand_cfg_path.relative_to(ROOT)).replace("\\", "/"),
                    "--output-dir",
                    str(cand_run_dir.relative_to(ROOT)).replace("\\", "/"),
                    "--no-live-snapshot",
                    "--recover-from-queued",
                    "--startup-timeout-s",
                    "1800",
                ]
                run_cmd(cmd)

            c, e, s = load_episode_metrics(out_file)
            comfort_vals.append(c)
            energy_vals.append(e)
            solve_vals.append(s)

        c_mean = sum(comfort_vals) / len(comfort_vals)
        e_mean = sum(energy_vals) / len(energy_vals)
        s_mean = sum(solve_vals) / len(solve_vals)

        # Weighted normalized score: lower is better.
        n_comf = c_mean / max(b_comf, 1e-9)
        n_energy = e_mean / max(b_energy, 1e-9)
        n_solve = s_mean / max(b_solve if b_solve > 0 else 1.0, 1e-9)
        score = 0.60 * n_comf + 0.30 * n_energy + 0.10 * n_solve

        rows.append(
            {
                "idx": float(idx),
                "comfort_w": cand.comfort_w,
                "energy_w": cand.energy_w,
                "smooth_w": cand.smooth_w,
                "solver_maxiter": float(cand.solver_maxiter),
                "comfort_mean": c_mean,
                "energy_mean": e_mean,
                "solve_mean_ms": s_mean,
                "norm_score": score,
            }
        )

    rows.sort(key=lambda r: r["norm_score"])
    pareto = pareto_front(rows)

    csv_path = out_root / "autotune_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    pareto_path = out_root / "pareto_front.csv"
    with pareto_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in pareto:
            writer.writerow(r)

    md_path = out_root / "autotune_summary.md"
    lines = []
    lines.append("# Automated MPC Weight Tuning Summary")
    lines.append("")
    lines.append(f"- Predictor: {args.predictor}")
    lines.append(f"- Episodes: {', '.join(args.episodes)}")
    lines.append(f"- Samples: {args.samples}")
    lines.append(f"- Baseline means: comfort_Kh={b_comf:.4f}, energy_Wh={b_energy:.2f}, solve_ms={b_solve:.3f}")
    lines.append("")
    lines.append("## Top 5 by normalized score")
    lines.append("| cand | comfort_w | energy_w | smooth_w | maxiter | comfort_Kh | energy_Wh | solve_ms | score |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows[:5]:
        lines.append(
            "| {idx:.0f} | {comfort_w:.3f} | {energy_w:.5f} | {smooth_w:.3f} | {solver_maxiter:.0f} | {comfort_mean:.4f} | {energy_mean:.2f} | {solve_mean_ms:.3f} | {norm_score:.4f} |".format(
                **r
            )
        )

    lines.append("")
    lines.append("## Pareto Front (comfort, energy, solve) size")
    lines.append(f"- {len(pareto)} candidates")
    lines.append("")
    lines.append("Use pareto_front.csv to pick candidates based on your priority (comfort-first vs energy-first).")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"written: {csv_path.as_posix()}")
    print(f"written: {pareto_path.as_posix()}")
    print(f"written: {md_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
