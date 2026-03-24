#!/usr/bin/env python3
"""
Clean old results, temporary artifacts, and outdated data to prevent accidental reuse.

Removes:
1. Old campaign results (eu_rc_vs_pinn/raw - before stage2)
2. Temporary smoke test artifacts (weighting_smoke)
3. Old log files (older than current batch)
4. Diagnostic probe datasets

PRESERVES:
- Newly trained PINN models (artifacts/eu/*/best_model.pt)
- Stage2 results (eu_rc_vs_pinn_stage2/)
- Current configs and manifests
- Datasets used for new training
"""

import argparse
import shutil
import sys
from pathlib import Path
from datetime import datetime, timedelta


ROOT = Path(__file__).resolve().parents[1]


CLEANUP_TARGETS = [
    ("results/eu_rc_vs_pinn/raw", "Old stage1 MPC results"),
    ("results/eu_rc_vs_pinn/runtime_discovery", "Old runtime discovery logs"),
    ("artifacts/weighting_smoke", "Temporary smoke test artifacts"),
    ("artifacts/eu/retrain_manual_summary.json", "Batch training summary archive"),
    ("datasets/eu_probe_bestest_hydronic", "Diagnostic probe dataset (bestest)"),
    ("datasets/eu_probe_timing", "Diagnostic probe dataset (timing - before clean)"),
    ("datasets/eu_probe_timing_clean", "Diagnostic probe dataset (timing - clean)"),
]

PRESERVE_MODELS = [
    "artifacts/eu/singlezone_commercial_hydronic/best_model.pt",
    "artifacts/eu/bestest_hydronic/best_model.pt",
    "artifacts/eu/bestest_hydronic_heat_pump/best_model.pt",
    "artifacts/eu/twozone_apartment_hydronic/best_model.pt",
]


def get_dir_size(path: Path) -> float:
    """Get directory/file size in MB."""
    if path.is_file():
        return path.stat().st_size / (1024 * 1024)
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total / (1024 * 1024)


def cleanup(dry_run: bool = True, verbose: bool = False) -> None:
    """Execute cleanup."""
    ts = datetime.now().isoformat(timespec='seconds')
    print(f"[{ts}] ========================================")
    print(f"[{ts}] CLEANUP: Old Results & Temporary Data")
    print(f"[{ts}] ========================================")
    if dry_run:
        print(f"[{ts}] [MODE] DRY RUN (no files deleted)")
    print()
    
    deleted_count = 0
    total_size_mb = 0.0
    
    # Remove cleanup targets
    print(f"[{ts}] Stage 1: Removing old campaign results and temp artifacts...")
    for target_rel, description in CLEANUP_TARGETS:
        target = ROOT / target_rel
        
        if target.exists():
            size_mb = get_dir_size(target)
            total_size_mb += size_mb
            
            if dry_run:
                print(f"[{ts}]   [DRY RUN] Would delete {description}: {target_rel} (~{size_mb:.1f} MB)")
            else:
                try:
                    if target.is_file():
                        target.unlink()
                    else:
                        shutil.rmtree(target)
                    print(f"[{ts}]   [OK] Deleted {description}: {target_rel} (~{size_mb:.1f} MB)")
                    deleted_count += 1
                except Exception as e:
                    print(f"[{ts}]   [ERROR] Failed to delete {description}: {e}")
        else:
            if verbose:
                print(f"[{ts}]   [SKIP] Not found: {target_rel}")
    
    # Clean old logs (>1 day old)
    print(f"\n[{ts}] Stage 2: Checking old logs (>1 day old)...")
    log_dir = ROOT / "logs/eu_campaign_stage1"
    if log_dir.exists():
        yesterday = datetime.now() - timedelta(days=1)
        old_logs = [f for f in log_dir.glob("*.log") if datetime.fromtimestamp(f.stat().st_mtime) < yesterday and f.name != "preflight.log"]
        
        for log_file in old_logs:
            size_mb = log_file.stat().st_size / (1024 * 1024)
            description = f"Old log ({log_file.stat().st_mtime})"
            
            if dry_run:
                print(f"[{ts}]   [DRY RUN] Would delete {description}: {log_file.name} (~{size_mb:.1f} MB)")
            else:
                try:
                    log_file.unlink()
                    print(f"[{ts}]   [OK] Deleted {description}: {log_file.name} (~{size_mb:.1f} MB)")
                    deleted_count += 1
                except Exception as e:
                    print(f"[{ts}]   [ERROR] Failed to delete old log: {e}")
    
    if log_dir.exists():
        recent_logs = [f for f in log_dir.glob("*.log") if f.is_file()]
        print(f"[{ts}]   Preserved {len(recent_logs)} recent log files")
    
    # Verify preservation
    print(f"\n[{ts}] Stage 3: Verifying newly trained models are PRESERVED...")
    all_preserved = True
    for model_rel in PRESERVE_MODELS:
        model = ROOT / model_rel
        if model.exists():
            size_mb = model.stat().st_size / (1024 * 1024)
            print(f"[{ts}]   [OK] Preserved: {model_rel} ({size_mb:.1f} MB)")
        else:
            print(f"[{ts}]   [ERROR] MISSING: {model_rel}")
            all_preserved = False
    
    print()
    print(f"[{ts}] ========================================")
    if all_preserved:
        print(f"[{ts}] ✓ Cleanup verification PASSED")
        if not dry_run:
            print(f"[{ts}] Deleted: {deleted_count} items (~{total_size_mb:.1f} MB)")
    else:
        print(f"[{ts}] ✗ Cleanup verification FAILED - some models missing!")
        sys.exit(1)
    print(f"[{ts}] ========================================")
    
    if dry_run:
        print()
        print(f"[{ts}] To execute cleanup (WARNING - irreversible):")
        print(f"[{ts}]   python scripts/cleanup_old_data.py --execute")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean old results and temporary data.")
    parser.add_argument("--execute", action="store_true", help="Really delete (default is dry-run).")
    parser.add_argument("--verbose", action="store_true", help="Verbose output.")
    args = parser.parse_args()
    
    cleanup(dry_run=not args.execute, verbose=args.verbose)


if __name__ == "__main__":
    main()
