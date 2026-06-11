"""
Rolling-horizon MPC solver backed by scipy.optimize.minimize (SLSQP).

The solver owns the warm-start state across consecutive calls so that
each step inherits the shifted previous solution as its initial guess.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import Bounds, minimize

from .occupancy import OccupancySchedule, comfort_bounds_sequence
from .predictors import PredictorBase


class MPCSolver:
    """Rolling-horizon MPC optimizer.

    Parameters
    ----------
    predictor
        Interior model (RCPredictor or PINNPredictor).
    horizon_steps
        Number of lookahead steps (default 24 -> 6 h at 900 s interval).
    dt_s
        Control interval in seconds.
    u_min, u_max
        Setpoint bounds in degC.
    w_comfort, w_energy, w_smooth
        Objective weights (must match the manifest spec).
    maxiter
        SLSQP iteration limit per solve call.
    ftol
        SLSQP function tolerance.
    occupied_bounds, unoccupied_bounds
        Comfort temperature ranges (degC) used for occupancy-aware penalties.
    occupancy_schedule
        OccupancySchedule instance defining when occupied hours occur.
        If None, uses global default (08:00-18:00 daily).
    """

    def __init__(
        self,
        predictor: PredictorBase,
        *,
        horizon_steps: int = 24,
        dt_s: float = 900.0,
        u_min: float = 18.0,
        u_max: float = 24.0,
        w_comfort: float = 100.0,
        w_energy: float = 0.001,
        w_smooth: float = 0.1,
        maxiter: int = 100,
        ftol: float = 1e-4,
        occupied_bounds: tuple[float, float] = (21.0, 24.0),
        unoccupied_bounds: tuple[float, float] = (15.0, 30.0),
        occupancy_schedule: OccupancySchedule | None = None,
    ) -> None:
        self.predictor = predictor
        self.horizon = horizon_steps
        self.dt_s = dt_s
        self.u_min = u_min
        self.u_max = u_max
        self.w_comfort = w_comfort
        self.w_energy = w_energy
        self.w_smooth = w_smooth
        self.maxiter = maxiter
        self.ftol = ftol
        self.occupied_bounds = occupied_bounds
        self.unoccupied_bounds = unoccupied_bounds
        self.occupancy_schedule = occupancy_schedule

        # Warm-start storage: shift-by-1 between steps.
        self._prev_solution: np.ndarray | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear warm-start state (call at the start of each episode)."""
        self._prev_solution = None

    def solve(
        self,
        t_zone: float,
        weather_forecast: list[dict[str, float]],
        u_prev: float,
        time_s: int,
    ) -> tuple[float, list[float], dict[str, Any]]:
        """
        Run one MPC optimization step.

        Parameters
        ----------
        t_zone
            Current measured zone temperature (degC).
        weather_forecast
            List of dicts with keys ``t_outdoor`` (degC) and ``h_global`` (W/m┬▓),
            one entry per horizon step.  Length ≥ horizon_steps.
        u_prev
            The setpoint applied at the previous control step (degC).
        time_s
            Current simulation time in seconds (for occupancy / cyclical features).

        Returns
        -------
        (u_first, u_sequence, info)
            u_first    - optimal setpoint to apply now (degC)
            u_sequence - full optimal N-step sequence (degC)
            info       - dict with solve_time_ms, n_iter, success, obj_val
        """
        n = min(self.horizon, len(weather_forecast))
        wseq = weather_forecast[:n]

        cb = comfort_bounds_sequence(
            time_s, n, int(self.dt_s), self.occupied_bounds, self.unoccupied_bounds,
            schedule=self.occupancy_schedule
        )

        # Warm start: shift previous solution or repeat current setpoint.
        if self._prev_solution is not None and len(self._prev_solution) >= n:
            u0 = np.concatenate([
                self._prev_solution[1:n],
                [self._prev_solution[-1]],
            ]).astype(np.float64)
        else:
            u0 = np.full(n, np.clip(u_prev, self.u_min, self.u_max), dtype=np.float64)

        bounds = Bounds(self.u_min, self.u_max)

        use_jac = getattr(self.predictor, "provides_gradient", False)

        def _obj_and_grad(u_np: np.ndarray):
            obj, grad = self.predictor.objective_and_grad(
                u_np, t_zone, wseq, u_prev, time_s,
                self.dt_s, cb, self.w_comfort, self.w_energy, self.w_smooth,
            )
            if use_jac:
                return float(obj), grad  # scipy expects (float, float64 array)
            return float(obj)

        t_start = time.perf_counter()
        result = minimize(
            _obj_and_grad,
            u0,
            method="SLSQP",
            jac=True if use_jac else False,
            bounds=bounds,
            options={"maxiter": self.maxiter, "ftol": self.ftol},
        )
        solve_time_ms = (time.perf_counter() - t_start) * 1000.0

        u_opt = np.clip(result.x, self.u_min, self.u_max)
        self._prev_solution = u_opt

        return (
            float(u_opt[0]),
            u_opt.tolist(),
            {
                "solve_time_ms": solve_time_ms,
                "n_iter": int(result.nit),
                "success": bool(result.success),
                "obj_val": float(result.fun),
            },
        )
