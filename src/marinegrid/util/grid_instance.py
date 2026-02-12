"""
Grid state data container for a single timestamp.

File: src/marinegrid/util/grid_instance.py
"""

# Standard library
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Set

# Third-party
import pandas as pd

@dataclass
class ComponentSchema:
    """
    Schema definition for a grid component DataFrame.

    Defines required and optional columns with their expected types
    and units for standardized power system data.

    Attributes:
        name: Component type name (e.g., "bus", "gen").
        id_column: Primary identifier column name.
        required_columns: List of columns that must be present.
        optional_columns: List of columns that may be present.
        units: Dictionary mapping column names to unit descriptions.
    """
    name: str
    id_column: str
    required_columns: List[str]
    optional_columns: List[str]
    units: Dict[str, str]


# Standard schemas for each component type
# All power values (p, q) are in per-unit on system MVA base
BUS_SCHEMA = ComponentSchema(
    name="bus",
    id_column="bus",
    required_columns=["bus", "bus_name", "type", "p", "q", "v_mag", "angle_deg"],
    optional_columns=["vbase"],
    units={
        "bus": "dimensionless",
        "bus_name": "string",
        "type": "string (PQ, PV, Slack)",
        "p": "per-unit (system MVA base)",
        "q": "per-unit (system MVA base)",
        "v_mag": "per-unit",
        "angle_deg": "degrees",
        "vbase": "kV",
    }
)

GEN_SCHEMA = ComponentSchema(
    name="gen",
    id_column="gen",
    required_columns=["gen", "gen_name", "bus", "p", "q", "status"],
    optional_columns=["p_nom", "q_max", "q_min"],
    units={
        "gen": "dimensionless",
        "gen_name": "string",
        "bus": "dimensionless",
        "p": "per-unit (system MVA base)",
        "q": "per-unit (system MVA base)",
        "p_nom": "MW",
        "status": "0/1",
    }
)

LINE_SCHEMA = ComponentSchema(
    name="line",
    id_column="line",
    required_columns=["line", "line_name", "ibus", "jbus", "status"],
    optional_columns=["p0", "p1", "q0", "q1", "loading_pct", "s_nom"],
    units={
        "line": "dimensionless",
        "line_name": "string",
        "ibus": "dimensionless (from bus)",
        "jbus": "dimensionless (to bus)",
        "p0": "per-unit (system MVA base, flow at ibus)",
        "p1": "per-unit (system MVA base, flow at jbus)",
        "q0": "per-unit (system MVA base)",
        "q1": "per-unit (system MVA base)",
        "loading_pct": "percent of s_nom",
        "s_nom": "MVA",
        "status": "0/1",
    }
)

LOAD_SCHEMA = ComponentSchema(
    name="load",
    id_column="load",
    required_columns=["load", "load_name", "bus", "p", "q", "status"],
    optional_columns=[],
    units={
        "load": "dimensionless",
        "load_name": "string",
        "bus": "dimensionless",
        "p": "per-unit (system MVA base)",
        "q": "per-unit (system MVA base)",
        "status": "0/1",
    }
)

TRANSFORMER_SCHEMA = ComponentSchema(
    name="transformer",
    id_column="transformer",
    required_columns=["transformer", "transformer_name", "bus0", "bus1", "status"],
    optional_columns=["p0", "p1", "tap_ratio", "phase_shift", "s_nom", "loading_pct"],
    units={
        "transformer": "dimensionless",
        "transformer_name": "string",
        "bus0": "dimensionless",
        "bus1": "dimensionless",
        "p0": "per-unit (system MVA base)",
        "p1": "per-unit (system MVA base)",
        "tap_ratio": "dimensionless",
        "phase_shift": "degrees",
        "s_nom": "MVA",
        "loading_pct": "percent",
        "status": "0/1",
    }
)

# Map component names to schemas
COMPONENT_SCHEMAS = {
    "bus": BUS_SCHEMA,
    "gen": GEN_SCHEMA,
    "line": LINE_SCHEMA,
    "load": LOAD_SCHEMA,
    "transformer": TRANSFORMER_SCHEMA,
}


