"""
WEC-Sim runner interface.

File: src/marinegrid/modeler/wecsim/wecsim.py
"""

# Standard library
from pathlib import Path
from typing import Optional

# Third-party


# Local


class WECSimModeler:
    """
    WEC-Sim modeling backend (stub).
    
    Manages configuration and execution of WEC-Sim simulations
    and provides interfaces to retrieve results for grid coupling.
    """
    
    def __init__(self):
        """Initialize WECSimModeler with default configuration."""
        self.wec_sim_path: Optional[Path] = None
        self.matlab_engine = None