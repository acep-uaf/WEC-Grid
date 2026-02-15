"""
PowerSystemModeler Abstract Base Class.

Defines ``PowerSystemModeler``, the ABC that all power-system backends
must implement, and ``SolveResult``, the dataclass returned by every
power-flow solve. Together they establish the interface contract that
``ModelerManager`` relies on for backend-agnostic simulation.

File: src/marinegrid/modeler/powersystem/base.py
"""

# Standard library
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# Third-party
import pandas as pd


@dataclass
class SolveResult:
    """
    Result of a single power flow solve.

    Returned by each backend's solve() method to provide the manager
    with details about solver performance and convergence.

    Attributes:
        converged: Whether the power flow converged.
        solve_time: Wall time for the solve in seconds.
        iterations: Number of solver iterations.
        message: Solver status message or error description.
    """
    converged: bool = False
    solve_time: float = 0.0
    iterations: int = 0
    message: str = ""

    def __repr__(self) -> str:
        status = "Converged" if self.converged else "Failed"
        return (
            f"SolveResult: {status}, "
            f"time={self.solve_time:.4f}s, "
            f"iterations={self.iterations}"
        )


class PowerSystemModeler(ABC):
    """
    Abstract base class for power system modeling backends.

    Defines the interface contract that all power system modelers
    must implement. Provides
    standardized methods for initialization, power flow solving,
    and component-level data access/updates.

    The backend does NOT own simulation time or grid history (GridData).
    Those are managed by the ModelerManager which drives the simulation
    loop and collects results.

    Attributes:
        backend: String identifier for the backend (e.g., "pypsa").
        sbase: System base power in MVA.
    """

    def __init__(self, backend: str):
        """
        Initialize the power system modeler.

        Args:
            backend: Name of the power system backend being used.
        """
        self.backend = backend
        self.sbase: float | None = None

    def __repr__(self) -> str:
        """Return a formatted summary of the modeler state."""
        class_name = self.__class__.__name__
        sbase_str = f"{self.sbase} MVA" if self.sbase else "Not set"

        return (
            f"{class_name}:\n"
            f"├─ Backend: {self.backend}\n"
            f"└─ System Base: {sbase_str}"
        )


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


    @abstractmethod
    def solve(self) -> SolveResult:
        """
        Run a single power flow solve on the current network state.

        Returns:
            SolveResult containing:
                - converged: whether the solve converged
                - solve_time: wall time in seconds
                - iterations: number of solver iterations
                - message: status message, warnings, or errors
        """


    # -------------------------------------------------------------------------
    # Component data retrieval - abstract methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_bus_data(self) -> pd.DataFrame:
        """
        Pull and organize all bus data in format specified in documentation.

        Return:
            Pandas DataFrame
        """


    @abstractmethod
    def get_generator_data(self) -> pd.DataFrame:
        """
        Pull and organize all generator data in format specified in documentation.

        Return:
            Pandas DataFrame
        """

    @abstractmethod
    def get_load_data(self) -> pd.DataFrame:
        """
        Pull and organize all load data in format specified in documentation.

        Return:
            Pandas DataFrame
        """

    @abstractmethod
    def get_line_data(self) -> pd.DataFrame:
        """
        Pull and organize all line data in format specified in documentation.

        Return:
            Pandas DataFrame
        """


    @abstractmethod
    def get_transformer_data(self) -> pd.DataFrame:
        """
        Pull and organize all transformer data in format specified in documentation.

        Return:
            Pandas DataFrame
        """


    # -------------------------------------------------------------------------
    # Component data updates - abstract methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def update_bus(self, name: str, **kwargs: Any) -> bool:
        """
        Update bus parameters in the model.

        Args:
            name: Bus identifier.
            **kwargs: Parameters to update (e.g., v_mag_pu_set, control).

        Returns:
            True if update succeeded, False otherwise.
        """

    @abstractmethod
    def update_generator(self, name: str, **kwargs: Any) -> bool:
        """
        Update generator parameters in the model.

        Args:
            name: Generator identifier.
            **kwargs: Parameters to update (e.g., p_set, q_set, p_nom).

        Returns:
            True if update succeeded, False otherwise.
        """

    @abstractmethod
    def update_load(self, name: str, **kwargs: Any) -> bool:
        """
        Update load parameters in the model.

        Args:
            name: Load identifier.
            **kwargs: Parameters to update (e.g., p_set, q_set).

        Returns:
            True if update succeeded, False otherwise.
        """

    @abstractmethod
    def update_line(self, name: str, **kwargs: Any) -> bool:
        """
        Update transmission line parameters in the model.

        Args:
            name: Line identifier.
            **kwargs: Parameters to update (e.g., s_nom, status).

        Returns:
            True if update succeeded, False otherwise.
        """

    @abstractmethod
    def update_transformer(self, name: str, **kwargs: Any) -> bool:
        """
        Update transformer parameters in the model.

        Args:
            name: Transformer identifier.
            **kwargs: Parameters to update (e.g., tap_ratio, s_nom).

        Returns:
            True if update succeeded, False otherwise.
        """

    # -------------------------------------------------------------------------
    # Component add - abstract methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def add_bus(self, name: str, **kwargs: Any) -> bool:
        """
        Add a bus to the network.

        Args:
            name: Unique bus identifier.
            **kwargs: Backend-specific parameters (e.g., v_nom, control).

        Returns:
            True if bus was added successfully, False otherwise.
        """

    @abstractmethod
    def add_generator(self, name: str, bus: str, **kwargs: Any) -> bool:
        """
        Add a generator to the network.

        Args:
            name: Unique generator identifier.
            bus: Bus name where generator connects.
            **kwargs: Backend-specific parameters (e.g., p_nom, carrier).

        Returns:
            True if generator was added successfully, False otherwise.
        """

    @abstractmethod
    def add_load(self, name: str, bus: str, **kwargs: Any) -> bool:
        """
        Add a load to the network.

        Args:
            name: Unique load identifier.
            bus: Bus name where load connects.
            **kwargs: Backend-specific parameters (e.g., p_set, q_set).

        Returns:
            True if load was added successfully, False otherwise.
        """

    @abstractmethod
    def add_line(self, name: str, bus0: str, bus1: str, **kwargs: Any) -> bool:
        """
        Add a transmission line to the network.

        Args:
            name: Unique line identifier.
            bus0: From bus name.
            bus1: To bus name.
            **kwargs: Backend-specific parameters (e.g., r, x, s_nom).

        Returns:
            True if line was added successfully, False otherwise.
        """

    @abstractmethod
    def add_transformer(self, name: str, bus0: str, bus1: str, s_nom: float, **kwargs: Any) -> bool:
        """
        Add a transformer to the network.

        Args:
            name: Unique transformer identifier.
            bus0: Primary bus name.
            bus1: Secondary bus name.
            s_nom: Nominal apparent power rating in MVA.
            **kwargs: Backend-specific parameters (e.g., tap_ratio, phase_shift).

        Returns:
            True if transformer was added successfully, False otherwise.
        """

    # -------------------------------------------------------------------------
    # Component remove - abstract methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def remove_bus(self, name: str) -> bool:
        """
        Remove a bus from the network.

        Also removes all components connected to this bus (generators,
        loads, lines, transformers).

        Args:
            name: Bus identifier to remove.

        Returns:
            True if bus was removed successfully, False otherwise.
        """

    @abstractmethod
    def remove_generator(self, name: str) -> bool:
        """
        Remove a generator from the network.

        Args:
            name: Generator identifier to remove.

        Returns:
            True if generator was removed successfully, False otherwise.
        """

    @abstractmethod
    def remove_load(self, name: str) -> bool:
        """
        Remove a load from the network.

        Args:
            name: Load identifier to remove.

        Returns:
            True if load was removed successfully, False otherwise.
        """

    @abstractmethod
    def remove_line(self, name: str) -> bool:
        """
        Remove a transmission line from the network.

        Args:
            name: Line identifier to remove.

        Returns:
            True if line was removed successfully, False otherwise.
        """

    @abstractmethod
    def remove_transformer(self, name: str) -> bool:
        """
        Remove a transformer from the network.

        Args:
            name: Transformer identifier to remove.

        Returns:
            True if transformer was removed successfully, False otherwise.
        """
