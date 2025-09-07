"""
WEC-Sim simulation runner for Wave Energy Converter device-level modeling.

This module provides the interface between WEC-Grid and WEC-Sim for high-fidelity
wave energy converter simulations using MATLAB engine integration.
"""

# Standard library
import io
import json
import os
import random
from typing import Optional

# Third-party
import matplotlib.pyplot as plt

# Local
from wecgrid.util import WECGridDB

from pathlib import Path


def _user_config_dir() -> Path:
    """Return a user-writable config directory for WEC-Grid.

    Uses ``platformdirs`` if available, otherwise falls back to ``~/.wecgrid``.
    """
    try:
        from platformdirs import user_config_dir  # type: ignore

        return Path(user_config_dir(appname="wecgrid", appauthor=False))
    except Exception:
        return Path.home() / ".wecgrid"


# Configuration file path (user-specific)
_CONFIG_FILE = _user_config_dir() / "wecsim_config.json"


class WECSimRunner:
    """Interface for running WEC-Sim device-level simulations via MATLAB engine.

    Simplified runner that manages MATLAB engine, executes WEC-Sim models from
    their native directories, and stores results in WEC-Grid database.

    Attributes:
        wec_sim_path (str, optional): Path to WEC-Sim MATLAB installation.
        database (WECGridDB): Database interface for simulation data storage.
        matlab_engine (matlab.engine.MatlabEngine, optional): Active MATLAB engine.
    """

    def __init__(self, database: WECGridDB):
        """Initialize a WEC-Sim runner tied to a database connection.

        Args:
            database (WECGridDB): Interface used to store and retrieve
                simulation data.

        Attributes:
            wec_sim_path (Optional[str]): Location of the WEC-Sim MATLAB
                installation. Defaults to ``None`` and may be populated from
                configuration.
            matlab_engine (Optional[matlab.engine.MatlabEngine]): Handle to the
                MATLAB engine. ``None`` until :meth:`start_matlab` is called.

        Side Effects:
            Loads ``wecsim_config.json`` to populate ``wec_sim_path`` if a
            configuration exists.
        """
        self.wec_sim_path: Optional[str] = None
        self.database: WECGridDB = database
        self.matlab_engine = None

    def _load_config(self) -> None:
        """Load WEC-Sim configuration from env var or JSON file."""
        # Highest priority: environment variable
        env_path = os.getenv("WECGRID_WECSIM_PATH")
        if env_path:
            self.wec_sim_path = env_path
            return

        try:
            if _CONFIG_FILE.exists():
                with open(_CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    self.wec_sim_path = config.get("wec_sim_path")
        except Exception as e:
            print(f"Warning: Could not load WEC-Sim config: {e}")

    def _save_config(self) -> None:
        """Save WEC-Sim configuration to user JSON file."""
        try:
            _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            config = {"wec_sim_path": self.wec_sim_path}
            with open(_CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            print(f"Saved WEC-Sim configuration to: {_CONFIG_FILE}")
        except Exception as e:
            print(f"Warning: Could not save WEC-Sim config: {e}")

    def set_wec_sim_path(self, path: str) -> None:
        """Configure the WEC-Sim MATLAB framework installation path.

        Args:
            path (str): Filesystem location of the WEC-Sim MATLAB installation.

        Raises:
            FileNotFoundError: If the supplied ``path`` does not exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"WEC-SIM path does not exist: {path}")
        self.wec_sim_path = path
        self._save_config()

    def get_wec_sim_path(self) -> Optional[str]:
        """Get the currently configured WEC-Sim path.

        Returns:
            Optional[str]: Absolute path to the WEC-Sim installation or ``None``
            if no path has been configured.
        """
        return self.wec_sim_path

    def show_config(self) -> None:
        """Display current WEC-Sim configuration.

        Prints the currently configured WEC-Sim path along with the location of
        the configuration file used to persist this setting.
        """
        print("WEC-Sim Configuration:")
        print(f"  Path: {self.wec_sim_path or 'Not configured'}")
        print(f"  Config file: {_CONFIG_FILE}")
        print(f"  Config exists: {_CONFIG_FILE.exists()}")
        print("  Env var: WECGRID_WECSIM_PATH (overrides config if set)")

    def start_matlab(self) -> bool:
        """Initialize MATLAB engine and configure WEC-Sim framework paths.

        Returns:
            bool: ``True`` if the MATLAB engine was started, ``False`` if the
            engine was already running or the MATLAB Python API is unavailable.
        """
        self._load_config()
        if self.wec_sim_path is None:
            print("\n" + "=" * 60)
            print("WEC-Sim Path not set")
            print("=" * 60)
            print(
                "Please set the WEC-Sim path here or using the wecsim.set_wec_sim_path() method."
            )
            path = input("Enter the WEC-Sim path: ")
            self.set_wec_sim_path(path)
        try:
            import matlab.engine
        except ImportError:
            print("MATLAB python API not installed. ")
            print(
                "https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html"
            )
            return False
        if self.matlab_engine is None:
            print(f"Starting MATLAB Engine... ", end="")
            self.matlab_engine = matlab.engine.start_matlab()
            print("MATLAB engine started.")

            if self.wec_sim_path is None:
                raise ValueError(
                    "WEC-SIM path is not configured. Please set it using set_wec_sim_path()"
                )

            if not os.path.exists(self.wec_sim_path):
                raise FileNotFoundError(
                    f"WEC-SIM path does not exist: {self.wec_sim_path}"
                )
            print(f"Adding WEC-SIM to path... ", end="")
            matlab_path = self.matlab_engine.genpath(str(self.wec_sim_path), nargout=1)
            self.matlab_engine.addpath(matlab_path, nargout=0)
            print("WEC-SIM path added.")

            self.out = io.StringIO()
            self.err = io.StringIO()
            return True
        else:
            print("MATLAB engine is already running.")
            return False

    def stop_matlab(self) -> bool:
        """Shutdown the MATLAB engine and free system resources.

        Returns:
            bool: ``True`` if the engine was stopped, ``False`` if no engine was
            running.
        """
        if self.matlab_engine is not None:
            self.matlab_engine.quit()
            self.matlab_engine = None
            print("MATLAB engine stopped.")
            self.out = None
            self.err = None
            return True
        print("MATLAB engine is not running.")
        return False

    def sim_results(self, df_power, model, wec_sim_id):
        """Generate visualization plots for WEC-Sim simulation results.

        Args:
            df_power (pd.DataFrame): Power and optional wave elevation time
                series produced by WEC-Sim.
            model (str): Name of the WEC-Sim model used for the simulation.
            wec_sim_id (int): Database identifier for the WEC-Sim run.
        """
        if df_power.empty:
            print("No power data available for visualization")
            return

        # Plot
        fig, ax1 = plt.subplots(figsize=(10, 5))

        # Secondary y-axis: Wave elevation (m) — drawn first for background
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

        # Primary y-axis: Active power W
        ax1.set_xlabel("Time (s)")
        ax1.set_ylabel("Active Power W")
        ax1.plot(
            df_power["time"],
            df_power["p"],
            color="tab:red",
            label="Power Output",
            linewidth=1.5,
        )

        # Title + layout
        fig.suptitle(f"WEC-SIM Output — Model: {model}, WEC Sim ID: {wec_sim_id}")
        fig.tight_layout()

        # Combine legends
        lines_1, labels_1 = ax1.get_legend_handles_labels()
        lines_2, labels_2 = ax2.get_legend_handles_labels()
        ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper right")

        plt.show()

    def __call__(
        self,
        model_path: str,
        sim_length: int = 3600 * 24,  # 24 hours
        delta_time: float = 0.1,
        spectrum_type: str = "PM",
        wave_class: str = "irregular",
        wave_height: float = 2.5,
        wave_period: float = 8.0,
        wave_seed: int = random.randint(1, 100),
    ) -> Optional[int]:
        """Execute a complete WEC-Sim device simulation with specified parameters.

        Args:
            model_path (str): Path to WEC model directory containing simulation files.
            sim_length (int, optional): Simulation duration in seconds. Defaults to 86400 (24 hours).
            delta_time (float, optional): Simulation time step in seconds. Defaults to 0.1.
            spectrum_type (str, optional): Wave spectrum type. Defaults to 'PM'.
            wave_class (str, optional): Wave type classification. Defaults to 'irregular'.
            wave_height (float, optional): Significant wave height in meters. Defaults to 2.5.
            wave_period (float, optional): Peak wave period in seconds. Defaults to 8.0.
            wave_seed (int, optional): Random seed for wave generation. Defaults to random 1-100.

        Returns:
            int: wec_sim_id from database if successful, None if failed.
        """
        print(
            r"""
              
            ⠀ WEC-SIM⠀⠀⠀⠀     ⣠⣴⣶⠾⠿⠿⠯⣷⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⣾⠛⠁⠀⠀⠀⠀⠀⠀⠈⢻⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⠿⠁⠀⠀⠀⢀⣤⣾⣟⣛⣛⣶⣬⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⠟⠃⠀⠀⠀⠀⠀⣾⣿⠟⠉⠉⠉⠉⠛⠿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⡟⠋⠀⠀⠀⠀⠀⠀⠀⣿⡏⣤⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⠀⠀⣠⡿⠛⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣷⡍⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⣤⣤⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⣠⣼⡏⠀⠀           ⠈⠙⠷⣤⣤⣠⣤⣤⡤⡶⣶⢿⠟⠹⠿⠄⣿⣿⠏⠀⣀⣤⡦⠀⠀⠀⠀⣀⡄
            ⢀⣄⣠⣶⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠓⠚⠋⠉⠀⠀⠀⠀⠀⠀⠈⠛⡛⡻⠿⠿⠙⠓⢒⣺⡿⠋⠁
            ⠉⠉⠉⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠁⠀
            """
        )

        try:
            # Validate model path
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"WEC model path '{model_path}' does not exist")

            model_name = os.path.basename(model_path)

            if self.start_matlab():
                print("Starting WEC-SIM simulation...")
                print(
                    f"\t Model: {model_name}\n"
                    f"\t Model Path: {model_path}\n"
                    f"\t Simulation Length: {sim_length} seconds\n"
                    f"\t Time Step: {delta_time} seconds\n"
                    f"\t Wave class: {wave_class}\n"
                    f"\t Wave Height: {wave_height} m\n"
                    f"\t Wave Period: {wave_period} s\n"
                )

                # Change to model directory - this is the key change from the old version
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
                out = io.StringIO()
                err = io.StringIO()

                # Run the WEC-SIM function from the model directory
                self.matlab_engine.eval(
                    "[m2g_out] = w2gSim(simLength,dt,spectrumType,waveClassType,waveHeight,wavePeriod,waveSeed);",
                    nargout=0,
                    stdout=out,
                    stderr=err,
                )
                print(
                    f"simulation complete... writing to database at \n\t{self.database.db_path}"
                )

                self.matlab_engine.eval("formatter", nargout=0, stdout=out, stderr=err)

                # Get the wec_sim_id that was created by the database
                wec_sim_id = self.matlab_engine.workspace["wec_sim_id_result"]
                wec_sim_id = int(wec_sim_id)  # Convert from MATLAB double to Python int

                print(
                    f"WEC-SIM complete: model = {model_name}, wec_sim_id = {wec_sim_id}, duration = {sim_length}s"
                )

                # Query power results for visualization
                power_query = """
                    SELECT time_sec as time, p_w as p, wave_elevation_m as eta 
                    FROM wec_power_results 
                    WHERE wec_sim_id = ? 
                    ORDER BY time_sec
                """
                df_power = self.database.query(
                    power_query, params=(wec_sim_id,), return_type="df"
                )
                print("MATLAB Output:")
                print("=" * 10)
                print(out.getvalue())
                print("=" * 10)
                self.stop_matlab()

                if not df_power.empty:
                    self.sim_results(df_power, model_name, wec_sim_id)

                return wec_sim_id

            print("Failed to start MATLAB engine.")
            return None

        except Exception as e:
            print(f"[WEC-SIM ERROR] model_path={model_path} → {e}")
            print("=" * 10)
            print("MATLAB Output:")
            print(out.getvalue())
            print("MATLAB Errors:")
            print(err.getvalue())
            print("=" * 10)

            self.stop_matlab()
            return None
