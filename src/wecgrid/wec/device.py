"""
Individual Wave Energy Converter device modeling for power system integration.

This module provides the WECDevice dataclass for representing individual Wave Energy
Converter (WEC) devices with their associated time-series data, grid connection
parameters, and simulation metadata. WECDevice objects form the building blocks
of WEC farms in power system studies.
"""

# Standard library
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

# Third-party
import pandas as pd


@dataclass
class WECDevice:
    """Individual Wave Energy Converter device with time-series power output data.

    Represents a single wave energy converter with simulation results, grid connection
    parameters, and metadata. Contains time-series power output data from WEC-Sim
    hydrodynamic simulations for realistic renewable generation modeling.

    Attributes:
        name (str): Unique device identifier, typically "{model}_{sim_id}_{index}".
        dataframe (pd.DataFrame): Primary time-series data for grid integration at
            5-minute intervals. Columns: time, p [MW], q [MVAr], base [MVA].
        dataframe_full (pd.DataFrame): High-resolution simulation data with complete
            WEC-Sim output including wave elevation and device states.
        base (float, optional): Base power rating [MVA] for per-unit calculations.
        bus_location (int, optional): Power system bus number for grid connection.
        model (str, optional): WEC device model type ("RM3", "LUPA", etc.).
        sim_id (int, optional): Database simulation identifier for traceability.

    Example:
        >>> power_data = pd.DataFrame({
        ...     'p': [2.5, 3.1, 2.8],  # MW
        ...     'q': [0.0, 0.0, 0.0],  # MVAr
        ...     'base': [100.0] * 3    # MVA
        ... })
        >>> device = WECDevice(
        ...     name="RM3_101_0",
        ...     dataframe=power_data,
        ...     base=100.0,
        ...     bus_location=14,
        ...     model="RM3"
        ... )

    Notes:
        - Variable power output based on wave conditions
        - Typically operates at unity power factor (zero reactive power)
        - Primary dataframe at 5-minute resolution for grid compatibility
        - Full dataframe contains high-resolution WEC-Sim results
    """

    name: str
    dataframe: pd.DataFrame = field(default_factory=pd.DataFrame)
    bus_location: Optional[int] = None
    model: Optional[str] = None
    wec_sim_id: Optional[int] = None

    def __repr__(self) -> str:
        """Return a formatted string representation of the WEC device configuration.

        Provides a hierarchical display of key device parameters for debugging,
        logging, and user information. The format shows essential device
        characteristics including identification, grid connection, and data status.

        Returns:
            str: Formatted multi-line string with device configuration details.
                Includes device name, model type, grid connection parameters,
                simulation metadata, base power rating, and data size in a
                tree-like structure for easy reading.

        Example:
            >>> device = WECDevice(
            ...     name="RM3_101_0",
            ...     model="RM3",
            ...     bus_location=14,
            ...     sim_id=101,
            ...     dataframe=power_data  # 288 rows
            ... )
            >>> print(device)
            WECDevice:
            ├─ name: 'RM3_101_0'
            ├─ model: 'RM3'
            ├─ bus_location: 14
            ├─ sim_id: 101
            └─ rows: 288

        Display Format:
            - **Tree structure**: Uses Unicode box-drawing characters
            - **Device identification**: Name and model type in quotes
            - **Grid parameters**: Bus location and simulation ID as integers
            - **Data size**: Number of time-series data points

        Information Categories:
            - **Identity**: Device name (typically includes model and index)
            - **Type**: WEC model for hydrodynamic characteristics
            - **Grid connection**: Bus location for electrical network modeling
            - **Simulation link**: Database ID for traceability
            - **Data status**: Time-series length for validation

        Use Cases:
            - **Interactive debugging**: Quick device configuration inspection
            - **Jupyter notebooks**: Clean display in research environments
            - **Logging output**: Structured device information for log files
            - **Data validation**: Verify device setup and data availability
            - **Farm inspection**: Review individual devices in large collections

        Notes:
            - Name and model shown in quotes to distinguish strings
            - Row count reflects primary dataframe length (grid integration data)
            - Missing values displayed as None for optional parameters
            - Unicode characters may not display properly in all terminals
            - Format consistent with WECFarm.__repr__() for visual coherence

        See Also:
            WECFarm.__repr__: Similar formatting for farm-level display
        """
        return f"""WECDevice:
    ├─ name: {self.name!r}
    ├─ model: {self.model!r}
    ├─ bus_location: {self.bus_location}
    ├─ sim_id: {self.wec_sim_id}
    └─ rows: {len(self.dataframe)}
    """
