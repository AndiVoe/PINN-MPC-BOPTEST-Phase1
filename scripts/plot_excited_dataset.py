from __future__ import annotations

import argparse
import json
from pathlib import Path
from itertools import cycle

import matplotlib.pyplot as plt
import pandas as pd


BASE = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = BASE / "datasets/phase1_excited/csv"
DEFAULT_OUTPUT_DIR = BASE / "results/figures/phase1_excited"


def load_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        df = pd.DataFrame(data["records"])
    else:
        raise ValueError(f"Unsupported dataset format: {path.suffix}")

    required = ["time_s", "T_zone_degC", "T_outdoor_degC", "H_global_Wm2", "u_heating"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in {path.name}: {', '.join(missing)}")

    df = df.copy()
    df = df.sort_values("time_s").reset_index(drop=True)
    t0 = df["time_s"].iloc[0]
    df["days"] = (df["time_s"] - t0) / (24 * 3600)
    return df


def plot_dataset_overview(df: pd.DataFrame, title: str, output_path: Path) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(
        3,
        1,
        figsize=(15, 12),
        sharex=True,
        gridspec_kw={"hspace": 0.15},
        constrained_layout=True,
    )

    axes[0].plot(df["days"], df["T_zone_degC"], label="Zone Temp", color="#2E86C1", linewidth=1.5)
    axes[0].plot(df["days"], df["T_outdoor_degC"], label="Outdoor Temp", color="#A93226", alpha=0.5, linewidth=1.0)
    axes[0].set_ylabel("Temperature [°C]", fontsize=12, fontweight="bold")
    axes[0].legend(loc="upper right", frameon=True, shadow=True)
    axes[0].set_title(title, fontsize=16, pad=20, fontweight="bold")

    axes[1].fill_between(df["days"], df["H_global_Wm2"], color="#F1C40F", alpha=0.3, label="Solar Irradiation")
    axes[1].plot(df["days"], df["H_global_Wm2"], color="#F39C12", linewidth=0.8)
    axes[1].set_ylabel("Solar [W/m²]", fontsize=12, fontweight="bold")
    axes[1].legend(loc="upper right", frameon=True, shadow=True)

    axes[2].step(df["days"], df["u_heating"], where="post", color="#16A085", linewidth=1.5, label="Excited Setpoint (u)")
    axes[2].set_ylabel("Setpoint [°C]", fontsize=12, fontweight="bold")
    axes[2].set_xlabel("Time [Days]", fontsize=12, fontweight="bold")
    axes[2].legend(loc="upper right", frameon=True, shadow=True)

    for ax in axes:
        ax.grid(True, which="both", linestyle="--", alpha=0.5)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def iter_input_files(input_dir: Path) -> list[Path]:
    files = sorted(input_dir.glob("*.csv")) + sorted(input_dir.glob("*.json"))
    return [path for path in files if path.is_file()]


def season_from_stem(stem: str) -> str | None:
    if "_win_" in stem or "te_exc_win" in stem:
        return "winter"
    if "_spr_" in stem:
        return "spring"
    if "_sum_" in stem:
        return "summer"
    if "_aut_" in stem:
        return "autumn"
    return None


def outdoor_trace_signature(df: pd.DataFrame) -> tuple[int, float, float, float]:
    return (
        len(df),
        float(df["time_s"].iloc[0]),
        float(df["time_s"].iloc[-1]),
        float(df["T_outdoor_degC"].round(6).sum()),
    )


def unique_outdoor_traces(datasets: list[tuple[Path, pd.DataFrame]]) -> list[tuple[Path, pd.DataFrame]]:
    unique: list[tuple[Path, pd.DataFrame]] = []
    seen: set[tuple[int, float, float, float]] = set()
    for path, df in datasets:
        signature = outdoor_trace_signature(df)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append((path, df))
    return unique


def plot_outdoor_temperatures_by_season(
    season_name: str,
    datasets: list[tuple[Path, pd.DataFrame]],
    output_path: Path,
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(15, 7), constrained_layout=True)

    color_cycle = cycle([
        "#2E86C1",
        "#A93226",
        "#16A085",
        "#8E44AD",
        "#D35400",
        "#1F618D",
        "#117A65",
        "#B03A2E",
        "#7D3C98",
        "#CA6F1E",
        "#566573",
    ])
    line_cycle = cycle(["-", "--", "-.", ":"])

    plotted_count = 0
    for path, df in datasets:
        ax.plot(
            df["days"],
            df["T_outdoor_degC"],
            label=path.stem,
            color=next(color_cycle),
            linestyle=next(line_cycle),
            linewidth=1.6,
            alpha=0.9,
        )
        plotted_count += 1

    if plotted_count == 0:
        return

    ax.set_title(f"Phase 1 Excited Datasets: Outdoor Temperature Comparison ({season_name})", fontsize=16, fontweight="bold")
    ax.set_xlabel("Time [Days]", fontsize=12, fontweight="bold")
    ax.set_ylabel("Outdoor Temperature [°C]", fontsize=12, fontweight="bold")
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", frameon=True, fontsize=9, ncol=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_all_outdoor_temperatures_grouped(datasets: list[tuple[Path, pd.DataFrame]], output_dir: Path) -> None:
    season_groups: dict[str, list[tuple[Path, pd.DataFrame]]] = {
        "winter": [],
        "spring": [],
        "summer": [],
        "autumn": [],
    }

    for path, df in datasets:
        season = season_from_stem(path.stem)
        if season is None:
            continue
        season_groups[season].append((path, df))

    for season_name, season_datasets in season_groups.items():
        if not season_datasets:
            continue
        output_path = output_dir / f"dataset_overview_outdoor_temperatures_{season_name}.png"
        unique_datasets = unique_outdoor_traces(season_datasets)
        plot_outdoor_temperatures_by_season(season_name, unique_datasets, output_path)
        print(f"  Saved -> {output_path.name}")


def plot_outdoor_temperatures_season_grid(datasets: list[tuple[Path, pd.DataFrame]], output_path: Path) -> None:
    season_order = ["winter", "spring", "summer", "autumn"]
    season_titles = {
        "winter": "Winter",
        "spring": "Spring",
        "summer": "Summer",
        "autumn": "Autumn",
    }
    season_groups: dict[str, list[tuple[Path, pd.DataFrame]]] = {season: [] for season in season_order}

    for path, df in datasets:
        season = season_from_stem(path.stem)
        if season is None:
            continue
        season_groups[season].append((path, df))

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 12), sharex=False, constrained_layout=True)
    axes_flat = axes.flatten()

    color_cycle = cycle([
        "#2E86C1",
        "#A93226",
        "#16A085",
        "#8E44AD",
        "#D35400",
        "#1F618D",
        "#117A65",
        "#B03A2E",
        "#7D3C98",
        "#CA6F1E",
        "#566573",
    ])
    line_cycle = cycle(["-", "--", "-.", ":"])

    for ax, season in zip(axes_flat, season_order, strict=True):
        season_datasets = unique_outdoor_traces(season_groups[season])
        for path, df in season_datasets:
            ax.plot(
                df["days"],
                df["T_outdoor_degC"],
                label=path.stem,
                color=next(color_cycle),
                linestyle=next(line_cycle),
                linewidth=1.5,
                alpha=0.9,
            )

        ax.set_title(f"{season_titles[season]}", fontsize=14, fontweight="bold")
        ax.set_xlabel("Time [Days]", fontsize=11, fontweight="bold")
        ax.set_ylabel("Outdoor Temp [°C]", fontsize=11, fontweight="bold")
        ax.grid(True, which="both", linestyle="--", alpha=0.5)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if season_datasets:
            ax.legend(loc="best", frameon=True, fontsize=8)
        else:
            ax.text(0.5, 0.5, "No datasets", ha="center", va="center", transform=ax.transAxes)

    fig.suptitle("Phase 1 Excited Datasets: Outdoor Temperature Comparison by Season", fontsize=18, fontweight="bold")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate overview plots for phase1 excited datasets.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR), help="Directory containing excited dataset CSV or JSON files.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory where plots will be written.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit on the number of files to plot.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_absolute():
        input_dir = BASE / input_dir

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = BASE / output_dir

    files = iter_input_files(input_dir)
    if args.limit and args.limit > 0:
        files = files[: args.limit]

    if not files:
        print(f"No CSV or JSON files found in {input_dir}")
        return 1

    print(f"Plotting {len(files)} excited dataset files from {input_dir}...")
    loaded_datasets: list[tuple[Path, pd.DataFrame]] = []
    for path in files:
        df = load_dataset(path)
        loaded_datasets.append((path, df))
        title = f"Dataset Overview: {path.stem}"
        output_path = output_dir / f"dataset_overview_{path.stem}.png"
        plot_dataset_overview(df, title, output_path)
        print(f"  Saved -> {output_path.name}")

    plot_all_outdoor_temperatures_grouped(loaded_datasets, output_dir)
    combined_output = output_dir / "dataset_overview_outdoor_temperatures_by_season.png"
    plot_outdoor_temperatures_season_grid(loaded_datasets, combined_output)
    print(f"  Saved -> {combined_output.name}")

    print(f"Done. Plots written to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())