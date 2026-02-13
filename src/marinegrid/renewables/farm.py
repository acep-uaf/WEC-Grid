"""
Renewable energy farm container.

File: src/marinegrid/renewables/farm.py
"""

# Third-party
import pandas as pd

# Local
from .base import RenewableDevice


class RenewableEnergyFarm:
    """
    Generic renewable energy farm that can hold mixed device types.

    A farm represents a collection of renewable energy devices (WEC, wind,
    solar, tidal, storage) connected to a single bus in the power grid.
    Provides aggregate power output across all devices for use in
    time-series simulation.

    Attributes:
        farm_name: Human-readable identifier for the farm.
        bus_location: Bus number where the farm connects.
        connecting_bus: Existing grid bus to link the farm into.
        size: Number of devices in the farm.
        devices: List of RenewableDevice instances.
        gen_name: Generator name in the grid model.
        sbase: Base power in MVA for per-unit conversion.

    Example:
        >>> farm = RenewableEnergyFarm(farm_name="Hybrid_Farm", bus_location=100)
        >>> farm.add_device(wind_device)
        >>> farm.add_device(solar_device)
        >>> total_p = farm.power_at_snapshot(timestamp)
    """

    def __init__(
        self,
        farm_name: str = "",
        bus_location: int | None = None,
        connecting_bus: int | None = None,
        size: int = 0,
        devices: list[RenewableDevice] | None = None,
        gen_name: str = "",
        sbase: float = 100.0,
    ) -> None:
        """
        Initialize a renewable energy farm container.

        Args:
            farm_name: Label for the farm.
            bus_location: Bus number where the farm connects.
            connecting_bus: Existing bus to link the farm into the network.
            size: Number of devices in the farm.
            devices: Pre-existing list of devices to include.
            gen_name: Generator name in the grid model.
            sbase: Base power in MVA for per-unit values.
        """
        self.farm_name = farm_name
        self.bus_location = bus_location
        self.connecting_bus = connecting_bus
        self.size = size
        self.devices: list[RenewableDevice] = devices or []
        self.gen_name = gen_name
        self.sbase = sbase

    def __repr__(self) -> str:
        """Return a compact summary of the farm."""
        device_types = {}
        for d in self.devices:
            dt = d.device_type or "Unknown"
            device_types[dt] = device_types.get(dt, 0) + 1
        type_str = ", ".join(f"{v} {k}" for k, v in device_types.items()) if device_types else "empty"

        return (
            f"RenewableEnergyFarm:\n"
            f"├─ name: {self.farm_name!r}\n"
            f"├─ devices: {len(self.devices)} ({type_str})\n"
            f"├─ bus_location: {self.bus_location}\n"
            f"├─ connecting_bus: {self.connecting_bus}\n"
            f"└─ sbase: {self.sbase} MVA"
        )

    def __len__(self) -> int:
        """Return number of devices in the farm."""
        return len(self.devices)

    def __iter__(self):
        """Iterate over devices in the farm."""
        return iter(self.devices)

    def add_device(self, device: RenewableDevice) -> None:
        """
        Add a device to the farm.

        Args:
            device: RenewableDevice instance to add.
        """
        self.devices.append(device)

    def remove_device(self, device: RenewableDevice) -> None:
        """
        Remove a device from the farm.

        Args:
            device: RenewableDevice instance to remove.

        Raises:
            ValueError: If device is not in the farm.
        """
        self.devices.remove(device)

    def power_at_snapshot(self, timestamp: pd.Timestamp) -> float:
        """
        Return total active power at a simulation timestamp.

        Sums the power output from all devices in the farm at the given
        timestamp. Power is returned in per-unit on the system MVA base.

        Args:
            timestamp: Time at which to read device power.

        Returns:
            Sum of device powers in per-unit on sbase.
        """
        total_power = 0.0
        for device in self.devices:
            if (
                device.data is not None
                and not device.data.empty
                and timestamp in device.data.index
                and "p" in device.data.columns
            ):
                total_power += device.data.at[timestamp, "p"]
        return total_power

    def get_power_timeseries(self) -> pd.DataFrame:
        """
        Get aggregate power time series for the entire farm.

        Returns:
            DataFrame with timestamp index and columns for total p and q
            in per-unit. Returns empty DataFrame if no devices have data.
        """
        if not self.devices:
            return pd.DataFrame()

        # Find first device with data
        result = None
        for device in self.devices:
            if device.data is not None and not device.data.empty:
                cols = [c for c in ["p", "q"] if c in device.data.columns]
                if cols:
                    result = device.data[cols].copy()
                    break

        if result is None:
            return pd.DataFrame()

        # Sum across remaining devices
        for device in self.devices:
            if device.data is None or device.data.empty:
                continue
            if device.data is result:
                continue
            for col in result.columns:
                if col in device.data.columns:
                    result[col] = result[col] + device.data[col]

        return result
