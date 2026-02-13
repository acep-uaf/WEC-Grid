"""
Wave energy converter device model.

File: src/marinegrid/renewables/wec.py
"""

# Standard library
from typing import TYPE_CHECKING

# Third-party
import pandas as pd
import numpy as np

# Local
from .base import RenewableDevice
from .farm import RenewableEnergyFarm
if TYPE_CHECKING:
    from ..util.time import Time
    from ..tool.database import Database


class WECDevice(RenewableDevice):
    """
    Wave Energy Converter device with time-series power output.

    Represents a single WEC unit with power output data indexed by timestamp.
    Power values are stored in per-unit on the system MVA base.

    Attributes:
        model: WEC model name (e.g., "RM3", "LUPA").
        wec_sim_id: Simulation identifier in the database.
        bus_location: Bus number where the device connects.

    Example:
        >>> device = WECDevice()
        >>> device.device_name = "RM3_1_0"
        >>> device.model = "RM3"
        >>> device.data = power_dataframe  # Index: timestamps, Columns: p, q
        >>> power = device.power_at(pd.Timestamp("2024-01-01 12:00"))
    """

    def __init__(
        self,
        name: str = "",
        data: pd.DataFrame | None = None,
        bus_location: int | None = None,
        model: str | None = None,
        wec_sim_id: int | None = None,
    ):
        """
        Initialize a WEC device.

        Args:
            name: Device identifier, typically "{model}_{sim_id}_{index}".
            data: DataFrame with timestamp index and p, q columns (per-unit).
            bus_location: Bus number for grid connection.
            model: WEC model name (e.g., "RM3").
            wec_sim_id: Simulation identifier in the database.
        """
        super().__init__()
        self.device_type = "WEC"
        self.device_name = name
        self.model = model
        self.wec_sim_id = wec_sim_id
        self.bus_location = bus_location

        if data is not None:
            self.data = data

    def __repr__(self) -> str:
        """Return a compact string describing the device."""
        return (
            f"WECDevice:\n"
            f"├─ name: {self.device_name!r}\n"
            f"├─ model: {self.model!r}\n"
            f"├─ bus_location: {self.bus_location}\n"
            f"├─ wec_sim_id: {self.wec_sim_id}\n"
            f"└─ data rows: {len(self.data)}"
        )

    def power_at(self, ts: pd.Timestamp) -> float:
        """
        Return active power at timestamp in per-unit.

        Args:
            ts: Timestamp to query power output.

        Returns:
            Active power output at the given timestamp in per-unit.

        Raises:
            TypeError: If ts is not a pd.Timestamp.
            KeyError: If timestamp is not in device data.
        """
        if ts not in self.data.index:
            raise KeyError(f"Timestamp {ts} not found in WEC device data")
        return float(self.data.loc[ts, "p"])

    def reactive_power_at(self, ts: pd.Timestamp) -> float:
        """
        Return reactive power at timestamp in per-unit.

        Args:
            ts: Timestamp to query reactive power output.

        Returns:
            Reactive power output at the given timestamp in per-unit.

        Raises:
            TypeError: If ts is not a pd.Timestamp.
            KeyError: If timestamp is not in device data.
        """
        if ts not in self.data.index:
            raise KeyError(f"Timestamp {ts} not found in WEC device data")
        return float(self.data.loc[ts, "q"])


