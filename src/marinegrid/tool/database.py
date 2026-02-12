"""
Database utilities for Marine-Grid.

File: src/marinegrid/tool/database.py

Configuration resolution order for database path:
- Environment variable ``MARINEGRID_DB_PATH`` (if set)
- User config file at ``<user-config>/marinegrid/database_config.json``
- Otherwise, user must configure a path via API methods
"""

# Standard library
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple, Union, Any, TYPE_CHECKING

# Third-party
import pandas as pd

if TYPE_CHECKING:
    from ..study import Study


def _user_config_dir() -> Path:
    """Return a user-writable config directory for Marine-Grid.

    Uses ``platformdirs`` if available, otherwise falls back to ``~/.marinegrid``.
    """
    try:
        from platformdirs import user_config_dir

        return Path(user_config_dir(appname="marinegrid", appauthor=False))
    except ImportError:
        return Path.home() / ".marinegrid"


def _db_config_file() -> Path:
    """Return path to database configuration file."""
    return _user_config_dir() / "database_config.json"


def get_database_config() -> Optional[str]:
    """Resolve database path from env var or user config file.

    Resolution order:
    1) ``MARINEGRID_DB_PATH`` environment variable
    2) ``<user-config>/marinegrid/database_config.json``

    Returns:
        Database path, or None if not configured.
    """
    env_path = os.getenv("MARINEGRID_DB_PATH")
    if env_path:
        return str(Path(env_path).expanduser().absolute())

    config_file = _db_config_file()
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
                db_path = config.get("database_path")
                if db_path:
                    return str(Path(db_path).absolute())
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def save_database_config(db_path: str) -> None:
    """Persist database path in user config directory.

    Args:
        db_path: Path to database file.

    Raises:
        TypeError: If db_path is not a string.
    """
    cfg_dir = _user_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    config_file = _db_config_file()
    config = {"database_path": str(Path(db_path).absolute())}
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)


