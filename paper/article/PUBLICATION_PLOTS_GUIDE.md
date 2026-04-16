# Publication-Quality Plot Generation Guide

**Generated: March 20, 2026**

## Overview

## Full Validation Publication Set (2026-04-02)

For the current manuscript cycle, use the refreshed full-validation artifacts under:

- `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/plots`

Primary figure set:

1. `comparison_all_controllers_combined.png`
2. `comparison_all_controllers_cost.png`
3. `comparison_all_controllers_tdis.png`
4. `comparison_all_controllers_solve_time.png`

Data sources to cite with this figure set:

- `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/summary_full_validation.json`
- `results/mpc_tuning_eval/autotune_v1_10cand/full_validation/execution_report_fixed.md`
- `artifacts/full_validation_all_controllers_aggregated.csv`

Caption guidance for this set:

- `comparison_all_controllers_cost.png`: Candidate-wise operating cost comparison for RC, PINN, and RBC against refreshed baselines.
- `comparison_all_controllers_tdis.png`: Candidate-wise thermal discomfort (`tdis_tot`) comparison across controllers.
- `comparison_all_controllers_solve_time.png`: MPC solve-time comparison (RBC at 0 ms by design).
- `comparison_all_controllers_combined.png`: Joint view of cost, comfort, and solve-time tradeoffs.

Notes:

- The `cost_comparison_pinn.png`, `tdis_comparison_pinn.png`, and `solve_time_comparison_pinn.png` plots are legacy PINN-only views; keep them as supplementary material unless explicitly needed.

Two complementary plot generation scripts are available:

1. **`qc_eu_results.py`** ─ Quality control and validation
   - Plausibility checks (data validation)
   - Per-episode timeseries comparisons
   - Basic overview plots (comfort-energy scatter, solver times)
   
2. **`generate_publication_plots.py`** ─ High-quality article-ready plots
   - Per-case KPI bar charts
   - Relative improvement analysis
   - Aggregated statistics with box plots
   - Enhanced Pareto frontier visualization

---

## Plot Overview for Your Article

### **Group 1: Per-Case Performance (3 plots)**

#### 01_energy_per_case.png
- **What**: Side-by-side RC vs PINN energy consumption for each case
- **Y-axis**: Total energy [Wh/m²] (normalized per floor area)
- **Use case**: Shows energy efficiency across different building types
- **Key insight**: Identify which cases benefit most from PINN optimization

#### 02_comfort_per_case.png
- **What**: Thermal comfort violation metrics by case
- **Y-axis**: Discomfort [K·h] - integral of temperature deviations
- **Use case**: Demonstrate thermal comfort maintenance
- **Key insight**: Show PINN performance on comfort constraints

#### 03_peak_power_per_case.png
- **What**: Peak power demand comparison
- **Y-axis**: Max power [W/m²] during episode
- **Use case**: Important for grid/infrastructure planning
- **Key insight**: PINN's impact on peak demand reduction

---

### **Group 2: Performance Analysis (2 plots)**

#### 04_relative_energy_improvement.png
- **What**: % energy difference (PINN vs RC) for each case
- **Axis**: Energy difference [%]
  - Negative values = PINN saves energy ✓
  - Positive values = RC saves energy
- **Use case**: Main headline metric for the paper
- **Key insight**: Quantify PINN advantage/disadvantage per case

#### 05_aggregated_kpi_boxplots.png
- **What**: Statistical distribution of all KPIs across episodes
- **Shows**: 
  - Energy consumption (distribution across all runs)
  - Comfort violations (spread & consistency)
  - Peak power (variability by approach)
  - Solver runtime (computational cost)
- **Use case**: Demonstrate not just average but also variability
- **Key insight**: Statistical significance & robustness

---

### **Group 3: Trade-off Analysis (1 plot)**

#### 06_pareto_frontier_enhanced.png
- **What**: Comfort vs Energy scatter with trend lines
- **X-axis**: Total energy [Wh/m²]
- **Y-axis**: Comfort deviation [K·h]
- **Markers**: 
  - Blue circles = RC results
  - Red squares = PINN results
- **Includes**: Trend lines for each predictor
- **Use case**: Show the feasible solution region & trade-off
- **Key insight**: Demonstrate Pareto optimality or clustering

---

## Running the Plot Generators

### Basic QC Plots (existing results):
```powershell
cd "C:\Users\AVoelser\..."
.venv\Scripts\python.exe scripts/qc_eu_results.py \
  --raw-root results/eu_rc_vs_pinn/raw \
  --out-dir results/eu_rc_vs_pinn/qc
```

### Publication Plots:
```powershell
.venv\Scripts\python.exe scripts/generate_publication_plots.py \
  --raw-root results/eu_rc_vs_pinn/raw \
  --out-dir results/publication_plots
```

### For Heating Season Campaign (once complete):
```powershell
.venv\Scripts\python.exe scripts/generate_publication_plots.py \
  --raw-root results/eu_rc_vs_pinn_heating/raw \
  --out-dir results/publication_plots/heating_season
```

---

## Article Structure Recommendations

### Section: Benchmark Results

**Paragraph 1: Case-wise Performance**
- Use: 01_energy_per_case.png, 02_comfort_per_case.png
- Text: "We evaluated both predictors on four distinct building types. Energy consumption per unit floor area ranges from X to Y Wh/m²..."

