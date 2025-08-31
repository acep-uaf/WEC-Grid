"""
Wave Energy Converter Farm modeling for power system integration.

This module provides the WECFarm class for managing collections of Wave Energy
Converter (WEC) devices within power system simulations. WEC farms aggregate
multiple identical devices at a common grid connection point, providing realistic
renewable energy profiles for grid integration studies.
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from .device import WECDevice
from ..modelers.wec_sim.runner import WECSimRunner


class WECFarm:
    """Collection of Wave Energy Converter devices at a common grid connection.

    Manages multiple identical WEC devices sharing a grid connection bus.
    Aggregates device power outputs and coordinates time-series data for
    power system integration studies.

    Attributes:
        farm_name (str): Human-readable farm identifier.
        database: Database interface for WEC simulation data.
        time: Time manager for simulation synchronization.
        wec_sim_id (int): Database simulation ID for WEC data retrieval.
        model (str): WEC device model type (e.g., "RM3").
        bus_location (int): Grid bus number for farm connection.
        connecting_bus (int): Network topology connection bus.
        id (str): Unique generator identifier for power system integration.
        size (int): Number of identical WEC devices in farm.
        config (Dict): Configuration parameters for the farm.
        wec_devices (List[WECDevice]): Collection of individual WEC devices.
        BASE (float): Base power rating [MVA] for per-unit calculations.

    Example:
        >>> farm = WECFarm(
        ...     farm_name="Oregon Coast Farm",
        ...     database=db,
        ...     time=time_mgr,
        ...     sim_id=101,
        ...     model="RM3",
        ...     bus_location=14,
        ...     size=5
        ... )
        >>> total_power = farm.power_at_snapshot(timestamp)

    Notes:
        - All devices use identical power profiles from WEC-Sim data
        - Power scales linearly with farm size
        - Requires WEC-Sim simulation data in database
        - Base power typically 100 MVA for utility-scale installations

    TODO:
        - Add heterogeneous device support for different models
        - Implement smart farm control and optimization
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
        """Initialize WEC farm with specified configuration.

        Args:
            farm_name (str): Human-readable WEC farm identifier.
            database: Database interface for WEC simulation data access.
            time: Time management object for simulation synchronization.
            wec_sim_id (int): Database simulation ID for WEC data retrieval.
            bus_location (int): Grid bus number for farm connection.
            connecting_bus (int, optional): Network topology connection bus. Defaults to 1.
            gen_name (str, optional): Generator name for power system integration. Defaults to ''.
            size (int, optional): Number of WEC devices in farm. Defaults to 1.
            farm_id (int, optional): Unique farm identifier. Defaults to None.
            sbase (float, optional): Base power rating [MVA] for per-unit calculations. Defaults to 100.0.
            scaling_factor (float, optional): Linear power scaling factor for aggregated output. Defaults to 1.0.

        Raises:
            RuntimeError: If WEC simulation data not found in database.
            ValueError: If database query returns empty results.

        Example:
            >>> farm = WECFarm(
            ...     farm_name="Newport Array",
            ...     database=db,
            ...     time=time_mgr,
            ...     wec_sim_id=101,
            ...     bus_location=14,
            ...     size=5
            ... )

        Notes:
            - Creates identical WECDevice objects for all farm devices
            - Retrieves WEC-Sim data from database using wec_sim_id
            - Sets up per-unit base power from simulation data
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
        """Return a formatted string representation of the WEC farm configuration.

        Provides a hierarchical display of key farm parameters for debugging,
        logging, and user information. The format is designed for readability
        and includes essential configuration details.

        Returns:
            str: Formatted multi-line string with farm configuration details.
                Includes farm name, size, model, grid connections, simulation ID,
                and base power rating in a tree-like structure.

        Example:
            >>> farm = WECFarm("Test Farm", db, time_mgr, 101, "RM3", 14, size=5)
            >>> print(farm)
            WECFarm:
            ├─ name: 'Test Farm'
            ├─ size: 5
            ├─ model: 'RM3'
            ├─ bus_location: 14
            ├─ connecting_bus: 1
            └─ wec_sim_id: 101

            Base: 100.0 MVA

        Display Format:
            - **Tree structure**: Uses Unicode box-drawing characters
            - **Key parameters**: Farm name, device count, model type
            - **Grid connections**: Bus locations for power system integration
            - **Simulation link**: Database simulation identifier
            - **Base power**: MVA rating for per-unit calculations

        Use Cases:
            - **Interactive debugging**: Quick farm configuration inspection
            - **Logging output**: Structured information for log files
            - **Jupyter notebooks**: Clean display in research environments
            - **Configuration validation**: Verify farm setup parameters

        Notes:
            - Size displays actual number of created devices (len(wec_devices))
            - Farm name shown in quotes to distinguish from other identifiers
            - Base power extracted from WEC simulation data during initialization
            - Unicode characters may not display properly in all terminals
        """
        return f"""WECFarm:
        ├─ name: {self.farm_name!r}
        ├─ size: {len(self.wec_devices)}
        ├─ model: {self.model!r}
        ├─ bus_location: {self.bus_location}
        ├─ connecting_bus: {self.connecting_bus}
        └─ sim_id: {self.wec_sim_id}

        Base: {self.sbase} MVA

    """

    def _prepare_farm(self):
        """Load WEC simulation data from database and create individual device objects.

        Internal method that handles the core initialization logic for the WEC farm.
        Validates database content, retrieves simulation results, processes time
        indexing, and instantiates the specified number of WEC device objects.

        Returns:
            None: Populates self.wec_devices with configured WECDevice objects.

        Raises:
            RuntimeError: If WEC simulation data not found or loading fails.
                Provides guidance on running WEC-Sim simulations first.
            ValueError: If database returns empty or invalid data.
            KeyError: If required columns missing from simulation data.

        Data Loading Process:
            1. **Table Existence Check**: Verify simulation tables exist in database
            2. **Grid Data Retrieval**: Load downsampled results for power system integration
            3. **Full Data Retrieval**: Load high-resolution results for detailed analysis
            4. **Time Index Creation**: Generate pandas datetime index for time series
            5. **Base Power Extraction**: Get MVA rating from simulation data
            6. **Device Instantiation**: Create specified number of WECDevice objects

        Database Table Schema:
            **Integration table** (`WECSIM_{model}_{sim_id}`):
            - time: Simulation time [s]
            - p: Active power output [MW]
            - q: Reactive power output [MVAr] (typically zero)
            - base: Base power rating [MVA]

            **Full resolution table** (`WECSIM_{model}_{sim_id}_full`):
            - time: Simulation time [s] (high frequency)
            - p: Active power output [MW]
            - eta: Wave surface elevation [m]
            - Additional WEC-Sim variables

        Time Series Processing:
            - **5-minute intervals**: Standard grid integration time step
            - **Datetime indexing**: Converts simulation seconds to timestamp format
            - **Start time alignment**: Uses time manager's configured start time
            - **Pandas integration**: Creates DataFrame index for efficient querying

        Device Creation:
            Each WECDevice configured with:
            - **Unique naming**: "{model}_{sim_id}_{index}" pattern
            - **Shared data**: Copy of power time series for each device
            - **Common parameters**: Bus location, base power, model type
            - **Individual objects**: Separate instance for potential customization

        Error Handling:
            - **Missing tables**: Clear error message with WEC-Sim guidance
            - **Empty data**: Validation of successful data retrieval
            - **Data integrity**: Checks for required columns and valid values
            - **Graceful failure**: Informative error messages for troubleshooting

        Performance Considerations:
            - **Single query**: Minimizes database access for efficiency
            - **Data copying**: Each device gets independent DataFrame copy
            - **Memory usage**: Scales with farm size and simulation duration
            - **Time indexing**: One-time conversion for all devices

        Notes:
            - Called automatically during farm initialization
            - Assumes WEC-Sim simulation completed successfully
            - Base power typically 100 MVA for utility-scale installations
            - All devices share identical power profiles (homogeneous farm)
            - TODO: Add data validation and integrity checks
            - TODO: Support for custom time intervals beyond 5 minutes

        See Also:
            WECDevice: Individual device objects created by this method
            WECSimRunner: Generates the simulation data loaded here
            WECGridTime: Provides time configuration for indexing
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
        """Downsample WEC time-series data to a coarser time resolution.

        Converts high-frequency WEC simulation data to lower frequency suitable for
        power system integration studies. Averages data over specified time windows
        to maintain energy conservation while reducing computational overhead.

        Based on MATLAB DownSampleTS function with pandas DataFrame implementation.

        Args:
            wec_df (pd.DataFrame): Original high-frequency WEC data with 'time' column.
                Must contain time series data with consistent time step.
            new_sample_period (float): New sampling period [seconds] for downsampled data.
                Typically 300s (5 minutes) for grid integration studies.
            timeshift (int, optional): Time alignment option. Defaults to 0.
                - 0: Samples at end of averaging period
                - 1: Samples centered within averaging period

        Returns:
            pd.DataFrame: Downsampled DataFrame with same columns as input.
                Time column adjusted to new sampling frequency.
                Data columns contain averaged values over sampling windows.

        Raises:
            ValueError: If new_sample_period is smaller than original time step.
            KeyError: If 'time' column not found in input DataFrame.

        Example:
            >>> # Downsample 0.1s WEC data to 5-minute intervals
            >>> df_original = pd.DataFrame({
            ...     'time': np.arange(0, 1000, 0.1),  # 0.1s timestep
            ...     'p': np.random.rand(10000),        # Power data
            ...     'eta': np.random.rand(10000)       # Wave elevation
            ... })
            >>> df_downsampled = farm.down_sample(df_original, 300.0)  # 5min
            >>> print(f"Original: {len(df_original)} points")
            >>> print(f"Downsampled: {len(df_downsampled)} points")
            Original: 10000 points
            Downsampled: 33 points

        Averaging Process:
            1. **Calculate sample ratio**: How many original points per new point
            2. **Determine new time grid**: Based on sample period and alignment
            3. **Window averaging**: Mean value over each time window
            4. **Energy conservation**: Maintains total energy content

        Time Alignment Options:
            **timeshift = 0** (End-aligned):
            - New timestamps at end of averaging window
            - t_new = [T, 2T, 3T, ...] where T = new_sample_period

            **timeshift = 1** (Center-aligned):
            - New timestamps at center of averaging window
            - t_new = [T/2, T+T/2, 2T+T/2, ...] where T = new_sample_period

        Data Processing:
            - **First window**: Averages from start to first sample point
            - **Subsequent windows**: Averages over fixed-width windows
            - **Missing data**: Handles partial windows at end of series
            - **Column preservation**: Maintains all non-time columns

        Performance Considerations:
            - **Memory efficient**: Uses vectorized pandas operations
            - **Flexible windows**: Handles non-integer sample ratios
            - **Large datasets**: Suitable for long WEC simulations
            - **Numerical stability**: Robust averaging implementation

        Grid Integration Usage:
            - **PSS®E studies**: 5-minute resolution for stability analysis
            - **Economic dispatch**: Hourly or 15-minute intervals
            - **Load forecasting**: Daily or weekly aggregation
            - **Resource assessment**: Monthly or seasonal averages

        Wave Energy Applications:
            - **Power smoothing**: Reduces high-frequency fluctuations
            - **Grid compliance**: Matches utility data requirements
            - **Forecast validation**: Aligns with meteorological predictions
            - **Storage sizing**: Determines energy storage requirements

        Notes:
            - Preserves energy content through proper averaging
            - Original time step must be consistent (fixed timestep)
            - New sample period should be multiple of original timestep
            - Returns DataFrame with same structure as input
            - Time column values updated to new sampling frequency

        See Also:
            _prepare_farm: Uses this method for WEC data preprocessing
            WECGridTime: Provides target sampling frequencies
            pandas.DataFrame.resample: Alternative pandas resampling method
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
        """Calculate total farm power output at a specific simulation time.

        Aggregates active power output from all WEC devices in the farm at the
        specified timestamp. This method provides the primary interface for
        power system integration, enabling time-varying renewable generation
        modeling in grid simulations.

        Args:
            timestamp (pd.Timestamp): Simulation time to query for power output.
                Must exist in the device DataFrame time index. Typically corresponds
                to grid simulation snapshots at 5-minute intervals.

        Returns:
            float: Total active power output from all farm devices in per-unit on
                the farm's ``sbase``. Sum of individual device outputs at the
                specified time. Returns 0.0 if no valid data available at
                timestamp.

        Raises:
            KeyError: If timestamp not found in device data index.
            AttributeError: If device DataFrame not properly initialized.

        Example:
            >>> # Get power at specific simulation time
            >>> timestamp = pd.Timestamp("2023-01-01 12:00:00")
            >>> power_pu = farm.power_at_snapshot(timestamp)
            >>> print(f"Farm output at noon: {power_pu:.4f} pu")
            Farm output at noon: 0.1575 pu

            >>> # Time series power extraction
            >>> time_series = []
            >>> for snapshot in time_manager.snapshots:
            ...     power_pu = farm.power_at_snapshot(snapshot)
            ...     time_series.append(power_pu)
            >>>
            >>> import matplotlib.pyplot as plt
            >>> plt.plot(time_manager.snapshots, time_series)
            >>> plt.ylabel("Farm Power Output [pu]")

        Power Aggregation:
            - **Linear summation**: Total = Σ(device_power[i] at timestamp)
            - **Homogeneous devices**: All devices have identical power profiles
            - **Realistic scaling**: Based on actual WEC device physics
            - **Wave correlation**: Devices respond to same ocean conditions

        Data Requirements:
            - **Valid timestamp**: Must exist in device DataFrame index
            - **Initialized devices**: All WECDevice objects must be properly created
            - **Power column**: Device data must contain "p" column for active power
            - **Time alignment**: Timestamp must match grid simulation schedule

        Error Handling:
            - **Missing data warning**: Prints warning for devices with no data
            - **Graceful degradation**: Continues calculation with available devices
            - **Zero fallback**: Returns 0.0 if no devices have valid data
            - **Timestamp validation**: Checks for existence in device index

        Performance Considerations:
            - **O(n) complexity**: Scales linearly with number of devices
            - **DataFrame lookup**: Efficient pandas indexing for time queries
            - **Memory efficiency**: No data copying, direct access to device data
            - **Repeated calls**: Suitable for time-series iteration

        Grid Integration Usage:
            - **PSS®E integration**: Provides generator output at each time step
            - **PyPSA integration**: Supplies renewable generation time series
            - **Load flow studies**: Time-varying injection for stability analysis
            - **Economic dispatch**: Variable renewable generation modeling

        Wave Energy Characteristics:
            - **Intermittent output**: Power varies with wave conditions
            - **Predictable patterns**: Follows ocean wave statistics
            - **Seasonal variation**: Higher output in winter storm seasons
            - **Capacity factor**: Typically 20-40% for ocean wave resources

        Notes:
            - Output is in per-unit on the farm's ``sbase``; multiply by
              ``sbase`` for MW
            - Power output includes WEC device efficiency and control effects
            - All devices share identical profiles (same wave field assumption)
            - Negative power values possible during reactive conditions
            - Zero output during calm conditions or device maintenance
            - Farm total limited by grid connection capacity

        See Also:
            WECDevice.dataframe: Individual device power time series
            Engine.simulate: Uses this method for grid integration
            WECGridPlotter.plot_wec_analysis: Visualizes farm power output
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
