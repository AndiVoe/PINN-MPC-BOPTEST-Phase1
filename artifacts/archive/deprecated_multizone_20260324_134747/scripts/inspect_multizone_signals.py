#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpc.boptest import BoptestClient


def main() -> None:
    manifest = yaml.safe_load(
        Path("manifests/eu/multizone_residential_hydronic_stage1.yaml").read_text(encoding="utf-8")
    )
    case = "multizone_residential_hydronic"
    episode = next(ep for ep in manifest["episodes"] if ep["id"] == "te_std_01")

    client = BoptestClient(base_url="http://127.0.0.1:8000")
    try:
        client.select_test_case(case)
        client.wait_running(timeout_s=240, poll_s=3)
        client.set_scenario({})
        payload = client.initialize(
            start_time_s=int(episode["start_time_s"]),
            warmup_period_s=int(manifest["defaults"]["warmup_period_s"]),
        )
        client.set_step(int(manifest["defaults"]["control_interval_s"]))

        print("payload_keys", len(payload))
        for key in sorted(payload.keys()):
            kl = key.lower()
            if any(t in kl for t in ("reaq", "reap", "power", "pel", "ele", "boi", "pum", "hea", "dh_", "ener")):
                print("Y", key, payload[key])

        inputs = client.get_inputs()
        print("input_keys", len(inputs))
        for key in sorted(inputs.keys()):
            kl = key.lower()
            if any(t in kl for t in ("set", "ove", "boi", "pum", "hea", "sup", "val")):
                print("IN", key)
    finally:
        client.stop()


if __name__ == "__main__":
    main()
