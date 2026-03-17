"""Probe BOPTEST for actual measurement/input signal names for EU cases 4 and 5."""
import requests, json, pathlib

BASE = "http://127.0.0.1:8000"
CASES = ["twozone_apartment_hydronic", "multizone_residential_hydronic"]
OUT = pathlib.Path("probe_signals_out.json")

results = {}
for case in CASES:
    r = requests.post(f"{BASE}/testcases/{case}/select", timeout=60)
    tid = r.json()["testid"]
    init = requests.put(f"{BASE}/initialize/{tid}", json={"start_time": 0, "warmup_period": 0}, timeout=600)
    meas = sorted(init.json().get("payload", {}).keys())
    inp_r = requests.get(f"{BASE}/inputs/{tid}", timeout=60)
    inp = sorted(inp_r.json().get("payload", {}).keys())
    requests.put(f"{BASE}/stop/{tid}", timeout=60)
    results[case] = {"measurements": meas, "inputs": inp}
    print(f"Done: {case} ({len(meas)} meas, {len(inp)} inputs)")

OUT.write_text(json.dumps(results, indent=2))
print(f"Wrote {OUT}")
