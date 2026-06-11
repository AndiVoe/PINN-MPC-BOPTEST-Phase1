#!/usr/bin/env python3
import argparse
import json
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pinn_model import load_training_config, SingleZonePINN

def load_checkpoint(ckpt_path):
    ckpt_path = Path(ckpt_path)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found at: {ckpt_path}")
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    return ckpt

def get_cyclical_features(time_s: int) -> list[float]:
    SECONDS_PER_DAY = 24 * 3600
    SECONDS_PER_YEAR = 365 * SECONDS_PER_DAY
    day_phase = 2.0 * math.pi * ((time_s % SECONDS_PER_DAY) / SECONDS_PER_DAY)
    year_phase = 2.0 * math.pi * ((time_s % SECONDS_PER_YEAR) / SECONDS_PER_YEAR)
    return [
        math.sin(day_phase),
        math.cos(day_phase),
        math.sin(year_phase),
        math.cos(year_phase),
    ]

def evaluate_open_loop(episode_json_path, pinn_ckpt_path, rc_ckpt_path, output_csv_path):
    episode_json_path = Path(episode_json_path)
    pinn_ckpt_path = Path(pinn_ckpt_path)
    rc_ckpt_path = Path(rc_ckpt_path)
    output_csv_path = Path(output_csv_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n--- Loading Episode Data: {episode_json_path.name} ---")
    with open(episode_json_path, "r", encoding="utf-8") as f:
        episode_data = json.load(f)
    records = episode_data["records"]
    n_steps = len(records)
    print(f"Loaded {n_steps} steps.")

    # Load normalizations and configurations
    pinn_ckpt = load_checkpoint(pinn_ckpt_path)
    rc_ckpt = load_checkpoint(rc_ckpt_path)

    pinn_config = pinn_ckpt["config"]
    pinn_stats = pinn_ckpt["normalization"]
    pinn_feature_names = pinn_ckpt["feature_names"]

    rc_stats = rc_ckpt["normalization"]

    # Reconstruct PINN Model
    pinn_model = SingleZonePINN(
        input_dim=len(pinn_feature_names),
        hidden_dim=pinn_config["model"]["hidden_dim"],
        depth=pinn_config["model"]["depth"],
        dropout=pinn_config["model"].get("dropout", 0.0)
    )
    pinn_model.load_state_dict(pinn_ckpt["model_state_dict"])
    pinn_model.eval()

    # Reconstruct RC Model
    rc_model = SingleZonePINN(
        input_dim=len(pinn_feature_names),
        hidden_dim=16,
        depth=1
    )
    # Reconstruct with zero correction network
    rc_model.network = torch.nn.Sequential(torch.nn.Linear(len(pinn_feature_names), 1))
    for p in rc_model.network.parameters():
        p.data.zero_()
    rc_model.load_state_dict(rc_ckpt["model_state_dict"])
    rc_model.eval()

    print("\n--- Physical Parameters Audit ---")
    with torch.no_grad():
        print(f"PINN UA:       {float(torch.exp(pinn_model.log_ua)):.4f} W/K")
        print(f"PINN Solar:    {float(torch.exp(pinn_model.log_solar_gain)):.4f}")
        print(f"PINN P_max:    {float(torch.exp(pinn_model.log_hvac_power_max)):.2f} W")
        print(f"PINN Capacity: {float(torch.exp(pinn_model.log_capacity)):.4f} kWh/K")
        
        print(f"RC UA:         {float(torch.exp(rc_model.log_ua)):.4f} W/K")
        print(f"RC Solar:      {float(torch.exp(rc_model.log_solar_gain)):.4f}")
        print(f"RC P_max:      {float(torch.exp(rc_model.log_hvac_power_max)):.2f} W")
        print(f"RC Capacity:   {float(torch.exp(rc_model.log_capacity)):.4f} kWh/K")

    # Initial states
    t0 = float(records[0]["T_zone_degC"])
    t_rc = t0
    t_pinn = t0

    # Normalization statistics
    f_mean = torch.tensor(pinn_stats["feature_mean"], dtype=torch.float32)
    f_std = torch.tensor(pinn_stats["feature_std"], dtype=torch.float32)
    t_mean = torch.tensor(pinn_stats["target_mean"], dtype=torch.float32)
    t_std = torch.tensor(pinn_stats["target_std"], dtype=torch.float32)

    # Rollout lists
    times = []
    t_actuals = []
    t_pred_rcs = []
    t_pred_pinns = []
    u_heatings = []
    t_outdoors = []
    h_globals = []
    corrections = []

    print("\nSimulating surrogates in open loop...")
    for k in range(n_steps - 1):
        curr_rec = records[k]
        next_rec = records[k+1]

        time_s = int(curr_rec["time_s"])
        dt_s = float(next_rec["time_s"] - time_s)
        t_act = float(curr_rec["T_zone_degC"])
        t_out = float(curr_rec["T_outdoor_degC"])
        h_glob = float(curr_rec["H_global_Wm2"])
        u_heat = float(curr_rec["u_heating"])
        if u_heat > 200.0:
            u_heat -= 273.15  # Decode Kelvin setpoint if necessary
        next_u_heat = float(next_rec["u_heating"])
        if next_u_heat > 200.0:
            next_u_heat -= 273.15

        cyc = get_cyclical_features(time_s)
        occupied = float(curr_rec.get("occupied", False))

        times.append(time_s)
        t_actuals.append(t_act)
        t_pred_rcs.append(t_rc)
        t_pred_pinns.append(t_pinn)
        u_heatings.append(u_heat)
        t_outdoors.append(t_out)
        h_globals.append(h_glob)

        # ----------------------------------------------------------------------
        # RC Model Transition (State updates strictly from previous prediction)
        # ----------------------------------------------------------------------
        rc_features = [
            t_rc,
            t_out,
            h_glob,
            u_heat,
            next_u_heat - u_heat,
            occupied,
            *cyc
        ]
        rc_feat_tensor = torch.tensor(rc_features, dtype=torch.float32)
        rc_feat_norm = (rc_feat_tensor - f_mean) / f_std

        with torch.no_grad():
            t_rc_tensor = torch.tensor([t_rc], dtype=torch.float32)
            t_out_tensor = torch.tensor([t_out], dtype=torch.float32)
            h_glob_tensor = torch.tensor([h_glob], dtype=torch.float32)
            u_heat_tensor = torch.tensor([u_heat], dtype=torch.float32)
            dt_tensor = torch.tensor([dt_s], dtype=torch.float32)

            rc_out = rc_model(
                rc_feat_norm.unsqueeze(0),
                t_rc_tensor,
                t_out_tensor,
                h_glob_tensor,
                u_heat_tensor,
                dt_tensor
            )
            t_rc = float(rc_out["predicted_next"].item())

        # ----------------------------------------------------------------------
        # PINN Model Transition (State updates strictly from previous prediction)
        # ----------------------------------------------------------------------
        # Feature vector using predicted t_pinn
        pinn_features = [
            t_pinn,
            t_out,
            h_glob,
            u_heat,
            next_u_heat - u_heat,
            occupied,
            *cyc
        ]
        
        pinn_feat_tensor = torch.tensor(pinn_features, dtype=torch.float32)
        pinn_feat_norm = (pinn_feat_tensor - f_mean) / f_std

        with torch.no_grad():
            t_pinn_tensor = torch.tensor([t_pinn], dtype=torch.float32)
            pinn_out = pinn_model(
                pinn_feat_norm.unsqueeze(0),
                t_pinn_tensor,
                t_out_tensor,
                h_glob_tensor,
                u_heat_tensor,
                dt_tensor
            )
            t_pinn = float(pinn_out["predicted_next"].item())
            corrections.append(float(pinn_out["correction"].item()))

    # Append the final step values
    times.append(int(records[-1]["time_s"]))
    t_actuals.append(float(records[-1]["T_zone_degC"]))
    t_pred_rcs.append(t_rc)
    t_pred_pinns.append(t_pinn)
    u_heatings.append(float(records[-1]["u_heating"]) - 273.15 if float(records[-1]["u_heating"]) > 200.0 else float(records[-1]["u_heating"]))
    t_outdoors.append(float(records[-1]["T_outdoor_degC"]))
    h_globals.append(float(records[-1]["H_global_Wm2"]))

    # Save to DataFrame and CSV
    df = pd.DataFrame({
        "time_s": times,
        "t_actual": t_actuals,
        "t_open_loop_rc": t_pred_rcs,
        "t_open_loop_pinn": t_pred_pinns,
        "u_heating": u_heatings,
        "t_outdoor": t_outdoors,
        "h_global": h_globals
    })
    df.to_csv(output_csv_path, index=False)
    print(f"Saved trajectory comparisons to: {output_csv_path}")

    # Compute metrics
    t_act_arr = np.array(t_actuals)
    t_rc_arr = np.array(t_pred_rcs)
    t_pinn_arr = np.array(t_pred_pinns)

    rmse_rc = np.sqrt(np.mean((t_act_arr - t_rc_arr)**2))
    mae_rc = np.mean(np.abs(t_act_arr - t_rc_arr))
    r2_rc = 1.0 - (np.sum((t_act_arr - t_rc_arr)**2) / np.sum((t_act_arr - np.mean(t_act_arr))**2))

    rmse_pinn = np.sqrt(np.mean((t_act_arr - t_pinn_arr)**2))
    mae_pinn = np.mean(np.abs(t_act_arr - t_pinn_arr))
    r2_pinn = 1.0 - (np.sum((t_act_arr - t_pinn_arr)**2) / np.sum((t_act_arr - np.mean(t_act_arr))**2))

    print("\n=======================================================")
    print(f"  OPEN-LOOP TRAJECTORY COMPARISON ({episode_json_path.stem})")
    print("=======================================================")
    print(f"  RC Model:   RMSE = {rmse_rc:.4f} °C, MAE = {mae_rc:.4f} °C, R2 = {r2_rc:.4f}")
    print(f"  PINN Model: RMSE = {rmse_pinn:.4f} °C, MAE = {mae_pinn:.4f} °C, R2 = {r2_pinn:.4f}")
    print("=======================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate surrogates in open loop rollout.")
    parser.add_argument("--episode", default="te_long_01", help="Episode dataset stem name.")
    parser.add_argument("--dataset-dir", default="datasets/phase1_singlezone/json")
    parser.add_argument("--pinn-ckpt", default="artifacts/pinn_phase1_building_scale/best_model.pt")
    parser.add_argument("--rc-ckpt", default="artifacts/rc_baseline_calibrated/rc_calibrated_checkpoint.pt")
    parser.add_argument("--output-dir", default="results/mpc_phase1")
    args = parser.parse_args()

    episode_path = Path(args.dataset_dir) / f"{args.episode}.json"
    output_path = Path(args.output_dir) / f"open_loop_{args.episode}_check.csv"

    evaluate_open_loop(episode_path, args.pinn_ckpt, args.rc_ckpt, output_path)
