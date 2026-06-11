#!/usr/bin/env python3
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

from pinn_model import build_datasets, load_training_config, SingleZonePINN, evaluate_model
from pinn_model.training import set_seed


def zero_network(module: nn.Module) -> None:
	for p in module.parameters():
		p.data.zero_()
		p.requires_grad = False


class FastRolloutDataset(torch.utils.data.Dataset):
	def __init__(self, episodes: dict[str, list], horizon: int, stride: int = 12) -> None:
		self.horizon = horizon
		self.episodes_data: list[dict[str, torch.Tensor]] = []
		self.windows: list[tuple[int, int]] = []

		for ep_idx, (ep_id, samples) in enumerate(episodes.items()):
			ordered = sorted(samples, key=lambda s: s.time_s)
			if len(ordered) < horizon:
				continue

			# Extract sequences as PyTorch tensors once
			t_zone = torch.tensor([s.t_zone for s in ordered], dtype=torch.float32)
			u_heating = torch.tensor([s.u_heating for s in ordered], dtype=torch.float32)
			t_outdoor = torch.tensor([s.t_outdoor for s in ordered], dtype=torch.float32)
			h_global = torch.tensor([s.h_global for s in ordered], dtype=torch.float32)
			dt_s = torch.tensor([s.dt_s for s in ordered], dtype=torch.float32)
			occupied = torch.tensor([s.occupied for s in ordered], dtype=torch.float32)
			cyc = torch.tensor([s.features[-4:] for s in ordered], dtype=torch.float32)
			target = torch.tensor([s.target_next_t_zone for s in ordered], dtype=torch.float32)

			self.episodes_data.append({
				"t_zone": t_zone,
				"u_heating": u_heating,
				"t_outdoor": t_outdoor,
				"h_global": h_global,
				"dt_s": dt_s,
				"occupied": occupied,
				"cyc": cyc,
				"target": target,
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
			"t_outdoor_seq": ep["t_outdoor"][start : start + h],
			"h_global_seq": ep["h_global"][start : start + h],
			"u_heating_seq": ep["u_heating"][start : start + h],
			"dt_s_seq": ep["dt_s"][start : start + h],
			"occupied_seq": ep["occupied"][start : start + h],
			"cyc_seq": ep["cyc"][start : start + h],
			"target_seq": ep["target"][start : start + h],
		}


def main() -> None:
	parser = argparse.ArgumentParser(description="Calibrate 1R1C RC baseline parameters on Phase 1 dataset.")
	parser.add_argument("--config", default="configs/pinn_phase1_improved.yaml")
	parser.add_argument("--artifact-dir", default="artifacts/rc_baseline_calibrated")
	parser.add_argument("--epochs", type=int, default=100) # Rollout is very fast to converge; fewer epochs needed
	parser.add_argument("--lr", type=float, default=0.01)
	parser.add_argument("--batch-size", type=int, default=64)
	# Default to 0 to avoid automatic L-BFGS polishing (can be enabled manually)
	parser.add_argument("--lbfgs-steps", type=int, default=0)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument("--device", default="cpu")
	parser.add_argument("--rollout-enabled", action="store_true", default=True, help="Use multi-step rollout calibration")
	parser.add_argument("--rollout-horizon", type=int, default=48, help="Rollout horizon steps")
	args = parser.parse_args()

	root = ROOT
	config = load_training_config(root / args.config)
	set_seed(int(args.seed))

	datasets = build_datasets(config, root)
	stats = datasets["stats"]

	device = torch.device(args.device if torch.cuda.is_available() or args.device == "cpu" else "cpu")

	# Instantiate PINN but force zero neural correction so we calibrate pure physics params.
	model = SingleZonePINN(input_dim=len(datasets["feature_names"]), hidden_dim=16, depth=1)
	# Replace network with a zero-output module and freeze it.
	model.network = nn.Sequential(nn.Linear(len(datasets["feature_names"]), 1))
	zero_network(model.network)

	# Enable grad only for physics parameters
	for name, param in model.named_parameters():
		param.requires_grad = False
	for pname in ("log_ua", "log_solar_gain", "log_hvac_power_max", "log_capacity"):
		getattr(model, pname).requires_grad_(True)

	model.to(device)

	params = [getattr(model, pname) for pname in ("log_ua", "log_solar_gain", "log_hvac_power_max", "log_capacity")]
	optimizer = torch.optim.Adam(params, lr=float(args.lr))
	mse = torch.nn.MSELoss()

	artifact_dir = Path(args.artifact_dir)
	artifact_dir.mkdir(parents=True, exist_ok=True)

	feature_mean = torch.tensor(stats.feature_mean, dtype=torch.float32, device=device)
	feature_std = torch.tensor(stats.feature_std, dtype=torch.float32, device=device)
	target_mean = torch.tensor(stats.target_mean, dtype=torch.float32, device=device)
	target_std = torch.tensor(stats.target_std, dtype=torch.float32, device=device)

	if args.rollout_enabled:
		print(f"Multi-step rollout calibration enabled: horizon = {args.rollout_horizon} steps.")
		train_dataset = FastRolloutDataset(datasets["train_episodes"], horizon=int(args.rollout_horizon), stride=12)
		train_loader = DataLoader(train_dataset, batch_size=int(args.batch_size), shuffle=True)
	else:
		print("1-step prediction calibration enabled.")
		train_loader = DataLoader(datasets["train_dataset"], batch_size=int(args.batch_size), shuffle=True)

	for epoch in range(1, args.epochs + 1):
		model.train()
		total_loss = 0.0
		total_count = 0
		for batch in train_loader:
			optimizer.zero_grad()
			if args.rollout_enabled:
				init_t_zone = batch["init_t_zone"].to(device)
				init_prev_u = batch["init_prev_u"].to(device)
				t_outdoor_seq = batch["t_outdoor_seq"].to(device)
				h_global_seq = batch["h_global_seq"].to(device)
				u_heating_seq = batch["u_heating_seq"].to(device)
				dt_s_seq = batch["dt_s_seq"].to(device)
				occupied_seq = batch["occupied_seq"].to(device)
				cyc_seq = batch["cyc_seq"].to(device)
				target_seq = batch["target_seq"].to(device)

				current_temp = init_t_zone
				prev_u = init_prev_u
				predicted_steps: list[torch.Tensor] = []
				horizon_steps = target_seq.shape[1]
				for step in range(horizon_steps):
					t_outdoor = t_outdoor_seq[:, step]
					h_global = h_global_seq[:, step]
					u_heating = u_heating_seq[:, step]
					dt_s = dt_s_seq[:, step]
					occupied = occupied_seq[:, step]
					cyc = cyc_seq[:, step, :]
					delta_u = u_heating - prev_u

					features = torch.stack(
						[
							current_temp,
							t_outdoor,
							h_global,
							u_heating,
							delta_u,
							occupied,
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
					current_temp = predicted_next
					prev_u = u_heating

				predicted_seq = torch.stack(predicted_steps, dim=1)
				predicted_norm = (predicted_seq - target_mean) / target_std
				target_norm = (target_seq - target_mean) / target_std
				loss = mse(predicted_norm, target_norm)
				bs = target_seq.shape[0]
			else:
				features = batch["features"].to(device)
				target = batch["target"].to(device)
				t_zone = batch["t_zone"].to(device)
				t_outdoor = batch["t_outdoor"].to(device)
				h_global = batch["h_global"].to(device)
				u_heating = batch["u_heating"].to(device)
				dt_s = batch["dt_s"].to(device)

				outputs = model(features, t_zone, t_outdoor, h_global, u_heating, dt_s)
				predicted_norm = (outputs["predicted_next"] - target_mean) / target_std
				loss = mse(predicted_norm, target)
				bs = target.shape[0]

			loss.backward()
			torch.nn.utils.clip_grad_norm_(params, max_norm=1.0)
			optimizer.step()

			total_loss += float(loss.detach().cpu()) * bs
			total_count += bs

		if epoch % 10 == 0 or epoch == args.epochs:
			print(f"Epoch {epoch}/{args.epochs} | train_loss={total_loss/max(total_count,1):.6f}")

	# Optional L-BFGS polishing
	if int(args.lbfgs_steps) > 0:
		lbfgs_opt = torch.optim.LBFGS(params, lr=0.1, max_iter=int(args.lbfgs_steps))

		def closure():
			lbfgs_opt.zero_grad()
			total = 0.0
			count = 0
			for batch in train_loader:
				if args.rollout_enabled:
					init_t_zone = batch["init_t_zone"].to(device)
					init_prev_u = batch["init_prev_u"].to(device)
					t_outdoor_seq = batch["t_outdoor_seq"].to(device)
					h_global_seq = batch["h_global_seq"].to(device)
					u_heating_seq = batch["u_heating_seq"].to(device)
					dt_s_seq = batch["dt_s_seq"].to(device)
					occupied_seq = batch["occupied_seq"].to(device)
					cyc_seq = batch["cyc_seq"].to(device)
					target_seq = batch["target_seq"].to(device)

					current_temp = init_t_zone
					prev_u = init_prev_u
					predicted_steps: list[torch.Tensor] = []
					horizon_steps = target_seq.shape[1]
					for step in range(horizon_steps):
						t_outdoor = t_outdoor_seq[:, step]
						h_global = h_global_seq[:, step]
						u_heating = u_heating_seq[:, step]
						dt_s = dt_s_seq[:, step]
						occupied = occupied_seq[:, step]
						cyc = cyc_seq[:, step, :]
						delta_u = u_heating - prev_u

						features = torch.stack(
							[
								current_temp,
								t_outdoor,
								h_global,
								u_heating,
								delta_u,
								occupied,
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
						current_temp = predicted_next
						prev_u = u_heating

					predicted_seq = torch.stack(predicted_steps, dim=1)
					predicted_norm = (predicted_seq - target_mean) / target_std
					target_norm = (target_seq - target_mean) / target_std
					loss = mse(predicted_norm, target_norm)
					bs = target_seq.shape[0]
				else:
					features = batch["features"].to(device)
					target = batch["target"].to(device)
					t_zone = batch["t_zone"].to(device)
					t_outdoor = batch["t_outdoor"].to(device)
					h_global = batch["h_global"].to(device)
					u_heating = batch["u_heating"].to(device)
					dt_s = batch["dt_s"].to(device)
					outputs = model(features, t_zone, t_outdoor, h_global, u_heating, dt_s)
					predicted_norm = (outputs["predicted_next"] - target_mean) / target_std
					loss = mse(predicted_norm, target)
					bs = target.shape[0]

				loss.backward()
				total += float(loss.detach().cpu()) * bs
				count += bs
			return torch.tensor(total / max(count, 1), device=device)

		print("Starting L-BFGS polish...")
		lbfgs_opt.step(closure)

	# Evaluate and save
	model.eval()
	results = evaluate_model(model, datasets, config, device)

	physics_parameters = {
		"ua": float(torch.exp(model.log_ua).detach().cpu()),
		"solar_gain": float(torch.exp(model.log_solar_gain).detach().cpu()),
		"hvac_power_max": float(torch.exp(model.log_hvac_power_max).detach().cpu()),
		"capacity": float(torch.exp(model.log_capacity).detach().cpu()),
	}

	torch.save(
		{
			"model_state_dict": model.state_dict(),
			"normalization": stats.to_dict(),
			"feature_names": datasets["feature_names"],
			"config": config,
			"physics_parameters": physics_parameters,
			"meta": {"type": "rc_baseline_calibrated"},
		},
		artifact_dir / "rc_calibrated_checkpoint.pt",
	)

	with (artifact_dir / "calibration_summary.json").open("w", encoding="utf-8") as handle:
		json.dump(
			{
				"train": {"n_samples": len(datasets["train_dataset"])},
				"validation": {"n_samples": len(datasets["val_dataset"])},
				"test": {"n_samples": len(datasets["test_dataset"])},
				"physics_parameters": physics_parameters,
				"calibration": {"config": str(root / args.config), "epochs": args.epochs, "lr": args.lr},
				"results": results,
			},
			handle,
			indent=2,
		)

	with (artifact_dir / "metrics.json").open("w", encoding="utf-8") as handle:
		json.dump({"validation": results["validation"], "test": results["test"], "physics_parameters": physics_parameters}, handle, indent=2)

	print("Calibration complete. Artifacts written to:", artifact_dir)


if __name__ == "__main__":
	main()
