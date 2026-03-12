from __future__ import annotations

import json
import math
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .data import NormalizationStats, Sample
from .model import SingleZonePINN


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def denormalize_target(target: torch.Tensor, stats: NormalizationStats) -> torch.Tensor:
    return target * stats.target_std + stats.target_mean


def _rmse(errors: list[float]) -> float:
    if not errors:
        return 0.0
    return math.sqrt(sum(error * error for error in errors) / len(errors))


def _mae(errors: list[float]) -> float:
    if not errors:
        return 0.0
    return sum(abs(error) for error in errors) / len(errors)


def _build_loader(dataset: Dataset[dict[str, torch.Tensor]], batch_size: int, shuffle: bool) -> DataLoader:
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, drop_last=False)


def _run_epoch(
    model: SingleZonePINN,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer | None,
    stats: NormalizationStats,
    device: torch.device,
    lambda_physics: float,
) -> dict[str, float]:
    mse_loss = nn.MSELoss()
    training = optimizer is not None
    if training:
        model.train()
    else:
        model.eval()

    total_loss = 0.0
    total_data_loss = 0.0
    total_physics_loss = 0.0
    total_count = 0
    errors: list[float] = []

    for batch in loader:
        features = batch["features"].to(device)
        target = batch["target"].to(device)
        t_zone = batch["t_zone"].to(device)
        t_outdoor = batch["t_outdoor"].to(device)
        h_global = batch["h_global"].to(device)
        u_heating = batch["u_heating"].to(device)
        dt_s = batch["dt_s"].to(device)

        context = torch.enable_grad() if training else torch.no_grad()
        with context:
            outputs = model(features, t_zone, t_outdoor, h_global, u_heating, dt_s)
            predicted_normalized = (outputs["predicted_next"] - stats.target_mean) / stats.target_std
            data_loss = mse_loss(predicted_normalized, target)
            physics_loss = torch.mean(outputs["correction"] ** 2)
            loss = data_loss + lambda_physics * physics_loss

            if training:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()

        predicted_raw = denormalize_target(predicted_normalized.detach().cpu(), stats)
        target_raw = denormalize_target(target.detach().cpu(), stats)
        batch_errors = (predicted_raw - target_raw).tolist()
        errors.extend(float(value) for value in batch_errors)

        batch_size = target.shape[0]
        total_count += batch_size
        total_loss += float(loss.detach().cpu()) * batch_size
        total_data_loss += float(data_loss.detach().cpu()) * batch_size
        total_physics_loss += float(physics_loss.detach().cpu()) * batch_size

    return {
        "loss": total_loss / max(total_count, 1),
        "data_loss": total_data_loss / max(total_count, 1),
        "physics_loss": total_physics_loss / max(total_count, 1),
        "rmse_degC": _rmse(errors),
        "mae_degC": _mae(errors),
    }


def evaluate_rollout(
    model: SingleZonePINN,
    episodes: dict[str, list[Sample]],
    stats: NormalizationStats,
    device: torch.device,
) -> dict[str, float]:
    model.eval()
    feature_mean = np.asarray(stats.feature_mean, dtype=np.float32)
    feature_std = np.asarray(stats.feature_std, dtype=np.float32)
    errors: list[float] = []

    with torch.no_grad():
        for samples in episodes.values():
            current_temp = samples[0].t_zone
            prev_u = samples[0].u_heating
            for sample in samples:
                cyc = sample.features[-4:]
                feature_vector = np.asarray(
                    [
                        current_temp,
                        sample.t_outdoor,
                        sample.h_global,
                        sample.u_heating,
                        sample.u_heating - prev_u,
                        *cyc,
                    ],
                    dtype=np.float32,
                )
                normalized = (feature_vector - feature_mean) / feature_std
                features = torch.tensor(normalized, dtype=torch.float32, device=device).unsqueeze(0)
                outputs = model(
                    features,
                    torch.tensor([current_temp], dtype=torch.float32, device=device),
                    torch.tensor([sample.t_outdoor], dtype=torch.float32, device=device),
                    torch.tensor([sample.h_global], dtype=torch.float32, device=device),
                    torch.tensor([sample.u_heating], dtype=torch.float32, device=device),
                    torch.tensor([sample.dt_s], dtype=torch.float32, device=device),
                )
                predicted_next = float(outputs["predicted_next"].cpu().item())
                if not math.isfinite(predicted_next):
                    predicted_next = current_temp
                predicted_next = max(-20.0, min(60.0, predicted_next))
                errors.append(predicted_next - sample.target_next_t_zone)
                current_temp = predicted_next
                prev_u = sample.u_heating

    return {
        "rollout_rmse_degC": _rmse(errors),
        "rollout_mae_degC": _mae(errors),
    }