**Paragraph 2: Comparative Advantage**
- Use: 04_relative_energy_improvement.png
- Text: "PINN-MPC demonstrates energy savings of X% on average across cases, with benefits particularly pronounced in multizone buildings..."

**Paragraph 3: Statistical Robustness**
- Use: 05_aggregated_kpi_boxplots.png
- Text: "Across all episodes, PINN shows consistent performance (σ = Y Wh/m²) compared to RC baseline..."

**Paragraph 4: Trade-off Analysis**
- Use: 06_pareto_frontier_enhanced.png
- Text: "The Pareto frontier reveals that solutions cluster into distinct regions based on... The trend lines suggest..."

**Sidebar: Computational Cost**
- Use: Solve time from 05_aggregated_kpi_boxplots.png (bottom-right)
- Text: "PINN-MPC requires X ms average solve time, providing real-time MPC capability..."

---

## Suggested Enhancements for Article Impact

### Additional Plots to Consider

1. **Case Ranking Heatmap** (when heating season is complete)
   - Color-code each case/predictor by relative performance
   - Shows at a glance which cases favor PINN vs RC

2. **Seasonal Comparison** (heating vs standard episodes)
   - Side-by-side bars for same cases in different seasons
   - Demonstrates seasonal robustness

3. **Control Strategy Comparison** (timeseries examples)
   - Select 2-3 representative episodes (1 cold, 1 mild, 1 mixed)
   - Show RC vs PINN heating setpoint evolution
   - Highlight when MPC makes aggressive vs conservative decisions

4. **Training Quality** (if including model variance analysis)
   - Test set RMSE by case
   - Model reliability estimate
   - Compare to physics-based baseline if available

5. **Cost-Benefit Analysis** (if energy pricing available)
   - Absolute cost savings [€/year]
   - Cost per comfort improvement [€/K·h avoided]
   - Payback period for surrogate training

---

## Quality Checklist for Plots

✓ **Font sizes**: Labels readable at journal column width (8-11 pt)
✓ **DPI**: All plots saved at 300 DPI for print quality
✓ **Colors**: Accessible (colorblind-friendly palette: blue/red)
✓ **Grid lines**: Light alpha for reference without clutter
✓ **Legends**: Included and positioned for clarity
✓ **Titles**: Clear and descriptive
✓ **Units**: Always shown on axes
✓ **Error bars**: Consider adding std dev to bar charts (optional enhancement)
✓ **Data labels**: Value numbers on bars for precise reading

---

## Next Steps When Heating Campaign Completes

1. **Generate heating season plots:**
   ```powershell
   .venv\Scripts\python.exe scripts/generate_publication_plots.py \
     --raw-root results/eu_rc_vs_pinn_heating/raw \
     --out-dir results/publication_plots/heating_season
   ```

2. **Compare standard vs heating:**
   - Create side-by-side figures showing seasonal differences
   - Quantify performance variation (CV, range)

3. **Create combined summary table:**
   - All cases × metrics in single CSV/table
   - Useful for supplementary material

4. **Optional: Generate Protocol A validation plots**
   - If you want to include fairness validation evidence
   - Show that manifests are equivalent for RC and PINN

---

## File Organization

```
results/
├── eu_rc_vs_pinn/
│   ├── raw/                    ← Episode JSON results
│   ├── qc/                     ← Quality control outputs
│   │   ├── kpi_table.csv
│   │   ├── plausibility_summary.csv
│   │   ├── timeseries/         ← Per-episode plots
│   │   └── overview/           ← Comfort-energy scatter, etc.
│   └── publication_plots/      ← High-quality article plots ✓
│       ├── 01_energy_per_case.png
│       ├── 02_comfort_per_case.png
│       ├── 03_peak_power_per_case.png
│       ├── 04_relative_energy_improvement.png
│       ├── 05_aggregated_kpi_boxplots.png
│       └── 06_pareto_frontier_enhanced.png
│
├── eu_rc_vs_pinn_heating/      ← Heating season campaign results
│   ├── raw/
│   └── publication_plots/heating_season/  ← Generate when complete
│
└── publication_plots/          ← Main hub for article figures
    ├── main_campaign/          ← Standard episodes (4/5 cases)
    ├── heating_season/         ← Seasonal subset (when ready)
    └── combined/               ← Side-by-side comparisons
```

---

## Current Status

**Main Campaign (Standard Episodes):**
- ✓ 4 of 4 cases complete
- ✓ All 24 episodes (4 cases × 3 episodes × 2 predictors) processed
- ✓ 6 publication plots generated

**Heating Campaign:**
- ⏳ 4 of 4 cases complete (multizone excluded from study)
- ⏳ Will have seasonal subset for robustness comparison
- ⏳ Estimated completion: 3-5 hours from now

---

## Tips for Figure Captions

**Example caption for 06_pareto_frontier_enhanced.png:**

> **Figure 4**: Energy-comfort trade-off frontier. RC baseline (blue) and PINN-MPC (red) solutions are plotted against total energy consumption and cumulative comfort violations. Trend lines (dashed) show the approximate Pareto frontier for each approach. PINN solutions cluster in the lower-left region, indicating simultaneous reductions in both energy consumption and discomfort. The overlapping regions suggest problem-dependent performance variations across building types.

---
