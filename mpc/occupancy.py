"""Occupancy schedule and comfort bound helpers."""

from __future__ import annotations

# Occupied hours: 08:00 – 18:00, applied every day (simplified commercial schedule).
_OCC_START_H = 8
_OCC_END_H = 18

_SECS_PER_DAY = 24 * 3600


def is_occupied(time_s: int) -> bool:
    """Return True if *time_s* (seconds from start of year) falls within occupied hours."""
    hour = (time_s % _SECS_PER_DAY) / 3600.0
    return _OCC_START_H <= hour < _OCC_END_H


def comfort_bounds(
    time_s: int,
    occupied: tuple[float, float] = (21.0, 24.0),
    unoccupied: tuple[float, float] = (15.0, 30.0),
) -> tuple[float, float]:
    """Return (T_lower_degC, T_upper_degC) comfort bounds for a given timestamp."""
    return occupied if is_occupied(time_s) else unoccupied


def comfort_bounds_sequence(
    start_time_s: int,
    n_steps: int,
    dt_s: int,
    occupied: tuple[float, float] = (21.0, 24.0),
    unoccupied: tuple[float, float] = (15.0, 30.0),
) -> list[tuple[float, float]]:
    """Return a list of comfort bound tuples for an N-step lookahead."""
    return [
        comfort_bounds(start_time_s + i * dt_s, occupied, unoccupied)
        for i in range(n_steps)
    ]
