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


def _save_training_checkpoint(checkpoint_path: Path, payload: dict[str, Any]) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = checkpoint_path.with_suffix(".tmp")
    torch.save(payload, tmp_path)
    tmp_path.replace(checkpoint_path)


def _load_training_checkpoint(checkpoint_path: Path, device: torch.device) -> dict[str, Any]:
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    return torch.load(checkpoint_path, map_location=device)


class LossWeighter:
    """Configurable weighting of data vs physics losses.

    Modes:
    - manual: fixed lambda_physics
    - gradient_balance: adapts lambda_physics from gradient-norm ratio
    - uncertainty: learns log-sigma terms (Kendall et al.-style multitask weighting)
    """

    def __init__(self, train_cfg: dict[str, Any], device: torch.device) -> None:
        lw_cfg = train_cfg.get("loss_weighting", {}) or {}
        self.mode = str(lw_cfg.get("mode", "manual")).strip().lower()
        if self.mode not in {"manual", "gradient_balance", "uncertainty"}:
            raise ValueError(f"Unsupported loss_weighting.mode: {self.mode}")

        self.lambda_physics = float(train_cfg.get("lambda_physics", 0.01))
        self._last_lambda = self.lambda_physics

        gb_cfg = lw_cfg.get("gradient_balance", {}) or {}
        self.gb_ema_beta = float(gb_cfg.get("ema_beta", 0.9))
        self.gb_lambda_min = float(gb_cfg.get("lambda_min", 1.0e-6))
        self.gb_lambda_max = float(gb_cfg.get("lambda_max", 1.0e3))
        self.gb_target_ratio = float(gb_cfg.get("target_ratio", 1.0))

        un_cfg = lw_cfg.get("uncertainty", {}) or {}
        init_log_sigma_data = float(un_cfg.get("init_log_sigma_data", 0.0))
        init_log_sigma_physics = float(un_cfg.get("init_log_sigma_physics", 0.0))
        self.log_sigma_data = torch.nn.Parameter(torch.tensor(init_log_sigma_data, device=device))
        self.log_sigma_physics = torch.nn.Parameter(torch.tensor(init_log_sigma_physics, device=device))

        self._eps = 1.0e-12

    def extra_parameters(self) -> list[torch.nn.Parameter]:
        if self.mode == "uncertainty":
            return [self.log_sigma_data, self.log_sigma_physics]
        return []

    def _grad_norm(self, loss: torch.Tensor, params: list[torch.nn.Parameter]) -> torch.Tensor:
        grads = torch.autograd.grad(
            loss,
            params,
            retain_graph=True,
            create_graph=False,
            allow_unused=True,
        )
        total = torch.zeros((), device=loss.device)
        for grad in grads:
            if grad is None:
                continue
            total = total + torch.sum(grad * grad)
        return torch.sqrt(total + self._eps)

    def combine(
        self,
        *,
        data_loss: torch.Tensor,
        physics_loss: torch.Tensor,
        model: SingleZonePINN,
        training: bool,
    ) -> torch.Tensor:
        if self.mode == "manual":
            self._last_lambda = self.lambda_physics
            return data_loss + self.lambda_physics * physics_loss

        if self.mode == "gradient_balance":
            if training:
                ref_params = [param for param in model.network.parameters() if param.requires_grad]
                if ref_params:
                    g_data = self._grad_norm(data_loss, ref_params)
                    g_phys = self._grad_norm(physics_loss, ref_params)
                    ratio = float((g_data / (g_phys + self._eps)).detach().cpu())
                    candidate = ratio * self.gb_target_ratio
                    candidate = max(self.gb_lambda_min, min(self.gb_lambda_max, candidate))
                    self._last_lambda = (
                        self.gb_ema_beta * self._last_lambda + (1.0 - self.gb_ema_beta) * candidate
                    )
            self._last_lambda = max(self.gb_lambda_min, min(self.gb_lambda_max, self._last_lambda))
            return data_loss + self._last_lambda * physics_loss

        # uncertainty mode
        w_data = torch.exp(-2.0 * self.log_sigma_data)
        w_phys = torch.exp(-2.0 * self.log_sigma_physics)
        return w_data * data_loss + w_phys * physics_loss + (self.log_sigma_data + self.log_sigma_physics)

    def metrics(self) -> dict[str, float]:
        out: dict[str, float] = {"loss_weight_mode": self.mode}
        if self.mode in {"manual", "gradient_balance"}:
            out["lambda_physics_eff"] = float(self._last_lambda)
        if self.mode == "uncertainty":
            out["log_sigma_data"] = float(self.log_sigma_data.detach().cpu())
            out["log_sigma_physics"] = float(self.log_sigma_physics.detach().cpu())
            out["weight_data"] = float(torch.exp(-2.0 * self.log_sigma_data).detach().cpu())
            out["weight_physics"] = float(torch.exp(-2.0 * self.log_sigma_physics).detach().cpu())
        return out

    def state_dict(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            "mode": self.mode,
            "lambda_physics": float(self.lambda_physics),
            "last_lambda": float(self._last_lambda),
        }
        if self.mode == "uncertainty":
            state["log_sigma_data"] = float(self.log_sigma_data.detach().cpu())
            state["log_sigma_physics"] = float(self.log_sigma_physics.detach().cpu())
        return state

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self._last_lambda = float(state.get("last_lambda", self.lambda_physics))
        if self.mode == "uncertainty":
            self.log_sigma_data.data = torch.tensor(
                float(state.get("log_sigma_data", float(self.log_sigma_data.detach().cpu()))),
                device=self.log_sigma_data.device,
            )
            self.log_sigma_physics.data = torch.tensor(
                float(state.get("log_sigma_physics", float(self.log_sigma_physics.detach().cpu()))),
                device=self.log_sigma_physics.device,
            )


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


