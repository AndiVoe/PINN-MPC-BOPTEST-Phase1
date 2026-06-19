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


def _remap_state_dict(raw_state_dict):
    """Remap legacy parameter names (log_hvac_power_max → log_hvac_gain)."""
    remap = {"log_hvac_power_max": "log_hvac_gain"}
    state = {}
    for key, value in raw_state_dict.items():
        key = remap.get(key, key)
        state[key] = value
    return state


def _check_legacy_exp(ckpt) -> bool:
    """Detect if checkpoint was trained with exp() activation (legacy) vs softplus()."""
    phys_file = Path(ckpt).parent / "physical_parameters.json"
    if phys_file.exists():
        import json
        with open(phys_file) as f:
            data = json.load(f)
        note = data.get("note", "")
        if "exp()" in note or "exp() activation" in note:
            return True
    
    # Heuristic: if log_ua > 5 (raw value), it's exp-space (softplus would produce absurdly large values)
    ckpt_data = torch.load(ckpt, map_location="cpu", weights_only=False)
    sd = ckpt_data["model_state_dict"]
    log_ua = float(sd.get("log_ua", 0))
    if log_ua > 5.0:
        return True
    return False


def _build_model(ckpt_path, input_dim, hidden_dim, depth, dropout, zero_network=False):
    """Build model with correct activation based on checkpoint type."""
    ckpt_data = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    is_legacy_exp = _check_legacy_exp(ckpt_path)
    
    model = SingleZonePINN(input_dim, hidden_dim, depth, dropout)
    
    if is_legacy_exp:
        # Legacy checkpoint trained with exp() — override activation
        model._positive = lambda p: torch.exp(p)
    
    state = _remap_state_dict(ckpt_data["model_state_dict"])
    
    model.load_state_dict(state)
    
    if zero_network:
        # Zero out the NN weights in-place (keep same architecture, zero output)
        for p in model.network.parameters():
            p.data.zero_()
    
    model.eval()
    return model


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
    pinn_feature_dim = len(pinn_feature_names)

    rc_stats = rc_ckpt["normalization"]

    # Check if PGNN uses legacy exp() or current softplus
    pnn_is_legacy = _check_legacy_exp(pinn_ckpt_path)

    # ---- Build PGNN (correction ON) ----
    pnn_cfg = pinn_config["model"]
    pinn_model = _build_model(
        pinn_ckpt_path, pinn_feature_dim,
        pnn_cfg["hidden_dim"], pnn_cfg["depth"],
        pnn_cfg.get("dropout", 0.0),
        zero_network=False,
    )

    # ---- Build PGNN-no-corrector (correction OFF) ----
    pinn_nocorr_model = _build_model(
        pinn_ckpt_path, pinn_feature_dim,
        pnn_cfg["hidden_dim"], pnn_cfg["depth"],
        pnn_cfg.get("dropout", 0.0),
        zero_network=True,
    )

    # ---- Build RC model (separately calibrated, uses softplus) ----
    # RC checkpoint has a single-layer network (replaced during calibration)
    rc_model = SingleZonePINN(pinn_feature_dim, hidden_dim=16, depth=1)
    rc_model.network = torch.nn.Sequential(torch.nn.Linear(pinn_feature_dim, 1))
    # Load state (physics params only, strict=False since network shape differs)
    rc_state = _remap_state_dict(rc_ckpt["model_state_dict"])
    rc_model.load_state_dict(rc_state, strict=False)
    # Zero the network
    for p in rc_model.network.parameters():
        p.data.zero_()
    rc_model.eval()

    # ---- Physical Parameters Audit ----
    print("\n--- Physical Parameters Audit ---")
    with torch.no_grad():
        if pnn_is_legacy:
            print("PGNN (exp activation — legacy):")
            act = lambda x: torch.exp(x)
        else:
            print("PGNN (softplus activation — current):")
            act = lambda x: torch.nn.functional.softplus(x)
        
        print(f"  UA:       {float(act(pinn_model.log_ua)):.2f} kW/K = {float(act(pinn_model.log_ua))*1000:.2f} W/K" if not pnn_is_legacy else f"  UA:       {float(act(pinn_model.log_ua)):.2f} kW/K = {float(act(pinn_model.log_ua))*1000:.2f} W/K")
        print(f"  Solar:    {float(act(pinn_model.log_solar_gain)):.4f} m2")
        print(f"  HVAC:     {float(act(pinn_model.log_hvac_gain)):.2f} kW/K = {float(act(pinn_model.log_hvac_gain))*1000:.2f} W/K" if not pnn_is_legacy else f"  HVAC:     {float(act(pinn_model.log_hvac_gain))*1000:.2f} W/K")
        print(f"  Capacity: {float(act(pinn_model.log_capacity)):.4f} kWh/K")

        print("RC (softplus activation):")
        import torch.nn.functional as F
        print(f"  UA:       {float(F.softplus(rc_model.log_ua)):.2f} kW/K = {float(F.softplus(rc_model.log_ua))*1000:.2f} W/K")
        print(f"  Solar:    {float(F.softplus(rc_model.log_solar_gain)):.4f} m2")
        print(f"  HVAC:     {float(F.softplus(rc_model.log_hvac_gain)):.2f} kW/K = {float(F.softplus(rc_model.log_hvac_gain))*1000:.2f} W/K")
        print(f"  Capacity: {float(F.softplus(rc_model.log_capacity)):.4f} kWh/K")

        # Debug first-step physics delta
        t0_d = float(records[0]["T_zone_degC"])
        t_out_d = float(records[0]["T_outdoor_degC"])
        h_glob_d = float(records[0]["H_global_Wm2"])
        u_heat_d = float(records[0]["u_heating"])
        if u_heat_d > 200.0:
            u_heat_d -= 273.15
        dt_d = 900.0
        pd_pgnn = pinn_model.physics_delta(
            torch.tensor([t0_d]), torch.tensor([t_out_d]),
            torch.tensor([h_glob_d]), torch.tensor([u_heat_d]),
            torch.tensor([dt_d]),
        )
        pd_rc = rc_model.physics_delta(
            torch.tensor([t0_d]), torch.tensor([t_out_d]),
            torch.tensor([h_glob_d]), torch.tensor([u_heat_d]),
            torch.tensor([dt_d]),
        )
        print(f"\n  Step-0 physics_delta: PGNN={float(pd_pgnn):.4f}°C, RC={float(pd_rc):.4f}°C")

    # ---- Initial states ----
    t0 = float(records[0]["T_zone_degC"])
    t_rc = t0
    t_pinn = t0
    t_pinn_nocorr = t0

    # ---- Normalization stats ----
    f_mean = torch.tensor(pinn_stats["feature_mean"], dtype=torch.float32)
    f_std = torch.tensor(pinn_stats["feature_std"], dtype=torch.float32)
    rc_f_mean = torch.tensor(rc_stats["feature_mean"], dtype=torch.float32)
    rc_f_std = torch.tensor(rc_stats["feature_std"], dtype=torch.float32)

    # ---- Rollout lists ----
    times = []
    t_actuals = []
    t_pred_rcs = []
    t_pred_pinns = []
    t_pred_pinn_nocorrs = []
    u_heatings = []
    t_outdoors = []
    h_globals = []
    corrections = []

    print("\nSimulating surrogates in open loop...")
    for k in range(n_steps - 1):
        curr_rec = records[k]
        next_rec = records[k + 1]

        time_s = int(curr_rec["time_s"])
        dt_s = float(next_rec["time_s"] - time_s)
        t_act = float(curr_rec["T_zone_degC"])
        t_out = float(curr_rec["T_outdoor_degC"])
        h_glob = float(curr_rec["H_global_Wm2"])
        u_heat = float(curr_rec["u_heating"])
        if u_heat > 200.0:
            u_heat -= 273.15
        next_u_heat = float(next_rec["u_heating"])
        if next_u_heat > 200.0:
            next_u_heat -= 273.15

        cyc = get_cyclical_features(time_s)
        occupied = float(curr_rec.get("occupied", False))

        times.append(time_s)
        t_actuals.append(t_act)
        t_pred_rcs.append(t_rc)
        t_pred_pinns.append(t_pinn)
        t_pred_pinn_nocorrs.append(t_pinn_nocorr)
        u_heatings.append(u_heat)
        t_outdoors.append(t_out)
        h_globals.append(h_glob)

        t_out_tensor = torch.tensor([t_out], dtype=torch.float32)
        h_glob_tensor = torch.tensor([h_glob], dtype=torch.float32)
        u_heat_tensor = torch.tensor([u_heat], dtype=torch.float32)
        dt_tensor = torch.tensor([dt_s], dtype=torch.float32)

        # ---- RC Model ----
        rc_features = [
            t_rc, t_out, h_glob, u_heat,
            next_u_heat - u_heat, occupied, *cyc,
        ]
        rc_feat_norm = (torch.tensor(rc_features, dtype=torch.float32) - rc_f_mean) / rc_f_std

        with torch.no_grad():
            rc_out = rc_model(
                rc_feat_norm.unsqueeze(0),
                torch.tensor([t_rc], dtype=torch.float32),
                t_out_tensor, h_glob_tensor, u_heat_tensor, dt_tensor,
            )
            t_rc = float(rc_out["predicted_next"].item())

        # ---- PGNN (correction ON) ----
        pinn_features = [
            t_pinn, t_out, h_glob, u_heat,
            next_u_heat - u_heat, occupied, *cyc,
        ]
        pinn_feat_norm = (torch.tensor(pinn_features, dtype=torch.float32) - f_mean) / f_std

        with torch.no_grad():
            pinn_out = pinn_model(
                pinn_feat_norm.unsqueeze(0),
                torch.tensor([t_pinn], dtype=torch.float32),
                t_out_tensor, h_glob_tensor, u_heat_tensor, dt_tensor,
            )
            t_pinn = float(pinn_out["predicted_next"].item())
            corrections.append(float(pinn_out["correction"].item()))

        # ---- PGNN No-Corrector (correction OFF) ----
        pinn_nc_features = [
            t_pinn_nocorr, t_out, h_glob, u_heat,
            next_u_heat - u_heat, occupied, *cyc,
        ]
        pinn_nc_feat_norm = (torch.tensor(pinn_nc_features, dtype=torch.float32) - f_mean) / f_std

        with torch.no_grad():
            pinn_nc_out = pinn_nocorr_model(
                pinn_nc_feat_norm.unsqueeze(0),
                torch.tensor([t_pinn_nocorr], dtype=torch.float32),
                t_out_tensor, h_glob_tensor, u_heat_tensor, dt_tensor,
            )
            t_pinn_nocorr = float(pinn_nc_out["predicted_next"].item())

    # ---- Append final step ----
    times.append(int(records[-1]["time_s"]))
    t_actuals.append(float(records[-1]["T_zone_degC"]))
    t_pred_rcs.append(t_rc)
    t_pred_pinns.append(t_pinn)
    t_pred_pinn_nocorrs.append(t_pinn_nocorr)
    u_heat_val = float(records[-1]["u_heating"])
    u_heatings.append(u_heat_val - 273.15 if u_heat_val > 200.0 else u_heat_val)
    t_outdoors.append(float(records[-1]["T_outdoor_degC"]))
    h_globals.append(float(records[-1]["H_global_Wm2"]))
    corrections.append(0.0)

    # ---- Save CSV ----
    df = pd.DataFrame({
        "time_s": times,
        "t_actual": t_actuals,
        "t_open_loop_rc": t_pred_rcs,
        "t_open_loop_pinn": t_pred_pinns,
        "t_open_loop_pinn_nocorr": t_pred_pinn_nocorrs,
        "u_heating": u_heatings,
        "t_outdoor": t_outdoors,
        "h_global": h_globals,
        "correction": corrections,
    })
    df.to_csv(output_csv_path, index=False)
    print(f"Saved trajectory comparisons to: {output_csv_path}")

    # ---- Metrics ----
    t_act_arr = np.array(t_actuals)
    t_rc_arr = np.array(t_pred_rcs)
    t_pinn_arr = np.array(t_pred_pinns)
    t_pinn_nc_arr = np.array(t_pred_pinn_nocorrs)

    def compute_metrics(true, pred):
        rmse = np.sqrt(np.mean((true - pred) ** 2))
        mae = np.mean(np.abs(true - pred))
        ss_res = np.sum((true - pred) ** 2)
        ss_tot = np.sum((true - np.mean(true)) ** 2)
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
        return rmse, mae, r2

    rmse_rc, mae_rc, r2_rc = compute_metrics(t_act_arr, t_rc_arr)
    rmse_pinn, mae_pinn, r2_pinn = compute_metrics(t_act_arr, t_pinn_arr)
    rmse_pinn_nc, mae_pinn_nc, r2_pinn_nc = compute_metrics(t_act_arr, t_pinn_nc_arr)

    corr_arr = np.array(corrections)
    mean_abs_corr = np.mean(np.abs(corr_arr))
    mean_corr = np.mean(corr_arr)
    std_corr = np.std(corr_arr)
    max_abs_corr = np.max(np.abs(corr_arr))

    print("\n=======================================================")
    print(f"  OPEN-LOOP TRAJECTORY COMPARISON ({episode_json_path.stem})")
    print("=======================================================")
    print(f"  RC Model:          RMSE = {rmse_rc:.4f} °C, MAE = {mae_rc:.4f} °C, R2 = {r2_rc:.4f}")
    print(f"  PGNN (corr ON):    RMSE = {rmse_pinn:.4f} °C, MAE = {mae_pinn:.4f} °C, R2 = {r2_pinn:.4f}")
    print(f"  PGNN (corr OFF):   RMSE = {rmse_pinn_nc:.4f} °C, MAE = {mae_pinn_nc:.4f} °C, R2 = {r2_pinn_nc:.4f}")
    print("-------------------------------------------------------")
    print(f"  Corrector effect (RMSE improvement):  {rmse_pinn_nc - rmse_pinn:.4f} °C")
    print(f"  Correction stats:  mean = {mean_corr:.4f} °C, |mean| = {mean_abs_corr:.4f} °C")
    print(f"                    std = {std_corr:.4f} °C, max|corr| = {max_abs_corr:.4f} °C")
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