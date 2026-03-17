#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from requests import RequestException


@dataclass
class DockerStats:
    available: bool
    queue_len_jobs: int | None = None
    tests_total: int | None = None
    tests_queued: int | None = None
    tests_running: int | None = None
    running_containers: str = ""
    all_containers: str = ""
    note: str = ""


def _json_get(url: str, timeout: int = 15) -> Any:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _json_post(url: str, timeout: int = 30) -> Any:
    resp = requests.post(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _json_put(url: str, body: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    resp = requests.put(url, json=body or {}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _status_payload(raw: Any) -> str:
    if isinstance(raw, dict) and "payload" in raw:
        return str(raw["payload"])
    return str(raw).strip('"')


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def _docker_stats() -> DockerStats:
    if shutil.which("docker") is None:
        return DockerStats(available=False, note="docker not found in PATH")

    running = _run(["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"])
    all_ctrs = _run(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"])

    if running.returncode != 0:
        note = (running.stderr or running.stdout or "docker ps failed").strip()
        return DockerStats(available=False, note=note)

    stats = DockerStats(
        available=True,
        running_containers=running.stdout.strip(),
        all_containers=all_ctrs.stdout.strip(),
    )

    redis_name = "project1-boptest-redis-1"
    q = _run(["docker", "exec", redis_name, "redis-cli", "LLEN", "jobs"])
    if q.returncode == 0:
        try:
            stats.queue_len_jobs = int((q.stdout or "").strip().splitlines()[-1])
        except Exception:
            pass

    script = (
        "local q=0; local r=0; local tot=0; "
        "for _,k in ipairs(redis.call('keys','tests:*')) do "
        "tot=tot+1; local s=redis.call('hget',k,'status'); "
        "if s=='Queued' then q=q+1 elseif s=='Running' then r=r+1 end; "
        "end; return {tot,q,r}"
    )
    cnt = _run(["docker", "exec", redis_name, "redis-cli", "--raw", "EVAL", script, "0"])
    if cnt.returncode == 0:
        lines = [x.strip() for x in cnt.stdout.splitlines() if x.strip()]
        if len(lines) >= 3:
            try:
                stats.tests_total = int(lines[0])
                stats.tests_queued = int(lines[1])
                stats.tests_running = int(lines[2])
            except Exception:
                pass

    return stats


def _pick_testcase_id(testcases_payload: Any, fallback_case: str) -> str:
    candidates = []
    if isinstance(testcases_payload, dict):
        payload = testcases_payload.get("payload")
        if isinstance(payload, list):
            candidates = payload
    elif isinstance(testcases_payload, list):
        candidates = testcases_payload

    names: list[str] = []
    for item in candidates:
        if isinstance(item, dict):
            tc = item.get("testcaseid") or item.get("id")
            if isinstance(tc, str):
                names.append(tc)

    if fallback_case in names:
        return fallback_case
    if "bestest_air" in names:
        return "bestest_air"
    if names:
        return names[0]
    return fallback_case


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight diagnostics for BOPTEST queue health.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--case", default="bestest_air")
    parser.add_argument("--max-wait-s", type=int, default=90)
    parser.add_argument("--poll-s", type=int, default=2)
    parser.add_argument("--output", default="results/eu_rc_vs_pinn/runtime_discovery/preflight_report.json")
    parser.add_argument("--require-running", action="store_true")
    args = parser.parse_args()

    report: dict[str, Any] = {
        "url": args.url.rstrip("/"),
        "requested_case": args.case,
        "max_wait_s": int(args.max_wait_s),
        "poll_s": int(args.poll_s),
    }

    base = report["url"]
    version_payload = _json_get(f"{base}/version", timeout=10)
    report["version"] = version_payload

    testcases_payload = _json_get(f"{base}/testcases", timeout=20)
    report["testcases"] = {
        "count": len(testcases_payload.get("payload", [])) if isinstance(testcases_payload, dict) else None
    }
    case_id = _pick_testcase_id(testcases_payload, args.case)
    report["selected_probe_case"] = case_id

    docker_stats = _docker_stats()
    report["docker"] = {
        "available": docker_stats.available,
        "queue_len_jobs": docker_stats.queue_len_jobs,
        "tests_total": docker_stats.tests_total,
        "tests_queued": docker_stats.tests_queued,
        "tests_running": docker_stats.tests_running,
        "note": docker_stats.note,
    }

    status_log: list[dict[str, Any]] = []
    running = False
    probe_testid: str | None = None
    try:
        select = _json_post(f"{base}/testcases/{case_id}/select", timeout=120)
        probe_testid = select.get("testid") or select.get("payload", {}).get("testid")
        if not probe_testid:
            raise RuntimeError(f"Could not read testid from select response: {select}")
        report["probe_testid"] = probe_testid

        start = time.time()
        while (time.time() - start) < args.max_wait_s:
            status_resp = _json_get(f"{base}/status/{probe_testid}", timeout=15)
            status = _status_payload(status_resp)
            elapsed = int(time.time() - start)
            status_log.append({"elapsed_s": elapsed, "status": status})
            if status == "Running":
                running = True
                break
            time.sleep(max(1, int(args.poll_s)))
    except RequestException as exc:
        report["probe_select_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if probe_testid:
            try:
                _json_put(f"{base}/stop/{probe_testid}", timeout=30)
            except Exception:
                pass

    report["probe_status_log"] = status_log
    report["probe_reached_running"] = running

    diagnosis = "healthy"
    recommendations: list[str] = []
    if not running:
        diagnosis = "queue_or_worker_blocked"
        recommendations.extend([
            "Verify local deployment is started exactly as upstream docs specify: docker compose up web worker provision",
            "Check queue saturation in Redis (LLEN jobs) and stale tests (tests:* hashes); backlog can keep new tests queued for hours",
            "Perform a clean shutdown/redeploy if backlog is stale: docker compose down, then docker compose up web worker provision",
            "If using Podman, verify port and provision readiness per PODMAN-MIGRATION troubleshooting",
            "Inspect logs for web/worker/provision for storage/redis/bootstrap errors",
        ])

        if docker_stats.queue_len_jobs is not None and docker_stats.queue_len_jobs > 0:
            recommendations.append(
                f"Current Redis jobs backlog detected: {docker_stats.queue_len_jobs}. Wait time can grow roughly with backlog * BOPTEST_TIMEOUT."
            )
        if "probe_select_error" in report:
            recommendations.append(
                "The select endpoint timed out, which indicates API saturation or deep queue pressure before status polling even begins."
            )

    report["diagnosis"] = diagnosis
    report["recommendations"] = recommendations

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))

    if args.require_running and not running:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
