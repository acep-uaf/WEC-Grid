"""
Grid history data container for time-series tracking.

File: src/marinegrid/util/grid_data.py
"""

# Standard library
from typing import Dict, List, Optional, Any, Union

# Third-party
import pandas as pd
import numpy as np

# Local
from .grid_instance import GridInstance, COMPONENT_SCHEMAS
class GridData:
    """
    Manager for time-series grid state history.

    Stores a collection of GridInstance snapshots indexed by timestamp,
    maintaining a historical record of the power system state throughout
    a simulation. Provides access to current state, full history, and
    time-series DataFrames for analysis.

    All power quantities (p, q) are stored in per-unit on the system MVA
    base for cross-platform consistency between different solvers.

    Attributes:
        history: Dictionary mapping timestamps to GridInstance objects.
        currentState: Most recently appended GridInstance.

    Example:
        >>> data = GridData()
        >>> data.appendState(state1)
        >>> data.appendState(state2)
        >>> print(data)
        GridData: 2 snapshots
        ├─ Time Range: 2024-01-01 12:00 → 2024-01-01 12:05
        ├─ Components: 30 buses, 6 gens, 41 lines, 21 loads
        └─ Current State: 2024-01-01 12:05

        # Get time-series for generator power
        >>> gen_p = data.get_timeseries("gen", "p")
        >>> gen_p.plot()
    """

    def __init__(self):
        """
        Initialize an empty GridData container.

        Creates empty history storage ready for GridInstance snapshots.
        """
        self._history: dict[pd.Timestamp, GridInstance] = {}
        self._currentState: GridInstance | None = None
        self._snapshots: list[pd.Timestamp] = []  # Ordered list of timestamps

    def __repr__(self) -> str:
        """Return a formatted summary of the grid data history."""
        n_snapshots = len(self._history)

        if n_snapshots == 0:
            return "GridData: Empty (no snapshots)"

        # Time range
        if self._snapshots:
            t_start = self._snapshots[0]
            t_end = self._snapshots[-1]
            time_str = f"{t_start} → {t_end}"
        else:
            time_str = "Unknown"

        # Component counts from current state
        if self._currentState is not None:
            bus_count = len(self._currentState.bus) if self._currentState.bus is not None else 0
            gen_count = len(self._currentState.gen) if self._currentState.gen is not None else 0
            line_count = len(self._currentState.line) if self._currentState.line is not None else 0
            load_count = len(self._currentState.load) if self._currentState.load is not None else 0
            comp_str = f"{bus_count} buses, {gen_count} gens, {line_count} lines, {load_count} loads"
            current_str = str(self._currentState.timestamp)
        else:
            comp_str = "No data"
            current_str = "None"

        return (
            f"GridData: {n_snapshots} snapshots\n"
            f"├─ Time Range: {time_str}\n"
            f"├─ Components: {comp_str}\n"
            f"└─ Current State: {current_str}"
        )

    def __len__(self) -> int:
        """Return the number of snapshots in history."""
        return len(self._history)

    def __getitem__(self, key: pd.Timestamp) -> GridInstance:
        """Get a GridInstance by timestamp."""
        return self._history[key]

    def __contains__(self, key: pd.Timestamp) -> bool:
        """Check if a timestamp exists in history."""
        return key in self._history

    def __iter__(self):
        """Iterate over timestamps in order."""
        return iter(self._snapshots)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def history(self) -> Dict[pd.Timestamp, GridInstance]:
        """
        Get the complete history of grid states.

        Returns:
            Dictionary mapping timestamps to GridInstance objects.
        """
        return self._history

    @property
    def currentState(self) -> GridInstance:
        """
        Get the most recent grid state.

        Returns:
            Most recently appended GridInstance or None if no states exist.
        """
        if self._currentState is None:
            raise ValueError("Current State Data is None")
        return self._currentState

    @property
    def snapshots(self) -> list[pd.Timestamp]:
        """
        Get ordered list of snapshot timestamps.

        Returns:
            List of timestamps in chronological order.
        """
        return self._snapshots.copy()

    @property
    def timestamps(self) -> pd.DatetimeIndex:
        """
        Get timestamps as a DatetimeIndex.

        Returns:
            Pandas DatetimeIndex of all snapshot times.
        """
        return pd.DatetimeIndex(self._snapshots)

    # -------------------------------------------------------------------------
    # Convenience properties for current state
    # -------------------------------------------------------------------------

    @property
    def bus(self) -> pd.DataFrame:
        """Current bus state DataFrame."""
        if self._currentState is None:
            raise ValueError("Bus Data not Avaible") 
        return self._currentState.bus

    @property
    def gen(self) -> Optional[pd.DataFrame]:
        """Current generator state DataFrame."""
        if self._currentState is None:
            return None
        return self._currentState.gen

    @property
    def line(self) -> Optional[pd.DataFrame]:
        """Current line state DataFrame."""
        if self._currentState is None:
            return None
        return self._currentState.line

    @property
    def load(self) -> Optional[pd.DataFrame]:
        """Current load state DataFrame."""
        if self._currentState is None:
            return None
        return self._currentState.load

    @property
    def transformer(self) -> Optional[pd.DataFrame]:
        """Current transformer state DataFrame."""
        if self._currentState is None:
            return None
        return self._currentState.transformer

    # -------------------------------------------------------------------------
    # State management
    # -------------------------------------------------------------------------

    def appendState(self, state: GridInstance) -> bool:
        """
        Add a new grid state to the history.

        Args:
            state: GridInstance to add to the history.

        Returns:
            True if state was successfully appended.

        Raises:
            TypeError: If state is not a GridInstance.
            ValueError: If state has no timestamp.
        """
        if not isinstance(state, GridInstance):
            raise TypeError("state must be a GridInstance")

        if state.timestamp is None:
            raise ValueError("GridInstance must have a timestamp set.")

        self._history[state.timestamp] = state
        self._currentState = state

        # Maintain ordered list of timestamps
        if state.timestamp not in self._snapshots:
            self._snapshots.append(state.timestamp)
            self._snapshots.sort()

        return True

    def getState(self, timestamp: pd.Timestamp) -> Optional[GridInstance]:
        """
        Get a grid state by timestamp.

        Args:
            timestamp: Timestamp to look up.

        Returns:
            GridInstance at that timestamp or None if not found.

        Raises:
            TypeError: If timestamp is not a pd.Timestamp.
        """
        return self._history.get(timestamp)

    def getStateAt(self, index: int) -> Optional[GridInstance]:
        """
        Get a grid state by index position.

        Args:
            index: Index in the ordered snapshot list (0 = first, -1 = last).

        Returns:
            GridInstance at that index or None if index out of range.

        Raises:
            TypeError: If index is not an int.
        """
        try:
            ts = self._snapshots[index]
            return self._history[ts]
        except IndexError:
            return None

    def clear(self) -> None:
        """Clear all history data."""
        self._history.clear()
        self._snapshots.clear()
        self._currentState = None

    # -------------------------------------------------------------------------
    # Time-series data access
    # -------------------------------------------------------------------------

    def get_timeseries(
        self,
        component: str,
        column: str,
        name_column: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Build a time-series DataFrame for a specific component variable.

        Creates a DataFrame with timestamps as rows and component IDs/names
        as columns, containing the values of the specified variable across
        all snapshots.

        Args:
            component: Component type ("bus", "gen", "line", "load", "transformer").
            column: Column name to extract (e.g., "p", "v_mag", "loading_pct").
            name_column: Optional column to use for column labels instead of IDs.
                         If None, uses "{component}_name" if available.

        Returns:
            DataFrame with timestamps as index and component IDs/names as columns.

        Raises:
            ValueError: If component is not a valid component type.

        Example:
            >>> gen_power = data.get_timeseries("gen", "p")
            >>> bus_voltage = data.get_timeseries("bus", "v_mag")
            >>> line_loading = data.get_timeseries("line", "loading_pct")
        """
        if not self._history:
            return pd.DataFrame()

        # Determine the name column to use for labels
        if name_column is None:
            name_column = f"{component}_name"

        # Get schema for ID column
        schema = COMPONENT_SCHEMAS.get(component)
        id_column = schema.id_column if schema else component

        rows = {}
        for ts in self._snapshots:
            state = self._history[ts]
            df = getattr(state, component, None)

            if df is None or df.empty or column not in df.columns:
                continue

            # Use names as column labels if available, otherwise use IDs
            if name_column in df.columns:
                labels = df[name_column].values
            elif id_column in df.columns:
                labels = df[id_column].values
            else:
                labels = df.index.values

            rows[ts] = pd.Series(df[column].values, index=labels)

        if not rows:
            return pd.DataFrame()

        result = pd.DataFrame(rows).T
        result.index.name = "timestamp"
        return result

    def get_component_history(self, component: str) -> Dict[str, pd.DataFrame]:
        """
        Get all time-series data for a component type.

        Returns a dictionary where keys are variable names and values are
        DataFrames with the time-series for that variable.

        Args:
            component: Component type ("bus", "gen", "line", "load", "transformer").

        Returns:
            Dictionary mapping variable names to time-series DataFrames.

        Raises:
            ValueError: If component is not a valid component type.

        Example:
            >>> bus_data = data.get_component_history("bus")
            >>> bus_data["v_mag"].plot()  # Plot voltage magnitudes over time
            >>> bus_data["p"].plot()      # Plot power injections over time
        """
        if not self._history:
            return {}

        # Get first non-empty state to determine available columns
        sample_df = None
        for state in self._history.values():
            df = getattr(state, component, None)
            if df is not None and not df.empty:
                sample_df = df
                break

        if sample_df is None:
            return {}

        # Build time-series for each numeric column
        result = {}
        for col in sample_df.columns:
            # Skip ID and name columns
            if col.endswith("_name") or col in ["bus", "gen", "line", "load", "transformer"]:
                continue

            ts_df = self.get_timeseries(component, col)
            if not ts_df.empty:
                result[col] = ts_df

        return result

    # -------------------------------------------------------------------------
    # Analysis helpers
    # -------------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """
        Generate a summary of the grid data history.

        Returns:
            Dictionary with summary statistics.
        """
        result = {
            "snapshot_count": len(self._history),
            "start_time": self._snapshots[0] if self._snapshots else None,
            "end_time": self._snapshots[-1] if self._snapshots else None,
        }

        if self._currentState is not None:
            result.update(self._currentState.summary())

        return result

    def get_statistics(self, component: str, column: str) -> pd.DataFrame:
        """
        Calculate statistics for a variable across all snapshots.

        Args:
            component: Component type ("bus", "gen", "line", "load", "transformer").
            column: Column name to analyze.

        Returns:
            DataFrame with min, max, mean, std for each component.

        Raises:
            ValueError: If component is not a valid component type.
        """
        ts_df = self.get_timeseries(component, column)
        if ts_df.empty:
            return pd.DataFrame()

        stats = pd.DataFrame({
            "min": ts_df.min(),
            "max": ts_df.max(),
            "mean": ts_df.mean(),
            "std": ts_df.std(),
        })
        return stats

    def get_voltage_violations(
        self,
        v_min: float = 0.95,
        v_max: float = 1.05
    ) -> pd.DataFrame:
        """
        Find voltage violations across all snapshots.

        Args:
            v_min: Minimum acceptable voltage in per-unit (must be > 0).
            v_max: Maximum acceptable voltage in per-unit (must be > 0).

        Returns:
            DataFrame with violation details (timestamp, bus, voltage, type).

        Raises:
            TypeError: If v_min or v_max are not float/int.
            ValueError: If v_min or v_max are not positive.
        """
        violations = []

        for ts in self._snapshots:
            state = self._history[ts]
            if state.bus is None or "v_mag" not in state.bus.columns:
                continue

            bus_df = state.bus

            # Check undervoltage
            under = bus_df[bus_df["v_mag"] < v_min]
            for _, row in under.iterrows():
                violations.append({
                    "timestamp": ts,
                    "bus": row.get("bus", row.name),
                    "bus_name": row.get("bus_name", ""),
                    "v_mag": row["v_mag"],
                    "violation_type": "undervoltage",
                })

            # Check overvoltage
            over = bus_df[bus_df["v_mag"] > v_max]
            for _, row in over.iterrows():
                violations.append({
                    "timestamp": ts,
                    "bus": row.get("bus", row.name),
                    "bus_name": row.get("bus_name", ""),
                    "v_mag": row["v_mag"],
                    "violation_type": "overvoltage",
                })

        return pd.DataFrame(violations)

    def get_line_overloads(self, threshold: float = 100.0) -> pd.DataFrame:
        """
        Find line overloads across all snapshots.

        Args:
            threshold: Overload threshold as percentage of rating (must be > 0).

        Returns:
            DataFrame with overload details (timestamp, line, loading).

        Raises:
            TypeError: If threshold is not a float/int.
            ValueError: If threshold is not positive.
        """
        overloads = []

        for ts in self._snapshots:
            state = self._history[ts]
            if state.line is None:
                continue

            # Check for loading_pct or line_pct column
            loading_col = None
            if "loading_pct" in state.line.columns:
                loading_col = "loading_pct"
            elif "line_pct" in state.line.columns:
                loading_col = "line_pct"

            if loading_col is None:
                continue

            line_df = state.line
            over = line_df[line_df[loading_col] > threshold]

            for _, row in over.iterrows():
                overloads.append({
                    "timestamp": ts,
                    "line": row.get("line", row.name),
                    "line_name": row.get("line_name", ""),
                    "loading_pct": row[loading_col],
                })

        return pd.DataFrame(overloads)

    # -------------------------------------------------------------------------
    # Export methods
    # -------------------------------------------------------------------------

    def to_dataframes(self) -> Dict[str, pd.DataFrame]:
        """
        Export all time-series data as DataFrames.

        Returns:
            Dictionary with keys like "bus_p", "bus_v_mag", "gen_p", etc.
        """
        result = {}

        for component in ["bus", "gen", "line", "load", "transformer"]:
            component_data = self.get_component_history(component)
            for var_name, df in component_data.items():
                key = f"{component}_{var_name}"
                result[key] = df

        return result

    def to_dict(self) -> Dict[pd.Timestamp, Dict[str, pd.DataFrame]]:
        """
        Export history as nested dictionary.

        Returns:
            Dictionary mapping timestamps to component DataFrames.
        """
        result = {}
        for ts, state in self._history.items():
            result[ts] = state.to_dict()
        return result
