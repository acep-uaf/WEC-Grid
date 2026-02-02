"""
PowerSystemModeler Abstract Base Class.

File: src/marinegrid/modeler/powersystem/base.py
"""

# Standard library
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Third-party
import pandas as pd


# Local
from ...util.grid_instance import GridInstance
from ...util.grid_data import GridData


@dataclass
class SolveReport:
    """
    Performance tracking for simulation runs.

    Attributes:
        simulation_time: Total wall time in seconds.
        case: Case name/identifier.
        backend: Backend name (e.g., "pypsa", "pandapower").
        snapshots: List of snapshot timestamps.
        converged: Per-step convergence flags.
        solve_time: Power flow solve time per step.
        solve_iterations: Solver iterations per step.
        messages: Solver status messages per step.
    """

    simulation_time: float = 0.0
    case: str = ""
    backend: str = ""
    snapshots: List = field(default_factory=list)
    converged: List[bool] = field(default_factory=list)
    solve_time: List[float] = field(default_factory=list)
    solve_iterations: List[int] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        """Return a one-line summary of solve status and timing."""
        if not self.converged:
            status = "No runs"
        elif all(self.converged):
            status = "Converged"
        else:
            failed = sum(1 for c in self.converged if not c)
            status = f"Failed ({failed}/{len(self.converged)})"

        return (
            f"SolveReport: {status}, "
            f"steps={len(self.snapshots)}, "
            f"time={self.simulation_time:.2f}s"
        )

    def add_solve_result(
        self,
        snapshot,
        converged: bool,
        solve_time: float = 0.0,
        iterations: int = 0,
        message: str = "",
    ):
        """
        Record solve result for a simulation step.

        Args:
            snapshot: Timestamp for this step.
            converged: Whether power flow converged.
            solve_time: Time to solve in seconds.
            iterations: Number of solver iterations.
            message: Solver status message.
        """
        self.snapshots.append(snapshot)
        self.converged.append(converged)
        self.solve_time.append(solve_time)
        self.solve_iterations.append(iterations)
        self.messages.append(message)

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert report to DataFrame for analysis.

        Returns:
            DataFrame with columns for each metric.
        """
        return pd.DataFrame({
            "snapshot": self.snapshots,
            "converged": self.converged,
            "solve_time": self.solve_time,
            "iterations": self.solve_iterations,
            "message": self.messages,
        })


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
    """

    def __init__(self, backend: str):
        """
        Initialize the power system modeler.

        Args:
            backend: Name of the power system backend being used.
        """
        # Class objects
        self.data = GridData()
        self.report = SolveReport(backend=backend)

        # Class attributes
        self.backend = backend
        self.sbase: Optional[float] = None

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

        return (
            f"{class_name}:\n"
            f"├─ Backend: {self.backend}\n"
            f"├─ System Base: {sbase_str}\n"
            f"├─ Components: {components}\n"
            f"├─ History: {history_count} snapshots\n"
            f"└─ {self.report}"
        )

    # -------------------------------------------------------------------------
    # Convenience properties for current state
    # -------------------------------------------------------------------------

    @property
    def bus(self) -> Optional[pd.DataFrame]:
        """Current bus state DataFrame."""
        if self.data.currentState is None:
            return None
        return self.data.currentState.bus

    @property
    def gen(self) -> Optional[pd.DataFrame]:
        """Current generator state DataFrame."""
        if self.data.currentState is None:
            return None
        return self.data.currentState.gen

    @property
    def line(self) -> Optional[pd.DataFrame]:
        """Current line state DataFrame."""
        if self.data.currentState is None:
            return None
        return self.data.currentState.line

    @property
    def load(self) -> Optional[pd.DataFrame]:
        """Current load state DataFrame."""
        if self.data.currentState is None:
            return None
        return self.data.currentState.load

    @property
    def transformer(self) -> Optional[pd.DataFrame]:
        """Current transformer state DataFrame."""
        if self.data.currentState is None:
            return None
        return self.data.currentState.transformer

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

    @abstractmethod
    def simulate(self, snapshots: Optional[pd.DatetimeIndex] = None) -> bool:
        """
        Run time-series power flow simulation.

        Executes power flow calculations across all snapshots,
        updating the grid state at each time step and capturing results.

        Args:
            snapshots: Time points to simulate. If None, uses single snapshot.

        Returns:
            True if simulation completed successfully, False otherwise.
        """
        pass

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
