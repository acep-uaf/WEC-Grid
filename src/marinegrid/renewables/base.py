"""
Renewable Device Abstract Base Class.

Defines ``RenewableDevice``, the ABC that all device types (WEC, wind,
solar, tidal, storage) extend. Guarantees a uniform interface for
time-series power access so that farms and the simulation loop can
treat every device type interchangeably.

File: src/marinegrid/renewables/base.py
"""

# Standard library
from abc import ABC, abstractmethod

# Third-party
import pandas as pd

class RenewableDevice(ABC):
    """
    Abstract base class for all renewable energy devices.
    
    Defines the interface contract for renewable energy devices including
    WECs, wind turbines, solar panels, tidal generators, and storage systems.
    Provides standardized access to device power output time series.
    
    Attributes:
        data: DataFrame containing time-series power data (p, q columns in pu).
        device_name: Human-readable device identifier.
        device_type: Type of device (e.g., "WEC", "Wind", "Solar").
        device_id: Unique identifier for the device.
        capacity: Rated capacity in per unit.
        bus_location: Bus number where device connects to grid.
    """
    
    def __init__(self):
        """
        Initialize a renewable device with default attributes.
        
        Subclasses should call super().__init__() and then set
        device-specific attributes.
        """
        # Class objects
        
        # Class attributes
        self.data: pd.DataFrame = pd.DataFrame()
        self.device_name: str = ""
        self.device_type: str = ""
        self.device_id: str = ""
        self.capacity: float = 0.0  # in pu
        self.bus_location: int | None = None
    
    def __repr__(self) -> str:
        """Return a compact string describing the device."""
        return (
            f"{self.__class__.__name__}:\n"
            f"├─ name: {self.device_name!r}\n"
            f"├─ type: {self.device_type!r}\n"
            f"├─ capacity: {self.capacity} pu\n"
            f"├─ bus: {self.bus_location}\n"
            f"└─ data rows: {len(self.data)}"
        )
        
    @abstractmethod
    def power_at(self, ts: pd.Timestamp) -> float:
        """
        Get power output at a specific timestamp.
        
        Args:
            ts: Timestamp to query power output.

        Returns:
            Active power output at the given timestamp in per unit.
            
        Raises:
            KeyError: If timestamp is not in device data.
        """
        pass