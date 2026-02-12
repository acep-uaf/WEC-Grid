"""
Energy storage device model.

File: src/marinegrid/renewables/storage.py
"""

# Standard library
from typing import Optional

# Third-party
import pandas as pd

# Local
from .base import RenewableDevice
class StorageDevice(RenewableDevice):
    """
    Energy storage system with time-series power data.
    
    Attributes:
        storage_model: Storage system model name.
        energy_capacity: Energy capacity in MWh.
        max_charge_rate: Maximum charge rate in MW.
        max_discharge_rate: Maximum discharge rate in MW.
    """

    def __init__(self) -> None:
        """Initialize a storage device with defaults."""
        super().__init__()
        self.device_type = "Storage"
        self.storage_model: Optional[str] = None
        self.energy_capacity: Optional[float] = None
        self.max_charge_rate: Optional[float] = None
        self.max_discharge_rate: Optional[float] = None

    def power_at(self, ts: pd.Timestamp) -> float:
        """Return net power at timestamp `ts` (per unit)."""
        if ts not in self.data.index:
            raise KeyError(f"Timestamp {ts} not found in storage device data")
        return float(self.data.loc[ts, "p"])