def evaluate_model(
    model: SingleZonePINN,
    datasets: dict[str, Any],
    config: dict[str, Any],
    device: torch.device,
) -> dict[str, Any]:
    train_cfg = config["training"]
    batch_size = int(train_cfg["batch_size"])
    stats = datasets["stats"]

    val_metrics = _run_epoch(
        model,
        _build_loader(datasets["val_dataset"], batch_size=batch_size, shuffle=False),
        optimizer=None,
        stats=stats,
        device=device,
        lambda_physics=float(train_cfg["lambda_physics"]),
    )
    test_metrics = _run_epoch(
        model,
        _build_loader(datasets["test_dataset"], batch_size=batch_size, shuffle=False),
        optimizer=None,
        stats=stats,
        device=device,
        lambda_physics=float(train_cfg["lambda_physics"]),
    )
    val_metrics.update(evaluate_rollout(model, datasets["val_episodes"], stats, device))
    test_metrics.update(evaluate_rollout(model, datasets["test_episodes"], stats, device))
    return {
        "validation": val_metrics,
        "test": test_metrics,
    }


def train_model(
    model: SingleZonePINN,
    datasets: dict[str, Any],
    config: dict[str, Any],
    artifact_dir: Path,
) -> dict[str, Any]:
    train_cfg = config["training"]
    stats = datasets["stats"]

    device = torch.device(train_cfg.get("device", "cpu"))
    if device.type == "cuda" and not torch.cuda.is_available():
        device = torch.device("cpu")
    model.to(device)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(train_cfg["learning_rate"]),
        weight_decay=float(train_cfg.get("weight_decay", 0.0)),
    )

    train_loader = _build_loader(
        datasets["train_dataset"],
        batch_size=int(train_cfg["batch_size"]),
        shuffle=True,
    )
    val_loader = _build_loader(
        datasets["val_dataset"],
        batch_size=int(train_cfg["batch_size"]),
        shuffle=False,
    )

    best_state: dict[str, torch.Tensor] | None = None
    best_val_loss = float("inf")
    best_epoch = -1
    patience = int(train_cfg["patience"])
    epochs_without_improvement = 0
    history: list[dict[str, float]] = []

    for epoch in range(1, int(train_cfg["epochs"]) + 1):
        train_metrics = _run_epoch(
            model,
            train_loader,
            optimizer=optimizer,
            stats=stats,
            device=device,
            lambda_physics=float(train_cfg["lambda_physics"]),
        )
        val_metrics = _run_epoch(
            model,
            val_loader,
            optimizer=None,
            stats=stats,
            device=device,
            lambda_physics=float(train_cfg["lambda_physics"]),
        )

        epoch_metrics = {
            "epoch": float(epoch),
            "train_loss": train_metrics["loss"],
            "train_rmse_degC": train_metrics["rmse_degC"],
            "val_loss": val_metrics["loss"],
            "val_rmse_degC": val_metrics["rmse_degC"],
        }
        history.append(epoch_metrics)

        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]
            best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        print(
            f"Epoch {epoch:03d} | train_loss={train_metrics['loss']:.4f} | "
            f"val_loss={val_metrics['loss']:.4f} | val_rmse={val_metrics['rmse_degC']:.4f} degC"
        )

        if epochs_without_improvement >= patience:
            print(f"Early stopping at epoch {epoch} (best epoch: {best_epoch}).")
            break

    if best_state is None:
        raise RuntimeError("Training did not produce a valid checkpoint.")

    model.load_state_dict(best_state)
    final_metrics = evaluate_model(model, datasets, config, device)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "normalization": stats.to_dict(),
            "feature_names": datasets["feature_names"],
            "config": config,
        },
        artifact_dir / "best_model.pt",
    )
    with (artifact_dir / "history.json").open("w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2)
    with (artifact_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "best_epoch": best_epoch,
                "best_val_loss": best_val_loss,
                "validation": final_metrics["validation"],
                "test": final_metrics["test"],
                "normalization": stats.to_dict(),
                "physics_parameters": {
                    "ua": float(torch.nn.functional.softplus(model.log_ua).detach().cpu()),
                    "solar_gain": float(torch.nn.functional.softplus(model.log_solar_gain).detach().cpu()),
                    "hvac_gain": float(torch.nn.functional.softplus(model.log_hvac_gain).detach().cpu()),
                    "capacity": float(torch.nn.functional.softplus(model.log_capacity).detach().cpu()),
                },
            },
            handle,
            indent=2,
        )
    with (artifact_dir / "training_config.json").open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)

    return {
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
        "history": history,
        "validation": final_metrics["validation"],
        "test": final_metrics["test"],
        "artifact_dir": str(artifact_dir),
        "device": str(device),
    }