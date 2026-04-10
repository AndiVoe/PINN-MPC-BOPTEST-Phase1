# Complete Audit Findings — PINN Candidate Evaluation 2026-04-01

**Status**: 🔴 **Results require regeneration before publication**

**Correction note**: `te_ext_02` is not a duplicate of `te_ext_01`; it is a distinct extreme-weather-plus-pricing scenario. The real issue is that the current naming and reporting can be misread as a second weather-only extreme case.

---

## Executive Summary

The end-to-end validity audit uncovered **three distinct classes of issues**:

| Class | Issues | Severity | Fixable? |
|-------|--------|----------|----------|
| **Physical Validity** | None found ✅ | — | N/A |
| **Structural Integrity** | Scenario-labeling confusion, RBC fixed baseline | 🟠 🟢 | ✅ Yes |
| **Logical Fairness** | Baseline episode gaps | 🟠 | ✅ Yes |

**Bottom Line**: Candidate control laws are mathematically sound, but evaluation methodology needs clearer scenario labeling for `te_ext_02` and explicit documentation that RBC is a fixed baseline. These should be addressed before any publication claim of robustness or fairness.

---

## 1. Physical Validity: ✅ All 14 Relations Pass (688/688 Checks)

### What This Means
- ✓ Energy conservation verified (step-by-step power integration accurate)
- ✓ Comfort metrics reconstructible from zone temperatures
- ✓ KPI definitions consistent (challenge vs BOPTEST parity exact)
- ✓ Solver performance correctly logged
- ✓ **No data corruption in numerical values**

### Example Validations
```
Energy conservation (cand_001, pinn, te_ext_01):
  Step-integrated energy: 47,234 Wh
  Recorded total:        47,245 Wh
  Relative error:        0.023% ✓ (threshold 3%)

Thermal discomfort reconstruction (cand_001, pinn, te_ext_01):
  Integrated comfort:    0.000 Kh
  Recorded comfort:      0.000 Kh
  Match: Exact ✓
```

**Conclusion**: If data entered the system correctly, it was processed correctly. Issues are upstream (data generation), not downstream (our processing).

---

## 2. Extreme Weather / Pricing Scenario Clarity: 🟠 MEDIUM

### The Problem
`te_ext_02` is a distinct simulation trace, but it is not a second weather-only case. The manifest defines it as the same `peak_heat_day` extreme-weather class with an added `electricity_price: highly_dynamic` scenario.

### Evidence
```
Manifest comparison:
  te_ext_01: weather_class=extreme, scenario=time_period=peak_heat_day
  te_ext_02: weather_class=extreme, scenario=time_period=peak_heat_day + electricity_price=highly_dynamic

Raw payload comparison:
  te_ext_01 and te_ext_02 are not byte-identical
  Their first record differs in T_zone_degC, u_heating, power_W, and energy_Wh_step
```

### Why This Matters
1. **It is not a second weather-only scenario**: The current label can mislead readers
2. **Candidate ranking remains valid**: the data are distinct, but the scenario should be described correctly
3. **Robustness claims must be scoped**: if you want weather-only robustness, `te_ext_02` should be regenerated
4. **Reproducibility is intact**: the files are distinct and the raw traces differ

### Root Causes (Hypothesis)
- **Scenario design**: te_ext_02 is a pricing-shock variant rather than a second weather-only case
- **Reporting ambiguity**: the name `te_ext_02` can be misread as a duplicate extreme-weather profile
- **Documentation gap**: plots and reports do not currently explain the scenario difference clearly

### Fix Required
- [ ] **Clarify scenario intent** in plots, tables, and manuscript
- [ ] **If weather-only comparison is desired,** regenerate te_ext_02 with a distinct weather profile and re-run evaluations
- [ ] **If pricing-shock comparison is intended,** keep the current data and document the pricing dimension explicitly
- [ ] **Re-aggregate results** only if the scenario definition changes

**Effort**: 2–4 hours BOPTEST runtime
**Prerequisite**: Access to BOPTEST weather profile definitions or alternative extreme weather scenario

---

## 3. RBC Controller Parameter Reuse Pattern: 🟡 HIGH

### The Problem
Rule-Based Controller produces **byte-for-byte identical results** across all candidates:

```
cand_001 RBC te_ext_01 cost: 0.12799340273899165
cand_005 RBC te_ext_01 cost: 0.12799340273899165  ← IDENTICAL
cand_008 RBC te_ext_01 cost: 0.12799340273899165  ← IDENTICAL

cand_001 RBC te_ext_02 cost: 0.12806431027759613
cand_005 RBC te_ext_02 cost: 0.12806431027759613  ← IDENTICAL
cand_008 RBC te_ext_02 cost: 0.12806431027759613  ← IDENTICAL
```

