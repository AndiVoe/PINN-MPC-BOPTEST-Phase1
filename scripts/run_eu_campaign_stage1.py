#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
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


def load_rc_topologies(config_path: Path) -> list[str]:
    if not config_path.exists():
        return ["1R1C"]
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    entries = data.get("topologies", [])
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"Invalid RC topology config: {config_path}")

    out: list[str] = []
    for item in entries:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
        else:
            name = ""
        if name:
            out.append(name)

    if not out:
        raise ValueError(f"No RC topologies configured in: {config_path}")
    return out


def build_manifest(case_id: str, season: str = "standard") -> dict[str, Any]:
    # Generic single-zone style mapping with broad candidates.
    # This can still fail for some multizone IDs if no compatible signals exist.
    case_mapping = {
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
            "oveTSet_u",
            "oveHeaPumY_u",
            "oveFan_u",
            "ovePum_u",
            "oveTZonSet_u",
            "oveTSetHea_u",
            "oveTRooSetHea_u",
            "oveValRad_u",
            "dh_oveTSupSetHea_u",
            "oveTSupSetAir_u",
        ],
        "control_activate_candidates": [
            "oveTSet_activate",
            "oveHeaPumY_activate",
            "oveFan_activate",
            "ovePum_activate",
            "oveTZonSet_activate",
            "oveTSetHea_activate",
            "oveTRooSetHea_activate",
            "oveValRad_activate",
            "dh_oveTSupSetHea_activate",
            "oveTSupSetAir_activate",
        ],
    }

    # Keep explicit mapping for known heat-pump case to avoid proxy-control fallback.
    if "heat_pump" in case_id:
        case_mapping["control_value_signal"] = "oveTSet_u"
        case_mapping["control_activate_signal"] = "oveTSet_activate"

    if season == "heating":
        test_episodes = [
            {"id": "te_heat_01", "split": "test", "weather_class": "standard", "start_time_s": 23673600},
            {"id": "te_heat_02", "split": "test", "weather_class": "standard", "start_time_s": 26352000},
            {"id": "te_heat_03", "split": "test", "weather_class": "standard", "start_time_s": 28944000},
        ]
        study_suffix = "heating_season"
    else:
        test_episodes = [
            {"id": "te_std_01", "split": "test", "weather_class": "standard", "start_time_s": 12096000},
            {"id": "te_std_02", "split": "test", "weather_class": "standard", "start_time_s": 24192000},
            {"id": "te_std_03", "split": "test", "weather_class": "standard", "start_time_s": 29030400},
        ]
        study_suffix = "stage1"

    return {
        "version": 1,
        "study_id": f"eu_{study_suffix}_{case_id}",
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
        "case_mappings": {case_id: case_mapping},
        "episodes": [
            {"id": "tr_std_01", "split": "train", "weather_class": "standard", "start_time_s": 0},
            {"id": "tr_std_02", "split": "train", "weather_class": "standard", "start_time_s": 9676800},
            {"id": "tr_std_03", "split": "train", "weather_class": "standard", "start_time_s": 19353600},
            {"id": "val_std_01", "split": "val", "weather_class": "standard", "start_time_s": 4838400},
            *test_episodes,
        ]
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


def _run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=ROOT)


def get_redis_queue_stats(redis_name: str = "project1-boptest-redis-1") -> dict[str, int] | None:
    if shutil.which("docker") is None:
        return None

    q = _run_capture(["docker", "exec", redis_name, "redis-cli", "LLEN", "jobs"])
    if q.returncode != 0:
        return None

    jobs = int((q.stdout or "0").strip().splitlines()[-1])

    script = (
        "local q=0; local r=0; local tot=0; "
        "for _,k in ipairs(redis.call('keys','tests:*')) do "
        "tot=tot+1; local s=redis.call('hget',k,'status'); "
        "if s=='Queued' then q=q+1 elseif s=='Running' then r=r+1 end; "
        "end; return {tot,q,r}"
    )
    cnt = _run_capture(["docker", "exec", redis_name, "redis-cli", "--raw", "EVAL", script, "0"])
    if cnt.returncode != 0:
        return {"jobs": jobs, "tests_total": -1, "tests_queued": -1, "tests_running": -1}

    lines = [x.strip() for x in (cnt.stdout or "").splitlines() if x.strip()]
    if len(lines) < 3:
        return {"jobs": jobs, "tests_total": -1, "tests_queued": -1, "tests_running": -1}

    return {
        "jobs": jobs,
        "tests_total": int(lines[0]),
        "tests_queued": int(lines[1]),
        "tests_running": int(lines[2]),
    }


