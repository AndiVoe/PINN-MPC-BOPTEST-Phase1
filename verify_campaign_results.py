#!/usr/bin/env python3
"""Verify 30-day campaign results for plausibility and integrity."""

import json
import glob
import os
import sys
from pathlib import Path

def verify_results():
    """Verify all RC and PINN outputs."""
    
    results_dir = Path('results/eu_rc_vs_pinn_stage2/raw')
    
    # Check RC outputs
    rc_files = sorted(glob.glob(str(results_dir / '*' / 'rc_*' / 'te_std_01.json')))
    pinn_files = sorted(glob.glob(str(results_dir / '*' / 'pinn' / 'te_std_01.json')))
    
    print("=" * 70)
    print("CAMPAIGN RESULTS VERIFICATION")
    print("=" * 70)
    print(f"\nRC outputs found: {len(rc_files)}")
    print(f"PINN outputs found: {len(pinn_files)}")
    print()
    
    # Verify RC outputs
    print("-" * 70)
    print("RC OUTPUTS VERIFICATION")
    print("-" * 70)
    
    if rc_files:
        all_valid = True
        for f in rc_files:
            case = Path(f).parts[-3]
            variant = Path(f).parts[-2]
            
            try:
                with open(f) as fp:
                    data = json.load(fp)
                
                n_steps = data.get('n_steps')
                kpis = data.get('kpi_summary', {})
                
                # Check for critical fields
                has_comfort = 'comfort_dissatisfaction_hours' in kpis
                has_energy = 'energy_use' in kpis
                
                status = "✓" if (n_steps == 2880 and has_comfort and has_energy) else "✗"
                
                if n_steps != 2880:
                    all_valid = False
                    
                print(f"{status} {case:35s} {variant:18s} n_steps={n_steps} "
                      f"comfort={'✓' if has_comfort else '✗'} "
                      f"energy={'✓' if has_energy else '✗'}")
                      
            except Exception as e:
                all_valid = False
                print(f"✗ {case:35s} {variant:18s} ERROR: {e}")
        
        print(f"\nRC outputs: {'VALID' if all_valid else 'ISSUES DETECTED'}")
    else:
        print("No RC outputs found!")
        all_valid = False
    
    # Verify PINN outputs
    print("\n" + "-" * 70)
    print("PINN OUTPUTS VERIFICATION")
    print("-" * 70)
    
    if pinn_files:
        all_pinn_valid = True
        for f in pinn_files:
            case = Path(f).parts[-3]
            
            try:
                with open(f) as fp:
                    data = json.load(fp)
                
                n_steps = data.get('n_steps')
                kpis = data.get('kpi_summary', {})
                has_comfort = 'comfort_dissatisfaction_hours' in kpis
                has_energy = 'energy_use' in kpis
                
                status = "✓" if (n_steps == 2880 and has_comfort and has_energy) else "✗"
                
                print(f"{status} {case:35s} pinn                 n_steps={n_steps} "
                      f"comfort={'✓' if has_comfort else '✗'} "
                      f"energy={'✓' if has_energy else '✗'}")
                      
            except Exception as e:
                all_pinn_valid = False
                print(f"✗ {case:35s} pinn ERROR: {e}")
        
        print(f"\nPINN outputs: {'VALID' if all_pinn_valid else 'ISSUES DETECTED'}")
    else:
        print("No PINN outputs found - PINN campaign needs to be launched")
        all_pinn_valid = False
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"RC outputs: {len(rc_files)}/12 present with n_steps=2880")
    print(f"PINN outputs: {len(pinn_files)}/4 present with n_steps=2880")
    print(f"\nRC Campaign Status: {'✓ COMPLETE' if len(rc_files) == 12 and all_valid else '✗ INCOMPLETE'}")
    print(f"PINN Campaign Status: {'✓ COMPLETE' if len(pinn_files) == 4 else '✗ NEEDS TO RUN'}")
    
    return len(rc_files) == 12 and all_valid, len(pinn_files) == 4

if __name__ == '__main__':
    rc_ok, pinn_ok = verify_results()
    sys.exit(0 if (rc_ok and pinn_ok) else 1)
