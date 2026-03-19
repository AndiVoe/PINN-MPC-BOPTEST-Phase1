# Plot Findings and Fix To-Do

Status legend: `[done]`, `[in progress]`, `[pending]`

## Findings

- [done] The current MPC objective penalizes control magnitude (`u`) rather than plant power, so `energy=0.0001` is often too weak to regularize behavior.
- [done] Signal resolution was based on first-match candidate selection, which is fragile for multi-zone cases and heat-pump cases.
- [done] The existing result JSONs do not expose enough signal-resolution metadata, so QC can mark problematic runs as `PASS` even when forecast channels are missing.
- [done] `twozone_apartment_hydronic` was controlling a single day-zone channel only and had no resolved outdoor/solar forecast signals.
- [done] `multizone_residential_hydronic` is a multi-zone case but was not configured with explicit grouped zone/control mappings.
- [done] `bestest_hydronic_heat_pump` showed unstable PINN behavior consistent with overly loose setpoint bounds and too little smoothing/energy regularization.

## Fix Tasks

- [done] Add explicit signal pinning support in the episode runner.
- [done] Add grouped zone-temperature averaging and grouped control application for multi-zone cases.
- [done] Add per-case MPC overrides in manifests for problematic cases.
- [done] Store resolved signals, mapping warnings, and effective MPC settings in output JSONs.
- [done] Update QC to flag missing forecast signals and excessive control saturation.
- [done] Validate code changes with static checks and targeted reruns.

## Validation Targets

- [done] Re-run `bestest_hydronic_heat_pump` (`te_std_01`) with RC and PINN.
- [done] Re-run `twozone_apartment_hydronic` (`te_std_01`) with grouped thermostat control and explicit weather mapping.
- [done] Re-run `multizone_residential_hydronic` (`te_std_01`) with grouped zone/control mappings.

## Validation Outcomes (Fixcheck)

- [done] New outputs include resolved-signal metadata and effective MPC settings.
- [done] Two-zone weather mapping warning was removed after switching to `weatherStation_*` signals.
- [done] Predictor-specific override split is working: RC uses baseline settings; PINN-only stabilization is applied for heat pump.
- [in progress] Heat-pump PINN still saturates near `u_min` (QC WARN: `high_control_saturation_at_u_min_gt_25pct`).
- [in progress] Multizone RC still saturates near `u_max` (QC WARN: `high_control_saturation_at_u_max_gt_25pct`), suggesting model/control-structure limits rather than mapping bugs.

## Next Actions

- [pending] Tune PINN-specific heat-pump weights/bounds further (or add anti-saturation penalty) to reduce lower-bound lock-in.
- [pending] Define multizone-specific control objective/structure (or zone-weighted objective) to avoid persistent upper-bound saturation.
- [pending] Re-run full `te_std_01..03` for all cases once these two control-behavior issues are addressed.