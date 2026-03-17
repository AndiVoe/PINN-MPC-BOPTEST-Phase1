#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cmd(cmd: list[str]) -> None:
	print(f"RUN: {' '.join(cmd)}", flush=True)
	result = subprocess.run(cmd, cwd=ROOT)
	if result.returncode != 0:
		raise RuntimeError(f"Command failed with code {result.returncode}: {' '.join(cmd)}")


def main() -> None:
	parser = argparse.ArgumentParser(description="Run multi-seed PINN train + MPC test sweep.")
	parser.add_argument(
		"--python",
		default=str(Path(".venv") / "Scripts" / "python.exe"),
	)
	parser.add_argument("--config", default="configs/pinn_phase1.yaml")
	parser.add_argument(
		"--seeds",
		nargs="+",
		type=int,
		default=[11, 22, 33, 44, 55],
	)
	parser.add_argument("--startup-timeout-s", type=int, default=240)
	parser.add_argument("--skip-mpc", action="store_true", help="Only train models for each seed.")
	args = parser.parse_args()

	py = str((ROOT / args.python))
	all_runs: list[dict[str, object]] = []

	for seed in args.seeds:
		artifact_dir = f"artifacts/seed_sweep/pinn_seed_{seed}"
		output_dir = f"results/seed_sweep/pinn_seed_{seed}"

		run_cmd([
			py,
			"scripts/train_pinn.py",
			"--config",
			args.config,
			"--artifact-dir",
			artifact_dir,
			"--seed",
			str(seed),
		])

		run_info: dict[str, object] = {
			"seed": seed,
			"artifact_dir": artifact_dir,
		}

		if not args.skip_mpc:
			run_cmd([
				py,
				"scripts/run_mpc_episode.py",
				"--predictor",
				"pinn",
				"--episode",
				"all-test",
				"--checkpoint",
				f"{artifact_dir}/best_model.pt",
				"--output-dir",
				output_dir,
				"--startup-timeout-s",
				str(args.startup_timeout_s),
				"--recover-from-queued",
			])
			run_info["output_dir"] = output_dir

		all_runs.append(run_info)

	summary_path = ROOT / "results" / "seed_sweep" / "seed_sweep_runs.json"
	summary_path.parent.mkdir(parents=True, exist_ok=True)
	summary_path.write_text(json.dumps({"runs": all_runs}, indent=2), encoding="utf-8")
	print(f"Wrote seed sweep run manifest: {summary_path}")


if __name__ == "__main__":
	try:
		main()
	except Exception as exc:
		print(f"ERROR: {exc}")
		raise