class Database:
    """
    SQLite interface for Marine-Grid simulations.

    Provides database connectivity for storing and retrieving simulation
    results, WEC-Sim data, and grid state history.

    Attributes:
        db_path: Path to the SQLite database file.
        study: Reference to parent Study object (if any).

    Example:
        >>> db = Database()
        >>> db.set_database_path("path/to/marinegrid.db")
        >>> results = db.query("SELECT * FROM wec_simulations", return_type="df")
    """

    def __init__(self, study: Optional["Study"] = None):
        """
        Initialize database handler.

        Args:
            study: Optional reference to parent Study object.
        """
        self.study = study
        self.db_path: Optional[str] = None

        # Try to get database path from config
        configured_path = get_database_config()
        if configured_path and os.path.exists(configured_path):
            self.db_path = configured_path

    def __repr__(self) -> str:
        """Return a compact summary of database state."""
        if self.db_path:
            return f"Database(path={self.db_path!r})"
        return "Database(not configured)"

    @contextmanager
    def connection(self):
        """
        Context manager for safe database connections.

        Provides transaction safety with automatic commit on success and
        rollback on exceptions. Connection closed automatically.

        Yields:
            sqlite3.Connection: Database connection object.

        Raises:
            ValueError: If database path is not configured.
        """
        if self.db_path is None:
            raise ValueError(
                "Database path not configured. "
                "Use database.set_database_path() to configure."
            )

        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def set_database_path(self, db_path: Union[str, Path]) -> str:
        """
        Set database path and save to configuration.

        Args:
            db_path: Path to database file.

        Returns:
            Absolute path to the database.

        Raises:
            TypeError: If db_path is not a str or Path.
            FileNotFoundError: If database file doesn't exist.
            ValueError: If db_path is not a file.
        """
        path = Path(db_path).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"Database file not found: {path}")

        self.db_path = str(path)
        save_database_config(self.db_path)

        return self.db_path

    def initialize_database(self, db_path: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize database with required schema.

        Creates the database file and all required tables if they don't exist.

        Args:
            db_path: Optional path for new database. If provided, updates
                the saved configuration.
        """
        if db_path:
            path = Path(db_path).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(path)
            save_database_config(self.db_path)

        if self.db_path is None:
            raise ValueError(
                "No database path configured. Provide db_path parameter or "
                "use database.set_database_path() first."
            )

        with self.connection() as conn:
            cursor = conn.cursor()

            # WEC simulation metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wec_simulations (
                    wec_sim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_type TEXT NOT NULL,
                    sim_duration_sec REAL NOT NULL,
                    delta_time REAL NOT NULL,
                    wave_height_m REAL,
                    wave_period_sec REAL,
                    wave_spectrum TEXT,
                    wave_class TEXT,
                    wave_seed INTEGER,
                    simulation_hash TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # WEC power time-series data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wec_power_results (
                    wec_sim_id INTEGER NOT NULL,
                    time_sec REAL NOT NULL,
                    device_index INTEGER NOT NULL DEFAULT 0,
                    p_w REAL,
                    q_var REAL,
                    wave_elevation_m REAL,
                    PRIMARY KEY (wec_sim_id, time_sec, device_index),
                    FOREIGN KEY (wec_sim_id)
                        REFERENCES wec_simulations(wec_sim_id) ON DELETE CASCADE
                )
            """)

            # Grid simulation metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grid_simulations (
                    grid_sim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sim_name TEXT,
                    case_name TEXT NOT NULL,
                    sbase_mva REAL NOT NULL,
                    sim_start_time TEXT NOT NULL,
                    sim_end_time TEXT,
                    delta_time INTEGER,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # WEC-Grid integration mapping
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wec_integrations (
                    integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grid_sim_id INTEGER NOT NULL,
                    wec_sim_id INTEGER NOT NULL,
                    farm_name TEXT NOT NULL,
                    bus_location INTEGER NOT NULL,
                    num_devices INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grid_sim_id)
                        REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE,
                    FOREIGN KEY (wec_sim_id)
                        REFERENCES wec_simulations(wec_sim_id) ON DELETE CASCADE
                )
            """)

            # Grid component results tables
            for component in ["bus", "generator", "load", "line", "transformer"]:
                self._create_component_table(cursor, component)

            # Performance indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_wec_power_time "
                "ON wec_power_results(wec_sim_id, time_sec)"
            )

    def _create_component_table(self, cursor, component: str) -> None:
        """Create a grid component results table."""
        if component == "bus":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bus_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    bus INTEGER NOT NULL,
                    bus_name TEXT,
                    type TEXT,
                    p REAL,
                    q REAL,
                    v_mag REAL,
                    angle_deg REAL,
                    vbase REAL,
                    PRIMARY KEY (grid_sim_id, timestamp, bus),
                    FOREIGN KEY (grid_sim_id)
                        REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
        elif component == "generator":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS generator_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    gen INTEGER NOT NULL,
                    gen_name TEXT,
                    bus INTEGER NOT NULL,
                    p REAL,
                    q REAL,
                    p_nom REAL,
                    status INTEGER,
                    PRIMARY KEY (grid_sim_id, timestamp, gen),
                    FOREIGN KEY (grid_sim_id)
                        REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
        elif component == "load":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS load_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    load INTEGER NOT NULL,
                    load_name TEXT,
                    bus INTEGER NOT NULL,
                    p REAL,
                    q REAL,
                    status INTEGER,
                    PRIMARY KEY (grid_sim_id, timestamp, load),
                    FOREIGN KEY (grid_sim_id)
                        REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
        elif component == "line":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS line_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    line INTEGER NOT NULL,
                    line_name TEXT,
                    ibus INTEGER NOT NULL,
                    jbus INTEGER NOT NULL,
                    loading_pct REAL,
                    status INTEGER,
                    PRIMARY KEY (grid_sim_id, timestamp, line),
                    FOREIGN KEY (grid_sim_id)
                        REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
        elif component == "transformer":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transformer_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    transformer INTEGER NOT NULL,
                    transformer_name TEXT,
                    bus0 INTEGER NOT NULL,
                    bus1 INTEGER NOT NULL,
                    tap_ratio REAL,
                    phase_shift REAL,
                    loading_pct REAL,
                    status INTEGER,
                    PRIMARY KEY (grid_sim_id, timestamp, transformer),
                    FOREIGN KEY (grid_sim_id)
                        REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)

    def query(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        return_type: str = "raw",
    ) -> Union[List[Tuple], pd.DataFrame, List[Dict[str, Any]]]:
        """
        Execute SQL query with flexible result formatting.

        Args:
            sql: SQL query string.
            params: Query parameters for safe substitution.
            return_type: Format for results - 'raw', 'df', or 'dict'.

        Returns:
            Results in specified format:
            - 'raw': List of tuples (default SQLite format)
            - 'df': pandas DataFrame with column names
            - 'dict': List of dictionaries with column names as keys

        Raises:
            TypeError: If sql is not a string.
            ValueError: If return_type is not one of 'raw', 'df', 'dict'.

        Example:
            >>> db.query(
            ...     "SELECT * FROM wec_simulations WHERE model_type = ?",
            ...     params=("RM3",),
            ...     return_type="df"
            ... )
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params or ())
            result = cursor.fetchall()

            if not result:
                if return_type == "df":
                    return pd.DataFrame()
                elif return_type == "dict":
                    return []
                return result

            if return_type == "df":
                columns = [desc[0] for desc in cursor.description]
                return pd.DataFrame(result, columns=columns)
            elif return_type == "dict":
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in result]
            else:
                return result

    def execute(self, sql: str, params: Optional[Tuple] = None) -> int:
        """
        Execute SQL statement (INSERT, UPDATE, DELETE).

        Args:
            sql: SQL statement.
            params: Statement parameters.

        Returns:
            Number of rows affected or last row ID for INSERT.

        Raises:
            TypeError: If sql is not a string.
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params or ())
            return cursor.lastrowid if "INSERT" in sql.upper() else cursor.rowcount

    def get_wec_simulations(self) -> pd.DataFrame:
        """
        Get all WEC simulation metadata.

        Returns:
            DataFrame of WEC simulations with parameters.
        """
        return self.query(
            """
            SELECT wec_sim_id, model_type, sim_duration_sec, delta_time,
                   wave_height_m, wave_period_sec, wave_spectrum, wave_class,
                   created_at
            FROM wec_simulations
            ORDER BY created_at DESC
            """,
            return_type="df",
        )

    def get_grid_simulations(self) -> pd.DataFrame:
        """
        Get all grid simulation metadata.

        Returns:
            DataFrame of grid simulations.
        """
        return self.query(
            """
            SELECT grid_sim_id, sim_name, case_name, sbase_mva,
                   sim_start_time, sim_end_time, delta_time, notes, created_at
            FROM grid_simulations
            ORDER BY created_at DESC
            """,
            return_type="df",
        )
