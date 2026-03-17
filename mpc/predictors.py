"""
Interior-model predictors for rolling-horizon MPC.

Two concrete implementations:
  - RCPredictor: simple 1R1C linear thermal model (whitebox baseline).
  - PINNPredictor: trained SingleZonePINN with analytical autograd gradient.

Both expose the same interface used by MPCSolver:

    obj, grad = predictor.objective_and_grad(
        u_np, t_zone_0, weather_seq, u_prev, time_s, dt_s,
        comfort_bounds_seq, w_comfort, w_energy, w_smooth
    )

    obj  : float ÔÇô total weighted cost
    grad : np.ndarray shape (N,) ÔÇô d_obj/d_u, or None ÔåÆ solver uses FD
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import torch

# Reuse cyclical feature encoder from data module.
from pinn_model.data import _cyclical_features
from pinn_model.model import SingleZonePINN


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class PredictorBase:
    """Abstract base class for MPC interior predictors."""

    #: Subclasses set this to True when objective_and_grad returns a gradient.
    provides_gradient: bool = False

    def predict_sequence(
        self,
        t_zone_0: float,
        weather_sequence: list[dict[str, float]],
        u_sequence: list[float],
        u_prev: float,
        time_s: int,
        dt_s: float,
    ) -> list[float]:
        """Return list of N predicted T_zone values (one per horizon step)."""
        raise NotImplementedError

    def objective_and_grad(
        self,
        u_np: np.ndarray,
        t_zone_0: float,
        weather_seq: list[dict[str, float]],
        u_prev: float,
        time_s: int,
        dt_s: float,
        comfort_bounds_seq: list[tuple[float, float]],
        w_comfort: float,
        w_energy: float,
        w_smooth: float,
    ) -> tuple[float, np.ndarray | None]:
        """
        Compute the MPC objective and its gradient w.r.t. u_np.

        Returns (objective, gradient_or_None).
        If gradient is None the solver falls back to finite differences.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 1R1C RC predictor (whitebox baseline)
# ---------------------------------------------------------------------------


class RCPredictor(PredictorBase):
    """
    Simple lumped-capacitance RC model:

        dT/dt = [ UA*(T_out - T) + solar_gain*(H/1000) + hvac_gain*max(u-T,0) ] / C

    integrated with Euler forward at dt_s/3600 per-hour scale.
    Physics parameters are loaded from the PINN checkpoint so both
    predictors share the same identified building parameters.
    """

    provides_gradient = False  # uses scipy finite differences

    def __init__(
        self,
        ua: float,
        solar_gain: float,
        hvac_gain: float,
        capacity: float,
    ) -> None:
        self.ua = ua
        self.solar_gain = solar_gain
        self.hvac_gain = hvac_gain
        self.capacity = max(capacity, 1e-6)

    @classmethod
    def from_checkpoint(cls, checkpoint_path: Path | str) -> "RCPredictor":
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        p = ckpt.get("physics_parameters", {})
        return cls(
            ua=float(p.get("ua", 0.185)),
            solar_gain=float(p.get("solar_gain", 0.347)),
            hvac_gain=float(p.get("hvac_gain", 0.767)),
            capacity=float(p.get("capacity", 10.7)),
        )

    # ------------------------------------------------------------------

    def _step(self, T: float, t_out: float, h_glo: float, u: float, dt_s: float) -> float:
        hvac_drive = max(0.0, u - T)
        heat_flow = (
            self.ua * (t_out - T)
            + self.solar_gain * (h_glo / 1000.0)
            + self.hvac_gain * hvac_drive
        )
        return T + (dt_s / 3600.0) * heat_flow / self.capacity

    def predict_sequence(
        self,
        t_zone_0: float,
        weather_sequence: list[dict[str, float]],
        u_sequence: list[float],
        u_prev: float,
        time_s: int,
        dt_s: float,
    ) -> list[float]:
        T = t_zone_0
        preds: list[float] = []
        for w, u in zip(weather_sequence, u_sequence):
            T = self._step(T, w["t_outdoor"], w["h_global"], u, dt_s)
            T = max(-20.0, min(60.0, T))
            preds.append(T)
        return preds

    def objective_and_grad(
        self,
        u_np: np.ndarray,
        t_zone_0: float,
        weather_seq: list[dict[str, float]],
        u_prev: float,
        time_s: int,
        dt_s: float,
        comfort_bounds_seq: list[tuple[float, float]],
        w_comfort: float,
        w_energy: float,
        w_smooth: float,
    ) -> tuple[float, None]:
        """Numpy rollout; gradient computed by scipy finite differences."""
        T = t_zone_0
        cost = 0.0
        for i, (w, (T_lo, T_hi)) in enumerate(zip(weather_seq, comfort_bounds_seq)):
            u = float(u_np[i])
            T = self._step(T, w["t_outdoor"], w["h_global"], u, dt_s)
            T = max(-20.0, min(60.0, T))
            viol = max(0.0, T_lo - T) + max(0.0, T - T_hi)
            cost += w_comfort * viol**2
            cost += w_energy * u
            u_prv = u_prev if i == 0 else float(u_np[i - 1])
            cost += w_smooth * abs(u - u_prv)
        return cost, None  # None ÔåÆ solver uses finite differences


# ---------------------------------------------------------------------------
# PINN predictor (surrogate)
# ---------------------------------------------------------------------------


