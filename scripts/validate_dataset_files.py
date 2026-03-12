#!/usr/bin/env python3
"""
Validate generated dataset files against the canonical schema.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def basic_validate(doc: dict) -> list[str]:
    errs: list[str] = []
    required = ["dataset_id", "split", "case_name", "control_interval_s", "horizon_s", "records"]
    for key in required:
        if key not in doc:
            errs.append(f"Missing top-level key: {key}")

    records = doc.get("records", [])
    if not isinstance(records, list):
        errs.append("records must be a list")
        return errs

    req_rec = ["time_s", "T_zone_degC", "T_outdoor_degC", "H_global_Wm2", "u_heating"]
    for idx, rec in enumerate(records[:5]):
        for key in req_rec:
            if key not in rec:
                errs.append(f"records[{idx}] missing key: {key}")
    return errs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", default="datasets/phase1_singlezone")
    parser.add_argument("--schema", default="data_contract/dataset_schema.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    dataset_root = root / args.dataset_root
    schema = load_json(root / args.schema)
    _ = schema

    json_dir = dataset_root / "json"
    if not json_dir.exists():
        raise SystemExit(f"Dataset folder does not exist: {json_dir}")

    jsonschema_validator = None
    try:
        import jsonschema  # type: ignore

        jsonschema_validator = jsonschema.Draft202012Validator(schema)
    except Exception:
        jsonschema_validator = None

    files = sorted(json_dir.glob("*.json"))
    if not files:
        raise SystemExit("No dataset JSON files found.")

    failed = 0
    for path in files:
        doc = load_json(path)
        errs = basic_validate(doc)
        if jsonschema_validator is not None:
            errs.extend([e.message for e in jsonschema_validator.iter_errors(doc)])

        if errs:
            failed += 1
            print(f"FAIL {path.name}")
            for err in errs[:10]:
                print(f" - {err}")
        else:
            print(f"OK   {path.name}")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
