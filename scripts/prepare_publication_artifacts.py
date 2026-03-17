"""Prepare publication-ready artifact bundle with file index and checksums.

This script builds a transparent bundle so every generated result can be
manually inspected and integrity-checked for publication workflows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(paths: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.is_file():
            out.append(p)
            continue
        if p.is_dir():
            out.extend(x for x in p.rglob("*") if x.is_file())
    # Stable ordering for deterministic indexes.
    return sorted(set(out), key=lambda x: str(x).lower())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build publication artifact bundle with checksums.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument(
        "--bundle-dir",
        default="results/eu_rc_vs_pinn/publication_bundle",
        help="Output directory for publication bundle metadata.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    bundle_dir = (root / args.bundle_dir).resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    tracked_targets = [
        root / "results/eu_rc_vs_pinn",
        root / "results/mpc_phase1/benchmark_summary.csv",
        root / "results/mpc_phase1/discomfort_comparison.csv",
        root / "results/mpc_phase1/discomfort_parity_report.csv",
        root / "configs/eu_rc_vs_pinn_campaign.yaml",
        root / "execution_plan_eu_rc_vs_pinn.md",
        root / "WORKFLOW_IDF_TO_BOPTEST_MPC_RESULTS.md",
    ]

    files = iter_files([p for p in tracked_targets if p.exists()])
    files = [p for p in files if bundle_dir not in p.parents and p != bundle_dir]

    file_index = bundle_dir / "file_index.csv"
    with file_index.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["relative_path", "size_bytes", "sha256", "modified_utc"],
        )
        writer.writeheader()
        for path in files:
            stat = path.stat()
            writer.writerow(
                {
                    "relative_path": str(path.relative_to(root)).replace("\\", "/"),
                    "size_bytes": stat.st_size,
                    "sha256": sha256_file(path),
                    "modified_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )

    manifest = {
        "created_utc": datetime.now(tz=timezone.utc).isoformat(),
        "root": str(root),
        "bundle_dir": str(bundle_dir),
        "file_count": len(files),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "index_csv": str(file_index.relative_to(root)).replace("\\", "/"),
    }

    manifest_path = bundle_dir / "bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Bundle metadata created: {manifest_path.relative_to(root)}")
    print(f"Indexed files: {len(files)}")
    print(f"File index: {file_index.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
