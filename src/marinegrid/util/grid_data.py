"""
Grid history data container for time-series tracking.

File: src/marinegrid/util/grid_data.py
"""

# Standard library
from typing import Dict, Optional

# Third-party
import pandas as pd

# Local
from .grid_instance import GridInstance
from .time import Time


class GridData:
    """
    Manager for time-series grid state history.
    
    Stores a collection of GridInstance snapshots indexed by timestamp,
    maintaining a historical record of the power system state throughout
    a simulation. Provides access to current state and full history.
    
    Attributes:
        time: Time instance for time management.
        history: Dictionary mapping timestamps to GridInstance objects.
        currentState: Most recently appended GridInstance.
    """
    
    def __init__(self):
        """
        Initialize an empty GridData container.
        
        Creates empty history storage and sets up time management.
        """
        # Class objects
        self.time = Time()
        
        # Class attributes
        self._history: Dict[pd.Timestamp, GridInstance] = {}
        self._currentState: Optional[GridInstance] = None
        
    @property
    def history(self) -> Dict[pd.Timestamp, GridInstance]:
        """
        Get the complete history of grid states.
        
        Returns:
            Dictionary mapping timestamps to GridInstance objects.
        """
        return self._history
    
    @property
    def currentState(self) -> Optional[GridInstance]:
        """
        Get the most recent grid state.
        
        Returns:
            Most recently appended GridInstance or None if no states exist.
        """
        return self._currentState
    
    def appendState(self, state: GridInstance) -> bool:
        """
        Add a new grid state to the history.
        
        Args:
            state: GridInstance to add to the history.
        
        Returns:
            True if state was successfully appended.
            
        Raises:
            TypeError: If state is not a GridInstance.
        """
        if not isinstance(state, GridInstance):
            raise TypeError("state must be an instance of GridInstance.")
        
        self._history[state.timestamp] = state
        self._currentState = state
        return True

