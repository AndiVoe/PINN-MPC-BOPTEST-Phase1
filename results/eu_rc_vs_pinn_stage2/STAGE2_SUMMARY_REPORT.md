# Stage 2: RC Parameter-Variant Selection & PINN Comparison Report

**Generated**: 2026-04-07 12:08:15
**Episode**: te_std_01
**Date**: April 07, 2026

## Executive Summary

This report presents the final RC parameter-variant selection based on Stage 2 benchmarking (30-day episodes)
and compares the best RC variant against the PINN model for each of the 4 European BOPTEST testcases.

### Key Findings

- **Average Cost Difference (PINN vs RC)**: -0.1671 €
  - Negative = PINN is more cost-effective on average
- **Average Comfort Difference**: -288.96 K·h
  - Negative = PINN achieves better comfort
- **Average Energy Difference**: -4975393 Wh
  - Negative = PINN consumes less energy

## Case-by-Case Analysis

### Case 1: bestest_hydronic

**Best RC Variant Selected**: `rc_envelope_plus`
**Selection Score**: 1014.62

#### Best RC Variant Performance

- **Energy**: 504.65 kWh
- **Comfort**: 502.07 K·h
- **Cost**: €0.5432
- **MPC Solve Time**: 3.075 ms

#### PINN Performance

- **Energy**: 362.92 kWh
- **Comfort**: 366.91 K·h
- **Cost**: €0.4027
- **MPC Solve Time**: 551.821 ms

#### Deltas (PINN minus Best RC)

- **Energy**: -141737 Wh (-28.09%)
  - ✓ PINN saves energy
- **Cost**: €-0.1405
  - ✓ PINN is cheaper
- **Comfort**: -135.16 K·h
  - ✓ PINN better comfort
- **Solver Time**: +548.746 ms
  - ✗ RC faster (+17845.4% relative)

### Case 2: bestest_hydronic_heat_pump

**Best RC Variant Selected**: `rc_base`
**Selection Score**: 625.87

#### Best RC Variant Performance

- **Energy**: 3981.93 kWh
- **Comfort**: 287.75 K·h
- **Cost**: €1.0555
- **MPC Solve Time**: 2.677 ms

#### PINN Performance

- **Energy**: 3058.54 kWh
- **Comfort**: 123.61 K·h
- **Cost**: €0.7396
- **MPC Solve Time**: 456.664 ms

#### Deltas (PINN minus Best RC)

- **Energy**: -923388 Wh (-23.19%)
  - ✓ PINN saves energy
- **Cost**: €-0.3158
  - ✓ PINN is cheaper
- **Comfort**: -164.14 K·h
  - ✓ PINN better comfort
- **Solver Time**: +453.987 ms
  - ✗ RC faster (+16958.8% relative)

### Case 3: singlezone_commercial_hydronic

**Best RC Variant Selected**: `rc_base`
**Selection Score**: 620.02

#### Best RC Variant Performance

- **Energy**: 30877.50 kWh
- **Comfort**: 154.18 K·h
- **Cost**: €0.2884
- **MPC Solve Time**: 2.585 ms

#### PINN Performance

- **Energy**: 12421.59 kWh
- **Comfort**: 26.74 K·h
- **Cost**: €0.1089
- **MPC Solve Time**: 194.154 ms

#### Deltas (PINN minus Best RC)

- **Energy**: -18455913 Wh (-59.77%)
  - ✓ PINN saves energy
- **Cost**: €-0.1795
  - ✓ PINN is cheaper
- **Comfort**: -127.44 K·h
  - ✓ PINN better comfort
- **Solver Time**: +191.569 ms
  - ✗ RC faster (+7410.8% relative)

### Case 4: twozone_apartment_hydronic

**Best RC Variant Selected**: `rc_envelope_plus`
**Selection Score**: 2031.81

#### Best RC Variant Performance

- **Energy**: 633.90 kWh
- **Comfort**: 1011.84 K·h
- **Cost**: €0.1782
- **MPC Solve Time**: 2.607 ms

#### PINN Performance

- **Energy**: 253.37 kWh
- **Comfort**: 282.75 K·h
- **Cost**: €0.1456
- **MPC Solve Time**: 440.996 ms

#### Deltas (PINN minus Best RC)

- **Energy**: -380533 Wh (-60.03%)
  - ✓ PINN saves energy
- **Cost**: €-0.0326
  - ✓ PINN is cheaper
- **Comfort**: -729.09 K·h
  - ✓ PINN better comfort
- **Solver Time**: +438.389 ms
  - ✗ RC faster (+16815.8% relative)

## Methodology Notes

- **Stage 1**: Screened 3 RC topologies (R3C2, R4C3, R5C3) on 7-day episodes
- **Stage 2**: Ran RC parameter variants (`rc_base`, `rc_envelope_plus`, `rc_mass_plus`) plus PINN on 30-day episodes for robustness validation
- **Topology note**: Stage 2 RC parameter variants are scaling variants on a fixed RC topology unless `--rc-topology` is explicitly provided
- **Scoring**: RC selection used weighted score: 10×cost + 2×comfort + 0.01×energy_kWh
- **Episode**: All 30-day runs use scenario `te_std_01` (standard conditions)

## Data Files

- Summary JSON: `results/eu_rc_vs_pinn_stage2/best_rc_vs_pinn_summary.json`
- Stage 1 (7-day PINN results): `results/eu_rc_vs_pinn/raw/[case]/pinn/`
- Stage 2 (30-day RC variants): `results/eu_rc_vs_pinn_stage2/raw/[case]/[variant]/`
- Stage 2 (30-day PINN results): `results/eu_rc_vs_pinn_stage2/raw/[case]/pinn/`
