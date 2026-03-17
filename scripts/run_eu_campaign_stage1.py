#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run(cmd: list[str], log_file: Path, on_heartbeat: Any = None) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now(timezone.utc).isoformat()}] CMD: {' '.join(cmd)}\n")
        f.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None

        line_queue: queue.Queue[str] = queue.Queue()

        def _reader() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                line_queue.put(line)

        reader = threading.Thread(target=_reader, daemon=True)
        reader.start()

        started = time.time()
        last_heartbeat = started
        heartbeat_interval_s = 20

        while True:
            drained = False
            while True:
                try:
                    line = line_queue.get_nowait()
                except queue.Empty:
                    break
                drained = True
                print(line, end="")
                f.write(line)
                f.flush()

            now = time.time()
            if now - last_heartbeat >= heartbeat_interval_s:
                elapsed = int(now - started)
                msg = f"[heartbeat] still running after {elapsed}s: {' '.join(cmd)}\n"
                print(msg, end="")
                f.write(msg)
                f.flush()
                if on_heartbeat is not None:
                    on_heartbeat(elapsed)
                last_heartbeat = now

            code = proc.poll()
            if code is not None and not drained and line_queue.empty():
                break
            time.sleep(0.2)

        reader.join(timeout=1)
        while not line_queue.empty():
            line = line_queue.get_nowait()
            print(line, end="")
            f.write(line)

        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"Command failed ({code}): {' '.join(cmd)}")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def load_expected_test_episode_ids(manifest_path: Path) -> list[str]:
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    episodes = data.get("episodes", [])
    out: list[str] = []
    for ep in episodes:
        if not isinstance(ep, dict):
            continue
        if ep.get("split") == "test" and ep.get("id"):
            out.append(str(ep["id"]))
    return out


def has_all_episode_outputs(output_dir: Path, episode_ids: list[str]) -> bool:
    if not episode_ids:
        return False
    return all((output_dir / f"{ep_id}.json").exists() for ep_id in episode_ids)


def build_manifest(case_id: str) -> dict[str, Any]:
    # Generic single-zone style mapping with broad candidates.
    # This can still fail for some multizone IDs if no compatible signals exist.
    return {
        "version": 1,
        "study_id": f"eu_stage1_{case_id}",
        "phase": "eu_stage1",
        "defaults": {
            "control_interval_s": 900,
            "episode_length_days": 7,
            "warmup_period_s": 604800,
            "start_time_s": 0,
            "control_policy": {
                "mode": "random_heating_setpoint",
                "seed_base": 20260316,
                "setpoint_min_degC": 19.0,
                "setpoint_max_degC": 24.0,
            },
        },
        "case_mappings": {
            case_id: {
                "zone_temp_candidates": [
                    "reaTZon_y",
                    "reaTRoo_y",
                    "TRooAir_y",
                    "zon_reaTRooAir_y",
                    "reaTZonNor_y",
                    "reaTZonCor_y",
                    "reaTZonSou_y",
                ],
                "outdoor_temp_candidates": [
                    "weaSta_reaWeaTDryBul_y",
                    "TDryBul_y",
                    "TDryBul",
                ],
                "solar_candidates": [
                    "weaSta_reaWeaHGloHor_y",
                    "HGloHor_y",
                    "HGloHor",
                ],
                "control_value_candidates": [
                    "oveTZonSet_u",
                    "oveTSetHea_u",
                    "oveTRooSetHea_u",
                    "oveValRad_u",
                    "dh_oveTSupSetHea_u",
                    "oveTSupSetAir_u",
                ],
                "control_activate_candidates": [
                    "oveTZonSet_activate",
                    "oveTSetHea_activate",
                    "oveTRooSetHea_activate",
                    "oveValRad_activate",
                    "dh_oveTSupSetHea_activate",
                    "oveTSupSetAir_activate",
                ],
            }
        },
        "episodes": [
            {"id": "tr_std_01", "split": "train", "weather_class": "standard", "start_time_s": 0},
            {"id": "tr_std_02", "split": "train", "weather_class": "standard", "start_time_s": 2419200},
            {"id": "tr_std_03", "split": "train", "weather_class": "standard", "start_time_s": 4838400},
            {"id": "val_std_01", "split": "val", "weather_class": "standard", "start_time_s": 7257600},
            {"id": "te_std_01", "split": "test", "weather_class": "standard", "start_time_s": 9676800},
            {"id": "te_std_02", "split": "test", "weather_class": "standard", "start_time_s": 12096000},
            {"id": "te_std_03", "split": "test", "weather_class": "standard", "start_time_s": 14515200},
        ],
    }


