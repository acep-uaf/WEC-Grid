"""
Simulation orchestration for Marine-Grid.

Defines the ``Study`` class, the top-level entry point that composes
``Time``, ``ModelerManager``, ``Database``, ``Plot``, and ``Analysis``
into a single coordinating object. Users create a Study, point it at a
case file, configure the timeline, load modelers, and run simulations.

File: src/marinegrid/study.py
"""

# Standard library
from pathlib import Path

# Local
from .tool.plot import Plot
from .tool.analysis import Analysis
from .tool.database import Database
from .util.time import Time
from .modeler.manager import ModelerManager


class Study:
    """
    Top-level controller for Marine-Grid simulations.

    Coordinates renewable energy farm integration with power system modelers,
    manages simulation time, and provides access to database, plotting, and
    analysis utilities.

    Attributes:
        case_path: Path to the input case file (e.g., RAW).
        case_name: Human-readable case identifier.
        time: Time manager instance.
        modeler: Unified modeler interface for managing backends.
        plot: Plotting utilities.
        analysis: Analysis and metrics utilities.
        database: Database interface.
        allowed_exts: Set of allowed case file extensions.
    """

    # Allowed case file extensions
    _ALLOWED_EXTS = {".raw"}

    def __init__(self) -> None:
        """
        Initialize the Marine-Grid Study.

        Sets up a study instance with default configuration. All modelers
        are uninitialized until explicitly loaded via modeler.load_modeler().
        The Time object is automatically shared with ModelerManager.
        """
        # Class objects
        self.plot = Plot(self)
        self.time = Time(self)
        self.analysis = Analysis(self)
        self.database = Database(self)
        self.modeler = ModelerManager()

        # Wire Time to ModelerManager
        self.modeler.set_time(self.time)

        # Class attributes
        self._case_path:  Path | None = None # path to case file
        self._case_name : str | None = None # name of the case
        
        
    
    @property
    def case_name(self) -> str:
        if self._case_name is None:
            raise RuntimeError("Case not set. Set study.case_path first.")
        return self._case_name
    
    
    @property
    def case_path(self) -> Path:
        if self._case_path is None:
            raise RuntimeError("Case not set. Set study.case_path first.")
        return self._case_path


    @case_path.setter
    def case_path(self, value: object) -> None:
        if not isinstance(value, str):
            raise TypeError(f"case_path must be a str, got {type(value).__name__}: {value!r}")

        s = value.strip()
        if not s:
            raise ValueError("case_path must be a non-empty path string")

        path = Path(s).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"Case file does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Case path is not a file: {path}")
        if self._ALLOWED_EXTS and path.suffix.lower() not in self._ALLOWED_EXTS:
            allowed = ", ".join(sorted(self._ALLOWED_EXTS))
            raise ValueError(f"Unsupported extension {path.suffix!r}. Allowed: {allowed}")

        self._case_path = path
        self._case_name = path.stem

    
    def run(self, **kwargs) -> bool:
        """
        Run the simulation.

        Convenience wrapper around ``modeler.simulate()``. Accepts the same
        keyword arguments (``gen_schedules``, ``load_schedules``).

        Returns:
            True if simulation completed successfully.
        """
        return self.modeler.simulate(**kwargs)

    def __repr__(self) -> str:
        """Return a compact summary of the study state."""
        loaded_modelers = ", ".join(self.modeler.loaded()) if self.modeler.loaded() else "None"
        return (
            f"Study:\n"
            f"├─ Case: {self._case_name or 'Not Set'}\n"
            f"├─ Case File: {self._case_path or 'Not Set'}\n"
            f"├─ Loaded Modelers: {loaded_modelers}\n"
            f"└─ Time: {self.time}"
        )

