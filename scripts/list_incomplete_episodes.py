#!/usr/bin/env python3
"""
Recovery script to complete missing benchmark episodes.
Identifies incomplete test runs and provides commands to finish them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def find_incomplete_episodes() -> dict[str, list[tuple[str, str]]]:
    """Find all incomplete test cases (missing PINN episodes)."""
    base_dir = Path("results/eu_rc_vs_pinn/raw")
    
    incomplete = {}
    
    for case_dir in sorted(base_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        
        case_name = case_dir.name
        
        # Count episodes for each predictor
        rc_dir = case_dir / "rc"
        pinn_dir = case_dir / "pinn"
        
        rc_episodes = set(f.stem for f in rc_dir.glob("*.json")) if rc_dir.exists() else set()
        pinn_episodes = set(f.stem for f in pinn_dir.glob("*.json")) if pinn_dir.exists() else set()
        
        # Find missing PINN episodes (that RC has)
        missing = rc_episodes - pinn_episodes
        
        if missing:
            # Check if manifest exists
            manifest_path = Path(f"manifests/eu/{case_name}_stage1.yaml")
            if manifest_path.exists():
                incomplete[case_name] = [(ep, str(manifest_path)) for ep in sorted(missing)]
    
    return incomplete


def generate_recovery_commands() -> None:
    """Generate shell commands to recover missing episodes."""
    incomplete = find_incomplete_episodes()
    
    if not incomplete:
        print("✓ All benchmark episodes are complete")
        return
    
    print("=" * 90)
    print("INCOMPLETE EPISODES RECOVERY GUIDE")
    print("=" * 90)
    print(f"\nFound {sum(len(eps) for eps in incomplete.values())} missing episodes:\n")
    
    for case_name, episodes in sorted(incomplete.items()):
        print(f"\n{case_name}: {len(episodes)} missing episodes")
        print(f"  Manifest: manifests/eu/{case_name}_stage1.yaml")
        print(f"  Checkpoint: artifacts/eu/{case_name}/best_model.pt")
        
        # Find the checkpoint and output dir
        checkpoint = Path(f"artifacts/eu/{case_name}/best_model.pt")
        output_dir = Path(f"results/eu_rc_vs_pinn/raw/{case_name}")
        
        if not checkpoint.exists():
            print(f"  ✗ WARNING: Checkpoint does not exist!")
            continue
        
        for episode_id, manifest_path in episodes:
            cmd = (
                f"python scripts/run_mpc_episode.py "
                f"--predictor pinn "
                f"--episode {episode_id} "
                f"--manifest {manifest_path} "
                f"--mpc-config configs/mpc_phase1.yaml "
                f"--checkpoint {checkpoint} "
                f"--output-dir {output_dir} "
                f"--url http://127.0.0.1:8000 "
                f"--case {case_name} "
                f"--startup-timeout-s 420"
            )
            print(f"\n  Episode: {episode_id}")
            print(f"  Command:\n    {cmd}\n")
    
    print("\n" + "=" * 90)
    print("To run all recovery commands at once, use:")
    print("  python scripts/run_recovery_batch.py")
    print("=" * 90)


def main() -> int:
    generate_recovery_commands()
    return 0


if __name__ == "__main__":
    sys.exit(main())
