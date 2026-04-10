#!/usr/bin/env python
"""Check extreme weather data (te_ext_01 vs te_ext_02) for anomalies."""
import json
import sys

def check_episodes():
    path_ext01 = 'results/mpc_tuning_eval/autotune_v1_10cand/full_validation/cand_001/pinn/te_ext_01.json'
    path_ext02 = 'results/mpc_tuning_eval/autotune_v1_10cand/full_validation/cand_001/pinn/te_ext_02.json'

    with open(path_ext01) as f:
        data01 = json.load(f)
    with open(path_ext02) as f:
        data02 = json.load(f)

    print('=' * 60)
    print('EXTREME WEATHER EPISODE COMPARISON: te_ext_01 vs te_ext_02')
    print('=' * 60)
    
    print('\n=== SUMMARY METRICS ===')
    print(f'{"Metric":<30} {"te_ext_01":<20} {"te_ext_02":<20}')
    print('-' * 70)
    
    for key in ['time_tot', 'cost_tot', 'tdis_tot']:
        val01 = data01.get('challenge_kpis', {}).get(key, {}).get('value', 'N/A')
        val02 = data02.get('challenge_kpis', {}).get(key, {}).get('value', 'N/A')
        print(f'{key:<30} {str(val01):<20} {str(val02):<20}')
    
    print()
    for key in ['total_energy_Wh', 'peak_power_W']:
        diag01 = data01.get('diagnostic_kpis', {}).get(key, 'N/A')
        diag02 = data02.get('diagnostic_kpis', {}).get(key, 'N/A')
        val01 = diag01.get('value', diag01) if isinstance(diag01, dict) else diag01
        val02 = diag02.get('value', diag02) if isinstance(diag02, dict) else diag02
    
    print(f'\n{"N steps":<30} {len(data01.get("step_records", [])):<20} {len(data02.get("step_records", [])):<20}')
    
    # Compare step records statistical properties
    print('\n=== STEP RECORD STATISTICS ===')
    steps01 = data01.get('step_records', [])
    steps02 = data02.get('step_records', [])
    
    if steps01 and steps02:
        from statistics import mean, stdev
        
        def get_stats(steps, key):
            vals = [s.get(key, 0) for s in steps if key in s]
            if not vals:
                return 'N/A', 'N/A', 'N/A'
            return min(vals), mean(vals), max(vals)
        
        for metric in ['t_zone', 'power_w', 'solve_time_ms']:
            min01, mean01, max01 = get_stats(steps01, metric)
            min02, mean02, max02 = get_stats(steps02, metric)
            
            print(f'\n{metric}:')
            print(f'  te_ext_01  min={min01:.2f}, mean={mean01:.2f}, max={max01:.2f}' if isinstance(min01, (int, float)) else f'  te_ext_01  min={min01}, mean={mean01}, max={max01}')
            print(f'  te_ext_02  min={min02:.2f}, mean={mean02:.2f}, max={max02:.2f}' if isinstance(min02, (int, float)) else f'  te_ext_02  min={min02}, mean={mean02}, max={max02}')
    
    # Check for data corruption/duplication
    print('\n=== DATA INTEGRITY CHECK ===')
    
    # Check if te_ext_02 is just a duplicate of te_ext_01
    if steps01 and steps02:
        if len(steps01) == len(steps02):
            matches = sum(1 for s1, s2 in zip(steps01, steps02) if s1.get('t_zone') == s2.get('t_zone'))
            match_pct = 100.0 * matches / len(steps01)
            print(f'Zone temperature matches: {matches}/{len(steps01)} ({match_pct:.1f}%)')
            if match_pct > 90:
                print('  ⚠️  WARNING: te_ext_02 appears to be largely a duplicate of te_ext_01!')
        else:
            print(f'⚠️  Different step counts: {len(steps01)} vs {len(steps02)}')
    
    # Check for NaN/Inf values
    import math
    for ep_name, data in [('te_ext_01', data01), ('te_ext_02', data02)]:
        bad_values = 0
        for step in data.get('step_records', []):
            for key in ['t_zone', 'power_w', 'solve_time_ms']:
                val = step.get(key)
                if isinstance(val, (int, float)) and (math.isnan(val) or math.isinf(val)):
                    bad_values += 1
        if bad_values > 0:
            print(f'⚠️  {ep_name}: Found {bad_values} NaN/Inf values')
        else:
            print(f'✓ {ep_name}: No NaN/Inf values detected')

if __name__ == '__main__':
    check_episodes()
