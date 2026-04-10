#!/usr/bin/env python3
"""Monitor PINN campaign completion and trigger analysis/plots when ready."""

import time
import json
from pathlib import Path
import subprocess
import sys

def check_pinn_completion():
    """Check if all 4 PINN outputs are present and valid."""
    cases = [
        'bestest_hydronic',
        'bestest_hydronic_heat_pump',
        'singlezone_commercial_hydronic',
        'twozone_apartment_hydronic'
    ]
    
    results_dir = Path('results/eu_rc_vs_pinn_stage2/raw')
    completed = []
    missing = []
    
    for case in cases:
        pinn_file = results_dir / case / 'pinn' / 'te_std_01.json'
        if pinn_file.exists():
            try:
                with open(pinn_file) as fp:
                    data = json.load(fp)
                if data.get('n_steps') == 2880:
                    completed.append(case)
                else:
                    missing.append((case, 'wrong_n_steps'))
            except Exception as e:
                missing.append((case, str(e)))
        else:
            missing.append((case, 'file_not_found'))
    
    return completed, missing

def main():
    """Monitor PINN and run analysis when complete."""
    print("Monitoring PINN 30-day campaign completion...")
    print("=" * 70)
    
    max_wait_s = 24 * 3600  # 24 hours
    check_interval_s = 300  # Check every 5 minutes
    elapsed_s = 0
    
    while elapsed_s < max_wait_s:
        completed, missing = check_pinn_completion()
        n_completed = len(completed)
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
              f"PINN status: {n_completed}/4 complete", end='')
        
        if missing:
            print(f", {len(missing)} pending")
            for case, reason in missing[:2]:  # Show first 2
                print(f"  - {case}: {reason}")
        else:
            print(" ✓ ALL COMPLETE!")
            print("\n" + "=" * 70)
            print("PINN CAMPAIGN COMPLETE - Proceeding with analysis")
            print("=" * 70)
            
            # Trigger analysis and plotting
            print("\nStep 1: Generating RC vs PINN summary...")
            result = subprocess.run([
                sys.executable, '-u',
                'scripts/stage2/analyze_rc_variants_vs_pinn.py',
                '--rc-root', 'results/eu_rc_vs_pinn_stage2/raw',
                '--episode', 'te_std_01',
                '--out-json', 'results/eu_rc_vs_pinn_stage2/best_rc_vs_pinn_summary.json'
            ], cwd=Path.cwd())
            
            if result.returncode == 0:
                print("\nStep 2: Generating publication plots and reports...")
                result = subprocess.run([
                    sys.executable, '-u',
                    'scripts/stage2_generate_reports_and_plots.py',
                    '--summary', 'results/eu_rc_vs_pinn_stage2/best_rc_vs_pinn_summary.json',
                    '--repo-root', str(Path.cwd()),
                    '--out-dir', 'results/eu_rc_vs_pinn_stage2/plots'
                ], cwd=Path.cwd())
                
                if result.returncode == 0:
                    print("\n" + "=" * 70)
                    print("✓ ANALYSIS COMPLETE")
                    print("=" * 70)
                    print("\nNext steps:")
                    print("  1. Review plots in results/eu_rc_vs_pinn_stage2/plots/")
                    print("  2. Update article with new results and methodology")
                    print("  3. Run: git add -A && git commit && git push")
                    return 0
        
        if elapsed_s < max_wait_s:
            time.sleep(check_interval_s)
            elapsed_s += check_interval_s
    
    print(f"\n✗ Timeout: PINN campaign did not complete within {max_wait_s/3600:.0f} hours")
    return 1

if __name__ == '__main__':
    sys.exit(main())
