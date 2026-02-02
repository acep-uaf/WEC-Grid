"""
PandaPower Modeler Module.

File: src/marinegrid/modeler/powersystem/pandapower.py
"""

# Standard library


# Third-party



# Local
from .base import PowerSystemModeler


class PandaPowerModeler(PowerSystemModeler):
    """PandaPower power system modeling backend (stub)."""

    def __init__(self):
        """Initialize PandaPowerModeler stub."""
        super().__init__(backend="pandapower")

    # TODO: Implement required abstract methods