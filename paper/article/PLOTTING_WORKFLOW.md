# Complete Plotting Workflow for Publication

## Overview

You now have **two complementary plotting systems**:

### System A: Quality Control & Validation
**Script:** `qc_eu_results.py`  
**Purpose:** Verify data integrity, show detailed episode timeseries  
**Output:** Per-episode comparisons + basic overview plots

### System B: Publication-Ready Figures
**Script:** `generate_publication_plots.py`  
**Purpose:** High-quality aggregate statistics for journal articles  
**Output:** 6 camera-ready plots at 300 DPI

---

## Step-by-Step Workflow

### **Phase 1: After Data Collection Completes** 

Your main campaign is `finished_with_failures` (4/5 complete) and heating campaign is `running`.

```powershell
# Step 1: Run quality checks on completed main campaign
cd "C:\Users\AVoelser\OneDrive - Scientific Network South Tyrol\3_PhD\Simulation\PINN"

.venv\Scripts\python.exe scripts/qc_eu_results.py `
  --raw-root results/eu_rc_vs_pinn/raw `
  --out-dir results/eu_rc_vs_pinn/qc
```

**Outputs:**
```
results/eu_rc_vs_pinn/qc/
├── kpi_table.csv                      ← Data for your own analysis
├── plausibility_summary.csv           ← Quality flags
├── plausibility_report.json           ← Detailed QC results
├── timeseries/                        ← Per-episode comparisons
│   ├── bestest_hydronic__te_std_01.png
│   ├── bestest_hydronic__te_std_02.png
│   └── ...
└── overview/
    ├── comfort_vs_energy.png          ← Basic scatter
    └── solve_time_distribution.png    ← Solver performance
```

### **Phase 2: Generate Publication Plots**

```powershell
# Step 2: Generate high-quality plots for article
.venv\Scripts\python.exe scripts/generate_publication_plots.py `
  --raw-root results/eu_rc_vs_pinn/raw `
  --out-dir results/publication_plots
```

**Outputs:**
```
results/publication_plots/
├── 01_energy_per_case.png             ← Figure 3a
├── 02_comfort_per_case.png            ← Figure 3b
├── 03_peak_power_per_case.png         ← Figure 3c
├── 04_relative_energy_improvement.png ← Figure 4 (KEY!)
├── 05_aggregated_kpi_boxplots.png     ← Figure 5 or Supplement
└── 06_pareto_frontier_enhanced.png    ← Figure 6
```

---

## How They Work Together

### **Scenario: Reviewer Questions Data Quality**

> "How do you know your results are reliable?"

**Answer:**
1. Show `plausibility_report.json` from qc_eu_results.py
2. Reference `timeseries/` plots showing smooth temperature evolution
3. Cite `kpi_table.csv` showing physically plausible values

### **Scenario: Reviewer Wants Detailed Case Analysis**

> "Show me the temperature control on cold vs mild days"

**Answer:**
1. Point to specific timeseries plots in `results/eu_rc_vs_pinn/qc/timeseries/`
2. Show control strategies (heating setpoint evolution)
3. Compare RC vs PINN decision-making

### **Scenario: Editor Wants Main Results**

> "Give me 3 figures for the main text"

**Answer:**
- Figure 3: `01_energy_per_case.png` + `02_comfort_per_case.png` + `03_peak_power_per_case.png` (or 3-panel)
- Figure 4: `04_relative_energy_improvement.png` (headline metric)
- Figure 5: `06_pareto_frontier_enhanced.png` (feasible region)

---

## When to Use Each System

| Situation | Use |
|-----------|-----|
| Verify data isn't corrupted | `qc_eu_results.py` → `plausibility_report.json` |
| Show episode-level detail | `qc_eu_results.py` → `timeseries/` plots |
| Present main results | `generate_publication_plots.py` → all 6 plots |
| Demonstrate robustness | `generate_publication_plots.py` → `05_aggregated_kpi_boxplots.png` |
| Show trade-offs | `generate_publication_plots.py` → `06_pareto_frontier_enhanced.png` |
| Create supplementary table | `qc_eu_results.py` → `kpi_table.csv` |
| Custom analysis | `kpi_table.csv` → import to Excel/R/Python |

---

## Recommended Figure Strategy for Different Journal Types

### **For Energy-Focused Journal** (e.g., Energy and Buildings)
```
Main Text:
- Figure 1: Energy per case + Relative improvement
- Figure 2: Peak power + comfort comparison
- Table 1: Aggregated statistics from kpi_table.csv

Supplementary:
- Pareto frontier
- Example timeseries (cold/mild/avg episodes)
- Detailed KPI table
```

### **For Building Science Journal** (e.g., Building and Environment)
```
Main Text:
- Figure 1: Pareto frontier (central result)
- Figure 2: Per-case KPIs (detailed analysis)
- Figure 3: Example indoor/outdoor temps + control (timeseries)

Supplementary:
- Aggregated boxplots
- QC report
- Full timeseries appendix
```

### **For Control/Optimization Journal** (e.g., Control Engineering Practice)
```
Main Text:
- Figure 1: Solver time comparison + feasibility
- Figure 2: Energy-comfort trade-off
- Figure 3: Case-dependent performance (relative improvement)

Supplementary:
- Detailed controls strategy (from timeseries)
- Computational requirements analysis
- Robustness metrics
```

