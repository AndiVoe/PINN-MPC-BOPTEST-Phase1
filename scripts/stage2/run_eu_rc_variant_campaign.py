#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpc.boptest import BoptestClient


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _load_case_ids(mapping_path: Path) -> list[str]:
    # Some generated mapping files include a UTF-8 BOM on Windows.
    data = json.loads(mapping_path.read_text(encoding="utf-8-sig"))
    out: list[str] = []
    for case in data.get("cases", []):
        if case.get("resolved") and case.get("resolved_api_id"):
            out.append(str(case["resolved_api_id"]))
    if not out:
        raise RuntimeError("No resolved cases in mapping.")
    return out


def _run(cmd: list[str]) -> None:
    print("RUN:", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="RC-only EU campaign for multiple RC variants.")
    parser.add_argument("--mapping", default="results/eu_rc_vs_pinn/runtime_discovery/eu_testcases_resolved_mapping.json")
    parser.add_argument("--variants", default="configs/eu/stage2/rc_variants.yaml")
    parser.add_argument("--manifest-dir", default="manifests/eu")
    parser.add_argument("--manifest-suffix", default="stage1")
    parser.add_argument("--artifact-dir", default="artifacts/eu")
    parser.add_argument("--output-root", default="results/eu_rc_vs_pinn_stage2/raw")
    parser.add_argument("--mpc-config", default="configs/mpc_phase1.yaml")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--episode", default="all-test")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--startup-timeout-s", type=int, default=900)
    args = parser.parse_args()

    py = str(ROOT / ".venv/Scripts/python.exe")
    mapping_path = ROOT / args.mapping
    variants_cfg = _load_yaml(ROOT / args.variants)
    variants = variants_cfg.get("variants", [])
    if not isinstance(variants, list) or not variants:
        raise RuntimeError("No variants defined in rc variants config.")

    case_ids = _load_case_ids(mapping_path)
    if args.max_cases > 0:
        case_ids = case_ids[: args.max_cases]

    failures: list[dict[str, str]] = []

    for case_id in case_ids:
        manifest = Path(args.manifest_dir) / f"{case_id}_{args.manifest_suffix}.yaml"
        ckpt = Path(args.artifact_dir) / case_id / "best_model.pt"
        out_case = Path(args.output_root) / case_id

        if not (ROOT / manifest).exists():
            raise FileNotFoundError(f"Manifest missing: {manifest}")
        if not (ROOT / ckpt).exists():
            raise FileNotFoundError(f"Checkpoint missing: {ckpt}")

        client = BoptestClient(args.url)
        testid = client.select_test_case(case_id)
        client.wait_running(timeout_s=args.startup_timeout_s, poll_s=5)
        print(f"Using shared testid for case {case_id}: {testid}", flush=True)

        try:
            for variant in variants:
                name = str(variant.get("name", "")).strip()
                if not name:
                    raise ValueError("Each variant must have a non-empty 'name'.")

                cmd = [
                    py,
                    "-u",
                    "scripts/run_mpc_episode.py",
                    "--predictor", "rc",
                    "--predictor-label", name,
                    "--episode", args.episode,
                    "--manifest", manifest.as_posix(),
                    "--mpc-config", args.mpc_config,
                    "--checkpoint", ckpt.as_posix(),
                    "--output-dir", out_case.as_posix(),
                    "--url", args.url,
                    "--case", case_id,
                    "--reuse-testid", testid,
                    "--startup-timeout-s", "180",
                    "--recover-from-queued",
                    "--rc-scale-ua", str(float(variant.get("scale_ua", 1.0))),
                    "--rc-scale-solar-gain", str(float(variant.get("scale_solar_gain", 1.0))),
                    "--rc-scale-hvac-gain", str(float(variant.get("scale_hvac_gain", 1.0))),
                    "--rc-scale-capacity", str(float(variant.get("scale_capacity", 1.0))),
                ]
                try:
                    _run(cmd)
                except Exception as exc:
                    failures.append({"case": case_id, "variant": name, "error": str(exc)})
                    print(f"WARN: variant run failed case={case_id} variant={name}: {exc}", flush=True)
        finally:
            try:
                client.stop()
            except Exception:
                pass

    summary_path = ROOT / "results/eu_rc_vs_pinn_stage2/rc_variant_failures.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({"failures": failures}, indent=2), encoding="utf-8")

    print("RC variant campaign complete.")
    print(f"Failure summary: {summary_path.as_posix()}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
