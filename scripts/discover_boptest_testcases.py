"""Discover BOPTEST testcase IDs and build European mapping artifacts.

Outputs:
1) Raw endpoint snapshot JSON
2) Flattened testcase table CSV
3) European testcase mapping JSON for campaign usage
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EU_CASES_BY_LABEL = {
    "BESTEST Hydronic": {
        "expected_api_id": "bestest_hydronic",
        "location": "Brussels, Belgium",
    },
    "BESTEST Hydronic Heat Pump": {
        "expected_api_id": "bestest_hydronic_heat_pump",
        "location": "Brussels, Belgium",
    },
    "Single Zone Commercial Hydronic": {
        "expected_api_id": "singlezone_commercial_hydronic",
        "location": "Copenhagen, Denmark",
    },
    "Two Zone Apartment Hydronic": {
        "expected_api_id": "twozone_apartment_hydronic",
        "location": "Milan, Italy",
    },
}


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def fetch_json(url: str, timeout: int = 10) -> Any:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        content = resp.read().decode("utf-8")
    return json.loads(content)


def try_discover_base(urls: list[str]) -> tuple[str | None, dict[str, Any]]:
    errors: dict[str, Any] = {}
    for base in urls:
        base = base.rstrip("/")
        version_url = f"{base}/version"
        testcases_url = f"{base}/testcases"
        try:
            version_data = fetch_json(version_url, timeout=5)
            testcases_data = fetch_json(testcases_url, timeout=10)
            return base, {
                "version": version_data,
                "testcases": testcases_data,
                "version_url": version_url,
                "testcases_url": testcases_url,
            }
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as ex:
            errors[base] = str(ex)
    return None, errors


def flatten_testcases(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                row = dict(item)
                # BOPTEST commonly returns testcaseid in list payloads.
                if "id" not in row and "testcaseid" in row:
                    row["id"] = row["testcaseid"]
                rows.append(row)
            else:
                rows.append({"id": str(item)})
        return rows

    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("id", key)
                rows.append(row)
            else:
                rows.append({"id": key, "value": value})
        return rows

    return [{"id": str(payload)}]


def best_match(testcases: list[dict[str, Any]], expected_id: str, label: str) -> tuple[str | None, float]:
    expected_norm = normalize(expected_id)
    label_norm = normalize(label)
    candidates: list[tuple[str, float]] = []

    for row in testcases:
        api_id = str(row.get("id", "")).strip()
        if not api_id:
            continue
        api_norm = normalize(api_id)

        score = 0.0
        if api_norm == expected_norm:
            score += 1.0
        if expected_norm in api_norm:
            score += 0.6
        if api_norm in expected_norm:
            score += 0.3
        if label_norm and label_norm in api_norm:
            score += 0.5
        name = str(row.get("name", ""))
        if normalize(name) == label_norm:
            score += 0.8
        if score > 0:
            candidates.append((api_id, score))

    if not candidates:
        return None, 0.0

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover BOPTEST testcase IDs and generate EU mapping.")
    parser.add_argument(
        "--base-urls",
        nargs="+",
        default=[
            "http://127.0.0.1:5000",
            "http://127.0.0.1:8000",
            "http://localhost:5000",
            "http://localhost:8000",
        ],
        help="Candidate BOPTEST API base URLs.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/eu_rc_vs_pinn/runtime_discovery",
        help="Output directory for discovery artifacts.",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base, data = try_discover_base(args.base_urls)
    timestamp = datetime.now(timezone.utc).isoformat()

    if base is None:
        failure_path = out_dir / "discovery_failure.json"
        mapping_json = out_dir / "eu_testcases_resolved_mapping.json"
        payload = {
            "created_utc": timestamp,
            "status": "failed",
            "tried_base_urls": args.base_urls,
            "errors": data,
            "hint": "Start BOPTEST API locally and rerun this script.",
        }
        failure_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        unresolved_payload = {
            "created_utc": timestamp,
            "status": "failed",
            "base_url": None,
            "all_resolved": False,
            "cases": [
                {
                    "display_name": label,
                    "location": spec["location"],
                    "expected_api_id": spec["expected_api_id"],
                    "resolved_api_id": None,
                    "match_score": 0.0,
                    "resolved": False,
                }
                for label, spec in EU_CASES_BY_LABEL.items()
            ],
            "failure_json": str(failure_path).replace("\\", "/"),
        }
        mapping_json.write_text(json.dumps(unresolved_payload, indent=2), encoding="utf-8")
        print(f"No reachable BOPTEST API. Wrote: {failure_path}")
        return 2

    snapshot_path = out_dir / "testcases_runtime_snapshot.json"
    snapshot_payload = {
        "created_utc": timestamp,
        "status": "ok",
        "base_url": base,
        "version": data["version"],
        "testcases": data["testcases"],
    }
    snapshot_path.write_text(json.dumps(snapshot_payload, indent=2), encoding="utf-8")

    rows = flatten_testcases(data["testcases"])
    table_csv = out_dir / "testcases_runtime_table.csv"
    fieldnames = sorted({k for row in rows for k in row.keys()})
    if "id" in fieldnames:
        fieldnames.remove("id")
        fieldnames = ["id"] + fieldnames

    with table_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    eu_mapping: list[dict[str, Any]] = []
    for label, spec in EU_CASES_BY_LABEL.items():
        match_id, score = best_match(rows, spec["expected_api_id"], label)
        eu_mapping.append(
            {
                "display_name": label,
                "location": spec["location"],
                "expected_api_id": spec["expected_api_id"],
                "resolved_api_id": match_id,
                "match_score": round(score, 3),
                "resolved": bool(match_id),
            }
        )

    mapping_payload = {
        "created_utc": timestamp,
        "base_url": base,
        "all_resolved": all(x["resolved"] for x in eu_mapping),
        "cases": eu_mapping,
        "snapshot": str(snapshot_path).replace("\\", "/"),
        "table_csv": str(table_csv).replace("\\", "/"),
    }
    mapping_json = out_dir / "eu_testcases_resolved_mapping.json"
    mapping_json.write_text(json.dumps(mapping_payload, indent=2), encoding="utf-8")

    print(f"Connected base URL: {base}")
    print(f"Snapshot:           {snapshot_path}")
    print(f"Table CSV:          {table_csv}")
    print(f"EU mapping:         {mapping_json}")
    print(f"All resolved:       {mapping_payload['all_resolved']}")
    return 0 if mapping_payload["all_resolved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
