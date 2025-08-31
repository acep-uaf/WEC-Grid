# src/wecgrid/modelers/power_system/base.py
"""Core interfaces and data structures for power-system modeling backends.

This module defines the foundational pieces used by all power-system
modelers within WEC-Grid:

* ``AttrDict`` – a convenience dictionary with attribute-style access for
  organizing time-series data.
* ``GridState`` – a dataclass that standardizes snapshot and historical data
  for buses, generators, lines, and loads.
* ``PowerSystemModeler`` – an abstract base class specifying the API that
  backend implementations must provide.

Concrete modelers such as :mod:`psse` and :mod:`pypsa` extend these classes
to interface with PSS®E and PyPSA, respectively, while adhering to the common
WEC-Grid modeling interface.
"""

# Standard library
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

# Third-party
import pandas as pd

# Local
from ...wec.farm import WECFarm


class AttrDict(dict):
    """Dictionary that allows attribute-style access to keys.
    
    This utility class enables accessing dictionary values using dot notation
    (d.key) in addition to the standard bracket notation (d['key']). This is
    used for convenient access to time-series data collections.
    
    Example:
        >>> data = AttrDict({'voltage': df1, 'power': df2})
        >>> data.voltage  # Same as data['voltage']
        >>> data.power = df3  # Same as data['power'] = df3
        
    Raises:
        AttributeError: If the requested attribute/key does not exist.
    """
    def __getattr__(self, name):
        """Map attribute access to dictionary lookup.

        Raises:
            AttributeError: If the key is absent.
        """
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'AttrDict' has no attribute '{name}'")

    def __setattr__(self, name, value):
        """Map attribute assignment to setting a dictionary key."""
        self[name] = value


# @dataclass
# class SolveReport:
#     simulation_time: float = 0.0
#     iter_time = [] # float 
#     converged = [] # bool 
#     pf_solve_time = [] # float 
#     pf_solve_iter = [] 
#     snapshot_time = [] # float
#     snapshot = [] # time index
#     message = [] # str 


@dataclass
class SolveReport:
    simulation_time: float = 0.0
    case: str = ""
    software: str = ""
    iter_time: list = field(default_factory=list)  # float 
    converged: list = field(default_factory=list)  # bool 
    pf_solve_time: list = field(default_factory=list)  # float 
    pf_solve_iter: list = field(default_factory=list)  # int
    snapshot_time: list = field(default_factory=list)  # float
    snapshot: list = field(default_factory=list)  # time index
    message: list = field(default_factory=list)  # str
    
    def __repr__(self) -> str:
        return (
            f"SolveReport:\n"
            f"├─ Converged: {'Failed' if not all(self.converged) else 'Successful'}\n"
            f"├─ Simulation Time: {self.simulation_time:.2f} s\n"
            f"├─ Num Steps: {len(self.snapshot)}\n"
            f"├─ Case: {self.case}\n"
            f"└─ Modeler: {self.software}"
        )
    
    def add_iteration_time(self, time_val: float):
        """Add iteration time for current snapshot."""
        self.iter_time.append(time_val)
    
    def add_pf_solve_data(self, solve_time: float, iterations: int, converged: bool, msg: str):
        """Add power flow solve data for current snapshot."""
        self.converged.append(converged)
        self.pf_solve_time.append(solve_time)
        self.pf_solve_iter.append(iterations)
        self.message.append(msg)
    
    def add_snapshot_data(self, snapshot_time: float):
        """Add snapshot timing"""
        self.snapshot_time.append(snapshot_time)
        
    def add_snapshot(self, snapshot_id):
        self.snapshot.append(snapshot_id)
    
    @property
    def as_dataframe(self) -> pd.DataFrame:
        """Convert to DataFrame for analysis (optional convenience method)."""
        # Pad shorter lists with None to match longest list
        max_len = max(len(getattr(self, attr)) for attr in 
                     ['iter_time', 'converged', 'pf_solve_time', 'pf_solve_iter', 
                      'snapshot_time', 'snapshot', 'message'])
        
        data = {}
        for attr in ['iter_time', 'converged', 'pf_solve_time', 'pf_solve_iter', 
                     'snapshot_time', 'snapshot', 'message']:
            values = getattr(self, attr)
            # Pad with None if shorter than max_len
            data[attr] = values + [None] * (max_len - len(values))
        
        return pd.DataFrame(data)
    