class PINNPredictor(PredictorBase):
    """
    Trained SingleZonePINN used as the MPC interior model.

    The objective gradient is computed analytically via torch.autograd,
    differentiating through the full N-step recursive rollout.
    """

    provides_gradient = True  # analytical gradient via torch.autograd

    def __init__(self, checkpoint_path: Path | str) -> None:
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

        config = ckpt["config"]
        # Config may be flat or nested under a "model" sub-key.
        model_cfg = config.get("model", config)
        feature_names = ckpt["feature_names"]
        self._model = SingleZonePINN(
            input_dim=len(feature_names),
            hidden_dim=model_cfg["hidden_dim"],
            depth=model_cfg["depth"],
            dropout=model_cfg.get("dropout", 0.0),
        )
        self._model.load_state_dict(ckpt["model_state_dict"])
        self._model.eval()

        # Disable gradient tracking for model parameters during rollout.
        for param in self._model.parameters():
            param.requires_grad_(False)

        norm = ckpt["normalization"]
        self._feat_mean = torch.tensor(norm["feature_mean"], dtype=torch.float32)
        self._feat_std = torch.tensor(norm["feature_std"], dtype=torch.float32)

    # ------------------------------------------------------------------

    def _forward_step(
        self,
        T: torch.Tensor,
        t_out_f: float,
        h_glo_f: float,
        u_i: torch.Tensor,
        u_prv: torch.Tensor,
        step_time_s: int,
        dt: torch.Tensor,
    ) -> torch.Tensor:
        """Single differentiable prediction step; returns T_next as scalar tensor."""
        delta_u = u_i - u_prv
        tod_sin, tod_cos, year_sin, year_cos = _cyclical_features(step_time_s)
        raw_feat = torch.stack([
            T,
            torch.tensor(t_out_f, dtype=torch.float32),
            torch.tensor(h_glo_f, dtype=torch.float32),
            u_i,
            delta_u,
            torch.tensor(tod_sin, dtype=torch.float32),
            torch.tensor(tod_cos, dtype=torch.float32),
            torch.tensor(year_sin, dtype=torch.float32),
            torch.tensor(year_cos, dtype=torch.float32),
        ])
        feat_norm = (raw_feat - self._feat_mean) / self._feat_std
        feat_batch = feat_norm.unsqueeze(0)

        out = self._model(
            feat_batch,
            T.unsqueeze(0),
            torch.tensor([t_out_f], dtype=torch.float32),
            torch.tensor([h_glo_f], dtype=torch.float32),
            u_i.unsqueeze(0),
            dt.unsqueeze(0),
        )
        return torch.clamp(out["predicted_next"].squeeze(), -20.0, 60.0)

    def predict_sequence(
        self,
        t_zone_0: float,
        weather_sequence: list[dict[str, float]],
        u_sequence: list[float],
        u_prev: float,
        time_s: int,
        dt_s: float,
    ) -> list[float]:
        T = torch.tensor(t_zone_0, dtype=torch.float32)
        dt = torch.tensor(dt_s, dtype=torch.float32)
        u_prev_t = torch.tensor(u_prev, dtype=torch.float32)
        preds: list[float] = []
        with torch.no_grad():
            for i, (w, u_f) in enumerate(zip(weather_sequence, u_sequence)):
                u_i = torch.tensor(u_f, dtype=torch.float32)
                u_prv = u_prev_t if i == 0 else torch.tensor(u_sequence[i - 1], dtype=torch.float32)
                T = self._forward_step(T, w["t_outdoor"], w["h_global"], u_i, u_prv,
                                       time_s + i * int(dt_s), dt)
                preds.append(float(T.item()))
        return preds

    def objective_and_grad(
        self,
        u_np: np.ndarray,
        t_zone_0: float,
        weather_seq: list[dict[str, float]],
        u_prev: float,
        time_s: int,
        dt_s: float,
        comfort_bounds_seq: list[tuple[float, float]],
        w_comfort: float,
        w_energy: float,
        w_smooth: float,
    ) -> tuple[float, np.ndarray]:
        """
        Differentiable rollout with analytical gradient via torch.autograd.
        Returns (objective, gradient_array_shape_N).
        """
        u_tensor = torch.tensor(u_np, dtype=torch.float32, requires_grad=True)
        T = torch.tensor(t_zone_0, dtype=torch.float32)
        dt = torch.tensor(dt_s, dtype=torch.float32)
        u_prev_t = torch.tensor(u_prev, dtype=torch.float32)

        total_cost = torch.zeros(1)

        for i, (w, (T_lo, T_hi)) in enumerate(zip(weather_seq, comfort_bounds_seq)):
            u_i = u_tensor[i]
            u_prv = u_prev_t if i == 0 else u_tensor[i - 1]
            T = self._forward_step(T, w["t_outdoor"], w["h_global"], u_i, u_prv,
                                   time_s + i * int(dt_s), dt)
            viol_lo = torch.clamp(torch.tensor(T_lo) - T, min=0.0)
            viol_hi = torch.clamp(T - torch.tensor(T_hi), min=0.0)
            total_cost = total_cost + w_comfort * (viol_lo**2 + viol_hi**2)
            total_cost = total_cost + w_energy * u_i
            total_cost = total_cost + w_smooth * torch.abs(u_i - u_prv)

        total_cost.backward()
        grad_np = u_tensor.grad.detach().numpy().astype(np.float64)
        return float(total_cost.item()), grad_np
