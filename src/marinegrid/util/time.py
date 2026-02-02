"""
Time management utilities for Marine-Grid.

File: src/marinegrid/util/time.py
"""

# Standard library
from datetime import datetime, timedelta
from typing import Optional

# Third-party
import pandas as pd

# Local


class Time:
    """
    Centralized time management for Marine-Grid simulations.

    Manages simulation time parameters including start time, duration,
    time step resolution, and snapshot generation. Ensures all backend
    modelers operate on the same time grid.

    Attributes:
        study: Reference to parent Study object.
        start_time: Simulation start datetime.
        num_steps: Number of time steps in simulation.
        freq: Pandas frequency string (e.g., "5min").
        delta_time: Time step duration in seconds.
        end_time: Computed simulation end datetime.
        snapshots: Pandas DatetimeIndex of all simulation timestamps.
    """

    def __init__(self, study=None):
        """
        Initialize Time with default parameters.

        Args:
            study: Optional reference to parent Study object.
        """
        # Class objects
        self.study = study

        # Class attributes
        self.start_time: datetime = datetime(2020, 1, 1, 0, 0, 0)
        self.num_steps: int = 288  # 24 hours at 5-min resolution
        self.freq: str = "5min"
        self.delta_time: int = 300  # seconds
        self.end_time: Optional[datetime] = None
        self.snapshots: Optional[pd.DatetimeIndex] = None

        # Compute derived values
        self._update_derived()

    def __repr__(self) -> str:
        """Return a compact summary of time parameters."""
        return (
            f"Time:\n"
            f"├─ Start: {self.start_time}\n"
            f"├─ End: {self.end_time}\n"
            f"├─ Steps: {self.num_steps}\n"
            f"└─ Frequency: {self.freq}"
        )

    def _update_derived(self):
        """
        Compute end time and snapshots from base parameters.

        Calculates the end_time based on start_time, num_steps, and
        delta_time, and generates the complete snapshot DatetimeIndex.
        """
        self.end_time = self.start_time + timedelta(seconds=self.delta_time * self.num_steps)
        self.snapshots = pd.date_range(
            start=self.start_time,
            periods=self.num_steps,
            freq=self.freq
        )

    def update(self, **kwargs):
        """
        Update time parameters and recompute derived values.

        Args:
            **kwargs: Time parameters to update (start_time, num_steps, freq, delta_time).
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self._update_derived()

    def set_by_end_time(self, end_time: datetime):
        """
        Set num_steps based on desired end time.

        Args:
            end_time: Desired simulation end datetime.
        """
        duration = (end_time - self.start_time).total_seconds()
        self.num_steps = int(duration / self.delta_time)
        self._update_derived()
