#!/usr/bin/env python3
"""
Compare top-3 autotuned MPC candidates from the full validation batch.

Reads results produced by run_top3_full_validation.ps1 (or its equivalent)
and generates a markdown report that ranks the three candidates across all
four full-validation episodes using comfort, energy, solve-time, and combined
normalised score.

Usage::

    python scripts/compare_top3_validation.py
    python scripts/compare_top3_validation.py \\
        --plan configs/autotune_top3_full_validation.yaml \\
        --report results/mpc_tuning_eval/autotune_v1_10cand/full_validation/comparison_report.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def cv(obj: Any) -> float:
    """Extract numeric value from a BOPTEST KPI dict or plain scalar."""
    if isinstance(obj, dict):
        return float(obj.get("value", np.nan))
    if obj is None:
        return np.nan
    return float(obj)


def get_metrics(payload: dict[str, Any]) -> dict[str, float]:
    diag = payload.get("diagnostic_kpis") or {}
    chal = payload.get("challenge_kpis") or {}
    return {
        "comfort_Kh":   float(diag.get("comfort_Kh", np.nan)),
        "energy_Wh":    float(diag.get("total_energy_Wh", np.nan)),
        "smoothness":   float(diag.get("control_smoothness", np.nan)),
        "solve_ms":     float(diag.get("mpc_solve_time_mean_ms", np.nan)),
        "tdis_tot":     cv(chal.get("tdis_tot")),
        "cost_tot":     cv(chal.get("cost_tot")),
    }


def fmt(v: float, digits: int = 3) -> str:
    if not np.isfinite(v):
        return "—"
    return f"{v:.{digits}f}"


def mean_finite(vals: list[float]) -> float:
    arr = [v for v in vals if np.isfinite(v)]
    return float(np.mean(arr)) if arr else np.nan


# ---------------------------------------------------------------------------
# Normalised score (same convention as autotune_mpc_weights.py)
# ---------------------------------------------------------------------------

def normalised_score(
    comfort: float,
    energy: float,
    solve_ms: float,
    ref_comfort: float,
    ref_energy: float,
    ref_solve: float,
    w_comfort: float = 0.5,
    w_energy: float = 0.4,
    w_solve: float = 0.1,
) -> float:
    """Compute a weighted average of per-metric ratios relative to reference values.

    Each finite metric contributes (weight * metric / reference) to the sum.
    Weights are re-normalised to the subset of available metrics, so missing or
    infinite values are silently excluded without distorting the score.
    Returns np.nan when no valid metric/reference pairs are available.
    Lower score is better.
    """
    parts: list[float] = []
    weights: list[float] = []
    if np.isfinite(comfort) and np.isfinite(ref_comfort) and ref_comfort > 1e-9:
        parts.append(w_comfort * comfort / ref_comfort)
        weights.append(w_comfort)
    if np.isfinite(energy) and np.isfinite(ref_energy) and ref_energy > 1e-9:
        parts.append(w_energy * energy / ref_energy)
        weights.append(w_energy)
    if np.isfinite(solve_ms) and np.isfinite(ref_solve) and ref_solve > 1e-9:
        parts.append(w_solve * solve_ms / ref_solve)
        weights.append(w_solve)
    if not parts:
        return np.nan
    return sum(parts) / sum(weights)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Compare top-3 full-validation candidates.")
    parser.add_argument(
        "--plan",
        default="configs/autotune_top3_full_validation.yaml",
        help="Path to the full-validation plan YAML (default: configs/autotune_top3_full_validation.yaml)",
    )
    parser.add_argument(
        "--report",
        default=None,
        help=(
            "Output markdown report path. "
            "Defaults to <output_root>/comparison_report.md from the plan."
        ),
    )
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"ERROR: plan file not found: {plan_path}")
        return 1

    plan = load_yaml(plan_path)
    val = plan.get("validation") or {}
    episodes: list[str] = val.get("episodes") or []
    output_root = Path(val.get("output_root") or "results/mpc_tuning_eval/autotune_v1_10cand/full_validation")

    candidates_cfg: list[dict[str, Any]] = plan.get("candidates") or []
    if not candidates_cfg:
        print("ERROR: no candidates found in plan file.")
        return 1
    if not episodes:
        print("ERROR: no episodes found in plan file.")
        return 1

    report_path = Path(args.report) if args.report else output_root / "comparison_report.md"

    # ------------------------------------------------------------------
    # Collect results
    # ------------------------------------------------------------------
    # cand_results[cand_id][episode] = metrics dict | None
    cand_results: dict[str, dict[str, dict[str, float] | None]] = {}

    missing: list[str] = []
    for cand in candidates_cfg:
        cand_id: str = cand["id"]
        cand_results[cand_id] = {}
        for ep in episodes:
            result_file = output_root / cand_id / f"{ep}.json"
            if result_file.exists():
                try:
                    payload = load_json(result_file)
                    cand_results[cand_id][ep] = get_metrics(payload)
                except Exception as exc:
                    print(f"WARNING: could not parse {result_file}: {exc}")
                    cand_results[cand_id][ep] = None
            else:
                cand_results[cand_id][ep] = None
                missing.append(str(result_file))

    if missing:
        print(f"WARNING: {len(missing)} result file(s) not found (validation may be incomplete):")
        for m in missing[:10]:
            print(f"  {m}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")

    # ------------------------------------------------------------------
    # Per-candidate aggregate means
    # ------------------------------------------------------------------
    agg: dict[str, dict[str, float]] = {}
    for cand in candidates_cfg:
        cid = cand["id"]
        rows = [m for m in cand_results[cid].values() if m is not None]
        agg[cid] = {
            "comfort_Kh":  mean_finite([r["comfort_Kh"] for r in rows]),
            "energy_Wh":   mean_finite([r["energy_Wh"] for r in rows]),
            "smoothness":  mean_finite([r["smoothness"] for r in rows]),
            "solve_ms":    mean_finite([r["solve_ms"] for r in rows]),
            "tdis_tot":    mean_finite([r["tdis_tot"] for r in rows]),
            "cost_tot":    mean_finite([r["cost_tot"] for r in rows]),
            "n_available": float(len(rows)),
        }

    # Reference = cross-candidate mean for each metric (used for normalised score)
    def cross_candidate_mean(key: str) -> float:
        return mean_finite([agg[c][key] for c in agg])

    ref_comfort = cross_candidate_mean("comfort_Kh")
    ref_energy  = cross_candidate_mean("energy_Wh")
    ref_solve   = cross_candidate_mean("solve_ms")

    for cid in agg:
        agg[cid]["norm_score"] = normalised_score(
            agg[cid]["comfort_Kh"], agg[cid]["energy_Wh"], agg[cid]["solve_ms"],
            ref_comfort, ref_energy, ref_solve,
        )

    ranked = sorted(candidates_cfg, key=lambda c: agg[c["id"]].get("norm_score", np.inf))
    # Only designate a best candidate when at least one result is available
    has_any_data = any(agg[c["id"]]["n_available"] > 0 for c in candidates_cfg)
    best_id = ranked[0]["id"] if (ranked and has_any_data) else None

    # ------------------------------------------------------------------
    # Build markdown report
    # ------------------------------------------------------------------
    lines: list[str] = []
    lines.append("# Top-3 Full Validation: Candidate Comparison Report")
    lines.append("")
    lines.append(f"- Plan file: `{plan_path.as_posix()}`")
    lines.append(f"- Output root: `{output_root.as_posix()}`")
    lines.append(f"- Episodes evaluated: {', '.join(f'`{e}`' for e in episodes)}")
    cand_ids_str = ", ".join(f"`{c['id']}`" for c in candidates_cfg)
    lines.append(f"- Candidates: {cand_ids_str}")
    lines.append("")

    # Episode-level table
    lines.append("## Results by Candidate and Episode")
    lines.append("")
    header_cols = ["Candidate", "Episode", "comfort_Kh", "energy_Wh", "smoothness", "solve_ms", "tdis_tot", "cost_tot"]
    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("| " + " | ".join(["---"] + ["---:"] * (len(header_cols) - 1)) + " |")

    for cand in candidates_cfg:
        cid = cand["id"]
        for ep in episodes:
            m = cand_results[cid].get(ep)
            if m is None:
                row = [cid, ep] + ["—"] * 6
            else:
                row = [
                    cid, ep,
                    fmt(m["comfort_Kh"], 4),
                    fmt(m["energy_Wh"], 0),
                    fmt(m["smoothness"], 4),
                    fmt(m["solve_ms"], 1),
                    fmt(m["tdis_tot"], 4),
                    fmt(m["cost_tot"], 5),
                ]
            lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    # Aggregate summary table
    lines.append("## Aggregate Summary (mean across available episodes)")
    lines.append("")
    agg_cols = ["Candidate", "episodes", "comfort_Kh", "energy_Wh", "smoothness", "solve_ms", "tdis_tot", "cost_tot", "norm_score"]
    lines.append("| " + " | ".join(agg_cols) + " |")
    lines.append("| " + " | ".join(["---"] + ["---:"] * (len(agg_cols) - 1)) + " |")

    for cand in ranked:
        cid = cand["id"]
        a = agg[cid]
        marker = " ✓" if cid == best_id else ""
        row = [
            f"{cid}{marker}",
            fmt(a["n_available"], 0),
            fmt(a["comfort_Kh"], 4),
            fmt(a["energy_Wh"], 0),
            fmt(a["smoothness"], 4),
            fmt(a["solve_ms"], 1),
            fmt(a["tdis_tot"], 4),
            fmt(a["cost_tot"], 5),
            fmt(a["norm_score"], 4),
        ]
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("> Norm score = weighted combination of comfort (50%), energy (40%), solve_ms (10%) ratios to cross-candidate mean. Lower is better.")
    lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    if missing:
        lines.append(
            f"> **INCOMPLETE** – {len(missing)} episode result(s) are missing. "
            "Re-run the full validation batch before treating this ranking as final."
        )
        lines.append("")

    if best_id:
        best_a = agg[best_id]
        lines.append(f"**Recommended candidate: `{best_id}`**")
        lines.append("")
        lines.append(
            f"- Mean comfort deviation: {fmt(best_a['comfort_Kh'], 4)} Kh "
            f"(tdis_tot: {fmt(best_a['tdis_tot'], 4)} Kh/zone)"
        )
        lines.append(f"- Mean energy: {fmt(best_a['energy_Wh'], 0)} Wh")
        lines.append(f"- Mean solve time: {fmt(best_a['solve_ms'], 1)} ms")
        lines.append(f"- Normalised score: {fmt(best_a['norm_score'], 4)}")
        lines.append("")
        lines.append("Next steps:")
        lines.append(f"1. Promote `{best_id}` config to `configs/mpc_phase1_final.yaml`.")
        lines.append("2. Re-run the Phase 1 benchmark with the final config to produce publication results.")
        lines.append("3. Update `VALIDATION_REPORT.md` with the finalised candidate and its KPIs.")
    else:
        lines.append("No valid candidate data found. Ensure the full validation batch has completed.")

    # ------------------------------------------------------------------
    # Write report
    # ------------------------------------------------------------------
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written: {report_path.as_posix()}")

    if missing:
        print(f"NOTE: report is partial – {len(missing)} result file(s) missing.")
        return 0

    print(f"Recommended candidate: {best_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
