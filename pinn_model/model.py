from __future__ import annotations

import torch
from torch import nn


class SingleZonePINN(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, depth: int, dropout: float = 0.0) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        in_dim = input_dim
        for _ in range(depth):
            layers.append(nn.Linear(in_dim, hidden_dim))
            layers.append(nn.Tanh())
            if dropout > 0.0:
                layers.append(nn.Dropout(dropout))
            in_dim = hidden_dim
        layers.append(nn.Linear(in_dim, 1))
        self.network = nn.Sequential(*layers)

        self.log_ua = nn.Parameter(torch.tensor(-1.5))
        self.log_solar_gain = nn.Parameter(torch.tensor(-3.0))
        self.log_hvac_gain = nn.Parameter(torch.tensor(-0.5))
        self.log_capacity = nn.Parameter(torch.tensor(12.0))

    def _positive(self, parameter: torch.Tensor) -> torch.Tensor:
        return torch.nn.functional.softplus(parameter)

    def physics_delta(
        self,
        t_zone: torch.Tensor,
        t_outdoor: torch.Tensor,
        h_global: torch.Tensor,
        u_heating: torch.Tensor,
        dt_s: torch.Tensor,
    ) -> torch.Tensor:
        ua = self._positive(self.log_ua)
        solar_gain = self._positive(self.log_solar_gain)
        hvac_gain = self._positive(self.log_hvac_gain)
        capacity = self._positive(self.log_capacity) + 1e-6

        hvac_drive = torch.relu(u_heating - t_zone)
        heat_flow = (
            ua * (t_outdoor - t_zone)
            + solar_gain * (h_global / 1000.0)
            + hvac_gain * hvac_drive
        )
        # Convert to a per-hour scale to keep the RC increment numerically stable at 900 s steps.
        return (dt_s / 3600.0) * heat_flow / capacity

    def forward(
        self,
        features: torch.Tensor,
        t_zone: torch.Tensor,
        t_outdoor: torch.Tensor,
        h_global: torch.Tensor,
        u_heating: torch.Tensor,
        dt_s: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        correction = 5.0 * torch.tanh(self.network(features).squeeze(-1))
        physics_delta = self.physics_delta(t_zone, t_outdoor, h_global, u_heating, dt_s)
        predicted_next = t_zone + physics_delta + correction
        return {
            "predicted_next": predicted_next,
            "physics_delta": physics_delta,
            "correction": correction,
        }