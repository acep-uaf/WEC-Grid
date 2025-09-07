# File: src/wecgrid/util/time.py

"""Time management utilities for WEC-Grid."""

from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd


@dataclass
class WECGridTime:
    """Manage simulation time for WEC-Grid.

    Attributes:
        start_time: Simulation start timestamp.
        num_steps: Number of time steps.
        freq: Pandas frequency string (e.g., ``"5min"``).
        delta_time: Step size in seconds.
    """

    start_time: datetime = field(
        default_factory=lambda: datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    )
    # sim_length: int = 288
    num_steps: int = 288
    freq: str = "5min"
    delta_time: int = 300  # seconds

    def __post_init__(self):
        """Initialize derived simulation parameters after dataclass construction."""
        self._update_sim_stop()

    def _update_sim_stop(self):
        """Update simulation stop time based on current parameters."""
        self.sim_stop = self.snapshots[-1] if self.num_steps > 0 else self.start_time

    @property
    def snapshots(self) -> pd.DatetimeIndex:
        """Return simulation timestamps."""
        return pd.date_range(
            start=self.start_time,
            periods=self.num_steps,
            freq=self.freq,
        )

    def update(
        self, *, start_time: datetime = None, num_steps: int = None, freq: str = None
    ):
        """Update simulation time parameters with automatic recalculation.

        Args:
            start_time (datetime, optional): New simulation start timestamp.
            num_steps (int, optional): New number of simulation time steps.
            freq (str, optional): New pandas frequency string for time intervals.
        """
        if start_time is not None:
            self.start_time = start_time
        if num_steps is not None:
            self.num_steps = num_steps
        if freq is not None:
            self.freq = freq
        self._update_sim_stop()

    def set_end_time(self, end_time: datetime):
        """Set simulation duration by specifying the end time.

        Args:
            end_time: Desired simulation end timestamp (should be ≥ start_time).
        """
        self.num_steps = len(
            pd.date_range(start=self.start_time, end=end_time, freq=self.freq)
        )
        self.sim_stop = end_time

    def __repr__(self) -> str:
        """Return concise string representation of the time configuration."""
        return (
            f"WECGridTime:\n"
            f"├─ start_time: {self.start_time}\n"
            f"├─ sim_stop:   {self.sim_stop}\n"
            f"├─ num_steps: {self.num_steps} steps\n"
            f"└─ frequency:  {self.freq}"
        )
