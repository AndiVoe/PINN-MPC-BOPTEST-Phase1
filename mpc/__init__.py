"""WP4 MPC harness package."""

from .kpi import KPILogger
from .occupancy import comfort_bounds, comfort_bounds_sequence, is_occupied
from .solver import MPCSolver

# Lazy import of PINN to avoid torch dependency when only using RC predictor
def __getattr__(name: str):
    if name == "PINNPredictor":
        from .predictors import PINNPredictor
        return PINNPredictor
    elif name == "RCPredictor":
        from .predictors import RCPredictor
        return RCPredictor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "KPILogger",
    "MPCSolver",
    "PINNPredictor",
    "RCPredictor",
    "comfort_bounds",
    "comfort_bounds_sequence",
    "is_occupied",
]

