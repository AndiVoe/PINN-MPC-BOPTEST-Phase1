#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    file_path: str
    case_name: str
    predictor: str
    episode_id: str
    check_name: str
    severity: str
    status: str
    message: str
    observed: float | None = None
    expected: float | None = None
    rel_error: float | None = None


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return math.nan
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _rel_error(observed: float, expected: float) -> float:
    denom = max(1e-9, abs(expected))
    return abs(observed - expected) / denom


def _iter_result_jsons(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        p
        for p in root.rglob("*.json")
        if not p.name.endswith(".live.json")
    )


def _check_step_relations(path: Path, payload: dict[str, Any]) -> list[CheckResult]:
    out: list[CheckResult] = []
    step_records = payload.get("step_records", [])
    if not isinstance(step_records, list) or not step_records:
        return out

    case_name = str(payload.get("case_name", ""))
    predictor = str(payload.get("predictor", payload.get("predictor_label", "")))
    episode_id = str(payload.get("episode_id", path.stem))
    dt_s = int(payload.get("control_interval_s", 0) or 0)
    n_steps = int(payload.get("n_steps", 0) or 0)
    diag = payload.get("diagnostic_kpis", {}) or {}

    if n_steps != len(step_records):
        out.append(
            CheckResult(
                str(path),
                case_name,
                predictor,
                episode_id,
                "step_count",
                "error",
                "fail",
                f"n_steps={n_steps} but len(step_records)={len(step_records)}",
                observed=float(len(step_records)),
                expected=float(n_steps),
                rel_error=_rel_error(float(len(step_records)), float(max(1, n_steps))),
            )
        )

    if dt_s <= 0:
        out.append(
            CheckResult(
                str(path),
                case_name,
                predictor,
                episode_id,
                "control_interval",
                "error",
                "fail",
                f"invalid control_interval_s={dt_s}",
            )
        )
        return out

    dt_h = dt_s / 3600.0
    times = [_safe_float(r.get("time_s")) for r in step_records]
    if all(not math.isnan(t) for t in times):
        for i in range(1, len(times)):
            if times[i] <= times[i - 1]:
                out.append(
                    CheckResult(
                        str(path),
                        case_name,
                        predictor,
                        episode_id,
                        "time_monotonic",
                        "error",
                        "fail",
                        f"non-increasing time at index {i}: {times[i - 1]} -> {times[i]}",
                    )
                )
                break

    # Energy and peak relations from logged step powers.
    p_tot = [_safe_float(r.get("power_w")) for r in step_records]
    p_heat = [_safe_float(r.get("power_heating_w")) for r in step_records]
    p_elec = [_safe_float(r.get("power_electric_w")) for r in step_records]
    solves = [_safe_float(r.get("solve_time_ms")) for r in step_records]

    def finite(xs: list[float]) -> list[float]:
        return [x for x in xs if not math.isnan(x)]

    p_tot_f = finite(p_tot)
    p_heat_f = finite(p_heat)
    p_elec_f = finite(p_elec)
    solves_f = finite(solves)

    if p_tot_f:
        energy_from_steps_wh = sum(max(x, 0.0) for x in p_tot_f) * dt_h
        energy_diag_wh = _safe_float(diag.get("total_energy_Wh"))
        if not math.isnan(energy_diag_wh):
            rel = _rel_error(energy_from_steps_wh, energy_diag_wh)
            status = "pass" if rel <= 0.03 else "fail"
            out.append(
                CheckResult(
                    str(path),
                    case_name,
                    predictor,
                    episode_id,
                    "energy_integral_total",
                    "error",
                    status,
                    "sum(max(power_w,0))*dt_h should match diagnostic total_energy_Wh",
                    observed=energy_from_steps_wh,
                    expected=energy_diag_wh,
                    rel_error=rel,
                )
            )

        peak_from_steps = max(p_tot_f)
        peak_diag = _safe_float(diag.get("peak_power_W"))
        if not math.isnan(peak_diag):
            rel = _rel_error(peak_from_steps, peak_diag)
            status = "pass" if rel <= 0.03 else "fail"
            out.append(
                CheckResult(
                    str(path),
                    case_name,
                    predictor,
                    episode_id,
                    "peak_power",
                    "error",
                    status,
                    "max(power_w) should match diagnostic peak_power_W",
                    observed=peak_from_steps,
                    expected=peak_diag,
                    rel_error=rel,
                )
            )

    if p_heat_f:
        heat_from_steps_wh = sum(max(x, 0.0) for x in p_heat_f) * dt_h
        heat_diag_wh = _safe_float(diag.get("heating_energy_Wh"))
        if not math.isnan(heat_diag_wh):
            rel = _rel_error(heat_from_steps_wh, heat_diag_wh)
            status = "pass" if rel <= 0.03 else "fail"
            out.append(
                CheckResult(
                    str(path),
                    case_name,
                    predictor,
                    episode_id,
                    "energy_integral_heating",
                    "error",
                    status,
                    "sum(max(power_heating_w,0))*dt_h should match diagnostic heating_energy_Wh",
                    observed=heat_from_steps_wh,
                    expected=heat_diag_wh,
                    rel_error=rel,
                )
            )

    if p_elec_f:
        elec_from_steps_wh = sum(max(x, 0.0) for x in p_elec_f) * dt_h
        elec_diag_wh = _safe_float(diag.get("electric_energy_Wh"))
        if not math.isnan(elec_diag_wh):
            rel = _rel_error(elec_from_steps_wh, elec_diag_wh)
            status = "pass" if rel <= 0.03 else "fail"
            out.append(
                CheckResult(
                    str(path),
                    case_name,
                    predictor,
                    episode_id,
                    "energy_integral_electric",
                    "warning",
                    status,
                    "sum(max(power_electric_w,0))*dt_h should match diagnostic electric_energy_Wh",
                    observed=elec_from_steps_wh,
                    expected=elec_diag_wh,
                    rel_error=rel,
                )
            )

    if solves_f:
        mean_from_steps = sum(solves_f) / len(solves_f)
        mean_diag = _safe_float(diag.get("mpc_solve_time_mean_ms"))
        if not math.isnan(mean_diag):
            rel = _rel_error(mean_from_steps, mean_diag)
            status = "pass" if rel <= 0.05 else "fail"
            out.append(
                CheckResult(
                    str(path),
                    case_name,
                    predictor,
                    episode_id,
                    "solve_time_mean",
                    "warning",
                    status,
                    "mean(step.solve_time_ms) should match diagnostic mpc_solve_time_mean_ms",
                    observed=mean_from_steps,
                    expected=mean_diag,
                    rel_error=rel,
                )
            )

    # Comfort relation from step bounds.
    comfort_from_steps = 0.0
    viol_steps = 0
    for rec in step_records:
        tz = _safe_float(rec.get("t_zone"))
        tl = _safe_float(rec.get("t_lower"))
        tu = _safe_float(rec.get("t_upper"))
        if math.isnan(tz) or math.isnan(tl) or math.isnan(tu):
            continue
        viol = max(tl - tz, 0.0) + max(tz - tu, 0.0)
        comfort_from_steps += viol * dt_h
        if viol > 0.0:
            viol_steps += 1

    comfort_diag = _safe_float(diag.get("comfort_Kh"))
    if not math.isnan(comfort_diag):
        rel = _rel_error(comfort_from_steps, comfort_diag)
        status = "pass" if rel <= 0.05 else "fail"
        out.append(
            CheckResult(
                str(path),
                case_name,
                predictor,
                episode_id,
                "comfort_integral",
                "error",
                status,
                "reconstructed comfort from step bounds should match diagnostic comfort_Kh",
                observed=comfort_from_steps,
                expected=comfort_diag,
                rel_error=rel,
            )
        )

    viol_diag = _safe_float(diag.get("comfort_violation_steps"))
    if not math.isnan(viol_diag):
        rel = _rel_error(float(viol_steps), float(max(1.0, viol_diag)))
        status = "pass" if abs(viol_steps - int(viol_diag)) <= 1 else "fail"
        out.append(
            CheckResult(
                str(path),
                case_name,
                predictor,
                episode_id,
                "comfort_violation_steps",
                "error",
                status,
                "count of violating steps should match diagnostic comfort_violation_steps",
                observed=float(viol_steps),
                expected=viol_diag,
                rel_error=rel,
            )
        )

    # Logical relation: challenge and boptest KPI values should agree when both exist.
    bop = payload.get("boptest_kpis", {}) or {}
    challenge = payload.get("challenge_kpis", {}) or {}
    for key in ("cost_tot", "tdis_tot", "idis_tot", "pele_tot", "pdih_tot"):
        b = _safe_float(bop.get(key))
        c = _safe_float((challenge.get(key) or {}).get("value"))
        if math.isnan(b) or math.isnan(c):
            continue
        rel = _rel_error(c, b)
        status = "pass" if rel <= 1e-6 else "fail"
        out.append(
            CheckResult(
                str(path),
                case_name,
                predictor,
                episode_id,
                f"challenge_equals_boptest_{key}",
                "error",
                status,
                "challenge_kpis value should equal boptest_kpis value",
                observed=c,
                expected=b,
                rel_error=rel,
            )
        )

    return out


