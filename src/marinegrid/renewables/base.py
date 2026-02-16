"""
Renewable Device Abstract Base Class.

Defines ``RenewableDevice``, the ABC that all device types (WEC, wind,
solar, tidal, storage) extend. Guarantees a uniform interface for
time-series power access so that farms and the simulation loop can
treat every device type interchangeably.

File: src/marinegrid/renewables/base.py
"""

# Standard library
from abc import ABC

# Third-party
import numpy as np
import pandas as pd

class RenewableDevice(ABC):
    """
    Abstract base class for all renewable energy devices.
    
    Defines the interface contract for renewable energy devices including
    WECs, wind turbines, solar panels, tidal generators, and storage systems.
    Provides standardized access to device power output time series.
    
    Attributes:
        data: DataFrame containing time-series power data (p, q columns in pu).
        raw_data: DataFrame containing full-resolution data from external
            simulations, before downsampling. Has a 'time' column in seconds.
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
        self.raw_data: pd.DataFrame = pd.DataFrame()
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
        
    # -------------------------------------------------------------------------
    # Downsampling
    # -------------------------------------------------------------------------

    def downsample(self, period_seconds: float = 300.0) -> pd.DataFrame:
        """
        Downsample full-resolution raw data to a coarser time step.

        Averages high-resolution data stored in ``raw_data`` over
        non-overlapping windows of ``period_seconds``. Requires
        ``raw_data`` to contain a ``time`` column in seconds.

        Args:
            period_seconds: Target sampling period in seconds.
                Default is 300 (5 minutes).

        Returns:
            Downsampled DataFrame with end-aligned timestamps and the
            same data columns as ``raw_data``.

        Raises:
            ValueError: If ``raw_data`` is empty or ``period_seconds``
                is not larger than the original time step.
            KeyError: If ``raw_data`` has no ``time`` column.
        """
        if self.raw_data is None or self.raw_data.empty:
            raise ValueError("No raw_data available for downsampling")

        if "time" not in self.raw_data.columns:
            raise KeyError("raw_data must contain a 'time' column for downsampling")

        df = self.raw_data
        time_values = df["time"].values

        if len(time_values) < 2:
            return df.copy()

        old_dt = float(time_values[1] - time_values[0])

        if period_seconds <= old_dt:
            raise ValueError(
                f"period_seconds ({period_seconds}s) must be larger than "
                f"original timestep ({old_dt}s)"
            )

        # Number of original samples per downsampled window
        t_sample = int(period_seconds / old_dt)
        n_samples = len(df) // t_sample

        if n_samples <= 0:
            return df.copy()

        data_columns = [col for col in df.columns if col != "time"]
        downsampled: dict[str, np.ndarray] = {
            "time": np.zeros(n_samples),
        }
        for col in data_columns:
            downsampled[col] = np.zeros(n_samples)

        for i in range(n_samples):
            start_idx = i * t_sample
            end_idx = min((i + 1) * t_sample, len(df))

            # End-aligned time stamp
            downsampled["time"][i] = float(df["time"].iloc[end_idx - 1])

            for col in data_columns:
                downsampled[col][i] = df[col].iloc[start_idx:end_idx].mean()

        return pd.DataFrame(downsampled)

    # -------------------------------------------------------------------------
    # Power Query
    # -------------------------------------------------------------------------

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
        if ts not in self.data.index:
            raise KeyError(f"Timestamp {ts} not found in {self.device_type or self.__class__.__name__} device data")
        return float(self.data.loc[ts, "p"])