"""
Tidal device model.

File: src/marinegrid/renewables/tidal.py
"""

# Local
from .base import RenewableDevice


class TidalDevice(RenewableDevice):
    """
    Tidal energy converter with time-series power output.
    
    Attributes:
        turbine_model: Tidal turbine model name.
        rotor_diameter: Rotor diameter in meters.
        depth: Installation depth in meters.
    """

    def __init__(self) -> None:
        """Initialize a tidal energy device with defaults."""
        super().__init__()
        self.device_type = "Tidal"
        self.turbine_model: str | None = None
        self.rotor_diameter: float | None = None
        self.depth: float | None = None