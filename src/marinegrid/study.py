"""
Simulation orchestration for Marine-Grid.

File: src/marinegrid/study.py
"""

# Standard library
from pathlib import Path
from typing import Optional

# Third-party


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
        case_file: Path to the input case file (e.g., RAW).
        case_name: Human-readable case identifier.
        time: Time manager instance.
        modeler: Unified modeler interface for managing backends.
        plot: Plotting utilities.
        analysis: Analysis and metrics utilities.
        database: Database interface.
        allowed_exts: Tuple of allowed case file extensions.
    """

    def __init__(self):
        """
        Initialize the Marine-Grid Study.
        
        Sets up a study instance with default configuration. All modelers
        are uninitialized until explicitly loaded via modeler.load_modeler().
        """
        # Class objects
        self.plot = Plot(self)
        self.time = Time(self)
        self.analysis = Analysis(self)
        self.database = Database(self)
        self.modeler = ModelerManager()
        
        # Class attributes
        self.case_file: Optional[Path] = None
        self.case_name: Optional[str] = None
        self.allowed_exts = (".raw",)

    def __repr__(self) -> str:
        """Return a compact summary of the study state."""
        loaded_modelers = ", ".join(self.modeler.loaded()) if self.modeler.loaded() else "None"
        return (
            f"Study:\n"
            f"├─ Case: {self.case_name or 'Not Set'}\n"
            f"├─ Case File: {self.case_file or 'Not Set'}\n"
            f"├─ Loaded Modelers: {loaded_modelers}\n"
            f"└─ Time: {self.time}"
        )

    def set_case(self, case_file: str | Path) -> None:
        """
        Normalize and validate a power system case file path.

        Args:
            case_file: Path to the power system case file.

        Raises:
            TypeError: If case_file is not a str or Path.
            FileNotFoundError: If the case file does not exist.
            ValueError: If the file extension is not allowed.
        """
        if not isinstance(case_file, (str, Path)):
            raise TypeError("case_file must be a str or pathlib.Path")
        
        path = Path(case_file).expanduser().resolve()
        
        if not path.exists():
            raise FileNotFoundError(f"Case file not found: {path}")
        if self.allowed_exts and path.suffix.lower() not in self.allowed_exts:
            raise ValueError(f"Unsupported case extension '{path.suffix}', allowed: {self.allowed_exts}")
        
        self.case_file = path
        self.case_name = path.stem
        

        
        
        
        
        