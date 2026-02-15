"""
Wind device model.

File: src/marinegrid/renewables/wind.py
"""

# Third-party
import pandas as pd

# Local
from .base import RenewableDevice


class WindDevice(RenewableDevice):
    """
    Wind turbine device with time-series power output.
    
    Attributes:
        turbine_model: Turbine model name.
        hub_height: Hub height in meters.
        rated_speed: Rated wind speed in m/s.
    """

    def __init__(self) -> None:
        """Initialize a wind turbine device with defaults."""
        super().__init__()
        self.device_type = "Wind"
        self.turbine_model: str | None = None
        self.hub_height: float | None = None
        self.rated_speed: float | None = None

    def power_at(self, ts: pd.Timestamp) -> float:
        """Return active power at timestamp `ts` (per unit)."""
        if ts not in self.data.index:
            raise KeyError(f"Timestamp {ts} not found in wind device data")
        return float(self.data.loc[ts, "p"])