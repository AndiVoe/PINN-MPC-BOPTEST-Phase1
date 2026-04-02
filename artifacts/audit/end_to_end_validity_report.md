# End-to-End Validity Audit Report

## Summary
- Total checks: 697
- Failed checks: 0
- Failed errors: 0
- Failed warnings: 0

## Enforced Relations
- Step count relation: n_steps == len(step_records)
- Time relation: time_s must be strictly increasing
- Energy relation: total_energy_Wh ~= sum(max(power_w,0))*dt_h
- Peak relation: peak_power_W ~= max(power_w)
- Comfort relation: comfort_Kh ~= sum(violation_K)*dt_h
- Violation relation: comfort_violation_steps ~= count(violation>0)
- KPI relation: challenge_kpis[*].value == boptest_kpis[*]
- Candidate relation: each candidate/controller folder must contain result JSON
- Baseline relation: baseline controller folders must contain result JSON

## Failures
- No failed checks.

## Check-Wise Pass Rates
| Check | Total | Pass | Fail |
|---|---:|---:|---:|
| baseline_controller_nonempty | 3 | 3 | 0 |
| candidate_baseline_episode_coverage | 9 | 9 | 0 |
| candidate_controller_nonempty | 9 | 9 | 0 |
| challenge_equals_boptest_cost_tot | 59 | 59 | 0 |
| challenge_equals_boptest_idis_tot | 59 | 59 | 0 |
| challenge_equals_boptest_pdih_tot | 27 | 27 | 0 |
| challenge_equals_boptest_pele_tot | 59 | 59 | 0 |
| challenge_equals_boptest_tdis_tot | 59 | 59 | 0 |
| comfort_integral | 59 | 59 | 0 |
| comfort_violation_steps | 59 | 59 | 0 |
| energy_integral_electric | 59 | 59 | 0 |
| energy_integral_heating | 59 | 59 | 0 |
| energy_integral_total | 59 | 59 | 0 |
| peak_power | 59 | 59 | 0 |
| solve_time_mean | 59 | 59 | 0 |