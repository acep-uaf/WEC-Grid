"""PyPSA modeler integration for WEC-Grid."""

# Standard library
import contextlib
import io
import logging
import time
from collections import defaultdict
from datetime import datetime
from math import inf
from typing import Any, Dict, Optional

# Third-party
import numpy as np
import pandas as pd
import pypsa
from tqdm import tqdm

# External packages
import grg_pssedata.io as grgio
from grg_pssedata.io import parse_psse_case_file

# Local
from .base import PowerSystemModeler, GridState


class PyPSAModeler(PowerSystemModeler):
    """PyPSA-backed power-system modeler.

    Builds a :class:`pypsa.Network` from a PSS®E RAW, solves power flow, and
    exposes snapshots/time-series in a unified :class:`GridState` schema.
    """

    def __init__(self, engine: Any):
        """Initialize PyPSAModeler with simulation engine.

        Args:
            engine: WEC-GRID Engine with case_file, time, and wec_farms attributes.

        Note:
            Call init_api() after construction to initialize PyPSA network.
        """
        super().__init__(engine)
        self.network: Optional[pypsa.Network] = None
        self.grid.software = "pypsa"
        self.report.software = "pypsa"
        self.grid.case = engine.case_name

    # def __repr__(self) -> str:
    #     """String representation of PyPSA model with network summary.

    #     Returns:
    #         str: Tree-style summary with case name, component counts, and system base [MVA].
    #     """
    #     return (
    #         f"pypsa:\n"
    #         f"├─ case: {self.engine.case_name}\n"
    #         f"├─ buses: {len(self.grid.bus)}\n"
    #         f"├─ generators: {len(self.grid.gen)}\n"
    #         f"├─ loads: {len(self.grid.load)}\n"
    #         f"└─ lines: {len(self.grid.line)}"
    #         f"\n"
    #         f"Sbase: {self.sbase} MVA"
    #     )

    def init_api(self) -> bool:
        """Parse case → build network → solve initial PF → take snapshot.

        Returns:
            True if initialization succeeds, otherwise False.
        """
        if not self.import_raw_to_pypsa():
            return False
        if not self.solve_powerflow():
            return False
        self.take_snapshot(timestamp=self.engine.time.start_time)  # populates self.grid
        # print("PyPSA software initialized")
        return True

    def solve_powerflow(self, log: bool = False) -> bool:
        """Solve power flow via ``Network.pf()``.

        Args:
            log: If True, record timing and iterations in the report.

        Returns:
            True if converged, otherwise False.
        """

        # Suppress PyPSA logging
        logger = logging.getLogger("pypsa")
        previous_level = logger.level
        logger.setLevel(logging.WARNING)

        try:
            # Optional: suppress stdout too, just in case
            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                # === Power Flow Solution ===
                pf_start = time.time()
                results = self.network.pf()
                pf_time = time.time() - pf_start

        except Exception as e:
            if log:
                self.report.add_pf_solve_data(
                    solve_time=0.0, iterations=0, converged=0, msg=e
                )
            return 0

        if log:
            self.report.add_pf_solve_data(
                solve_time=pf_time,
                iterations=results.n_iter.iloc[0][0],
                converged=1,
                msg="converged",
            )
        return 1

    def import_raw_to_pypsa(self) -> bool:
        """Import PSS®E case file and build PyPSA Network.

        Builds a PyPSA Network from a parsed PSS®E RAW case file using the GRG parser.
        Converts PSS®E data structures and impedance values to PyPSA format, including
        buses, lines, generators, loads, transformers, and shunt impedances.

        Returns:
            bool: True if case import is successful, False otherwise.

        Raises:
            Exception: If case file parsing fails or case is invalid.

        Notes:
            The import process includes:

            Bus Data:
            - Bus numbers, names, and base voltages [kV]
            - Voltage magnitude setpoints and limits [pu]
            - Bus type mapping (PQ, PV, Slack)

            Line Data:
            - Resistance and reactance converted from [pu] to [Ohm]
            - Conductance and susceptance converted from [pu] to [Siemens]
            - Thermal ratings [MVA]

            Generator Data:
            - Active and reactive power setpoints [MW], [MVAr]
            - Power limits and control modes
            - Generator status and carrier type

            Load Data:
            - Active and reactive power consumption [MW], [MVAr]
            - Load status and bus assignment

            Transformer Data:
            - Impedance values normalized to transformer base [pu]
            - Tap ratios and phase shift angles [degrees]
            - Thermal ratings [MVA]

            Shunt Data:
            - Conductance and susceptance [Siemens]
            - Status and bus assignment
        """
        try:
            # Temporarily silence GRG's print_err
            original_print_err = grgio.print_err
            grgio.print_err = lambda *args, **kwargs: None

            self.parser = parse_psse_case_file(self.engine.case_file)

            # Restore original print_err
            grgio.print_err = original_print_err

            # Validate case
            if not self.parser or not self.parser.buses:
                print("[GRG ERROR] Parsed case is empty or invalid.")
                return False

            self.sbase = self.parser.sbase
            self.network = pypsa.Network(s_n_mva=self.sbase)

        except Exception as e:
            print(f"[GRG ERROR] Failed to parse case: {e}")
            return False

        self.parser.bus_lookup = {bus.i: bus for bus in self.parser.buses}

        # Mapping PSS/E bus types to PyPSA control types
        ide_to_ctrl = {1: "PQ", 2: "PV", 3: "Slack"}

        # --- Add Buses ---
        for bus in self.parser.buses:
            self.network.add(
                "Bus",
                name=str(bus.i),
                v_nom=bus.basekv,  # [kV]
                v_mag_pu_set=bus.vm,  # [pu]
                v_mag_pu_min=bus.nvlo,  # [pu]
                v_mag_pu_max=bus.nvhi,  # [pu]
                control=ide_to_ctrl.get(bus.ide, "PQ"),
            )

        # --- Add Lines (Branches) ---
        for idx, br in enumerate(self.parser.branches):
            line_name = f"L{idx}"
            S_base_MVA = self.parser.sbase
            V_base_kV = self.network.buses.at[str(br.i), "v_nom"]

            # Convert PSS®E p.u. values to physical units
            r_ohm = br.r * (V_base_kV**2) / S_base_MVA
            x_ohm = br.x * (V_base_kV**2) / S_base_MVA
            g_siemens = (br.gi + br.gj) * S_base_MVA / (V_base_kV**2)
            b_siemens = (br.bi + br.bj) * S_base_MVA / (V_base_kV**2)

            self.network.add(
                "Line",
                name=line_name,
                bus0=str(br.i),
                bus1=str(br.j),
                type="",
                r=r_ohm,
                x=x_ohm,
                g=g_siemens,
                b=b_siemens,
                s_nom=br.ratea,
                s_nom_extendable=False,
                length=br.len,
                v_ang_min=-inf,
                v_ang_max=inf,
            )

        # --- Add Generators ---
        for idx, g in enumerate(self.parser.generators):
            if g.stat != 1:
                continue
            gname = f"G{idx}"
            S_base_MVA = self.parser.sbase

            # Control type from IDE (bus type), fallback to "PQ"
            ctrl = ide_to_ctrl.get(self.parser.bus_lookup[g.i].ide, "PQ")

            # Active power limits and nominal power
            p_nom = g.pt  # pt (float): active power output upper bound (MW)
            p_nom_min = g.pb  # pb (float): active power output lower bound (MW)
            p_set = g.pg  # pg (float): active power output (MW)
            p_min_pu = g.pb / g.pt if g.pt != 0 else 0.0  # Avoid div by zero

            # Reactive setpoint
            q_set = g.qg  # qg (float): reactive power output (MVAr)

            # Optional: carrier type (e.g., detect wind)
            carrier = "wind" if getattr(g, "wmod", 0) != 0 else "other"

            self.network.add(
                "Generator",
                name=gname,
                bus=str(g.i),
                control=ctrl,
                p_nom=p_nom,
                p_nom_extendable=False,
                p_nom_min=p_nom_min,
                p_nom_max=p_nom,
                p_min_pu=p_min_pu,
                p_max_pu=1.0,
                p_set=p_set,
                q_set=q_set,
                carrier=carrier,
                efficiency=1.0,  # Default unless you have a better estimate
            )

        # --- Add Loads ---
        for idx, load in enumerate(self.parser.loads):
            if load.status != 1:
                continue  # Skip out-of-service loads

            lname = f"L{idx}"

            self.network.add(
                "Load",
                name=lname,
                bus=str(load.i),
                carrier="AC",  # Default for electrical loads
                p_set=load.pl,
                q_set=load.ql,
            )
        # --- Add Transformers ---
        for idx, tx in enumerate(self.parser.transformers):
            p1 = tx.p1
            p2 = tx.p2
            w1 = tx.w1
            w2 = tx.w2

            # Skip transformer if it's out of service (status not equal to 1 = fully in-service)
            if p1.stat != 1:
                continue

            # Transformer name and buses
            name = f"T{idx}"
            bus0 = str(p1.i)
            bus1 = str(p1.j)

            # Apparent power base (MVA)
            s_nom = w1.rata if w1.rata > 0.0 else p2.sbase12

            # Normalize impedance from sbase12 to s_nom
            r = p2.r12 * (p2.sbase12 / s_nom)
            x = p2.x12 * (p2.sbase12 / s_nom)

            # Optional magnetizing admittance (can be set to 0.0 if not used)
            g = p1.mag1 / s_nom if p1.mag1 != 0.0 else 0.0
            b = p1.mag2 / s_nom if p1.mag2 != 0.0 else 0.0

            # Tap ratio and angle shift
            tap_ratio = w1.windv
            phase_shift = w1.ang
            # --- Add Two-Winding Transformers ---
            self.network.add(
                "Transformer",
                name=name,
                bus0=bus0,
                bus1=bus1,
                type="",  # Use explicit parameters
                model="t",  # PyPSA's physical default
                r=r,
                x=x,
                g=g,
                b=b,
                s_nom=s_nom,
                s_nom_extendable=False,
                num_parallel=1,
                tap_ratio=tap_ratio,
                tap_side=0,
                phase_shift=phase_shift,
                # active      = True,
                v_ang_min=-180,
                v_ang_max=180,
            )

        # --- Add Shunt Impedances ---
        for idx, sh in enumerate(self.parser.switched_shunts):
            if sh.stat != 1:
                continue  # Skip out-of-service shunts

            # For switched shunts, calculate total susceptance from initial + all blocks
            # binit is in MVAr at 1.0 pu voltage on system base
            total_susceptance_mvar = sh.binit

            # Add all switched shunt blocks that are available
            blocks = [
                (sh.n1, sh.b1),
                (sh.n2, sh.b2),
                (sh.n3, sh.b3),
                (sh.n4, sh.b4),
                (sh.n5, sh.b5),
                (sh.n6, sh.b6),
                (sh.n7, sh.b7),
                (sh.n8, sh.b8),
            ]

            # For initial power flow, only use binit (fixed part)
            # Switchable blocks would be controlled during operation
            for n_steps, b_increment in blocks:
                if n_steps is not None and b_increment is not None and n_steps > 0:
                    # Conservative: assume steps are off initially
                    pass

            # Skip shunts with zero susceptance
            if abs(total_susceptance_mvar) < 1e-6:
                continue

            # Convert MVAr to Siemens
            # PSS®E shunt: binit is "MVAr per unit voltage"
            # This means: at 1.0 pu voltage (= V_base_kV), reactive power = binit MVAr
            # Formula: B_siemens = Q_MVAr_at_rated_voltage / V_base_kV^2
            v_base_kv = self.network.buses.at[str(sh.i), "v_nom"]

            # Convert: B = Q / V^2 (Siemens = MVAr / kV^2)
            b_siemens = total_susceptance_mvar / (v_base_kv**2)

            # Additional check for reasonable values
            if abs(b_siemens) > 1000:  # Very large susceptance values
                print(
                    f"[WARNING] Large shunt susceptance at bus {sh.i}: {b_siemens:.6f} S"
                )
                continue

            shunt_name = f"Shunt_{idx}"

            self.network.add(
                "ShuntImpedance",
                name=shunt_name,
                bus=str(sh.i),
                g=0.0,  # Switched shunts typically don't have conductance
                b=b_siemens,
            )
        return 1

    def add_wec_farm(self, farm) -> bool:
        """Add a WEC farm to the PyPSA model.

        This method adds a WEC farm to the PyPSA model by creating the necessary
        electrical infrastructure: a new bus for the WEC farm, a generator on that bus,
        and a transmission line connecting it to the existing grid.

        Args:
            farm (WECFarm): The WEC farm object containing connection details including
                bus_location, connecting_bus, and farm identification.

        Returns:
            bool: True if the farm is added successfully, False otherwise.

        Raises:
            Exception: If the WEC farm cannot be added due to PyPSA errors.

        Notes:
            The WEC farm addition process includes:

            Bus Creation:
            - Creates new bus at farm.bus_location
            - Uses same voltage level as connecting bus [kV]
            - Sets AC carrier type for electrical connection

            Line Creation:
            - Adds transmission line between WEC bus and grid
            - Uses hardcoded impedance values [Ohm]
            - Sets thermal rating [MVA]

            Generator Creation:
            - Adds WEC generator with wave energy carrier type
            - Initial power setpoint of 0.0 [MW]
            - PV control mode for voltage regulation

        TODO:
            Replace hardcoded line impedance values with calculated values
            based on farm specifications and connection distance.
        """
        try:
            self.network.add(
                "Bus",
                name=str(farm.bus_location),
                v_nom=self.network.buses.at[str(farm.connecting_bus), "v_nom"],
                carrier="AC",
            )
            self.network.add(
                "Line",
                name=f"WEC Line {farm.bus_location}",  # todo updat this to follow convention
                bus0=str(farm.bus_location),
                bus1=str(farm.connecting_bus),
                r=0.01,
                x=0.05,
                s_nom=130.00,
            )
            self.network.add(
                "Generator",
                name=f"W{farm.farm_id}",
                bus=str(farm.bus_location),
                carrier="wave",
                p_set=0.0,
                control="PV",
            )
            self.grid = (
                GridState()
            )  # TODO Reset state after adding farm but should be a bette way
            self.grid.software = "pypsa"
            self.grid.case = self.engine.case_name
            self.solve_powerflow()
            self.take_snapshot(
                timestamp=self.engine.time.start_time
            )  # Update grid state

            return True
        except Exception as e:
            print(f"[PyPSA ERROR]: Failed to add WEC Components: {e}")
            return False

    # def simulate(self, load_curve=None) -> bool:
    #     """Simulate the PyPSA grid over time with WEC farm updates.

    #     Simulates the PyPSA grid over a series of time snapshots, updating WEC farm
    #     generator outputs and optionally bus loads at each time step. For each
    #     snapshot, the method updates generator power outputs, applies load changes
    #     if provided, solves the power flow, and captures the grid state.

    #     Args:
    #         load_curve (Optional[pd.DataFrame]): DataFrame containing load values for
    #             each bus at each snapshot. Index should be snapshots (same dtype/order
    #             as self.engine.time.snapshots), columns should be bus IDs. If None,
    #             loads remain constant.

    #     Returns:
    #         bool: True if the simulation completes successfully.

    #     Raises:
    #         Exception: If there is an error setting generator power, setting load data,
    #             or solving the power flow at any snapshot.

    #     Notes:
    #         The simulation process includes:

    #         WEC Generator Updates:
    #         - Updates WEC generator power setpoints [MW]
    #         - Converts from per-unit to MW using system base (self.sbase)
    #         - Uses farm power curve data for each time snapshot

    #         Load Updates (if load_curve provided):
    #         - Updates bus load values [MW]
    #         - Converts from per-unit to MW using system base
    #         - Maps bus numbers to PyPSA load component names

    #         Power Flow Solution:
    #         - Solves power flow at each time step
    #         - Captures grid state snapshots for analysis
    #         - Provides progress indication via tqdm
    #     """
    #     n = self.network
    #     sbase = float(self.sbase)

    #     # ---------- timing ----------
    #     if not hasattr(self, "_timing_data"):
    #         self._timing_data = {
    #             "simulation_total": 0.0,
    #             "iteration_times": [],
    #             "solve_powerflow_times": [],
    #             "take_snapshot_times": [],
    #         }

    #     # ---------- mappings (once) ----------
    #     bus_to_load = {str(bus): name for name, bus in n.loads["bus"].items()}

    #     mapped_cols = []
    #     mapped_load_ids = []
    #     load_row_pos = None
    #     pset_col_pos = None
    #     fast_row_lookup = False
    #     load_curve_np = None

    #     if load_curve is not None and not load_curve.empty:
    #         for col in load_curve.columns:
    #             lid = bus_to_load.get(str(col))
    #             if lid is not None and lid in n.loads.index:
    #                 mapped_cols.append(col)
    #                 mapped_load_ids.append(lid)

    #         if mapped_load_ids:
    #             load_row_pos = n.loads.index.get_indexer(pd.Index(mapped_load_ids))
    #             pset_col_pos = n.loads.columns.get_loc("p_set")

    #             fast_row_lookup = load_curve.index.equals(self.engine.time.snapshots)
    #             if fast_row_lookup:
    #                 load_curve_np = load_curve[mapped_cols].to_numpy(dtype=float, copy=False)

    #     # WEC farms → generator ids
    #     farm_objs = list(self.engine.wec_farms)
    #     farm_gen_ids = [f"W{farm.farm_id}" for farm in farm_objs]
    #     missing = [gid for gid in farm_gen_ids if gid not in n.generators.index]
    #     if missing:
    #         raise ValueError(f"Missing WEC generators in network: {missing}")

    #     # ---------- main loop ----------
    #     t0 = time.perf_counter()
    #     for t_idx, snapshot in enumerate(tqdm(self.engine.time.snapshots, desc="PyPSA Simulating", unit="step")):
    #         step_start = time.perf_counter()

    #         # --- WEC generator p_set (vector) ---
    #         if farm_gen_ids:
    #             p_mw = np.fromiter(
    #                 (farm.power_at_snapshot(snapshot) * sbase for farm in farm_objs),
    #                 dtype=float,
    #                 count=len(farm_objs),
    #             )
    #             n.generators.loc[farm_gen_ids, "p_set"] = p_mw

    #         # --- Loads p_set (vector) ---
    #         if mapped_cols:
    #             if fast_row_lookup:
    #                 row = load_curve_np[t_idx] * sbase
    #             else:
    #                 row = load_curve.loc[snapshot, mapped_cols].to_numpy(dtype=float, copy=False) * sbase
    #             n.loads.iloc[load_row_pos, pset_col_pos] = row

    #         # --- solve PF + snapshot timing ---
    #         pf_start = time.perf_counter()
    #         ok = self.solve_powerflow()
    #         pf_end = time.perf_counter()
    #         if not ok:
    #             raise Exception(f"Powerflow failed at snapshot {snapshot}")
    #         self._timing_data["solve_powerflow_times"].append(pf_end - pf_start)

    #         snap_start = time.perf_counter()
    #         self.take_snapshot(timestamp=snapshot)
    #         snap_end = time.perf_counter()
    #         self._timing_data["take_snapshot_times"].append(snap_end - snap_start)

    #         step_end = time.perf_counter()
    #         self._timing_data["iteration_times"].append(step_end - step_start)

    #     self._timing_data["simulation_total"] = time.perf_counter() - t0
    #     return True

    def simulate(self, load_curve=None) -> bool:
        """Simulate the PyPSA grid over time with WEC farm updates.

        Args:
            load_curve (Optional[pd.DataFrame]): DataFrame containing load values for
                each bus at each snapshot. Index should be snapshots, columns should
                be bus IDs. If None, loads remain constant.

        Returns:
            bool: True if the simulation completes successfully.
        """

        # Create clean bus-to-load mapping
        bus_to_load = {}
        for load_idx, bus_num in self.network.loads["bus"].items():
            bus_to_load[str(bus_num)] = load_idx

        # Map WEC farms to their generator names
        wec_generators = {}
        available_gens = list(self.network.generators.index)

        for farm in self.engine.wec_farms:
            # Try common WEC generator naming patterns
            possible_names = [f"W{farm.farm_id}", f"WEC_{farm.farm_id}", farm.farm_name]
            gen_name = next(
                (name for name in possible_names if name in available_gens), None
            )

            if gen_name is None:
                print(f"Error: WEC generator for farm {farm.farm_id} not found")
                return False

            wec_generators[farm.farm_id] = gen_name

        # Main simulation loop
        sim_start = time.time()

        for snapshot in tqdm(
            self.engine.time.snapshots, desc="PyPSA Simulating", unit="step"
        ):
            self.report.add_snapshot(snapshot)
            iter_start = time.time()

            # Update WEC generators
            for farm in self.engine.wec_farms:
                gen_name = wec_generators[farm.farm_id]
                power_pu = farm.power_at_snapshot(snapshot)
                power_mw = power_pu * self.sbase  # Convert pu -> MW
                # print(f"{farm.farm_name}: Seting {gen_name} - {power_mw} MW")
                self.network.generators.at[gen_name, "p_set"] = power_mw

            # Update loads if provided
            if load_curve is not None and snapshot in load_curve.index:
                for bus_str in load_curve.columns:
                    if str(bus_str) in bus_to_load:
                        load_name = bus_to_load[str(bus_str)]
                        load_pu = load_curve.loc[snapshot, bus_str]
                        if not pd.isna(load_pu):
                            load_mw = float(load_pu) * self.sbase
                            self.network.loads.at[load_name, "p_set"] = load_mw

            # Solve power flow
            results = self.solve_powerflow(log=True)
            if results:
                snap_start = time.time()
                self.take_snapshot(timestamp=snapshot)
                self.report.add_snapshot_data(time.time() - snap_start)
            else:
                raise Exception(f"Powerflow failed at snapshot {snapshot}")

            self.report.add_iteration_time(time.time() - iter_start)

        # log simulation end
        self.report.simulation_time = time.time() - sim_start
        return True

    def take_snapshot(self, timestamp: datetime) -> None:
        """Take a snapshot of the current grid state.

        Captures the current state of all grid components (buses, generators, lines,
        and loads) at the specified timestamp and updates the grid state object.

        Args:
            timestamp (datetime): The timestamp for the snapshot.

        Returns:
            None

        Note:
            This method calls individual snapshot methods for each component type
            and updates the internal grid state with time-series data.
        """
        self.grid.update("bus", timestamp, self.snapshot_buses())
        self.grid.update("gen", timestamp, self.snapshot_generators())
        self.grid.update("line", timestamp, self.snapshot_lines())
        self.grid.update("load", timestamp, self.snapshot_loads())

    def snapshot_buses(self) -> pd.DataFrame:
        """Capture current bus state from PyPSA.

        Returns:
            DataFrame with columns: bus, bus_name, type, p, q, v_mag,
            angle_deg, vbase.
        """
        n = self.network
        buses = n.buses  # index = bus names (strings)

        # choose the latest snapshot (or change to a passed-in timestamp)
        if len(n.snapshots) > 0:
            ts = n.snapshots[-1]
            p_MW = (
                getattr(n.buses_t, "p", pd.DataFrame())
                .reindex(index=[ts], columns=buses.index)
                .iloc[0]
                .fillna(0.0)
            )
            q_MVAr = (
                getattr(n.buses_t, "q", pd.DataFrame())
                .reindex(index=[ts], columns=buses.index)
                .iloc[0]
                .fillna(0.0)
            )
            vmag_pu = (
                getattr(n.buses_t, "v_mag_pu", pd.DataFrame())
                .reindex(index=[ts], columns=buses.index)
                .iloc[0]
                .fillna(1.0)
            )
            vang_rad = (
                getattr(n.buses_t, "v_ang", pd.DataFrame())
                .reindex(index=[ts], columns=buses.index)
                .iloc[0]
                .fillna(0.0)
            )
        else:
            # no time series yet
            idx = buses.index
            p_MW = pd.Series(0.0, index=idx)
            q_MVAr = pd.Series(0.0, index=idx)
            vmag_pu = pd.Series(1.0, index=idx)
            vang_rad = pd.Series(0.0, index=idx)

        df = pd.DataFrame(
            {
                "bus": buses.index.astype(int),
                "bus_name": [f"Bus_{int(bus_id)}" for bus_id in buses.index],
                "type": buses.get("control", pd.Series("PQ", index=buses.index)).fillna(
                    "PQ"
                ),
                "p": (p_MW / self.sbase).astype(float),
                "q": (q_MVAr / self.sbase).astype(float),
                "v_mag": vmag_pu.astype(float),
                "angle_deg": np.degrees(vang_rad.astype(float)),
                "vbase": buses.get(
                    "v_nom", pd.Series(np.nan, index=buses.index)
                ).astype(float),
            }
        )

        df.attrs["df_type"] = "BUS"
        df.index = pd.RangeIndex(start=0, stop=len(df))
        return df

    def snapshot_generators(self) -> pd.DataFrame:
        """Capture current generator state from PyPSA.

        Returns:
            DataFrame with columns: gen, gen_name, bus, p, q, Mbase, status.
        """

        n = self.network
        gens = n.generators
        sbase = self.sbase

        if len(n.snapshots) > 0:
            ts = n.snapshots[-1]
            p_MW = (
                getattr(n.generators_t, "p", pd.DataFrame())
                .reindex(index=[ts], columns=gens.index)
                .iloc[0]
                .fillna(0.0)
            )
            q_MVAr = (
                getattr(n.generators_t, "q", pd.DataFrame())
                .reindex(index=[ts], columns=gens.index)
                .iloc[0]
                .fillna(0.0)
            )
            stat = (
                getattr(n.generators_t, "status", pd.DataFrame())
                .reindex(index=[ts], columns=gens.index)
                .iloc[0]
            )
            if stat.isna().all() and "active" in gens.columns:
                stat = gens["active"].astype(int).reindex(gens.index).fillna(1)
            else:
                stat = stat.fillna(1).astype(int)
        else:
            idx = gens.index
            p_MW = pd.Series(0.0, index=idx)
            q_MVAr = pd.Series(0.0, index=idx)
            stat = pd.Series(1, index=idx, dtype=int)

        # Counter per bus for naming

        bus_nums = []
        gen_ids = []
        gen_names = []

        for i, bus in enumerate(gens["bus"]):
            try:
                bus_num = int(bus)
            except Exception:
                bus_num = bus
            bus_nums.append(bus_num)
            gen_ids.append(i + 1)
            gen_names.append(f"Gen_{i+1}")

        df = pd.DataFrame(
            {
                "gen": gen_ids,
                "gen_name": gen_names,
                "bus": bus_nums,
                "p": (p_MW / sbase).astype(float),
                "q": (q_MVAr / sbase).astype(float),
                "Mbase": 0.0,  # MBASE not avaiable
                "status": stat.astype(int),
            }
        )

        df.attrs["df_type"] = "GEN"
        df.index = pd.RangeIndex(start=0, stop=len(df))
        return df

    def snapshot_lines(self) -> pd.DataFrame:
        """Capture current transmission line state from PyPSA.

        Builds a Pandas DataFrame of the current transmission line state for the loaded
        PyPSA network. The DataFrame includes line loading percentages and connection
        information.

        Returns:
            pd.DataFrame: DataFrame with columns: line, ibus, jbus, line_pct, status.
                Line names are formatted as "Line_ibus_jbus_count".

        Notes:
            The following PyPSA network data is used to create line snapshots:

            Line Information:
            - Line bus connections (bus0, bus1) [dimensionless]
            - Line thermal ratings (s_nom) [MVA]
            - Line status (assumed active = 1)

            Power Flow Data:
            - Active power flow at both ends [MW]
            - Reactive power flow at both ends [MVAr]
            - Apparent power calculated from P and Q [MVA]
            - Line loading as percentage of thermal rating [%]

            Naming Convention:
            - Lines named as "Line_ibus_jbus_count" for consistency
            - Per-bus-pair counter for multiple parallel lines
            - Bus numbers converted from PyPSA string indices
        """

        n = self.network

        # choose latest snapshot if available
        if len(n.snapshots) > 0:
            ts = n.snapshots[-1]
            p0 = (
                getattr(n.lines_t, "p0", pd.DataFrame())
                .reindex(index=[ts], columns=n.lines.index)
                .iloc[0]
                .fillna(0.0)
            )
            q0 = (
                getattr(n.lines_t, "q0", pd.DataFrame())
                .reindex(index=[ts], columns=n.lines.index)
                .iloc[0]
                .fillna(0.0)
            )
            p1 = (
                getattr(n.lines_t, "p1", pd.DataFrame())
                .reindex(index=[ts], columns=n.lines.index)
                .iloc[0]
                .fillna(0.0)
            )
            q1 = (
                getattr(n.lines_t, "q1", pd.DataFrame())
                .reindex(index=[ts], columns=n.lines.index)
                .iloc[0]
                .fillna(0.0)
            )
        else:
            # no time series → assume zero flow
            idx = n.lines.index
            p0 = pd.Series(0.0, index=idx)
            q0 = pd.Series(0.0, index=idx)
            p1 = pd.Series(0.0, index=idx)
            q1 = pd.Series(0.0, index=idx)

        rows = []

        for i, (line_name, line) in enumerate(n.lines.iterrows()):
            ibus_name, jbus_name = line.bus0, line.bus1

            ibus = int(ibus_name)
            jbus = int(jbus_name)

            line_id = i + 1

            # apparent power (MVA) at each end
            S0 = np.hypot(p0[line_name], q0[line_name])
            S1 = np.hypot(p1[line_name], q1[line_name])
            Smax = max(S0, S1)

            s_nom = float(line.s_nom) if pd.notna(line.s_nom) else np.nan
            line_pct = float(100.0 * Smax / s_nom) if s_nom and s_nom > 0 else np.nan

            rows.append(
                {
                    "line": line_id,
                    "line_name": f"Line_{line_id}",
                    "ibus": ibus,
                    "jbus": jbus,
                    "line_pct": line_pct,  # % of s_nom at latest snapshot
                    "status": 1,  # hard coded
                }
            )

        df = pd.DataFrame(rows)
        df.attrs["df_type"] = "LINE"
        df.index = pd.RangeIndex(start=0, stop=len(df))
        return df

    def snapshot_loads(self) -> pd.DataFrame:
        """Capture current load state from PyPSA.

        Returns:
            DataFrame with columns: load, load_name, bus, p, q, status.
        """
        n = self.network
        sbase = float(self.sbase)

        # latest snapshot values (MW / MVAr)
        if len(n.snapshots) and hasattr(n.loads_t, "p") and hasattr(n.loads_t, "q"):
            ts = n.snapshots[-1]
            p_MW = (
                n.loads_t.p.reindex(index=[ts], columns=n.loads.index)
                .iloc[0]
                .fillna(0.0)
            )
            q_MVAr = (
                n.loads_t.q.reindex(index=[ts], columns=n.loads.index)
                .iloc[0]
                .fillna(0.0)
            )
        else:
            idx = n.loads.index
            p_MW = pd.Series(0.0, index=idx)
            q_MVAr = pd.Series(0.0, index=idx)

        # status: use 'active' if present, else assume in-service
        has_active = "active" in getattr(n.loads, "columns", [])
        status_series = (
            n.loads["active"].astype(bool)
            if has_active
            else pd.Series(True, index=n.loads.index)
        )

        rows = []
        count = 1
        for load_name, rec in n.loads.iterrows():
            bus = int(rec.bus)

            rows.append(
                {
                    "load": count,
                    "load_name": f"Load_{count}",
                    "bus": bus,
                    "p": float(p_MW.get(load_name, 0.0)) / sbase,
                    "q": float(q_MVAr.get(load_name, 0.0)) / sbase,
                    "status": 1 if bool(status_series.get(load_name, True)) else 0,
                }
            )
            count += 1

        df = pd.DataFrame(rows)
        df.attrs["df_type"] = "LOAD"
        df.index = pd.RangeIndex(start=0, stop=len(df))
        return df
