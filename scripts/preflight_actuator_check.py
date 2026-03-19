#!/usr/bin/env python3
"""
Preflight actuator-effectiveness check.

Tests whether BOPTEST control signals actually affect zone temperature.
Flags cases where heating setpoint changes have minimal thermal response,
indicating non-responsive actuators or plant issues.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpc.boptest import BoptestClient


def run_preflight_check(
    base_url: str,
    case_name: str,
    pulse_duration_s: int = 3600,  # 1 hour pulse
    pulse_setpoint_low: float = 18.0,
    pulse_setpoint_high: float = 24.0,
    baseline_duration_s: int = 3600,
) -> dict[str, Any]:
    """
    Test actuator responsiveness by measuring temperature response to setpoint pulse.

    Parameters
    ----------
    base_url : str
        BOPTEST API URL.
    case_name : str
        Test case name (e.g., 'bestest_hydronic_heat_pump').
    pulse_duration_s : int
        Duration to hold high setpoint (default 3600 = 1 hour).
    pulse_setpoint_low : float
        Low setpoint for baseline (degC).
    pulse_setpoint_high : float
        High setpoint for pulse (degC).
    baseline_duration_s : int
        Duration to hold baseline low setpoint before pulse (default 3600 = 1 hour).

    Returns
    -------
    result : dict
        Contains 'status' (PASS/WARN/FAIL), 't_response_delta_K' (observed temperature rise),
        'setpoint_applied' (actual setpoint commands sent), and 'recommendation'.
    """

    client = BoptestClient(base_url)

    try:
        print(f"[PREFLIGHT] Selecting test case: {case_name}")
        testid = client.select(case_name)
        print(f"[PREFLIGHT] Test ID: {testid}")

        # Baseline period: establish steady-state with low setpoint.
        print(f"[PREFLIGHT] Baseline phase ({baseline_duration_s}s at {pulse_setpoint_low}°C)")
        client.initialize(start_time_s=0, warmup_period_s=0)
        client.set_step(900)

        baseline_temps: list[float] = []
        for _ in range(baseline_duration_s // 900):
            current = client.get_measurements()
            temps = [v for k, v in current.items() if "tzon" in k.lower() or "troo" in k.lower()]
            if temps:
                baseline_temps.append(sum(temps) / len(temps))
            client.inputs = {"oveTSet_u": pulse_setpoint_low}  # Low setpoint
            client.step()

        baseline_temp_mean = sum(baseline_temps) / len(baseline_temps) if baseline_temps else 0.0
        print(f"[PREFLIGHT] Baseline mean temperature: {baseline_temp_mean:.2f}°C")

        # Pulse phase: apply high setpoint and monitor response.
        print(f"[PREFLIGHT] Pulse phase ({pulse_duration_s}s at {pulse_setpoint_high}°C)")
        pulse_temps: list[float] = []
        for _ in range(pulse_duration_s // 900):
            current = client.get_measurements()
            temps = [v for k, v in current.items() if "tzon" in k.lower() or "troo" in k.lower()]
            if temps:
                pulse_temps.append(sum(temps) / len(temps))
            client.inputs = {"oveTSet_u": pulse_setpoint_high}  # High setpoint
            client.step()

        pulse_temp_mean = sum(pulse_temps) / len(pulse_temps) if pulse_temps else 0.0
        pulse_temp_max = max(pulse_temps) if pulse_temps else 0.0
        temp_delta = pulse_temp_mean - baseline_temp_mean
        temp_delta_max = pulse_temp_max - baseline_temp_mean

        print(f"[PREFLIGHT] Pulse mean temperature: {pulse_temp_mean:.2f}°C")
        print(f"[PREFLIGHT] Temperature rise: {temp_delta:.2f}K (max: {temp_delta_max:.2f}K)")

        # Evaluation thresholds.
        if temp_delta < 0.5:  # Less than 0.5 K rise
            status = "FAIL"
            recommendation = "SKIP: Heating control is non-responsive; skip MPC benchmarking."
        elif temp_delta < 1.5:  # Less than 1.5 K rise
            status = "WARN"
            recommendation = "CAUTION: Weak heating response; expect poor comfort control."
        else:
            status = "PASS"
            recommendation = "OK: Heating response is adequate; proceed with benchmarking."

        result = {
            "status": status,
            "case_name": case_name,
            "testid": testid,
            "baseline_temp_mean_degC": round(baseline_temp_mean, 2),
            "pulse_temp_mean_degC": round(pulse_temp_mean, 2),
            "t_response_delta_K": round(temp_delta, 2),
            "t_response_delta_max_K": round(temp_delta_max, 2),
            "setpoint_low_degC": pulse_setpoint_low,
            "setpoint_high_degC": pulse_setpoint_high,
            "duration_baseline_s": baseline_duration_s,
            "duration_pulse_s": pulse_duration_s,
            "recommendation": recommendation,
        }

        try:
            client.stop(testid)
        except Exception:
            pass

        return result

    except Exception as e:
        return {
            "status": "ERROR",
            "case_name": case_name,
            "error_message": str(e),
            "recommendation": f"SKIP: Test case initialization failed: {e}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preflight actuator-responsiveness check for BOPTEST cases."
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="BOPTEST API URL")
    parser.add_argument(
        "--case", required=True, help="Test case name (e.g., bestest_hydronic_heat_pump)"
    )
    parser.add_argument(
        "--baseline-duration-s", type=int, default=3600, help="Baseline phase duration (s)"
    )
    parser.add_argument(
        "--pulse-duration-s", type=int, default=3600, help="Pulse phase duration (s)"
    )
    parser.add_argument(
        "--output-dir", help="Directory to save results; if provided, saves JSON report"
    )

    args = parser.parse_args()

    result = run_preflight_check(
        base_url=args.url,
        case_name=args.case,
        baseline_duration_s=args.baseline_duration_s,
        pulse_duration_s=args.pulse_duration_s,
    )

    # Print result.
    print("\n" + "=" * 60)
    print(f"PREFLIGHT RESULT: {result['status']}")
    print(f"Case: {result['case_name']}")
    if result["status"] != "ERROR":
        print(f"  Temperature response: {result['t_response_delta_K']}K (max {result['t_response_delta_max_K']}K)")
        print(f"  Baseline temp: {result['baseline_temp_mean_degC']}°C")
        print(f"  Pulse temp: {result['pulse_temp_mean_degC']}°C")
    print(f"Recommendation: {result['recommendation']}")
    print("=" * 60)

    if args.output_dir:
        output_path = Path(args.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        report_file = output_path / f"preflight_{args.case}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\nReport saved to: {report_file}")

    return 0 if result["status"] == "PASS" else (1 if result["status"] == "ERROR" else 2)


if __name__ == "__main__":
    sys.exit(main())
