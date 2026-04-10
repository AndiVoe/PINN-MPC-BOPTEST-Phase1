#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CASES = [
    "bestest_hydronic",
    "bestest_hydronic_heat_pump",
    "singlezone_commercial_hydronic",
    "twozone_apartment_hydronic",
]


def _run(cmd: list[str]) -> None:
    print("RUN:", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="PINN-only EU stage2 campaign for 30-day episodes.")
    parser.add_argument("--manifest-dir", default="manifests/eu/stage2")
    parser.add_argument("--artifact-dir", default="artifacts/eu")
    parser.add_argument("--output-root", default="results/eu_rc_vs_pinn_stage2/raw")
    parser.add_argument("--mpc-config", default="configs/mpc_phase1.yaml")
    parser.add_argument("--episode", default="te_std_01")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--startup-timeout-s", type=int, default=900)
    args = parser.parse_args()

    py = str(ROOT / ".venv/Scripts/python.exe")
    failures: list[dict[str, str]] = []

    for case_name in CASES:
        manifest = Path(args.manifest_dir) / f"{case_name}_stage2.yaml"
        ckpt = Path(args.artifact_dir) / case_name / "best_model.pt"
        out_case = Path(args.output_root) / case_name / "pinn"

        if not (ROOT / manifest).exists():
            raise FileNotFoundError(f"Manifest missing: {manifest}")
        if not (ROOT / ckpt).exists():
            raise FileNotFoundError(f"Checkpoint missing: {ckpt}")

        cmd = [
            py,
            "-u",
            "scripts/run_mpc_episode.py",
            "--predictor",
            "pinn",
            "--episode",
            args.episode,
            "--manifest",
            manifest.as_posix(),
            "--mpc-config",
            args.mpc_config,
            "--checkpoint",
            ckpt.as_posix(),
            "--output-dir",
            out_case.as_posix(),
            "--url",
            args.url,
            "--case",
            case_name,
            "--startup-timeout-s",
            str(args.startup_timeout_s),
            "--resume-existing",
        ]
        try:
            _run(cmd)
        except Exception as exc:
            failures.append({"case": case_name, "error": str(exc)})
            print(f"WARN: case run failed case={case_name}: {exc}", flush=True)

    summary_path = ROOT / "results/eu_rc_vs_pinn_stage2/pinn_run_failures.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        __import__("json").dumps({"failures": failures}, indent=2),
        encoding="utf-8",
    )

    print("PINN stage2 campaign complete.")
    print(f"Failure summary: {summary_path.as_posix()}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
