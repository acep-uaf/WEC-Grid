# src/wecgrid/modelers/power_system/base.py
"""Base interfaces and data containers for power-system modelers."""

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
    """Dict with attribute-style access (``d.key``) to keys.

    Raises:
        AttributeError: If the attribute is not present.
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


@dataclass
class SolveReport:
    """Lightweight performance log for a simulation run.

    Attributes:
        simulation_time: Total wall time in seconds.
        case: Case name/identifier.
        software: Backend name ("psse", "pypsa").
        iter_time: Per-step iteration time [s].
        converged: Per-step convergence flags.
        pf_solve_time: Powerflow solve time [s] per step.
        pf_solve_iter: Solver iterations per step.
        snapshot_time: Snapshot capture time [s] per step.
        snapshot: Snapshot identifiers (timestamps).
        message: Solver status messages.
    """
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
        """Return a one-line summary of solve status and timing."""
        if not self.converged:
            status = "Unknown"
        else:
            status = "Successful" if all(self.converged) else "Failed"
        return (
            f"SolveReport: {status}, steps={len(self.snapshot)}, time={self.simulation_time:.2f}s, case={self.case}, sw={self.software}"
        )

    def add_iteration_time(self, time_val: float):
        """Record iteration timing for current simulation snapshot.
        
        Args:
            time_val (float): Iteration execution time in seconds.
        """
        self.iter_time.append(time_val)

    def add_pf_solve_data(
        self, solve_time: float, iterations: int, converged: bool, msg: str
    ):
        """Record power flow solver performance data for current snapshot.
        
        Args:
            solve_time (float): Power flow solution time in seconds.
            iterations (int): Number of solver iterations required.
            converged (bool): Whether power flow converged successfully.
            msg (str): Solver status or error message.
        """
        self.converged.append(converged)
        self.pf_solve_time.append(solve_time)
        self.pf_solve_iter.append(iterations)
        self.message.append(msg)

    def add_snapshot_data(self, snapshot_time: float):
        """Record grid state snapshot capture timing.
        
        Args:
            snapshot_time (float): Time required to capture grid state in seconds.
        """
        self.snapshot_time.append(snapshot_time)

    def add_snapshot(self, snapshot_id):
        """Record snapshot identifier for simulation tracking.
        
        Args:
            snapshot_id: Timestamp or identifier for the simulation snapshot.
        """
        self.snapshot.append(snapshot_id)

    @property
    def dataframe(self) -> pd.DataFrame:
        """Convert performance metrics to DataFrame for analysis.
        
        Returns:
            pd.DataFrame: Performance data with columns for timing, convergence,
                and solver statistics. Missing values padded with None.
        """
        # Pad shorter lists with None to match longest list
        max_len = max(
            len(getattr(self, attr))
            for attr in [
                "iter_time",
                "converged",
                "pf_solve_time",
                "pf_solve_iter",
                "snapshot_time",
                "snapshot",
                "message",
            ]
        )

        data = {}
        for attr in [
            "iter_time",
            "converged",
            "pf_solve_time",
            "pf_solve_iter",
            "snapshot_time",
            "snapshot",
            "message",
        ]:
            values = getattr(self, attr)
            # Pad with None if shorter than max_len
            data[attr] = values + [None] * (max_len - len(values))

        return pd.DataFrame(data)


@dataclass
class GridState:
    """Snapshot and time-series container for grid components.

    Power quantities are per-unit on system base unless noted.

    Attributes:
        software: Backend identifier.
        case: Case identifier.
        bus: Current bus snapshot DataFrame.
        gen: Current generator snapshot DataFrame.
        line: Current line snapshot DataFrame.
        load: Current load snapshot DataFrame.
        bus_t: Time series by bus variable.
        gen_t: Time series by generator variable.
        line_t: Time series by line variable.
        load_t: Time series by load variable.
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
        """Return a compact summary with component counts."""

        def ts_info(component_t):
            """Format time-series information with variable count and snapshot count."""
            if not component_t:
                return "none"
            variables = list(component_t.keys())
            if variables:
                # Get snapshot count from first variable's DataFrame
                snapshot_count = (
                    len(component_t[variables[0]])
                    if len(component_t[variables[0]]) > 0
                    else 0
                )
                var_str = ", ".join(variables)
                return f"{var_str} ({snapshot_count} snapshots)"
            return "none"

        def backend_name(software):
            """Convert software code to descriptive name."""
            names = {
                "psse": "PSS®E Modeler",
                "pypsa": "PyPSA Modeler",
                "": "No backend specified",
            }
            return names.get(software.lower(), f"{software} simulation modeler")

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
        """Set current snapshot and append to time series for a component.

        Args:
            component: One of "bus", "gen", "line", "load".
            timestamp: Snapshot timestamp.
            df: Component DataFrame. Must define ``df.attrs['df_type']`` and
                include an ID column (e.g., "bus", "gen").

        Raises:
            ValueError: If the component or ID mapping cannot be determined.
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
            raise ValueError(
                f"'{id_col}' not found in columns or as index for df_type='{df_type}'"
            )

        df = df.copy()
        # df.set_index(id_col, inplace=True)   # now index = IDs (bus #, gen ID, etc.)

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
                series_with_names.index = [
                    id_to_name.get(idx, str(idx)) for idx in series.index
                ]

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
        report (SolveReport): Performance tracking for simulation runs.
        sbase (float, optional): System base power [MVA].

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
        case_name = getattr(self.engine, "case_name", "No case loaded")
        if hasattr(self.engine, "case_file") and self.engine.case_file:
            case_file = (
                str(self.engine.case_file).split("\\")[-1].split("/")[-1]
            )  # Get filename
            case_name = case_file

        sbase_info = f" ({self.sbase} MVA base)" if self.sbase else ""
        case_line = f"├─ Case: {case_name}{sbase_info}"

        # Grid component counts
        grid_line = (
            f"├─ Grid Components: {len(self.grid.bus)} buses, "
            f"{len(self.grid.gen)} generators, {len(self.grid.load)} loads, "
            f"{len(self.grid.line)} lines"
        )

        # Time configuration
        time_line = "├─ Time Configuration: Not configured"
        if hasattr(self.engine, "time") and self.engine.time:
            time_mgr = self.engine.time
            if hasattr(time_mgr, "start_time") and hasattr(time_mgr, "delta_time"):
                start = getattr(time_mgr, "start_time", "Unknown")
                end = getattr(time_mgr, "sim_stop", "Unknown")
                delta = getattr(time_mgr, "delta_time", "Unknown")

                if start != "Unknown" and end != "Unknown":
                    time_line = (
                        f"├─ Time Configuration: {start} → {end} ({delta} min steps)"
                    )
                elif start != "Unknown":
                    time_line = (
                        f"├─ Time Configuration: Starting {start} ({delta} min steps)"
                    )

        # WEC farm information
        wec_line = "├─ WEC Farms: None"
        if hasattr(self.engine, "wec_farms") and self.engine.wec_farms:
            num_farms = len(self.engine.wec_farms)
            total_devices = sum(
                len(farm.wec_devices) for farm in self.engine.wec_farms
            )
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
            Implementation should initialize backend API/environment, load case
            file (.sav, .raw, etc.), set system base MVA (self.sbase), perform
            initial power flow solution, and take initial grid state snapshot.
        """
        pass

    @abstractmethod
    def solve_powerflow(self) -> bool:
        """Run power flow solution using backend solver.

        Returns:
            bool: True if power flow converged, False otherwise.

        Notes:
            Implementation should call backend's power flow solver, check
            convergence status, handle solver-specific parameters, and
            suppress verbose output if needed.
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
            Implementation should create new bus for WEC connection, add WEC
            generator with power characteristics, create transmission line to
            existing grid, update grid state after modifications, and solve
            power flow to validate changes.
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
            Implementation should iterate through all time snapshots from engine.time,
            update WEC generator power outputs [MW] from farm data, update bus loads
            [MW] if load_curve provided, solve power flow at each time step, capture
            grid state snapshots for analysis, and handle convergence failures gracefully.
        """
        pass

    @abstractmethod
    def take_snapshot(self, timestamp: datetime) -> None:
        """Capture current grid state at specified timestamp.

        Args:
            timestamp (datetime): Timestamp for the snapshot.

        Notes:
            Implementation should extract bus data (voltages [p.u.], [degrees], power
            [MW], [MVAr]), generator data (power outputs [MW], [MVAr], status), line
            data (power flows [MW], [MVAr], loading [%]), and load data (power
            consumption [MW], [MVAr]), convert to standardized WEC-GRID schema,
            and store in self.grid with timestamp indexing.
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
