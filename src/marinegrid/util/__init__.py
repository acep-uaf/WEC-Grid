"""
Utility classes for Marine-Grid.

Shared Domain and Application Layer utilities. ``Time`` manages the
simulation timeline, ``GridInstance`` and ``GridData`` capture per-unit
grid state snapshots and their time-series history, and ``Converter``
translates case files into solver-ready networks.

Key exports:
    Time         — Simulation timeline with snapshot generation.
    GridData     — Ordered collection of GridInstance snapshots.
    GridInstance  — Single-timestamp grid state container.
    Converter    — RAW-to-PyPSA case file converter.

File: src/marinegrid/util/__init__.py
"""

from .time import Time
from .grid_data import GridData
from .grid_instance import GridInstance
from .convert import Converter

__all__ = [
    "Time",
    "GridData",
    "GridInstance",
    "Converter",
]
