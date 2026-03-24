#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

RAW_ROOT = Path("results/eu_rc_vs_pinn/raw")
PLOT_ROOT = Path("results/publication_plots")

required_diag = ["total_energy_Wh", "peak_power_W", "comfort_Kh"]

json_files = sorted(RAW_ROOT.rglob("*.json"))
zero_byte: list[str] = []
bad_json: list[str] = []
missing_kpi: list[str] = []
coverage: dict[tuple[str, str], list[str]] = defaultdict(list)

for f in json_files:
    if f.stat().st_size <= 0:
        zero_byte.append(str(f))
        continue

    try:
        payload = json.loads(f.read_text(encoding="utf-8"))
    except Exception as exc:
        bad_json.append(f"{f} :: {exc}")
        continue

    diag = payload.get("diagnostic_kpis", {})
    missing = [k for k in required_diag if diag.get(k) is None]
    if missing:
        missing_kpi.append(f"{f} :: missing {missing}")

    # Expected path shape: raw/<case>/<predictor>/<episode>.json
    parts = f.parts
    try:
        raw_idx = parts.index("raw")
        case = parts[raw_idx + 1]
        predictor = parts[raw_idx + 2]
        episode = f.stem
        coverage[(case, predictor)].append(episode)
    except Exception:
        pass

print("---RAW JSON FILE INTEGRITY---")
print(f"json_count={len(json_files)}")
print(f"zero_byte_files={len(zero_byte)}")
print(f"json_parse_errors={len(bad_json)}")
print(f"missing_required_kpis={len(missing_kpi)}")

print("\n---EPISODE COVERAGE BY CASE/PREDICTOR---")
for (case, predictor), episodes in sorted(coverage.items()):
    eps = ", ".join(sorted(episodes))
    print(f"{case}/{predictor} :: count={len(episodes)} :: {eps}")

print("\n---PLOT FILE INTEGRITY---")
if PLOT_ROOT.exists():
    pngs = sorted(PLOT_ROOT.glob("*.png"))
    print(f"plot_png_count={len(pngs)}")
    for p in pngs:
        print(f"{p.name} :: {p.stat().st_size / 1024:.1f} KB")
else:
    print("plot directory not found")

print("\n---DETAILS (only if issues exist)---")
if zero_byte:
    print("ZERO BYTE:")
    for x in zero_byte:
        print(x)
if bad_json:
    print("BAD JSON:")
    for x in bad_json:
        print(x)
if missing_kpi:
    print("MISSING KPI:")
    for x in missing_kpi:
        print(x)
if not zero_byte and not bad_json and not missing_kpi:
    print("No integrity issues detected.")
