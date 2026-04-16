#!/usr/bin/env python3
"""
WP4 - MPC episode runner.

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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Path setup - makes sibling packages importable when run as a script.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpc.boptest import BoptestClient
from mpc.kpi import KPILogger
from mpc.occupancy import comfort_bounds, is_occupied, OccupancySchedule
from mpc.predictors import PINNPredictor, RCPredictor
from mpc.solver import MPCSolver


class _RBCSolverAdapter:
    """Minimal solver-like adapter for rule-based control mode."""

    def __init__(self, *, horizon_steps: int, dt_s: float, u_min: float, u_max: float) -> None:
        self.horizon = int(horizon_steps)
        self.dt_s = float(dt_s)
        self.u_min = float(u_min)
        self.u_max = float(u_max)

    def reset(self) -> None:
        return


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


def _as_name_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise ValueError(f"Signal mapping must be a string or list[str], got: {value!r}")


def _unique_in_order(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _validate_available(names: list[str], available: set[str], label: str) -> list[str]:
    missing = [name for name in names if name not in available]
    if missing:
        raise RuntimeError(f"Could not resolve {label}: missing {missing}")
    return names


def _resolve_signal_group(
    mappings: dict[str, Any],
    *,
    singular_key: str,
    plural_key: str,
    candidate_key: str,
    available: set[str],
    required: bool,
    label: str,
) -> list[str]:
    explicit = _as_name_list(mappings.get(plural_key))
    if not explicit:
        explicit = _as_name_list(mappings.get(singular_key))
    if explicit:
        return _unique_in_order(_validate_available(explicit, available, label))

    picked = _pick_first(mappings.get(candidate_key, []), available)
    if picked is not None:
        return [picked]
    if required:
        raise RuntimeError(f"Could not resolve {label}.")
    return []


def _resolve_optional_signal(
    mappings: dict[str, Any],
    *,
    explicit_key: str,
    candidate_key: str,
    available: set[str],
) -> str | None:
    explicit = mappings.get(explicit_key)
    if explicit is not None:
        names = _validate_available(_as_name_list(explicit), available, explicit_key)
        if len(names) != 1:
            raise RuntimeError(f"{explicit_key} must resolve to exactly one signal.")
        return names[0]
    return _pick_first(mappings.get(candidate_key, []), available)


def _resolve_fixed_control_commands(
    mappings: dict[str, Any],
    *,
    available: set[str],
) -> dict[str, float]:
    raw = mappings.get("fixed_control_commands", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("fixed_control_commands must be a mapping of signal->value.")
    missing = [name for name in raw.keys() if name not in available]
    if missing:
        raise RuntimeError(f"Could not resolve fixed control command signals: {missing}")
    parsed: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(value, (int, float)):
            raise ValueError(f"fixed_control_commands[{key}] must be numeric, got {value!r}")
        parsed[key] = float(value)
    return parsed


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


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(path)


def _has_valid_existing_output(path: Path, episode_id: str, predictor_label: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    return (
        payload.get("episode_id") == episode_id
        and payload.get("predictor_label") == predictor_label
        and isinstance(payload.get("step_records"), list)
        and len(payload.get("step_records", [])) > 0
    )


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _control_uses_kelvin(signal_name: str) -> bool:
    signal_name_l = signal_name.lower()
    return any(token in signal_name_l for token in ("set", "tset", "zonset"))


class AdvanceExecutionError(RuntimeError):
    """Raised when a BOPTEST /advance call fails during an MPC step."""

    def __init__(self, *, step_index: int, waited_s: int, cause: Exception) -> None:
        self.step_index = int(step_index)
        self.waited_s = int(waited_s)
        self.cause = cause
        super().__init__(f"Advance failed at step {self.step_index}: {cause}")


def _is_retriable_first_advance_failure(exc: Exception) -> bool:
    if not isinstance(exc, AdvanceExecutionError):
        return False
    if exc.step_index != 1:
        return False
    text = str(exc.cause)
    text_l = text.lower()
    return (
        "http 500" in text_l
        or "internal server error" in text_l
        or "timed out" in text_l
        or "timeout" in text_l
    )


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
    solver: MPCSolver | _RBCSolverAdapter,
    predictor_name: str,
    predictor_base: str,
    occupancy_schedule: OccupancySchedule | None = None,
    advance_heartbeat_s: int = 60,
    live_snapshot_path: Path | None = None,
    attempt_index: int = 1,
    max_attempts: int = 1,
    export_solver_trace: bool = True,
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
          f"(start={start_time_s}s, warmup={warmup_s}s, steps={n_steps}) ...", flush=True)
    init_payload = client.initialize(start_time_s=start_time_s, warmup_period_s=warmup_s)
    client.set_step(step_s)

    # Resolve available signals.
    inputs = client.get_inputs()
    input_names = set(inputs.keys())
    init_names = set(init_payload.keys())
    all_names = init_names | input_names

    mappings = case_mappings
    zone_signals = _resolve_signal_group(
        mappings,
        singular_key="zone_temp_signal",
        plural_key="zone_temp_signals",
        candidate_key="zone_temp_candidates",
        available=all_names,
        required=True,
        label="zone temperature signal",
    )
    outdoor_signal = _resolve_optional_signal(
        mappings,
        explicit_key="outdoor_temp_signal",
        candidate_key="outdoor_temp_candidates",
        available=all_names,
    )
    solar_signal = _resolve_optional_signal(
        mappings,
        explicit_key="solar_signal",
        candidate_key="solar_candidates",
        available=all_names,
    )
    u_val_names = _resolve_signal_group(
        mappings,
        singular_key="control_value_signal",
        plural_key="control_value_signals",
        candidate_key="control_value_candidates",
        available=input_names,
        required=True,
        label="control input signal",
    )
    system_u_val_names = _resolve_signal_group(
        mappings,
        singular_key="system_control_value_signal",
        plural_key="system_control_value_signals",
        candidate_key="system_control_value_candidates",
        available=input_names,
        required=False,
        label="system control input signal",
    )
    u_act_names = _resolve_signal_group(
        mappings,
        singular_key="control_activate_signal",
        plural_key="control_activate_signals",
        candidate_key="control_activate_candidates",
        available=input_names,
        required=False,
        label="control activate signal",
    )
    system_u_act_names = _resolve_signal_group(
        mappings,
        singular_key="system_control_activate_signal",
        plural_key="system_control_activate_signals",
        candidate_key="system_control_activate_candidates",
        available=input_names,
        required=False,
        label="system control activate signal",
    )
    power_heat_names = _resolve_signal_group(
        mappings,
        singular_key="power_heating_signal",
        plural_key="power_heating_signals",
        candidate_key="power_heating_candidates",
        available=all_names,
        required=False,
        label="heating power signal",
    )
    power_ele_names = _resolve_signal_group(
        mappings,
        singular_key="power_electric_signal",
        plural_key="power_electric_signals",
        candidate_key="power_electric_candidates",
        available=all_names,
        required=False,
        label="electric power signal",
    )
    fixed_control_cmd = _resolve_fixed_control_commands(mappings, available=input_names)

    print(
        f"  Signals: zone={zone_signals}, outdoor={outdoor_signal}, "
        f"solar={solar_signal}, u={u_val_names}, system_u={system_u_val_names}, "
        f"p_heat={power_heat_names}, p_ele={power_ele_names}",
        flush=True,
    )

    def _write_live_snapshot(snapshot: dict[str, Any]) -> None:
        if live_snapshot_path is None:
            return
        try:
            base = {
                "episode_id": episode["id"],
                "predictor_label": predictor_name,
                "case_name": case_name,
                "attempt_index": int(attempt_index),
                "max_attempts": int(max_attempts),
                "start_time_s": start_time_s,
                "warmup_period_s": warmup_s,
                "control_interval_s": step_s,
                "n_steps": n_steps,
                "updated_at_unix_s": time.time(),
            }
            base.update(snapshot)
            _write_json_atomic(live_snapshot_path, base)
        except Exception:
            # Snapshot writing is best-effort and must not interrupt MPC execution.
            pass

    mapping_warnings: list[str] = []
    if outdoor_signal is None:
        mapping_warnings.append("missing_outdoor_temp_signal")
    if solar_signal is None:
        mapping_warnings.append("missing_solar_signal")
    
    # Check for multi-zone control without proper vectorization
    if len(u_val_names) > 1 or len(system_u_val_names) > 1:
        mapping_warnings.append(
            f"multi_zone_control_uses_scalar_setpoint: {len(u_val_names)} zone(s) + "
            f"{len(system_u_val_names)} system control signal(s) use the same scalar MPC output. "
            f"For independent per-zone optimization, solver vectorization required."
        )

    forecast_points = []
    forecast_available: set[str] = set()
    try:
        forecast_available = client.get_forecast_points()
    except Exception as exc:
        mapping_warnings.append(f"forecast_points_unavailable:{type(exc).__name__}")

    if outdoor_signal and (not forecast_available or outdoor_signal in forecast_available):
        forecast_points.append(outdoor_signal)
    elif outdoor_signal:
        mapping_warnings.append(f"outdoor_not_in_forecast_points:{outdoor_signal}")
    if solar_signal and (not forecast_available or solar_signal in forecast_available):
        forecast_points.append(solar_signal)
    elif solar_signal:
        mapping_warnings.append(f"solar_not_in_forecast_points:{solar_signal}")

    horizon_s = int(solver.horizon * solver.dt_s)

    kpi = KPILogger(dt_s=float(step_s))
    solver.reset()
    solver_trace: list[dict[str, Any]] = []

    # Initial measurements from init_payload.
    current = init_payload
    t_s = start_time_s
    u_prev = float(solver.u_min + solver.u_max) / 2.0  # neutral initial guess
    episode_wall_start = time.perf_counter()

    def _read_zone_temp(payload: dict) -> float:
        values: list[float] = []
        for zone_signal in zone_signals:
            val = payload.get(zone_signal)
            if val is None:
                raise RuntimeError(f"Zone signal '{zone_signal}' missing from payload.")
            result = _to_degc(float(val))
            if result is None:
                raise RuntimeError(f"Could not decode zone temperature from '{zone_signal}'.")
            values.append(result)
        return sum(values) / len(values)

    def _read_power_components(payload: dict[str, Any]) -> dict[str, float]:
        if power_heat_names or power_ele_names:
            p_heat = sum(max(0.0, float(payload.get(name, 0.0) or 0.0)) for name in power_heat_names)
            p_ele = sum(max(0.0, float(payload.get(name, 0.0) or 0.0)) for name in power_ele_names)
            return {
                "power_total_w": p_heat + p_ele,
                "power_heating_w": p_heat,
                "power_electric_w": p_ele,
            }

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
            if any(token in key_l for token in ("reaqhea", "qhea", "reahea", "district", "dh_")):
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

    try:
        init_t_zone = _read_zone_temp(current)
    except Exception:
        init_t_zone = None

    _write_live_snapshot(
        {
            "state": "initialized",
            "step_index": 0,
            "sim_time_s": t_s,
            "t_zone_degC": init_t_zone,
            "resolved_signals": {
                "zone_temp_signals": zone_signals,
                "outdoor_temp_signal": outdoor_signal,
                "solar_signal": solar_signal,
                "control_value_signals": u_val_names,
                "system_control_value_signals": system_u_val_names,
                "control_activate_signals": u_act_names,
                "system_control_activate_signals": system_u_act_names,
                "power_heating_signals": power_heat_names,
                "power_electric_signals": power_ele_names,
            },
            "initialize_payload": current,
            "mapping_warnings": mapping_warnings,
        }
    )

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

        # --- Control step (MPC or RBC) ---
        if predictor_base == "rbc":
            # Occupancy-aware deadband thermostat with anti-chatter hysteresis.
            t_lo, t_hi = comfort_bounds(t_s, schedule=occupancy_schedule)
            occupied = is_occupied(t_s, occupancy_schedule)
            deadband = 0.2
            ramp_degC = 1.5

            if occupied:
                hold_setpoint = min(solver.u_max, max(solver.u_min, t_lo + 0.3))
            else:
                hold_setpoint = solver.u_min

            if t_zone < (t_lo - deadband):
                u_opt = min(solver.u_max, max(hold_setpoint, t_lo + 0.7))
            elif t_zone > (t_hi + deadband):
                u_opt = solver.u_min
            else:
                u_opt = max(solver.u_min, min(solver.u_max, u_prev))

            u_opt = float(max(solver.u_min, min(solver.u_max, u_opt)))
            if abs(u_opt - u_prev) > ramp_degC:
                u_opt = u_prev + (ramp_degC if u_opt > u_prev else -ramp_degC)
                u_opt = float(max(solver.u_min, min(solver.u_max, u_opt)))

            u_seq = [u_opt for _ in range(solver.horizon)]
            solve_info = {
                "solve_time_ms": 0.0,
                "n_iter": 0,
                "success": True,
                "obj_val": 0.0,
                "controller_mode": "rbc_deadband",
                "occupied": bool(occupied),
                "t_lower": float(t_lo),
                "t_upper": float(t_hi),
            }
        else:
            weather_fc = _get_weather_forecast(solver.horizon)
            u_opt, u_seq, solve_info = solver.solve(
                t_zone=t_zone,
                weather_forecast=weather_fc,
                u_prev=u_prev,
                time_s=t_s,
            )

        if export_solver_trace:
            solver_trace.append(
                {
                    "step_index": int(step_idx + 1),
                    "time_s": int(t_s),
                    "t_zone_degC": float(t_zone),
                    "u_prev_degC": float(u_prev),
                    "u_opt_degC": float(u_opt),
                    "u_sequence_degC": [float(u) for u in u_seq],
                    "solve_info": {
                        "solve_time_ms": float(solve_info.get("solve_time_ms", 0.0)),
                        "n_iter": int(solve_info.get("n_iter", 0)),
                        "success": bool(solve_info.get("success", False)),
                        "obj_val": float(solve_info.get("obj_val", 0.0)),
                    },
                }
            )

        control_cmd: dict[str, float] = {}
        # Apply the scalar MPC setpoint to all zone control value signals.
        # Note: For truly independent per-zone control, the solver would need to be
        # vectorized (multi-input optimization). Currently, we use the average zone
        # temperature and apply the resulting setpoint uniformly across all zones.
        for u_val_name in u_val_names:
            u_cmd = u_opt + 273.15 if _control_uses_kelvin(u_val_name) else u_opt
            control_cmd[u_val_name] = u_cmd
        # Apply same setpoint to system-level controls (e.g., supply temperature setpoint)
        for system_u_val_name in system_u_val_names:
            u_cmd = u_opt + 273.15 if _control_uses_kelvin(system_u_val_name) else u_opt
            control_cmd[system_u_val_name] = u_cmd
        for u_act_name in u_act_names:
            control_cmd[u_act_name] = 1.0
        for system_u_act_name in system_u_act_names:
            control_cmd[system_u_act_name] = 1.0
        for signal_name, signal_value in fixed_control_cmd.items():
            control_cmd[signal_name] = signal_value

        _write_live_snapshot(
            {
                "state": "waiting_advance",
                "step_index": step_idx + 1,
                "sim_time_s": t_s,
                "waited_on_advance_s": 0,
                "t_zone_degC": t_zone,
                "u_opt_degC": u_opt,
                "solve_info": solve_info,
                "control_cmd": control_cmd,
            }
        )

        advance_wall_start = time.perf_counter()
        heartbeat_s = max(0, int(advance_heartbeat_s))
        if heartbeat_s == 0:
            try:
                next_payload = client.advance(control_cmd)
            except Exception as exc:
                _write_live_snapshot(
                    {
                        "state": "advance_failed",
                        "step_index": step_idx + 1,
                        "sim_time_s": t_s,
                        "waited_on_advance_s": 0,
                        "t_zone_degC": t_zone,
                        "u_opt_degC": u_opt,
                        "solve_info": solve_info,
                        "control_cmd": control_cmd,
                        "error": str(exc),
                    }
                )
                raise AdvanceExecutionError(
                    step_index=step_idx + 1,
                    waited_s=0,
                    cause=exc,
                ) from exc
        else:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(client.advance, control_cmd)
                waited_s = 0
                while True:
                    try:
                        next_payload = future.result(timeout=heartbeat_s)
                        break
                    except FuturesTimeout:
                        waited_s += heartbeat_s
                        print(
                            f"  step {step_idx + 1:4d}/{n_steps} waiting on BOPTEST /advance ... "
                            f"{waited_s}s elapsed",
                            flush=True,
                        )
                        _write_live_snapshot(
                            {
                                "state": "waiting_advance",
                                "step_index": step_idx + 1,
                                "sim_time_s": t_s,
                                "waited_on_advance_s": waited_s,
                                "t_zone_degC": t_zone,
                                "u_opt_degC": u_opt,
                                "solve_info": solve_info,
                                "control_cmd": control_cmd,
                            }
                        )
                    except Exception as exc:
                        _write_live_snapshot(
                            {
                                "state": "advance_failed",
                                "step_index": step_idx + 1,
                                "sim_time_s": t_s,
                                "waited_on_advance_s": waited_s,
                                "t_zone_degC": t_zone,
                                "u_opt_degC": u_opt,
                                "solve_info": solve_info,
                                "control_cmd": control_cmd,
                                "error": str(exc),
                            }
                        )
                        raise AdvanceExecutionError(
                            step_index=step_idx + 1,
                            waited_s=waited_s,
                            cause=exc,
                        ) from exc
        advance_wall_s = time.perf_counter() - advance_wall_start

        # Record KPIs using current-step T_zone and power from the advance response.
        pwr = _read_power_components(next_payload)
        t_lo, t_hi = comfort_bounds(t_s, schedule=occupancy_schedule)
        occupied = is_occupied(t_s, occupancy_schedule)

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

        if (step_idx == 0) or ((step_idx + 1) % 12 == 0) or (step_idx == n_steps - 1):
            print(
                f"  step {step_idx + 1:4d}/{n_steps}  t_s={t_s:8d}  "
                f"T_zone={t_zone:.2f} degC  u={u_opt:.2f} degC  "
                f"solve={solve_info['solve_time_ms']:.1f}ms  "
                f"advance={advance_wall_s:.1f}s  "
                f"{'OK' if solve_info['success'] else 'WARN:infeasible'}",
                flush=True,
            )

        _write_live_snapshot(
            {
                "state": "step_completed",
                "step_index": step_idx + 1,
                "sim_time_s": t_s,
                "waited_on_advance_s": 0,
                "t_zone_degC": t_zone,
                "u_opt_degC": u_opt,
                "solve_info": solve_info,
                "advance_wall_s": advance_wall_s,
                "latest_payload": next_payload,
            }
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

    _write_live_snapshot(
        {
            "state": "episode_completed",
            "step_index": n_steps,
            "episode_wall_time_s": round(episode_wall_s, 2),
            "challenge_kpis": challenge_kpis,
            "diagnostic_kpis": diagnostic_kpis,
        }
    )

    return {
        "episode_id": episode["id"],
        "predictor": predictor_name,
        "split": episode.get("split", "unknown"),
        "weather_class": episode.get("weather_class", "unknown"),
        "case_name": case_name,
        "start_time_s": start_time_s,
        "control_interval_s": step_s,
        "n_steps": n_steps,
        "resolved_signals": {
            "zone_temp_signals": zone_signals,
            "outdoor_temp_signal": outdoor_signal,
            "solar_signal": solar_signal,
            "control_value_signals": u_val_names,
            "control_activate_signals": u_act_names,
            "system_control_value_signals": system_u_val_names,
            "system_control_activate_signals": system_u_act_names,
            "power_heating_signals": power_heat_names,
            "power_electric_signals": power_ele_names,
            "fixed_control_commands": fixed_control_cmd,
            "has_forecast_signals": bool(forecast_points),
        },
        "mapping_warnings": mapping_warnings,
        "kpi_summary": challenge_kpis,
        "challenge_kpis": challenge_kpis,
        "diagnostic_kpis": diagnostic_kpis,
        "boptest_kpis": boptest_kpis,
        "step_records": kpi.step_records(),
        "solver_trace_summary": {
            "enabled": bool(export_solver_trace),
            "n_solver_records": len(solver_trace),
            "final_solver_solution": solver_trace[-1] if solver_trace else None,
        },
        "solver_trace": solver_trace if export_solver_trace else [],
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="WP4 MPC episode runner.")
    parser.add_argument(
        "--predictor", choices=["rc", "pinn", "rbc"], required=True,
        help="Controller mode: 'rc' (whitebox RC-MPC), 'pinn' (surrogate-MPC), or 'rbc' (rule-based baseline).",
    )
    parser.add_argument(
        "--predictor-label",
        default="",
        help="Optional output/result label (e.g. rc_fast). Defaults to predictor name.",
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
        "--advance-timeout-s",
        type=int,
        default=300,
        help="Timeout in seconds for each /advance request to BOPTEST.",
    )
    parser.add_argument(
        "--advance-heartbeat-s",
        type=int,
        default=60,
        help="Emit a heartbeat log line every N seconds while waiting on /advance (0 disables).",
    )
    parser.add_argument(
        "--recover-from-queued",
        action="store_true",
        help="If startup stays Queued, stop the stuck test and retry selection once.",
    )
    parser.add_argument("--rc-scale-ua", type=float, default=1.0)
    parser.add_argument("--rc-scale-solar-gain", type=float, default=1.0)
    parser.add_argument("--rc-scale-hvac-gain", type=float, default=1.0)
    parser.add_argument("--rc-scale-capacity", type=float, default=1.0)
    parser.add_argument(
        "--rc-topology",
        choices=list(RCPredictor.SUPPORTED_TOPOLOGIES),
        default="1R1C",
        help="RC network topology used when --predictor rc.",
    )
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Skip episodes that already have a valid output JSON file.",
    )
    parser.add_argument(
        "--live-snapshot",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Write a sidecar .live.json snapshot for each episode with latest initialization/step state "
            "(use --no-live-snapshot to disable)."
        ),
    )
    parser.add_argument(
        "--retry-first-advance-failures",
        type=int,
        default=1,
        help=(
            "Automatically retry an episode after first-step /advance server failures/timeouts. "
            "Set to 0 to disable."
        ),
    )
    parser.add_argument(
        "--export-solver-trace",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Store per-step MPC solver sequences and solve metadata in output JSON "
            "(use --no-export-solver-trace to reduce file size)."
        ),
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
        print("Loading PINN predictor ...", flush=True)
        predictor = PINNPredictor(ckpt_path)
        predictor_name = "pinn"
    elif args.predictor == "rc":
        print("Loading RC predictor from checkpoint ...", flush=True)
        rc_base = RCPredictor.from_checkpoint(ckpt_path, topology=args.rc_topology)
        predictor = RCPredictor(
            ua=rc_base.ua * args.rc_scale_ua,
            solar_gain=rc_base.solar_gain * args.rc_scale_solar_gain,
            hvac_gain=rc_base.hvac_gain * args.rc_scale_hvac_gain,
            capacity=rc_base.capacity * args.rc_scale_capacity,
            topology=args.rc_topology,
        )
        predictor_name = "rc"
        print(
            f"  RC params: ua={predictor.ua:.4f}, solar_gain={predictor.solar_gain:.4f}, "
            f"hvac_gain={predictor.hvac_gain:.4f}, capacity={predictor.capacity:.4f}"
            f" | topology={predictor.topology}"
            f" | scales=({args.rc_scale_ua:.3f},{args.rc_scale_solar_gain:.3f},"
            f"{args.rc_scale_hvac_gain:.3f},{args.rc_scale_capacity:.3f})",
            flush=True,
        )
    else:
        print("Using RBC controller mode (no interior predictor load).", flush=True)
        predictor = None
        predictor_name = "rbc"

    predictor_label = args.predictor_label.strip() or predictor_name

    # ------------------------------------------------------------------ solver
    case_mpc_overrides = case_mappings.get("mpc_overrides", {})
    predictor_mpc_overrides = (case_mappings.get("predictor_mpc_overrides", {}) or {}).get(predictor_name, {})
    mpc = _deep_merge(mpc_cfg.get("mpc", {}), case_mpc_overrides)
    mpc = _deep_merge(mpc, predictor_mpc_overrides)
    horizon_s = int(mpc.get("horizon_s", 21600))
    dt_s = int(defaults["control_interval_s"])
    horizon_steps = horizon_s // dt_s

    if case_mpc_overrides:
        print(f"Applying case-specific MPC overrides: {json.dumps(case_mpc_overrides)}", flush=True)
    if predictor_mpc_overrides:
        print(
            f"Applying predictor-specific MPC overrides for {predictor_name}: "
            f"{json.dumps(predictor_mpc_overrides)}",
            flush=True,
        )

    comfort_occ = tuple(mpc.get("comfort_bounds_degC", {}).get("occupied", [21.0, 24.0]))
    comfort_unocc = tuple(mpc.get("comfort_bounds_degC", {}).get("unoccupied", [15.0, 30.0]))
    weights = mpc.get("objective_weights", {})
    
    # Extract occupancy schedule from case mappings (optional)
    occ_cfg = case_mappings.get("occupancy_schedule", {}) or {}
    occupancy_schedule_local = OccupancySchedule.from_dict(occ_cfg) if occ_cfg else None

    if predictor_name == "rbc":
        solver = _RBCSolverAdapter(
            horizon_steps=horizon_steps,
            dt_s=float(dt_s),
            u_min=float(mpc.get("u_min_degC", 18.0)),
            u_max=float(mpc.get("u_max_degC", 26.0)),
        )
    else:
        assert predictor is not None
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
            occupancy_schedule=occupancy_schedule_local,
        )

    # ------------------------------------------------------------------ connect
    boptest_url = _resolve_boptest_url(args.url)
    print(f"Connecting to BOPTEST at {boptest_url} ...", flush=True)
    client = BoptestClient(boptest_url, advance_timeout_s=args.advance_timeout_s)

    def _select_case_and_wait(stage_label: str) -> str:
        print(f"Selecting test case '{args.case}' ({stage_label}) ...", flush=True)
        selected_testid = client.select_test_case(args.case)
        print(f"  testid={selected_testid}", flush=True)
        print("Waiting for Running state ...", flush=True)
        try:
            client.wait_running(timeout_s=args.startup_timeout_s)
        except TimeoutError:
            if not args.recover_from_queued:
                raise
            print("Startup timeout in Queued state. Attempting one-time recovery ...", flush=True)
            try:
                stopped = client.stop()
                print(f"  stop({selected_testid}) -> {stopped}", flush=True)
            except Exception as exc:
                print(f"  Warning: stop failed: {exc}", flush=True)

            print(f"Re-selecting test case '{args.case}' after cleanup ...", flush=True)
            selected_testid = client.select_test_case(args.case)
            print(f"  retry testid={selected_testid}", flush=True)
            print("Waiting for Running state (retry) ...", flush=True)
            client.wait_running(timeout_s=args.startup_timeout_s)

        return selected_testid

    if args.reuse_testid:
        print(f"Attaching to testid {args.reuse_testid} ...", flush=True)
        client.attach_testid(args.reuse_testid)
        owns_test_session = False
    else:
        owns_test_session = True
        _select_case_and_wait("initial")

    # ------------------------------------------------------------------ run
    output_dir = ROOT / args.output_dir / predictor_label
    _ensure_dir(output_dir)

    try:
        for episode in target_episodes:
            ep_id = episode["id"]
            out_path = output_dir / f"{ep_id}.json"
            live_snapshot_path = out_path.with_suffix(".live.json") if args.live_snapshot else None

            if args.resume_existing and _has_valid_existing_output(out_path, ep_id, predictor_label):
                print(f"Skipping episode {ep_id}: existing output found at {out_path}", flush=True)
                continue

            print(f"\n{'='*60}", flush=True)
            print(f"Episode {ep_id} | predictor={predictor_label}", flush=True)
            print(f"{'='*60}", flush=True)
            if live_snapshot_path is not None:
                print(f"  Live snapshot -> {live_snapshot_path}", flush=True)

            max_attempts = 1 + max(0, int(args.retry_first_advance_failures))
            result: dict[str, Any] | None = None
            run_error: Exception | None = None

            for attempt_index in range(1, max_attempts + 1):
                try:
                    result = run_mpc_episode(
                        client=client,
                        case_name=args.case,
                        case_mappings=case_mappings,
                        episode=episode,
                        defaults=defaults,
                        solver=solver,
                        predictor_name=predictor_label,
                        predictor_base=predictor_name,
                        occupancy_schedule=occupancy_schedule_local,
                        advance_heartbeat_s=args.advance_heartbeat_s,
                        live_snapshot_path=live_snapshot_path,
                        attempt_index=attempt_index,
                        max_attempts=max_attempts,
                        export_solver_trace=bool(args.export_solver_trace),
                    )
                    run_error = None
                    break
                except Exception as exc:
                    run_error = exc
                    can_retry = (
                        attempt_index < max_attempts
                        and owns_test_session
                        and _is_retriable_first_advance_failure(exc)
                    )
                    if not can_retry:
                        break

                    print(
                        f"  First-step /advance failed on attempt {attempt_index}/{max_attempts} "
                        f"({exc}). Recovering BOPTEST session and retrying once ...",
                        flush=True,
                    )
                    if live_snapshot_path is not None:
                        _write_json_atomic(
                            live_snapshot_path,
                            {
                                "episode_id": ep_id,
                                "predictor_label": predictor_label,
                                "case_name": args.case,
                                "state": "retry_scheduled",
                                "attempt_index": attempt_index,
                                "next_attempt_index": attempt_index + 1,
                                "max_attempts": max_attempts,
                                "error": str(exc),
                                "updated_at_unix_s": time.time(),
                            },
                        )

                    try:
                        stopped = client.stop()
                        print(f"  stop(current_testid) -> {stopped}", flush=True)
                    except Exception as stop_exc:
                        print(f"  Warning: stop before retry failed: {stop_exc}", flush=True)

                    _select_case_and_wait(f"retry-{attempt_index + 1}")

            try:
                if result is None:
                    assert run_error is not None
                    raise run_error

                result["mpc_config"] = {
                    "horizon_s": horizon_s,
                    "u_min_degC": float(mpc.get("u_min_degC", 18.0)),
                    "u_max_degC": float(mpc.get("u_max_degC", 26.0)),
                    "comfort_bounds_degC": mpc.get("comfort_bounds_degC", {}),
                    "objective_weights": mpc.get("objective_weights", {}),
                    "solver_maxiter": int(mpc.get("solver_maxiter", 100)),
                    "solver_ftol": float(mpc.get("solver_ftol", 1e-4)),
                }
                result["predictor_base"] = predictor_name
                result["predictor_label"] = predictor_label
                if predictor_name == "rc":
                    result["rc_variant"] = {
                        "topology": predictor.topology,
                        "scale_ua": args.rc_scale_ua,
                        "scale_solar_gain": args.rc_scale_solar_gain,
                        "scale_hvac_gain": args.rc_scale_hvac_gain,
                        "scale_capacity": args.rc_scale_capacity,
                        "ua": predictor.ua,
                        "solar_gain": predictor.solar_gain,
                        "hvac_gain": predictor.hvac_gain,
                        "capacity": predictor.capacity,
                    }
                elif predictor_name == "rbc":
                    result["rbc_variant"] = {
                        "type": "deadband_thermostat",
                        "horizon_steps": int(horizon_steps),
                        "u_min_degC": float(mpc.get("u_min_degC", 18.0)),
                        "u_max_degC": float(mpc.get("u_max_degC", 26.0)),
                    }
                with out_path.open("w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)
                print(f"  Saved -> {out_path}", flush=True)
                summary = result.get("solver_trace_summary", {})
                if summary.get("enabled"):
                    final_sol = summary.get("final_solver_solution") or {}
                    print(
                        "  Solver trace: "
                        f"records={summary.get('n_solver_records', 0)} "
                        f"final_u_opt={final_sol.get('u_opt_degC')} "
                        f"final_obj={((final_sol.get('solve_info') or {}).get('obj_val'))}",
                        flush=True,
                    )
                print("  Challenge KPIs:", json.dumps(result["challenge_kpis"], indent=4), flush=True)
                print("  Diagnostic KPIs:", json.dumps(result["diagnostic_kpis"], indent=4), flush=True)
            except Exception as exc:
                print(f"  ERROR running episode {ep_id}: {exc}", flush=True)
                import traceback
                traceback.print_exc()
    finally:
        if owns_test_session:
            try:
                stopped = client.stop()
                print(f"Stopped MPC test session: {stopped}", flush=True)
            except Exception as exc:
                print(f"Warning: failed to stop MPC test session: {exc}", flush=True)

    print("\nAll done.", flush=True)


if __name__ == "__main__":
    main()
