# src/wecgrid/__init__.py

"""
WEC-Grid Python package
Author: Alexander Barajas-Ritchie
Email: barajale@oregonstate.edu
"""

__version__ = "1.0.0"

# Expose the main Engine entry point
from .engine import Engine

__all__ = ["Engine", "__version__"]
