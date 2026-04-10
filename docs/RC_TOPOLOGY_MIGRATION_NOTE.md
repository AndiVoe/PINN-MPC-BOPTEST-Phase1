# RC Topology Migration Note

## What changed

Stage-1 campaign can now run multiple RC topology candidates instead of a single RC baseline:
- R3C2
- R4C3
- R5C3

Default topology for standalone runs remains `1R1C` unless `--rc-topology` is explicitly set.

## New knobs

- `scripts/run_mpc_episode.py`
  - `--rc-topology {1R1C,R3C2,R4C3,R5C3}`
- `scripts/run_eu_campaign_stage1.py`
  - `--rc-topologies-config configs/eu/stage1/rc_topologies.yaml`

## Output layout

- Legacy single RC runs still use `.../rc/<episode>.json`.
- Multi-topology campaign runs use topology-specific labels:
  - `.../rc_r3c2/<episode>.json`
  - `.../rc_r4c3/<episode>.json`
  - `.../rc_r5c3/<episode>.json`

## Aggregation behavior

`aggregate_mpc_results.py` now scans both legacy `rc` and topology-specific `rc_*` folders.
When multiple RC variants exist, it reports the best RC variant by comfort KPI.

## Backward compatibility

Existing historical results and one-RC workflows remain valid.
No migration is required for old artifact folders.
