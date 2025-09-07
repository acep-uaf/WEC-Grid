"""Wave Energy Converter farms composed of identical devices."""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from .device import WECDevice
from ..modelers.wec_sim.runner import WECSimRunner


class WECFarm:
    """Group of identical WEC devices connected to one bus.

    Attributes:
        farm_name: Human-readable identifier for the farm.
        database: Database interface used to fetch WEC-Sim results.
        time: Time manager providing simulation snapshots.
        wec_sim_id: Simulation ID used for database queries.
        model: WEC device model name.
        bus_location: Bus number where the farm connects.
        connecting_bus: Bus used to link the farm into the network.
        gen_name: Generator name in the grid model.
        size: Number of devices in the farm.
        wec_devices: Created ``WECDevice`` instances.
        sbase: Base power in MVA for per-unit values.
        scaling_factor: Linear multiplier applied to device power.
    """

    def __init__(
        self,
        farm_name: str,
        database,
        time: Any,
        wec_sim_id: int,
        bus_location: int,
        connecting_bus: int = 1,
        gen_name: str = "",
        size: int = 1,
        farm_id: int = None,
        sbase: float = 100.0,
        scaling_factor: float = 1.0,
    ):
        """Initialize the farm and load associated WEC-Sim data.

        Args:
            farm_name: Label for the farm.
            database: Interface used to query WEC-Sim results.
            time: Time manager providing simulation snapshots.
            wec_sim_id: Identifier of the WEC simulation to load.
            bus_location: Bus number where the farm connects.
            connecting_bus: Bus used to link the farm into the network.
            gen_name: Generator name in the grid model.
            size: Number of devices in the farm.
            farm_id: Optional integer identifier for the farm.
            sbase: Base power in MVA for per-unit values.
            scaling_factor: Linear multiplier applied to device power.

        Raises:
            RuntimeError: If WEC simulation data is missing.
            ValueError: If the database returns empty results.
        """

        self.farm_name: str = farm_name
        self.database = database  # TODO make this a WECGridDB data type
        self.time = time  # todo might need to update time to be SimulationTime type
        self.wec_sim_id: int = wec_sim_id
        self.model: str = ""
        self.bus_location: int = bus_location
        self.connecting_bus: int = (
            connecting_bus  # todo this should default to swing bus
        )
        self.farm_id: int = farm_id
        self.size: int = size
        self.config: Dict = None
        self.wec_devices: List[WECDevice] = []
        self.sbase: float = sbase
        self.scaling_factor: float = scaling_factor
        self.gen_name = gen_name
        # todo don't need the base here anymore
        # todo: add bus voltage.
        # todo: connecting line

        self._prepare_farm()

    def __repr__(self) -> str:
        """Return a compact string describing the farm."""
        return (
            f"WECFarm:\n"
            f"├─ name: {self.farm_name!r}\n"
            f"├─ size: {len(self.wec_devices)}\n"
            f"├─ model: {self.model!r}\n"
            f"├─ bus_location: {self.bus_location}\n"
            f"├─ connecting_bus: {self.connecting_bus}\n"
            f"└─ sim_id: {self.wec_sim_id}\n\n"
            f"Base: {self.sbase} MVA\n"
        )

    def _prepare_farm(self):
        """Load WEC-Sim data and create device objects.

        Queries the database for the selected simulation, down-samples the
        power data and instantiates ``size`` ``WECDevice`` objects.

        Raises:
            RuntimeError: If simulation data is missing or invalid.
        """
        # First get model type from wec_simulations table using wec_sim_id
        model_query = "SELECT model_type FROM wec_simulations WHERE wec_sim_id = ?"
        model_result = self.database.query(model_query, params=(self.wec_sim_id,))

        if not model_result:
            raise RuntimeError(
                f"[Farm] No simulation metadata found for wec_sim_id={self.wec_sim_id}"
            )

        # Update self.model from database
        if isinstance(model_result, list) and len(model_result) > 0:
            self.model = (
                model_result[0][0]
                if isinstance(model_result[0], (list, tuple))
                else model_result[0]["model_type"]
            )
        else:
            raise RuntimeError(
                f"[Farm] Invalid model data returned for wec_sim_id={self.wec_sim_id}"
            )

        # print(f"[Farm] Loaded WEC model '{self.model}' for simulation ID {self.wec_sim_id}")

        # Check if WEC simulation data exists in new schema
        sim_check_query = "SELECT wec_sim_id FROM wec_simulations WHERE wec_sim_id = ?"
        sim_result = self.database.query(sim_check_query, params=(self.wec_sim_id,))

        if not sim_result:
            raise RuntimeError(
                f"[Farm] No WEC simulation found for wec_sim_id={self.wec_sim_id}. Run WEC-SIM first."
            )

        # Load WEC power data from new database schema
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
                f"[Farm] No WEC power data found for wec_sim_id={self.wec_sim_id}"
            )

        df_full.p = self.scaling_factor * df_full.p  # scale active power
        df_full.q = self.scaling_factor * df_full.q  # scale reactive power

        # Downsample the full resolution data for grid integration
        df_downsampled = self.down_sample(df_full, self.time.delta_time)

        # Apply time index at 5 min resolution using start time
        df_downsampled["snapshots"] = pd.date_range(
            start=self.time.start_time,
            periods=df_downsampled.shape[0],
            freq=self.time.freq,
        )

        # apply the snapshots
        df_downsampled.set_index("snapshots", inplace=True)

        # Convert Watts to per-unit of sbase MVA
        # WEC data is stored in Watts, need to convert to MW then to per-unit
        # Conversion: Watts → MW (÷1e6) → per-unit (÷sbase_MVA)
        df_downsampled["p"] = df_downsampled["p"] / (self.sbase * 1e6)  # Watts to pu
        df_downsampled["q"] = df_downsampled["q"] / (self.sbase * 1e6)  # Watts to pu

        for i in range(self.size):
            name = f"{self.model}_{self.wec_sim_id}_{i}"
            device = WECDevice(
                name=name,
                dataframe=df_downsampled.copy(),  # Use downsampled data for grid integration
                bus_location=self.bus_location,
                model=self.model,
                wec_sim_id=self.wec_sim_id,
            )
            self.wec_devices.append(device)

    def down_sample(
        self, wec_df: pd.DataFrame, new_sample_period: float, timeshift: int = 0
    ) -> pd.DataFrame:
        """Downsample WEC time series.

        Args:
            wec_df: Input data with a ``time`` column in seconds.
            new_sample_period: Desired sampling period in seconds.
            timeshift: ``0`` for end-aligned timestamps or ``1`` for centered.

        Returns:
            pd.DataFrame: Downsampled data with the same columns.

        Raises:
            ValueError: If ``new_sample_period`` is smaller than the original step.
            KeyError: If the ``time`` column is missing.
        """
        if "time" not in wec_df.columns:
            raise KeyError("DataFrame must contain 'time' column for downsampling")

        # Calculate original time step (assuming fixed timestep)
        time_values = wec_df["time"].values
        if len(time_values) < 2:
            return wec_df.copy()  # Return original if too few points

        old_dt = time_values[1] - time_values[0]

        if new_sample_period <= old_dt:
            raise ValueError(
                f"New sample period ({new_sample_period}s) must be larger than original timestep ({old_dt}s)"
            )

        # Calculate sampling parameters
        t_sample = int(new_sample_period / old_dt)  # Points per new sample
        new_sample_size = int((time_values[-1] - time_values[0]) / new_sample_period)

        if new_sample_size <= 0:
            return wec_df.copy()  # Return original if downsampling not possible

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

        # Ensure we don't exceed the original time range
        new_times = new_times[new_times <= time_values[-1]]
        new_sample_size = len(new_times)

        # Initialize downsampled DataFrame
        downsampled_data = {"time": new_times}

        # Downsample each data column (excluding time)
        data_columns = [col for col in wec_df.columns if col != "time"]

        for col in data_columns:
            downsampled_values = np.zeros(new_sample_size)

            for i in range(new_sample_size):
                if i == 0:
                    # First window: from start to first sample point
                    start_idx = 0
                    end_idx = min(t_sample, len(wec_df))
                else:
                    # Subsequent windows: fixed-width windows
                    start_idx = (i - 1) * t_sample
                    end_idx = min(i * t_sample, len(wec_df))

                if start_idx < len(wec_df) and end_idx > start_idx:
                    downsampled_values[i] = wec_df[col].iloc[start_idx:end_idx].mean()
                else:
                    downsampled_values[i] = 0.0  # Handle edge cases

            downsampled_data[col] = downsampled_values

        return pd.DataFrame(downsampled_data)

    def power_at_snapshot(self, timestamp: pd.Timestamp) -> float:
        """Return total active power at a simulation time.

        Args:
            timestamp: Time at which to read device power.

        Returns:
            float: Sum of device powers in per unit on ``sbase``.

        Raises:
            KeyError: If ``timestamp`` is not present in the device data.
        """
        total_power = 0.0
        for device in self.wec_devices:
            if (
                device.dataframe is not None
                and not device.dataframe.empty
                and timestamp in device.dataframe.index
            ):
                power = device.dataframe.at[timestamp, "p"]
                total_power += power
            else:
                print(f"[WARNING] Missing data for {device.name} at {timestamp}")
        return total_power
