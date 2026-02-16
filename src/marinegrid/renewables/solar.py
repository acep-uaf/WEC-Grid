"""
Solar device model.

File: src/marinegrid/renewables/solar.py
"""

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