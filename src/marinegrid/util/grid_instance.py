"""
Grid state data container for a single timestamp.

File: src/marinegrid/util/grid_instance.py
"""

# Standard library
from typing import Optional

# Third-party
import pandas as pd

# Local


class GridInstance:
    """
    Container for power system component data at a single point in time.
    
    Stores DataFrames of bus, line, generator, load, and transformer
    parameters at a specific timestamp. Provides type-safe property
    access with validation.
    
    Attributes:
        timestamp: Time point for this grid state snapshot.
        bus: DataFrame of bus data (voltage, power, type).
        line: DataFrame of line data (flows, loading, status).
        gen: DataFrame of generator data (output, setpoints, status).
        load: DataFrame of load data (consumption, status).
        transformer: DataFrame of transformer data (flows, taps, status).
    """
    
    def __init__(self):
        """
        Initialize an empty GridInstance.
        
        All component DataFrames are set to None initially and must
        be populated via property setters.
        """
        # Class objects
        
        # Class attributes
        self._bus: Optional[pd.DataFrame] = None
        self._line: Optional[pd.DataFrame] = None
        self._gen: Optional[pd.DataFrame] = None
        self._load: Optional[pd.DataFrame] = None
        self._transformer: Optional[pd.DataFrame] = None
        self._timestamp: Optional[pd.Timestamp] = None
        
    @property
    def timestamp(self) -> Optional[pd.Timestamp]:
        """
        Get the timestamp for this grid state.
        
        Returns:
            Pandas Timestamp or None if not set.
        """
        return self._timestamp
    
    @timestamp.setter
    def timestamp(self, value: Optional[pd.Timestamp]):
        """
        Set the timestamp for this grid state.
        
        Args:
            value: Pandas Timestamp or None.
            
        Raises:
            TypeError: If value is not a Timestamp or None.
        """
        if value is not None and not isinstance(value, pd.Timestamp):
            raise TypeError("timestamp must be a pandas Timestamp instance or None.")
        self._timestamp = value
    
    @property
    def bus(self) -> Optional[pd.DataFrame]:
        """
        Get bus data DataFrame.
        
        Returns:
            DataFrame of bus data or None if not set.
        """
        return self._bus
    
    @bus.setter
    def bus(self, value: Optional[pd.DataFrame]):
        """
        Set bus data DataFrame.
        
        Args:
            value: DataFrame of bus data or None.
            
        Raises:
            TypeError: If value is not a DataFrame or None.
        """
        if value is not None and not isinstance(value, pd.DataFrame):
            raise TypeError("bus must be a pandas DataFrame instance or None.")
        self._bus = value
    
    @property
    def line(self) -> Optional[pd.DataFrame]:
        """
        Get line data DataFrame.
        
        Returns:
            DataFrame of line data or None if not set.
        """
        return self._line   
    
    @line.setter
    def line(self, value: Optional[pd.DataFrame]):
        """
        Set line data DataFrame.
        
        Args:
            value: DataFrame of line data or None.
            
        Raises:
            TypeError: If value is not a DataFrame or None.
        """
        if value is not None and not isinstance(value, pd.DataFrame):
            raise TypeError("line must be a pandas DataFrame instance or None.")
        self._line = value
    
    @property
    def gen(self) -> Optional[pd.DataFrame]:
        """
        Get generator data DataFrame.
        
        Returns:
            DataFrame of generator data or None if not set.
        """
        return self._gen
    
    @gen.setter
    def gen(self, value: Optional[pd.DataFrame]): 
        """
        Set generator data DataFrame.
        
        Args:
            value: DataFrame of generator data or None.
            
        Raises:
            TypeError: If value is not a DataFrame or None.
        """
        if value is not None and not isinstance(value, pd.DataFrame):
            raise TypeError("gen must be a pandas DataFrame instance or None.")
        self._gen = value
    
    @property
    def load(self) -> Optional[pd.DataFrame]:
        """
        Get load data DataFrame.
        
        Returns:
            DataFrame of load data or None if not set.
        """
        return self._load
    
    @load.setter
    def load(self, value: Optional[pd.DataFrame]):
        """
        Set load data DataFrame.
        
        Args:
            value: DataFrame of load data or None.
            
        Raises:
            TypeError: If value is not a DataFrame or None.
        """
        if value is not None and not isinstance(value, pd.DataFrame):
            raise TypeError("load must be a pandas DataFrame instance or None.")
        self._load = value  
        
    @property
    def transformer(self) -> Optional[pd.DataFrame]:
        """
        Get transformer data DataFrame.
        
        Returns:
            DataFrame of transformer data or None if not set.
        """
        return self._transformer
    
    @transformer.setter
    def transformer(self, value: Optional[pd.DataFrame]):
        """
        Set transformer data DataFrame.
        
        Args:
            value: DataFrame of transformer data or None.
            
        Raises:
            TypeError: If value is not a DataFrame or None.
        """
        if value is not None and not isinstance(value, pd.DataFrame):
            raise TypeError("transformer must be a pandas DataFrame instance or None.")
        self._transformer = value
    