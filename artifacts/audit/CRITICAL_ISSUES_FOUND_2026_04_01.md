# Critical Issues Found - Candidate Evaluation Data Quality

## Issue 1: Extreme Weather / Pricing Scenario Confusion ⚠️

**Severity**: 🟠 **Medium** — Scenario labeling needs clarification

### Finding
`te_ext_02` is a distinct file and a distinct simulation trace, but it is **not a second weather-only scenario**. The manifest defines it as the same `peak_heat_day` extreme-weather class with an additional `electricity_price: highly_dynamic` scenario, and the raw record payload differs from `te_ext_01`.

Observed from direct comparison:
- `te_ext_01` and `te_ext_02` have different raw record payloads
- First record differs in `T_zone_degC`, `u_heating`, `power_W`, and `energy_Wh_step`
- The episode files are not byte-identical

### Root Cause
The issue is primarily **scenario interpretation**, not duplication:
1. `te_ext_02` is a pricing-shock variant on the same extreme-weather day
2. The name can be misread as a second weather-only test case
3. The current plots and summaries do not make that distinction explicit

### Impact
- ⚠️ Cannot claim `te_ext_02` is an independent weather-only extreme episode
- ⚠️ Results should be described as extreme-weather-plus-pricing sensitivity
- ⚠️ If the intent was to test two distinct weather profiles, the dataset needs regeneration

### Evidence
```
Dataset comparison:
  te_ext_01: weather_class=extreme, scenario=time_period=peak_heat_day
  te_ext_02: weather_class=extreme, scenario=time_period=peak_heat_day + electricity_price=highly_dynamic

Raw record comparison:
  record[0] differs in T_zone_degC, u_heating, power_W, and energy_Wh_step
  file bytes are not identical
```

---

## Issue 2: RBC Controller Duplication ⚠️

**Severity**: 🟡 **High** — Questions validity of control comparisons

### Finding
Rule-Based Controller (RBC) produces **identical cost values** across all three candidate parameter sets:

```
Candidate | te_ext_01 Cost | te_ext_02 Cost
-----------|----------------|---------------
cand_001   | 0.127993       | 0.128064
cand_005   | 0.127993       | 0.128064  ← SAME AS cand_001
cand_008   | 0.127993       | 0.128064  ← SAME AS cand_001
```

Also observed for all episodes (te_std_01, te_std_02) and all metrics (tdis_tot, control_smoothness).

### Why This Matters
RBC is a **fixed, rule-based controller** that does NOT depend on candidate parameters. Therefore, identical performance across candidates is **expected by design**.

The raw RBC files are not byte-identical across candidates, but their KPI values are the same because the controller is deterministic on the same episode inputs.

### Evidence vs. PINN
```
PINN (parameter-tuned MPC):
  cand_001: 0.13878199259285184
  cand_005: 0.13858584117339860  ← Different (as expected)
  cand_008: 0.13863159559229580  ← Different (as expected)

RBC (rule-based, fixed):
  cand_001: 0.12799340273899165
  cand_005: 0.12799340273899165  ← IDENTICAL
  cand_008: 0.12799340273899165  ← IDENTICAL
```

### Is This Really a Problem?
- **From control perspective**: No, RBC should not vary by candidate
- **From reporting perspective**: The plots should label RBC as a shared fixed baseline so readers do not expect candidate-specific variation

### Best Practice Would Be
- Re-run RBC on each candidate's evaluation set (even though results should be identical)
- Document explicitly: "RBC controller is invariant across candidates by design; re-evaluation on each candidate confirms reproducibility of fixed control strategy"

---

## Impact on Validity Audit

### Current Audit Status
- ✅ **Physical integrity**: ALL checks pass (energy, comfort, KPI parity)
- ❌ **Logical integrity**: 9 failures identified from baseline-episode coverage
- ⚠️ **Scenario clarity**: te_ext_02 should be described as a pricing-shock variant unless a second weather-only episode is generated

