#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

AREA_M2 = {
    "bestest_hydronic": 48.0,
    "bestest_hydronic_heat_pump": 48.0,
    "singlezone_commercial_hydronic": 8500.0,
    "twozone_apartment_hydronic": 44.5,
}

ROOTS = [
    Path("results/eu_rc_vs_pinn/raw"),
    Path("results/eu_rc_vs_pinn_fixcheck/raw"),
]

files: list[Path] = []
for root in ROOTS:
    if root.exists():
        files.extend(sorted(root.rglob("*.json")))

print("---PHYSICAL SANITY CHECK---")
print(f"scanned_files={len(files)}")

issues: list[str] = []

for f in files:
    payload = json.loads(f.read_text(encoding="utf-8"))
    case = str(payload.get("case_name", ""))
    ep = str(payload.get("episode_id", f.stem))
    predictor = str(payload.get("predictor", ""))
    diag = payload.get("diagnostic_kpis", {})
    bop = payload.get("boptest_kpis", {})

    energy_wh = float(diag.get("total_energy_Wh", 0.0) or 0.0)
    peak_w = float(diag.get("peak_power_W", 0.0) or 0.0)
    comfort_kh = float(diag.get("comfort_Kh", 0.0) or 0.0)
    area = AREA_M2.get(case)

    # Basic physical checks
    if energy_wh < 0 or peak_w < 0 or comfort_kh < 0:
        issues.append(f"NEGATIVE KPI :: {case}/{predictor}/{ep} :: energy_wh={energy_wh}, peak_w={peak_w}, comfort_kh={comfort_kh}")

    if area:
        e_kwh_m2 = energy_wh / 1000.0 / area
        p_w_m2 = peak_w / area

        if e_kwh_m2 > 300:
            issues.append(f"VERY HIGH ENERGY DENSITY :: {case}/{predictor}/{ep} :: {e_kwh_m2:.2f} kWh/m2")
        if p_w_m2 > 1500:
            issues.append(f"VERY HIGH PEAK DENSITY :: {case}/{predictor}/{ep} :: {p_w_m2:.2f} W/m2")

        # Suspiciously low consumption with meaningful comfort violations
        if e_kwh_m2 < 0.1 and comfort_kh > 10:
            issues.append(f"LOW ENERGY + HIGH DISCOMFORT (SUSPICIOUS) :: {case}/{predictor}/{ep} :: {e_kwh_m2:.3f} kWh/m2, comfort={comfort_kh:.2f} Kh")

    # Consistency check against BOPTEST energy KPI if available
    ener_tot = bop.get("ener_tot")
    if area and ener_tot is not None:
        try:
            ener_tot = float(ener_tot)
            diag_kwh_m2 = energy_wh / 1000.0 / area
            # Compare two possible conventions: ener_tot in kWh/m2 or MWh/m2
            rel_k = abs(diag_kwh_m2 - ener_tot) / max(1e-9, abs(ener_tot))
            rel_m = abs(diag_kwh_m2 - ener_tot * 1000.0) / max(1e-9, abs(ener_tot * 1000.0))
            if min(rel_k, rel_m) > 0.5:
                issues.append(
                    f"ENERGY KPI INCONSISTENCY :: {case}/{predictor}/{ep} :: diag={diag_kwh_m2:.4f} kWh/m2 vs boptest ener_tot={ener_tot}"
                )
        except Exception:
            pass

print(f"issues_found={len(issues)}")
if issues:
    print("\n---ISSUES---")
    for item in issues:
        print(item)
