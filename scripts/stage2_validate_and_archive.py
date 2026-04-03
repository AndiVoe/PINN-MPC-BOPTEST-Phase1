#!/usr/bin/env python3
"""
Validate Stage 2 results integrity and prepare publication artifacts.
"""

import argparse
import json
from pathlib import Path
from typing import Any
import hashlib


def verify_result_file(path: Path) -> dict[str, Any]:
    """Verify a result JSON file is valid and complete."""
    result = {
        "path": path.as_posix(),
        "exists": path.exists(),
        "valid_json": False,
        "size_kb": 0,
        "has_diagnostic_kpis": False,
        "has_challenge_kpis": False,
        "episode_id": None,
        "checksum": None,
        "status": "unknown",
    }
    
    if not path.exists():
        result["status"] = "MISSING"
        return result
    
    try:
        result["size_kb"] = path.stat().st_size / 1024
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        result["valid_json"] = True
        
        # Check required fields
        result["has_diagnostic_kpis"] = "diagnostic_kpis" in data
        result["has_challenge_kpis"] = "challenge_kpis" in data
        result["episode_id"] = data.get("episode_id")
        
        # Compute checksum
        result["checksum"] = hashlib.md5(content.encode("utf-8")).hexdigest()
        
        if result["has_diagnostic_kpis"] and result["has_challenge_kpis"]:
            result["status"] = "OK"
        else:
            result["status"] = "INCOMPLETE"
    
    except Exception as e:
        result["status"] = f"ERROR: {str(e)[:50]}"
    
    return result


def validate_stage2_results(raw_root: Path) -> dict[str, Any]:
    """Validate all Stage 2 result files."""
    validation = {
        "total_files": 0,
        "valid_files": 0,
        "missing_files": 0,
        "error_files": 0,
        "by_case": {},
    }
    
    for case_dir in sorted(raw_root.glob("*")):
        if not case_dir.is_dir():
            continue
        
        case_name = case_dir.name
        case_results = {
            "variants": [],
            "all_valid": True,
        }
        
        for variant_dir in sorted(case_dir.glob("*")):
            result_file = variant_dir / "te_std_01.json"
            check = verify_result_file(result_file)
            
            validation["total_files"] += 1
            if check["status"] == "OK":
                validation["valid_files"] += 1
            elif check["status"] == "MISSING":
                validation["missing_files"] += 1
                case_results["all_valid"] = False
            else:
                validation["error_files"] += 1
                case_results["all_valid"] = False
            
            case_results["variants"].append({
                "name": variant_dir.name,
                **check,
            })
        
        validation["by_case"][case_name] = case_results
    
    return validation


