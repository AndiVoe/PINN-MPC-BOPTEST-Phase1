#!/usr/bin/env python3
"""Verify corrected energy values after floor area update."""

import json
from pathlib import Path

# Corrected floor areas from BOPTEST specifications
cases = {
    "bestest_hydronic": 48.0,
    "bestest_hydronic_heat_pump": 48.0,
    "singlezone_commercial_hydronic": 8500.0,
    "twozone_apartment_hydronic": 44.5,
}

print("Corrected Energy Normalization (kWh/m²):")
print("=" * 80)

results_dir = Path("results/eu_rc_vs_pinn/raw")
for case_name, area_m2 in cases.items():
    print(f"\n{case_name} (Floor Area: {area_m2} m²)")
    print("-" * 80)
    
    rc_file = results_dir / case_name / "rc" / "te_std_01.json"
    pinn_file = results_dir / case_name / "pinn" / "te_std_01.json"

    missing = [str(p) for p in (rc_file, pinn_file) if not p.exists()]
    if missing:
        print("  Missing result file(s):")
        for path_str in missing:
            print(f"    - {path_str}")
        continue

    for model, fpath in [("RC ", rc_file), ("PINN", pinn_file)]:
        data = json.loads(fpath.read_text())
        diag = data.get("diagnostic_kpis", {})
        energy_wh = float(diag.get("total_energy_Wh", 0))
        energy_kwh = energy_wh / 1000.0
        energy_kwh_m2 = energy_kwh / area_m2
        peak_w = float(diag.get("peak_power_W", 0))
        peak_w_m2 = peak_w / area_m2
        comfort_kh = float(diag.get("comfort_Kh", 0))

        print(f"  {model}: {energy_kwh_m2:7.2f} kWh/m²  | {energy_kwh:8.2f} kWh total | "
              f"{peak_w_m2:6.2f} W/m² peak | {comfort_kh:6.2f} K·h comfort")

print("\n" + "=" * 80)
print("Values now use BOPTEST-specified floor areas (source: testcase documentation)")
