"""Validate discomfort metric comparability and definition mismatch risk.

This script compares RC and PINN MPC result files episode-by-episode and
computes discomfort in two ways:
1) Challenge metric from BOPTEST (`boptest_kpis.tdis_tot`)
2) Local diagnostic discomfort from step records based on logged bounds

It writes a CSV report and exits with code 0 when all paired episodes are
comparable at metadata level. It does not fail on metric mismatch because that
can be expected when definitions differ; instead, it emits explicit risk flags.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _compute_local_discomfort_kh(step_records: list[dict[str, Any]], dt_s: int) -> float:
    dt_h = float(dt_s) / 3600.0
    total = 0.0
    for rec in step_records:
        t_zone = float(rec["t_zone"])
        t_lower = float(rec["t_lower"])
        t_upper = float(rec["t_upper"])
        below = max(t_lower - t_zone, 0.0)
        above = max(t_zone - t_upper, 0.0)
        total += below + above
    return total * dt_h


def _safe_float(value: Any) -> float:
    if value is None:
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _episode_meta(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode_id": data.get("episode_id"),
        "split": data.get("split"),
        "weather_class": data.get("weather_class"),
        "case_name": data.get("case_name"),
        "start_time_s": data.get("start_time_s"),
        "control_interval_s": data.get("control_interval_s"),
        "n_steps": data.get("n_steps"),
        "step_count": len(data.get("step_records", [])),
    }


def _comparable(pinn_meta: dict[str, Any], rc_meta: dict[str, Any]) -> tuple[bool, list[str]]:
    diffs: list[str] = []
    keys = [
        "episode_id",
        "split",
        "weather_class",
        "case_name",
        "start_time_s",
        "control_interval_s",
        "n_steps",
        "step_count",
    ]
    for key in keys:
        if pinn_meta.get(key) != rc_meta.get(key):
            diffs.append(key)
    return (len(diffs) == 0, diffs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate discomfort parity across MPC result files.")
    parser.add_argument("--results-root", default="results/mpc_phase1", help="Root directory with rc/ and pinn/ subfolders.")
    parser.add_argument("--output", default="results/mpc_phase1/discomfort_parity_report.csv", help="CSV report path.")
    parser.add_argument("--epsilon", type=float, default=1e-6, help="Tolerance for zero/non-zero checks.")
    args = parser.parse_args()

    root = Path(args.results_root)
    pinn_dir = root / "pinn"
    rc_dir = root / "rc"
    output = Path(args.output)

    if not pinn_dir.exists() or not rc_dir.exists():
        raise FileNotFoundError(f"Expected both predictor folders under {root}")

    pinn_files = {p.stem: p for p in pinn_dir.glob("*.json")}
    rc_files = {p.stem: p for p in rc_dir.glob("*.json")}

    episodes = sorted(set(pinn_files) | set(rc_files))
    rows: list[dict[str, Any]] = []

    for ep in episodes:
        pinn_path = pinn_files.get(ep)
        rc_path = rc_files.get(ep)
        if pinn_path is None or rc_path is None:
            rows.append(
                {
                    "episode": ep,
                    "comparable": False,
                    "missing_pair": True,
                    "diff_fields": "missing predictor file",
                }
            )
            continue

        pinn = _load_json(pinn_path)
        rc = _load_json(rc_path)

        pinn_meta = _episode_meta(pinn)
        rc_meta = _episode_meta(rc)
        is_comparable, diffs = _comparable(pinn_meta, rc_meta)

        pinn_tdis = _safe_float(((pinn.get("boptest_kpis") or {}).get("tdis_tot")))
        rc_tdis = _safe_float(((rc.get("boptest_kpis") or {}).get("tdis_tot")))

        pinn_local = _compute_local_discomfort_kh(
            pinn.get("step_records", []), int(pinn.get("control_interval_s", 900))
        )
        rc_local = _compute_local_discomfort_kh(
            rc.get("step_records", []), int(rc.get("control_interval_s", 900))
        )

        mismatch_risk = (
            abs(rc_tdis) <= args.epsilon
            and rc_local > args.epsilon
            and abs(pinn_tdis) <= args.epsilon
            and abs(pinn_local) <= args.epsilon
        )

        rows.append(
            {
                "episode": ep,
                "comparable": is_comparable,
                "missing_pair": False,
                "diff_fields": "|".join(diffs),
                "split": pinn_meta["split"],
                "weather_class": pinn_meta["weather_class"],
                "n_steps": pinn_meta["n_steps"],
                "dt_s": pinn_meta["control_interval_s"],
                "pinn_boptest_tdis_tot": round(pinn_tdis, 6),
                "rc_boptest_tdis_tot": round(rc_tdis, 6),
                "pinn_local_discomfort_kh": round(pinn_local, 6),
                "rc_local_discomfort_kh": round(rc_local, 6),
                "definition_mismatch_risk": mismatch_risk,
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "episode",
        "comparable",
        "missing_pair",
        "diff_fields",
        "split",
        "weather_class",
        "n_steps",
        "dt_s",
        "pinn_boptest_tdis_tot",
        "rc_boptest_tdis_tot",
        "pinn_local_discomfort_kh",
        "rc_local_discomfort_kh",
        "definition_mismatch_risk",
    ]
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    comparable_count = sum(1 for r in rows if r.get("comparable") is True)
    risk_count = sum(1 for r in rows if r.get("definition_mismatch_risk") is True)

    print(f"Episodes processed: {len(rows)}")
    print(f"Comparable pairs:  {comparable_count}")
    print(f"Risk flags:        {risk_count}")
    print(f"Report written:    {output}")

    # Metadata comparability is hard requirement; mismatch risk is a diagnostic output.
    all_comparable = all(r.get("comparable") is True for r in rows)
    return 0 if all_comparable else 2


if __name__ == "__main__":
    raise SystemExit(main())
