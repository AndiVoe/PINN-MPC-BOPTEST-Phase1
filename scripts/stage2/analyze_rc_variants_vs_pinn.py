#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_episode_file(root: Path, episode: str) -> Path | None:
    """Find an episode output file under a case directory.

    The stage 2 runners sometimes write into nested directories such as
    `pinn/pinn/te_std_01.json`, so we resolve files recursively instead of
    assuming a single fixed layout.
    """
    direct = root / f"{episode}.json"
    if direct.exists():
        return direct

    matches = sorted(root.rglob(f"{episode}.json"))
    if matches:
        return matches[0]
    return None


def _metric_payload(payload: dict[str, Any]) -> dict[str, float | None]:
    diag = payload.get("diagnostic_kpis", {})
    chall = payload.get("challenge_kpis", {})
    tdis = chall.get("tdis_tot") if isinstance(chall.get("tdis_tot"), dict) else {}
    cost = chall.get("cost_tot") if isinstance(chall.get("cost_tot"), dict) else {}
    return {
        "comfort_Kh": float(diag.get("comfort_Kh")) if diag.get("comfort_Kh") is not None else None,
        "total_energy_Wh": float(diag.get("total_energy_Wh")) if diag.get("total_energy_Wh") is not None else None,
        "solve_ms": float(diag.get("mpc_solve_time_mean_ms")) if diag.get("mpc_solve_time_mean_ms") is not None else None,
        "cost_tot": float(cost.get("value")) if isinstance(cost, dict) and cost.get("value") is not None else None,
        "tdis_tot": float(tdis.get("value")) if isinstance(tdis, dict) and tdis.get("value") is not None else None,
    }


def _score(metrics: dict[str, float | None]) -> float:
    # Lower is better. Cost + discomfort are primary, energy secondary.
    cost = metrics.get("cost_tot") or 0.0
    comfort = metrics.get("comfort_Kh") or 0.0
    energy_kwh = (metrics.get("total_energy_Wh") or 0.0) / 1000.0
    return 10.0 * cost + 2.0 * comfort + 0.01 * energy_kwh


def main() -> int:
    parser = argparse.ArgumentParser(description="Pick best RC variant and compare against PINN.")
    parser.add_argument("--rc-root", default="results/eu_rc_vs_pinn_stage2/raw")
    parser.add_argument("--pinn-root", default="results/eu_rc_vs_pinn_stage2/raw")
    parser.add_argument("--episode", default="te_std_01")
    parser.add_argument("--out-json", default="results/eu_rc_vs_pinn_stage2/best_rc_vs_pinn_summary.json")
    args = parser.parse_args()

    rc_root = Path(args.rc_root)
    pinn_root = Path(args.pinn_root)

    per_case: list[dict[str, Any]] = []
    for case_dir in sorted(rc_root.glob("*")):
        if not case_dir.is_dir():
            continue

        variant_rows: list[dict[str, Any]] = []
        for variant_dir in sorted(case_dir.glob("*")):
            ep_file = variant_dir / f"{args.episode}.json"
            if not ep_file.exists():
                continue
            payload = _load_json(ep_file)
            m = _metric_payload(payload)
            variant_rows.append({
                "variant": variant_dir.name,
                "metrics": m,
                "score": _score(m),
                "file": ep_file.as_posix(),
            })

        if not variant_rows:
            continue

        best = sorted(variant_rows, key=lambda r: r["score"])[0]
        pinn_case_root = pinn_root / case_dir.name / "pinn"
        pinn_file = _find_episode_file(pinn_case_root, args.episode)
        if pinn_file is None:
            continue
        pinn_payload = _load_json(pinn_file)
        pinn_metrics = _metric_payload(pinn_payload)

        per_case.append(
            {
                "case": case_dir.name,
                "episode": args.episode,
                "best_rc_variant": best["variant"],
                "best_rc_metrics": best["metrics"],
                "best_rc_score": best["score"],
                "pinn_metrics": pinn_metrics,
                "pinn_score": _score(pinn_metrics),
                "delta_cost_tot_pinn_minus_best_rc": (pinn_metrics.get("cost_tot") or 0.0) - (best["metrics"].get("cost_tot") or 0.0),
                "delta_comfort_Kh_pinn_minus_best_rc": (pinn_metrics.get("comfort_Kh") or 0.0) - (best["metrics"].get("comfort_Kh") or 0.0),
                "delta_energy_Wh_pinn_minus_best_rc": (pinn_metrics.get("total_energy_Wh") or 0.0) - (best["metrics"].get("total_energy_Wh") or 0.0),
                "delta_solve_ms_pinn_minus_best_rc": (pinn_metrics.get("solve_ms") or 0.0) - (best["metrics"].get("solve_ms") or 0.0),
            }
        )

    out = {
        "episode": args.episode,
        "n_cases": len(per_case),
        "cases": per_case,
        "aggregate": {
            "mean_delta_cost_tot": mean([x["delta_cost_tot_pinn_minus_best_rc"] for x in per_case]) if per_case else None,
            "mean_delta_comfort_Kh": mean([x["delta_comfort_Kh_pinn_minus_best_rc"] for x in per_case]) if per_case else None,
            "mean_delta_energy_Wh": mean([x["delta_energy_Wh_pinn_minus_best_rc"] for x in per_case]) if per_case else None,
            "mean_delta_solve_ms": mean([x["delta_solve_ms_pinn_minus_best_rc"] for x in per_case]) if per_case else None,
            "pinn_better_cases_by_score": sum(1 for x in per_case if x["pinn_score"] < x["best_rc_score"]),
            "best_rc_better_cases_by_score": sum(1 for x in per_case if x["pinn_score"] >= x["best_rc_score"]),
        },
    }

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote: {out_path.as_posix()}")
    print(json.dumps(out["aggregate"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