def get_redis_active_tests(redis_name: str = "project1-boptest-redis-1") -> list[tuple[str, str]] | None:
    if shutil.which("docker") is None:
        return None

    script = (
        "local out={}; "
        "for _,k in ipairs(redis.call('keys','tests:*')) do "
        "local s=redis.call('hget',k,'status'); "
        "if s=='Queued' or s=='Running' then table.insert(out,k..'='..s) end; "
        "end; return out"
    )
    res = _run_capture(["docker", "exec", redis_name, "redis-cli", "--raw", "EVAL", script, "0"])
    if res.returncode != 0:
        return None

    out: list[tuple[str, str]] = []
    for raw in (res.stdout or "").splitlines():
        line = raw.strip()
        if not line or not line.startswith("tests:") or "=" not in line:
            continue
        key, status = line.split("=", 1)
        test_id = key.split(":", 1)[1]
        out.append((test_id, status))
    return out


def get_redis_active_test_details(
    redis_name: str = "project1-boptest-redis-1",
) -> list[dict[str, int | str]] | None:
    if shutil.which("docker") is None:
        return None

    script = (
        "local out={}; "
        "for _,k in ipairs(redis.call('keys','tests:*')) do "
        "local s=redis.call('hget',k,'status'); "
        "if s=='Queued' or s=='Running' then "
        "local ts=redis.call('hget',k,'timestamp'); "
        "if not ts then ts='0' end; "
        "table.insert(out,k..'='..s..'='..ts); "
        "end; end; return out"
    )
    res = _run_capture(["docker", "exec", redis_name, "redis-cli", "--raw", "EVAL", script, "0"])
    if res.returncode != 0:
        return None

    out: list[dict[str, int | str]] = []
    for raw in (res.stdout or "").splitlines():
        line = raw.strip()
        if not line or not line.startswith("tests:"):
            continue
        parts = line.split("=", 2)
        if len(parts) != 3:
            continue
        key, status, ts_raw = parts
        try:
            ts_ms = int(ts_raw)
        except ValueError:
            ts_ms = 0
        out.append(
            {
                "test_id": key.split(":", 1)[1],
                "status": status,
                "timestamp_ms": ts_ms,
            }
        )
    return out


def restart_boptest_services(services: list[str] | None = None) -> bool:
    if shutil.which("docker") is None:
        return False
    svc = services or ["project1-boptest-web-1", "project1-boptest-worker-1"]
    cmd = ["docker", "restart", *svc]
    res = _run_capture(cmd)
    return res.returncode == 0