@dataclass
class GridState:
    """Standardized container for power system snapshot and time-series data.
    
    The GridState class provides a unified data structure for storing power system
    component states across different simulation backends (PSS®E, PyPSA, etc.). It
    maintains both current snapshot data and historical time-series data for buses,
    generators, lines, and loads using standardized DataFrame schemas.
    
    This class enables cross-platform validation and comparison between different
    power system analysis tools by enforcing consistent data formats and units.
    All electrical quantities are stored in per-unit values based on system MVA.
    
    Attributes:
        software (str): Backend software name ("psse", "pypsa", etc.).
        bus (pd.DataFrame): Current bus state with voltage, power injection data.
        gen (pd.DataFrame): Current generator state with power output data.
        line (pd.DataFrame): Current transmission line state with loading data.
        load (pd.DataFrame): Current load state with power consumption data.
        bus_t (AttrDict): Time-series bus data organized by variable name.
        gen_t (AttrDict): Time-series generator data organized by variable name.
        line_t (AttrDict): Time-series line data organized by variable name.
        load_t (AttrDict): Time-series load data organized by variable name.
        
    Example:
        >>> grid = GridState()
        >>> # Update with current snapshot
        >>> grid.update("bus", timestamp, bus_dataframe)
        >>> # Access current state
        >>> print(f"Number of buses: {len(grid.bus)}")
        >>> # Access time-series data
        >>> voltage_history = grid.bus_t.v_mag  # All bus voltages over time
        
    Notes:
        - All power values are in per-unit on system base MVA
        - Voltage magnitudes are in per-unit, angles in degrees
        - Line loading is expressed as percentage of thermal rating
        - Component IDs must be consistent across all DataFrames
        - Time-series data is automatically maintained when snapshots are updated
        
    DataFrame Schemas:
        Each component DataFrame follows a standardized schema as documented
        in the individual update method and property descriptions.
    """
    
    software: str = ""
    case: str = ""
    bus: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    gen: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    line: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    load: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    bus_t: AttrDict = field(default_factory=AttrDict)
    gen_t: AttrDict = field(default_factory=AttrDict)
    line_t: AttrDict = field(default_factory=AttrDict)
    load_t: AttrDict = field(default_factory=AttrDict)

    # todo: need to add a way to identify WECs on a grid, 'G7' is a wecfarm
    
    def __repr__(self) -> str:
        """Return a formatted string representation of the GridState.
        
        Provides a tree-style summary showing the number of components in each
        category and the available time-series variables for each component type.
        
        Returns:
            str: Multi-line string representation showing component counts and
                available time-series data.
                
        Example:
            >>> print(grid)
            GridState (psse):
            ├─ Components:
            │   ├─ bus:   14 components
            │   ├─ gen:   5 components  
            │   ├─ line:  20 components
            │   └─ load:  11 components
            └─ Backend: PSS®E simulation model
        """
        def ts_info(component_t):
            """Format time-series information with variable count and snapshot count."""
            if not component_t:
                return "none"
            variables = list(component_t.keys())
            if variables:
                # Get snapshot count from first variable's DataFrame
                snapshot_count = len(component_t[variables[0]]) if len(component_t[variables[0]]) > 0 else 0
                var_str = ", ".join(variables)
                return f"{var_str} ({snapshot_count} snapshots)"
            return "none"
        
        def backend_name(software):
            """Convert software code to descriptive name."""
            names = {
                'psse': 'PSS®E Modeler',
                'pypsa': 'PyPSA Modeler', 
                '': 'No backend specified'
            }
            return names.get(software.lower(), f'{software} simulation modeler')

        return (
            f"GridState:\n"
            f"├─ Components:\n"
            f"│   ├─ bus:   {len(self.bus)} components\n"
            f"│   ├─ gen:   {len(self.gen)} components\n"
            f"│   ├─ line:  {len(self.line)} components\n"
            f"│   └─ load:  {len(self.load)} components\n"
            f"├─ Case: {self.case}\n"
            f"└─ Modeler: {self.software}"
        )

    def update(self, component: str, timestamp: pd.Timestamp, df: pd.DataFrame):
        """
        Update snapshot and time-series data for a power system component.

        This method updates both the current snapshot DataFrame and the historical
        time-series data for the specified component type. It expects DataFrames
        with standardized WEC-Grid schemas and proper `df.attrs['df_type']` attributes.

        Args:
            component (str):
                Component type ("bus", "gen", "line", "load").
            timestamp (pd.Timestamp):
                Timestamp for this snapshot.
            df (pd.DataFrame):
                Component data with `df.attrs['df_type']` set to one of
                {"BUS", "GEN", "LINE", "LOAD"}.

        Raises:
            ValueError:
                If component is not recognized, `df_type` is invalid, or required
                ID columns are missing.

        ----------------------------------------------------------------------
        DataFrame Schemas
        ----------------------------------------------------------------------
        Component ID:
            for the component attribute the ID will be an incrementing ID number starting from 1 in order of bus number

        Component Names:
            for the component_name attribute the name will be the corresponding component label and ID (e.g., "Bus_1", "Gen_1").

        **Bus DataFrame** (`df_type="BUS"`)

        | Column    | Description                                 | Type   | Units            | Base Used              |
        |-----------|---------------------------------------------|--------|------------------|------------------------|
        | bus       | Bus number (unique identifier)              | int    | —                | —                      |
        | bus_name  | Bus name/label (e.g., "Bus_1", "Bus_2")     | str    | —                | —                      |
        | type      | Bus type: "Slack", "PV", "PQ"               | str    | —                | —                      |
        | p         | Net active power injection (Gen − Load)     | float  | pu               | **S_base** (MVA)       |
        | q         | Net reactive power injection (Gen − Load)   | float  | pu               | **S_base** (MVA)       |
        | v_mag     | Voltage magnitude                           | float  | pu               | **V_base** (kV LL)     |
        | angle_deg | Voltage angle                               | float  | degrees          | —                      |
        | vbase     | Bus nominal voltage (line-to-line)          | float  | kV               | —                      |

        **Generator DataFrame** (`df_type="GEN"`)

        | Column     | Description                                 | Type   | Units            | Base Used              |
        |------------|---------------------------------------------|--------|------------------|------------------------|
        | gen        | Generator ID                                | int    | —                | —                      |
        | gen_name   | Generator name (e.g., "Gen_1")              | str    | —                | —                      |
        | bus        | Connected bus number                        | int    | —                | —                      |
        | p          | Active power output                         | float  | pu               | **S_base** (MVA)       |
        | q          | Reactive power output                       | float  | pu               | **S_base** (MVA)       |
        | Mbase      | Generator nameplate MVA rating              | float  | MVA              | **Mbase** (machine)    |
        | status     | Generator status (1=online, 0=offline)      | int    | —                | —                      |

        **Load DataFrame** (`df_type="LOAD"`)

        | Column     | Description                                 | Type   | Units            | Base Used              |
        |------------|---------------------------------------------|--------|------------------|------------------------|
        | load       | Load ID                                     | int    | —                | —                      |
        | load_name  | Load name (e.g., "Load_1")                  | str    | —                | —                      |
        | bus        | Connected bus number                        | int    | —                | —                      |
        | p          | Active power demand                         | float  | pu               | **S_base** (MVA)       |
        | q          | Reactive power demand                       | float  | pu               | **S_base** (MVA)       |
        | status     | Load status (1=connected, 0=offline)        | int    | —                | —                      |

        **Line DataFrame** (`df_type="LINE"`)

        | Column     | Description                                 | Type   | Units            | Base Used              |
        |------------|---------------------------------------------|--------|------------------|------------------------|
        | line       | Line ID                                     | int    | —                | —                      |
        | line_name  | Line name (e.g., "Line_1_2")                | str    | —                | —                      |
        | ibus       | From bus number                             | int    | —                | —                      |
        | jbus       | To bus number                               | int    | —                | —                      |
        | line_pct   | Percentage of thermal rating in use         | float  | %                | —                      |
        | status     | Line status (1=online, 0=offline)           | int    | —                | —                      |

        ----------------------------------------------------------------------
        Base Usage Summary
        ----------------------------------------------------------------------
        - **S_base (System Power Base):**
        All `p` and `q` values across buses, generators, and loads are in per-unit
        on the single, case-wide power base (e.g., 100 MVA):

        - **V_base (Bus Voltage Base):**
        Each bus has a nominal voltage in kV (line-to-line)

        - **Mbase (Machine Base):**
        Per-generator nameplate MVA rating used for manufacturer parameters. 

        Example:
            >>> # Update bus data at current time
            >>> bus_df = create_bus_dataframe()  # with proper schema
            >>> bus_df.attrs['df_type'] = 'BUS'
            >>> grid.update("bus", pd.Timestamp.now(), bus_df)

            >>> # Access updated data
            >>> current_buses = grid.bus
            >>> voltage_timeseries = grid.bus_t.v_mag
        """

        if df is None or df.empty:
            return

        # --- figure out the ID column for this df_type ---
        df_type = df.attrs.get("df_type", None)
        id_map = {"BUS": "bus", "GEN": "gen", "LINE": "line", "LOAD": "load"}
        id_col = id_map.get(df_type)
        if id_col is None:
            raise ValueError(f"Cannot determine ID column from df_type='{df_type}'")

        # --- ensure the ID is a real column and set as the index for alignment ---
        if id_col in df.columns:
            pass
        elif df.index.name == id_col:
            df = df.reset_index()
        else:
            raise ValueError(f"'{id_col}' not found in columns or as index for df_type='{df_type}'")

        df = df.copy()
        #df.set_index(id_col, inplace=True)   # now index = IDs (bus #, gen ID, etc.)

        # keep snapshot (indexed by ID)
        if not hasattr(self, component):
            raise ValueError(f"No snapshot attribute for component '{component}'")
        setattr(self, component, df)

        # --- write into the time-series store ---
        t_attr = getattr(self, f"{component}_t", None)
        if t_attr is None:
            raise ValueError(f"No time-series attribute for component '{component}'")

        # for each measured variable, maintain a DataFrame with:
        #   rows    = timestamps
        #   columns = component names (not IDs)
        for var in df.columns:
            series = df[var]  # index = IDs, values = this variable for this snapshot

            if var not in t_attr:
                t_attr[var] = pd.DataFrame()

            tdf = t_attr[var]
            
            # Use component names as column headers instead of IDs
            name_col = f"{component}_name"
            if name_col in df.columns:
                # Create mapping from ID to name
                id_to_name = dict(zip(df.index, df[name_col]))
                # Convert series index from IDs to names
                series_with_names = series.copy()
                series_with_names.index = [id_to_name.get(idx, str(idx)) for idx in series.index]
                
                # add any new component names as columns
                missing = series_with_names.index.difference(tdf.columns)
                if len(missing) > 0:
                    for col in missing:
                        tdf[col] = pd.NA

                # set the row for this timestamp, one component at a time to avoid alignment issues
                for comp_name, value in series_with_names.items():
                    tdf.loc[timestamp, comp_name] = value
            else:
                # Fallback to using IDs if no name column available
                # add any new IDs as columns
                missing = series.index.difference(tdf.columns)
                if len(missing) > 0:
                    for col in missing:
                        tdf[col] = pd.NA

                # set the row for this timestamp, one component at a time
                for comp_id, value in series.items():
                    tdf.loc[timestamp, comp_id] = value
                
            t_attr[var] = tdf


