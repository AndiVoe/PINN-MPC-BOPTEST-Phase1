#!/usr/bin/env python3
"""
Campaign diagnostic and failure analysis tool.
Analyzes the EU campaign results and identifies issues/gaps.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def analyze_campaign_status() -> dict[str, Any]:
    """Analyze campaign live status."""
    status_file = Path("results/eu_rc_vs_pinn/runtime_discovery/campaign_live_status.json")
    
    if not status_file.exists():
        return {"error": "Campaign status file not found"}
    
    status = json.loads(status_file.read_text())
    
    return {
        "state": status.get("state"),
        "total_cases": status.get("total_cases"),
        "completed_cases": status.get("completed_cases"),
        "failed_cases": status.get("failed_cases"),
        "current_case": status.get("current_case", ""),
        "last_error": status.get("last_error", ""),
        "started_utc": status.get("started_utc"),
        "updated_utc": status.get("updated_utc"),
    }


def analyze_artifact_availability() -> dict[str, Any]:
    """Check which trained models are available."""
    artifact_dir = Path("artifacts/eu")
    
    if not artifact_dir.exists():
        return {"error": "No artifacts found"}
    
    models = {}
    for case_dir in artifact_dir.iterdir():
        if case_dir.is_dir():
            model_file = case_dir / "best_model.pt"
            metrics_file = case_dir / "metrics.json"
            
            if model_file.exists():
                model_size_kb = model_file.stat().st_size / 1024
                test_rmse = None
                
                if metrics_file.exists():
                    try:
                        metrics = json.loads(metrics_file.read_text())
                        test_rmse = metrics.get("test", {}).get("rmse_degC")
                    except:
                        pass
                
                models[case_dir.name] = {
                    "model_exists": True,
                    "model_size_kb": round(model_size_kb, 1),
                    "test_rmse_degC": test_rmse,
                    "metrics_exist": metrics_file.exists(),
                }
            else:
                models[case_dir.name] = {
                    "model_exists": False,
                    "model_size_kb": None,
                }
    
    return models


def analyze_results_coverage() -> dict[str, Any]:
    """Check which results have been generated."""
    results_dir = Path("results/eu_rc_vs_pinn/raw")
    
    if not results_dir.exists():
        return {"error": "No results directory found"}
    
    coverage = {}
    
    for case_dir in results_dir.iterdir():
        if case_dir.is_dir():
            case_name = case_dir.name
            
            # Count episodes for each predictor
            rc_episodes = list((case_dir / "rc").glob("*.json")) if (case_dir / "rc").exists() else []
            pinn_episodes = list((case_dir / "pinn").glob("*.json")) if (case_dir / "pinn").exists() else []
            
            coverage[case_name] = {
                "rc_episodes": len(rc_episodes),
                "pinn_episodes": len(pinn_episodes),
                "rc_complete": len(rc_episodes) >= 3,  # assumes 3 test episodes
                "pinn_complete": len(pinn_episodes) >= 3,
            }
    
    return coverage


def analyze_failures() -> dict[str, Any]:
    """Check failure summary if it exists."""
    failure_file = Path("results/eu_rc_vs_pinn/stage1_failures.json")
    
    if not failure_file.exists():
        return {"error": "No failures file found"}
    
    failures = json.loads(failure_file.read_text())
    return failures


def main() -> int:
    print("=" * 80)
    print("EU CAMPAIGN DIAGNOSTIC REPORT")
    print("=" * 80)
    
    # Campaign status
    print("\n1. CAMPAIGN STATUS")
    print("-" * 80)
    status = analyze_campaign_status()
    if "error" in status:
        print(f"  ✗ {status['error']}")
    else:
        print(f"  State: {status.get('state')}")
        print(f"  Progress: {status.get('completed_cases')}/{status.get('total_cases')} cases completed")
        if status.get("failed_cases", 0) > 0:
            print(f"  ✗ Failed cases: {status.get('failed_cases')}")
            if status.get("last_error"):
                # Extract just the key part of the error
                err = status["last_error"]
                lines = err.split("\n")
                for line in lines:
                    if line.strip():
                        print(f"    {line.strip()[:100]}")
        print(f"  Started: {status.get('started_utc')}")
        print(f"  Updated: {status.get('updated_utc')}")
    
    # Model availability
    print("\n2. TRAINED MODELS")
    print("-" * 80)
    models = analyze_artifact_availability()
    if "error" in models:
        print(f"  ✗ {models['error']}")
    else:
        for case_name, info in models.items():
            if info.get("model_exists"):
                rmse_str = f"RMSE={info['test_rmse_degC']:.4f}°C" if info['test_rmse_degC'] else "N/A"
                print(f"  ✓ {case_name}: {info['model_size_kb']:.1f}KB, {rmse_str}")
            else:
                print(f"  ✗ {case_name}: No model file")
    
    # Results coverage
    print("\n3. BENCHMARK RESULTS COVERAGE")
    print("-" * 80)
    coverage = analyze_results_coverage()
    if "error" in coverage:
        print(f"  ✗ {coverage['error']}")
    else:
        for case_name, info in coverage.items():
            rc_status = "✓" if info["rc_complete"] else "✗"
            pinn_status = "✓" if info["pinn_complete"] else "✗"
            print(f"  {case_name}:")
            print(f"    RC:   {rc_status} ({info['rc_episodes']} episodes)")
            print(f"    PINN: {pinn_status} ({info['pinn_episodes']} episodes)")
    
    # Failures
    print("\n4. FAILURE ANALYSIS")
    print("-" * 80)
    failures = analyze_failures()
    if "error" in failures:
        print(f"  No failure details available")
    else:
        if isinstance(failures, dict):
            for key, val in failures.items():
                print(f"  {key}: {val}")
        elif isinstance(failures, list):
            for i, failure in enumerate(failures):
                print(f"  Failure {i+1}: {failure}")
    
    # Summary
    print("\n5. SUMMARY & RECOMMENDATIONS")
    print("-" * 80)
    if status.get("state") == "finished_with_failures":
        print("  ⚠ Campaign did not complete successfully")
        print("  Recommendations:")
        print("    1. Check the last error above")
        print("    2. Review the PINN model for multizone_residential_hydronic")
        print("    3. May need to retrain or investigate BOPTEST compatibility")
    elif status.get("state") == "finished":
        print("  ✓ Campaign completed successfully")
        completed = status.get("completed_cases", 0)
        total = status.get("total_cases", 0)
        if completed == total:
            print(f"  All {total} cases have been benchmarked")
    
    print("\n" + "=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
