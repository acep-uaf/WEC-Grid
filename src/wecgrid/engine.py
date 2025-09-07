"""Simulation orchestration for WEC-Grid.

Provides the :class:`Engine` entry point that wires together WEC farms,
power-system modelers (PSS®E, PyPSA), time management, a results database,
and plotting utilities.
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
    """Top-level controller for WEC-Grid simulations.

    Coordinates WEC farm integration with PSS®E and/or PyPSA, manages
    simulation time, and provides access to the database and plotting.

    Attributes:
        case_file: Path to the input case file (RAW/SAV).
        case_name: Human-readable case identifier.
        time: Time manager (:class:`WECGridTime`).
        psse: PSS®E modeler instance or ``None``.
        pypsa: PyPSA modeler instance or ``None``.
        wec_farms: WEC farms added to the simulation.
        database: Database interface (:class:`WECGridDB`).
        plot: Plotting utilities (:class:`WECGridPlot`).
        wecsim: WEC-Sim runner (:class:`WECSimRunner`).
        sbase: System base power [MVA] once a modeler is initialized.
    """

    def __init__(self):
        """Initialize the WEC-Grid Engine.

        Sets up an engine instance with default configuration.  
        All modelers are uninitialized (``None``) until explicitly loaded
        via the ``load()`` method.
        """
        self.case_file: Optional[str] = None
        self.case_name: Optional[str] = None
        self.time = WECGridTime()
        self.psse: Optional[PSSEModeler] = None
        self.pypsa: Optional[PyPSAModeler] = None
        self.wec_farms: List[WECFarm] = []
        self.database = WECGridDB(self)
        self.plot = WECGridPlot(self)
        self.wecsim: WECSimRunner = WECSimRunner(self.database)
        self.sbase: Optional[float] = None


    def __repr__(self) -> str:
        """Return a compact tree-style summary of the engine state."""
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
        """Set the power-system case file to load later.

        Args:
            case_file: Path or identifier for a case file (RAW/SAV).

        Note:
            This only records the path and a friendly name; it does not
            validate file existence or format.
        """

        self.case_file = str(case_file)
        self.case_name = Path(case_file).stem.replace("_", " ").replace("-", " ")

    def load(self, software: List[str]) -> None:
        """Initialize one or more modelers.

        Args:
            software: Iterable of backends to initialize ("psse", "pypsa").

        Raises:
            ValueError: If no case is set or an unsupported backend is given.
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
        scaling_factor: float = 1.0,  # used for scaling WEC power output
    ) -> None:
        """Add a WEC farm connected at a bus.

        Args:
            farm_name: Farm identifier.
            size: Number of identical devices in the farm.
            wec_sim_id: WEC-Sim run ID in the database.
            bus_location: Bus number to connect the WEC farm.
            connecting_bus: Existing bus to which the new bus/branch ties.
            scaling_factor: Linear multiplier applied to device power.

        Note:
            Power scales with ``size`` and ``scaling_factor``. Modelers are
            updated if already loaded.
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
        amplitude: float = 0.05,  # ±5% swing around mean
        min_multiplier: float = 0.50,  # floor/ceiling clamp
        amp_overrides: Optional[Dict[int, float]] = None,
    ) -> pd.DataFrame:
        """Create simple double-peak daily load multipliers (per-unit).

        Args:
            morning_peak_hour: Morning peak time [h].
            evening_peak_hour: Evening peak time [h].
            morning_sigma_h: Morning peak width [h].
            evening_sigma_h: Evening peak width [h].
            amplitude: Max variation (e.g., 0.05 for ±5%).
            min_multiplier: Floor for the multiplier.
            amp_overrides: Optional per-bus amplitude overrides.

        Returns:
            DataFrame indexed by simulation snapshots with bus-number columns
            and per-unit load values as entries.

        Raises:
            ValueError: If no modeler is loaded to provide base loads.
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

                Args:
                    h: Hours at which the Gaussian is evaluated.
                    mu: Peak hour of the Gaussian curve.
                    sig: Standard deviation of the curve.

                Returns:
                    numpy.ndarray: Gaussian weights for ``h``.

                """
                h = np.asarray(h, dtype=float)
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
        """Run a time-series simulation across loaded modelers.

        Args:
            num_steps: Optional number of steps to run; defaults to available data.
            load_curve: If True, apply synthetic per-unit load multipliers.
            strict_convergence: Reserved for future use.
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