def _check_candidate_tree(root: Path) -> list[CheckResult]:
    out: list[CheckResult] = []
    full_validation = root / "results" / "mpc_tuning_eval" / "autotune_v1_10cand" / "full_validation"
    if not full_validation.exists():
        return out

    candidates = sorted(p for p in full_validation.iterdir() if p.is_dir() and p.name.startswith("cand_"))
    expected_controllers = ("pinn", "rbc", "rc")

    # Baseline folders are required for relative comparison.
    baseline = root / "results" / "mpc_tuning_eval" / "baseline"
    baseline_eps: dict[str, set[str]] = {}
    for ctrl in expected_controllers:
        ctrl_dir = baseline / ctrl
        files = sorted(ctrl_dir.glob("*.json")) if ctrl_dir.exists() else []
        baseline_eps[ctrl] = {f.stem for f in files}
        status = "pass" if files else "fail"
        out.append(
            CheckResult(
                str(ctrl_dir),
                "candidate_eval",
                ctrl,
                "baseline",
                "baseline_controller_nonempty",
                "error",
                status,
                f"baseline/{ctrl} must contain at least one result JSON",
                observed=float(len(files)),
                expected=1.0,
            )
        )

    for cand in candidates:
        for ctrl in expected_controllers:
            ctrl_dir = cand / ctrl
            files = sorted(ctrl_dir.glob("*.json")) if ctrl_dir.exists() else []
            cand_eps = {f.stem for f in files}
            status = "pass" if files else "fail"
            out.append(
                CheckResult(
                    str(ctrl_dir),
                    "candidate_eval",
                    ctrl,
                    cand.name,
                    "candidate_controller_nonempty",
                    "error",
                    status,
                    f"{cand.name}/{ctrl} must contain at least one result JSON",
                    observed=float(len(files)),
                    expected=1.0,
                )
            )

            # Logical fairness relation: every candidate episode must have a baseline counterpart.
            missing = sorted(cand_eps - baseline_eps.get(ctrl, set()))
            status_cov = "pass" if not missing else "fail"
            out.append(
                CheckResult(
                    str(ctrl_dir),
                    "candidate_eval",
                    ctrl,
                    cand.name,
                    "candidate_baseline_episode_coverage",
                    "error",
                    status_cov,
                    "candidate episodes must all exist in baseline for fair delta computation"
                    + ("" if not missing else f"; missing baseline episodes: {', '.join(missing)}"),
                    observed=float(len(cand_eps) - len(missing)),
                    expected=float(len(cand_eps)),
                )
            )

    return out


