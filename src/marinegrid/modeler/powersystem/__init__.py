"""
Power system modeler backends.

Defines the ABC contract (``PowerSystemModeler``) and its concrete
implementation (``PyPSAModeler``). ``SolveResult`` carries convergence
details from each power-flow solve back to ``ModelerManager``.

Key exports:
    PowerSystemModeler — ABC that all backends implement.
    SolveResult        — Dataclass for solver outcome metadata.
    PyPSAModeler       — PyPSA-based concrete backend.

File: src/marinegrid/modeler/powersystem/__init__.py
"""

from .base import PowerSystemModeler, SolveResult
from .pypsa import PyPSAModeler

__all__ = [
    "PowerSystemModeler",
    "SolveResult",
    "PyPSAModeler",
]
