"""Occupancy schedule and comfort bound helpers."""

from __future__ import annotations

from typing import Any

# Default occupied hours (backup for global use): 08:00 ÔÇô 18:00, simplified commercial schedule.
_DEFAULT_OCC_START_H = 8
_DEFAULT_OCC_END_H = 18

_SECS_PER_DAY = 24 * 3600


class OccupancySchedule:
    """Encapsulates occupancy schedule for a testcase.
    
    Parameters
    ----------
    start_hour : float
        Hour of day (0-24) when occupancy begins (e.g., 8 for 08:00).
    end_hour : float
        Hour of day (0-24) when occupancy ends (e.g., 18 for 18:00).
    weekends_occupied : bool
        If False, weekends are always unoccupied (simplified; assumes day-of-week is computable).
        If True, occupancy schedule applies every day.
    """
    
    def __init__(
        self,
        start_hour: float = _DEFAULT_OCC_START_H,
        end_hour: float = _DEFAULT_OCC_END_H,
        weekends_occupied: bool = True,
    ) -> None:
        self.start_hour = float(start_hour)
        self.end_hour = float(end_hour)
        self.weekends_occupied = bool(weekends_occupied)
    
    def is_occupied(self, time_s: int) -> bool:
        """Return True if time_s falls within occupied hours.
        
        Handles wrap-around schedules (e.g., 22:00-08:00 for evening/night occupancy).
        """
        if not self.weekends_occupied:
            # Day index convention: day 0 is Monday, day 5-6 are weekend.
            day_idx = int(time_s // _SECS_PER_DAY) % 7
            if day_idx >= 5:
                return False

        hour = (time_s % _SECS_PER_DAY) / 3600.0
        
        if self.start_hour < self.end_hour:
            # Normal schedule (e.g., 08:00-18:00)
            return self.start_hour <= hour < self.end_hour
        else:
            # Wrap-around schedule (e.g., 22:00-08:00, midnight crossing)
            return hour >= self.start_hour or hour < self.end_hour
    
    @classmethod
    def from_dict(cls, config: dict[str, Any] | None) -> "OccupancySchedule":
        """Create schedule from config dict (supports None for defaults)."""
        if config is None:
            return cls()
        return cls(
            start_hour=float(config.get("start_hour", _DEFAULT_OCC_START_H)),
            end_hour=float(config.get("end_hour", _DEFAULT_OCC_END_H)),
            weekends_occupied=bool(config.get("weekends_occupied", True)),
        )


# Global default schedule instance (used when no per-case schedule is provided).
_global_schedule = OccupancySchedule()


def is_occupied(time_s: int, schedule: OccupancySchedule | None = None) -> bool:
    """Return True if *time_s* (seconds from start of year) falls within occupied hours.
    
    Parameters
    ----------
    time_s : int
        Time in seconds (from start of year or arbitrary epoch).
    schedule : OccupancySchedule, optional
        Schedule to use. If None, uses global default (08:00-18:00).
    """
    sched = schedule or _global_schedule
    return sched.is_occupied(time_s)


def comfort_bounds(
    time_s: int,
    occupied: tuple[float, float] = (21.0, 24.0),
    unoccupied: tuple[float, float] = (15.0, 30.0),
    schedule: OccupancySchedule | None = None,
) -> tuple[float, float]:
    """Return (T_lower_degC, T_upper_degC) comfort bounds for a given timestamp.
    
    Parameters
    ----------
    time_s : int
        Time in seconds.
    occupied : tuple
        Comfort bounds during occupied hours (T_lower, T_upper).
    unoccupied : tuple
        Comfort bounds during unoccupied hours.
    schedule : OccupancySchedule, optional
        Schedule to use. If None, uses global default.
    """
    return occupied if is_occupied(time_s, schedule) else unoccupied


def comfort_bounds_sequence(
    start_time_s: int,
    n_steps: int,
    dt_s: int,
    occupied: tuple[float, float] = (21.0, 24.0),
    unoccupied: tuple[float, float] = (15.0, 30.0),
    schedule: OccupancySchedule | None = None,
) -> list[tuple[float, float]]:
    """Return a list of comfort bound tuples for an N-step lookahead.
    
    Parameters
    ----------
    start_time_s : int
        Start time in seconds.
    n_steps : int
        Number of lookahead steps.
    dt_s : int
        Time step in seconds.
    occupied : tuple
        Comfort bounds during occupied hours.
    unoccupied : tuple
        Comfort bounds during unoccupied hours.
    schedule : OccupancySchedule, optional
        Schedule to use. If None, uses global default.
    """
    return [
        comfort_bounds(start_time_s + i * dt_s, occupied, unoccupied, schedule)
        for i in range(n_steps)
    ]
