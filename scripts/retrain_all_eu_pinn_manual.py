#!/usr/bin/env python3
"""
Retrain all EU stage-1 PINN models with manual loss weighting.

This script sequentially trains all 4 active case-specific PINN models:
1. singlezone_commercial_hydronic
2. bestest_hydronic
3. bestest_hydronic_heat_pump
4. twozone_apartment_hydronic

Uses manual weighting mode (empirically best from smoke test).
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]


CASES = [
    ("singlezone_commercial_hydronic", "configs/eu/pinn_singlezone_commercial_hydronic.yaml"),
    ("bestest_hydronic", "configs/eu/pinn_bestest_hydronic.yaml"),
    ("bestest_hydronic_heat_pump", "configs/eu/pinn_bestest_hydronic_heat_pump.yaml"),
    ("twozone_apartment_hydronic", "configs/eu/pinn_twozone_apartment_hydronic.yaml"),
]


def log_progress(msg: str) -> None:
    ts = datetime.now().isoformat(timespec='seconds')
    print(f"[{ts}] {msg}")


def train_case(case_name: str, config_path: str) -> dict:
    """Train a single case. Return result dict with status."""
    log_progress(f"Starting training: {case_name}")
    
    artifact_dir = f"artifacts/eu/{case_name}"
    
    # Use activated venv Python directly
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = ROOT / ".venv" / "bin" / "python"
    
    cmd = [
        str(venv_python),
        "scripts/train_pinn.py",
        "--config", config_path,
        "--artifact-dir", artifact_dir,
    ]
    
    start_time = datetime.now()
    try:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=3600)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if result.returncode == 0:
            try:
                output = json.loads(result.stdout)
                log_progress(f"[OK] Completed {case_name} in {elapsed:.1f}s: val_loss={output.get('best_val_loss', 'N/A')}")
                return {
                    "case": case_name,
                    "status": "success",
                    "elapsed_s": elapsed,
                    "output": output,
                }
            except json.JSONDecodeError:
                log_progress(f"[WARN] {case_name} completed but output was not valid JSON.")
                return {
                    "case": case_name,
                    "status": "warning",
                    "elapsed_s": elapsed,
                    "error": "Invalid JSON output",
                    "stdout": result.stdout[-500:] if result.stdout else "",
                }
        else:
            log_progress(f"[FAIL] Failed {case_name} (exit code {result.returncode}):\n{result.stderr[-500:]}")
            return {
                "case": case_name,
                "status": "error",
                "elapsed_s": elapsed,
                "error": result.stderr[-500:] if result.stderr else "Unknown error",
            }
    except subprocess.TimeoutExpired:
        log_progress(f"[TIMEOUT] {case_name} (exceeded 3600s)")
        return {
            "case": case_name,
            "status": "timeout",
            "elapsed_s": 3600,
            "error": "Training exceeded 1-hour timeout",
        }
    except Exception as e:
        log_progress(f"[ERROR] Exception {case_name}: {e}")
        return {
            "case": case_name,
            "status": "error",
            "error": str(e),
        }


def main() -> None:
    log_progress("=" * 70)
    log_progress("BATCH PINN RETRAINING: Manual Weighting Mode (EU Stage1)")
    log_progress("=" * 70)
    
    results = []
    for case_name, config_path in CASES:
        result = train_case(case_name, config_path)
        results.append(result)
        print()
    
    # Write summary
    summary_path = ROOT / "artifacts/eu/retrain_manual_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "cases": CASES,
            "results": results,
            "summary": {
                "total": len(results),
                "success": sum(1 for r in results if r["status"] == "success"),
                "failed": sum(1 for r in results if r["status"] in ("error", "timeout")),
                "warning": sum(1 for r in results if r["status"] == "warning"),
            }
        }, f, indent=2)
    
    log_progress("=" * 70)
    log_progress(f"Summary written to {summary_path}")
    log_progress("=" * 70)
    
    # Print summary table
    print("\nTraining Summary:")
    print("-" * 80)
    for r in results:
        case = r["case"]
        status = r["status"].upper()
        elapsed = r.get("elapsed_s", 0)
        if r["status"] == "success":
            best_loss = r["output"].get("best_val_loss", "?")
            print(f"  {case:40s} {status:10s} {elapsed:8.1f}s  best_loss={best_loss}")
        else:
            error_msg = r.get("error", "")[:50]
            print(f"  {case:40s} {status:10s} {elapsed:8.1f}s  {error_msg}")
    
    # Exit with error if any cases failed
    failed = [r for r in results if r["status"] in ("error", "timeout")]
    if failed:
        print(f"\n[WARNING] {len(failed)} case(s) failed. See summary for details.")
        sys.exit(1)
    else:
        print("\n[OK] All cases trained successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
