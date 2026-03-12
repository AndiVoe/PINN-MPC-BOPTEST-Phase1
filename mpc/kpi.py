"""KPI accumulator for MPC episodes."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass
class _StepRecord:
    time_s: int
    t_zone: float
    u_heating: float
    power_w: float
    power_heating_w: float
    power_electric_w: float
    solve_time_ms: float
    t_lower: float
    t_upper: float
    occupied: bool


class KPILogger:
    """Accumulates per-step measurements and computes end-of-episode KPIs."""

    def __init__(self, dt_s: float = 900.0) -> None:
        self.dt_s = dt_s
        self._steps: list[_StepRecord] = []

    def record(
        self,
        *,
        time_s: int,
        t_zone: float,
        u_heating: float,
        power_w: float,
        power_heating_w: float,
        power_electric_w: float,
        solve_time_ms: float,
        t_lower: float,
        t_upper: float,
        occupied: bool,
    ) -> None:
        self._steps.append(
            _StepRecord(
                time_s=time_s,
                t_zone=t_zone,
                u_heating=u_heating,
                power_w=power_w,
                power_heating_w=power_heating_w,
                power_electric_w=power_electric_w,
                solve_time_ms=solve_time_ms,
                t_lower=t_lower,
                t_upper=t_upper,
                occupied=occupied,
            )
        )

    # ------------------------------------------------------------------
    # KPI computation
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return diagnostic KPIs used for debugging and controller analysis."""
        steps = self._steps
        if not steps:
            return {}

        dt_h = self.dt_s / 3600.0

        # Thermal comfort: degree-hours of violation during occupied periods only.
        comfort_Kh = 0.0
        comfort_steps = 0
        for s in steps:
            if not s.occupied:
                continue
            viol = max(0.0, s.t_lower - s.t_zone) + max(0.0, s.t_zone - s.t_upper)
            if viol > 0.0:
                comfort_Kh += viol * dt_h
                comfort_steps += 1

        valid_power_total = [s.power_w for s in steps if math.isfinite(s.power_w) and s.power_w >= 0.0]
        valid_power_heat = [s.power_heating_w for s in steps if math.isfinite(s.power_heating_w) and s.power_heating_w >= 0.0]
        valid_power_ele = [s.power_electric_w for s in steps if math.isfinite(s.power_electric_w) and s.power_electric_w >= 0.0]

        total_energy_Wh = sum(p * dt_h for p in valid_power_total)
        heating_energy_Wh = sum(p * dt_h for p in valid_power_heat)
        electric_energy_Wh = sum(p * dt_h for p in valid_power_ele)

        peak_power_W = max(valid_power_total) if valid_power_total else 0.0
        peak_heating_power_W = max(valid_power_heat) if valid_power_heat else 0.0
        peak_electric_power_W = max(valid_power_ele) if valid_power_ele else 0.0

        # Control smoothness: sum of absolute setpoint changes.
        smoothness = sum(
            abs(steps[i].u_heating - steps[i - 1].u_heating)
            for i in range(1, len(steps))
        )

        # MPC solve times (only steps where an actual solve occurred).
        solve_times = sorted(s.solve_time_ms for s in steps if s.solve_time_ms > 0.0)
        if solve_times:
            n = len(solve_times)
            st_mean = sum(solve_times) / n
            idx_p95 = max(0, int(math.ceil(0.95 * n)) - 1)
            st_p95 = solve_times[idx_p95]
            st_max = solve_times[-1]
        else:
            st_mean = st_p95 = st_max = 0.0

        return {
            "n_steps": len(steps),
            "comfort_Kh": round(comfort_Kh, 4),
            "comfort_violation_steps": comfort_steps,
            "total_energy_Wh": round(total_energy_Wh, 2),
            "heating_energy_Wh": round(heating_energy_Wh, 2),
            "electric_energy_Wh": round(electric_energy_Wh, 2),
            "peak_power_W": round(peak_power_W, 2),
            "peak_heating_power_W": round(peak_heating_power_W, 2),
            "peak_electric_power_W": round(peak_electric_power_W, 2),
            "control_smoothness": round(smoothness, 4),
            "mpc_solve_time_mean_ms": round(st_mean, 3),
            "mpc_solve_time_p95_ms": round(st_p95, 3),
            "mpc_solve_time_max_ms": round(st_max, 3),
            "n_mpc_solves": len(solve_times),
        }

    def challenge_kpis(self, boptest_kpis: dict | None = None) -> dict:
        """
        Return the 5 essential Adrenalin BOPTEST challenge KPIs.

        Website-defined KPI names:
          - cost_tot
          - idis_tot
          - pdih_tot
          - pele_tot
          - tdis_tot

        If official BOPTEST KPIs are available, they are used as source-of-truth.
        Otherwise local estimates are provided where possible and clearly labeled.
        """
        diag = self.summary()
        bop = boptest_kpis or {}

        def _entry(name: str, unit: str, description: str, fallback_value: float | None) -> dict:
            if name in bop and bop[name] is not None:
                try:
                    value = float(bop[name])
                except (TypeError, ValueError):
                    value = bop[name]
                return {
                    "value": value,
                    "unit": unit,
                    "description": description,
                    "source": "boptest",
                }
            source = "estimated" if fallback_value is not None else "unavailable"
            return {
                "value": fallback_value,
                "unit": unit,
                "description": description,
                "source": source,
            }

        return {
            "cost_tot": _entry(
                "cost_tot",
                "EUR/m2",
                "Operational HVAC cost (energy * price).",
                None,
            ),
            "idis_tot": _entry(
                "idis_tot",
                "ppm*h/zone",
                "IAQ discomfort from CO2 concentration above bounds.",
                None,
            ),
            "pdih_tot": _entry(
                "pdih_tot",
                "kW/m2",
                "Peak district heating demand (15 min).",
                (diag.get("peak_heating_power_W", 0.0) / 1000.0) if diag else 0.0,
            ),
            "pele_tot": _entry(
                "pele_tot",
                "kW/m2",
                "Peak electrical demand (15 min).",
                (diag.get("peak_electric_power_W", 0.0) / 1000.0) if diag else 0.0,
            ),
            "tdis_tot": _entry(
                "tdis_tot",
                "Kh/zone",
                "Thermal discomfort relative to comfort bounds.",
                diag.get("comfort_Kh") if diag else 0.0,
            ),
        }

    def build_kpi_payload(self, boptest_kpis: dict | None = None) -> dict:
        """Return structured KPI payload with challenge + diagnostic groups."""
        return {
            "challenge_kpis": self.challenge_kpis(boptest_kpis=boptest_kpis),
            "diagnostic_kpis": self.summary(),
        }

    def step_records(self) -> list[dict]:
        return [asdict(s) for s in self._steps]