class RolloutWindowDataset(Dataset[dict[str, torch.Tensor]]):
    """Fixed-horizon windows for trajectory-consistent multi-step training."""

    def __init__(self, windows: list[list[Sample]]) -> None:
        if not windows:
            raise ValueError("RolloutWindowDataset requires at least one window.")
        self.windows = windows

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        window = self.windows[index]
        first = window[0]
        t_outdoor_seq = [sample.t_outdoor for sample in window]
        h_global_seq = [sample.h_global for sample in window]
        u_heating_seq = [sample.u_heating for sample in window]
        dt_s_seq = [sample.dt_s for sample in window]
        cyc_seq = [sample.features[-4:] for sample in window]
        target_seq = [sample.target_next_t_zone for sample in window]
        return {
            "init_t_zone": torch.tensor(first.t_zone, dtype=torch.float32),
            "init_prev_u": torch.tensor(first.u_heating, dtype=torch.float32),
            "t_outdoor_seq": torch.tensor(t_outdoor_seq, dtype=torch.float32),
            "h_global_seq": torch.tensor(h_global_seq, dtype=torch.float32),
            "u_heating_seq": torch.tensor(u_heating_seq, dtype=torch.float32),
            "dt_s_seq": torch.tensor(dt_s_seq, dtype=torch.float32),
            "cyc_seq": torch.tensor(cyc_seq, dtype=torch.float32),
            "target_seq": torch.tensor(target_seq, dtype=torch.float32),
        }


def _build_rollout_windows(
    episodes: dict[str, list[Sample]],
    horizon_steps: int,
    max_windows_per_episode: int,
) -> list[list[Sample]]:
    windows: list[list[Sample]] = []
    for samples in episodes.values():
        ordered = sorted(samples, key=lambda sample: sample.time_s)
        if len(ordered) < horizon_steps:
            continue
        max_start = len(ordered) - horizon_steps
        starts = list(range(max_start + 1))
        if max_windows_per_episode > 0 and len(starts) > max_windows_per_episode:
            starts = np.linspace(0, max_start, num=max_windows_per_episode, dtype=int).tolist()
        for start in starts:
            windows.append(ordered[start : start + horizon_steps])
    return windows


