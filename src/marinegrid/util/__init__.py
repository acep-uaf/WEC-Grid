"""
Utility classes for Marine-Grid.

File: src/marinegrid/util/__init__.py
"""

from .time import Time
from .grid_data import GridData
from .grid_instance import GridInstance
from .convert import Converter
from .validation import (
    validate_types,
    validate_not_none,
    validate_path,
    validate_range,
    validate_choice,
    validate_dataframe,
    TypedProperty,
    require_initialized,
)

__all__ = [
    "Time",
    "GridData",
    "GridInstance",
    "Converter",
    # Validation utilities
    "validate_types",
    "validate_not_none",
    "validate_path",
    "validate_range",
    "validate_choice",
    "validate_dataframe",
    "TypedProperty",
    "require_initialized",
]
