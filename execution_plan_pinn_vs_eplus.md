# PINN vs EnergyPlus MPC Comparison - Execution Plan

Date: 2026-03-11

## Scope Lock (based on user decisions)

- Surrogate model: PINN only (no LSTM in first pass).
- Primary objectives: Thermal comfort and energy consumption.
- Preferred approach: Clean and rigorous setup, not a quick prototype.
- Available IDF currently: `bestest_naive.idf` (BESTEST Case 600 style, single-zone behavior).

## Test Case Recommendation

### Recommendation for Phase 1

Use `singlezone_commercial_hydronic` as the primary BOPTEST benchmark for the first rigorous comparison.

Why:
- Lower system complexity makes model mismatch diagnosis easier.
- Faster iteration for PINN training and MPC debugging.
- Clearer attribution of errors (plant dynamics vs controller settings vs training data).

### Recommendation for Phase 2

Promote to `multizone_office_simple_hydronic` once the full pipeline is validated on single-zone.

Why:
- Better realism and stronger external validity.
- More challenging dynamics for proving surrogate utility.

## KPI Set

### Mandatory KPIs

- Thermal comfort violation (Kh or degree-hour discomfort).
- Total HVAC/thermal/electrical energy over episode.

### Strongly Recommended Additional KPIs

- Peak power demand (kW) and 95th percentile power.
- Control smoothness (sum of absolute control moves).
- Constraint violation count (hard-limit exceedance events).
- MPC solve-time statistics (mean/p95/max per control step).
- End-to-end wall-clock simulation time per episode.
- Feasibility rate (% steps with feasible optimization).

Optional if signals are available:
- CO2 concentration violations.
- Cost and/or emissions (if tariff/carbon factors provided).

## Fair Comparison Rules (must hold)

Use identical for both controllers:
- Prediction horizon.
- Control interval.
- Objective weights.
- Comfort bounds.
- Actuator and rate constraints.
- Forecast inputs and uncertainty assumptions.
- Initialization and warmup logic.
- Evaluation weather episodes.

## Dual-Protocol Benchmark Design (locked)

To ensure both methodological rigor and practical relevance, run and report two protocols.

### Protocol A: Fixed-Weight Fair Benchmark (primary)

Goal:
- Isolate predictor effect only (RC vs PINN) under identical MPC settings.

Rules:
- Use one shared MPC configuration for both predictors.
- Do not allow predictor-specific MPC overrides in manifests.
- Keep train/val/test episode definitions fixed.
- Use identical startup/warmup and episode metadata.

Current fairness action from audit:
- Remove or neutralize `predictor_mpc_overrides` for strict A-runs.
- In current manifests, predictor-specific overrides are present in:
  - `manifests/eu/bestest_hydronic_heat_pump_stage1.yaml` (PINN override)
  - `manifests/eu/singlezone_commercial_hydronic_stage1.yaml` (RC override)

Execution practice:
- Create strict fair manifest variants with no predictor-specific overrides.
- Store outputs in a protocol-specific folder (example: `results/eu_rc_vs_pinn/protocol_a_fixed/`).

Protocol A manifests prepared:
- manifests/eu/bestest_hydronic_heat_pump_stage1_protocol_a.yaml
- manifests/eu/singlezone_commercial_hydronic_stage1_protocol_a.yaml

Protocol A command templates (test episodes):
- RC:
  c:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe -u scripts/run_mpc_episode.py --predictor rc --episode all-test --manifest manifests/eu/bestest_hydronic_heat_pump_stage1_protocol_a.yaml --mpc-config configs/mpc_phase1.yaml --checkpoint artifacts/eu/bestest_hydronic_heat_pump/best_model.pt --output-dir results/eu_rc_vs_pinn/protocol_a_fixed/raw/bestest_hydronic_heat_pump --url http://127.0.0.1:8000 --case bestest_hydronic_heat_pump --startup-timeout-s 420 --recover-from-queued --resume-existing
- PINN:
  c:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe -u scripts/run_mpc_episode.py --predictor pinn --episode all-test --manifest manifests/eu/bestest_hydronic_heat_pump_stage1_protocol_a.yaml --mpc-config configs/mpc_phase1.yaml --checkpoint artifacts/eu/bestest_hydronic_heat_pump/best_model.pt --output-dir results/eu_rc_vs_pinn/protocol_a_fixed/raw/bestest_hydronic_heat_pump --url http://127.0.0.1:8000 --case bestest_hydronic_heat_pump --startup-timeout-s 420 --recover-from-queued --resume-existing

Analysis templates on Protocol A outputs:
- c:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe -u scripts/qc_eu_results.py --raw-root results/eu_rc_vs_pinn/protocol_a_fixed/raw --out-dir results/eu_rc_vs_pinn/protocol_a_fixed/qc
- c:/Users/AVoelser/OneDrive - Scientific Network South Tyrol/3_PhD/Simulation/PINN/.venv/Scripts/python.exe -u scripts/validate_discomfort_parity.py --results-root results/eu_rc_vs_pinn/protocol_a_fixed/raw/bestest_hydronic_heat_pump --output results/eu_rc_vs_pinn/protocol_a_fixed/discomfort_parity_report_bestest_hydronic_heat_pump.csv

### Protocol B: Model-Tuned Benchmark (secondary)

Goal:
- Measure best-achievable practical performance per predictor under a controlled, symmetric tuning budget.