def build_pinn_config(dataset_root: str) -> dict[str, Any]:
    return {
        "study_id": "pinn_eu_stage1",
        "data": {"dataset_root": dataset_root},
        "model": {"hidden_dim": 64, "depth": 3, "dropout": 0.0},
        "training": {
            "seed": 42,
            "device": "cpu",
            "batch_size": 256,
            "epochs": 150,
            "patience": 20,
            "learning_rate": 0.001,
            "weight_decay": 0.00001,
            "lambda_physics": 0.01,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EU stage-1 baseline campaign (1 RC + 1 PINN per case).")
    parser.add_argument("--mapping", default="results/eu_rc_vs_pinn/runtime_discovery/eu_testcases_resolved_mapping.json")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--max-cases", type=int, default=0, help="0 means all")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip BOPTEST health preflight gate.")
    args = parser.parse_args()

    mapping_path = ROOT / args.mapping
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    cases = [c for c in mapping.get("cases", []) if c.get("resolved")]
    if args.max_cases > 0:
        cases = cases[: args.max_cases]

    if not cases:
        raise RuntimeError("No resolved cases available in mapping file.")

    py = str(ROOT / ".venv/Scripts/python.exe")
    log_root = ROOT / "logs/eu_campaign_stage1"
    status_path = ROOT / "results/eu_rc_vs_pinn/runtime_discovery/campaign_live_status.json"

    status: dict[str, Any] = {
        "started_utc": now_utc_iso(),
        "updated_utc": now_utc_iso(),
        "state": "starting",
        "total_cases": len(cases),
        "completed_cases": 0,
        "failed_cases": 0,
        "current_case": None,
        "current_case_index": 0,
        "current_step": None,
        "step_started_utc": None,
        "step_elapsed_s": 0,
        "last_step_status": None,
        "last_error": None,
        "failure_summary": "results/eu_rc_vs_pinn/stage1_failures.json",
    }

    def update_status(**changes: Any) -> None:
        status.update(changes)
        status["updated_utc"] = now_utc_iso()
        write_json(status_path, status)

    if not args.skip_preflight:
        preflight_case = str(cases[0]["resolved_api_id"])
        preflight_log = log_root / "preflight.log"
        update_status(
            state="preflight",
            current_case=preflight_case,
            current_case_index=0,
            current_step="preflight",
            step_started_utc=now_utc_iso(),
            step_elapsed_s=0,
            heartbeat="preflight started",
        )
        run([
            py,
            "-u",
            "scripts/check_boptest_preflight.py",
            "--url", args.url,
            "--case", preflight_case,
            "--max-wait-s", "120",
            "--poll-s", "2",
            "--require-running",
            "--output", "results/eu_rc_vs_pinn/runtime_discovery/preflight_report.json",
        ], preflight_log, on_heartbeat=lambda elapsed: update_status(step_elapsed_s=elapsed, heartbeat="preflight running"))
        update_status(last_step_status="ok", heartbeat="preflight completed")

    failures: list[dict[str, str]] = []
    update_status(state="running", current_case=None, current_case_index=0, current_step=None, step_elapsed_s=0)

    for case_index, case in enumerate(cases, start=1):
        case_id = str(case["resolved_api_id"])
        print(f"\n{'='*72}\nCASE: {case_id}\n{'='*72}")
        update_status(
            current_case=case_id,
            current_case_index=case_index,
            current_step=None,
            step_started_utc=None,
            step_elapsed_s=0,
            last_error=None,
            heartbeat=f"case {case_id} started",
        )

        manifest_rel = Path(f"manifests/eu/{case_id}_stage1.yaml")
        pinn_cfg_rel = Path(f"configs/eu/pinn_{case_id}.yaml")
        dataset_rel = Path(f"datasets/eu/{case_id}")
        artifact_rel = Path(f"artifacts/eu/{case_id}")
        result_rel = Path(f"results/eu_rc_vs_pinn/raw/{case_id}")
        case_log = log_root / f"{case_id}.log"

        def run_step(step_name: str, cmd: list[str]) -> None:
            step_t0 = time.time()
            update_status(
                current_step=step_name,
                step_started_utc=now_utc_iso(),
                step_elapsed_s=0,
                heartbeat=f"{step_name} started",
            )
            run(cmd, case_log, on_heartbeat=lambda elapsed: update_status(step_elapsed_s=elapsed, heartbeat=f"{step_name} running"))
            update_status(
                last_step_status="ok",
                step_elapsed_s=int(time.time() - step_t0),
                heartbeat=f"{step_name} completed",
            )

        try:
            manifest_abs = ROOT / manifest_rel
            pinn_cfg_abs = ROOT / pinn_cfg_rel

            # Preserve curated per-case manifests/configs when they already exist.
            if not manifest_abs.exists():
                write_yaml(manifest_abs, build_manifest(case_id))
            if not pinn_cfg_abs.exists():
                write_yaml(pinn_cfg_abs, build_pinn_config(str(dataset_rel).replace('\\', '/')))

            test_episode_ids = load_expected_test_episode_ids(manifest_abs)

            # Dataset generation
            if not args.resume or not (ROOT / dataset_rel / "index.json").exists():
                run_step("dataset_generation", [
                    py,
                    "-u",
                    "scripts/generate_boptest_datasets.py",
                    "--url", args.url,
                    "--case", case_id,
                    "--manifest", str(manifest_rel).replace('\\', '/'),
                    "--output", str(dataset_rel).replace('\\', '/'),
                    "--startup-timeout-s", "180",
                    "--startup-poll-interval-s", "5",
                    "--recover-from-queued",
                    "--resume",
                ])

            # Train PINN per case
            checkpoint = ROOT / artifact_rel / "best_model.pt"
            if not args.resume or not checkpoint.exists():
                run_step("train_pinn", [
                    py,
                    "-u",
                    "scripts/train_pinn.py",
                    "--config", str(pinn_cfg_rel).replace('\\', '/'),
                    "--artifact-dir", str(artifact_rel).replace('\\', '/'),
                ])

            # RC benchmark (single implemented RC architecture)
            rc_out = ROOT / result_rel / "rc"
            if not args.resume or not has_all_episode_outputs(rc_out, test_episode_ids):
                run_step("benchmark_rc", [
                    py,
                    "-u",
                    "scripts/run_mpc_episode.py",
                    "--predictor", "rc",
                    "--episode", "all-test",
                    "--manifest", str(manifest_rel).replace('\\', '/'),
                    "--mpc-config", "configs/mpc_phase1.yaml",
                    "--checkpoint", str((artifact_rel / "best_model.pt").as_posix()),
                    "--output-dir", str(result_rel).replace('\\', '/'),
                    "--url", args.url,
                    "--case", case_id,
                    "--startup-timeout-s", "180",
                    "--recover-from-queued",
                ])

            # PINN benchmark
            pinn_out = ROOT / result_rel / "pinn"
            if not args.resume or not has_all_episode_outputs(pinn_out, test_episode_ids):
                run_step("benchmark_pinn", [
                    py,
                    "-u",
                    "scripts/run_mpc_episode.py",
                    "--predictor", "pinn",
                    "--episode", "all-test",
                    "--manifest", str(manifest_rel).replace('\\', '/'),
                    "--mpc-config", "configs/mpc_phase1.yaml",
                    "--checkpoint", str((artifact_rel / "best_model.pt").as_posix()),
                    "--output-dir", str(result_rel).replace('\\', '/'),
                    "--url", args.url,
                    "--case", case_id,
                    "--startup-timeout-s", "180",
                    "--recover-from-queued",
                ])

            update_status(
                completed_cases=int(status["completed_cases"]) + 1,
                current_step=None,
                step_started_utc=None,
                step_elapsed_s=0,
                heartbeat=f"case {case_id} completed",
            )
        except Exception as exc:
            failures.append({"case_id": case_id, "error": str(exc)})
            print(f"Case {case_id} failed and will be skipped: {exc}")
            update_status(
                failed_cases=int(status["failed_cases"]) + 1,
                last_step_status="failed",
                last_error=str(exc),
                heartbeat=f"case {case_id} failed",
            )
            continue

    summary_path = ROOT / "results/eu_rc_vs_pinn/stage1_failures.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({"failures": failures}, indent=2), encoding="utf-8")

    update_status(
        state="finished" if not failures else "finished_with_failures",
        current_case=None,
        current_step=None,
        step_started_utc=None,
        step_elapsed_s=0,
        heartbeat="campaign finished",
    )

    print("\nStage-1 baseline campaign finished.")
    print(f"Failure summary: {summary_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
