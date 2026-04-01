#!/usr/bin/env python3
"""Parse full-validation report and create comparison plots for all controllers.

Saves PNGs to the full_validation/plots folder and an aggregated CSV to artifacts/.
"""
from pathlib import Path
import sys
import math

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
except Exception as e:
    print('Missing plotting dependencies:', e)
    print('Install with: pip install pandas matplotlib seaborn')
    raise


ROOT = Path(__file__).resolve().parents[1]
REPORT_MD = ROOT / 'results' / 'mpc_tuning_eval' / 'autotune_v1_10cand' / 'full_validation' / 'execution_report_fixed.md'
PLOTS_DIR = ROOT / 'results' / 'mpc_tuning_eval' / 'autotune_v1_10cand' / 'full_validation' / 'plots'
ARTIFACT_CSV = ROOT / 'artifacts' / 'full_validation_all_controllers_aggregated.csv'


def parse_aggregates(md_path: Path):
    text = md_path.read_text(encoding='utf-8')
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith('## Aggregates per candidate'):
            start = i
            break
    if start is None:
        raise RuntimeError('Aggregates section not found in ' + str(md_path))

    # find the table header
    header_idx = None
    for j in range(start, start + 60):
        if lines[j].strip().startswith('| Candidate'):
            header_idx = j
            break
    if header_idx is None:
        raise RuntimeError('Table header not found after aggregates section')

    rows = []
    for ln in lines[header_idx+2:]:
        if not ln.strip().startswith('|'):
            break
        parts = [p.strip() for p in ln.strip().split('|')[1:-1]]
        if len(parts) < 7:
            continue
        rows.append(parts[:7])

    df = pd.DataFrame(rows, columns=['candidate','controller','cost_mean','tdis_mean','solve_mean_ms','wall_time_s_mean','smoothness_mean'])
    for c in ['cost_mean','tdis_mean','solve_mean_ms','wall_time_s_mean','smoothness_mean']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


def ensure_dir(p: Path):
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)


def annotate_bars(ax, fmt='{:.4f}', fontsize=9):
    for p in ax.patches:
        try:
            h = p.get_height()
        except Exception:
            continue
        if math.isnan(h):
            continue
        x = p.get_x() + p.get_width() / 2
        y = h
        if abs(h) < 1e-6:
            label = fmt.format(float(h))
        else:
            label = fmt.format(float(h))
        ax.annotate(label, (x, y), ha='center', va='bottom', fontsize=fontsize, xytext=(0, 3), textcoords='offset points')


def plot_grouped(df, ycol, ylabel, outname, value_fmt='{:.4f}'):
    ensure_dir(PLOTS_DIR)
    plt.figure(figsize=(8, 4.5))
    sns.set(style='whitegrid')
    ax = sns.barplot(data=df, x='candidate', y=ycol, hue='controller')
    ax.set_ylabel(ylabel)
    ax.set_xlabel('Candidate')
    plt.legend(title='Controller')
    annotate_bars(ax, fmt=value_fmt)
    plt.tight_layout()
    outpath = PLOTS_DIR / outname
    plt.savefig(outpath, dpi=200)
    plt.close()
    print('Wrote:', outpath)


def plot_combined(df, outname='comparison_all_controllers_combined.png'):
    ensure_dir(PLOTS_DIR)
    sns.set(style='whitegrid')
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    sns.barplot(data=df, x='candidate', y='cost_mean', hue='controller', ax=axes[0])
    axes[0].set_title('Cost (mean)')
    axes[0].set_ylabel('cost_mean')

    sns.barplot(data=df, x='candidate', y='tdis_mean', hue='controller', ax=axes[1])
    axes[1].set_title('Thermal discomfort (mean)')
    axes[1].set_ylabel('tdis_mean')

    sns.barplot(data=df, x='candidate', y='solve_mean_ms', hue='controller', ax=axes[2])
    axes[2].set_title('Solver time (ms, mean)')
    axes[2].set_ylabel('solve_mean_ms')

    # Annotate each subplot
    for ax in axes:
        # remove duplicate legends
        if ax is not axes[2]:
            ax.get_legend().remove()
        annotate_bars(ax, fmt='{:.3f}', fontsize=8)

    plt.tight_layout()
    outpath = PLOTS_DIR / outname
    fig.savefig(outpath, dpi=200)
    plt.close(fig)
    print('Wrote:', outpath)


def main():
    if not REPORT_MD.exists():
        print('Report file not found:', REPORT_MD)
        sys.exit(2)

    df = parse_aggregates(REPORT_MD)
    # Persist a clean CSV for reuse
    ensure_dir(ARTIFACT_CSV.parent)
    df.to_csv(ARTIFACT_CSV, index=False)
    print('Wrote CSV:', ARTIFACT_CSV)

    # Individual plots with values
    plot_grouped(df, 'cost_mean', 'Cost (mean)', 'comparison_all_controllers_cost.png', value_fmt='{:.6f}')
    plot_grouped(df, 'tdis_mean', 'Thermal discomfort (mean)', 'comparison_all_controllers_tdis.png', value_fmt='{:.4f}')
    plot_grouped(df, 'solve_mean_ms', 'Solver time (ms, mean)', 'comparison_all_controllers_solve_time.png', value_fmt='{:.3f}')

    # Combined figure
    plot_combined(df)


if __name__ == '__main__':
    main()
