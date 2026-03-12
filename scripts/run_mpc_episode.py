#!/usr/bin/env python3
"""
WP4 – MPC episode runner.

Runs one rolling-horizon MPC experiment for a given episode definition,
using either the RC whitebox predictor or the trained PINN surrogate as
the interior model.  Results are saved to the output directory as JSON.

Usage examples:
    python scripts/run_mpc_episode.py --predictor rc   --episode te_std_01
    python scripts/run_mpc_episode.py --predictor pinn --episode te_std_01
    python scripts/run_mpc_episode.py --predictor pinn --episode all-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Path setup – makes sibling packages importable when run as a script.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpc.boptest import BoptestClient
from mpc.kpi import KPILogger
from mpc.occupancy import comfort_bounds, is_occupied
from mpc.predictors import PINNPredictor, RCPredictor
from mpc.solver import MPCSolver


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _pick_first(candidates: list[str], available: set[str]) -> str | None:
    for name in candidates:
        if name in available:
            return name
    return None


def _to_degc(value: float | None) -> float | None:
    if value is None:
        return None
    return value - 273.15 if value > 200.0 else value


def _resolve_boptest_url(hint: str) -> str:
    import requests
    candidates = list(dict.fromkeys([
        hint.rstrip("/"),
        "http://127.0.0.1:5000",
        "http://127.0.0.1:8000",
        "http://localhost:5000",
        "http://localhost:8000",
    ]))
    for url in candidates:
        try:
            resp = requests.get(f"{url}/version", timeout=3)
            if resp.ok:
                return url
        except Exception:
            continue
    raise RuntimeError("No reachable BOPTEST API found. Checked: " + ", ".join(candidates))


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Core episode runner
# ---------------------------------------------------------------------------

def run_mpc_episode(
    *,
    client: BoptestClient,
    case_name: str,
    case_mappings: dict[str, Any],
    episode: dict[str, Any],
    defaults: dict[str, Any],
    solver: MPCSolver,
    predictor_name: str,
) -> dict[str, Any]:
    """
    Run one full MPC episode against the BOPTEST plant.

    Returns a result dict with step-level records and end-of-episode KPIs.
    """
    step_s = int(defaults["control_interval_s"])
    length_days = int(episode.get("episode_length_days", defaults["episode_length_days"]))
    n_steps = int(length_days * 24 * 3600 / step_s)
    warmup_s = int(episode.get("warmup_period_s", defaults["warmup_period_s"]))
    start_time_s = int(episode.get("start_time_s", defaults.get("start_time_s", 0)))

    scenario = episode.get("scenario", {})
    client.set_scenario(scenario)

    print(f"  Initializing episode '{episode['id']}' "
          f"(start={start_time_s}s, warmup={warmup_s}s, steps={n_steps}) …", flush=True)
    init_payload = client.initialize(start_time_s=start_time_s, warmup_period_s=warmup_s)
    client.set_step(step_s)

    # Resolve available signals.
    inputs = client.get_inputs()
    input_names = set(inputs.keys())
    init_names = set(init_payload.keys())
    all_names = init_names | input_names

    mappings = case_mappings
    zone_signal = _pick_first(mappings["zone_temp_candidates"], all_names)
    outdoor_signal = _pick_first(mappings["outdoor_temp_candidates"], all_names)
    solar_signal = _pick_first(mappings["solar_candidates"], all_names)
    u_val_name = _pick_first(mappings["control_value_candidates"], input_names)
    u_act_name = _pick_first(mappings["control_activate_candidates"], input_names)

    print(f"  Signals: zone={zone_signal}, outdoor={outdoor_signal}, "
          f"solar={solar_signal}, u={u_val_name}", flush=True)

    if zone_signal is None:
        raise RuntimeError("Could not resolve zone temperature signal.")
    if u_val_name is None:
        raise RuntimeError("Could not resolve control input signal.")

    forecast_points = []
    if outdoor_signal:
        forecast_points.append(outdoor_signal)
    if solar_signal:
        forecast_points.append(solar_signal)

    horizon_s = int(solver.horizon * solver.dt_s)

    kpi = KPILogger(dt_s=float(step_s))
    solver.reset()

    # Initial measurements from init_payload.
    current = init_payload
    t_s = start_time_s
    u_prev = float(solver.u_min + solver.u_max) / 2.0  # neutral initial guess
    episode_wall_start = time.perf_counter()

    def _read_zone_temp(payload: dict) -> float:
        val = payload.get(zone_signal)
        if val is None:
            raise RuntimeError(f"Zone signal '{zone_signal}' missing from payload.")
        result = _to_degc(float(val))
        if result is None:
            raise RuntimeError("Could not decode zone temperature.")
        return result

    def _read_power_components(payload: dict[str, Any]) -> dict[str, float]:
        p_heat = 0.0
        p_ele = 0.0
        p_other = 0.0
        for key, val in payload.items():
            if not isinstance(val, (int, float)):
                continue
            value = float(val)
            if not (value == value):
                continue
            key_l = key.lower()
            if any(token in key_l for token in ("reaqhea", "qhea", "district", "dh_")):
                p_heat += max(0.0, value)
            elif any(token in key_l for token in ("reap", "pele", "pel", "power", "ele")):
                p_ele += max(0.0, value)
            elif re.search(r"(reaq|q_)", key_l):
                p_other += max(0.0, value)
        p_total = p_heat + p_ele + p_other
        return {
            "power_total_w": p_total,
            "power_heating_w": p_heat,
            "power_electric_w": p_ele,
        }

    def _get_weather_forecast(n_steps_fwd: int) -> list[dict[str, float]]:
        try:
            fc = client.get_forecast(forecast_points, horizon_s=n_steps_fwd * step_s, interval_s=step_s)
        except Exception:
            fc = {}
        t_out_list = []
        h_glo_list = []
        if outdoor_signal and outdoor_signal in fc:
            t_out_list = [_to_degc(v) or 0.0 for v in fc[outdoor_signal]]
        if solar_signal and solar_signal in fc:
            h_glo_list = [max(0.0, float(v)) for v in fc[solar_signal]]
        # Pad to requested length.
        t_out_now = _to_degc(current.get(outdoor_signal, 273.15 + 10.0)) or 10.0
        h_glo_now = max(0.0, float(current.get(solar_signal, 0.0)))
        while len(t_out_list) < n_steps_fwd:
            t_out_list.append(t_out_now)
        while len(h_glo_list) < n_steps_fwd:
            h_glo_list.append(h_glo_now)
        return [
            {"t_outdoor": t_out_list[k], "h_global": h_glo_list[k]}
            for k in range(n_steps_fwd)
        ]

    # Main control loop.
    for step_idx in range(n_steps):
        t_zone = _read_zone_temp(current)

        # --- MPC solve ---
        weather_fc = _get_weather_forecast(solver.horizon)
        u_opt, u_seq, solve_info = solver.solve(
            t_zone=t_zone,
            weather_forecast=weather_fc,
            u_prev=u_prev,
            time_s=t_s,
        )

        # Apply setpoint to plant (convert degC → K for oveTZonSet_u).
        u_cmd = u_opt + 273.15 if ("Set" in u_val_name or "TSet" in u_val_name or "ZonSet" in u_val_name) else u_opt
        control_cmd: dict[str, float] = {u_val_name: u_cmd}
        if u_act_name:
            control_cmd[u_act_name] = 1.0

        next_payload = client.advance(control_cmd)

        # Record KPIs using current-step T_zone and power from the advance response.
        pwr = _read_power_components(next_payload)
        t_lo, t_hi = comfort_bounds(t_s)
        occupied = is_occupied(t_s)

        kpi.record(
            time_s=t_s,
            t_zone=t_zone,
            u_heating=u_opt,
            power_w=pwr["power_total_w"],
            power_heating_w=pwr["power_heating_w"],
            power_electric_w=pwr["power_electric_w"],
            solve_time_ms=solve_info["solve_time_ms"],
            t_lower=t_lo,
            t_upper=t_hi,
            occupied=occupied,
        )

        if (step_idx + 1) % 96 == 0 or step_idx == n_steps - 1:
            print(
                f"  step {step_idx + 1:4d}/{n_steps}  t_s={t_s:8d}  "
                f"T_zone={t_zone:.2f}°C  u={u_opt:.2f}°C  "
                f"solve={solve_info['solve_time_ms']:.1f}ms  "
                f"{'OK' if solve_info['success'] else 'WARN:infeasible'}",
                flush=True,
            )

        current = next_payload
        u_prev = u_opt
        t_s += step_s

    episode_wall_s = time.perf_counter() - episode_wall_start
    print(f"  Episode done in {episode_wall_s:.1f}s.", flush=True)

    # Collect end-of-episode KPIs from BOPTEST (informational; may fail).
    boptest_kpis: dict = {}
    try:
        boptest_kpis = client.kpi()
    except Exception as exc:
        print(f"  Warning: could not fetch BOPTEST KPIs: {exc}", flush=True)

    payload = kpi.build_kpi_payload(boptest_kpis=boptest_kpis)
    challenge_kpis = payload["challenge_kpis"]
    diagnostic_kpis = payload["diagnostic_kpis"]
    diagnostic_kpis["episode_wall_time_s"] = round(episode_wall_s, 2)

    return {
        "episode_id": episode["id"],
        "predictor": predictor_name,
        "split": episode.get("split", "unknown"),
        "weather_class": episode.get("weather_class", "unknown"),
        "case_name": case_name,
        "start_time_s": start_time_s,
        "control_interval_s": step_s,
        "n_steps": n_steps,
        "kpi_summary": challenge_kpis,
        "challenge_kpis": challenge_kpis,
        "diagnostic_kpis": diagnostic_kpis,
        "boptest_kpis": boptest_kpis,
        "step_records": kpi.step_records(),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="WP4 MPC episode runner.")
    parser.add_argument(
        "--predictor", choices=["rc", "pinn"], required=True,
        help="Interior model: 'rc' (whitebox RC) or 'pinn' (surrogate).",
    )
    parser.add_argument(
        "--episode", default="all-test",
        help="Episode ID from the manifest (e.g. te_std_01) or 'all-test' for all test episodes.",
    )
    parser.add_argument("--manifest", default="manifests/episode_split_phase1.yaml")
    parser.add_argument("--mpc-config", default="configs/mpc_phase1.yaml")
    parser.add_argument("--checkpoint", default="artifacts/pinn_phase1/best_model.pt")
    parser.add_argument("--output-dir", default="results/mpc_phase1")
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--case", default="singlezone_commercial_hydronic")
    parser.add_argument("--reuse-testid", default="",
                        help="Attach to an already-Running BOPTEST testid.")
    parser.add_argument("--startup-timeout-s", type=int, default=900)
    parser.add_argument(
        "--recover-from-queued",
        action="store_true",
        help="If startup stays Queued, stop the stuck test and retry selection once.",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------ setup
    manifest = _load_yaml(ROOT / args.manifest)
    mpc_cfg = _load_yaml(ROOT / args.mpc_config)
    defaults = manifest["defaults"]
    case_mappings = manifest["case_mappings"][args.case]
    episodes = manifest["episodes"]

    # Filter to requested episode(s).
    if args.episode == "all-test":
        target_episodes = [e for e in episodes if e.get("split") == "test"]
    else:
        target_episodes = [e for e in episodes if e["id"] == args.episode]
    if not target_episodes:
        raise ValueError(f"Episode '{args.episode}' not found in manifest.")

    # ------------------------------------------------------------------ predictor
    ckpt_path = ROOT / args.checkpoint
    if args.predictor == "pinn":
        print("Loading PINN predictor …", flush=True)
        predictor = PINNPredictor(ckpt_path)
        predictor_name = "pinn"
    else:
        print("Loading RC predictor from checkpoint …", flush=True)
        predictor = RCPredictor.from_checkpoint(ckpt_path)
        predictor_name = "rc"
        print(
            f"  RC params: ua={predictor.ua:.4f}, solar_gain={predictor.solar_gain:.4f}, "
            f"hvac_gain={predictor.hvac_gain:.4f}, capacity={predictor.capacity:.4f}",
            flush=True,
        )

    # ------------------------------------------------------------------ solver
    mpc = mpc_cfg.get("mpc", {})
    horizon_s = int(mpc.get("horizon_s", 21600))
    dt_s = int(defaults["control_interval_s"])
    horizon_steps = horizon_s // dt_s

    comfort_occ = tuple(mpc.get("comfort_bounds_degC", {}).get("occupied", [21.0, 24.0]))
    comfort_unocc = tuple(mpc.get("comfort_bounds_degC", {}).get("unoccupied", [15.0, 30.0]))
    weights = mpc.get("objective_weights", {})

    solver = MPCSolver(
        predictor=predictor,
        horizon_steps=horizon_steps,
        dt_s=float(dt_s),
        u_min=float(mpc.get("u_min_degC", 18.0)),
        u_max=float(mpc.get("u_max_degC", 26.0)),
        w_comfort=float(weights.get("comfort", 100.0)),
        w_energy=float(weights.get("energy", 0.0001)),
        w_smooth=float(weights.get("control_smoothness", 0.1)),
        maxiter=int(mpc.get("solver_maxiter", 100)),
        ftol=float(mpc.get("solver_ftol", 1e-4)),
        occupied_bounds=comfort_occ,
        unoccupied_bounds=comfort_unocc,
    )

    # ------------------------------------------------------------------ connect
    boptest_url = _resolve_boptest_url(args.url)
    print(f"Connecting to BOPTEST at {boptest_url} …", flush=True)
    client = BoptestClient(boptest_url)

    if args.reuse_testid:
        print(f"Attaching to testid {args.reuse_testid} …", flush=True)
        client.attach_testid(args.reuse_testid)
    else:
        print(f"Selecting test case '{args.case}' …", flush=True)
        testid = client.select_test_case(args.case)
        print(f"  testid={testid}", flush=True)
        print("Waiting for Running state …", flush=True)
        try:
            client.wait_running(timeout_s=args.startup_timeout_s)
        except TimeoutError:
            if not args.recover_from_queued:
                raise
            print("Startup timeout in Queued state. Attempting one-time recovery …", flush=True)
            try:
                stopped = client.stop()
                print(f"  stop({testid}) -> {stopped}", flush=True)
            except Exception as exc:
                print(f"  Warning: stop failed: {exc}", flush=True)

            print(f"Re-selecting test case '{args.case}' after cleanup …", flush=True)
            testid = client.select_test_case(args.case)
            print(f"  retry testid={testid}", flush=True)
            print("Waiting for Running state (retry) …", flush=True)
            client.wait_running(timeout_s=args.startup_timeout_s)

    # ------------------------------------------------------------------ run
    output_dir = ROOT / args.output_dir / predictor_name
    _ensure_dir(output_dir)

    for episode in target_episodes:
        ep_id = episode["id"]
        out_path = output_dir / f"{ep_id}.json"
        print(f"\n{'='*60}", flush=True)
        print(f"Episode {ep_id} | predictor={predictor_name}", flush=True)
        print(f"{'='*60}", flush=True)

        try:
            result = run_mpc_episode(
                client=client,
                case_name=args.case,
                case_mappings=case_mappings,
                episode=episode,
                defaults=defaults,
                solver=solver,
                predictor_name=predictor_name,
            )
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"  Saved → {out_path}", flush=True)
            print("  Challenge KPIs:", json.dumps(result["challenge_kpis"], indent=4), flush=True)
            print("  Diagnostic KPIs:", json.dumps(result["diagnostic_kpis"], indent=4), flush=True)
        except Exception as exc:
            print(f"  ERROR running episode {ep_id}: {exc}", flush=True)
            import traceback
            traceback.print_exc()

    print("\nAll done.", flush=True)


if __name__ == "__main__":
    main()