def _run_epoch(
    model: SingleZonePINN,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer | None,
    stats: NormalizationStats,
    device: torch.device,
    loss_weighter: LossWeighter,
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
            loss = loss_weighter.combine(
                data_loss=data_loss,
                physics_loss=physics_loss,
                model=model,
                training=training,
            )

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


def _run_rollout_epoch(
    model: SingleZonePINN,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer | None,
    stats: NormalizationStats,
    device: torch.device,
    loss_weighter: LossWeighter,
) -> dict[str, float]:
    mse_loss = nn.MSELoss()
    training = optimizer is not None
    if training:
        model.train()
    else:
        model.eval()

    feature_mean = torch.tensor(stats.feature_mean, dtype=torch.float32, device=device)
    feature_std = torch.tensor(stats.feature_std, dtype=torch.float32, device=device)
    target_mean = torch.tensor(stats.target_mean, dtype=torch.float32, device=device)
    target_std = torch.tensor(stats.target_std, dtype=torch.float32, device=device)

    total_loss = 0.0
    total_data_loss = 0.0
    total_physics_loss = 0.0
    total_count = 0
    errors: list[float] = []

    for batch in loader:
        init_t_zone = batch["init_t_zone"].to(device)
        init_prev_u = batch["init_prev_u"].to(device)
        t_outdoor_seq = batch["t_outdoor_seq"].to(device)
        h_global_seq = batch["h_global_seq"].to(device)
        u_heating_seq = batch["u_heating_seq"].to(device)
        dt_s_seq = batch["dt_s_seq"].to(device)
        cyc_seq = batch["cyc_seq"].to(device)
        target_seq = batch["target_seq"].to(device)

        context = torch.enable_grad() if training else torch.no_grad()
        with context:
            current_temp = init_t_zone
            prev_u = init_prev_u
            predicted_steps: list[torch.Tensor] = []
            correction_steps: list[torch.Tensor] = []
            horizon_steps = target_seq.shape[1]
            for step in range(horizon_steps):
                t_outdoor = t_outdoor_seq[:, step]
                h_global = h_global_seq[:, step]
                u_heating = u_heating_seq[:, step]
                dt_s = dt_s_seq[:, step]
                cyc = cyc_seq[:, step, :]
                delta_u = u_heating - prev_u

                features = torch.stack(
                    [
                        current_temp,
                        t_outdoor,
                        h_global,
                        u_heating,
                        delta_u,
                        cyc[:, 0],
                        cyc[:, 1],
                        cyc[:, 2],
                        cyc[:, 3],
                    ],
                    dim=1,
                )
                normalized_features = (features - feature_mean) / feature_std
                outputs = model(normalized_features, current_temp, t_outdoor, h_global, u_heating, dt_s)
                predicted_next = outputs["predicted_next"]

                predicted_steps.append(predicted_next)
                correction_steps.append(outputs["correction"])
                current_temp = predicted_next
                prev_u = u_heating

            predicted_seq = torch.stack(predicted_steps, dim=1)
            correction_seq = torch.stack(correction_steps, dim=1)

            predicted_norm = (predicted_seq - target_mean) / target_std
            target_norm = (target_seq - target_mean) / target_std
            data_loss = mse_loss(predicted_norm, target_norm)
            physics_loss = torch.mean(correction_seq**2)
            loss = loss_weighter.combine(
                data_loss=data_loss,
                physics_loss=physics_loss,
                model=model,
                training=training,
            )

            if training:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()

        batch_errors = (predicted_seq.detach().cpu() - target_seq.detach().cpu()).reshape(-1).tolist()
        errors.extend(float(value) for value in batch_errors)

        batch_size = target_seq.shape[0]
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
        loss_weighter=LossWeighter(train_cfg, device),
    )
    test_metrics = _run_epoch(
        model,
        _build_loader(datasets["test_dataset"], batch_size=batch_size, shuffle=False),
        optimizer=None,
        stats=stats,
        device=device,
        loss_weighter=LossWeighter(train_cfg, device),
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
    resume_checkpoint: bool = False,
) -> dict[str, Any]:
    train_cfg = config["training"]
    stats = datasets["stats"]

    device = torch.device(train_cfg.get("device", "cpu"))
    if device.type == "cuda" and not torch.cuda.is_available():
        device = torch.device("cpu")
    model.to(device)

    loss_weighter = LossWeighter(train_cfg, device)
    optimizer = torch.optim.Adam(
        list(model.parameters()) + loss_weighter.extra_parameters(),
        lr=float(train_cfg["learning_rate"]),
        weight_decay=float(train_cfg.get("weight_decay", 0.0)),
    )

    artifact_dir.mkdir(parents=True, exist_ok=True)
    latest_checkpoint_path = artifact_dir / "latest_checkpoint.pt"
    checkpoint_every_epochs = int(train_cfg.get("checkpoint_every_epochs", 1))
    resumed_from_checkpoint = False

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

    rollout_cfg = train_cfg.get("rollout_training", {}) or {}
    rollout_enabled = bool(rollout_cfg.get("enabled", False))
    rollout_weight = float(rollout_cfg.get("weight", 1.0))
    rollout_horizon_steps = int(rollout_cfg.get("horizon_steps", 24))
    rollout_batch_size = int(rollout_cfg.get("batch_size", train_cfg["batch_size"]))
    rollout_max_windows_per_episode = int(rollout_cfg.get("max_windows_per_episode", 0))
    train_rollout_loader: DataLoader | None = None
    val_rollout_loader: DataLoader | None = None
    if rollout_enabled:
        train_rollout_windows = _build_rollout_windows(
            datasets["train_episodes"],
            horizon_steps=rollout_horizon_steps,
            max_windows_per_episode=rollout_max_windows_per_episode,
        )
        val_rollout_windows = _build_rollout_windows(
            datasets["val_episodes"],
            horizon_steps=rollout_horizon_steps,
            max_windows_per_episode=rollout_max_windows_per_episode,
        )
        if not train_rollout_windows or not val_rollout_windows:
            rollout_enabled = False
            print(
                "Rollout training requested but no valid windows were found; "
                "continuing with one-step training only."
            )
        else:
            train_rollout_loader = _build_loader(
                RolloutWindowDataset(train_rollout_windows),
                batch_size=rollout_batch_size,
                shuffle=True,
            )
            val_rollout_loader = _build_loader(
                RolloutWindowDataset(val_rollout_windows),
                batch_size=rollout_batch_size,
                shuffle=False,
            )
            print(
                f"Rollout training enabled: horizon={rollout_horizon_steps} steps, "
                f"weight={rollout_weight:.3f}, "
                f"train_windows={len(train_rollout_windows)}, "
                f"val_windows={len(val_rollout_windows)}."
            )

    best_state: dict[str, torch.Tensor] | None = None
    best_val_loss = float("inf")
    best_epoch = -1
    patience = int(train_cfg["patience"])
    epochs_without_improvement = 0
    history: list[dict[str, float]] = []
    start_epoch = 1

    if resume_checkpoint and latest_checkpoint_path.exists():
        checkpoint = _load_training_checkpoint(latest_checkpoint_path, device)
        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        if "loss_weighter_state" in checkpoint:
            loss_weighter.load_state_dict(checkpoint["loss_weighter_state"])
        best_state_raw = checkpoint.get("best_state")
        if isinstance(best_state_raw, dict):
            best_state = {
                str(key): value.detach().cpu().clone()
                for key, value in best_state_raw.items()
                if isinstance(value, torch.Tensor)
            }
        best_val_loss = float(checkpoint.get("best_val_loss", best_val_loss))
        best_epoch = int(checkpoint.get("best_epoch", best_epoch))
        epochs_without_improvement = int(
            checkpoint.get("epochs_without_improvement", epochs_without_improvement)
        )
        raw_history = checkpoint.get("history", [])
        if isinstance(raw_history, list):
            history = [entry for entry in raw_history if isinstance(entry, dict)]
        start_epoch = int(checkpoint.get("epoch", 0)) + 1
        resumed_from_checkpoint = True
        print(
            f"Resumed training checkpoint from epoch {start_epoch - 1} "
            f"(best_epoch={best_epoch}, best_val_loss={best_val_loss:.6f})."
        )

    for epoch in range(start_epoch, int(train_cfg["epochs"]) + 1):
        train_metrics = _run_epoch(
            model,
            train_loader,
            optimizer=optimizer,
            stats=stats,
            device=device,
            loss_weighter=loss_weighter,
        )
        val_metrics = _run_epoch(
            model,
            val_loader,
            optimizer=None,
            stats=stats,
            device=device,
            loss_weighter=loss_weighter,
        )
        train_rollout_metrics: dict[str, float] | None = None
        val_rollout_metrics: dict[str, float] | None = None
        if rollout_enabled and train_rollout_loader is not None and val_rollout_loader is not None:
            train_rollout_metrics = _run_rollout_epoch(
                model,
                train_rollout_loader,
                optimizer=optimizer,
                stats=stats,
                device=device,
                loss_weighter=loss_weighter,
            )
            val_rollout_metrics = _run_rollout_epoch(
                model,
                val_rollout_loader,
                optimizer=None,
                stats=stats,
                device=device,
                loss_weighter=loss_weighter,
            )

        train_objective = train_metrics["loss"]
        val_objective = val_metrics["loss"]
        if train_rollout_metrics is not None:
            train_objective += rollout_weight * train_rollout_metrics["loss"]
        if val_rollout_metrics is not None:
            val_objective += rollout_weight * val_rollout_metrics["loss"]

        epoch_metrics = {
            "epoch": float(epoch),
            "train_loss": train_objective,
            "train_step_loss": train_metrics["loss"],
            "train_rmse_degC": train_metrics["rmse_degC"],
            "val_loss": val_objective,
            "val_step_loss": val_metrics["loss"],
            "val_rmse_degC": val_metrics["rmse_degC"],
        }
        if train_rollout_metrics is not None and val_rollout_metrics is not None:
            epoch_metrics["train_rollout_loss"] = train_rollout_metrics["loss"]
            epoch_metrics["train_rollout_rmse_degC"] = train_rollout_metrics["rmse_degC"]
            epoch_metrics["val_rollout_loss"] = val_rollout_metrics["loss"]
            epoch_metrics["val_rollout_rmse_degC"] = val_rollout_metrics["rmse_degC"]
        epoch_metrics.update(loss_weighter.metrics())
        history.append(epoch_metrics)

        if val_objective < best_val_loss:
            best_val_loss = val_objective
            best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        summary = (
            f"Epoch {epoch:03d} | train_loss={train_objective:.4f} "
            f"(step={train_metrics['loss']:.4f}) | val_loss={val_objective:.4f} "
            f"(step={val_metrics['loss']:.4f}) | val_rmse={val_metrics['rmse_degC']:.4f} degC"
        )
        if val_rollout_metrics is not None:
            summary += f" | val_rollout_rmse={val_rollout_metrics['rmse_degC']:.4f} degC"
        summary += f" | weight_mode={loss_weighter.mode}"
        print(summary)

        if checkpoint_every_epochs > 0 and (epoch % checkpoint_every_epochs == 0):
            _save_training_checkpoint(
                latest_checkpoint_path,
                {
                    "epoch": int(epoch),
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "loss_weighter_state": loss_weighter.state_dict(),
                    "best_state": best_state,
                    "best_val_loss": float(best_val_loss),
                    "best_epoch": int(best_epoch),
                    "epochs_without_improvement": int(epochs_without_improvement),
                    "history": history,
                    "config": config,
                },
            )

        if epochs_without_improvement >= patience:
            print(f"Early stopping at epoch {epoch} (best epoch: {best_epoch}).")
            break

    if best_state is None:
        raise RuntimeError("Training did not produce a valid checkpoint.")

    model.load_state_dict(best_state)
    final_metrics = evaluate_model(model, datasets, config, device)

    physics_parameters = {
        "ua": float(torch.nn.functional.softplus(model.log_ua).detach().cpu()),
        "solar_gain": float(torch.nn.functional.softplus(model.log_solar_gain).detach().cpu()),
        "hvac_gain": float(torch.nn.functional.softplus(model.log_hvac_gain).detach().cpu()),
        "capacity": float(torch.nn.functional.softplus(model.log_capacity).detach().cpu()),
    }

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "normalization": stats.to_dict(),
            "feature_names": datasets["feature_names"],
            "config": config,
            "physics_parameters": physics_parameters,
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
                    "ua": physics_parameters["ua"],
                    "solar_gain": physics_parameters["solar_gain"],
                    "hvac_gain": physics_parameters["hvac_gain"],
                    "capacity": physics_parameters["capacity"],
                },
                "loss_weighting": loss_weighter.metrics(),
                    "rollout_training": {
                        "enabled": rollout_enabled,
                        "weight": rollout_weight,
                        "horizon_steps": rollout_horizon_steps,
                        "batch_size": rollout_batch_size,
                        "max_windows_per_episode": rollout_max_windows_per_episode,
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
        "resumed_from_checkpoint": resumed_from_checkpoint,
        "latest_checkpoint": str(latest_checkpoint_path),
    }
