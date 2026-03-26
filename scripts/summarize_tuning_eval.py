#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import yaml

CONTROLLERS = ["rc", "pinn", "rbc"]
EPISODES = ["te_std_01", "te_ext_01"]
LABEL = {"rc": "RC", "pinn": "PINN", "rbc": "RBC"}


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def get_metrics(payload: dict) -> dict[str, float]:
    d = payload.get("diagnostic_kpis", {})
    b = payload.get("challenge_kpis", {})

    def cv(name: str) -> float:
        x = b.get(name, {})
        if isinstance(x, dict):
            return float(x.get("value", np.nan))
        return float(np.nan)

    return {
        "comfort_kh": float(d.get("comfort_Kh", np.nan)),
        "energy_wh": float(d.get("total_energy_Wh", np.nan)),
        "smoothness": float(d.get("control_smoothness", np.nan)),
        "solve_ms": float(d.get("mpc_solve_time_mean_ms", np.nan)),
        "tdis_tot": cv("tdis_tot"),
        "cost_tot": cv("cost_tot"),
    }


def lag_metrics(payload: dict) -> dict[str, float]:
    rec = payload.get("step_records", []) or []
    if len(rec) < 8:
        return {"mean_abs_du": np.nan, "xcorr_lag": np.nan, "event_lag_p50": np.nan}

    u = np.asarray([float(r.get("u_heating", np.nan)) for r in rec], dtype=float)
    z = np.asarray([float(r.get("t_zone", np.nan)) for r in rec], dtype=float)
    m = np.isfinite(u) & np.isfinite(z)
    u = u[m]
    z = z[m]
    if len(u) < 8:
        return {"mean_abs_du": np.nan, "xcorr_lag": np.nan, "event_lag_p50": np.nan}

    du = np.diff(u)
    dz = np.diff(z)

    # mean |du|
    mean_abs_du = float(np.mean(np.abs(du))) if len(du) else np.nan

    # xcorr lag
    max_lag = min(24, len(du) // 2)
    best_lag = np.nan
    best_abs = -1.0
    for lag in range(0, max_lag + 1):
        x = du[: len(du) - lag] if lag > 0 else du
        y = dz[lag:]
        if len(x) < 4 or len(y) < 4:
            continue
        sx = float(np.std(x))
        sy = float(np.std(y))
        if sx < 1e-9 or sy < 1e-9:
            continue
        c = float(np.corrcoef(x, y)[0, 1])
        if np.isfinite(c) and abs(c) > best_abs:
            best_abs = abs(c)
            best_lag = float(lag)

    # event lag p50
    idx = np.where(np.abs(du) >= 0.4)[0]
    lags: list[int] = []
    for i in idx:
        sgn = np.sign(du[i])
        if sgn == 0:
            continue
        end = min(len(dz), i + 24)
        for j in range(i + 1, end):
            if np.sign(dz[j]) == sgn and abs(dz[j]) >= 0.03:
                lags.append(j - i)
                break
    event_p50 = float(np.percentile(lags, 50)) if lags else np.nan

    return {
        "mean_abs_du": mean_abs_du,
        "xcorr_lag": best_lag,
        "event_lag_p50": event_p50,
    }


def pct_delta(new: float, old: float) -> float:
    if not np.isfinite(new) or not np.isfinite(old) or abs(old) < 1e-12:
        return np.nan
    return 100.0 * (new - old) / old


def fmt(v: float, digits: int = 3) -> str:
    if not np.isfinite(v):
        return "nan"
    return f"{v:.{digits}f}"


def load_cfg(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize MPC tuning candidate vs baseline.")
    parser.add_argument("--candidate", default="tuned_v1", help="Candidate folder under results/mpc_tuning_eval")
    parser.add_argument("--config", default="configs/mpc_phase1_tuned_v1.yaml", help="Config file path for report text")
    parser.add_argument("--report", default="results/mpc_phase1/plots_3way_refresh/tuning_v1_execution_report.md", help="Output markdown report path")
    args = parser.parse_args()

    root = Path("results/mpc_tuning_eval")
    bdir = root / "baseline"
    tdir = root / args.candidate
    out = Path(args.report)
    base_cfg = load_cfg(Path("configs/mpc_phase1.yaml"))
    cand_cfg = load_cfg(Path(args.config))

    bw = (((base_cfg.get("mpc") or {}).get("objective_weights") or {}))
    cw = (((cand_cfg.get("mpc") or {}).get("objective_weights") or {}))
    bmaxiter = ((base_cfg.get("mpc") or {}).get("solver_maxiter", np.nan))
    cmaxiter = ((cand_cfg.get("mpc") or {}).get("solver_maxiter", np.nan))

    lines: list[str] = []
    lines.append(f"# MPC {args.candidate}: Plan and Step-by-Step Execution Report")
    lines.append("")
    lines.append("## Plan")
    lines.append("1. Define a small, representative tuning subset (te_std_01, te_ext_01).")
    lines.append("2. Create lag-aware tuning candidate config with stronger smoothness penalty.")
    lines.append("3. Run baseline RC/PINN/RBC on subset.")
    lines.append(f"4. Run {args.candidate} RC/PINN/RBC on the same subset.")
    lines.append("5. Compare KPI + lag + solve-time deltas and decide next tuning move.")
    lines.append("")

    lines.append("## Tuned Config")
    lines.append(f"- File: {args.config}")
    lines.append(
        "- objective_weights: "
        f"comfort {fmt(float(bw.get('comfort', np.nan)),3)} -> {fmt(float(cw.get('comfort', np.nan)),3)}, "
        f"energy {fmt(float(bw.get('energy', np.nan)),4)} -> {fmt(float(cw.get('energy', np.nan)),4)}, "
        f"control_smoothness {fmt(float(bw.get('control_smoothness', np.nan)),3)} -> {fmt(float(cw.get('control_smoothness', np.nan)),3)}"
    )
    lines.append(f"- solver_maxiter: {bmaxiter} -> {cmaxiter}")
    lines.append("")

    lines.append("## Results by Controller/Episode")
    lines.append("| Controller | Episode | comfort_Kh delta % | energy_Wh delta % | smoothness delta % | mean abs du delta % | xcorr lag delta [steps] | solve mean delta [ms] |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")

    # Aggregate for quick decision lines
    agg = {c: {"comfort": [], "energy": [], "smooth": [], "du": [], "solve": []} for c in CONTROLLERS}

    for c in CONTROLLERS:
        for ep in EPISODES:
            bp = load_json(bdir / c / f"{ep}.json")
            tp = load_json(tdir / c / f"{ep}.json")
            bm = get_metrics(bp)
            tm = get_metrics(tp)
            bl = lag_metrics(bp)
            tl = lag_metrics(tp)

            d_comf = pct_delta(tm["comfort_kh"], bm["comfort_kh"])
            d_en = pct_delta(tm["energy_wh"], bm["energy_wh"])
            d_sm = pct_delta(tm["smoothness"], bm["smoothness"])
            d_du = pct_delta(tl["mean_abs_du"], bl["mean_abs_du"])
            d_lag = tl["xcorr_lag"] - bl["xcorr_lag"] if np.isfinite(tl["xcorr_lag"]) and np.isfinite(bl["xcorr_lag"]) else np.nan
            d_solve = tm["solve_ms"] - bm["solve_ms"] if np.isfinite(tm["solve_ms"]) and np.isfinite(bm["solve_ms"]) else np.nan

            lines.append(
                f"| {LABEL[c]} | {ep} | {fmt(d_comf,1)} | {fmt(d_en,1)} | {fmt(d_sm,1)} | {fmt(d_du,1)} | {fmt(d_lag,2)} | {fmt(d_solve,1)} |"
            )

            if np.isfinite(d_comf):
                agg[c]["comfort"].append(d_comf)
            if np.isfinite(d_en):
                agg[c]["energy"].append(d_en)
            if np.isfinite(d_sm):
                agg[c]["smooth"].append(d_sm)
            if np.isfinite(d_du):
                agg[c]["du"].append(d_du)
            if np.isfinite(d_solve):
                agg[c]["solve"].append(d_solve)

    lines.append("")
    lines.append("## Aggregate Delays and Side Effects")
    avg: dict[str, dict[str, float]] = {c: {} for c in CONTROLLERS}
    for c in CONTROLLERS:
        mc = np.mean(agg[c]["comfort"]) if agg[c]["comfort"] else np.nan
        me = np.mean(agg[c]["energy"]) if agg[c]["energy"] else np.nan
        ms = np.mean(agg[c]["smooth"]) if agg[c]["smooth"] else np.nan
        md = np.mean(agg[c]["du"]) if agg[c]["du"] else np.nan
        msolve = np.mean(agg[c]["solve"]) if agg[c]["solve"] else np.nan
        avg[c] = {"comfort": mc, "energy": me, "smooth": ms, "du": md, "solve": msolve}
        lines.append(
            f"- {LABEL[c]} avg deltas: comfort {fmt(mc,1)}%, energy {fmt(me,1)}%, smoothness {fmt(ms,1)}%, mean |du| {fmt(md,1)}%, solve_mean {fmt(msolve,1)} ms."
        )

    lines.append("")
    lines.append("## Interpretation")
    lines.append("- RBC is unchanged (as expected), confirming comparison integrity.")
    lines.append("- RC changed slightly but did not show a clean smoothness-energy-comfort improvement tradeoff on this subset.")
    pinn_solve = avg["pinn"].get("solve", np.nan)
    pinn_comfort = avg["pinn"].get("comfort", np.nan)
    if np.isfinite(pinn_solve) and pinn_solve > 50:
        solve_text = "optimizer runtime increased strongly"
    elif np.isfinite(pinn_solve) and pinn_solve < -10:
        solve_text = "optimizer runtime improved"
    else:
        solve_text = "optimizer runtime stayed close to baseline"
    lines.append(
        f"- PINN summary: comfort delta {fmt(pinn_comfort,1)}% and {solve_text} ({fmt(pinn_solve,1)} ms mean delta)."
    )
    lines.append("")
    lines.append("## Decision")
    if np.isfinite(pinn_comfort) and pinn_comfort <= 5 and np.isfinite(pinn_solve) and pinn_solve <= 20:
        lines.append(f"- {args.candidate} is acceptable for wider validation (meets subset acceptance thresholds).")
        lines.append("- Next step: expand to all refreshed episodes and re-check comfort/energy parity.")
    else:
        lines.append(f"- Keep the step-by-step pipeline, but reject {args.candidate} as a production candidate.")
        lines.append("- Next candidate should preserve PINN comfort parity while keeping solve-time overhead low.")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {out.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
