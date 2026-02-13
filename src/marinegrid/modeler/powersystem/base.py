"""
PowerSystemModeler Abstract Base Class.

File: src/marinegrid/modeler/powersystem/base.py
"""

# Standard library
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

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
    (PyPSA, PandaPower, OpenDSS, etc.) must implement. Provides
    standardized methods for initialization, power flow solving,
    and component-level data access/updates.

    The backend does NOT own simulation time or grid history (GridData).
    Those are managed by the ModelerManager which drives the simulation
    loop and collects results.

    Attributes:
        backend: String identifier for the backend (e.g., "pypsa").
        sbase: System base power in MVA.
        api: Backend-specific API/connection object.
    """

    def __init__(self, backend: str):
        """
        Initialize the power system modeler.

        Args:
            backend: Name of the power system backend being used.
        """
        self.backend = backend
        self.sbase: float | None = None
        self.api: Any = None

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
    def getBusData(self) -> pd.DataFrame:
        """
        Pull and organize all bus data in format specified in documentation.

        Return:
            Pandas DataFrame
        """


    @abstractmethod
    def getGeneratorData(self) -> pd.DataFrame:
        """
        Pull and organize all generator data in format specified in documentation.

        Return:
            Pandas DataFrame
        """

    @abstractmethod
    def getLoadData(self) -> pd.DataFrame:
        """
        Pull and organize all load data in format specified in documentation.

        Return:
            Pandas DataFrame
        """

    @abstractmethod
    def getLineData(self) -> pd.DataFrame:
        """
        Pull and organize all line data in format specified in documentation.

        Return:
            Pandas DataFrame
        """


    @abstractmethod
    def getTransformerData(self) -> pd.DataFrame:
        """
        Pull and organize all transformer data in format specified in documentation.

        Return:
            Pandas DataFrame
        """


    # -------------------------------------------------------------------------
    # Component data updates - abstract methods
    # TODO: fix the doc strings and functions here, not sure if I'll be passing in DFs
    # -------------------------------------------------------------------------

    @abstractmethod
    def updateBus(self) -> bool:
        """
        Update bus parameters in the model.

        Returns:
            True if update succeeded, False otherwise.
        """


    @abstractmethod
    def updateGenerator(self) -> bool:
        """
        Update generator parameters in the model.

        Returns:
            True if update succeeded, False otherwise.
        """


    @abstractmethod
    def updateLoad(self) -> bool:
        """
        Update load parameters in the model.

        Returns:
            True if update succeeded, False otherwise.
        """


    @abstractmethod
    def updateLine(self) -> bool:
        """
        Update transmission line parameters in the model.

        Returns:
            True if update succeeded, False otherwise.
        """


    @abstractmethod
    def updateTransformer(self) -> bool:
        """
        Update transformer parameters in the model.

        Returns:
            True if update succeeded, False otherwise.
        """


    # -------------------------------------------------------------------------
    # Component add  - abstract methods
    # TODO: fix the doc strings and functions here, not sure how I want to go about passing in parameters
    # -------------------------------------------------------------------------

    @abstractmethod
    def add_bus(self) -> bool:
        """
        Add a bus to the network.

        Returns:
            True if bus was added successfully, False otherwise.
        """


    @abstractmethod
    def add_generator(self) -> bool:
        """
        Add a generator to the network.

        Returns:
            True if generator was added successfully, False otherwise.
        """


    @abstractmethod
    def add_load(self) -> bool:
        """
        Add a load to the network.

        Returns:
            True if load was added successfully, False otherwise.
        """


    @abstractmethod
    def add_line(self) -> bool:
        """
        Add a transmission line to the network.

        Returns:
            True if line was added successfully, False otherwise.
        """



    @abstractmethod
    def add_transformer(self) -> bool:
        """
        Add a transformer to the network.

        Returns:
            True if transformer was added successfully, False otherwise.
        """



    # -------------------------------------------------------------------------
    # Component remove  - abstract methods
    # TODO: fix the doc strings and functions here, not sure how I want to go about passing in parameters
    # -------------------------------------------------------------------------


    @abstractmethod
    def remove_bus(self) -> bool:
        """
        Remove a bus from the network.

        Also removes all components connected to this bus (generators,
        loads, lines, transformers).

        Returns:
            True if bus was removed successfully, False otherwise.
        """


    @abstractmethod
    def remove_generator(self) -> bool:
        """
        Remove a generator from the network.

        Returns:
            True if generator was removed successfully, False otherwise.
        """


    @abstractmethod
    def remove_load(self) -> bool:
        """
        Remove a load from the network.

        Returns:
            True if load was removed successfully, False otherwise.
        """


    @abstractmethod
    def remove_line(self) -> bool:
        """
        Remove a transmission line from the network.

        Returns:
            True if line was removed successfully, False otherwise.
        """

    @abstractmethod
    def remove_transformer(self) -> bool:
        """
        Remove a transformer from the network.

        Returns:
            True if transformer was removed successfully, False otherwise.
        """
