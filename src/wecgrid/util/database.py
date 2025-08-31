"""WEC-Grid Database Interface Module.

SQLite database interface for WEC-Grid simulation data management, including 
time series storage, configuration persistence, and result archival.
"""

# Standard library
import json
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Third-party
import pandas as pd

def get_database_config():
    """Load database configuration from JSON file.
    
    Returns:
        str or None: Database path if found and valid, None otherwise.
    """
    config_file = Path(__file__).parent / 'database_config.json'
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                db_path = config.get('database_path')
                if db_path and os.path.exists(db_path):
                    return str(Path(db_path).absolute())
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error reading database config: {e}")
    
    return None

def save_database_config(db_path):
    """Save database path to configuration file.
    
    Args:
        db_path (str): Path to database file.
    """
    config_file = Path(__file__).parent / 'database_config.json'
    config = {
        "database_path": str(Path(db_path).absolute())
    }
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

def _show_database_setup_message():
    """Show simple setup message for missing database."""
    print("\n" + "="*60)
    print("WEC-Grid Database Setup Required")
    print("="*60)
    print("No database path is configured.")
    print("\nPreloaded database can be downloaded here:")
    print("https://github.com/acep-uaf/wecgrid-database")
    print("\nOptions to configure database:")
    print('1. Use existing database: engine.database.set_database_path(r"path/to/WEC-GRID.db")')
    print('2. Create new database: engine.database.initialize_database(r"path/to/new_database.db")')
    print("="*60 + "\n")

