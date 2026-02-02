"""
Solar device model.

File: src/marinegrid/renewables/solar.py
"""

# Standard library
from typing import Optional

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

    def __init__(self):
        """Initialize a solar device with defaults."""
        super().__init__()
        self.device_type = "Solar"
        self.panel_model: Optional[str] = None
        self.tilt_angle: Optional[float] = None
        self.azimuth: Optional[float] = None

    def power_at(self, ts: pd.Timestamp) -> float:
        """Return active power at timestamp `ts` (per unit)."""
        if ts not in self.data.index:
            raise KeyError(f"Timestamp {ts} not found in solar device data")
        return float(self.data.loc[ts, "p"])