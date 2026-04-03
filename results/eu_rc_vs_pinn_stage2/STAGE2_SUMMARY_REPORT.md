# Stage 2: RC Variant Selection & PINN Comparison Report

**Generated**: os.stat_result(st_mode=33206, st_ino=8725724278054312, st_dev=6952144387345894898, st_nlink=1, st_uid=0, st_gid=0, st_size=11565, st_atime=1775194710, st_mtime=1775194706, st_ctime=1775194705)
**Episode**: te_std_01
**Date**: April 3, 2026

## Executive Summary

This report presents the final RC variant selection based on Stage 2 benchmarking (30-day episodes)
and compares the best RC variant against the PINN model for each of the 4 European BOPTEST testcases.

### Key Findings

- **Average Cost Difference (PINN vs RC)**: -0.1036 €
  - Negative = PINN is more cost-effective on average
- **Average Comfort Difference**: -40.32 K·h
  - Negative = PINN achieves better comfort
- **Average Energy Difference**: -2089299 Wh
  - Negative = PINN consumes less energy

## Case-by-Case Analysis

### Case 1: bestest_hydronic

**Best RC Variant Selected**: `rc`
**Selection Score**: 64.25

#### Best RC Variant Performance

- **Energy**: 215.51 kWh
- **Comfort**: 29.88 K·h
- **Cost**: €0.2328
- **MPC Solve Time**: 2.767 ms

#### PINN Performance

- **Energy**: 185.28 kWh
- **Comfort**: 18.91 K·h
- **Cost**: €0.2031
- **MPC Solve Time**: 294.596 ms

#### Deltas (PINN minus Best RC)

- **Energy**: -30221 Wh (-14.02%)
  - ✓ PINN saves energy
- **Cost**: €-0.0297
  - ✓ PINN is cheaper
- **Comfort**: -10.97 K·h
  - ✓ PINN better comfort
- **Solver Time**: +291.829 ms
  - ✗ RC faster (+10546.8% relative)

### Case 2: bestest_hydronic_heat_pump

**Best RC Variant Selected**: `rc_base`
**Selection Score**: 99.56

#### Best RC Variant Performance

- **Energy**: 1746.93 kWh
- **Comfort**: 38.91 K·h
- **Cost**: €0.4273
- **MPC Solve Time**: 2.773 ms

#### PINN Performance

- **Energy**: 906.68 kWh
- **Comfort**: 80.36 K·h
- **Cost**: €0.1885
- **MPC Solve Time**: 1217.492 ms

#### Deltas (PINN minus Best RC)

- **Energy**: -840251 Wh (-48.10%)
  - ✓ PINN saves energy
- **Cost**: €-0.2388
  - ✓ PINN is cheaper
- **Comfort**: +41.45 K·h
  - ✗ RC better comfort
- **Solver Time**: +1214.719 ms
  - ✗ RC faster (+43805.2% relative)

### Case 3: singlezone_commercial_hydronic

**Best RC Variant Selected**: `rc_mass_plus`
**Selection Score**: 165.06

#### Best RC Variant Performance

- **Energy**: 14808.18 kWh
- **Comfort**: 7.78 K·h
- **Cost**: €0.1413
- **MPC Solve Time**: 2.974 ms

#### PINN Performance

- **Energy**: 7475.02 kWh
- **Comfort**: 0.00 K·h
- **Cost**: €0.0700
- **MPC Solve Time**: 60.071 ms

#### Deltas (PINN minus Best RC)

- **Energy**: -7333161 Wh (-49.52%)
  - ✓ PINN saves energy
- **Cost**: €-0.0713
  - ✓ PINN is cheaper
- **Comfort**: -7.78 K·h
  - ✓ PINN better comfort
- **Solver Time**: +57.097 ms
  - ✗ RC faster (+1919.9% relative)

### Case 4: twozone_apartment_hydronic

**Best RC Variant Selected**: `rc_base`
**Selection Score**: 433.87

#### Best RC Variant Performance

- **Energy**: 258.37 kWh
- **Comfort**: 214.87 K·h
- **Cost**: €0.1548
- **MPC Solve Time**: 2.893 ms

#### PINN Performance

- **Energy**: 104.80 kWh
- **Comfort**: 30.88 K·h
- **Cost**: €0.0802
- **MPC Solve Time**: 394.729 ms

#### Deltas (PINN minus Best RC)

- **Energy**: -153563 Wh (-59.44%)
  - ✓ PINN saves energy
- **Cost**: €-0.0746
  - ✓ PINN is cheaper
- **Comfort**: -183.99 K·h
  - ✓ PINN better comfort
- **Solver Time**: +391.836 ms
  - ✗ RC faster (+13544.3% relative)

## Methodology Notes

- **Stage 1**: Screened 3 RC candidates (R3C2, R4C3, R5C3) on 7-day episodes
- **Stage 2**: Ran best RC variant + PINN on 30-day episodes for robustness validation
- **Scoring**: RC selection used weighted score: 10×cost + 2×comfort + 0.01×energy_kWh
- **Episode**: All 30-day runs use scenario `te_std_01` (standard conditions)

## Data Files

- Summary JSON: `results/eu_rc_vs_pinn_stage2/best_rc_vs_pinn_summary.json`
- Stage 1 (7-day PINN results): `results/eu_rc_vs_pinn/raw/[case]/pinn/`
- Stage 2 (30-day RC variants): `results/eu_rc_vs_pinn_stage2/raw/[case]/[variant]/`
- Stage 2 (30-day PINN results): `results/eu_rc_vs_pinn/raw/[case]/pinn/`