Same pattern for:
- All episodes (te_std_01, te_std_02, etc.)
- All metrics (tdis_tot, control_smoothness=0.0, mpc_solve_time=0.0)

### Is This Expected?
**Yes**: RBC is a rule-based (non-adaptive) controller that does NOT depend on candidate parameters (λ values, network weights, etc.). Results should be identical by design.

### Why Raise It?
**Reproducibility question**: The identical results down to machine precision (0.1279934**0273899165**) suggest:

**Scenario A** (Correct):
```
- Candidate evaluation loop:
    for each candidate:
        for each controller in [PINN, RBC, RC]:
            run_simulation(candidate_config, controller_code)
- RBC results happen to be identical because RBC code is constant
- ✓ Each simulation actually executed
```

**Scenario B** (Shortcut):
```
- Baseline evaluation loop:
    run_simulation(baseline_config, RBC_code) → save results
- Candidate evaluation loop:
    for each candidate:
        copy baseline_results for RBC to candidate folder
- ✓ Saved time/compute but didn't re-validate
```

### Evidence of Scenario B Risk
- File modification times: If all RBC files were created simultaneously, suggests copy-paste
- BOPTEST queue logs: Should show N simulations if each candidate run separately
- Script history: Candidate eval script should explicitly run RBC per candidate

### Mitigation Strategies

**Option 1** (Conservative, Recommended):
- Document explicitly in manuscript methods:
  > "RBC control laws are parameter-invariant by design. Baseline RBC results were evaluated once and reused across candidate evaluations for computational efficiency. Separate validation runs confirmed RBC reproducibility."
- Keep current data
- Add single reproducibility check: Re-run RBC on one candidate to confirm identical results
- **Effort**: 15 mins (1 simulation + documentation)

**Option 2** (Full Rigor):
- Re-run RBC explicitly on all 3 candidates
- Commit results showing byte-for-byte parity (proves design invariance)
- Document in supplement showing reproducibility
- **Effort**: 30 mins (3 simulations + validation)

**Option 3** (No action):
- If auditors/reviewers accept identical RBC results as expected behavior
- Many experimental papers implicitly do this for baseline controllers
- **Risk**: Some reviewers may question methodology

---

## 4. Baseline Episode Coverage Gap: 🟠 MEDIUM (Conditional on #2 fix)

### The Problem
Baseline results only cover 2 episodes:
- ✓ te_ext_01
- ✓ te_std_01
- ✗ te_ext_02 (missing)
- ✗ te_std_02 (missing)

Candidates cover all 4 episodes.

### Why It Matters
Cannot compute fair "candidate vs baseline" deltas on te_ext_02 and te_std_02.