def recover_stale_queued_tests(
    url: str,
    redis_name: str = "project1-boptest-redis-1",
    stale_queued_age_s: int = 180,
    allow_container_restart: bool = True,
) -> bool:
    stats = get_redis_queue_stats(redis_name=redis_name)
    if stats is None:
        return False
    if int(stats.get("tests_queued", 0)) <= 0:
        return False

    active_details = get_redis_active_test_details(redis_name=redis_name)
    if active_details is None:
        return False

    queued = [x for x in active_details if x.get("status") == "Queued"]
    running = [x for x in active_details if x.get("status") == "Running"]
    if not queued:
        return False

    now_ms = int(time.time() * 1000)
    oldest_queued_ms = min(int(x.get("timestamp_ms", 0) or 0) for x in queued)
    oldest_age_s = max(0, (now_ms - oldest_queued_ms) // 1000) if oldest_queued_ms > 0 else 0

    # Recovery is only appropriate when queue is stale and nothing is actively running.
    if running:
        return False
    if oldest_age_s < max(30, int(stale_queued_age_s)):
        return False

    to_stop = [str(x["test_id"]) for x in queued]
    if not to_stop:
        return False

    print(
        "[queue-guard] Attempting stale queue cleanup for "
        f"{len(to_stop)} queued test(s), oldest_age_s={oldest_age_s} ..."
    )
    stopped = 0
    base = url.rstrip("/")
    for test_id in to_stop:
        req = urllib.request.Request(f"{base}/stop/{test_id}", method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=20):
                stopped += 1
        except (urllib.error.URLError, TimeoutError):
            continue

    recovered = stopped > 0
    time.sleep(2)

    post = get_redis_queue_stats(redis_name=redis_name)
    if post is not None:
        print(
            "[queue-guard] Cleanup result: "
            f"jobs={post['jobs']} queued={post['tests_queued']} running={post['tests_running']}"
        )

    # If stale queue still remains, restart web+worker once.
    if allow_container_restart and post is not None and int(post.get("tests_queued", 0)) > 0 and int(post.get("tests_running", 0)) == 0:
        print("[queue-guard] Queue still stale after stop cleanup; restarting web/worker ...")
        if restart_boptest_services():
            recovered = True
            time.sleep(5)
            post2 = get_redis_queue_stats(redis_name=redis_name)
            if post2 is not None:
                print(
                    "[queue-guard] Post-restart queue status: "
                    f"jobs={post2['jobs']} queued={post2['tests_queued']} running={post2['tests_running']}"
                )

    return recovered


def clear_stale_jobs_queue_if_idle(redis_name: str = "project1-boptest-redis-1") -> bool:
    stats = get_redis_queue_stats(redis_name=redis_name)
    if stats is None:
        return False
    if int(stats.get("jobs", 0)) <= 0:
        return False
    if int(stats.get("tests_running", 0)) > 0 or int(stats.get("tests_queued", 0)) > 0:
        return False

    print(f"[queue-guard] Clearing stale Redis jobs list (jobs={stats['jobs']}, no active tests).")
    res = _run_capture(["docker", "exec", redis_name, "redis-cli", "DEL", "jobs"])
    return res.returncode == 0


def enforce_queue_guard(
    *,
    context: str,
    max_jobs: int,
    max_queued_tests: int,
    url: str | None = None,
    auto_recover_once: bool = False,
    redis_name: str = "project1-boptest-redis-1",
    stale_queued_age_s: int = 180,
    allow_container_restart: bool = True,
) -> None:
    if max_jobs <= 0 and max_queued_tests <= 0:
        return

    stats = get_redis_queue_stats(redis_name=redis_name)
    if stats is None:
        print(f"[queue-guard] Skipped ({context}): docker/redis stats unavailable.")
        return

    def _collect_violations(current: dict[str, int]) -> list[str]:
        items: list[str] = []
        if max_jobs > 0 and int(current["jobs"]) > max_jobs:
            items.append(f"jobs={current['jobs']} > max_jobs={max_jobs}")
        if max_queued_tests > 0 and int(current["tests_queued"]) > max_queued_tests:
            items.append(
                f"tests_queued={current['tests_queued']} > max_queued_tests={max_queued_tests}"
            )
        return items

    violations = _collect_violations(stats)
    should_try_stale_recover = (
        auto_recover_once
        and url is not None
        and int(stats.get("tests_queued", 0)) > 0
        and int(stats.get("tests_running", 0)) == 0
    )

    if (violations or should_try_stale_recover) and auto_recover_once and url:
        recovered = recover_stale_queued_tests(url=url, redis_name=redis_name)
        if recovered:
            refreshed = get_redis_queue_stats(redis_name=redis_name)
            if refreshed is not None:
                stats = refreshed
                violations = _collect_violations(stats)

    if violations and auto_recover_once:
        cleaned = clear_stale_jobs_queue_if_idle(redis_name=redis_name)
        if cleaned:
            refreshed = get_redis_queue_stats(redis_name=redis_name)
            if refreshed is not None:
                stats = refreshed
                violations = _collect_violations(stats)

    if violations:
        raise RuntimeError(
            f"Queue guard blocked run at {context}: {'; '.join(violations)}. "
            f"Current tests_running={stats['tests_running']}, tests_total={stats['tests_total']}."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EU stage-1 baseline campaign (RC topology candidates + PINN + RBC per case).")
    parser.add_argument("--mapping", default="results/eu_rc_vs_pinn/runtime_discovery/eu_testcases_resolved_mapping.json")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--season",
        choices=["standard", "heating"],
        default="standard",
        help="Episode season profile for test splits. 'heating' uses winter-oriented test windows.",
    )
    parser.add_argument("--max-cases", type=int, default=0, help="0 means all")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip BOPTEST health preflight gate.")
    parser.add_argument(
        "--startup-timeout-s",
        type=int,
        default=420,
        help="Timeout for BOPTEST case startup (Queued->Running) per step in seconds.",
    )
    parser.add_argument(
        "--no-auto-discover-mapping",
        action="store_true",
        help="Do not auto-run testcase discovery when mapping file is missing.",
    )
    parser.add_argument("--short-episode", action="store_true", help="Use shorter timeouts and validation runs (1-day episodes only). Useful for quick validation before full campaigns.")
    parser.add_argument(
        "--step-max-retries",
        type=int,
        default=2,
        help="Maximum retries per step after the initial attempt (default: 2).",
    )
    parser.add_argument(
        "--step-retry-backoff-s",
        type=int,
        default=20,
        help="Initial backoff in seconds between retry attempts (exponential).",
    )
    parser.add_argument(
        "--max-queue-jobs",
        type=int,
        default=12,
        help="Fail fast when Redis jobs queue exceeds this threshold (<=0 disables).",
    )
    parser.add_argument(
        "--max-queued-tests",
        type=int,
        default=6,
        help="Fail fast when Redis tests in Queued state exceed this threshold (<=0 disables).",
    )
    parser.add_argument(
        "--stale-queued-age-s",
        type=int,
        default=180,
        help="Auto-recover if queued tests are older than this age (and no tests are Running).",
    )
    parser.add_argument(
        "--no-queue-container-restart",
        action="store_true",
        help="Disable automatic web/worker restart during stale queue recovery.",
    )
    parser.add_argument(
        "--rc-topologies-config",
        default="configs/eu/stage1/rc_topologies.yaml",
        help="YAML file defining RC topology candidates for stage-1 runs.",
    )
    args = parser.parse_args()
    
    # Adjust timeouts for short-episode mode
    startup_timeout_s = "120" if args.short_episode else str(int(args.startup_timeout_s))
    if args.short_episode:
        episode_label = f"SHORT VALIDATION ({args.season})"
    else:
        episode_label = f"FULL CAMPAIGN ({args.season})"

    rc_topologies = load_rc_topologies(ROOT / args.rc_topologies_config)

    results_root = Path("results/eu_rc_vs_pinn/raw") if args.season == "standard" else Path("results/eu_rc_vs_pinn_heating/raw")
    runtime_root = Path("results/eu_rc_vs_pinn/runtime_discovery") if args.season == "standard" else Path("results/eu_rc_vs_pinn_heating/runtime_discovery")

    venv_python = ROOT / ".venv/Scripts/python.exe"
    py = str(venv_python if venv_python.exists() else Path(sys.executable))
    log_root = ROOT / "logs/eu_campaign_stage1"
    log_root.mkdir(parents=True, exist_ok=True)

    mapping_path = ROOT / args.mapping
    if not mapping_path.exists():
        if args.no_auto_discover_mapping:
            raise FileNotFoundError(
                f"Mapping file not found: {mapping_path}. "
                "Run scripts/discover_boptest_testcases.py first or remove --no-auto-discover-mapping."
            )
        discover_log = log_root / "discover_mapping.log"
        print(f"Mapping missing at {mapping_path}. Running testcase discovery ...")
        run(
            [
                py,
                "-u",
                "scripts/discover_boptest_testcases.py",
                "--base-urls",
                args.url,
                "--output-dir",
                str(mapping_path.parent.relative_to(ROOT)).replace("\\", "/"),
            ],
            discover_log,
        )
        if not mapping_path.exists():
            raise FileNotFoundError(
                "Testcase discovery completed but mapping is still missing at "
                f"{mapping_path}. Check {discover_log} for details."
            )

    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid mapping JSON at {mapping_path}: {exc}. "
            "Re-run scripts/discover_boptest_testcases.py to regenerate."
        ) from exc

    cases = [c for c in mapping.get("cases", []) if c.get("resolved")]
    if args.max_cases > 0:
        cases = cases[: args.max_cases]

    if not cases:
        raise RuntimeError("No resolved cases available in mapping file.")

    status_path = ROOT / runtime_root / "campaign_live_status.json"

    status: dict[str, Any] = {
        "started_utc": now_utc_iso(),
        "updated_utc": now_utc_iso(),
        "state": "starting",
        "mode": "short_validation" if args.short_episode else "full_campaign",
        "episode_type": episode_label,
        "total_cases": len(cases),
        "completed_cases": 0,
        "failed_cases": 0,
        "current_case": None,
        "current_case_index": 0,
        "current_step": None,
        "current_step_attempt": 0,
        "step_started_utc": None,
        "step_elapsed_s": 0,
        "last_step_status": None,
        "last_error": None,
        "failure_summary": (str((results_root.parent / "stage1_failures.json").as_posix())),
        "rc_topologies": rc_topologies,
    }

    print(f"\n{'='*72}")
    print(f"CAMPAIGN MODE: {episode_label}")
    print(f"Total cases: {len(cases)}")
    print(f"Startup timeout: {startup_timeout_s}s")
    print(
        "Queue guard: "
        f"max_jobs={args.max_queue_jobs}, max_queued_tests={args.max_queued_tests}"
    )
    print(
        "Retries: "
        f"max_retries={args.step_max_retries}, backoff_s={args.step_retry_backoff_s}"
    )
    print(f"RC topologies: {', '.join(rc_topologies)}")
    print(f"{'='*72}\n")

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

    try:
        enforce_queue_guard(
            context="campaign_start",
            max_jobs=int(args.max_queue_jobs),
            max_queued_tests=int(args.max_queued_tests),
            url=args.url,
            auto_recover_once=True,
            stale_queued_age_s=int(args.stale_queued_age_s),
            allow_container_restart=not bool(args.no_queue_container_restart),
        )
    except Exception as exc:
        update_status(state="blocked_queue", last_error=str(exc), heartbeat="queue guard failed")
        raise

    failures: list[dict[str, str]] = []
    update_status(state="running", current_case=None, current_case_index=0, current_step=None, step_elapsed_s=0)

    for case_index, case in enumerate(cases, start=1):
        case_id = str(case["resolved_api_id"])
        print(f"\n{'='*72}\nCASE: {case_id}\n{'='*72}")
        update_status(
            current_case=case_id,
            current_case_index=case_index,
            current_step=None,
            current_step_attempt=0,
            step_started_utc=None,
            step_elapsed_s=0,
            last_error=None,
            heartbeat=f"case {case_id} started",
        )

        manifest_suffix = "stage1" if args.season == "standard" else "heating_season"
        manifest_rel = Path(f"manifests/eu/{case_id}_{manifest_suffix}.yaml")
        pinn_cfg_rel = Path(f"configs/eu/pinn_{case_id}.yaml")
        dataset_rel = Path(f"datasets/eu/{case_id}")
        artifact_rel = Path(f"artifacts/eu/{case_id}")
        result_rel = results_root / case_id
        case_log = log_root / f"{case_id}.log"

        def run_step(step_name: str, cmd: list[str], require_queue_capacity: bool = False) -> None:
            max_attempts = 1 + max(0, int(args.step_max_retries))
            for attempt in range(1, max_attempts + 1):
                if require_queue_capacity:
                    enforce_queue_guard(
                        context=f"{case_id}:{step_name}:attempt_{attempt}",
                        max_jobs=int(args.max_queue_jobs),
                        max_queued_tests=int(args.max_queued_tests),
                        url=args.url,
                        auto_recover_once=True,
                        stale_queued_age_s=int(args.stale_queued_age_s),
                        allow_container_restart=not bool(args.no_queue_container_restart),
                    )

                step_t0 = time.time()
                update_status(
                    current_step=step_name,
                    current_step_attempt=attempt,
                    step_started_utc=now_utc_iso(),
                    step_elapsed_s=0,
                    heartbeat=f"{step_name} attempt {attempt}/{max_attempts} started",
                )
                try:
                    run(
                        cmd,
                        case_log,
                        on_heartbeat=lambda elapsed: update_status(
                            step_elapsed_s=elapsed,
                            heartbeat=f"{step_name} attempt {attempt}/{max_attempts} running",
                        ),
                    )
                    update_status(
                        last_step_status="ok",
                        step_elapsed_s=int(time.time() - step_t0),
                        heartbeat=f"{step_name} completed",
                    )
                    return
                except Exception as exc:
                    if attempt >= max_attempts:
                        update_status(
                            last_step_status="failed",
                            last_error=f"{step_name} failed after {max_attempts} attempts: {exc}",
                            step_elapsed_s=int(time.time() - step_t0),
                            heartbeat=f"{step_name} failed",
                        )
                        raise

                    wait_s = int(args.step_retry_backoff_s) * (2 ** (attempt - 1))
                    msg = (
                        f"{step_name} attempt {attempt}/{max_attempts} failed for case {case_id}: {exc}. "
                        f"Retrying in {wait_s}s ..."
                    )
                    print(msg)
                    update_status(
                        last_step_status="retrying",
                        last_error=msg,
                        heartbeat=f"{step_name} retry scheduled",
                    )
                    time.sleep(wait_s)

        try:
            manifest_abs = ROOT / manifest_rel
            pinn_cfg_abs = ROOT / pinn_cfg_rel

            # Preserve curated per-case manifests/configs when they already exist.
            if not manifest_abs.exists():
                write_yaml(manifest_abs, build_manifest(case_id, season=args.season))
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
                ], require_queue_capacity=True)

            # Train PINN per case
            checkpoint = ROOT / artifact_rel / "best_model.pt"
            if not args.resume or not checkpoint.exists():
                train_cmd = [
                    py,
                    "-u",
                    "scripts/train_pinn.py",
                    "--config", str(pinn_cfg_rel).replace('\\', '/'),
                    "--artifact-dir", str(artifact_rel).replace('\\', '/'),
                ]
                if args.resume:
                    train_cmd.append("--resume-checkpoint")
                run_step("train_pinn", train_cmd)

            # RC benchmark (all configured RC topology candidates)
            for rc_topology in rc_topologies:
                rc_label = (
                    "rc"
                    if len(rc_topologies) == 1 and rc_topology.upper() == "1R1C"
                    else f"rc_{rc_topology.lower()}"
                )
                rc_out = ROOT / result_rel / rc_label
                if not args.resume or not has_all_episode_outputs(rc_out, test_episode_ids):
                    run_step(f"benchmark_{rc_label}", [
                        py,
                        "-u",
                        "scripts/run_mpc_episode.py",
                        "--predictor", "rc",
                        "--predictor-label", rc_label,
                        "--rc-topology", rc_topology,
                        "--episode", "all-test",
                        "--manifest", str(manifest_rel).replace('\\', '/'),
                        "--mpc-config", "configs/mpc_phase1.yaml",
                        "--checkpoint", str((artifact_rel / "best_model.pt").as_posix()),
                        "--output-dir", str(result_rel).replace('\\', '/'),
                        "--url", args.url,
                        "--case", case_id,
                        "--startup-timeout-s", startup_timeout_s,
                        "--recover-from-queued",
                        "--resume-existing",
                    ], require_queue_capacity=True)

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
                    "--startup-timeout-s", startup_timeout_s,
                    "--recover-from-queued",
                    "--resume-existing",
                ], require_queue_capacity=True)

            # RBC (rule-based control) benchmark
            rbc_out = ROOT / result_rel / "rbc"
            if not args.resume or not has_all_episode_outputs(rbc_out, test_episode_ids):
                run_step("benchmark_rbc", [
                    py,
                    "-u",
                    "scripts/run_mpc_episode.py",
                    "--predictor", "rbc",
                    "--episode", "all-test",
                    "--manifest", str(manifest_rel).replace('\\', '/'),
                    "--mpc-config", "configs/mpc_phase1.yaml",
                    "--checkpoint", str((artifact_rel / "best_model.pt").as_posix()),
                    "--output-dir", str(result_rel).replace('\\', '/'),
                    "--url", args.url,
                    "--case", case_id,
                    "--startup-timeout-s", startup_timeout_s,
                    "--recover-from-queued",
                    "--resume-existing",
                ], require_queue_capacity=True)

            update_status(
                completed_cases=int(status["completed_cases"]) + 1,
                current_step=None,
                current_step_attempt=0,
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

    summary_path = ROOT / results_root.parent / "stage1_failures.json"
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
