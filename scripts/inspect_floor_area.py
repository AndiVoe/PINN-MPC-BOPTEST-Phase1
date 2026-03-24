#!/usr/bin/env python3
"""Inspect available floor area data in BOPTEST results."""

import json
from pathlib import Path

raw_root = Path('results/eu_rc_vs_pinn/raw')

for case_dir in sorted(raw_root.glob('*/')):
    case = case_dir.name
    ep_files = list(case_dir.glob('rc/te_std_01.json')) or list(case_dir.glob('pinn/te_std_01.json'))
    if not ep_files:
        print(f'\n=== {case} === NO DATA FOUND')
        continue
    ep_file = ep_files[0]
    
    with open(ep_file) as f:
        data = json.load(f)
    
    print(f'\n=== {case} ===')
    
    # Check diagnostic KPIs
    diag = data.get('diagnostic_kpis', {})
    print(f'Total Energy: {diag.get("total_energy_Wh"):,.0f} Wh')
    print(f'Peak Heating Power: {diag.get("peak_heating_power_W"):,.1f} W')
    print(f'Peak Power: {diag.get("peak_power_W"):,.1f} W')
    
    # Check challenge KPIs
    chall = data.get('challenge_kpis', {})
    if 'pdih_tot' in chall:
        pdih = chall['pdih_tot']
        if isinstance(pdih, dict):
            print(f'pdih_tot: {pdih.get("value"):.3f} {pdih.get("unit")} - {pdih.get("description")}')
        else:
            print(f'pdih_tot: {pdih}')
    
    # Print all challenge KPI keys
    print(f'All challenge_kpi keys: {", ".join(chall.keys())}')
    
    # Check boptest_kpis
    boptest = data.get('boptest_kpis', {})
    print(f'All boptest_kpi keys: {", ".join(list(boptest.keys())[:10])}{"..." if len(boptest) > 10 else ""}')
    
    # Look for area-related info anywhere
    for section_name, section in [('diagnostic_kpis', diag), ('challenge_kpis', chall), ('boptest_kpis', boptest)]:
        for key in section.keys():
            if any(x in key.lower() for x in ['area', 'floor', 'surface', 'gross', 'net', 'conditioned']):
                val = section[key]
                if isinstance(val, dict):
                    val = val.get('value', val)
                print(f'  FOUND IN {section_name}: {key} = {val}')
