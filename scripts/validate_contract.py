#!/usr/bin/env python3
"""
Validates WP1 contract files and manifest consistency.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'pyyaml'. Install with: pip install pyyaml"
        ) from exc

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def validate(workspace: Path) -> int:
    contract_path = workspace / "data_contract" / "signal_contract.yaml"
    schema_path = workspace / "data_contract" / "dataset_schema.json"
    manifest_path = workspace / "manifests" / "phase1_singlezone.yaml"
    metrics_path = workspace / "configs" / "metrics_catalog.yaml"

    missing = [
        str(p) for p in [contract_path, schema_path, manifest_path, metrics_path] if not p.exists()
    ]
    if missing:
        print("Missing required files:")
        for path in missing:
            print(f" - {path}")
        return 2

    contract = _read_yaml(contract_path)
    schema = _read_json(schema_path)
    manifest = _read_yaml(manifest_path)
    metrics = _read_yaml(metrics_path)

    errors: list[str] = []

    if contract.get("primary_case", {}).get("boptest_case") != manifest.get("cases", {}).get("primary"):
        errors.append("Primary BOPTEST case mismatch between signal contract and phase manifest.")

    required_record_fields = {
        "time_s",
        "T_zone_degC",
        "T_outdoor_degC",
        "H_global_Wm2",
        "u_heating",
    }

    records = (
        schema.get("properties", {})
        .get("records", {})
        .get("items", {})
        .get("required", [])
    )
    if set(records) != required_record_fields:
        errors.append(
            "Dataset schema required record fields do not match expected canonical set."
        )

    mandatory_kpis = set(contract.get("kpis", {}).get("mandatory", []))
    if not {"comfort_degree_hours", "total_energy"}.issubset(mandatory_kpis):
        errors.append("Mandatory KPIs must include comfort_degree_hours and total_energy.")

    if "comfort" not in metrics or "energy" not in metrics:
        errors.append("Metrics catalog must define comfort and energy sections.")

    if errors:
        print("Contract validation failed:")
        for err in errors:
            print(f" - {err}")
        return 1

    print("Contract validation successful.")
    print(f"Primary case: {manifest.get('cases', {}).get('primary')}")
    print(f"Surrogate: {manifest.get('models', {}).get('surrogate', {}).get('type')}")
    return 0


def main() -> None:
    workspace = Path(__file__).resolve().parents[1]
    code = validate(workspace)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
