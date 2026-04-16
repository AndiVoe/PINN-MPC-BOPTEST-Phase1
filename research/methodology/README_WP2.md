# WP2 Deliverables (Dataset Generation)

This stage generates train/val/test episodes from BOPTEST and stores schema-compliant JSON datasets.

## New Files

- `manifests/episode_split_phase1.yaml`
  - Explicit split with standard/extreme episode definitions.
  - Case-specific signal mapping candidates.
- `scripts/generate_boptest_datasets.py`
  - Episode runner and exporter.
  - Signal auto-resolution and control injection.
- `scripts/validate_dataset_files.py`
  - Schema/baseline checks for exported datasets.

## Prerequisites

Install dependencies in the active environment:

```powershell
"C:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe" -m pip install requests pyyaml jsonschema
```

## Generate a Smoke Dataset

Run only first 1-2 episodes to test connectivity and mappings:

```powershell
"C:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe" scripts/generate_boptest_datasets.py --url http://127.0.0.1:5000 --case singlezone_commercial_hydronic --max-episodes 2
```

## Validate Exported Files

```powershell
"C:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe" scripts/validate_dataset_files.py
```

## Output Structure

- `datasets/phase1_singlezone/index.json`: summary of successes/failures.
- `datasets/phase1_singlezone/json/*.json`: per-episode datasets.

## Notes

- Scenario setting is best-effort and depends on BOPTEST deployment endpoints.
- If control override points are absent, data will still be generated with baseline control.
