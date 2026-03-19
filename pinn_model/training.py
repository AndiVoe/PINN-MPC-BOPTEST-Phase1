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

        epoch_metrics = {
            "epoch": float(epoch),
            "train_loss": train_metrics["loss"],
            "train_rmse_degC": train_metrics["rmse_degC"],
            "val_loss": val_metrics["loss"],
            "val_rmse_degC": val_metrics["rmse_degC"],
        }
        epoch_metrics.update(loss_weighter.metrics())
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
            f"val_loss={val_metrics['loss']:.4f} | val_rmse={val_metrics['rmse_degC']:.4f} degC | "
            f"weight_mode={loss_weighter.mode}"
        )

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
                "loss_weighting": loss_weighter.metrics(),
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
