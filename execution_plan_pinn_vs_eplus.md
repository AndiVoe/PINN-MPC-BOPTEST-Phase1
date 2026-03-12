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

1. Confirm primary case for Phase 1 (`singlezone_commercial_hydronic` recommended).
2. Freeze variable list for measurements, controls, and forecasts.
3. Implement dataset generator first (episodes + split manifest).
4. Implement baseline MPC run harness with detailed timing logs.
5. Add PINN training and swap predictor in same MPC harness.

## Open Technical Decisions

- Exact MPC solver package (CasADi/IPOPT vs alternatives).
- Comfort metric definition details (e.g., operative vs air temperature, occupied-hours weighting).
- Episode lengths and number of random seeds for statistical confidence.
