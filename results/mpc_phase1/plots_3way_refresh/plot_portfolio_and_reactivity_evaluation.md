# Plot Portfolio and Controller Reactivity Evaluation

## Evaluated Plot Set
- Folder: results/mpc_phase1/plots_3way_refresh
- Files: 01_energy_comparison, 02_comfort_comparison, 03_peak_power_comparison, 04_boxplot_aggregated, energy_3way_refreshed, comfort_3way_refreshed, peak_3way_refreshed, energy_delta_vs_rbc_refreshed, energy_delta_vs_rc_refreshed, timeseries_case_episode/*

## Keep / Redundant Decision
### Keep (primary, main narrative)
- 01_energy_comparison.png: compact cross-case headline for energy.
- 02_comfort_comparison.png: compact cross-case comfort comparison.
- 03_peak_power_comparison.png: compact cross-case demand/peak comparison.
- energy_delta_vs_rbc_refreshed.png: best baseline framing (RBC as operational reference).
- timeseries_case_episode/*.png: only plots that reveal control dynamics/oscillation.

### Keep (secondary, appendix)
- 04_boxplot_aggregated.png: spread/outliers across all episodes.
- comfort_3way_refreshed.png, peak_3way_refreshed.png: refreshed subset details.

### Redundant (or only keep in appendix)
- energy_3way_refreshed.png: overlaps with 01_energy_comparison (same KPI story at different aggregation).
- energy_delta_vs_rc_refreshed.png: lower value once RBC is the chosen baseline.

## Reactivity Analysis
Two scopes are reported to avoid bias from a small subset:
- Scope A: refreshed common episodes in results/mpc_phase1 (te_ext_01, te_ext_02, te_std_01, te_std_02).
- Scope B: EU raw campaign, per-case std episodes (3 episodes per case), aggregated by case.

### Scope A (refreshed subset)
| Controller | Mean energy [MWh] | Mean comfort [Kh] | Mean peak [kW] | mean |du| [degC/step] | p95 |du| | jump>0.5C | distinct setpoints (0.1C) |
|---|---:|---:|---:|---:|---:|---:|---:|
| RC | 19.550 | 5.5255 | 177.54 | 0.0045 | 0.0000 | 0.19% | 2.75 |
| PINN | 11.121 | 0.6489 | 173.66 | 0.0017 | 0.0027 | 0.00% | 2.50 |
| RBC | 11.078 | 0.8105 | 173.66 | 0.0000 | 0.0000 | 0.00% | 1.00 |

Scope A finding: no strong overreaction signal; RBC is most constant, PINN is smooth in this subset.

### Scope B (EU raw campaign, case-wise reactivity)
| Case | RC mean |du| | PINN mean |du| | RBC mean |du| | Most reactive |
|---|---:|---:|---:|---|
| bestest_hydronic | 0.0009 | 0.0600 | 0.0174 | PINN |
| bestest_hydronic_heat_pump | 0.0013 | 0.1793 | 0.0078 | PINN |
| singlezone_commercial_hydronic | 0.0014 | 0.0139 | 0.0040 | PINN |
| twozone_apartment_hydronic | 0.0010 | 0.3745 | 0.0156 | PINN |

| Controller | Mean case-level |du| [degC/step] |
|---|---:|
| RC | 0.0012 |
| PINN | 0.1569 |
| RBC | 0.0112 |

Scope B finding: PINN is clearly the most reactive overall, with strong sensitivity in bestest_hydronic_heat_pump and twozone_apartment_hydronic.

## Final Judgment on Overreaction/Oscillation Risk
- On refreshed phase1 subset: low oscillation risk is observed.
- On broader EU case set: PINN shows aggressive control motion in multiple cases, consistent with potential overreaction/chattering risk.
- Recommendation: tune PINN-MPC with stronger slew-rate penalty and/or move suppression, then re-run this same reactivity table as acceptance criteria.

## Practical Plot Set to Keep Going Forward
Main report: 01_energy_comparison, 02_comfort_comparison, 03_peak_power_comparison, energy_delta_vs_rbc_refreshed, plus 2-4 representative timeseries_case_episode plots.
Appendix: 04_boxplot_aggregated, comfort_3way_refreshed, peak_3way_refreshed.
Drop from main set: energy_3way_refreshed, energy_delta_vs_rc_refreshed.