class GridInstance:
    """
    Container for power system component data at a single point in time.

    Stores DataFrames of bus, line, generator, load, and transformer
    data at a specific timestamp. All power quantities (p, q) are stored
    in per-unit on the system MVA base for cross-platform consistency.

    Attributes:
        timestamp: Time point for this grid state snapshot.
        bus: DataFrame of bus data (voltage, power, type).
        line: DataFrame of line data (flows, loading, status).
        gen: DataFrame of generator data (output, status).
        load: DataFrame of load data (consumption, status).
        transformer: DataFrame of transformer data (flows, taps, status).

    Example:
        >>> state = GridInstance()
        >>> state.timestamp = pd.Timestamp("2024-01-01 12:00:00")
        >>> state.bus = bus_dataframe  # Must have required columns
        >>> print(state)
        GridInstance @ 2024-01-01 12:00:00
        ├─ Buses: 30
        ├─ Generators: 6
        ├─ Lines: 41
        ├─ Loads: 21
        └─ Transformers: 0
    """

    def __init__(self):
        """
        Initialize an empty GridInstance.

        All component DataFrames are set to None initially and must
        be populated via property setters.
        """
        self._bus: Optional[pd.DataFrame] = None
        self._line: Optional[pd.DataFrame] = None
        self._gen: Optional[pd.DataFrame] = None
        self._load: Optional[pd.DataFrame] = None
        self._transformer: Optional[pd.DataFrame] = None
        self._timestamp: Optional[pd.Timestamp] = None

    def __repr__(self) -> str:
        """Return a formatted summary of the grid instance."""
        ts_str = str(self._timestamp) if self._timestamp else "No timestamp"

        bus_count = len(self._bus) if self._bus is not None else 0
        gen_count = len(self._gen) if self._gen is not None else 0
        line_count = len(self._line) if self._line is not None else 0
        load_count = len(self._load) if self._load is not None else 0
        tx_count = len(self._transformer) if self._transformer is not None else 0

        return (
            f"GridInstance @ {ts_str}\n"
            f"├─ Buses: {bus_count}\n"
            f"├─ Generators: {gen_count}\n"
            f"├─ Lines: {line_count}\n"
            f"├─ Loads: {load_count}\n"
            f"└─ Transformers: {tx_count}"
        )

    # -------------------------------------------------------------------------
    # Timestamp property
    # -------------------------------------------------------------------------

    @property
    def timestamp(self) -> Optional[pd.Timestamp]:
        """Get the timestamp for this grid state."""
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

    # -------------------------------------------------------------------------
    # Component properties with validation
    # -------------------------------------------------------------------------

    @property
    def bus(self) -> Optional[pd.DataFrame]:
        """Get bus data DataFrame."""
        return self._bus

    @bus.setter
    def bus(self, value: Optional[pd.DataFrame]):
        """Set bus data DataFrame with validation."""
        if value is not None:
            self._validate_dataframe(value, "bus")
        self._bus = value

    @property
    def line(self) -> Optional[pd.DataFrame]:
        """Get line data DataFrame."""
        return self._line

    @line.setter
    def line(self, value: Optional[pd.DataFrame]):
        """Set line data DataFrame with validation."""
        if value is not None:
            self._validate_dataframe(value, "line")
        self._line = value

    @property
    def gen(self) -> Optional[pd.DataFrame]:
        """Get generator data DataFrame."""
        return self._gen

    @gen.setter
    def gen(self, value: Optional[pd.DataFrame]):
        """Set generator data DataFrame with validation."""
        if value is not None:
            self._validate_dataframe(value, "gen")
        self._gen = value

    @property
    def load(self) -> Optional[pd.DataFrame]:
        """Get load data DataFrame."""
        return self._load

    @load.setter
    def load(self, value: Optional[pd.DataFrame]):
        """Set load data DataFrame with validation."""
        if value is not None:
            self._validate_dataframe(value, "load")
        self._load = value

    @property
    def transformer(self) -> Optional[pd.DataFrame]:
        """Get transformer data DataFrame."""
        return self._transformer

    @transformer.setter
    def transformer(self, value: Optional[pd.DataFrame]):
        """Set transformer data DataFrame with validation."""
        if value is not None:
            self._validate_dataframe(value, "transformer")
        self._transformer = value

    # -------------------------------------------------------------------------
    # Validation methods
    # -------------------------------------------------------------------------

    def _validate_dataframe(self, df: pd.DataFrame, component: str) -> None:
        """
        Validate a component DataFrame against its schema.

        Args:
            df: DataFrame to validate.
            component: Component type name ("bus", "gen", "line", "load", "transformer").

        Raises:
            TypeError: If df is not a DataFrame.
            ValueError: If required columns are missing.
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"{component} must be a pandas DataFrame instance.")

        # Empty DataFrames are allowed
        if df.empty:
            return

        schema = COMPONENT_SCHEMAS.get(component)
        if schema is None:
            return  # No schema defined, skip validation

        # Check for required columns
        missing = set(schema.required_columns) - set(df.columns)
        if missing:
            # Warn but don't raise - allow flexibility
            pass  # Could add logging here

    def validate(self) -> Dict[str, List[str]]:
        """
        Validate all component DataFrames and return any issues.

        Returns:
            Dictionary mapping component names to lists of validation issues.
            Empty dict if no issues found.
        """
        issues = {}

        components = {
            "bus": self._bus,
            "gen": self._gen,
            "line": self._line,
            "load": self._load,
            "transformer": self._transformer,
        }

        for name, df in components.items():
            component_issues = []

            if df is None:
                continue

            schema = COMPONENT_SCHEMAS.get(name)
            if schema is None:
                continue

            # Check required columns
            missing = set(schema.required_columns) - set(df.columns)
            if missing:
                component_issues.append(f"Missing required columns: {missing}")

            # Check ID column exists and has no nulls
            if schema.id_column in df.columns:
                if df[schema.id_column].isna().any():
                    component_issues.append(f"ID column '{schema.id_column}' contains null values")

            if component_issues:
                issues[name] = component_issues

        return issues

    # -------------------------------------------------------------------------
    # Summary methods
    # -------------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """
        Generate a summary of the grid state.

        Returns:
            Dictionary with summary statistics for each component type.
        """
        result = {
            "timestamp": self._timestamp,
            "bus_count": len(self._bus) if self._bus is not None else 0,
            "gen_count": len(self._gen) if self._gen is not None else 0,
            "line_count": len(self._line) if self._line is not None else 0,
            "load_count": len(self._load) if self._load is not None else 0,
            "transformer_count": len(self._transformer) if self._transformer is not None else 0,
        }

        # Add power summaries if data available
        if self._gen is not None and "p" in self._gen.columns:
            result["total_generation_pu"] = float(self._gen["p"].sum())

        if self._load is not None and "p" in self._load.columns:
            result["total_load_pu"] = float(self._load["p"].sum())

        if self._bus is not None and "v_mag" in self._bus.columns:
            result["v_min_pu"] = float(self._bus["v_mag"].min())
            result["v_max_pu"] = float(self._bus["v_mag"].max())

        return result

    def to_dict(self) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Convert all component data to a dictionary.

        Returns:
            Dictionary mapping component names to their DataFrames.
        """
        return {
            "bus": self._bus,
            "gen": self._gen,
            "line": self._line,
            "load": self._load,
            "transformer": self._transformer,
        }

    @classmethod
    def get_schema(cls, component: str) -> Optional[ComponentSchema]:
        """
        Get the schema for a component type.

        Args:
            component: Component type name ("bus", "gen", "line", "load", "transformer").

        Returns:
            ComponentSchema for the component or None if not found.

        Raises:
            ValueError: If component is not a valid component type.
        """
        return COMPONENT_SCHEMAS.get(component)

    @classmethod
    def get_required_columns(cls, component: str) -> List[str]:
        """
        Get required columns for a component type.

        Args:
            component: Component type name ("bus", "gen", "line", "load", "transformer").

        Returns:
            List of required column names.

        Raises:
            ValueError: If component is not a valid component type.
        """
        schema = COMPONENT_SCHEMAS.get(component)
        return schema.required_columns if schema else []

    @classmethod
    def get_units(cls, component: str) -> Dict[str, str]:
        """
        Get unit descriptions for a component type's columns.

        Args:
            component: Component type name ("bus", "gen", "line", "load", "transformer").

        Returns:
            Dictionary mapping column names to unit descriptions.

        Raises:
            ValueError: If component is not a valid component type.
        """
        schema = COMPONENT_SCHEMAS.get(component)
        return schema.units if schema else {}
