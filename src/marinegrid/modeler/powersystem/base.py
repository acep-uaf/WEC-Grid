"""
PowerSystemModeler Abstract Base Class.

File: src/marinegrid/modeler/powersystem/base.py
"""

# Standard library
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

# Third-party
import pandas as pd


# Local
from ...util.grid_instance import GridInstance
from ...util.grid_data import GridData
# if TYPE_CHECKING:
#     from ...util.time import Time


class PowerSystemModeler(ABC):
    """
    Abstract base class for power system modeling backends.

    Defines the interface contract that all power system modelers
    (PyPSA, PandaPower, OpenDSS, etc.) must implement. Provides
    standardized methods for initialization, power flow solving,
    state capture, and component-level data access/updates.

    Attributes:
        data: GridData instance for tracking simulation history.
        report: SolveReport for performance tracking.
        backend: String identifier for the backend (e.g., "pypsa").
        sbase: System base power in MVA.
        time: Reference to the central Time object for simulation timeline.
    """

    def __init__(self, backend: str):
        """
        Initialize the power system modeler.

        Args:
            backend: Name of the power system backend being used.
        """
        # Class objects
        self._data = GridData()
        #self.report = SolveReport(backend=backend) 
        self._time: Optional["Time"] = None
        self.api: Any = None # API connection object

        # Class attributes
        self.backend = backend
        self.sbase: float | None = None

    @property
    def time(self) -> Optional["Time"]:
        """Get the central Time object for simulation timeline."""
        return self._time

    def set_time(self, time: "Time") -> None:
        """
        Set the central Time object for simulation timeline.

        Args:
            time: Time object to use as the simulation timeline.

        Raises:
            TypeError: If time is not a Time instance.
        """
        self._time = time

    def __repr__(self) -> str:
        """Return a formatted summary of the modeler state."""
        class_name = self.__class__.__name__

        # Current state info
        current = self.data.currentState
        if current is not None:
            bus_count = len(current.bus) if current.bus is not None else 0
            gen_count = len(current.gen) if current.gen is not None else 0
            line_count = len(current.line) if current.line is not None else 0
            load_count = len(current.load) if current.load is not None else 0
            components = f"{bus_count} buses, {gen_count} gens, {line_count} lines, {load_count} loads"
        else:
            components = "No state captured"

        # History info
        history_count = len(self.data.history)

        # Sbase info
        sbase_str = f"{self.sbase} MVA" if self.sbase else "Not set"

        # Time info
        if self._time is not None:
            time_str = f"{len(self._time)} steps @ {self._time.freq}"
        else:
            time_str = "Not set"

        return (
            f"{class_name}:\n"
            f"├─ Backend: {self.backend}\n"
            f"├─ System Base: {sbase_str}\n"
            f"├─ Time: {time_str}\n"
            f"├─ Components: {components}\n"
            f"├─ History: {history_count} snapshots\n"
            f"└─ {self.report}"
        )

    # -------------------------------------------------------------------------
    # Convenience properties for current state
    # -------------------------------------------------------------------------

    # @property
    # def bus(self) -> pd.DataFrame:
    #     """Current bus state DataFrame."""
    #     if self._data.currentState is None:
    #          raise ValueError("bus data unavailble")
    #     return self._data.currentState.bus

    # @property
    # def gen(self) -> Optional[pd.DataFrame]:
    #     """Current generator state DataFrame."""
    #     if self._data.currentState is None:
    #         return None
    #     return self._data.currentState.gen

    # @property
    # def line(self) -> Optional[pd.DataFrame]:
    #     """Current line state DataFrame."""
    #     if self._data.currentState is None:
    #         return None
    #     return self._data.currentState.line

    # @property
    # def load(self) -> Optional[pd.DataFrame]:
    #     """Current load state DataFrame."""
    #     if self._data.currentState is None:
    #         return None
    #     return self._data.currentState.load

    # @property
    # def transformer(self) -> Optional[pd.DataFrame]:
    #     """Current transformer state DataFrame."""
    #     if self._data.currentState is None:
    #         return None
    #     return self._data.currentState.transformer

    # -------------------------------------------------------------------------
    # Abstract methods - must be implemented by subclasses
    # -------------------------------------------------------------------------

    @abstractmethod
    def initialize(self, *args, **kwargs) -> bool:
        """
        Initialize the power system modeler backend.

        Performs backend-specific initialization, including loading
        the network model, setting up solvers, and preparing for
        simulation.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def solve(self) -> bool:
        """
        Run the power flow solution and update the model state.

        Executes a single power flow calculation for the current
        network state and updates voltage, power, and flow values.

        Returns:
            True if the solution converged, False otherwise.
        """
        pass
    
    

    # @abstractmethod
    # def simulate(
    #     self,
    #     gen_schedules: Optional[Dict[str, Union[pd.Series, pd.DataFrame]]] = None,
    #     load_schedules: Optional[Dict[str, Union[pd.Series, pd.DataFrame]]] = None,
    # ) -> bool:
    #     """
    #     Run time-series power flow simulation.

    #     Executes power flow calculations across all snapshots from the
    #     Time object, updating the grid state at each time step and
    #     capturing results to GridData.

    #     Uses self.time.snapshots as the simulation timeline. If no Time
    #     object is set, runs a single snapshot simulation.

    #     Args:
    #         gen_schedules: Dictionary mapping generator names/IDs to time series.
    #             Values can be Series (p only) or DataFrame (p, q columns).
    #             Power values in per-unit on system MVA base.
    #         load_schedules: Dictionary mapping load names/IDs to time series.
    #             Same format as gen_schedules.

    #     Returns:
    #         True if simulation completed successfully, False otherwise.
    #     """
    #     pass

    @abstractmethod
    def getState(self, timestamp: pd.Timestamp) -> bool:
        """
        Capture current grid state at specified timestamp.

        Creates a GridInstance with all component data and appends
        it to the GridData history.

        Args:
            timestamp: Timestamp for this grid state snapshot.

        Returns:
            True if state capture succeeded, False otherwise.
        """
        pass

    # -------------------------------------------------------------------------
    # Component data retrieval - abstract methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def getBusData(self) -> pd.DataFrame:
        """
        Retrieve bus data from the model.

        Returns:
            DataFrame with columns: bus, bus_name, type, p, q, v_mag, angle_deg, vbase.
        """
        pass

    @abstractmethod
    def getGeneratorData(self) -> pd.DataFrame:
        """
        Retrieve generator data from the model.

        Returns:
            DataFrame with columns: gen, gen_name, bus, p, q, p_nom, status.
        """
        pass

    @abstractmethod
    def getLoadData(self) -> pd.DataFrame:
        """
        Retrieve load data from the model.

        Returns:
            DataFrame with columns: load, load_name, bus, p, q, status.
        """
        pass

    @abstractmethod
    def getLineData(self) -> pd.DataFrame:
        """
        Retrieve transmission line data from the model.

        Returns:
            DataFrame with columns: line, line_name, bus0, bus1, p0, p1, loading_pct, status.
        """
        pass

    @abstractmethod
    def getTransformerData(self) -> pd.DataFrame:
        """
        Retrieve transformer data from the model.

        Returns:
            DataFrame with columns: transformer, bus0, bus1, p0, p1, tap_ratio, status.
        """
        pass

    # -------------------------------------------------------------------------
    # Component data updates - abstract methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def updateBus(self, bus_data: pd.DataFrame) -> bool:
        """
        Update bus parameters in the model.

        Args:
            bus_data: DataFrame with bus parameters to update.

        Returns:
            True if update succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def updateGenerator(self, gen_data: pd.DataFrame) -> bool:
        """
        Update generator parameters in the model.

        Args:
            gen_data: DataFrame with generator parameters to update.

        Returns:
            True if update succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def updateLoad(self, load_data: pd.DataFrame) -> bool:
        """
        Update load parameters in the model.

        Args:
            load_data: DataFrame with load parameters to update.

        Returns:
            True if update succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def updateLine(self, line_data: pd.DataFrame) -> bool:
        """
        Update transmission line parameters in the model.

        Args:
            line_data: DataFrame with line parameters to update.

        Returns:
            True if update succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def updateTransformer(self, transformer_data: pd.DataFrame) -> bool:
        """
        Update transformer parameters in the model.

        Args:
            transformer_data: DataFrame with transformer parameters to update.

        Returns:
            True if update succeeded, False otherwise.
        """
        pass

    # -------------------------------------------------------------------------
    # Component add/remove - abstract methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def add_bus(
        self,
        name: str,
        v_nom: float,
        **kwargs,
    ) -> bool:
        """
        Add a bus to the network.

        Args:
            name: Unique bus identifier/name.
            v_nom: Nominal voltage in kV.
            **kwargs: Additional backend-specific parameters.
                Common options:
                - v_mag_pu_set: Voltage magnitude setpoint [pu]
                - v_mag_pu_min: Minimum voltage [pu]
                - v_mag_pu_max: Maximum voltage [pu]
                - control: Control type ('PQ', 'PV', 'Slack')

        Returns:
            True if bus was added successfully, False otherwise.
        """
        pass

    @abstractmethod
    def remove_bus(self, name: str) -> bool:
        """
        Remove a bus from the network.

        Also removes all components connected to this bus (generators,
        loads, lines, transformers).

        Args:
            name: Bus identifier/name to remove.

        Returns:
            True if bus was removed successfully, False otherwise.
        """
        pass

    @abstractmethod
    def add_generator(
        self,
        name: str,
        bus: str,
        p_nom: float,
        **kwargs,
    ) -> bool:
        """
        Add a generator to the network.

        Args:
            name: Unique generator identifier/name.
            bus: Bus name where generator connects.
            p_nom: Nominal power capacity in MW.
            **kwargs: Additional backend-specific parameters.
                Common options:
                - p_set: Active power setpoint [MW]
                - q_set: Reactive power setpoint [MVAr]
                - p_min: Minimum active power [MW]
                - p_max: Maximum active power [MW]
                - control: Control mode ('PQ', 'PV', 'Slack')
                - carrier: Energy carrier type (e.g., 'AC', 'wave', 'wind')

        Returns:
            True if generator was added successfully, False otherwise.
        """
        pass

    @abstractmethod
    def remove_generator(self, name: str) -> bool:
        """
        Remove a generator from the network.

        Args:
            name: Generator identifier/name to remove.

        Returns:
            True if generator was removed successfully, False otherwise.
        """
        pass

    @abstractmethod
    def add_load(
        self,
        name: str,
        bus: str,
        p_set: float,
        **kwargs,
    ) -> bool:
        """
        Add a load to the network.

        Args:
            name: Unique load identifier/name.
            bus: Bus name where load connects.
            p_set: Active power consumption in MW.
            **kwargs: Additional backend-specific parameters.
                Common options:
                - q_set: Reactive power consumption [MVAr]

        Returns:
            True if load was added successfully, False otherwise.
        """
        pass

    @abstractmethod
    def remove_load(self, name: str) -> bool:
        """
        Remove a load from the network.

        Args:
            name: Load identifier/name to remove.

        Returns:
            True if load was removed successfully, False otherwise.
        """
        pass

    @abstractmethod
    def add_line(
        self,
        name: str,
        bus0: str,
        bus1: str,
        **kwargs,
    ) -> bool:
        """
        Add a transmission line to the network.

        Args:
            name: Unique line identifier/name.
            bus0: From bus name.
            bus1: To bus name.
            **kwargs: Additional backend-specific parameters.
                Common options:
                - r: Resistance [Ohm or pu]
                - x: Reactance [Ohm or pu]
                - b: Susceptance [S or pu]
                - s_nom: Thermal rating [MVA]
                - length: Line length [km]

        Returns:
            True if line was added successfully, False otherwise.
        """
        pass

    @abstractmethod
    def remove_line(self, name: str) -> bool:
        """
        Remove a transmission line from the network.

        Args:
            name: Line identifier/name to remove.

        Returns:
            True if line was removed successfully, False otherwise.
        """
        pass

    @abstractmethod
    def add_transformer(
        self,
        name: str,
        bus0: str,
        bus1: str,
        s_nom: float,
        **kwargs,
    ) -> bool:
        """
        Add a transformer to the network.

        Args:
            name: Unique transformer identifier/name.
            bus0: Primary bus name.
            bus1: Secondary bus name.
            s_nom: Nominal apparent power rating [MVA].
            **kwargs: Additional backend-specific parameters.
                Common options:
                - r: Resistance [pu]
                - x: Reactance [pu]
                - tap_ratio: Off-nominal tap ratio
                - phase_shift: Phase shift angle [degrees]

        Returns:
            True if transformer was added successfully, False otherwise.
        """
        pass

    @abstractmethod
    def remove_transformer(self, name: str) -> bool:
        """
        Remove a transformer from the network.

        Args:
            name: Transformer identifier/name to remove.

        Returns:
            True if transformer was removed successfully, False otherwise.
        """
        pass
