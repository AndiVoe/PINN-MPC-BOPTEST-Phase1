#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

CONTROLLERS = ["rc", "pinn", "rbc"]
LABELS = {"rc": "RC", "pinn": "PINN", "rbc": "RBC"}


def _list_common_episodes(root: Path) -> list[str]:
    sets: list[set[str]] = []
    for ctrl in CONTROLLERS:
        d = root / ctrl
        if not d.exists():
            return []
        sets.append({p.stem for p in d.glob("te_*.json") if not p.name.endswith(".live.json")})
    return sorted(set.intersection(*sets))


def _load_series(path: Path) -> dict[str, np.ndarray] | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rec = payload.get("step_records", []) or []
    if len(rec) < 8:
        return None

    t = np.asarray([float(r.get("time_s", i)) for i, r in enumerate(rec)], dtype=float)
    u = np.asarray([float(r.get("u_heating", np.nan)) for r in rec], dtype=float)
    z = np.asarray([float(r.get("t_zone", np.nan)) for r in rec], dtype=float)

    m = np.isfinite(u) & np.isfinite(z)
    if m.sum() < 8:
        return None

    t = t[m]
    u = u[m]
    z = z[m]
    if len(t) < 8:
        return None

    return {"t": t, "u": u, "z": z}


def _crosscorr_lag_steps(u: np.ndarray, z: np.ndarray) -> float:
    du = np.diff(u)
    dz = np.diff(z)
    if len(du) < 6:
        return np.nan

    max_lag = min(24, len(du) // 2)
    if max_lag < 2:
        return np.nan

    best_lag = 0
    best_abs_corr = -1.0

    for lag in range(0, max_lag + 1):
        x = du[: len(du) - lag] if lag > 0 else du
        y = dz[lag:]
        if len(x) < 4 or len(y) < 4:
            continue
        sx = float(np.std(x))
        sy = float(np.std(y))
        if sx < 1e-9 or sy < 1e-9:
            continue
        corr = float(np.corrcoef(x, y)[0, 1])
        if np.isfinite(corr) and abs(corr) > best_abs_corr:
            best_abs_corr = abs(corr)
            best_lag = lag

    return float(best_lag)


def _event_response_lags(u: np.ndarray, z: np.ndarray, du_threshold: float = 0.4, dz_threshold: float = 0.03, horizon: int = 24) -> tuple[list[int], int]:
    du = np.diff(u)
    dz = np.diff(z)
    idxs = np.where(np.abs(du) >= du_threshold)[0]
    lags: list[int] = []

    for i in idxs:
        direction = np.sign(du[i])
        if direction == 0:
            continue
        end = min(len(dz), i + horizon)
        found = None
        for j in range(i + 1, end):
            if np.sign(dz[j]) == direction and abs(dz[j]) >= dz_threshold:
                found = j - i
                break
        if found is not None:
            lags.append(int(found))

    return lags, int(len(idxs))


def _settling_proxy_steps(u: np.ndarray, z: np.ndarray, move_threshold: float = 0.4, stable_dz_threshold: float = 0.01, stable_window: int = 12) -> list[int]:
    du = np.diff(u)
    dz = np.diff(z)
    idxs = np.where(np.abs(du) >= move_threshold)[0]
    out: list[int] = []

    for i in idxs:
        for j in range(i + 1, len(dz) - stable_window):
            seg = np.abs(dz[j : j + stable_window])
            if np.all(seg <= stable_dz_threshold):
                out.append(int(j - i))
                break

    return out


def _analyze_root(root: Path) -> tuple[list[str], dict[str, dict[str, list[float] | int]]]:
    eps = _list_common_episodes(root)
    metrics: dict[str, dict[str, list[float] | int]] = {
        c: {
            "mean_abs_du": [],
            "xcorr_lag_steps": [],
            "event_lag_steps": [],
            "event_count": 0,
            "settle_steps": [],
        }
        for c in CONTROLLERS
    }

    for ep in eps:
        series = {}
        for c in CONTROLLERS:
            s = _load_series(root / c / (ep + ".json"))
            if s is None:
                series = {}
                break
            series[c] = s

        if not series:
            continue

        for c in CONTROLLERS:
            u = series[c]["u"]
            z = series[c]["z"]
            du = np.diff(u)
            metrics[c]["mean_abs_du"].append(float(np.mean(np.abs(du))))

            lag = _crosscorr_lag_steps(u, z)
            if np.isfinite(lag):
                metrics[c]["xcorr_lag_steps"].append(float(lag))

            event_lags, n_events = _event_response_lags(u, z)
            metrics[c]["event_lag_steps"].extend([float(v) for v in event_lags])
            metrics[c]["event_count"] = int(metrics[c]["event_count"]) + int(n_events)

            settle = _settling_proxy_steps(u, z)
            metrics[c]["settle_steps"].extend([float(v) for v in settle])

    return eps, metrics


def _mean(v: list[float]) -> float:
    return float(np.mean(v)) if v else float("nan")


def _p(v: list[float], q: int) -> float:
    return float(np.percentile(v, q)) if v else float("nan")


def _summarize_block(title: str, eps_desc: str, metrics: dict[str, dict[str, list[float] | int]]) -> list[str]:
    lines = [f"## {title}", f"- Episodes: {eps_desc}", ""]
    lines.append("| Controller | mean |du| [degC/step] | xcorr lag [steps] | event lag p50 [steps] | event lag p90 [steps] | large move events | settle p50 [steps] |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    for c in CONTROLLERS:
        d = metrics[c]
        mean_abs_du = _mean(d["mean_abs_du"])  # type: ignore[arg-type]
        xcorr = _mean(d["xcorr_lag_steps"])  # type: ignore[arg-type]
        p50 = _p(d["event_lag_steps"], 50)  # type: ignore[arg-type]
        p90 = _p(d["event_lag_steps"], 90)  # type: ignore[arg-type]
        settle50 = _p(d["settle_steps"], 50)  # type: ignore[arg-type]
        event_count = int(d["event_count"])  # type: ignore[arg-type]
        lines.append(
            f"| {LABELS[c]} | {mean_abs_du:.4f} | {xcorr:.2f} | {p50:.2f} | {p90:.2f} | {event_count} | {settle50:.2f} |"
        )

    lines.append("")
    return lines


def main() -> int:
    phase1_root = Path("results/mpc_phase1")
    eu_root = Path("results/eu_rc_vs_pinn/raw")
    out_path = Path("results/mpc_phase1/plots_3way_refresh/controller_inertia_lag_analysis.md")

    eps_phase1, m_phase1 = _analyze_root(phase1_root)

    # Pool all EU case folders
    pooled = {
        c: {
            "mean_abs_du": [],
            "xcorr_lag_steps": [],
            "event_lag_steps": [],
            "event_count": 0,
            "settle_steps": [],
        }
        for c in CONTROLLERS
    }
    eu_ep_count = 0

    for case in sorted([p for p in eu_root.glob("*") if p.is_dir()]):
        eps_case, m_case = _analyze_root(case)
        if not eps_case:
            continue
        eu_ep_count += len(eps_case)
        for c in CONTROLLERS:
            pooled[c]["mean_abs_du"].extend(m_case[c]["mean_abs_du"])  # type: ignore[index]
            pooled[c]["xcorr_lag_steps"].extend(m_case[c]["xcorr_lag_steps"])  # type: ignore[index]
            pooled[c]["event_lag_steps"].extend(m_case[c]["event_lag_steps"])  # type: ignore[index]
            pooled[c]["settle_steps"].extend(m_case[c]["settle_steps"])  # type: ignore[index]
            pooled[c]["event_count"] = int(pooled[c]["event_count"]) + int(m_case[c]["event_count"])  # type: ignore[index]

    lines: list[str] = []
    lines.append("# Controller Inertia / Delay / Lag Analysis")
    lines.append("")
    lines.append("Goal: determine whether poor behavior is mainly controller reaction timing or building inertia.")
    lines.append("")
    lines.append("Method:")
    lines.append("- Cross-correlation lag: lag between control changes (du) and temperature response (dz).")
    lines.append("- Event lag: after large setpoint move (|du| >= 0.4 degC), steps to first consistent response (|dz| >= 0.03 degC, same sign).")
    lines.append("- Settling proxy: steps after a large move until dz stays small (|dz| <= 0.01) for ~3h.")
    lines.append("")

    lines.extend(_summarize_block(
        "Scope A: Refreshed Phase1 Set",
        f"{len(eps_phase1)} ({', '.join(eps_phase1) if eps_phase1 else 'none'})",
        m_phase1,
    ))

    lines.extend(_summarize_block(
        "Scope B: EU Campaign Aggregate",
        f"{eu_ep_count} pooled common episodes across case folders",
        pooled,
    ))

    lines.append("## Interpretation")
    lines.append("- Similar response lag across controllers implies the plant inertia is shared and likely dominant in raw response timing.")
    lines.append("- Large differences in |du| with similar lag imply controller aggressiveness differences (possible overreaction).")
    lines.append("")
    for c in CONTROLLERS:
        lines.append(
            f"- {LABELS[c]} EU aggregate: mean |du|={_mean(pooled[c]['mean_abs_du']):.4f} degC/step, mean xcorr lag={_mean(pooled[c]['xcorr_lag_steps']):.2f} steps."  # type: ignore[index]
        )
    lines.append("")
    lines.append("## Conclusion")
    lines.append("- Building inertia is non-negligible: response and settling span multiple control steps.")
    lines.append("- Controller aggressiveness is also a key factor: PINN typically moves faster/larger in several cases than RC/RBC.")
    lines.append("- Therefore, both matter: inertia sets the physical delay, and tuning should reduce overreaction to that delay.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {out_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
