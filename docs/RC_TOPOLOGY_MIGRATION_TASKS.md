# RC Topology Migration Tasks (1R1C -> R3C2/R4C3/R5C3)

## Objective

Implement true RC topology variants (R3C2, R4C3, R5C3) in the MPC pipeline while keeping backward compatibility with existing 1R1C runs and existing analysis scripts.

## Scope

In scope:
- RC predictor topology support in runtime MPC inference.
- Campaign orchestration to run all RC topology candidates per case.
- Result metadata and file layout updates for topology-aware comparison.
- Backward-compatible behavior for existing `rc` outputs.

Out of scope for Phase 1:
- Re-training PINN artifacts.
- Full scientific re-calibration of every RC topology parameter to measured data.
- Publication text finalization.

## Risks to Control

- Breaking output directory assumptions (`results/.../<predictor>/<episode>.json`).
- Breaking scripts that assume a single RC folder named `rc`.
- Introducing incompatible JSON schema changes in result files.
- Creating RC topologies with unstable rollout dynamics.

## Acceptance Criteria

1. `scripts/run_mpc_episode.py` accepts RC topology selection and stores topology metadata in result JSON.
2. Default behavior without new flags remains compatible with current 1R1C workflow.
3. Stage-1 campaign can execute three RC candidates per case without manual script edits.
4. Existing downstream aggregators continue to run on legacy outputs.
5. New topology outputs can be analyzed without renaming old result folders.

## Execution Checklist

### Phase 1 - Runtime Topology Support

- [x] Add topology-aware RC predictor implementation in `mpc/predictors.py`.
- [x] Keep 1R1C as default topology for backward compatibility.
- [x] Add CLI flag `--rc-topology` in `scripts/run_mpc_episode.py`.
- [x] Save topology and effective parameters under `result["rc_variant"]`.

### Phase 2 - Campaign Wiring

- [x] Add stage-1 RC topology variant config file.
- [x] Update stage-1 campaign runner to iterate RC topology candidates.
- [x] Ensure predictor labels separate outputs per topology (for example `rc_r3c2`).

### Phase 3 - Analysis Compatibility

- [x] Add/adjust helper script to aggregate topology-aware RC outputs.
- [x] Keep old one-RC analysis path untouched for archived runs.
- [x] Add short migration note for users running comparisons.

### Phase 4 - Validation

- [ ] Smoke test one case, one episode, all RC topologies.
- [ ] Verify KPI JSON fields and no missing required keys.
- [ ] Run comparison script on topology-aware outputs.
- [ ] Record failures and rollback path.

## Rollback Plan

- Keep default `--rc-topology 1R1C` and existing `--predictor rc` semantics.
- Keep legacy output structure and scripts unchanged for old runs.
- If variant campaign fails, continue with legacy single-RC run by disabling topology loop.

## Notes for Autonomous Execution

Implementation order:
1. Predictor + episode runner changes.
2. Stage-1 campaign topology loop.
3. Minimal topology-aware aggregation helper.
4. Smoke validation command set and quick report.
