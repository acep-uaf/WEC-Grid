"""
Marine-Grid: Marine Renewable Energy Grid Integration Tool.

Top-level package for Marine-Grid (v2.0.0). The primary entry point
is ``Study``, which composes the simulation timeline, modeler backends,
database, and analysis tools into a single orchestrating object.

Key exports (Application Layer):
    Study — Create, configure, and run grid simulations.

File: src/marinegrid/__init__.py
"""

__version__ = "2.0.0"

from .study import Study

__all__ = [
    "Study",
    "__version__",
]
