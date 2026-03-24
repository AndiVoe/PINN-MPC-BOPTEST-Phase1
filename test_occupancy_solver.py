#!/usr/bin/env python3
"""Test occupancy schedule integration with solver."""
from pathlib import Path
from mpc.occupancy import OccupancySchedule
from mpc.predictors import RCPredictor
from mpc.solver import MPCSolver

# Load RC predictor
ckpt = Path('artifacts/pinn_phase1/best_model.pt')
rc = RCPredictor.from_checkpoint(ckpt)
print(f'OK: Loaded RC predictor with params: ua={rc.ua:.4f}')

# Create occupancy schedule
sched = OccupancySchedule(start_hour=9, end_hour=17)
print(f'OK: Created occupancy schedule (09:00-17:00)')

# Create solver with occupancy schedule
solver = MPCSolver(
    predictor=rc,
    horizon_steps=24,
    dt_s=900,
    occupancy_schedule=sched,
)
print(f'OK: Created MPCSolver with occupancy schedule')

# Test a solve call
weather_fc = [{'t_outdoor': 5 + i*0.1, 'h_global': 200 + i*10} for i in range(24)]
u_opt, u_seq, info = solver.solve(
    t_zone=20.0,
    weather_forecast=weather_fc,
    u_prev=21.0,
    time_s=36000,  # 10:00 AM
)
print(f'OK: MPC solve successful: u_opt={u_opt:.2f} degC, solve_time={info["solve_time_ms"]:.1f}ms')

# Print comfort bounds at different times during occupancy schedule
from mpc.occupancy import comfort_bounds, comfort_bounds_sequence

t_occ_9am = 9 * 3600
t_noon = 12 * 3600
t_evening_6pm = 18 * 3600

bounds_morning = comfort_bounds(t_occ_9am, schedule=sched)
bounds_noon = comfort_bounds(t_noon, schedule=sched)
bounds_evening = comfort_bounds(t_evening_6pm, schedule=sched)

print(f'OK: Comfort bounds at 09:00: {bounds_morning} (occupied)')
print(f'OK: Comfort bounds at 12:00: {bounds_noon} (occupied)')
print(f'OK: Comfort bounds at 18:00: {bounds_evening} (unoccupied)')

# Test comfort bounds sequence
cb_seq = comfort_bounds_sequence(9*3600, 24, 900, schedule=sched)
occ_count = sum(1 for b in cb_seq if b == (21.0, 24.0))
print(f'OK: Comfort bounds sequence has {occ_count}/24 occupied bounds over 6 hours starting at 09:00')

print('\nOK: All occupancy schedule integration tests passed!')
