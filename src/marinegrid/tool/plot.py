"""
Plotting utilities for Marine-Grid.

File: src/marinegrid/tool/plot.py
"""

# Standard library
from typing import Optional, TYPE_CHECKING

# Third-party


# Local

if TYPE_CHECKING:
    from ..study import Study


class Plot:
    """Plotting utilities for Marine-Grid simulations (stub)."""

    def __init__(self, study: Optional["Study"] = None) -> None:
        """
        Initialize plotting helper with optional study reference.

        Args:
            study: Optional reference to parent Study object.
        """
        self.study = study
