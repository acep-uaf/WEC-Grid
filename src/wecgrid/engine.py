"""Top-level orchestration for WEC-Grid simulations.

Defines the :class:`Engine` that coordinates WEC farms, power system modelers,
database access, and visualization utilities. The module links PSS®E and
PyPSA backends, manages time through :class:`WECGridTime`, and integrates
WEC-Sim for device-level modeling.
"""

# Standard library
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Third-party
import numpy as np
import pandas as pd

# Local
from wecgrid.modelers import PSSEModeler, PyPSAModeler
from wecgrid.util import WECGridDB, WECGridTime, WECGridPlot
from wecgrid.wec import WECFarm, WECSimRunner


class Engine:
    """Main orchestrator for WEC-Grid simulations and cross-platform power system analysis.

    Coordinates WEC farm integration with PSS®E and PyPSA power system modeling backends.
    Manages simulation workflows, time synchronization, and visualization for grid studies.

    Attributes:
        case_file (str | None): Path to power system case file (.RAW).
        case_name (str | None): Human-readable case identifier.
        time (WECGridTime): Time coordination and snapshot management.
        psse (PSSEModeler | None): PSS®E simulation interface.
        pypsa (PyPSAModeler | None): PyPSA simulation interface.
        wec_farms (List[WECFarm]): Collection of WEC farms in simulation.
        database (WECGridDB): Database interface for simulation data.
        plot (WECGridPlot): Visualization and plotting interface.
        wecsim (WECSimRunner): WEC-Sim integration for device modeling.
        sbase (float | None): System base power in MVA.

    Example:
        >>> engine = Engine()
        >>> engine.case("IEEE_30_bus")
        >>> engine.load(["psse", "pypsa"])
        >>> engine.apply_wec("North Farm", size=5, bus_location=14)
        >>> engine.simulate(load_curve=True)
        >>> engine.plot.comparison_suite()

    Notes:
        - PSS®E requires commercial license; PyPSA is open-source
        - WEC data from WEC-Sim simulations (requires MATLAB)
        - Supports cross-platform validation studies

    TODO:
        - Consider renaming to WECGridEngine for clarity
        - need a way to map GridState componet names to modeler component names
    """

    def __init__(self):
        """Initialize the WEC-Grid Engine with default configuration.

        Creates engine instance ready for case loading and simulation setup.
        All modelers are None until explicitly loaded via load() method.
        """
        self.case_file: Optional[str] = None
        self.case_name: Optional[str] = None
        self.time = WECGridTime()  # TODO this needs more functionality
        self.psse: Optional[PSSEModeler] = None
        self.pypsa: Optional[PyPSAModeler] = None
        self.wec_farms: List[WECFarm] = []
        self.database = WECGridDB(self)
        self.plot = WECGridPlot(self)
        self.wecsim: WECSimRunner = WECSimRunner(self.database)
        self.sbase: Optional[float] = None

    # print(r"""

    #  __     __     ______     ______     ______     ______     __     _____
    # /\ \  _ \ \   /\  ___\   /\  ___\   /\  ___\   /\  == \   /\ \   /\  __-.
    # \ \ \/ ".\ \  \ \  __\   \ \ \____  \ \ \__ \  \ \  __<   \ \ \  \ \ \/\ \
    #  \ \__/".~\_\  \ \_____\  \ \_____\  \ \_____\  \ \_\ \_\  \ \_\  \ \____-
    #   \/_/   \/_/   \/_____/   \/_____/   \/_____/   \/_/ /_/   \/_/   \/____/
    #             """)

    def __repr__(self) -> str:
        """String representation of Engine.

        Returns:
            str: Tree-style summary
        """
        return (
            f"Engine:\n"
            f"├─ Case: {self.case_name}\n"
            f"├─ PyPSA: {'Loaded' if self.pypsa else 'Not Loaded'}\n"
            f"├─ PSS/E: {'Loaded' if self.psse else 'Not Loaded'}\n"
            f"├─ WEC-Farms/WECs: {len(self.wec_farms)} - {len(self.wec_farms) and sum(len(farm.wec_devices) for farm in self.wec_farms) or 0}\n"
            f"└─ Buses: {len(self.pypsa.bus) if self.pypsa else len(self.psse.bus) if self.psse else 0}\n"
            f"\n"
            f"Sbase: {self.sbase if self.sbase else 'Not Loaded'} MVA"
        )

    def case(self, case_file: str):
        """Specify the power system case file for subsequent loading.

        Args:
            case_file (str): Path or identifier for a PSS®E RAW case file. Examples:
                - Full paths: ``"/path/to/system.RAW"``
                - Bundled cases: ``"IEEE_30_bus"``
                - With extension: ``"IEEE_39_bus.RAW"``

        Example:
            >>> engine.case("IEEE_30_bus")
            >>> print(engine.case_name)
            IEEE 30 bus

        Notes:
            This method only stores the file path and a human-friendly name.
            It does not verify that the file exists or is loadable.
            Only PSS®E RAW (.RAW) format is supported.
        """
        self.case_file = str(case_file)
        self.case_name = Path(case_file).stem.replace("_", " ").replace("-", " ")

    def load(self, software: List[str]) -> None:
        """Initialize power system simulation backends.

        Args:
            software (List[str]): Backends to initialize ("psse", "pypsa").

        Raises:
            ValueError: If no case file loaded or invalid software name.
            RuntimeError: If initialization fails (missing license, etc.).

        Example:
            >>> engine.case("IEEE_30_bus")
            >>> engine.load(["psse", "pypsa"])

        Notes:
            - PSS®E requires commercial license; PyPSA is open-source
            - Enables cross-platform validation studies
            - Both backends are independent and can simulate separately

        TODO:
            - Add error handling for PSS®E license failures
        """
        if self.case_file is None:
            raise ValueError(
                "No case file set. Use `engine.case('path/to/case.RAW')` first."
            )

        for name in software:
            name = name.lower()
            if name == "psse":
                self.psse = PSSEModeler(self)
                self.psse.init_api()
                self.sbase = self.psse.sbase
                # TODO: check if error is thrown if init fails
            elif name == "pypsa":
                self.pypsa = PyPSAModeler(self)
                self.pypsa.init_api()
                self.sbase = self.pypsa.sbase
                # if self.psse is not None:
                #     self.psse.adjust_reactive_lim()
                # TODO: check if error is thrown if init fails
            else:
                raise ValueError(
                    f"Unsupported software: '{name}'. Use 'psse' or 'pypsa'."
                )

    def apply_wec(
        self,
        farm_name: str,
        size: int = 1,
        wec_sim_id: int = 1,
        bus_location: int = 1,
        connecting_bus: int = 1,  # todo this should default to swing bus
        scaling_factor: int = 1,  # used for scaling wec power output
    ) -> None:
        """Add a Wave Energy Converter (WEC) farm to the power system.

        Args:
            farm_name (str): Human-readable WEC farm identifier.
            size (int, optional): Number of WEC devices in farm. Defaults to 1.
            wec_sim_id (int, optional): Database simulation ID for WEC data. Defaults to 1.
            bus_location (int, optional): Grid bus for WEC connection. Defaults to 1.
            connecting_bus (int, optional): Network topology connection bus. Defaults to 1.
            scaling_factor (int, optional): Multiplier applied to WEC power output
                [unitless]. Defaults to 1.

        Example:
            >>> engine.apply_wec("North Coast Farm", size=20, bus_location=14)
            >>> print(f"Total farms: {len(engine.wec_farms)}")
            Total farms: 1

        Notes:
            - Farm power scales linearly with device count
            - WEC data sourced from database using sim_id
            - Generator IDs are auto-assigned sequentially based on farm order

        TODO:
            - Fix PSS®E generator ID limitation (max 9 farms)
            - Default connecting_bus should be swing bus
        """
        wec_farm: WECFarm = WECFarm(
            farm_name=farm_name,
            farm_id=len(self.wec_farms) + 1,  # Unique farm_id for each farm,
            gen_name="",
            database=self.database,
            time=self.time,
            wec_sim_id=wec_sim_id,
            bus_location=bus_location,
            connecting_bus=connecting_bus,
            size=size,
            sbase=self.sbase,
            scaling_factor=scaling_factor,
            # TODO potenital issue where PSSE is using gen_id as the gen identifer and that's limited to 2 chars. so hard cap at 9 farms in this code rn
        )
        self.wec_farms.append(wec_farm)

        for modeler in [self.psse, self.pypsa]:
            if modeler is not None:
                modeler.add_wec_farm(wec_farm)
                wec_farm.gen_name = (
                    modeler.grid.gen.loc[
                        modeler.grid.gen.bus == wec_farm.bus_location, "gen_name"
                    ].iloc[0]
                    if (modeler.grid.gen.bus == wec_farm.bus_location).any()
                    else None
                )
        print("WEC Farm added:", wec_farm.farm_name)

    def generate_load_curves(
        self,
        morning_peak_hour: float = 8.0,
        evening_peak_hour: float = 18.0,
        morning_sigma_h: float = 2.0,
        evening_sigma_h: float = 3.0,
        amplitude: float = 0.05,  # ±30% swing around mean
        min_multiplier: float = 0.50,  # floor/ceiling clamp
        amp_overrides: Optional[Dict[int, float]] = None,
    ) -> pd.DataFrame:
        """Generate realistic time-varying load profiles for power system simulation.

        Creates bus-specific load time series with double-peak daily pattern
        representing typical electrical demand. Scales base case loads with
        configurable peak timing and variability.

        Args:
            morning_peak_hour (float, optional): Morning demand peak time [hours].
                Defaults to 8.0.
            evening_peak_hour (float, optional): Evening demand peak time [hours].
                Defaults to 18.0.
            morning_sigma_h (float, optional): Morning peak width [hours]. Defaults to 2.0.
            evening_sigma_h (float, optional): Evening peak width [hours]. Defaults to 3.0.
            amplitude (float, optional): Maximum variation around base load.
                Defaults to 0.30 (±30%).
            min_multiplier (float, optional): Minimum load multiplier. Defaults to 0.70.
            amp_overrides (Dict[int, float], optional): Per-bus amplitude overrides.

        Returns:
            pd.DataFrame: Time-indexed load profiles [MW]. Index: simulation snapshots,
                Columns: bus numbers, Values: active power demand.

        Raises:
            ValueError: If no power system modeler loaded.

        Example:
            >>> # Generate standard load curves
            >>> profiles = engine.generate_load_curves()
            >>> print(f"Buses: {list(profiles.columns)}")

            >>> # Custom peaks for industrial area
            >>> custom = engine.generate_load_curves(
            ...     morning_peak_hour=6.0,
            ...     evening_peak_hour=22.0,
            ...     amplitude=0.15
            ... )

        Notes:
            - Double-peak pattern: morning and evening demand peaks
            - Short simulations (<6h): flat profile to avoid artificial peaks
            - PSS®E base loads: system MVA base
            - PyPSA base loads: aggregated by bus

        TODO:
            - Add weekly/seasonal variation patterns
        """

        if self.psse is None and self.pypsa is None:
            raise ValueError(
                "No power system modeler loaded. Use `engine.load(...)` first."
            )

            # --- Use PSSE or PyPSA Grid state to get base load ---
        if self.psse is not None:
            base_load = (
                self.psse.grid.load[["bus", "p"]]
                .drop_duplicates("bus")
                .set_index("bus")["p"]
            )
        elif self.pypsa is not None:
            base_load = (
                self.pypsa.grid.load[["bus", "p"]]
                .drop_duplicates("bus")
                .set_index("bus")["p"]
            )
        else:
            raise ValueError("No valid base load could be extracted from modelers.")

        snaps = pd.to_datetime(self.time.snapshots)
        prof = pd.DataFrame(index=snaps)

        # make sure this is a plain ndarray, not a Float64Index
        hours = (
            snaps.hour.values
            + snaps.minute.values / 60.0
            + snaps.second.values / 3600.0
        )

        dur_sec = 0 if len(snaps) < 2 else (snaps.max() - snaps.min()).total_seconds()

        if dur_sec < 6 * 3600:
            z = np.zeros_like(hours, dtype=float)
        else:

            def g(h, mu, sig):
                """Return Gaussian weights for given hours.

                Parameters
                ----------
                h : array-like
                    Hours at which the Gaussian is evaluated. Values are
                    cast to a NumPy array to ensure vectorized
                    operations.
                mu : float
                    Peak hour (mean) of the Gaussian curve.
                sig : float
                    Spread of the curve (standard deviation).

                Returns
                -------
                numpy.ndarray
                Array of Gaussian weights corresponding to ``h``.

                Notes
                -----
                Intended for shaping daily load profiles by combining
                morning and evening peaks.
                """
                h = np.asarray(h, dtype=float)  # <-- belt-and-suspenders
                return np.exp(-0.5 * ((h - mu) / sig) ** 2)

            s = g(hours, morning_peak_hour, morning_sigma_h) + g(
                hours, evening_peak_hour, evening_sigma_h
            )
            s = np.asarray(s, dtype=float)
            z = (s - s.mean()) / (
                s.std() + 1e-12
            )  # or: z = (s - np.mean(s)) / (np.std(s) + 1e-12)

        amp_overrides = (
            {}
            if amp_overrides is None
            else {int(k): float(v) for k, v in amp_overrides.items()}
        )

        for bus, p_base in base_load.items():
            if p_base <= 0:
                continue
            a = amp_overrides.get(int(bus), amplitude)  # per-bus amplitude
            shape_bus = 1.0 + a * z
            shape_bus = np.clip(shape_bus, min_multiplier, 2.0 - min_multiplier)
            prof[int(bus)] = p_base * shape_bus

        prof.index.name = "time"
        return prof

    def simulate(
        self, num_steps: Optional[int] = None, load_curve: bool = False, strict_convergence: bool = False
    ) -> None:
        """Execute time-series power system simulation across loaded backends.

        Args:
            num_steps (int | None): Number of simulation time steps. If ``None``,
                the simulation uses the full available data length, constrained by
                WEC time-series if present.
            load_curve (bool): Enable time-varying load profiles. Defaults to ``False``.
            strict_convergence (bool): Stop simulation on first convergence failure.
                Defaults to ``False`` (robust mode continues and reports failed steps).

        Raises:
            ValueError: If no power system modelers are loaded.

        Example:
            >>> engine.simulate(num_steps=144)
            >>> engine.simulate(load_curve=True)
            >>> engine.simulate(strict_convergence=True)  # Operational mode

        Notes:
            - All backends use identical time snapshots for comparison
            - WEC data length constrains maximum simulation length
            - Load curves use reduced amplitude (10%) for realism
            - Results accessible via ``engine.psse.grid`` and ``engine.pypsa.grid``
            - Strict mode provides traditional power system analysis behavior

        TODO:
            - Address multi-farm data length inconsistencies
            - Implement automatic plotting feature
        """

        # show that if different farms have different wec durations this logic fails
        if self.wec_farms:
            available_len = len(self.wec_farms[0].wec_devices[0].dataframe)

            if num_steps is not None:
                if num_steps > available_len:
                    print(
                        f"[WARNING] Requested num_steps={num_steps} exceeds "
                        f"WEC data length={available_len}. Truncating to {available_len}."
                    )
                final_len = min(num_steps, available_len)
            else:
                final_len = available_len

            if final_len != self.time.snapshots.shape[0]:
                self.time.update(num_steps=final_len)

        else:
            # No WEC farm — just update if num_steps is given
            if num_steps is not None:
                self.time.update(num_steps=num_steps)

        load_curve_df = (
            self.generate_load_curves(amplitude=0.10) if load_curve else None
        )

        for modeler in [self.psse, self.pypsa]:
            if modeler is not None:
                modeler.simulate(load_curve=load_curve_df)
                # todo if plot then plot