class WECFarm(RenewableEnergyFarm):
    """
    Farm of WEC devices with database loading and downsampling.

    Extends RenewableEnergyFarm with WEC-specific behavior: loading
    simulation data from a database, downsampling high-resolution
    WEC-Sim output to the grid simulation frequency, and managing
    device scaling.

    Attributes:
        database: Database interface used to fetch WEC-Sim results.
        time: Time manager providing simulation snapshots.
        wec_sim_id: Simulation ID used for database queries.
        model: WEC device model name (populated from database).
        farm_id: Optional integer identifier for the farm.
        scaling_factor: Linear multiplier applied to device power.

    Example:
        >>> farm = WECFarm(
        ...     farm_name="Humboldt_WEC",
        ...     database=db,
        ...     time=study.time,
        ...     wec_sim_id=1,
        ...     bus_location=100,
        ...     size=10,
        ... )
        >>> power = farm.power_at_snapshot(pd.Timestamp("2024-01-01 12:00"))
    """

    def __init__(
        self,
        farm_name: str,
        database: "Database",
        time: "Time",
        wec_sim_id: int,
        bus_location: int,
        connecting_bus: int = 1,
        gen_name: str = "",
        size: int = 1,
        farm_id: int | None = None,
        sbase: float = 100.0,
        scaling_factor: float = 1.0,
    ):
        """
        Initialize the farm and load associated WEC-Sim data.

        Args:
            farm_name: Label for the farm.
            database: Interface used to query WEC-Sim results.
            time: Time manager providing simulation snapshots.
            wec_sim_id: Identifier of the WEC simulation to load.
            bus_location: Bus number where the farm connects.
            connecting_bus: Existing bus to link the farm into the network.
            gen_name: Generator name in the grid model.
            size: Number of devices in the farm.
            farm_id: Optional integer identifier for the farm.
            sbase: Base power in MVA for per-unit values.
            scaling_factor: Linear multiplier applied to device power.

        Raises:
            RuntimeError: If WEC simulation data is missing.
            ValueError: If the database returns empty results.
        """
        super().__init__(
            farm_name=farm_name,
            bus_location=bus_location,
            connecting_bus=connecting_bus,
            size=size,
            gen_name=gen_name,
            sbase=sbase,
        )
        self.database = database
        self.time = time
        self.wec_sim_id = wec_sim_id
        self.model: str = ""
        self.farm_id = farm_id
        self.scaling_factor = scaling_factor

        self._prepare_farm()

    def __repr__(self) -> str:
        """Return a compact string describing the farm."""
        return (
            f"WECFarm:\n"
            f"├─ name: {self.farm_name!r}\n"
            f"├─ size: {len(self.devices)}\n"
            f"├─ model: {self.model!r}\n"
            f"├─ bus_location: {self.bus_location}\n"
            f"├─ connecting_bus: {self.connecting_bus}\n"
            f"├─ wec_sim_id: {self.wec_sim_id}\n"
            f"└─ sbase: {self.sbase} MVA"
        )

    def _prepare_farm(self) -> None:
        """
        Load WEC-Sim data and create device objects.

        Queries the database for the selected simulation, downsamples the
        power data to the grid simulation frequency, and instantiates
        `size` WECDevice objects.

        Raises:
            RuntimeError: If simulation data is missing or invalid.
        """
        # Get model type from wec_simulations table
        model_query = "SELECT model_type FROM wec_simulations WHERE wec_sim_id = ?"
        model_result = self.database.query(model_query, params=(self.wec_sim_id,))

        if not model_result:
            raise RuntimeError(
                f"No simulation metadata found for wec_sim_id={self.wec_sim_id}"
            )

        # Extract model name from result
        if isinstance(model_result, list) and len(model_result) > 0:
            first_row = model_result[0]
            if isinstance(first_row, (list, tuple)):
                self.model = first_row[0]
            elif isinstance(first_row, dict):
                self.model = first_row["model_type"]
            else:
                self.model = str(first_row)
        else:
            raise RuntimeError(
                f"Invalid model data returned for wec_sim_id={self.wec_sim_id}"
            )

        # Verify simulation exists
        sim_check_query = "SELECT wec_sim_id FROM wec_simulations WHERE wec_sim_id = ?"
        sim_result = self.database.query(sim_check_query, params=(self.wec_sim_id,))

        if not sim_result:
            raise RuntimeError(
                f"No WEC simulation found for wec_sim_id={self.wec_sim_id}. "
                "Run WEC-Sim first."
            )

        # Load WEC power data
        power_query = """
            SELECT time_sec as time, p_w as p, q_var as q, wave_elevation_m as eta
            FROM wec_power_results
            WHERE wec_sim_id = ?
            ORDER BY time_sec
        """
        df_full = self.database.query(
            power_query, params=(self.wec_sim_id,), return_type="df"
        )

        if df_full is None or df_full.empty:
            raise RuntimeError(
                f"No WEC power data found for wec_sim_id={self.wec_sim_id}"
            )

        # Apply scaling factor
        df_full["p"] = self.scaling_factor * df_full["p"]
        df_full["q"] = self.scaling_factor * df_full["q"]

        # Downsample to grid simulation frequency
        df_downsampled = self.downsample(df_full, self.time.delta_time)

        # Apply timestamp index aligned with simulation time
        df_downsampled["snapshots"] = pd.date_range(
            start=self.time.start_time,
            periods=len(df_downsampled),
            freq=self.time.freq,
        )
        df_downsampled.set_index("snapshots", inplace=True)

        # Convert Watts to per-unit
        # WEC data stored in Watts → MW (÷1e6) → per-unit (÷sbase_MVA)
        df_downsampled["p"] = df_downsampled["p"] / (self.sbase * 1e6)
        df_downsampled["q"] = df_downsampled["q"] / (self.sbase * 1e6)

        # Create device instances
        for i in range(self.size):
            name = f"{self.model}_{self.wec_sim_id}_{i}"
            device = WECDevice(
                name=name,
                data=df_downsampled.copy(),
                bus_location=self.bus_location,
                model=self.model,
                wec_sim_id=self.wec_sim_id,
            )
            self.devices.append(device)

    @staticmethod
    def downsample(
        wec_df: pd.DataFrame,
        new_sample_period: float,
        timeshift: int = 0,
    ) -> pd.DataFrame:
        """
        Downsample WEC time series to a coarser resolution.

        Averages high-resolution WEC-Sim output to match the grid simulation
        time step. This is necessary because WEC-Sim typically runs at
        sub-second resolution while grid simulations use 5-minute or longer
        time steps.

        Args:
            wec_df: Input data with a "time" column in seconds.
            new_sample_period: Desired sampling period in seconds (must be > 0).
            timeshift: 0 for end-aligned timestamps, 1 for centered.

        Returns:
            Downsampled DataFrame with the same columns.

        Raises:
            TypeError: If wec_df is not a DataFrame or new_sample_period is not numeric.
            ValueError: If new_sample_period is not positive or smaller than original step.
            KeyError: If the "time" column is missing.
        """
        if "time" not in wec_df.columns:
            raise KeyError("DataFrame must contain 'time' column for downsampling")

        time_values = wec_df["time"].values
        if len(time_values) < 2:
            return wec_df.copy()

        # Calculate original time step
        old_dt = time_values[1] - time_values[0]

        if new_sample_period <= old_dt:
            raise ValueError(
                f"New sample period ({new_sample_period}s) must be larger than "
                f"original timestep ({old_dt}s)"
            )

        # Calculate sampling parameters
        t_sample = int(new_sample_period / old_dt)
        new_sample_size = int((time_values[-1] - time_values[0]) / new_sample_period)

        if new_sample_size <= 0:
            return wec_df.copy()

        # Create new time grid
        if timeshift == 1:
            # Center-aligned timestamps
            new_times = np.arange(
                new_sample_period / 2,
                new_sample_size * new_sample_period + new_sample_period / 2,
                new_sample_period,
            )
        else:
            # End-aligned timestamps
            new_times = np.arange(
                new_sample_period,
                (new_sample_size + 1) * new_sample_period,
                new_sample_period,
            )

        # Ensure we don't exceed original time range
        new_times = new_times[new_times <= time_values[-1]]
        new_sample_size = len(new_times)

        # Initialize downsampled data
        downsampled_data = {"time": new_times}

        # Downsample each data column (excluding time)
        data_columns = [col for col in wec_df.columns if col != "time"]

        for col in data_columns:
            downsampled_values = np.zeros(new_sample_size)

            for i in range(new_sample_size):
                if i == 0:
                    start_idx = 0
                    end_idx = min(t_sample, len(wec_df))
                else:
                    start_idx = (i - 1) * t_sample
                    end_idx = min(i * t_sample, len(wec_df))

                if start_idx < len(wec_df) and end_idx > start_idx:
                    downsampled_values[i] = wec_df[col].iloc[start_idx:end_idx].mean()
                else:
                    downsampled_values[i] = 0.0

            downsampled_data[col] = downsampled_values

        return pd.DataFrame(downsampled_data)

    def reactive_power_at_snapshot(self, timestamp: pd.Timestamp) -> float:
        """
        Return total reactive power at a simulation timestamp.

        Args:
            timestamp: Time at which to read device reactive power.

        Returns:
            Sum of device reactive powers in per-unit on sbase.

        Raises:
            TypeError: If timestamp is not a pd.Timestamp.
        """
        total_power = 0.0
        for device in self.devices:
            if (
                device.data is not None
                and not device.data.empty
                and timestamp in device.data.index
            ):
                total_power += device.data.at[timestamp, "q"]
        return total_power