class WECGridDB:
    """SQLite database interface for WEC-Grid simulation data management.
    
    Provides database operations for storing WEC simulation results, device
    configurations, and time series data. Supports both raw SQL queries and
    pandas DataFrame integration with multi-software backend support.
    
    Database Schema Overview:
    ------------------------
    Metadata Tables:
        - grid_simulations: Grid simulation metadata and parameters
        - wec_simulations: WEC-Sim simulation parameters and wave conditions
        - wec_integrations: Links WEC farms to grid connection points
        
    PSS®E Results Tables:
        - psse_bus_results: Bus voltages, power injections [pu on S_base]
        - psse_generator_results: Generator outputs [pu on S_base] 
        - psse_load_results: Load demands [pu on S_base]
        - psse_line_results: Line loadings [% of thermal rating]
        
    PyPSA Results Tables:
        - pypsa_bus_results: Same schema as PSS®E for cross-platform comparison
        - pypsa_generator_results: Same schema as PSS®E
        - pypsa_load_results: Same schema as PSS®E  
        - pypsa_line_results: Same schema as PSS®E
        
    WEC Simulation Data:
        - wec_simulations: Metadata including wave spectrum, class, and conditions
        - wec_power_results: High-resolution WEC device power output [Watts]
    
    Key Design Features:
        - Software-specific tables enable multi-backend comparisons
        - All grid power values in per-unit on system S_base (MVA)
        - GridState DataFrame schema alignment for direct data mapping
        - Optional storage model - persist only when explicitly requested
        - JSON configuration file for database path management
        - User-guided setup for first-time configuration
        - Support for downloaded or cloned database repositories
    
    Database Location:
        Configured via database_config.json in the same directory as this module.
        Users can point to downloaded database file, cloned repository, or create new empty database.
    
    Attributes:
        db_path (str): Path to SQLite database file (from JSON configuration).
        
    Example:
        >>> db = WECGridDB(engine)  # Uses path from database_config.json
        >>> # First run will prompt user to configure database path
        >>> with db.connection() as conn:
        ...     results = db.query("SELECT * FROM grid_simulations", return_type="df")
    
    Notes:
        Database path is configured via JSON file on first use.
        Users are guided through setup process with clear instructions.
        All database operations are transaction-safe with automatic rollback on errors.
    """
    
    def __init__(self, engine):
        """Initialize database handler.
        
        Args:
            engine: WEC-GRID engine instance
        """
        self.engine = engine
        
        # Get database path from config
        self.db_path = get_database_config()
        if self.db_path is None:
            _show_database_setup_message()
            print("Warning: Database not configured. Use engine.database.set_database_path() to configure.")
            return  # Allow user to continue and set path later
        
        #print(f"Using database: {self.db_path}")
        self.check_and_initialize()
        
    def check_and_initialize(self):
        """Check if database exists and has correct schema, initialize if needed.
        
        Validates that all required tables exist with proper structure.
        Creates database and initializes schema if missing or incomplete.
        
        Returns:
            bool: True if database was already valid, False if initialization was needed.
        """
        if self.db_path is None:
            print("Warning: Database path not set. Cannot initialize database.")
            return False
            
        if not os.path.exists(self.db_path):
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.initialize_database()
            return False
            
        # Check if all required tables exist
        required_tables = [
            'grid_simulations', 'wec_simulations', 'wec_integrations',
            'psse_bus_results', 'psse_generator_results', 'psse_load_results', 'psse_line_results',
            'pypsa_bus_results', 'pypsa_generator_results', 'pypsa_load_results', 'pypsa_line_results',
            'wec_power_results'
        ]
        
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row[0] for row in cursor.fetchall()}
            
            missing_tables = set(required_tables) - existing_tables
            if missing_tables:
                self.initialize_database()
                return False
                
        # Check for missing columns in existing tables and migrate
        self._migrate_schema()
                
        return True

    def _migrate_schema(self):
        """Migrate database schema to add missing columns."""
        with self.connection() as conn:
            cursor = conn.cursor()
            
            # Check if wave_spectrum and wave_class columns exist in wec_simulations
            cursor.execute("PRAGMA table_info(wec_simulations)")
            columns = [row[1] for row in cursor.fetchall()]
            
            migrations_applied = False
            
            if 'wave_spectrum' not in columns:
                cursor.execute("ALTER TABLE wec_simulations ADD COLUMN wave_spectrum TEXT")
                migrations_applied = True
                
            if 'wave_class' not in columns:
                cursor.execute("ALTER TABLE wec_simulations ADD COLUMN wave_class TEXT")
                migrations_applied = True
                
            if migrations_applied:
                conn.commit()

    @contextmanager
    def connection(self):
        """Context manager for safe database connections.
        
        Provides transaction safety with automatic commit on success and
        rollback on exceptions. Connection closed automatically.
            
        """
        if self.db_path is None:
            raise ValueError(
                "Database path not configured. Please use engine.database.set_database_path() to configure."
            )
            
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_database(self, db_path: Optional[str] = None):
        """Initialize database schema with WEC-Grid tables and indexes.
        
        Args:
            db_path (str, optional): Path where database should be created. 
                If provided, creates new database at this location and updates 
                the current instance to use it. If None, uses existing database path.
        
        Creates all required tables according to the finalized WEC-Grid schema:
        - Metadata tables for simulation parameters
        - Software-specific result tables (PSS®E, PyPSA) 
        - WEC time-series data tables
        - Performance indexes for efficient queries
        
        All existing data is preserved if tables already exist.
        
        Example:
            >>> # Create new database when none is configured
            >>> engine.database.initialize_database("/path/to/new_database.db")
            
            >>> # Initialize schema on existing configured database
            >>> engine.database.initialize_database()
        """
        if db_path:
            # Convert to absolute path
            db_path = str(Path(db_path).absolute())
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Update the instance to use this new database path
            save_database_config(db_path)
            self.db_path = db_path
            
            # Create the database file if it doesn't exist
            if not os.path.exists(db_path):
                # Touch the file to create it
                conn = sqlite3.connect(db_path)
                conn.close()

        # Verify we have a database path to work with
        if self.db_path is None:
            raise ValueError(
                "No database path configured. Please provide db_path parameter or "
                "use engine.database.set_database_path() to configure a database path first."
            )

        with self.connection() as conn:
            cursor = conn.cursor()
            
            # ================================================================
            # METADATA TABLES
            # ================================================================
            
            # Grid simulation metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grid_simulations (
                    grid_sim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sim_name TEXT,
                    case_name TEXT NOT NULL,
                    psse BOOLEAN DEFAULT FALSE,
                    pypsa BOOLEAN DEFAULT FALSE,
                    sbase_mva REAL NOT NULL,
                    sim_start_time TEXT NOT NULL,
                    sim_end_time TEXT,
                    delta_time INTEGER,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # WEC simulation parameters
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
                    FOREIGN KEY (grid_sim_id) REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE,
                    FOREIGN KEY (wec_sim_id) REFERENCES wec_simulations(wec_sim_id) ON DELETE CASCADE
                )
            """)
            
            # ================================================================
            # PSS®E-SPECIFIC TABLES (GridState Schema Alignment)
            # ================================================================
            
            # PSS®E Bus Results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS psse_bus_results (
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
                    FOREIGN KEY (grid_sim_id) REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
            
            # PSS®E Generator Results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS psse_generator_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    gen INTEGER NOT NULL,
                    gen_name TEXT,
                    bus INTEGER NOT NULL,
                    p REAL,
                    q REAL,
                    mbase REAL,
                    status INTEGER,
                    PRIMARY KEY (grid_sim_id, timestamp, gen),
                    FOREIGN KEY (grid_sim_id) REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
            
            # PSS®E Load Results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS psse_load_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    load INTEGER NOT NULL,
                    load_name TEXT,
                    bus INTEGER NOT NULL,
                    p REAL,
                    q REAL,
                    status INTEGER,
                    PRIMARY KEY (grid_sim_id, timestamp, load),
                    FOREIGN KEY (grid_sim_id) REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
            
            # PSS®E Line Results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS psse_line_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    line INTEGER NOT NULL,
                    line_name TEXT,
                    ibus INTEGER NOT NULL,
                    jbus INTEGER NOT NULL,
                    line_pct REAL,
                    status INTEGER,
                    PRIMARY KEY (grid_sim_id, timestamp, line),
                    FOREIGN KEY (grid_sim_id) REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
            
            # ================================================================
            # PyPSA-SPECIFIC TABLES (Identical to PSS®E for Cross-Platform Comparison)
            # ================================================================
            
            # PyPSA Bus Results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pypsa_bus_results (
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
                    FOREIGN KEY (grid_sim_id) REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
            
            # PyPSA Generator Results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pypsa_generator_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    gen INTEGER NOT NULL,
                    gen_name TEXT,
                    bus INTEGER NOT NULL,
                    p REAL,
                    q REAL,
                    mbase REAL,
                    status INTEGER,
                    PRIMARY KEY (grid_sim_id, timestamp, gen),
                    FOREIGN KEY (grid_sim_id) REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
            
            # PyPSA Load Results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pypsa_load_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    load INTEGER NOT NULL,
                    load_name TEXT,
                    bus INTEGER NOT NULL,
                    p REAL,
                    q REAL,
                    status INTEGER,
                    PRIMARY KEY (grid_sim_id, timestamp, load),
                    FOREIGN KEY (grid_sim_id) REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
            
            # PyPSA Line Results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pypsa_line_results (
                    grid_sim_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    line INTEGER NOT NULL,
                    line_name TEXT,
                    ibus INTEGER NOT NULL,
                    jbus INTEGER NOT NULL,
                    line_pct REAL,
                    status INTEGER,
                    PRIMARY KEY (grid_sim_id, timestamp, line),
                    FOREIGN KEY (grid_sim_id) REFERENCES grid_simulations(grid_sim_id) ON DELETE CASCADE
                )
            """)
            
            # ================================================================
            # WEC TIME-SERIES DATA
            # ================================================================
            
            # WEC Power Results (High-Resolution Time Series)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wec_power_results (
                    wec_sim_id INTEGER NOT NULL,
                    time_sec REAL NOT NULL,
                    device_index INTEGER NOT NULL,
                    p_w REAL,
                    q_var REAL,
                    wave_elevation_m REAL,
                    PRIMARY KEY (wec_sim_id, time_sec, device_index),
                    FOREIGN KEY (wec_sim_id) REFERENCES wec_simulations(wec_sim_id) ON DELETE CASCADE
                )
            """)
            
            # ================================================================
            # PERFORMANCE INDEXES
            # ================================================================
            
            # Grid simulation indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_grid_sim_time ON grid_simulations(sim_start_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_grid_sim_case ON grid_simulations(case_name)")
            
            # PSS®E result indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_psse_bus_time ON psse_bus_results(grid_sim_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_psse_gen_time ON psse_generator_results(grid_sim_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_psse_load_time ON psse_load_results(grid_sim_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_psse_line_time ON psse_line_results(grid_sim_id, timestamp)")
            
            # PyPSA result indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pypsa_bus_time ON pypsa_bus_results(grid_sim_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pypsa_gen_time ON pypsa_generator_results(grid_sim_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pypsa_load_time ON pypsa_load_results(grid_sim_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pypsa_line_time ON pypsa_line_results(grid_sim_id, timestamp)")
            
            # WEC time-series indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wec_power_time ON wec_power_results(wec_sim_id, time_sec)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wec_integration ON wec_integrations(grid_sim_id, wec_sim_id)")
            
    def clean_database(self):
        """Delete the current database and reinitialize with fresh schema.
        
        WARNING: This will permanently delete all stored simulation data.
        Use with caution - all existing data will be lost.
        
        Returns:
            bool: True if database was successfully cleaned and reinitialized.
        
        Notes: 
            Wasn't working if my Jupyter Kernal was still going, need to restart then call
        Example:
            >>> engine.database.clean_database()
            WARNING: This will delete all data in the database!
            Database cleaned and reinitialized successfully.
        """
        print("WARNING: This will delete all data in the database!")
        
        # Close any existing connections by creating a temporary one and closing it
        try:
            conn = sqlite3.connect(self.db_path)
            conn.close()
        except:
            pass
        
        # Delete the database file if it exists
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError as e:
                print(f"Error deleting database file: {e}")
                return False
        
        # Reinitialize with fresh schema
        try:
            self.initialize_database()
            return True
        except Exception as e:
            print(f"Error reinitializing database: {e}")
            return False

    def query(self, sql: str, params: tuple = None, return_type: str = "raw"):
        """Execute SQL query with flexible result formatting.
        
        Args:
            sql (str): SQL query string.
            params (tuple, optional): Query parameters for safe substitution.
            return_type (str): Format for results - 'raw', 'df', or 'dict'.
            
        Returns:
            Results in specified format:
            - 'raw': List of tuples (default SQLite format)
            - 'df': pandas DataFrame with column names
            - 'dict': List of dictionaries with column names as keys
            
        Example:
            >>> db.query("SELECT * FROM grid_simulations WHERE case_name = ?", 
            ...           params=("IEEE_14_bus",), return_type="df")
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params or ())
            result = cursor.fetchall()

            if return_type == "df":
                columns = [desc[0] for desc in cursor.description]
                return pd.DataFrame(result, columns=columns)
            elif return_type == "dict":
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in result]
            elif return_type == "raw":
                return result
            else:
                raise ValueError(f"Invalid return_type '{return_type}'. Must be 'raw', 'df', or 'dict'.")
                
    def save_sim(self, sim_name: str, notes: str = None) -> int:
        """Save simulation data for all available software backends in the engine.
        
        Automatically detects and stores data from all active software backends
        (PSS®E, PyPSA) and WEC farms present in the engine object.
        
        Always creates a new simulation entry - no duplicate checking.
        Users can manage simulation names as needed.
        
        Args:
            sim_name (str): User-friendly simulation name.
            notes (str, optional): Simulation notes.
            
        Returns:
            int: grid_sim_id of the created simulation.
            
        Example:
            >>> sim_id = engine.database.save_sim(
            ...     sim_name="IEEE 30 test",
            ...     notes="testing the database"
            ... )
        """
        # Gather all available software objects from engine
        softwares = []
        
        # Check for PSS®E
        if hasattr(self.engine, 'psse') and hasattr(self.engine.psse, 'grid'):
            softwares.append(self.engine.psse.grid)
        
        # Check for PyPSA  
        if hasattr(self.engine, 'pypsa') and hasattr(self.engine.pypsa, 'grid'):
            softwares.append(self.engine.pypsa.grid)
        
        if not softwares:
            raise ValueError("No software backends found in engine. Ensure PSS®E or PyPSA models are loaded.")
        
        # Get case name from engine
        case_name = getattr(self.engine, 'case_name', 'Unknown_Case')
        
        # Get time manager from engine
        timeManager = getattr(self.engine, 'time', None)
        if timeManager is None:
            raise ValueError("No time manager found in engine. Ensure engine.time is properly initialized.")
        
        # Extract software flags and determine sbase
        psse_used = False
        pypsa_used = False
        sbase_mva = None
        
        for i, software_obj in enumerate(softwares):
            software_name = getattr(software_obj, 'software', '')
            
            software_name = software_name.lower() if software_name else ''
            
            if software_name == "psse":
                psse_used = True
            elif software_name == "pypsa":
                pypsa_used = True
            else:
                continue  # Skip this software object instead of processing it
            
            # Get sbase from the first software object
            if sbase_mva is None:
                if hasattr(software_obj, 'sbase'):
                    sbase_mva = software_obj.sbase
                else:
                    # Try to get from parent object  
                    parent = getattr(software_obj, '_parent', None)
                    if parent and hasattr(parent, 'sbase'):
                        sbase_mva = parent.sbase
                    else:
                        sbase_mva = 100.0  # Default fallback
        
        # Get time information from simulation 
        sim_start_time = timeManager.start_time.isoformat()
        sim_end_time = getattr(timeManager, 'sim_stop', None)
        if sim_end_time:
            sim_end_time = sim_end_time.isoformat()
        delta_time = timeManager.delta_time
        
        # Create new grid simulation record (always create new entry)
        with self.connection() as conn:
            cursor = conn.cursor()
            
            # Insert new simulation - always create new entry
            cursor.execute("""
                INSERT INTO grid_simulations 
                (sim_name, case_name, psse, pypsa, sbase_mva, sim_start_time, 
                 sim_end_time, delta_time, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sim_name, case_name, psse_used, pypsa_used, sbase_mva, sim_start_time,
                  sim_end_time, delta_time, notes))
            
            grid_sim_id = cursor.lastrowid
        
        # Store data for each valid software
        valid_softwares = []
        for software_obj in softwares:
            software_name = getattr(software_obj, 'software', '').lower()
            
            # Only process valid software names
            if software_name in ['psse', 'pypsa']:
                valid_softwares.append((software_obj, software_name))
        
        for software_obj, software_name in valid_softwares:
            # Store all time-series data from GridState
            self._store_all_gridstate_timeseries(grid_sim_id, software_obj, software_name, timeManager)
        
        # Store WEC farm data if available
        if hasattr(self.engine, 'wec_farms') and self.engine.wec_farms:
            self._store_wec_farm_data(grid_sim_id)
        
        # Create summary of used software
        used_software = []
        if psse_used:
            used_software.append("PSS®E")
        if pypsa_used:
            used_software.append("PyPSA")
        
        print(f"Simulation saved: ID {grid_sim_id} - {sim_name}")
        
        return grid_sim_id
        
    def _store_all_gridstate_timeseries(self, grid_sim_id: int, grid_state_obj, software: str, timeManager):
        """Store all time-series data from GridState object.
        
        Args:
            grid_sim_id (int): Grid simulation ID.
            grid_state_obj: GridState object with time-series data.
            software (str): Software name ("psse" or "pypsa").
            timeManager: WECGridTime object.
        """
        # Validate software name
        if software not in ['psse', 'pypsa']:
            raise ValueError(f"Invalid software name: '{software}'. Must be 'psse' or 'pypsa'.")
            
        table_prefix = f"{software}_"
        snapshots = timeManager.snapshots
        
        with self.connection() as conn:
            cursor = conn.cursor()
            
            # Store bus time-series data
            if hasattr(grid_state_obj, 'bus_t') and grid_state_obj.bus_t:
                for timestamp in snapshots:
                    timestamp_str = timestamp.isoformat()
                    
                    # Create bus data for this timestamp
                    if hasattr(grid_state_obj, 'bus') and not grid_state_obj.bus.empty:
                        for idx, row in grid_state_obj.bus.iterrows():
                            cursor.execute(f"""
                                INSERT OR REPLACE INTO {table_prefix}bus_results 
                                (grid_sim_id, timestamp, bus, bus_name, type, p, q, v_mag, angle_deg, vbase)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (grid_sim_id, timestamp_str, row.get("bus"), row.get('bus_name'), row.get('type'),
                                  self._get_timeseries_value(grid_state_obj.bus_t, 'p', row.get("bus"), timestamp),
                                  self._get_timeseries_value(grid_state_obj.bus_t, 'q', row.get("bus"), timestamp),
                                  self._get_timeseries_value(grid_state_obj.bus_t, 'v_mag', row.get("bus"), timestamp),
                                  self._get_timeseries_value(grid_state_obj.bus_t, 'angle_deg', row.get("bus"), timestamp),
                                  row.get('vbase')))
            
            # Store generator time-series data
            if hasattr(grid_state_obj, 'gen_t') and grid_state_obj.gen_t:
                for timestamp in snapshots:
                    timestamp_str = timestamp.isoformat()
                    
                    if hasattr(grid_state_obj, 'gen') and not grid_state_obj.gen.empty:
                        for idx, row in grid_state_obj.gen.iterrows():
                            cursor.execute(f"""
                                INSERT OR REPLACE INTO {table_prefix}generator_results 
                                (grid_sim_id, timestamp, gen, gen_name, bus, p, q, mbase, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (grid_sim_id, timestamp_str, row.get('gen'), row.get('gen_name'), row.get('bus'),
                                  self._get_timeseries_value(grid_state_obj.gen_t, 'p', row.get('gen'), timestamp),
                                  self._get_timeseries_value(grid_state_obj.gen_t, 'q', row.get('gen'), timestamp),
                                  row.get('Mbase'),
                                  self._get_timeseries_value(grid_state_obj.gen_t, 'status', row.get('gen'), timestamp)))
            
            # Store load time-series data
            if hasattr(grid_state_obj, 'load_t') and grid_state_obj.load_t:
                for timestamp in snapshots:
                    timestamp_str = timestamp.isoformat()
                    
                    if hasattr(grid_state_obj, 'load') and not grid_state_obj.load.empty:
                        for idx, row in grid_state_obj.load.iterrows():
                            cursor.execute(f"""
                                INSERT OR REPLACE INTO {table_prefix}load_results 
                                (grid_sim_id, timestamp, load, load_name, bus, p, q, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (grid_sim_id, timestamp_str, row.get('load'), row.get('load_name'), row.get('bus'),
                                  self._get_timeseries_value(grid_state_obj.load_t, 'p', row.get('load'), timestamp),
                                  self._get_timeseries_value(grid_state_obj.load_t, 'q', row.get('load'), timestamp),
                                  self._get_timeseries_value(grid_state_obj.load_t, 'status', row.get('load'), timestamp)))
            
            # Store line time-series data
            if hasattr(grid_state_obj, 'line_t') and grid_state_obj.line_t:
                for timestamp in snapshots:
                    timestamp_str = timestamp.isoformat()
                    
                    if hasattr(grid_state_obj, 'line') and not grid_state_obj.line.empty:
                        for idx, row in grid_state_obj.line.iterrows():
                            cursor.execute(f"""
                                INSERT OR REPLACE INTO {table_prefix}line_results 
                                (grid_sim_id, timestamp, line, line_name, ibus, jbus, line_pct, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (grid_sim_id, timestamp_str, row.get('line'), row.get('line_name'), row.get('ibus'),
                                  row.get('jbus'),
                                  self._get_timeseries_value(grid_state_obj.line_t, 'line_pct', row.get('line'), timestamp),
                                  self._get_timeseries_value(grid_state_obj.line_t, 'status', row.get('line'), timestamp)))
                                  
    def _store_wec_farm_data(self, grid_sim_id: int):
        """Store WEC farm data if available in the engine.
        
        Args:
            grid_sim_id (int): Grid simulation ID to link WEC data to.
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            
            for farm in self.engine.wec_farms:
                # Store wec_integrations record linking farm to grid simulation
                cursor.execute("""
                    INSERT OR REPLACE INTO wec_integrations 
                    (grid_sim_id, wec_sim_id, farm_name, bus_location, num_devices)
                    VALUES (?, ?, ?, ?, ?)
                """, (grid_sim_id, farm.wec_sim_id, farm.farm_name, farm.bus_location, farm.size))
                                  
    def _get_timeseries_value(self, timeseries_dict, parameter: str, component_id: int, timestamp):
        """Extract time-series value for specific component and timestamp.
        
        Args:
            timeseries_dict: AttrDict containing time-series DataFrames.
            parameter (str): Parameter name (e.g., 'p', 'q', 'v_mag').
            component_id (int): Component ID.
            timestamp: Timestamp to extract.
            
        Returns:
            Value at the specified timestamp or None if not available.
        """
        try:
            if parameter in timeseries_dict:
                df = timeseries_dict[parameter]
                
                # GridState stores time-series with component names as columns, not IDs
                # Try both component_id directly and component name patterns
                possible_columns = [
                    component_id,  # Try direct ID first (fallback case)
                    str(component_id),  # String version of ID
                    f"Bus_{component_id}",  # Bus name pattern
                    f"Gen_{component_id}",  # Generator name pattern  
                    f"Line_{component_id}",  # Line name pattern
                    f"Load_{component_id}"  # Load name pattern
                ]
                
                for col in possible_columns:
                    if col in df.columns and timestamp in df.index:
                        value = df.loc[timestamp, col]
                        # Debug: Print if value is None/NaN for slack bus
                        # if component_id == 1 and parameter in ['p', 'q', 'v_mag', 'angle_deg'] and (pd.isna(value) or value is None):
                        #     print(f"DEBUG: Slack bus {component_id} {parameter} = {value} (column: {col})")
                        #     print(f"Available columns: {list(df.columns)}")
                        #     print(f"Available timestamps: {list(df.index)}")
                        return value
                        
        except (KeyError, AttributeError) as e:
            # Debug: Print error for slack bus
            if component_id == 1:
                print(f"DEBUG: Error getting slack bus {component_id} {parameter}: {e}")
            pass
        return None
            
    def store_gridstate_data(self, grid_sim_id: int, timestamp: str, grid_state, software: str):
        """Store GridState data to appropriate software-specific tables.
        
        Args:
            grid_sim_id (int): Grid simulation ID.
            timestamp (str): ISO datetime string for this snapshot.
            grid_state: GridState object with bus, gen, load, line DataFrames.
            software (str): Software backend - "PSSE" or "PyPSA".
            
        Example:
            >>> db.store_gridstate_data(
            ...     grid_sim_id=123,
            ...     timestamp="2025-08-14T10:05:00", 
            ...     grid_state=my_grid_state,
            ...     software="PSSE"
            ... )
        """
        software = software.lower()
        table_prefix = f"{software}_"
        
        with self.connection() as conn:
            cursor = conn.cursor()
            
            # Store bus results
            if not grid_state.bus.empty:
                for bus_id, row in grid_state.bus.iterrows():
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO {table_prefix}bus_results 
                        (grid_sim_id, timestamp, bus, bus_name, type, p, q, v_mag, angle_deg, vbase)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (grid_sim_id, timestamp, bus_id, row.get('bus_name'), row.get('type'),
                          row.get('p'), row.get('q'), row.get('v_mag'), row.get('angle_deg'), row.get('vbase')))
            
            # Store generator results
            if not grid_state.gen.empty:
                for gen_id, row in grid_state.gen.iterrows():
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO {table_prefix}generator_results 
                        (grid_sim_id, timestamp, gen, gen_name, bus, p, q, mbase, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (grid_sim_id, timestamp, gen_id, row.get('gen_name'), row.get('bus'),
                          row.get('p'), row.get('q'), row.get('Mbase'), row.get('status')))
            
            # Store load results
            if not grid_state.load.empty:
                for load_id, row in grid_state.load.iterrows():
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO {table_prefix}load_results 
                        (grid_sim_id, timestamp, load, load_name, bus, p, q, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (grid_sim_id, timestamp, load_id, row.get('load_name'), row.get('bus'),
                          row.get('p'), row.get('q'), row.get('status')))
            
            # Store line results
            if not grid_state.line.empty:
                for line_id, row in grid_state.line.iterrows():
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO {table_prefix}line_results 
                        (grid_sim_id, timestamp, line, line_name, ibus, jbus, line_pct, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (grid_sim_id, timestamp, line_id, row.get('line_name'), row.get('ibus'),
                          row.get('jbus'), row.get('line_pct'), row.get('status')))
                          
    def get_simulation_info(self, grid_sim_id: int = None) -> pd.DataFrame:
        """Get grid simulation information.
        
        Args:
            grid_sim_id (int, optional): Specific simulation ID. If None, returns all.
            
        Returns:
            pd.DataFrame: Simulation metadata.
        """
        if grid_sim_id:
            return self.query(
                "SELECT * FROM grid_simulations WHERE grid_sim_id = ?",
                params=(grid_sim_id,), return_type="df"
            )
        else:
            return self.query("SELECT * FROM grid_simulations ORDER BY created_at DESC", return_type="df")
            
    def grid_sims(self) -> pd.DataFrame:
        """Get all grid simulation metadata in a user-friendly format.
        
        Returns:
            pd.DataFrame: Grid simulations with key metadata columns.
            
        Example:
            >>> engine.database.grid_sims()
               grid_sim_id     sim_name      case_name  psse  pypsa  sbase_mva  ...
            0           1     Test Run   IEEE_14_bus  True  False      100.0  ...
        """
        return self.query("""
            SELECT grid_sim_id, sim_name, case_name, psse, pypsa, sbase_mva,
                   sim_start_time, sim_end_time, delta_time, notes, created_at
            FROM grid_simulations 
            ORDER BY created_at DESC
        """, return_type="df")
        
    def wecsim_runs(self) -> pd.DataFrame:
        """Get all WEC simulation metadata with enhanced wave parameters.
        
        Returns:
            pd.DataFrame: WEC simulations with parameters and wave conditions including
                wave spectrum type, wave class, and all simulation parameters.
            
        Example:
            >>> engine.database.wecsim_runs()
               wec_sim_id model_type  sim_duration_sec  delta_time  wave_spectrum  wave_class  ...
            0          1       RM3             600.0        0.1             PM   irregular  ...
        """
        return self.query("""
            SELECT wec_sim_id, model_type, sim_duration_sec, delta_time,
                   wave_height_m, wave_period_sec, wave_spectrum, wave_class, wave_seed,
                   simulation_hash, created_at
            FROM wec_simulations 
            ORDER BY created_at DESC
        """, return_type="df")
    
    def pull_sim(self, grid_sim_id: int, software: str = None):
        """Pull simulation data from database and reconstruct GridState object.
        
        Retrieves all time-series data for a specific simulation and recreates
        the GridState object with both snapshot data and time-series history.
        
        Args:
            grid_sim_id (int): Grid simulation ID to retrieve.
            software (str, optional): Software backend to pull data for ("psse" or "pypsa").
                If None, automatically detects which software was used based on 
                grid_simulations table flags.
                
        Returns:
            GridState: Reconstructed GridState object with time-series data.
            
        Raises:
            ValueError: If grid_sim_id not found or software not available for this simulation.
            
        Example:
            >>> # Pull PSS®E simulation data
            >>> grid_state = engine.database.pull_sim(grid_sim_id=123, software="psse")
            >>> print(f"Buses: {len(grid_state.bus)}")
            >>> print(f"Time series data: {list(grid_state.bus_t.keys())}")
            
            >>> # Auto-detect software and pull data
            >>> grid_state = engine.database.pull_sim(grid_sim_id=123)
        """
        # Import here to avoid circular import
        from ..modelers.power_system.base import GridState, AttrDict
        # Get simulation metadata
        sim_info = self.query(
            "SELECT * FROM grid_simulations WHERE grid_sim_id = ?",
            params=(grid_sim_id,), return_type="df"
        )
        
        if sim_info.empty:
            raise ValueError(f"Simulation with ID {grid_sim_id} not found in database")
        
        sim_row = sim_info.iloc[0]
        
        # Auto-detect software if not specified
        if software is None:
            if sim_row['psse']:
                software = 'psse'
            elif sim_row['pypsa']:
                software = 'pypsa'
            else:
                raise ValueError(f"No software backend data found for simulation {grid_sim_id}")
        
        # Validate software choice
        if software not in ['psse', 'pypsa']:
            raise ValueError(f"Invalid software: '{software}'. Must be 'psse' or 'pypsa'.")
            
        if software == 'psse' and not sim_row['psse']:
            raise ValueError(f"PSS®E data not available for simulation {grid_sim_id}")
        if software == 'pypsa' and not sim_row['pypsa']:
            raise ValueError(f"PyPSA data not available for simulation {grid_sim_id}")
        
        # Create GridState object
        grid_state = GridState(software=software)
        
        # Set case name from database metadata
        grid_state.case = sim_row['case_name']
        
        # Table prefix for this software
        table_prefix = f"{software}_"
        table_prefix = f"{software}_"
        
        # Pull bus data
        bus_data = self.query(f"""
            SELECT * FROM {table_prefix}bus_results 
            WHERE grid_sim_id = ? 
            ORDER BY timestamp, bus
        """, params=(grid_sim_id,), return_type="df")
        
        # Pull generator data
        gen_data = self.query(f"""
            SELECT * FROM {table_prefix}generator_results 
            WHERE grid_sim_id = ? 
            ORDER BY timestamp, gen
        """, params=(grid_sim_id,), return_type="df")
        
        # Pull load data
        load_data = self.query(f"""
            SELECT * FROM {table_prefix}load_results 
            WHERE grid_sim_id = ? 
            ORDER BY timestamp, load
        """, params=(grid_sim_id,), return_type="df")
        
        # Pull line data
        line_data = self.query(f"""
            SELECT * FROM {table_prefix}line_results 
            WHERE grid_sim_id = ? 
            ORDER BY timestamp, line
        """, params=(grid_sim_id,), return_type="df")
        
        # Convert timestamp strings to pandas timestamps
        if not bus_data.empty:
            bus_data['timestamp'] = pd.to_datetime(bus_data['timestamp'])
        if not gen_data.empty:
            gen_data['timestamp'] = pd.to_datetime(gen_data['timestamp'])
        if not load_data.empty:
            load_data['timestamp'] = pd.to_datetime(load_data['timestamp'])
        if not line_data.empty:
            line_data['timestamp'] = pd.to_datetime(line_data['timestamp'])
        
        # Reconstruct current snapshot data (use latest timestamp)
        if not bus_data.empty:
            latest_time = bus_data['timestamp'].max()
            latest_bus = bus_data[bus_data['timestamp'] == latest_time].copy()
            latest_bus.drop(columns=['grid_sim_id', 'timestamp'], inplace=True)
            latest_bus.reset_index(drop=True, inplace=True)
            # Ensure clean column headers
            latest_bus.columns.name = None
            latest_bus.index.name = None
            latest_bus.attrs['df_type'] = 'BUS'
            grid_state.bus = latest_bus
            
        if not gen_data.empty:
            latest_time = gen_data['timestamp'].max()
            latest_gen = gen_data[gen_data['timestamp'] == latest_time].copy()
            latest_gen.drop(columns=['grid_sim_id', 'timestamp'], inplace=True)
            latest_gen.reset_index(drop=True, inplace=True)
            # Ensure clean column headers
            latest_gen.columns.name = None
            latest_gen.index.name = None
            latest_gen.attrs['df_type'] = 'GEN'
            grid_state.gen = latest_gen
            
        if not load_data.empty:
            latest_time = load_data['timestamp'].max()
            latest_load = load_data[load_data['timestamp'] == latest_time].copy()
            latest_load.drop(columns=['grid_sim_id', 'timestamp'], inplace=True)
            latest_load.reset_index(drop=True, inplace=True)
            # Ensure clean column headers
            latest_load.columns.name = None
            latest_load.index.name = None
            latest_load.attrs['df_type'] = 'LOAD'
            grid_state.load = latest_load
            
        if not line_data.empty:
            latest_time = line_data['timestamp'].max()
            latest_line = line_data[line_data['timestamp'] == latest_time].copy()
            latest_line.drop(columns=['grid_sim_id', 'timestamp'], inplace=True)
            latest_line.reset_index(drop=True, inplace=True)
            # Ensure clean column headers
            latest_line.columns.name = None
            latest_line.index.name = None
            latest_line.attrs['df_type'] = 'LINE'
            grid_state.line = latest_line
        
        # Reconstruct time-series data
        def _reconstruct_timeseries(data_df, id_col, component_type):
            """Helper function to reconstruct time-series data for a component type."""
            if data_df.empty:
                return AttrDict()
                
            ts_data = AttrDict()
            
            # Get all variable columns (exclude metadata columns)
            exclude_cols = {'grid_sim_id', 'timestamp', id_col, f'{component_type}_name'}
            if component_type == 'bus':
                exclude_cols.update({'bus_name', 'vbase'})  # Updated to include bus_name
            elif component_type == 'gen':
                exclude_cols.update({'gen_name', 'mbase'})  # Updated to include gen_name
            elif component_type == 'line':
                exclude_cols.update({'line_name', 'ibus', 'jbus'})  # Updated to include line_name
            elif component_type == 'load':
                exclude_cols.add('load_name')  # Added load_name
            
            var_cols = [col for col in data_df.columns if col not in exclude_cols]
            
            # For each variable, create a time-series DataFrame
            for var in var_cols:
                if f'{component_type}_name' not in data_df.columns:
                    # Fallback: use component IDs as column names
                    pivot_data = data_df.pivot(
                        index='timestamp', 
                        columns=id_col, 
                        values=var
                    )
                else:
                    # Pivot data to have timestamps as rows and component names as columns
                    pivot_data = data_df.pivot(
                        index='timestamp', 
                        columns=f'{component_type}_name', 
                        values=var
                    )
                
                # Clean up column headers
                pivot_data.columns.name = None
                pivot_data.index.name = None
                ts_data[var] = pivot_data
                
            return ts_data
        
        # Reconstruct time-series for each component type
        grid_state.bus_t = _reconstruct_timeseries(bus_data, 'bus', 'bus')
        grid_state.gen_t = _reconstruct_timeseries(gen_data, 'gen', 'gen')
        grid_state.load_t = _reconstruct_timeseries(load_data, 'load', 'load')
        grid_state.line_t = _reconstruct_timeseries(line_data, 'line', 'line')
        
        print(f"GridState reconstructed: {sim_row['case_name']} ({software.upper()}) - "
              f"{len(grid_state.bus)} buses, {len(grid_state.gen)} generators")
        
        return grid_state
    
    def set_database_path(self, db_path):
        """Set database path and reinitialize connection.
        
        Args:
            db_path (str): Path to WEC-GRID database file.
            
        Example:
            >>> engine.database.set_database_path("/path/to/wecgrid-database/WEC-GRID.db")
        """
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found: {db_path}")
        
        # Save to config
        save_database_config(db_path)
        
        # Update current instance
        self.db_path = str(Path(db_path).absolute())
        
        # Reinitialize
        self.check_and_initialize()
        
        return self.db_path