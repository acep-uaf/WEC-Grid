"""
WEC-Sim interface for Marine-Grid.

File: src/marinegrid/modeler/wecsim/wecsim.py

Provides the interface between Marine-Grid and WEC-Sim for high-fidelity
wave energy converter simulations using MATLAB engine integration.
"""

# Standard library
import io
import json
import logging
import os
import random
from pathlib import Path
from typing import Any, TYPE_CHECKING

# Third-party
import pandas as pd

# Local
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ...util.time import Time
    from ...tool.database import Database


def _user_config_dir() -> Path:
    """Return a user-writable config directory for Marine-Grid.

    Uses ``platformdirs`` if available, otherwise falls back to ``~/.marinegrid``.
    """
    try:
        from platformdirs import user_config_dir

        return Path(user_config_dir(appname="marinegrid", appauthor=False))
    except ImportError:
        return Path.home() / ".marinegrid"


def _wecsim_config_file() -> Path:
    """Return path to WEC-Sim configuration file."""
    return _user_config_dir() / "wecsim_config.json"


class WECSimModeler:
    """
    Interface for running WEC-Sim device-level simulations via MATLAB engine.

    Manages MATLAB engine lifecycle, executes WEC-Sim models from their native
    directories, and stores results in the Marine-Grid database. Provides
    methods for configuring simulation parameters and retrieving results.

    Attributes:
        wec_sim_path: Path to WEC-Sim MATLAB installation.
        database: Database interface for simulation data storage.
        matlab_engine: Active MATLAB engine instance (None until started).
        time: Reference to the central Time object for coordination.

    Example:
        >>> wecsim = WECSimModeler(database=study.database)
        >>> wecsim.set_wec_sim_path("/path/to/WEC-Sim")
        >>> wec_sim_id = wecsim.simulate(
        ...     model_path="/path/to/RM3",
        ...     sim_length=86400,
        ...     wave_height=2.5,
        ...     wave_period=8.0,
        ... )
    """

    def __init__(self, database: "Database | None" = None):
        """
        Initialize WEC-Sim interface.

        Args:
            database: Database interface for storing simulation results.
                If None, must be set before running simulations.

        Note:
            Automatically loads configuration from environment variable
            ``MARINEGRID_WECSIM_PATH`` or ``~/.marinegrid/wecsim_config.json``.
        """
        self.wec_sim_path: str | None = None
        self.database: "Database | None" = database
        self.matlab_engine: Any = None
        self._time: "Time | None" = None
        self._stdout: io.StringIO | None = None
        self._stderr: io.StringIO | None = None

        # Load configuration on init
        self._load_config()

    def __repr__(self) -> str:
        """Return a compact summary of WEC-Sim interface state."""
        engine_status = "Running" if self.matlab_engine else "Stopped"
        path_status = self.wec_sim_path or "Not configured"
        return (
            f"WECSimModeler:\n"
            f"├─ WEC-Sim Path: {path_status}\n"
            f"├─ MATLAB Engine: {engine_status}\n"
            f"└─ Database: {'Connected' if self.database else 'Not set'}"
        )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def time(self) -> "Time | None":
        """Get the central Time object for simulation timeline."""
        return self._time

    def set_time(self, time: "Time") -> None:
        """
        Set the central Time object for simulation timeline.

        Args:
            time: Time object to use as the simulation timeline.
        """
        self._time = time

    @property
    def is_running(self) -> bool:
        """Check if MATLAB engine is currently running."""
        return self.matlab_engine is not None

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def _load_config(self) -> None:
        """Load WEC-Sim configuration from env var or JSON file."""
        # Priority 1: Environment variable
        env_path = os.getenv("MARINEGRID_WECSIM_PATH")
        if env_path:
            self.wec_sim_path = env_path
            return

        # Priority 2: Config file
        config_file = _wecsim_config_file()
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                    self.wec_sim_path = config.get("wec_sim_path")
            except (json.JSONDecodeError, KeyError, OSError):
                pass

    def _save_config(self) -> None:
        """Save WEC-Sim configuration to user JSON file."""
        try:
            config_file = _wecsim_config_file()
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config = {"wec_sim_path": self.wec_sim_path}
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
        except OSError as e:
            logger.warning("Could not save WEC-Sim config: %s", e)

    def set_wec_sim_path(self, path: str) -> str:
        """
        Configure the WEC-Sim MATLAB framework installation path.

        Args:
            path: Filesystem path to the WEC-Sim MATLAB installation.

        Returns:
            Absolute path that was set.

        Raises:
            FileNotFoundError: If the supplied path does not exist.
        """
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"WEC-Sim path does not exist: {resolved}")

        self.wec_sim_path = str(resolved)
        self._save_config()
        return self.wec_sim_path

    def get_wec_sim_path(self) -> str | None:
        """
        Get the currently configured WEC-Sim path.

        Returns:
            Path to WEC-Sim installation or None if not configured.
        """
        return self.wec_sim_path

    def show_config(self) -> None:
        """Display current WEC-Sim configuration."""
        config_file = _wecsim_config_file()
        logger.info("WEC-Sim Configuration:")
        logger.info("  Path: %s", self.wec_sim_path or "Not configured")
        logger.info("  Config file: %s", config_file)
        logger.info("  Config exists: %s", config_file.exists())
        logger.info("  Env var: MARINEGRID_WECSIM_PATH (overrides config if set)")
        logger.info("  MATLAB Engine: %s", "Running" if self.is_running else "Stopped")

    # -------------------------------------------------------------------------
    # MATLAB Engine Management
    # -------------------------------------------------------------------------

    def start_matlab(self) -> bool:
        """
        Initialize MATLAB engine and configure WEC-Sim framework paths.

        Starts the MATLAB engine if not already running and adds the WEC-Sim
        installation path to MATLAB's search path.

        Returns:
            True if engine was started successfully, False otherwise.

        Raises:
            ValueError: If WEC-Sim path is not configured.
            FileNotFoundError: If WEC-Sim path does not exist.
        """
        # Reload config in case it changed
        self._load_config()

        # Check for MATLAB Python API
        try:
            import matlab.engine
        except ImportError:
            logger.error(
                "MATLAB Python API not installed. See: "
                "https://www.mathworks.com/help/matlab/matlab_external/"
                "install-the-matlab-engine-for-python.html"
            )
            return False

        # Engine already running
        if self.matlab_engine is not None:
            logger.info("MATLAB engine is already running.")
            return True

        # Validate WEC-Sim path
        if self.wec_sim_path is None:
            logger.error(
                "WEC-Sim path not configured. "
                "Use set_wec_sim_path() or set MARINEGRID_WECSIM_PATH env var."
            )
            return False

        if not os.path.exists(self.wec_sim_path):
            raise FileNotFoundError(
                f"WEC-Sim path does not exist: {self.wec_sim_path}"
            )

        # Start engine
        logger.info("Starting MATLAB engine...")
        self.matlab_engine = matlab.engine.start_matlab()
        logger.info("MATLAB engine started.")

        # Add WEC-Sim to MATLAB path
        logger.info("Adding WEC-Sim to MATLAB path...")
        matlab_path = self.matlab_engine.genpath(self.wec_sim_path, nargout=1)
        self.matlab_engine.addpath(matlab_path, nargout=0)
        logger.info("WEC-Sim added to MATLAB path.")

        # Initialize output capture
        self._stdout = io.StringIO()
        self._stderr = io.StringIO()

        return True

    def stop_matlab(self) -> bool:
        """
        Shutdown the MATLAB engine and free system resources.

        Returns:
            True if engine was stopped, False if no engine was running.
        """
        if self.matlab_engine is not None:
            self.matlab_engine.quit()
            self.matlab_engine = None
            self._stdout = None
            self._stderr = None
            logger.info("MATLAB engine stopped.")
            return True

        logger.info("MATLAB engine is not running.")
        return False

    # -------------------------------------------------------------------------
    # Simulation
    # -------------------------------------------------------------------------

    def simulate(
        self,
        model_path: str,
        sim_length: int = 86400,  # 24 hours in seconds
        delta_time: float = 0.1,
        spectrum_type: str = "PM",
        wave_class: str = "irregular",
        wave_height: float = 2.5,
        wave_period: float = 8.0,
        wave_seed: int | None = None,
        show_results: bool = True,
    ) -> int | None:
        """
        Execute a WEC-Sim device simulation with specified parameters.

        Runs a complete WEC-Sim simulation using MATLAB engine, stores results
        in the database, and optionally displays visualization plots.

        Args:
            model_path: Path to WEC model directory containing simulation files.
            sim_length: Simulation duration in seconds (default: 86400 = 24 hours).
            delta_time: Simulation time step in seconds (default: 0.1).
            spectrum_type: Wave spectrum type, e.g., "PM" (Pierson-Moskowitz).
            wave_class: Wave classification, "irregular" or "regular".
            wave_height: Significant wave height in meters (default: 2.5).
            wave_period: Peak wave period in seconds (default: 8.0).
            wave_seed: Random seed for wave generation (default: random 1-100).
            show_results: If True, display results plot after simulation.

        Returns:
            wec_sim_id from database if successful, None if failed.

        Raises:
            FileNotFoundError: If model_path does not exist.
            ValueError: If database is not configured.

        Example:
            >>> wec_sim_id = wecsim.simulate(
            ...     model_path="/models/RM3",
            ...     sim_length=3600,
            ...     wave_height=2.0,
            ...     wave_period=10.0,
            ... )
            >>> print(f"Simulation complete: wec_sim_id={wec_sim_id}")
        """
        # Set random seed if not provided
        if wave_seed is None:
            wave_seed = random.randint(1, 100)

        # Validate inputs
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"WEC model path does not exist: {model_path}")

        if self.database is None or self.database.db_path is None:
            raise ValueError(
                "Database not configured. Set database before running simulation."
            )

        model_name = os.path.basename(model_path)

        # Print simulation banner
        self._print_banner()

        logger.info("Starting WEC-Sim simulation...")
        logger.info("  Model: %s", model_name)
        logger.info("  Model Path: %s", model_path)
        logger.info("  Duration: %s seconds", sim_length)
        logger.info("  Time Step: %s seconds", delta_time)
        logger.info("  Wave Class: %s", wave_class)
        logger.info("  Wave Height: %s m", wave_height)
        logger.info("  Wave Period: %s s", wave_period)
        logger.info("  Wave Seed: %s", wave_seed)

        # Start MATLAB if needed
        if not self.start_matlab():
            logger.error("Failed to start MATLAB engine.")
            return None

        stdout = io.StringIO()
        stderr = io.StringIO()

        try:
            # Change to model directory
            self.matlab_engine.cd(str(model_path))

            # Set simulation parameters in MATLAB workspace
            self.matlab_engine.workspace["simLength"] = sim_length
            self.matlab_engine.workspace["dt"] = delta_time
            self.matlab_engine.workspace["spectrumType"] = spectrum_type
            self.matlab_engine.workspace["waveClassType"] = wave_class
            self.matlab_engine.workspace["waveHeight"] = wave_height
            self.matlab_engine.workspace["wavePeriod"] = wave_period
            self.matlab_engine.workspace["waveSeed"] = int(wave_seed)
            self.matlab_engine.workspace["DB_PATH"] = self.database.db_path

            # Run WEC-Sim
            self.matlab_engine.eval(
                "[m2g_out] = w2gSim(simLength,dt,spectrumType,waveClassType,"
                "waveHeight,wavePeriod,waveSeed);",
                nargout=0,
                stdout=stdout,
                stderr=stderr,
            )

            logger.info("Simulation complete. Writing to database...")

            # Run formatter to process results
            self.matlab_engine.eval("formatter", nargout=0, stdout=stdout, stderr=stderr)

            # Get the wec_sim_id from MATLAB workspace
            wec_sim_id = int(self.matlab_engine.workspace["wec_sim_id_result"])

            logger.info("WEC-Sim complete: model=%s, wec_sim_id=%s", model_name, wec_sim_id)

            # Show results if requested
            if show_results:
                self._show_results(wec_sim_id, model_name)

            return wec_sim_id

        except Exception as e:
            logger.error("WEC-Sim simulation failed: %s", e)
            if stdout.getvalue():
                logger.debug("MATLAB Output:\n%s", stdout.getvalue())
            if stderr.getvalue():
                logger.debug("MATLAB Errors:\n%s", stderr.getvalue())
            return None

        finally:
            # Don't auto-stop MATLAB - user may want to run multiple simulations
            pass

    def _print_banner(self) -> None:
        """Log WEC-Sim ASCII art banner."""
        logger.info(
            r"""
        WEC-SIM         ⣠⣴⣶⠾⠿⠿⠯⣷⣄⡀
                     ⢀⣼⣾⠛⠁⠀⠀⠀⠀⠀⠀⠈⢻⣦
                   ⣠⣾⠿⠁⠀⠀⠀⢀⣤⣾⣟⣛⣛⣶⣬⣿⣆
                 ⢀⣾⠟⠃⠀⠀⠀⠀⠀⣾⣿⠟⠉⠉⠉⠉⠛⠿⠟
               ⢀⣴⡟⠋⠀⠀⠀⠀⠀⠀⠀⣿⡏⣤
             ⣠⡿⠛⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣷⡍⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⣤⣤⣤⣀
           ⣠⣼⡏          ⠈⠙⠷⣤⣤⣠⣤⣤⡤⡶⣶⢿⠟⠹⠿⠄⣿⣿⠏⠀⣀⣤⡦⠀⠀⣀⡄
        ⣶⣿⠏                ⠈⠉⠓⠚⠋⠉⠀⠀⠀⠀⠀⠈⠛⡛⡻⠿⠿⠙⠓⢒⣺⡿⠋⠁
        ⠛⠁
            """
        )

    def _show_results(self, wec_sim_id: int, model_name: str) -> None:
        """
        Display visualization plots for WEC-Sim results.

        Args:
            wec_sim_id: Database ID of the simulation.
            model_name: Name of the WEC model.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not available for plotting")
            return

        # Query power results
        power_query = """
            SELECT time_sec as time, p_w as p, wave_elevation_m as eta
            FROM wec_power_results
            WHERE wec_sim_id = ?
            ORDER BY time_sec
        """
        df_power = self.database.query(power_query, params=(wec_sim_id,), return_type="df")

        if df_power.empty:
            logger.warning("No power data available for visualization")
            return

        # Create plot
        fig, ax1 = plt.subplots(figsize=(10, 5))

        # Secondary y-axis: Wave elevation
        ax2 = ax1.twinx()
        ax2.set_ylabel("Wave Elevation (m)")
        if "eta" in df_power.columns:
            ax2.plot(
                df_power["time"],
                df_power["eta"],
                color="tab:blue",
                alpha=0.3,
                linewidth=1,
                label="Wave Elevation",
            )

        # Primary y-axis: Power
        ax1.set_xlabel("Time (s)")
        ax1.set_ylabel("Active Power (W)")
        ax1.plot(
            df_power["time"],
            df_power["p"],
            color="tab:red",
            label="Power Output",
            linewidth=1.5,
        )

        # Title and layout
        fig.suptitle(f"WEC-Sim Output — Model: {model_name}, ID: {wec_sim_id}")
        fig.tight_layout()

        # Combine legends
        lines_1, labels_1 = ax1.get_legend_handles_labels()
        lines_2, labels_2 = ax2.get_legend_handles_labels()
        ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper right")

        plt.show()

    # -------------------------------------------------------------------------
    # Results Access
    # -------------------------------------------------------------------------

    def get_simulation_info(self, wec_sim_id: int) -> pd.DataFrame | None:
        """
        Get metadata for a WEC-Sim simulation.

        Args:
            wec_sim_id: Database ID of the simulation.

        Returns:
            DataFrame with simulation metadata or None if not found.
        """
        if self.database is None:
            return None

        return self.database.query(
            "SELECT * FROM wec_simulations WHERE wec_sim_id = ?",
            params=(wec_sim_id,),
            return_type="df",
        )

    def get_power_results(self, wec_sim_id: int) -> pd.DataFrame:
        """
        Get power time-series results for a WEC-Sim simulation.

        Args:
            wec_sim_id: Database ID of the simulation.

        Returns:
            DataFrame with columns: time, p (Watts), q (VAR), eta (wave elevation).
        """
        if self.database is None:
            return pd.DataFrame()

        return self.database.query(
            """
            SELECT time_sec as time, p_w as p, q_var as q, wave_elevation_m as eta
            FROM wec_power_results
            WHERE wec_sim_id = ?
            ORDER BY time_sec
            """,
            params=(wec_sim_id,),
            return_type="df",
        )

    def list_simulations(self) -> pd.DataFrame:
        """
        List all WEC-Sim simulations in the database.

        Returns:
            DataFrame with simulation metadata.
        """
        if self.database is None:
            return pd.DataFrame()

        return self.database.query(
            """
            SELECT wec_sim_id, model_type, sim_duration_sec, delta_time,
                   wave_height_m, wave_period_sec, wave_spectrum, wave_class,
                   created_at
            FROM wec_simulations
            ORDER BY created_at DESC
            """,
            return_type="df",
        )
