#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pinn_model.data import build_datasets, load_training_config
from pinn_model.model import SingleZonePINN


def _load_history(history_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with history_path.open("r", encoding="utf-8") as f:
        history = json.load(f)

    if not isinstance(history, list):
        raise ValueError(f"Expected list history format in {history_path}")

    epochs: list[float] = []
    train_loss: list[float] = []
    val_loss: list[float] = []
    for row in history:
        if not isinstance(row, dict):
            continue
        if "epoch" in row and "train_loss" in row and "val_loss" in row:
            epochs.append(float(row["epoch"]))
            train_loss.append(float(row["train_loss"]))
            val_loss.append(float(row["val_loss"]))

    return np.asarray(epochs), np.asarray(train_loss), np.asarray(val_loss)


def _load_model(checkpoint_path: Path, input_dim: int, hidden_dim: int, depth: int, dropout: float) -> SingleZonePINN:
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if "model_state_dict" not in ckpt:
        raise KeyError(f"Checkpoint missing model_state_dict: {checkpoint_path}")

    model = SingleZonePINN(input_dim=input_dim, hidden_dim=hidden_dim, depth=depth, dropout=dropout)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model


def _predict_episode(model: SingleZonePINN, samples: list, stats: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    feature_mean = np.asarray(stats["feature_mean"], dtype=np.float32)
    feature_std = np.asarray(stats["feature_std"], dtype=np.float32)

    true_next = np.asarray([float(s.target_next_t_zone) for s in samples], dtype=np.float32)
    times_h = np.asarray([float(s.time_s) / 3600.0 for s in samples], dtype=np.float32)

    one_step_preds: list[float] = []
    rollout_preds: list[float] = []

    rollout_current = float(samples[0].t_zone)
    prev_u = float(samples[0].u_heating)

    with torch.no_grad():
        for s in samples:
            # One-step (teacher forcing): current state comes from real measurement
            fv_one = np.asarray(
                [
                    float(s.t_zone),
                    float(s.t_outdoor),
                    float(s.h_global),
                    float(s.u_heating),
                    float(s.u_heating) - float(prev_u),
                    *[float(v) for v in s.features[-4:]],
                ],
                dtype=np.float32,
            )
            f_one = torch.tensor((fv_one - feature_mean) / feature_std, dtype=torch.float32).unsqueeze(0)
            out_one = model(
                f_one,
                torch.tensor([float(s.t_zone)], dtype=torch.float32),
                torch.tensor([float(s.t_outdoor)], dtype=torch.float32),
                torch.tensor([float(s.h_global)], dtype=torch.float32),
                torch.tensor([float(s.u_heating)], dtype=torch.float32),
                torch.tensor([float(s.dt_s)], dtype=torch.float32),
            )
            one_step_preds.append(float(out_one["predicted_next"].item()))

            # Rollout: current state comes from previous prediction
            fv_roll = np.asarray(
                [
                    float(rollout_current),
                    float(s.t_outdoor),
                    float(s.h_global),
                    float(s.u_heating),
                    float(s.u_heating) - float(prev_u),
                    *[float(v) for v in s.features[-4:]],
                ],
                dtype=np.float32,
            )
            f_roll = torch.tensor((fv_roll - feature_mean) / feature_std, dtype=torch.float32).unsqueeze(0)
            out_roll = model(
                f_roll,
                torch.tensor([float(rollout_current)], dtype=torch.float32),
                torch.tensor([float(s.t_outdoor)], dtype=torch.float32),
                torch.tensor([float(s.h_global)], dtype=torch.float32),
                torch.tensor([float(s.u_heating)], dtype=torch.float32),
                torch.tensor([float(s.dt_s)], dtype=torch.float32),
            )
            rollout_current = float(out_roll["predicted_next"].item())
            rollout_preds.append(rollout_current)
            prev_u = float(s.u_heating)

    return times_h, true_next, np.asarray(one_step_preds), np.asarray(rollout_preds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot PINN training and real-vs-pred trajectories")
    parser.add_argument("--config", default="configs/pinn_phase1.yaml")
    parser.add_argument("--artifact-dir", default="artifacts/pinn_phase1")
    parser.add_argument("--episode-id", default=None, help="Optional validation episode id")
    parser.add_argument(
        "--output",
        default="artifacts/pinn_phase1/training_diagnostics.png",
        help="Output image path",
    )
    args = parser.parse_args()

    config = load_training_config(ROOT / args.config)
    datasets = build_datasets(config, ROOT)

    artifact_dir = ROOT / args.artifact_dir
    history_path = artifact_dir / "history.json"
    checkpoint_path = artifact_dir / "best_model.pt"
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    epochs, train_loss, val_loss = _load_history(history_path)

    model = _load_model(
        checkpoint_path=checkpoint_path,
        input_dim=len(datasets["feature_names"]),
        hidden_dim=int(config["model"]["hidden_dim"]),
        depth=int(config["model"]["depth"]),
        dropout=float(config["model"].get("dropout", 0.0)),
    )

    val_episodes = datasets["val_episodes"]
    if not val_episodes:
        raise RuntimeError("No validation episodes available for plotting.")

    if args.episode_id is not None:
        if args.episode_id not in val_episodes:
            raise KeyError(f"Episode {args.episode_id} not found in validation episodes.")
        episode_id = args.episode_id
    else:
        episode_id = sorted(val_episodes.keys())[0]

    samples = val_episodes[episode_id]
    stats = datasets["stats"].to_dict()
    times_h, true_next, one_step_pred, rollout_pred = _predict_episode(model, samples, stats)

    one_step_rmse = float(np.sqrt(np.mean((one_step_pred - true_next) ** 2)))
    rollout_rmse = float(np.sqrt(np.mean((rollout_pred - true_next) ** 2)))

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)

    axes[0].plot(epochs, train_loss, label="Train loss", linewidth=1.8)
    axes[0].plot(epochs, val_loss, label="Validation loss", linewidth=1.8)
    best_idx = int(np.argmin(val_loss))
    axes[0].scatter([epochs[best_idx]], [val_loss[best_idx]], color="red", zorder=5, label="Best val epoch")
    axes[0].set_title("PINN training curves")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].grid(alpha=0.3)
    axes[0].legend()

    axes[1].plot(times_h, true_next, label="Real next T_zone", linewidth=2.0)
    axes[1].plot(times_h, one_step_pred, label=f"PINN one-step (RMSE={one_step_rmse:.3f})", linewidth=1.6)
    axes[1].plot(times_h, rollout_pred, label=f"PINN rollout (RMSE={rollout_rmse:.3f})", linewidth=1.6)
    axes[1].set_title(f"Validation episode: {episode_id} (real vs prediction)")
    axes[1].set_xlabel("Time [h]")
    axes[1].set_ylabel("Zone temperature [degC]")
    axes[1].grid(alpha=0.3)
    axes[1].legend()

    fig.savefig(output_path, dpi=160)
    print(f"Saved plot: {output_path}")
    print(f"Episode used: {episode_id}")
    print(f"One-step RMSE: {one_step_rmse:.4f} degC")
    print(f"Rollout RMSE: {rollout_rmse:.4f} degC")


if __name__ == "__main__":
    main()
