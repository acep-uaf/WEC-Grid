"""
WEC-Sim modeler backend.

Infrastructure Layer interface to the MATLAB-based WEC-Sim
hydrodynamic simulator. Manages MATLAB engine lifecycle, parametric
simulation execution, and result storage in the Marine-Grid database.

Key exports:
    WECSimModeler — MATLAB/WEC-Sim simulation runner.

File: src/marinegrid/modeler/wecsim/__init__.py
"""

from .wecsim import WECSimModeler

__all__ = [
    "WECSimModeler",
]
