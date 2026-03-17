# Execution Plan: European BOPTEST RC vs PINN

## Goal

Compare three pure RC candidates against one PINN model per testcase, using only European BOPTEST cases.

## Inclusion Rule

- Include only cases with European locations.
- Exclude non-European cases even if they are in the latest BOPTEST release.
- Exclude hybrid RC-neural models from this benchmark.

## European Cases in Scope

1. BESTEST Hydronic (Brussels, Belgium)
2. BESTEST Hydronic Heat Pump (Brussels, Belgium)
3. Single Zone Commercial Hydronic (Copenhagen, Denmark)
4. Two Zone Apartment Hydronic (Milan, Italy)
5. Multizone Residential Hydronic (Copenhagen, Denmark)

## Model Set Per Testcase

- PINN: one model per testcase
- RC candidates: R3C2, R4C3, R5C3

## Evaluation Protocol

### Stage 1 (screening)

- Run all 3 RC candidates and PINN on 7-day episodes.
- Select best RC per testcase using weighted score on:
  - cost_tot
  - tdis_tot
  - idis_tot
  - solve time

### Stage 2 (final)

- Run best RC and PINN on 30-day episodes.
- Compare final rankings and robustness.

## Comparability Controls

- Same testcase, scenario family, start time, control interval, and horizon per paired run.
- Run discomfort parity validator on outputs to detect metric definition mismatch risk.

## Immediate Next Step

1. Query BOPTEST /testcases and confirm exact API ids for all five European cases.
2. Generate per-testcase manifests with matched 7-day and 30-day episodes.
3. Launch stage-1 training and benchmarking pipeline.
