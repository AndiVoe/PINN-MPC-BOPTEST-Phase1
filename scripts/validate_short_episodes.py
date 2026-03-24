#!/usr/bin/env python3
"""
Run short (1-day) episode tests for heat-pump PINN and twozone RC to validate
control logic before embarking on 7-day runs. This helps avoid worker lockups from
very long simulations.

Tests:
1. bestest_hydronic_heat_pump (PINN), episode: all-test (1 day)
2. twozone_apartment_hydronic (RC), episode: all-test (1 day)
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]


EPISODES = [
    {
        "predictor": "pinn",
        "case": "bestest_hydronic_heat_pump",
        "manifest": "manifests/eu/bestest_hydronic_heat_pump_stage1.yaml",
        "checkpoint": "artifacts/eu/bestest_hydronic_heat_pump/best_model.pt",
        "output_dir": "results/eu_rc_vs_pinn_stage2/validation/bestest_hydronic_heat_pump",
        "episode": "all-test",  # 1-day episode (all-test forecast window is ~24 hours)
    },
    {
        "predictor": "rc",
        "case": "twozone_apartment_hydronic",
        "manifest": "manifests/eu/twozone_apartment_hydronic_stage1.yaml",
        "checkpoint": "artifacts/eu/twozone_apartment_hydronic/best_model.pt",
        "output_dir": "results/eu_rc_vs_pinn_stage2/validation/twozone_apartment_hydronic",
        "episode": "all-test",
    },
]


def log_msg(msg: str) -> None:
    ts = datetime.now().isoformat(timespec='seconds')
    print(f"[{ts}] {msg}")


def run_episode(episode_config: dict) -> dict:
    """Run a single episode. Return status dict."""
    case = episode_config["case"]
    predictor = episode_config["predictor"]
    log_msg(f"Starting {predictor.upper()} episode: {case}")
    
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    
    cmd = [
        str(venv_python),
        "scripts/run_mpc_episode.py",
        "--predictor", predictor,
        "--episode", episode_config["episode"],
        "--manifest", episode_config["manifest"],
        "--mpc-config", "configs/mpc_phase1.yaml",
        "--checkpoint", episode_config["checkpoint"],
        "--output-dir", episode_config["output_dir"],
        "--url", "http://127.0.0.1:8000",
        "--case", case,
        "--startup-timeout-s", "600",  # 10 min for startup (longer than 7-day due to complexity)
        "--recover-from-queued",
    ]
    
    start_time = datetime.now()
    try:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=3600)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if result.returncode == 0:
            log_msg(f"[OK] {case} episode succeeded in {elapsed:.1f}s")
            return {
                "case": case,
                "predictor": predictor,
                "status": "success",
                "elapsed_s": elapsed,
                "output_dir": episode_config["output_dir"],
            }
        else:
            log_msg(f"[FAIL] {case} episode failed (exit code {result.returncode})")
            error_tail = result.stderr[-300:] if result.stderr else "(no stderr)"
            return {
                "case": case,
                "predictor": predictor,
                "status": "error",
                "elapsed_s": elapsed,
                "error": error_tail,
            }
    except subprocess.TimeoutExpired:
        log_msg(f"[TIMEOUT] {case} episode exceeded 1-hour limit (likely stuck in Queued or slow advance)")
        return {
            "case": case,
            "predictor": predictor,
            "status": "timeout",
            "elapsed_s": 3600,
            "error": "Episode timeout after 1 hour",
        }
    except Exception as e:
        log_msg(f"[ERROR] {case} exception: {e}")
        return {
            "case": case,
            "predictor": predictor,
            "status": "error",
            "error": str(e),
        }


def main() -> None:
    log_msg("=" * 70)
    log_msg("SHORT EPISODE VALIDATION: 1-day episodes (heat-pump PINN + twozone RC)")
    log_msg("=" * 70)
    
    results = []
    for ep_config in EPISODES:
        result = run_episode(ep_config)
        results.append(result)
        print()
    
    log_msg("=" * 70)
    log_msg("Short Episode Validation Summary:")
    log_msg("=" * 70)
    
    for r in results:
        case = r["case"]
        predictor = r["predictor"].upper()
        status = r["status"].upper()
        elapsed = r.get("elapsed_s", 0)
        
        if r["status"] == "success":
            log_msg(f"  [{predictor}] {case:40s} {status:10s} {elapsed:8.1f}s")
        else:
            error_msg = r.get("error", "")[:60]
            log_msg(f"  [{predictor}] {case:40s} {status:10s} {elapsed:8.1f}s | {error_msg}")
    
    failed = [r for r in results if r["status"] != "success"]
    if failed:
        log_msg(f"\n[WARNING] {len(failed)} episode(s) failed.")
        sys.exit(1)
    else:
        log_msg(f"\n[OK] All short episodes completed successfully.")
        log_msg("Ready for full 7-day campaign runs.")
        sys.exit(0)


if __name__ == "__main__":
    main()
