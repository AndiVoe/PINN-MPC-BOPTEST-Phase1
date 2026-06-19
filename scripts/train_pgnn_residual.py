#!/usr/bin/env python3
"""
Train PGNN residual corrector with frozen RC physics and 48-step rollout.

Architecture:
  1. Build model with RC-calibrated physics parameters (FROZEN)
  2. Train ONLY the neural network on 48-step rollout loss
  3. Physics stays at RC values — the NN learns residuals

This enables the 3-way comparison:
  RC (independent calibration)  vs  PGNN (RC physics + NN corrector)  vs  PGNN-no-corr (RC physics only)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from pinn_model import build_datasets, load_training_config, SingleZonePINN
from pinn_model.training import set_seed


class RolloutDataset(torch.utils.data.Dataset):
    def __init__(self, episodes: dict[str, list], horizon: int, stride: int = 12) -> None:
        self.horizon = horizon
        self.episodes_data: list[dict[str, torch.Tensor]] = []
        self.windows: list[tuple[int, int]] = []

        for ep_idx, (ep_id, samples) in enumerate(episodes.items()):
            ordered = sorted(samples, key=lambda s: s.time_s)
            if len(ordered) < horizon:
                continue

            t_zone = torch.tensor([s.t_zone for s in ordered], dtype=torch.float32)
            u_heating = torch.tensor([s.u_heating for s in ordered], dtype=torch.float32)
            t_outdoor = torch.tensor([s.t_outdoor for s in ordered], dtype=torch.float32)
            h_global = torch.tensor([s.h_global for s in ordered], dtype=torch.float32)
            dt_s = torch.tensor([s.dt_s for s in ordered], dtype=torch.float32)
            occupied = torch.tensor([s.occupied for s in ordered], dtype=torch.float32)
            cyc = torch.tensor([s.features[-4:] for s in ordered], dtype=torch.float32)
            target = torch.tensor([s.target_next_t_zone for s in ordered], dtype=torch.float32)

            self.episodes_data.append({
                "t_zone": t_zone, "u_heating": u_heating, "t_outdoor": t_outdoor,
                "h_global": h_global, "dt_s": dt_s, "occupied": occupied,
                "cyc": cyc, "target": target,
            })

            max_start = len(ordered) - horizon
            for start in range(0, max_start + 1, stride):
                self.windows.append((ep_idx, start))

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        ep_idx, start = self.windows[idx]
        ep = self.episodes_data[ep_idx]
        h = self.horizon
        return {
            "init_t_zone": ep["t_zone"][start],
            "init_prev_u": ep["u_heating"][start],
            "t_outdoor_seq": ep["t_outdoor"][start: start + h],
            "h_global_seq": ep["h_global"][start: start + h],
            "u_heating_seq": ep["u_heating"][start: start + h],
            "dt_s_seq": ep["dt_s"][start: start + h],
            "occupied_seq": ep["occupied"][start: start + h],
            "cyc_seq": ep["cyc"][start: start + h],
            "target_seq": ep["target"][start: start + h],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train PGNN residual corrector (frozen RC physics, 48-step rollout).")
    parser.add_argument("--config", default="configs/pinn_phase1_excited.yaml")
    parser.add_argument("--rc-ckpt", default="artifacts/rc_baseline_calibrated/rc_calibrated_checkpoint.pt")
    parser.add_argument("--artifact-dir", default="artifacts/pinn_residual_corrector")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--rollout-horizon", type=int, default=48)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    root = ROOT
    config = load_training_config(root / args.config)
    set_seed(int(args.seed))
    device = torch.device(args.device if torch.cuda.is_available() or args.device == "cpu" else "cpu")

    datasets = build_datasets(config, root)
    stats = datasets["stats"]
    feature_names = datasets["feature_names"]
    feature_dim = len(feature_names)

    # ---- Load RC physics ----
    rc_ckpt = torch.load(root / args.rc_ckpt, map_location="cpu", weights_only=False)
    rc_phys = rc_ckpt["physics_parameters"]

    # ---- Build model with RC physics, freeze all physics params ----
    model_cfg = config["model"]
    model = SingleZonePINN(
        input_dim=feature_dim,
        hidden_dim=int(model_cfg["hidden_dim"]),
        depth=int(model_cfg["depth"]),
        dropout=float(model_cfg.get("dropout", 0.0)),
    )

    # Set physics params to RC-calibrated values (inverse softplus)
    def _softplus_inverse(y: float) -> torch.Tensor:
        if y > 20.0:
            return torch.tensor(y, dtype=torch.float32)
        return torch.log(torch.exp(torch.tensor(y, dtype=torch.float32)) - 1.0 + 1e-8)

    with torch.no_grad():
        model.log_ua.data = _softplus_inverse(rc_phys["ua"])
        model.log_solar_gain.data = _softplus_inverse(rc_phys["solar_gain"])
        model.log_hvac_gain.data = _softplus_inverse(rc_phys["hvac_gain"])
        model.log_capacity.data = _softplus_inverse(rc_phys["capacity"])

    # Freeze ALL physics parameters
    for name, param in model.named_parameters():
        param.requires_grad = False
    # Unfreeze only NN weights
    for param in model.network.parameters():
        param.requires_grad = True

    print("=== PGNN: Frozen RC physics, training NN only ===")
    with torch.no_grad():
        for name, param in model.named_parameters():
            if not param.requires_grad:
                if "log_" in name:
                    val = float(nn.functional.softplus(param))
                    if "capacity" in name:
                        print(f"  {name}: {val:.4f} kWh/K [FROZEN]")
                    else:
                        print(f"  {name}: {val:.4f} kW/K = {val*1000:.2f} W/K [FROZEN]")

    trainable = [n for n, p in model.named_parameters() if p.requires_grad]
    n_nn = sum(p.numel() for p in model.network.parameters())
    print(f"  Trainable: {len(trainable)} tensors (NN only, {n_nn} params)")

    model.to(device)

    # ---- Rollout training setup ----
    horizon = int(args.rollout_horizon)
    print(f"\nUsing {horizon}-step rollout")

    train_dataset = RolloutDataset(datasets["train_episodes"], horizon=horizon, stride=12)
    val_dataset = RolloutDataset(datasets["val_episodes"], horizon=horizon, stride=12)

    train_loader = DataLoader(train_dataset, batch_size=int(args.batch_size), shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=int(args.batch_size), shuffle=False)

    optimizer = torch.optim.Adam(model.network.parameters(), lr=float(args.lr))
    mse = nn.MSELoss()

    f_mean = torch.tensor(stats.feature_mean, dtype=torch.float32, device=device)
    f_std = torch.tensor(stats.feature_std, dtype=torch.float32, device=device)
    t_mean = torch.tensor(stats.target_mean, dtype=torch.float32, device=device)
    t_std = torch.tensor(stats.target_std, dtype=torch.float32, device=device)

    best_val_loss = float("inf")
    best_state = None
    artifact_dir = root / args.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)

    print(f"Training NN corrector ({args.epochs} epochs)...")
    for epoch in range(1, args.epochs + 1):
        # --- Train ---
        model.train()
        train_loss = 0.0
        train_count = 0

        for batch in train_loader:
            init_t_zone = batch["init_t_zone"].to(device)
            init_prev_u = batch["init_prev_u"].to(device)
            t_out_seq = batch["t_outdoor_seq"].to(device)
            h_glob_seq = batch["h_global_seq"].to(device)
            u_heat_seq = batch["u_heating_seq"].to(device)
            dt_s_seq = batch["dt_s_seq"].to(device)
            occ_seq = batch["occupied_seq"].to(device)
            cyc_seq = batch["cyc_seq"].to(device)
            target_seq = batch["target_seq"].to(device)

            optimizer.zero_grad()

            current_temp = init_t_zone
            prev_u = init_prev_u
            predicted_steps = []
            h = target_seq.shape[1]
            for step in range(h):
                t_out = t_out_seq[:, step]
                h_glob = h_glob_seq[:, step]
                u_heat = u_heat_seq[:, step]
                dt_s = dt_s_seq[:, step]
                occ = occ_seq[:, step]
                cyc = cyc_seq[:, step, :]
                delta_u = u_heat - prev_u

                features = torch.stack([
                    current_temp, t_out, h_glob, u_heat, delta_u, occ,
                    cyc[:, 0], cyc[:, 1], cyc[:, 2], cyc[:, 3],
                ], dim=1)
                features_norm = (features - f_mean) / f_std

                outputs = model(features_norm, current_temp, t_out, h_glob, u_heat, dt_s)
                predicted_steps.append(outputs["predicted_next"])
                current_temp = outputs["predicted_next"]
                prev_u = u_heat

            predicted_seq = torch.stack(predicted_steps, dim=1)
            pred_norm = (predicted_seq - t_mean) / t_std
            target_norm = (target_seq - t_mean) / t_std
            loss = mse(pred_norm, target_norm)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.network.parameters(), max_norm=1.0)
            optimizer.step()

            bs = target_seq.shape[0]
            train_loss += float(loss.detach().cpu()) * bs
            train_count += bs

        # --- Validate ---
        model.eval()
        val_loss = 0.0
        val_count = 0
        with torch.no_grad():
            for batch in val_loader:
                init_t_zone = batch["init_t_zone"].to(device)
                init_prev_u = batch["init_prev_u"].to(device)
                t_out_seq = batch["t_outdoor_seq"].to(device)
                h_glob_seq = batch["h_global_seq"].to(device)
                u_heat_seq = batch["u_heating_seq"].to(device)
                dt_s_seq = batch["dt_s_seq"].to(device)
                occ_seq = batch["occupied_seq"].to(device)
                cyc_seq = batch["cyc_seq"].to(device)
                target_seq = batch["target_seq"].to(device)

                current_temp = init_t_zone
                prev_u = init_prev_u
                predicted_steps = []
                h = target_seq.shape[1]
                for step in range(h):
                    t_out = t_out_seq[:, step]
                    h_glob = h_glob_seq[:, step]
                    u_heat = u_heat_seq[:, step]
                    dt_s = dt_s_seq[:, step]
                    occ = occ_seq[:, step]
                    cyc = cyc_seq[:, step, :]
                    delta_u = u_heat - prev_u

                    features = torch.stack([
                        current_temp, t_out, h_glob, u_heat, delta_u, occ,
                        cyc[:, 0], cyc[:, 1], cyc[:, 2], cyc[:, 3],
                    ], dim=1)
                    features_norm = (features - f_mean) / f_std

                    outputs = model(features_norm, current_temp, t_out, h_glob, u_heat, dt_s)
                    predicted_steps.append(outputs["predicted_next"])
                    current_temp = outputs["predicted_next"]
                    prev_u = u_heat

                predicted_seq = torch.stack(predicted_steps, dim=1)
                pred_norm = (predicted_seq - t_mean) / t_std
                target_norm = (target_seq - t_mean) / t_std
                data_loss = mse(pred_norm, target_norm)
                val_loss += float(data_loss.detach().cpu()) * target_seq.shape[0]
                val_count += target_seq.shape[0]

        avg_val_loss = val_loss / max(val_count, 1)
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

        if epoch % 10 == 0 or epoch == args.epochs:
            print(f"  Epoch {epoch:3d}/{args.epochs} | train={train_loss/max(train_count,1):.6f} | val={avg_val_loss:.6f}")

    # ---- Save best checkpoint ----
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()

    # Verify physics unchanged from RC
    physics_params = {}
    with torch.no_grad():
        for k in ["ua", "solar_gain", "hvac_gain", "capacity"]:
            log_name = f"log_{k}"
            physics_params[k] = float(nn.functional.softplus(getattr(model, log_name)).detach().cpu())

    print(f"\n=== Physics params (should match RC exactly) ===")
    for k, v in physics_params.items():
        rc_v = rc_phys[k]
        match = "✓" if abs(v - rc_v) < 1e-6 else "✗ MISMATCH"
        print(f"  {k}: {v:.6f} (RC: {rc_v:.6f}) {match}")

    torch.save({
        "model_state_dict": model.state_dict(),
        "normalization": stats.to_dict(),
        "feature_names": feature_names,
        "config": config,
        "physics_parameters": physics_params,
        "rc_source_physics": rc_phys,
        "meta": {"type": "pgnn_frozen_physics_rollout", "horizon": horizon, "physics_frozen": True},
    }, artifact_dir / "best_model.pt")

    print(f"\nCheckpoint saved to: {artifact_dir / 'best_model.pt'}")


if __name__ == "__main__":
    main()