def _write_csv(path: Path, rows: list[CheckResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "file_path",
        "case_name",
        "predictor",
        "episode_id",
        "check_name",
        "severity",
        "status",
        "message",
        "observed",
        "expected",
        "rel_error",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "file_path": r.file_path,
                    "case_name": r.case_name,
                    "predictor": r.predictor,
                    "episode_id": r.episode_id,
                    "check_name": r.check_name,
                    "severity": r.severity,
                    "status": r.status,
                    "message": r.message,
                    "observed": r.observed,
                    "expected": r.expected,
                    "rel_error": r.rel_error,
                }
            )


def _write_markdown(path: Path, rows: list[CheckResult]) -> None:
    total = len(rows)
    fails = [r for r in rows if r.status == "fail"]
    fail_errors = [r for r in fails if r.severity == "error"]
    fail_warnings = [r for r in fails if r.severity != "error"]

    by_check: dict[str, list[CheckResult]] = {}
    for r in rows:
        by_check.setdefault(r.check_name, []).append(r)

    lines: list[str] = []
    lines.append("# End-to-End Validity Audit Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total checks: {total}")
    lines.append(f"- Failed checks: {len(fails)}")
    lines.append(f"- Failed errors: {len(fail_errors)}")
    lines.append(f"- Failed warnings: {len(fail_warnings)}")
    lines.append("")
    lines.append("## Enforced Relations")
    lines.append("- Step count relation: n_steps == len(step_records)")
    lines.append("- Time relation: time_s must be strictly increasing")
    lines.append("- Energy relation: total_energy_Wh ~= sum(max(power_w,0))*dt_h")
    lines.append("- Peak relation: peak_power_W ~= max(power_w)")
    lines.append("- Comfort relation: comfort_Kh ~= sum(violation_K)*dt_h")
    lines.append("- Violation relation: comfort_violation_steps ~= count(violation>0)")
    lines.append("- KPI relation: challenge_kpis[*].value == boptest_kpis[*]")
    lines.append("- Candidate relation: each candidate/controller folder must contain result JSON")
    lines.append("- Baseline relation: baseline controller folders must contain result JSON")
    lines.append("")
    lines.append("## Failures")
    if not fails:
        lines.append("- No failed checks.")
    else:
        for r in fails[:200]:
            rel_txt = ""
            if r.rel_error is not None:
                rel_txt = f" (rel_error={r.rel_error:.6f})"
            lines.append(
                f"- [{r.severity}] {r.check_name} :: {r.case_name}/{r.predictor}/{r.episode_id} :: {r.message}{rel_txt}"
            )
        if len(fails) > 200:
            lines.append(f"- ... truncated {len(fails) - 200} additional failures")

    lines.append("")
    lines.append("## Check-Wise Pass Rates")
    lines.append("| Check | Total | Pass | Fail |")
    lines.append("|---|---:|---:|---:|")
    for name in sorted(by_check):
        rs = by_check[name]
        ok = sum(1 for r in rs if r.status == "pass")
        bad = sum(1 for r in rs if r.status == "fail")
        lines.append(f"| {name} | {len(rs)} | {ok} | {bad} |")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end physical/logical validity audit for MPC/PINN results")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path")
    parser.add_argument(
        "--scan-roots",
        nargs="*",
        default=["results/mpc_phase1", "results/eu_rc_vs_pinn/raw", "results/eu_rc_vs_pinn_fixcheck/raw"],
        help="Result roots to scan for JSON outputs",
    )
    parser.add_argument(
        "--csv-out",
        default="artifacts/audit/end_to_end_validity_checks.csv",
        help="CSV output path",
    )
    parser.add_argument(
        "--report-out",
        default="artifacts/audit/end_to_end_validity_report.md",
        help="Markdown output path",
    )
    args = parser.parse_args()

    ws = Path(args.workspace_root)
    rows: list[CheckResult] = []

    for rel_root in args.scan_roots:
        root = ws / rel_root
        for p in _iter_result_jsons(root):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception as exc:
                rows.append(
                    CheckResult(
                        str(p),
                        "",
                        "",
                        p.stem,
                        "json_parse",
                        "error",
                        "fail",
                        f"JSON parse error: {exc}",
                    )
                )
                continue
            if not isinstance(data, dict):
                rows.append(
                    CheckResult(
                        str(p),
                        "",
                        "",
                        p.stem,
                        "json_shape",
                        "error",
                        "fail",
                        "JSON root is not an object",
                    )
                )
                continue
            rows.extend(_check_step_relations(p, data))

    rows.extend(_check_candidate_tree(ws))

    csv_out = ws / args.csv_out
    report_out = ws / args.report_out
    _write_csv(csv_out, rows)
    _write_markdown(report_out, rows)

    n_fail_error = sum(1 for r in rows if r.status == "fail" and r.severity == "error")
    n_fail_warn = sum(1 for r in rows if r.status == "fail" and r.severity != "error")
    print(f"checks_total={len(rows)}")
    print(f"failed_errors={n_fail_error}")
    print(f"failed_warnings={n_fail_warn}")
    print(f"csv={csv_out.as_posix()}")
    print(f"report={report_out.as_posix()}")

    return 0 if n_fail_error == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
