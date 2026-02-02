"""
Wave energy converter device model.

File: src/marinegrid/renewables/wec.py
"""

# Standard library
from typing import Optional

# Third-party
import pandas as pd

# Local
from .base import RenewableDevice


class WECDevice(RenewableDevice):
    """
    Wave Energy Converter device with time-series power output.
    
    Attributes:
        model: WEC model name (e.g., "RM3", "LUPA").
        wec_sim_id: Simulation identifier in the database.
        bus_location: Bus number where the device connects.
    """

    def __init__(self):
        """Initialize a WEC device with default metadata."""
        super().__init__()
        self.device_type = "WEC"
        self.model: Optional[str] = None
        self.wec_sim_id: Optional[int] = None
        self.bus_location: Optional[int] = None

    def power_at(self, ts: pd.Timestamp) -> float:
        """Return active power at timestamp `ts` (per unit)."""
        if ts not in self.data.index:
            raise KeyError(f"Timestamp {ts} not found in WEC device data")
        return float(self.data.loc[ts, "p"])