class PowerSystemModeler(ABC):
    """Abstract base class for power system modeling backends.
    
    Defines standardized interface for PSS®E, PyPSA, and other power system tools
    in WEC-GRID framework. Provides grid analysis, WEC integration, and time-series
    simulation capabilities through common API.
    
    Args:
        engine: WEC-GRID Engine with case_file, time, and wec_farms attributes.
    
    Attributes:
        engine: Reference to simulation engine.
        grid (GridState): Time-series data for buses, generators, lines, loads.
        sbase (float, optional): System base power [MVA].
        
    Example:
        >>> from wecgrid.modelers import PSSEModeler, PyPSAModeler
        >>> psse_model = PSSEModeler(engine)
        >>> pypsa_model = PyPSAModeler(engine)
        
    Notes:
        - Abstract class - use concrete implementations (PSSEModeler, PyPSAModeler)
        - Grid state data follows standardized schema for cross-platform comparison
        - All abstract methods must be implemented by subclasses
    """
    
    def __init__(self, engine: Any):
        """Initialize PowerSystemModeler with simulation engine.
        
        Args:
            engine: WEC-GRID Engine with case_file, time, and wec_farms attributes.
                
        Note:
            Call init_api() after construction to initialize backend tool.
        """
        self.engine = engine
        self.grid = GridState()
        self.report = SolveReport()
        self.grid.case = engine.case_name
        self.report.case = engine.case_name
        
        self.sbase: Optional[float] = None
        
    def __repr__(self) -> str:
        """Return a formatted string representation of the PowerSystemModeler.
        
        Provides summary of modeler state, case information, and grid statistics.
        
        Returns:
            str: Multi-line string representation showing modeler configuration and status.
            
        Example:
            >>> print(modeler)
            PSSEModeler:
            ├─ Case: IEEE_30_bus.raw (100.0 MVA base)
            ├─ Grid Components: 30 buses, 6 generators, 21 loads, 41 lines
            ├─ Time Configuration: 2025-08-23 10:00:00 → 2025-08-23 12:00:00 (5 min steps)
            ├─ WEC Farms: 2 farms, 15 total devices
            └─ Status: ✓ Initialized, ✓ Power flow converged
        """
        # Get class name (e.g., "PSSEModeler", "PyPSAModeler")
        class_name = self.__class__.__name__
        
        # Case information
        case_name = getattr(self.engine, 'case_name', 'No case loaded')
        if hasattr(self.engine, 'case_file') and self.engine.case_file:
            case_file = str(self.engine.case_file).split('\\')[-1].split('/')[-1]  # Get filename
            case_name = case_file
        
        sbase_info = f" ({self.sbase} MVA base)" if self.sbase else ""
        case_line = f"├─ Case: {case_name}{sbase_info}"
        
        # Grid component counts
        grid_line = (f"├─ Grid Components: {len(self.grid.bus)} buses, "
                    f"{len(self.grid.gen)} generators, {len(self.grid.load)} loads, "
                    f"{len(self.grid.line)} lines")
        
        # Time configuration
        time_line = "├─ Time Configuration: Not configured"
        if hasattr(self.engine, 'time') and self.engine.time:
            time_mgr = self.engine.time
            if hasattr(time_mgr, 'start_time') and hasattr(time_mgr, 'delta_time'):
                start = getattr(time_mgr, 'start_time', 'Unknown')
                end = getattr(time_mgr, 'sim_stop', 'Unknown')
                delta = getattr(time_mgr, 'delta_time', 'Unknown')
                
                if start != 'Unknown' and end != 'Unknown':
                    time_line = f"├─ Time Configuration: {start} → {end} ({delta} min steps)"
                elif start != 'Unknown':
                    time_line = f"├─ Time Configuration: Starting {start} ({delta} min steps)"
        
        # WEC farm information
        wec_line = "├─ WEC Farms: None"
        if hasattr(self.engine, 'wec_farms') and self.engine.wec_farms:
            num_farms = len(self.engine.wec_farms)
            total_devices = sum(len(farm.devices) for farm in self.engine.wec_farms.values())
            wec_line = f"├─ WEC Farms: {num_farms} farms, {total_devices} total devices"
        
        # Status indicators (this would be implemented by subclasses with more specific info)
        status_line = "└─ Status: ⚠ Not initialized"
        
        return (
            f"{class_name}:\n"
            f"{case_line}\n"
            f"{grid_line}\n"
            f"{time_line}\n"
            f"{wec_line}\n"
            f"{status_line}"
        )

    @abstractmethod
    def init_api(self) -> bool:
        """Initialize backend power system tool and load case file.
        
        Returns:
            bool: True if initialization successful, False otherwise.
            
        Raises:
            ImportError: If backend tool not found or configured.
            ValueError: If case file invalid or cannot be loaded.
            
        Notes:
            Implementation should:
            
            - Initialize backend API/environment
            - Load case file (.sav, .raw, etc.)
            - Set system base MVA (self.sbase)
            - Perform initial power flow solution
            - Take initial grid state snapshot
            
        Example:
            >>> if modeler.init_api():
            ...     print("Backend initialized successfully")
        """
        pass

    @abstractmethod
    def solve_powerflow(self) -> bool:
        """Run power flow solution using backend solver.
        
        Returns:
            bool: True if power flow converged, False otherwise.
            
        Notes:
            Implementation should:
            
            - Call backend's power flow solver
            - Check convergence status
            - Handle solver-specific parameters
            - Suppress verbose output if needed
            
        Example:
            >>> if modeler.solve_powerflow():
            ...     print("Power flow converged")
        """
        pass

    @abstractmethod
    def add_wec_farm(self, farm: WECFarm) -> bool:
        """Add WEC farm to power system model.

        Args:
            farm (WECFarm): WEC farm with connection details and power characteristics.

        Returns:
            bool: True if farm added successfully, False otherwise.

        Raises:
            ValueError: If WEC farm parameters invalid.
            
        Notes:
            Implementation should:
            
            - Create new bus for WEC connection
            - Add WEC generator with power characteristics
            - Create transmission line to existing grid
            - Update grid state after modifications
            - Solve power flow to validate changes
            
        Example:
            >>> if modeler.add_wec_farm(wec_farm):
            ...     print("WEC farm added successfully")
        """
        pass

    @abstractmethod
    def simulate(self, load_curve: Optional[pd.DataFrame] = None) -> bool:
        """Run time-series simulation with WEC and load updates.
        
        Args:
            load_curve (pd.DataFrame, optional): Load values for each bus at each snapshot.
                Index: snapshots, columns: bus IDs. If None, loads remain constant.

        Returns:
            bool: True if simulation completes successfully, False otherwise.
            
        Raises:
            Exception: If error updating components or solving power flow.

        Notes:
            Implementation should:
            
            - Iterate through all time snapshots from engine.time
            - Update WEC generator power outputs [MW] from farm data
            - Update bus loads [MW] if load_curve provided
            - Solve power flow at each time step
            - Capture grid state snapshots for analysis
            - Handle convergence failures gracefully
            
        Example:
            >>> # Constant loads
            >>> modeler.simulate()
            >>> 
            >>> # Time-varying loads
            >>> modeler.simulate(load_curve=load_df)
        """
        pass

    @abstractmethod
    def take_snapshot(self, timestamp: datetime) -> None:
        """Capture current grid state at specified timestamp.
        
        Args: 
            timestamp (datetime): Timestamp for the snapshot.

        Notes:
            Implementation should:
            
            - Extract bus data: voltages [p.u.], [degrees], power [MW], [MVAr]
            - Extract generator data: power outputs [MW], [MVAr], status
            - Extract line data: power flows [MW], [MVAr], loading [%]
            - Extract load data: power consumption [MW], [MVAr]
            - Convert to standardized WEC-GRID schema
            - Store in self.grid with timestamp indexing
            
        Example:
            >>> modeler.take_snapshot(datetime.now())
        """
        pass

    # Convenience accessors
    @property
    def bus(self) -> Optional[pd.DataFrame]:
        """Current bus state with columns: bus, bus_name, type, p, q, v_mag, angle_deg, base.
        
        Returns:
            pd.DataFrame: Bus state data [p.u. on system MVA base] or None if no snapshots.
        """
        return self.grid.bus

    @property
    def gen(self) -> Optional[pd.DataFrame]:
        """Current generator state with columns: gen, bus, p, q, base, status.
        
        Returns:
            pd.DataFrame: Generator state data [p.u. on generator MVA base] or None if no snapshots.
        """
        return self.grid.gen

    @property
    def load(self) -> Optional[pd.DataFrame]:
        """Current load state with columns: load, bus, p, q, base, status.
        
        Returns:
            pd.DataFrame: Load state data [p.u. on system MVA base] or None if no snapshots.
        """
        return self.grid.load

    @property
    def line(self) -> Optional[pd.DataFrame]:
        """Current line state with columns: line, ibus, jbus, line_pct, status.
        
        Returns:
            pd.DataFrame: Line state data [line_pct as % of thermal rating] or None if no snapshots.
        """
        return self.grid.line

    @property
    def bus_t(self) -> Dict[str, pd.DataFrame]:
        """Time-series bus data for all snapshots.
        
        Returns:
            Dict[str, pd.DataFrame]: Keys: timestamp strings, Values: bus state DataFrames.
        """
        return self.grid.bus_t

    @property
    def gen_t(self) -> Dict[str, pd.DataFrame]:
        """Time-series generator data for all snapshots.
        
        Returns:
            Dict[str, pd.DataFrame]: Keys: timestamp strings, Values: generator state DataFrames.
        """
        return self.grid.gen_t

    @property
    def load_t(self) -> Dict[str, pd.DataFrame]:
        """Time-series load data for all snapshots.
        
        Returns:
            Dict[str, pd.DataFrame]: Keys: timestamp strings, Values: load state DataFrames.
        """
        return self.grid.load_t

    @property
    def line_t(self) -> Dict[str, pd.DataFrame]:
        """Time-series line data for all snapshots.
        
        Returns:
            Dict[str, pd.DataFrame]: Keys: timestamp strings, Values: line state DataFrames.
        """
        return self.grid.line_t