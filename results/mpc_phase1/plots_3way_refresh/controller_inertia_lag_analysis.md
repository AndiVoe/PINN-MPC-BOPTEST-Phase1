# Controller Inertia / Delay / Lag Analysis

Goal: determine whether poor behavior is mainly controller reaction timing or building inertia.

Method:
- Cross-correlation lag: lag between control changes (du) and temperature response (dz).
- Event lag: after large setpoint move (|du| >= 0.4 degC), steps to first consistent response (|dz| >= 0.03 degC, same sign).
- Settling proxy: steps after a large move until dz stays small (|dz| <= 0.01) for ~3h.

## Scope A: Refreshed Phase1 Set
- Episodes: 4 (te_ext_01, te_ext_02, te_std_01, te_std_02)

| Controller | mean |du| [degC/step] | xcorr lag [steps] | event lag p50 [steps] | event lag p90 [steps] | large move events | settle p50 [steps] |
|---|---:|---:|---:|---:|---:|---:|
| RC | 0.0045 | 11.25 | 1.00 | 1.00 | 5 | 76.00 |
| PINN | 0.0017 | 3.75 | nan | nan | 0 | nan |
| RBC | 0.0000 | 0.00 | nan | nan | 0 | nan |

## Scope B: EU Campaign Aggregate
- Episodes: 12 pooled common episodes across case folders

| Controller | mean |du| [degC/step] | xcorr lag [steps] | event lag p50 [steps] | event lag p90 [steps] | large move events | settle p50 [steps] |
|---|---:|---:|---:|---:|---:|---:|
| RC | 0.0012 | 8.75 | 1.00 | 2.20 | 5 | 58.00 |
| PINN | 0.1569 | 3.33 | 1.00 | 16.00 | 364 | 115.00 |
| RBC | 0.0112 | 4.58 | 6.00 | 20.20 | 67 | 77.00 |

## Interpretation
- Similar response lag across controllers implies the plant inertia is shared and likely dominant in raw response timing.
- Large differences in |du| with similar lag imply controller aggressiveness differences (possible overreaction).

- RC EU aggregate: mean |du|=0.0012 degC/step, mean xcorr lag=8.75 steps.
- PINN EU aggregate: mean |du|=0.1569 degC/step, mean xcorr lag=3.33 steps.
- RBC EU aggregate: mean |du|=0.0112 degC/step, mean xcorr lag=4.58 steps.

## Conclusion
- Building inertia is non-negligible: response and settling span multiple control steps.
- Controller aggressiveness is also a key factor: PINN typically moves faster/larger in several cases than RC/RBC.
- Therefore, both matter: inertia sets the physical delay, and tuning should reduce overreaction to that delay.