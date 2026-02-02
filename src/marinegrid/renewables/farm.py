"""
Renewable energy farm container.

File: src/marinegrid/renewables/farm.py
"""

# Standard library
from typing import List, Optional

# Third-party


# Local
from .base import RenewableDevice


class RenewableEnergyFarm:
    """
    Collection of renewable devices connected to a single bus.
    
    Attributes:
        farm_name: Human-readable identifier for the farm.
        devices: List of RenewableDevice instances.
        bus_location: Bus number where the farm connects.
        size: Number of devices in the farm.
    """
    
    def __init__(
        self,
        farm_name: str = "",
        bus_location: Optional[int] = None,
        size: int = 0,
        devices: Optional[List[RenewableDevice]] = None,
    ):
        """Initialize a renewable energy farm container."""
        self.farm_name = farm_name
        self.bus_location = bus_location
        self.size = size
        self.devices: List[RenewableDevice] = devices or []
