"""
Solar device model.

File: src/marinegrid/renewables/solar.py
"""

# Third-party
import pandas as pd

# Local
from .base import RenewableDevice
class SolarDevice(RenewableDevice):
    """
    Solar photovoltaic device with time-series power output.
    
    Attributes:
        panel_model: Solar panel model name.
        tilt_angle: Panel tilt angle in degrees.
        azimuth: Panel azimuth angle in degrees.
    """

    def __init__(self) -> None:
        """Initialize a solar device with defaults."""
        super().__init__()
        self.device_type = "Solar"
        self.panel_model: str | None = None
        self.tilt_angle: float | None = None
        self.azimuth: float | None = None

    def power_at(self, ts: pd.Timestamp) -> float:
        """Return active power at timestamp `ts` (per unit)."""
        if ts not in self.data.index:
            raise KeyError(f"Timestamp {ts} not found in solar device data")
        return float(self.data.loc[ts, "p"])