---

## Data Pipeline for Custom Analysis

If you need to create additional plots or analysis:

```powershell
# Step 1: Get the KPI data as CSV
$kpis = Import-Csv "results/eu_rc_vs_pinn/qc/kpi_table.csv"

# Step 2: Filter for specific analysis
$pinn_energy = $kpis | Where-Object {$_.predictor -eq "pinn"} | Select-Object total_energy_Wh_per_m2

# Step 3: Create your own visualizations in Excel, R, or Python
```

**Key CSV Columns Available:**
- `case`: Building type
- `predictor`: RC or PINN
- `episode_id`: Test episode
- `comfort_Kh`: Comfort violations
- `total_energy_Wh`: Total energy
- `total_energy_Wh_per_m2`: Normalized energy
- `peak_power_W`: Max power
- `peak_power_W_per_m2`: Normalized peak
- `mpc_solve_time_mean_ms`: Computational cost
- `mpc_solve_time_p95_ms`: 95th percentile latency
- `tdis_tot`: Thermal discomfort (if available)
- `cost_tot`: Energy cost (if available)

---

## Timeline for Your Article

### **Now (Main Campaign Complete, 4/5)**
✅ Run `qc_eu_results.py` → Validate data quality  
✅ Run `generate_publication_plots.py` → Get 6 figures ready

### **When Heating Campaign Finishes (Est. 3-5 hours)**
⏳ Run both scripts on `results/eu_rc_vs_pinn_heating/raw`  
⏳ Compare seasonal performance (heating vs standard)  
⏳ Create seasonal comparison plots if needed

### **Writing Paper**
1. Use 6 publication plots from `results/publication_plots/`
2. Reference QC data if reviewers ask about validation
3. Include example timeseries from `qc_eu_results.py` in appendix
4. Use `kpi_table.csv` for supplementary material tables

### **Reviewer Response**
1. Detailed timeseries ready in `results/eu_rc_vs_pinn/qc/timeseries/`
2. Full QC/validation report available
3. Statistical details from boxplots (Figure 5)
4. Case-specific analysis from per-case plots (Figure 3a-c)

---

## File Organization for Submission

Organize your submission materials:

```
article_submission/
├── main_figures/
│   ├── Figure_3_KPIs.png          (01, 02, 03 combined)
│   ├── Figure_4_RelativeImprovement.png  (04)
│   ├── Figure_5_Statistics.png    (05)
│   └── Figure_6_Pareto.png        (06)
│
├── supplementary/
│   ├── detailed_timeseries/       (from qc_eu_results.py)
│   ├── validation_report.json     (plausibility)
│   ├── kpi_table.csv              (raw data)
│   └── example_episodes.png       (select best timeseries)
│
└── raw_data/
    └── [actual JSON episode files if needed]
```

---

## Troubleshooting

### **Plot shows empty/no data**
- Check: `results/eu_rc_vs_pinn/raw/` has RC and PINN subdirectories with JSON files
- Run: `qc_eu_results.py` first to validate data

### **Publication plots look different than expected**
- This is normal - they're aggregated across all cases/episodes
- Values depend on actual results (electricity prices, building properties, etc.)

### **Missing a specific metric?**
- Check `kpi_table.csv` - has 18 KPI columns
- Create custom plot from that CSV if needed
- Or modify `generate_publication_plots.py` to add metrics

### **Want to compare against other approaches?**
- Use `kpi_table.csv` as baseline
- Ensure other approaches have same episode definitions
- Add comparison bars to plots

---

## Quick Command Reference

```powershell
# Full workflow (both scripts)
cd "C:\Users\AVoelser\OneDrive - Scientific Network South Tyrol\3_PhD\Simulation\PINN"

# Quality check
.venv\Scripts\python.exe scripts/qc_eu_results.py --raw-root results/eu_rc_vs_pinn/raw

# Publication plots  
.venv\Scripts\python.exe scripts/generate_publication_plots.py --raw-root results/eu_rc_vs_pinn/raw

# For heating season (when complete)
.venv\Scripts\python.exe scripts/generate_publication_plots.py --raw-root results/eu_rc_vs_pinn_heating/raw --out-dir results/publication_plots/heating_season

# View results
explorer.exe results\publication_plots
explorer.exe results\eu_rc_vs_pinn\qc\timeseries
```

---

## Summary

| Component | Location | Purpose | For Article |
|-----------|----------|---------|-------------|
| Publication Plots | `results/publication_plots/` | Ready for submission | Main figures 3-6 |
| QC Report | `results/eu_rc_vs_pinn/qc/` | Data validation | Supplementary material |
| Timeseries Plots | `results/eu_rc_vs_pinn/qc/timeseries/` | Episode detail | Appendix examples |
| KPI Table | `results/eu_rc_vs_pinn/qc/kpi_table.csv` | Raw metrics | Data availability |

**Status:** ✅ Main campaign plots ready  
**Next:** ⏳ Heating season completion (3-5h)  
**Ready to Write:** ✅ Yes - 6 figures are production-quality

---
