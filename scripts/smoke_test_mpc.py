"""Quick smoke test for WP4 MPC modules. Run from PINN root."""
import sys
sys.path.insert(0, ".")

from pathlib import Path
import numpy as np

from mpc import RCPredictor, PINNPredictor, MPCSolver, KPILogger
from mpc.occupancy import comfort_bounds_sequence

CKPT = Path("artifacts/pinn_phase1/best_model.pt")

# ---- RC predictor ----
rc = RCPredictor.from_checkpoint(CKPT)
print(f"RC params: ua={rc.ua:.4f}, solar_gain={rc.solar_gain:.4f}, "
      f"hvac_gain={rc.hvac_gain:.4f}, capacity={rc.capacity:.4f}")

weather = [{"t_outdoor": 5.0, "h_global": 200.0}] * 24
preds_rc = rc.predict_sequence(21.0, weather, [22.0] * 24, 22.0, 0, 900.0)
print(f"RC rollout (first 4): {[round(p, 3) for p in preds_rc[:4]]}")

# ---- PINN predictor ----
pinn = PINNPredictor(CKPT)
preds_pinn = pinn.predict_sequence(21.0, weather, [22.0] * 24, 22.0, 0, 900.0)
print(f"PINN rollout (first 4): {[round(p, 3) for p in preds_pinn[:4]]}")

# ---- Analytical gradient ----
u_np = np.full(24, 22.0)
cb = comfort_bounds_sequence(0, 24, 900)
obj, grad = pinn.objective_and_grad(u_np, 21.0, weather, 22.0, 0, 900.0, cb, 100.0, 0.0001, 0.1)
print(f"PINN gradient: obj={obj:.4f}, grad[:4]={[round(g, 4) for g in grad[:4]]}")
assert grad is not None and len(grad) == 24, "Gradient shape mismatch"

# ---- RC gradient (FD) ----
obj_rc, grad_rc = rc.objective_and_grad(u_np, 21.0, weather, 22.0, 0, 900.0, cb, 100.0, 0.0001, 0.1)
print(f"RC objective (FD): obj={obj_rc:.4f}, grad=None (expected: {grad_rc})")

# ---- Solver with PINN ----
solver_pinn = MPCSolver(predictor=pinn, horizon_steps=24, dt_s=900.0)
u_first, u_seq, info = solver_pinn.solve(21.0, weather, 22.0, 0)
print(f"PINN solver: u_first={u_first:.2f}  success={info['success']}  "
      f"solve={info['solve_time_ms']:.1f}ms  n_iter={info['n_iter']}")

# ---- Solver with RC ----
solver_rc = MPCSolver(predictor=rc, horizon_steps=24, dt_s=900.0)
u_first_rc, _, info_rc = solver_rc.solve(21.0, weather, 22.0, 0)
print(f"RC solver:   u_first={u_first_rc:.2f}  success={info_rc['success']}  "
      f"solve={info_rc['solve_time_ms']:.1f}ms  n_iter={info_rc['n_iter']}")

# ---- KPILogger ----
kpi = KPILogger(dt_s=900.0)
for k in range(10):
    kpi.record(
        time_s=k * 900 + 8 * 3600,
        t_zone=22.0 + k * 0.1,
        u_heating=22.0,
        power_w=500.0,
      power_heating_w=300.0,
      power_electric_w=200.0,
        solve_time_ms=50.0,
        t_lower=21.0,
        t_upper=24.0,
        occupied=True,
    )
s = kpi.summary()
print(f"KPI summary: {s}")
print(f"Challenge KPIs: {kpi.challenge_kpis({})}")

print("\n=== ALL SMOKE TESTS PASSED ===")
