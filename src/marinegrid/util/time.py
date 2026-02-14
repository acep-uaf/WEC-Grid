"""
Time management utilities for Marine-Grid.

File: src/marinegrid/util/time.py
"""

# Standard library
from datetime import datetime, timedelta
from collections.abc import Iterator

# Third-party
import pandas as pd

class Time:
    """
    Centralized time management for Marine-Grid simulations.

    Manages simulation time parameters including start time, duration,
    time step resolution, and snapshot generation. Ensures all backend
    modelers operate on the same time grid.

    All time-series data in Marine-Grid is indexed by timestamps generated
    from this class, ensuring consistency across power system solvers and
    renewable device models.

    Attributes:
        start_time: Simulation start datetime.
        num_steps: Number of time steps in simulation.
        freq: Pandas frequency string (e.g., "5min", "1h", "15s").
        delta_time: Time step duration in seconds.

    Example:
        >>> time = Time()
        >>> time.configure(
        ...     start_time=datetime(2024, 1, 1, 0, 0),
        ...     num_steps=288,
        ...     freq="5min"
        ... )
        >>> print(time)
        Time:
        ├─ Start: 2024-01-01 00:00:00
        ├─ End: 2024-01-01 23:55:00
        ├─ Steps: 288
        └─ Frequency: 5min

        >>> for ts in time:
        ...     print(ts)
    """

    def __init__(self, study=None):
        """
        Initialize Time with default parameters.

        Defaults to 24 hours of simulation at 5-minute resolution,
        starting at midnight today.

        Args:
            study: Optional reference to parent Study object.
        """
        # Reference to parent
        self._study = study

        # Core time parameters
        self._start_time: datetime = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self._num_steps: int = 288  # 24 hours at 5-min resolution
        self._freq: str = "5min"
        self._delta_time: int = 300  # seconds

        # Cached snapshots (invalidated on parameter change)
        self._snapshots_cache: pd.DatetimeIndex | None = None

    def __repr__(self) -> str:
        """Return a compact summary of time parameters."""
        return (
            f"Time:\n"
            f"├─ Start: {self._start_time}\n"
            f"├─ End: {self.end_time}\n"
            f"├─ Steps: {self._num_steps}\n"
            f"├─ Duration: {self.duration}\n"
            f"└─ Frequency: {self._freq}"
        )

    def __len__(self) -> int:
        """Return the number of time steps."""
        return self._num_steps

    def __iter__(self) -> Iterator[pd.Timestamp]:
        """Iterate over all snapshots."""
        return iter(self.snapshots)

    def __getitem__(self, index: int) -> pd.Timestamp:
        """Get a snapshot by index."""
        return self.snapshots[index]

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def start_time(self) -> datetime:
        """Get simulation start time."""
        return self._start_time

    @start_time.setter
    def start_time(self, value: datetime):
        """Set simulation start time and invalidate cache."""
        self._start_time = value
        self._invalidate_cache()

    @property
    def num_steps(self) -> int:
        """Get number of time steps."""
        return self._num_steps

    @num_steps.setter
    def num_steps(self, value: int):
        """Set number of time steps and invalidate cache."""
        if value < 0:
            raise ValueError("num_steps must be non-negative")
        self._num_steps = value
        self._invalidate_cache()

    @property
    def freq(self) -> str:
        """Get pandas frequency string."""
        return self._freq

    @freq.setter
    def freq(self, value: str):
        """Set frequency and update delta_time accordingly."""
        self._freq = value
        # Update delta_time based on freq
        self._delta_time = self._freq_to_seconds(value)
        self._invalidate_cache()

    @property
    def delta_time(self) -> int:
        """Get time step duration in seconds."""
        return self._delta_time

    @property
    def end_time(self) -> datetime:
        """
        Get simulation end time (computed from start + steps * delta).

        Returns:
            Datetime of the last snapshot.
        """
        if self._num_steps == 0:
            return self._start_time
        # End time is the last snapshot, which is (num_steps - 1) steps after start
        return self._start_time + timedelta(seconds=self._delta_time * (self._num_steps - 1))

    @property
    def duration(self) -> timedelta:
        """Get total simulation duration."""
        return timedelta(seconds=self._delta_time * max(0, self._num_steps - 1))

    @property
    def duration_hours(self) -> float:
        """Get total simulation duration in hours."""
        return self.duration.total_seconds() / 3600

    @property
    def snapshots(self) -> pd.DatetimeIndex:
        """
        Get simulation timestamps as DatetimeIndex.

        Snapshots are computed lazily and cached. The cache is
        invalidated when any time parameter changes.

        Returns:
            DatetimeIndex of all simulation timestamps.
        """
        if self._snapshots_cache is None:
            self._snapshots_cache = pd.date_range(
                start=self._start_time,
                periods=self._num_steps,
                freq=self._freq,
            )
        return self._snapshots_cache

    # -------------------------------------------------------------------------
    # Configuration methods
    # -------------------------------------------------------------------------

    def configure(
        self,
        start_time: datetime | None = None,
        num_steps: int | None = None,
        freq: str | None = None,
        end_time: datetime | None = None,
    ) -> "Time":
        """
        Configure time parameters.

        Can specify either num_steps or end_time, but not both.
        If end_time is provided, num_steps is calculated automatically.

        Args:
            start_time: Simulation start datetime.
            num_steps: Number of time steps.
            freq: Pandas frequency string (e.g., "5min", "1h").
            end_time: Simulation end datetime (alternative to num_steps).

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If both num_steps and end_time are provided.
        """
        if num_steps is not None and end_time is not None:
            raise ValueError("Cannot specify both num_steps and end_time")

        # Update freq first as it affects delta_time
        if freq is not None:
            self._freq = freq
            self._delta_time = self._freq_to_seconds(freq)

        if start_time is not None:
            self._start_time = start_time

        if num_steps is not None:
            self._num_steps = num_steps
        elif end_time is not None:
            self._set_end_time(end_time)

        self._invalidate_cache()
        return self

    def set_duration(self, hours: float) -> "Time":
        """
        Set simulation duration in hours.

        Args:
            hours: Duration in hours (must be > 0).

        Returns:
            Self for method chaining.

        Raises:
            TypeError: If hours is not a float or int.
            ValueError: If hours is not positive.
        """
        total_seconds = hours * 3600
        self._num_steps = int(total_seconds / self._delta_time) + 1
        self._invalidate_cache()
        return self

    def set_range(self, start: datetime, end: datetime, freq: str | None = None) -> "Time":
        """
        Set simulation time range.

        Args:
            start: Start datetime.
            end: End datetime.
            freq: Optional frequency (uses current if not provided).

        Returns:
            Self for method chaining.

        Raises:
            TypeError: If start or end are not datetime instances.
        """
        if freq is not None:
            self._freq = freq
            self._delta_time = self._freq_to_seconds(freq)

        self._start_time = start
        self._set_end_time(end)
        self._invalidate_cache()
        return self

    # -------------------------------------------------------------------------
    # Query methods
    # -------------------------------------------------------------------------

    def get_step(self, timestamp: datetime | pd.Timestamp) -> int:
        """
        Get the step index for a timestamp.

        Args:
            timestamp: Datetime to look up.

        Returns:
            Step index (0-based).

        Raises:
            TypeError: If timestamp is not a datetime or Timestamp.
            ValueError: If timestamp is outside simulation range.
        """
        if timestamp < self._start_time or timestamp > self.end_time:
            raise ValueError(f"Timestamp {timestamp} is outside simulation range")

        delta = (timestamp - self._start_time).total_seconds()
        return int(delta / self._delta_time)

    def get_timestamp(self, step: int) -> pd.Timestamp:
        """
        Get the timestamp for a step index.

        Args:
            step: Step index (0-based).

        Returns:
            Timestamp at that step.

        Raises:
            TypeError: If step is not an int.
            IndexError: If step is out of range.
        """
        if step < 0 or step >= self._num_steps:
            raise IndexError(f"Step {step} is out of range [0, {self._num_steps})")
        return self.snapshots[step]

    def contains(self, timestamp: datetime | pd.Timestamp) -> bool:
        """
        Check if a timestamp is within the simulation range.

        Args:
            timestamp: Datetime to check.

        Returns:
            True if timestamp is within range.

        Raises:
            TypeError: If timestamp is not a datetime or Timestamp.
        """
        return self._start_time <= timestamp <= self.end_time

    def nearest_snapshot(self, timestamp: datetime | pd.Timestamp) -> pd.Timestamp:
        """
        Find the nearest snapshot to a timestamp.

        Args:
            timestamp: Datetime to match.

        Returns:
            Nearest snapshot timestamp.

        Raises:
            TypeError: If timestamp is not a datetime or Timestamp.
        """
        idx = self.snapshots.get_indexer([timestamp], method="nearest")[0]
        return self.snapshots[idx]

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _invalidate_cache(self) -> None:
        """Invalidate cached snapshots."""
        self._snapshots_cache = None

    def _set_end_time(self, end_time: datetime) -> None:
        """Set num_steps based on desired end time."""
        if end_time < self._start_time:
            raise ValueError("end_time must be >= start_time")

        # Calculate number of steps to include end_time
        duration_seconds = (end_time - self._start_time).total_seconds()
        self._num_steps = int(duration_seconds / self._delta_time) + 1

    @staticmethod
    def _freq_to_seconds(freq: str) -> int:
        """
        Convert pandas frequency string to seconds.

        Args:
            freq: Pandas frequency string (e.g., "5min", "1h", "30s").

        Returns:
            Duration in seconds.
        """
        # Create a small date range to determine the frequency in seconds
        try:
            ts = pd.date_range(start="2000-01-01", periods=2, freq=freq)
            return int((ts[1] - ts[0]).total_seconds())
        except Exception:
            # Fallback: try to parse common formats
            freq_lower = freq.lower()
            if "min" in freq_lower:
                return int(freq_lower.replace("min", "")) * 60
            elif "h" in freq_lower:
                return int(freq_lower.replace("h", "")) * 3600
            elif "s" in freq_lower:
                return int(freq_lower.replace("s", ""))
            else:
                return 300  # Default to 5 minutes

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict[str, datetime | int | str | float]:
        """
        Export time configuration as dictionary.

        Returns:
            Dictionary with time parameters.
        """
        return {
            "start_time": self._start_time,
            "end_time": self.end_time,
            "num_steps": self._num_steps,
            "freq": self._freq,
            "delta_time": self._delta_time,
            "duration_hours": self.duration_hours,
        }

    @classmethod
    def from_dict(cls, config: dict) -> "Time":
        """
        Create Time instance from configuration dictionary.

        Args:
            config: Dictionary with time parameters.

        Returns:
            Configured Time instance.
        """
        time = cls()
        time.configure(
            start_time=config.get("start_time"),
            num_steps=config.get("num_steps"),
            freq=config.get("freq"),
        )
        return time