| Issue | Classification | Severity | Blocks Publication? |
|-------|-----------------|----------|-------------------|
| Extreme weather / pricing scenario confusion | Scenario labeling | 🟠 Medium | Conditional |
| RBC parameter reuse | Expected fixed baseline | 🟢 Low | No, but document clearly |
| Baseline episode gaps | Fairness gap | 🟠 Medium | Conditional |

---

## Remediation Required

### Issue 1: Scenario Clarification (MUST CLARIFY)
**Required action**: Decide whether `te_ext_02` is meant to be:
1. a pricing-shock variant of the same extreme-weather day, or
2. a second weather-only extreme episode.

If it is meant to be a weather-only comparison:
- regenerate `te_ext_02` with distinct weather inputs
- re-run all 3 candidates × 3 controllers on the new episode

If it is meant to be a pricing-shock variant:
- rename/document it that way in the manuscript and plots
- keep the current data

### Issue 2: RBC (RECOMMENDED FIX)
**Option A** (rigorous):
- Re-run RBC explicitly on each candidate evaluation scenario
- Document that results are identical by design
- Commits full reproducibility claim
- **Effort**: 1–2 hours
- **Benefit**: Eliminates reproducibility doubt

**Option B** (pragmatic):
- Document in manuscript: "RBC control is parameter-invariant; baseline RBC results reused across candidate evaluations for computational efficiency"
- Fully transparent about data reuse
- **Effort**: 5 mins (documentation only)
- **Risk**: Might raise reviewer questions

### Issue 3: Baseline Episodes (CONDITIONAL)
- Only relevant if extreme weather duplication is fixed
- Once te_ext_02 is fixed, extend baseline to match candidate episodes
- **Effort**: 1–2 hours

---

## Revised Audit Summary

**Current Audit Verdict**: 
> "Results are physically valid. The main issue is scenario labeling for `te_ext_02` and baseline episode coverage. RBC remains a valid fixed baseline."

**Post-Remediation Audit Verdict** (if scenario labeling and baseline coverage are clarified):
> "All results physically and logically valid. Full reproducibility demonstrated."

---

## Recommendations for User

### Immediate (This Week)
1. ✅ **Confirm the intended meaning of te_ext_02** (pricing variant vs. weather variant)
2. ✅ **Document RBC as a fixed baseline** (its identical values across candidates are expected)
3. **Decide remediation path**:
  - Path A (Weather-only): Regenerate te_ext_02 and re-run evaluations
  - Path B (Pricing variant): Keep data and rename/document the scenario clearly
  - Path C (Conservative): Restrict comparisons to te_ext_01 + te_std_01 only

### Before Publication Submission
- [ ] Scenario intent for te_ext_02 must be explicit in plots and manuscript
- [ ] RBC methodology explicitly stated as fixed baseline
- [ ] Baseline extended if claiming full episode coverage

### Documentation
Add new audit finding section to [FINAL_AUDIT_SUMMARY_2026_04_01.md](artifacts/audit/FINAL_AUDIT_SUMMARY_2026_04_01.md):
> **Critical Structural Issues Discovered Post-Audit**:
> - Extreme weather duplication (te_ext_02 = te_ext_01)
> - RBC parameter reuse pattern (identical results across candidates)
> - Status: Requires investigation and potential regeneration

---

## Files for Reference
- Diagnosis script: `scripts/check_extreme_weather_issue.py`
- Comparison data: `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/summary_full_validation.json`
- Raw results: `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/{cand_*/}{pinn,rbc,rc}/{te_ext_01,te_ext_02}.json`

---

## Next Steps
1. **User decision**: Which remediation path (A, B, or C)?
2. **Root cause investigation**: Why did duplication occur?
3. **Re-execution**: If Path A or B chosen, schedule BOPTEST runs
4. **Re-audit**: After fixes, run `audit_end_to_end_validity.py` again