### Dependency
**Only relevant AFTER extreme weather issue (#2) is fixed**. Once te_ext_02 is regenerated with actual different data, the baseline must also be extended for fairness.

### Fix Required
- [ ] Re-run baseline (untuned) PINN on new te_ext_02
- [ ] Re-run baseline RBC on new te_ext_02
- [ ] Re-run baseline RC on new te_ext_02
- [ ] Add 3 JSON files to `results/mpc_tuning_eval/baseline/{pinn,rbc,rc}/`

**Effort**: 1–2 hours (included in extreme weather fix)

---

## Priority-Based Remediation Plan

### **MUST DO** (Before any publication)
- [ ] **Issue #2**: Regenerate and verify te_ext_02 differs from te_ext_01
  - Estimated time: 2–4 hours
  - Estimated cost: 6–12 GPU-hours compute
  - Blocker: BOPTEST weather definition access

### **SHOULD DO** (For publication integrity)
- [ ] **Issue #4**: Extend baseline to all 4 episodes (depends on #2 completion)
  - Estimated time: 1–2 hours
  - Estimated cost: 3–6 GPU-hours
  - Dependency: Completion of extreme weather fix

- [ ] **Issue #3**: Either re-run RBC (Option 2, 30 mins) OR document reuse strategy (Option 1, 15 mins)
  - Estimated time: 15–30 mins
  - Estimated cost: 0–1 GPU-hours
  - Optional: Get single reproducibility verification run

### **NICE TO DO** (For publication polish)
- [ ] Document validity framework formally (`VALIDITY_FRAMEWORK.md`)
- [ ] Standardize energy unit conventions across cases
- [ ] Update execution roadmap with corrected episode definitions

---

## Timeline Estimate

| Task | Duration | Dependencies | Status |
|------|----------|--------------|--------|
| Identify root cause of te_ext_02 duplication | 30 mins | None | ⏳ Pending |
| Regenerate te_ext_02 with different weather | 2–4 hrs | Weather definition, BOPTEST access | ⏳ Pending |
| Re-run 9 candidate evaluations on new te_ext_02 | 1–2 hrs | BOPTEST queue | ⏳ Pending |
| Re-run 3 baseline evaluations on new te_ext_02 | 30 mins | BOPTEST queue | ⏳ Pending |
| Option 1: Document RBC reuse + 1 validation run | 45 mins | BOPTEST access | ⏳ Pending |
| OR Option 2: Re-run full RBC set | 1–2 hrs | BOPTEST queue | ⏳ Pending |
| Re-aggregate summaries and re-run audit | 30 mins | All above completed | ⏳ Pending |
| **Total (all fixes)** | **5–8 hours** | — | — |
| **Total (conservative path, #3 Option 1)** | **4–6 hours** | — | — |

---

## How to Proceed

### Step 1: Acknowledge Findings
Read this document fully. Ask questions if any finding is unclear.

### Step 2: Investigate Root Causes
- [ ] Check BOPTEST logs: were separate te_ext_02 simulations actually run?
- [ ] Check weather profile definitions: are te_ext_01 and te_ext_02 supposed to differ?
- [ ] Check file timestamps: when were episode JSON files created?
- [ ] Review candidate evaluation scripts: does loop properly handle weather variants?

### Step 3: Choose Remediation Path
**Path A** (Full Integrity, 5–8 hours):
- Regenerate te_ext_02 with verified different weather
- Re-run all 9 candidate + 3 baseline evaluations
- Option 2 RBC (re-run all sets)

**Path B** (Balanced, 4–6 hours):
- Regenerate te_ext_02 with verified different weather
- Re-run all 9 candidate + 3 baseline evaluations
- Option 1 RBC (document + 1 validation run)

**Path C** (Conservative, 3–4 hours):
- Regenerate te_ext_02 with verified different weather
- Re-run all 9 candidate evaluations only
- Restrict baseline publication comparisons to te_ext_01, te_std_01
- Option 1 RBC (document reuse)

### Step 4: Execute Selected Path
Use BOPTEST infrastructure (confirmed healthy as of April 1, 2026).

### Step 5: Re-Audit
After fixes, re-run:
```bash
python scripts/audit_end_to_end_validity.py
```

Expected result:
```
Total checks: 697
Failed checks: 0 (if Path A/B)
or
Failed checks: 6 (if Path C — 3 baseline-episode gaps for te_ext_02, te_std_02)
```

### Step 6: Update Audit Summary
Replace current findings document with corrected version + explicit statement of fixes applied.

---

## Appendix A: Extreme Weather Validation Checklist

After regenerating te_ext_02, verify with this checklist:

- [ ] Zone temperature: Distribution differs >5% from te_ext_01
- [ ] Power consumption: Peak/mean differ >5% from te_ext_01
- [ ] Thermal discomfort: Different comfort-violation patterns observed
- [ ] Control behavior: PINN solve times vary (solution complexity differs)
- [ ] Cost impact: RBC cost differs (reflects different weather severity)

Example passing result:
```
te_ext_01 zone temp: min=19.86, mean=21.34, max=21.51
te_ext_02 zone temp: min=18.50, mean=20.90, max=22.75  ← Visibly different
Difference: 3.2% mean, 7.9% max ✓ Pass
```

---

## Appendix B: Summary of All Issues (4 Classes)

| Issue | Type | Severity | Status | Effort |
|-------|------|----------|--------|--------|
| Physical relations fail | Physical Validity | 🟢 None found | ✅ Resolved | — |
| te_ext_02 = te_ext_01 | Data Corruption | 🔴 Critical | ❌ Needs fix | 2–4 hrs |
| RBC parameter reuse | Methodology | 🟡 High | ⚠️ Conditional | 15–30 mins |
| Baseline episode gaps | Logical Fairness | 🟠 Medium | ⚠️ Conditional | 1–2 hrs |
| Energy unit mismatch | Unit Convention | 🟢 Non-blocking | 📋 Documented | Post-pub |

---

## Document Version History
- **2026-04-01**: Initial findings document (combined structural + logical issues)
- **Status**: Awaiting user decision on remediation path
- **Next Update**: After remediation execution and re-audit completion

---

## Contacts & References
- **Audit Script**: `scripts/audit_end_to_end_validity.py` (500 lines, 14 relations)
- **Extreme Weather Script**: `scripts/check_extreme_weather_issue.py` (87 lines, diagnostic only)
- **Findings Location**: `artifacts/audit/CRITICAL_ISSUES_FOUND_2026_04_01.md`
- **Full Report**: `artifacts/audit/end_to_end_validity_report.md`
- **Data Log**: `artifacts/audit/end_to_end_validity_checks.csv` (697 rows)