Rules:
- Allow predictor-specific tuning of MPC weights and optional solver settings.
- Tune only on training/validation episodes, never on test/future-test episodes.
- Use equal tuning budget for RC and PINN (same number of trials and same stopping policy).
- Freeze tuned settings before test execution.

Execution practice:
- Keep tuned settings explicit in manifest/config artifacts.
- Store outputs in a separate folder (example: `results/eu_rc_vs_pinn/protocol_b_tuned/`).

### Reporting Policy

- Treat Protocol A as the primary scientific fairness claim.
- Treat Protocol B as a deployment-oriented practical benchmark.
- Publish both with clear labeling to avoid mixing conclusions.

## Data Strategy (BOPTEST constraints and weather)

Generate training/validation/test data from BOPTEST episodes:

- Standard weather scenarios.
- Extreme weather scenarios.

Split policy:
- Train: mostly standard + subset of extreme.
- Validation: held-out standard/extreme days.
- Test: fully unseen episodes (both standard and extreme).

Avoid leakage:
- No overlap of timestamps/episodes across splits.
- Keep test episodes untouched until final evaluation.

## Architecture

### Plant Side

- White-box reference: BOPTEST plant behavior and KPIs.
- Secondary white-box traceability: EnergyPlus runs from IDF where aligned.

### Surrogate Side (PINN)

- Inputs: weather, occupancy/internal gains proxies, and control actions.
- Outputs: key temperatures + energy/power proxy states needed by MPC objective.
- Physics regularization: thermal-balance residual terms to constrain extrapolation.

### Controller

- One MPC formulation, two prediction models:
  - MPC-Eplus/plant model
  - MPC-PINN surrogate model

## Minimal-Docker Strategy

Given Docker connectivity issues, use Docker only when necessary for benchmark ground truth.

Primary run mode during development:
- Use local BOPTEST Python testcase interface where possible (FMU direct mode).
- Reuse existing direct mode pattern already present in `closed_loop_runner.py` (`--direct`).

Validation checkpoints can still be run against web API when connection is stable.

## Work Packages and Timeline (clean version)

1. WP1 - Signal Contract and Case Lock (3-4 days)
- Freeze case, signals, units, and constraints.
- Define one canonical data schema used by both models.

2. WP2 - Data Generation Pipeline (1-1.5 weeks)
- Build scripts for weather scenario episode generation.
- Export aligned train/val/test datasets with metadata.

3. WP3 - PINN Training + Validation (1.5-2.5 weeks)
- Implement/train PINN.
- Tune loss weights and regularization.
- Validate on held-out episodes.

4. WP4 - MPC Integration (1-1.5 weeks)
- Integrate PINN predictor into MPC loop.
- Stabilize optimization and constraints.

5. WP5 - Benchmark Campaign (1-1.5 weeks)
- Run matched experiments for both models.
- Collect KPI and runtime statistics with confidence intervals.

6. WP6 - Robustness + Documentation (1-2 weeks)
- Stress tests (extreme weather, forecast errors).
- Write methods, assumptions, limitations.

Estimated total: 7 to 10 weeks for a rigorous single-case study.

## Key Risks and Mitigations

- Risk: IDF and BOPTEST plant mismatch.
  - Mitigation: treat BOPTEST plant as evaluation authority; use IDF-based model as a controlled comparator with explicit caveats.

- Risk: PINN unstable on extremes.
  - Mitigation: include extreme weather in training and residual regularization; evaluate OOD explicitly.

- Risk: MPC infeasibility spikes.
  - Mitigation: soft constraints with penalty continuation and fallback control policy.

- Risk: runtime comparison bias.
  - Mitigation: fix hardware, software versions, and solver settings; report p50/p95/max times.

## Immediate Next Steps

1. Finalize strict manifest variants without predictor-specific overrides for Protocol A.
2. Run Protocol A campaign end-to-end with resume enabled and write to a dedicated output root.
3. Define predictor-specific tuning search space and equal budget policy for Protocol B.
4. Run Protocol B tuning on train/val only, freeze parameters, then execute test/future-test.
5. Generate parity, QC, and bundle artifacts for each protocol separately.

## Existing Analysis Tooling (ready now)

The repository already contains scripts to support postprocessing and publication traceability.

- `scripts/validate_discomfort_parity.py`
  - Produces paired RC/PINN comparability and discomfort-definition risk report.
  - Default output: `results/mpc_phase1/discomfort_parity_report.csv`.

- `scripts/qc_eu_results.py`
  - Runs plausibility checks and exports KPI tables/plots for episode JSON outputs.
  - Expects raw episode layout under `results/eu_rc_vs_pinn/raw` by default.

- `scripts/prepare_publication_artifacts.py`
  - Builds checksum-indexed publication bundle metadata.
  - Includes benchmark/discomfort CSV artifacts when present.

- `scripts/reproduce_phase1.ps1`
  - Existing baseline pipeline that runs training, RC/PINN MPC, parity check, and bundle generation.
  - Useful as execution template for both Protocol A and Protocol B runs.

Operational note:
- `scripts/run_mpc_episode.py` currently applies `predictor_mpc_overrides` when present in a case manifest.
- This behavior is intended for Protocol B, and must be disabled by manifest hygiene in Protocol A.

## Open Technical Decisions

- Exact MPC solver package (CasADi/IPOPT vs alternatives).
- Comfort metric definition details (e.g., operative vs air temperature, occupied-hours weighting).
- Episode lengths and number of random seeds for statistical confidence.