def create_validation_report(validation: dict[str, Any], out_path: Path) -> None:
    """Create a markdown validation report."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    lines = [
        "# Stage 2 Results Validation Report",
        "",
        "## Summary",
        "",
        f"- **Total Files Checked**: {validation['total_files']}",
        f"- **Valid Files**: {validation['valid_files']}",
        f"- **Missing Files**: {validation['missing_files']}",
        f"- **Error Files**: {validation['error_files']}",
        "",
    ]
    
    if validation['missing_files'] == 0 and validation['error_files'] == 0:
        lines.append("**Status: ✓ ALL FILES VALID**")
    else:
        lines.append("**Status: ✗ SOME FILES INVALID OR MISSING**")
    
    lines.extend([
        "",
        "## Per-Case Details",
        "",
    ])
    
    for case_name in sorted(validation['by_case'].keys()):
        case_info = validation['by_case'][case_name]
        status_icon = "✓" if case_info['all_valid'] else "✗"
        lines.append(f"### {status_icon} {case_name}")
        lines.append("")
        
        for var in case_info['variants']:
            lines.append(f"#### Variant: `{var['name']}`")
            lines.append(f"- **Status**: {var['status']}")
            lines.append(f"- **File Size**: {var['size_kb']:.2f} KB")
            lines.append(f"- **Valid JSON**: {'✓' if var['valid_json'] else '✗'}")
            lines.append(f"- **Has diagnostic_kpis**: {'✓' if var['has_diagnostic_kpis'] else '✗'}")
            lines.append(f"- **Has challenge_kpis**: {'✓' if var['has_challenge_kpis'] else '✗'}")
            if var['episode_id']:
                lines.append(f"- **Episode ID**: {var['episode_id']}")
            if var['checksum']:
                lines.append(f"- **MD5 Checksum**: {var['checksum']}")
            lines.append("")
    
    report_text = "\n".join(lines)
    out_path.write_text(report_text, encoding="utf-8")
    print(f"✓ Validation report: {out_path.name}")


def create_archive_manifest(raw_root: Path, summary_path: Path, plots_dir: Path, report_path: Path, out_path: Path) -> None:
    """Create a manifest file documenting all publication artifacts."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "stage": "Stage 2: RC Variant Selection & PINN Comparison",
        "date": "2026-04-03",
        "episode": "te_std_01",
        "files": {
            "summary_json": {
                "path": summary_path.as_posix(),
                "description": "Best RC variant per case + PINN comparison metrics",
                "exists": summary_path.exists(),
            },
            "validation_report": {
                "path": (report_path.parent / "VALIDATION_REPORT.md").as_posix(),
                "description": "Data integrity and completeness report",
                "exists": (report_path.parent / "VALIDATION_REPORT.md").exists(),
            },
            "summary_report": {
                "path": report_path.as_posix(),
                "description": "Case-by-case analysis with deltas and metrics",
                "exists": report_path.exists(),
            },
            "plots": {
                "directory": plots_dir.as_posix(),
                "description": "Publication-quality PNG plots (5 figures)",
                "files": [
                    "01_stage2_energy_comparison.png",
                    "02_stage2_comfort_comparison.png",
                    "03_stage2_solve_time_comparison.png",
                    "04_stage2_relative_energy_improvement.png",
                    "05_stage2_cost_comparison.png",
                ] if plots_dir.exists() else [],
            },
            "raw_data": {
                "rc_results": raw_root.as_posix(),
                "description": "30-day episode results for best RC variant per case (te_std_01.json)",
            },
        },
        "intended_use": {
            "article_figures": [
                "01_stage2_energy_comparison.png (main energy figure)",
                "02_stage2_comfort_comparison.png (comfort robustness)",
                "04_stage2_relative_energy_improvement.png (relative gains)",
            ],
            "supplementary": [
                "03_stage2_solve_time_comparison.png (computational cost)",
                "05_stage2_cost_comparison.png (operating cost)",
            ],
        },
    }
    
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"✓ Archive manifest: {out_path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and archive Stage 2 results.")
    parser.add_argument("--raw-root", default="results/eu_rc_vs_pinn_stage2/raw")
    parser.add_argument("--summary", default="results/eu_rc_vs_pinn_stage2/best_rc_vs_pinn_summary.json")
    parser.add_argument("--plots-dir", default="results/eu_rc_vs_pinn_stage2/publication_plots")
    parser.add_argument("--report", default="results/eu_rc_vs_pinn_stage2/STAGE2_SUMMARY_REPORT.md")
    parser.add_argument("--out-validation", default="results/eu_rc_vs_pinn_stage2/VALIDATION_REPORT.md")
    parser.add_argument("--out-manifest", default="results/eu_rc_vs_pinn_stage2/PUBLICATION_MANIFEST.json")
    args = parser.parse_args()
    
    raw_root = Path(args.raw_root)
    if not raw_root.exists():
        print(f"Error: Raw root not found: {raw_root}")
        return 1
    
    print(f"Validating Stage 2 results in: {raw_root}")
    validation = validate_stage2_results(raw_root)
    
    print("\n--- Validation Summary ---")
    print(f"Total files: {validation['total_files']}")
    print(f"Valid: {validation['valid_files']}")
    print(f"Missing: {validation['missing_files']}")
    print(f"Errors: {validation['error_files']}")
    
    print("\n--- Creating Reports ---")
    create_validation_report(validation, Path(args.out_validation))
    create_archive_manifest(
        raw_root,
        Path(args.summary),
        Path(args.plots_dir),
        Path(args.report),
        Path(args.out_manifest),
    )
    
    print(f"\n✓ Validation and archival complete!")
    if validation['missing_files'] == 0 and validation['error_files'] == 0:
        print("✓ All results are valid and ready for publication.")
        return 0
    else:
        print("⚠ Some issues detected — review validation report.")
        return 1


if __name__ == "__main__":
    exit(main())
