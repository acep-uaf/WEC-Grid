"""
Modeler backends for Marine-Grid.

Plugin-style architecture for power system and hydrodynamic simulation
backends. ``ModelerManager`` (Application Layer) discovers and loads
concrete backends on demand. Current backends (Infrastructure Layer):
``PyPSAModeler`` for AC power flow and ``WECSimModeler`` for MATLAB-based
WEC-Sim execution.

Key exports:
    ModelerManager     — Dynamic loader and simulation coordinator.
    PowerSystemModeler — ABC for power-system backends.
    PyPSAModeler       — PyPSA concrete backend.
    WECSimModeler      — MATLAB/WEC-Sim concrete backend.

File: src/marinegrid/modeler/__init__.py
"""

from .manager import ModelerManager
from .powersystem import PowerSystemModeler, PyPSAModeler
from .wecsim import WECSimModeler

__all__ = [
    "ModelerManager",
    "PowerSystemModeler",
    "PyPSAModeler",
    "WECSimModeler",
]
