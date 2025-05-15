"""
PyPSA Wrapper Module

This module provides a wrapper class for PyPSA (Python for Power System Analysis) functionality,
specifically designed for Wave Energy Converter (WEC) integration into power systems.

Classes:
    pyPSAWrapper: Main class for managing PyPSA network operations with WEC integration
"""

# Standard Libraries
import os
import sys
from datetime import datetime, timezone, timedelta
import contextlib
import io
import logging
import io
import contextlib

# 3rd Party Libraries
import pypsa
import pandas as pd
import cmath
import numpy as np
import matlab.engine
import pypower.api as pypower
from pandas.tseries.offsets import DateOffset
from math import inf

import grg_pssedata.io as grgio
from grg_pssedata.io import parse_psse_case_file

# Local Libraries (updated with relative imports)
#from ..utilities.util import read_paths  # Relative import for utilities/util.py
from ..viz.pypsa_viz import PyPSAVisualizer

# # Initialize the PATHS dictionary
# PATHS = read_paths()
# CURR_DIR = os.path.dirname(os.path.abspath(__file__))


class PYPSAInterface:
    """
    A wrapper class for PyPSA network operations with WEC integration.

    This class provides methods for initializing, modifying, and analyzing power systems
    with integrated Wave Energy Converters using PyPSA.

    Attributes:
        case_file (str): Path to the case file
        pypsa_history (dict): History of PyPSA operations
        pypsa_object_history (dict): History of PyPSA objects
        dataframe (pd.DataFrame): Current network state
        flow_data (dict): Power flow data
        WecGridCore (object): Parent WecGridCore reference
        timestamp_start (datetime): Initialization timestamp
    """

    def __init__(self, case : str, engine: "WecGridEngine"):
        """
        Initialize PyPSA wrapper.

        Args:
            case (str): Path to case file
            WecGridCore (object): Reference to parent WecGridCore object

        Returns:
            None
        """
        self.case_file = case
        self.engine = engine
        
        #Grid dfs
        self.bus_dataframe = pd.DataFrame()
        self.generator_dataframe = pd.DataFrame()
        self.branches_dataframe = pd.DataFrame()
        self.loads_dataframe = pd.DataFrame()
        self.two_winding_dataframe = pd.DataFrame()
        self.three_winding_dataframe = pd.DataFrame()
        
        
        # Wrapper 
        self.snapshots = engine.snapshots
        self.snapshot_history = []
        self.load_profiles = pd.DataFrame()
        self.viz = PyPSAVisualizer(self)
        self.parser = None
        
        
        
        # API objects
        self.network = None
        
    def init_api(self)-> bool:
        if self.import_raw_to_pypsa():
            if self.pf():
                print("PyPSA software initialized")
                return True
        else:
            print("Failed to initialize pyPSA network.")
            return False
     
    def import_raw_to_pypsa(self) -> bool:
        """
        Builds a PyPSA Network from a parsed PSS/E RAW case file.
        Only sets necessary fields for a valid power flow.
        """
        try:
            # Temporarily silence GRG's print_err
            original_print_err = grgio.print_err
            grgio.print_err = lambda *args, **kwargs: None

            self.parser = parse_psse_case_file(self.case_file)
            
    
            # Restore original print_err
            grgio.print_err = original_print_err

            # Validate case
            if not self.parser or not self.parser.buses:
                print("[GRG ERROR] Parsed case is empty or invalid.")
                return False

            self.network = pypsa.Network(s_n_mva=self.parser.sbase)

        except Exception as e:
            print(f"[GRG ERROR] Failed to parse case: {e}")
            return False
        
        self.parser.bus_lookup = {bus.i: bus for bus in self.parser.buses}

        # Mapping PSS/E bus types to PyPSA control types
        ide_to_ctrl = {1: "PQ", 2: "PV", 3: "Slack"}

        # --- Add Buses ---
        for bus in self.parser.buses:
            self.network.add("Bus",
                name          = str(bus.i),
                v_nom         = bus.basekv,        # [kV]
                v_mag_pu_set  = bus.vm,             # [pu]
                v_mag_pu_min  = bus.nvlo,           # [pu]
                v_mag_pu_max  = bus.nvhi,           # [pu]
                control       = ide_to_ctrl.get(bus.ide, "PQ"),
            )

        # --- Add Lines (Branches) ---
        for idx, br in enumerate(self.parser.branches):
            line_name = f"L{idx}"
            S_base_MVA = self.parser.sbase
            V_base_kV = self.network.buses.at[str(br.i), "v_nom"]
        
            # Convert PSS®E p.u. values to physical units
            r_ohm = br.r * (V_base_kV ** 2) / S_base_MVA
            x_ohm = br.x * (V_base_kV ** 2) / S_base_MVA
            g_siemens = (br.gi + br.gj) * S_base_MVA / (V_base_kV ** 2)
            b_siemens = (br.bi + br.bj) * S_base_MVA / (V_base_kV ** 2)

            self.network.add("Line",
                name    = line_name,
                bus0    = str(br.i),
                bus1    = str(br.j),
                type    = "",
                r       = r_ohm,
                x       = x_ohm,
                g       = g_siemens,
                b       = b_siemens,
                s_nom   = br.ratea,
                s_nom_extendable = False,
                length  = 0.0,
                v_ang_min = -inf,
                v_ang_max = inf,
            )
            # print(f"Line {line_name}:")
            # print(f" bus0 : {str(br.i)} - bus1: {str(br.j)}")
            # print(f"  Original values (p.u.): r={br.r}, x={br.x}, g={br.gi + br.gj}, b={br.bi + br.bj}")
            # print(f"  Converted values (physical units): r_ohm={r_ohm:.6f}, x_ohm={x_ohm:.6f}, g_siemens={g_siemens:.6f}, b_siemens={b_siemens:.6f}")
            
            
        # --- Add Generators ---
        for idx, g in enumerate(self.parser.generators):
            if g.stat != 1:
                continue
            gname = f"G{idx}"
            S_base_MVA = self.parser.sbase

            # Control type from IDE (bus type), fallback to "PQ"
            ctrl = ide_to_ctrl.get(self.parser.bus_lookup[g.i].ide, "PQ")

            # Active power limits and nominal power
            p_nom = g.pt
            p_nom_min = g.pb
            p_set = g.pg
            p_min_pu = g.pb / g.pt if g.pt != 0 else 0.0  # Avoid div by zero

            # Reactive setpoint
            q_set = g.qg

            # Optional: carrier type (e.g., detect wind)
            carrier = "wind" if getattr(g, "wmod", 0) != 0 else "other"

            self.network.add("Generator",
                name       = gname,
                bus        = str(g.i),
                control    = ctrl,
                p_nom      = p_nom,
                p_nom_extendable = False,
                p_nom_min  = p_nom_min,
                p_nom_max  = p_nom,
                p_min_pu   = p_min_pu,
                p_max_pu   = 1.0,
                p_set      = p_set,
                q_set      = q_set,
                carrier    = carrier,
                #active     = in_service,
                efficiency = 1.0,  # Default unless you have a better estimate
            )
            

        # --- Add Loads ---
        for idx, load in enumerate(self.parser.loads):
            if load.status != 1:
                continue  # Skip out-of-service loads

            lname = f"L{idx}"

            self.network.add("Load",
                name   = lname,
                bus    = str(load.i),
                carrier = "AC",        # Default for electrical loads
                p_set  = load.pl,
                q_set  = load.ql,
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

            self.network.add("Transformer",
                name        = name,
                bus0        = bus0,
                bus1        = bus1,
                type        = "",         # Use explicit parameters
                model       = "t",        # PyPSA's physical default
                r           = r,
                x           = x,
                g           = g,
                b           = b,
                s_nom       = s_nom,
                s_nom_extendable = False,
                num_parallel = 1,
                tap_ratio   = tap_ratio,
                tap_side    = 0,
                phase_shift = phase_shift,
                #active      = True,
                v_ang_min   = -180,
                v_ang_max   = 180,
            )
           # --- Add Two-Winding Transformers ---     

        # --- Add Shunt Impedances ---
        for idx, sh in enumerate(self.parser.switched_shunts):
            if sh.status != 1:
                continue  # Skip out-of-service shunts

            v_nom = self.network.buses.at[str(sh.i), "v_nom"]  # in kV
            v_sq = v_nom ** 2

            g_siemens = sh.gl / v_sq  # MW / kV^2 → Siemens
            b_siemens = sh.bl / v_sq  # MVAr / kV^2 → Siemens

            shunt_name = f"Shunt_{idx}"

            self.network.add("ShuntImpedance",
                name = shunt_name,
                bus  = str(sh.i),
                g    = g_siemens,
                b    = b_siemens,
                active = True,
            )
        return 1

    def pf(self) -> bool:
        """
        Runs power flow silently and checks for convergence.
        """
        try:
            # Suppress PyPSA logging
            logger = logging.getLogger("pypsa")
            previous_level = logger.level
            logger.setLevel(logging.WARNING)

            # Optional: suppress stdout too, just in case
            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                results = self.network.pf()

            # Restore logging level
            logger.setLevel(previous_level)

        except Exception as e:
            print("[PyPSA ERROR]:", str(e))
            return False

        # Check convergence
        if not results.converged.all().bool():
            print("[PyPSA WARNING]: Some snapshots failed to converge.")
            failed = results.converged[~results.converged[0]].index.tolist()
            print("Non-converged snapshots:", failed)
            return False

        # Update internal dataframes
        self.bus_dataframe = self.network.buses.copy()
        self.generator_dataframe = self.network.generators.copy()
        self.branches_dataframe = self.network.lines.copy()
        return True
        
    def add_wec(self, model: str, ibus: int, jbus: int, p_nom=5.0, bus_voltage_kv=34.5,line_r_pu=0.01, line_x_pu=0.05) -> bool:
        try:
            # add Bus
            self.network.add("Bus",
                name=str(ibus),
                v_nom=self.network.buses.at[str(jbus), "v_nom"],
                carrier="AC",
            )
            # did this work? 
            # if not return false
            
            # Add branch
            # V_nom_V = self.network.buses.at[str(ibus), "v_nom"] * 1e3
            # S_base_VA = self.network.s_n_mva * 1e6
            # Z_base = V_nom_V**2 / S_base_VA

            self.network.add("Line",
                name="WEC Line",
                bus0=str(ibus),
                bus1=str(jbus),
                r=7.875648,
                x=28.784447,
                s_nom=130.00,  # scale line nominal power
            )
            
            # add generator
            for i, wec in enumerate(self.engine.wecObj_list):
                wec.gen_id = f"W{i}"
                wec.gen_name = f"{wec.gen_id}-{wec.model}-{wec.ID}"
                self.network.add("Generator",
                    name=str(wec.gen_id),
                    bus=str(ibus),
                    carrier="wave",
                    p_nom=0.03,
                    # p_nom_min = self.network.generators.query(f"bus == '{jbus}'")["p_nom_min"][0],
                    # p_nom_max = self.network.generators.query(f"bus == '{jbus}'")["p_nom_max"][0],
                    # p_min_pu = self.network.generators.query(f"bus == '{jbus}'")["p_min_pu"][0],
                    # p_max_pu = self.network.generators.query(f"bus == '{jbus}'")["p_max_pu"][0],
                    p_nom_min = 0.0,
                    p_nom_max = 0.03,
                    p_min_pu = 0.0,
                    p_max_pu = 1.0,
                    p_set=0.001,
                    control="PV",
                    efficiency=1.0,
                )
            
            self.pf()
            return True
        except Exception as e:
            print(f"[PyPSA ERROR]: Failed to add WEC Components: {e}")
            return False

    # def generate_load_curve(self):
    #     """
    #     Generate a double-peaking load profile for each load in the PyPSA network.

    #     Applies a morning and evening peak profile across a 24-hour period,
    #     scaled by each load's base demand. The output is assigned to
    #     self.load_profiles as a DataFrame indexed by snapshots.
    #     """
    #     import numpy as np
    #     import pandas as pd

    #     # Get base load values
    #     base_loads = self.network.loads["p_set"]

    #     # Extract time-of-day from snapshots
    #     times = self.snapshots
    #     hours = pd.to_datetime(times).hour + pd.to_datetime(times).minute / 60.0

    #     # Create a double-peaking profile: one at 8 AM and one at 6 PM
    #     def double_peak(hour):
    #         # Gaussian-like bumps centered at 8 and 18
    #         morning_peak = np.exp(-0.5 * ((hour - 8) / 2) ** 2)
    #         evening_peak = np.exp(-0.5 * ((hour - 18) / 2) ** 2)
    #         return 0.5 + 0.5 * (morning_peak + evening_peak)  # normalize to ~[0.5, 1.5]

    #     shape = double_peak(hours)

    #     # Build the load profile DataFrame
    #     load_profiles = pd.DataFrame(index=self.snapshots)

    #     for load_id, base in base_loads.items():
    #         if base == 0:
    #             continue
    #         load_profiles[load_id] = base * shape

    #     self.load_profiles = load_profiles
            

    def simulate(self, snapshots=None, sim_length=None, load_curve=False, plot=True)->bool:

        p_set_data = {}
        # Iterate over all WEC objects to gather data
        for idx, wec in enumerate(self.engine.wecObj_list):
            '''
            This is assuming the WEC output is in kW, so we convert it to MW. 
            0.016 from wec-sim is = 16kW, so we divide by 1000 to get MW.
            '''
            pg_data = wec.dataframe["pg"]
            p_set_data[wec.gen_id] = pg_data.to_list()
        
        
        self.network.set_snapshots(self.snapshots) 
        self.network.generators_t.p_set = pd.DataFrame(p_set_data, index=self.snapshots)
        if load_curve:
            if self.load_profiles is None or self.load_profiles.empty:
                self.engine.generate_load_profiles()
            self.network.loads_t.p_set = self.load_profiles.copy()
        
        self.pf()
        
        if plot:
            self.viz.plot_all()
        return True
    

    
    # def simulate(self, snapshots=None, sim_length=None, load_curve=False, plot=True) -> bool:
    #     # Determine snapshots if not provided
    #     if snapshots is None:
    #         num_snapshots = len(self.engine.wecObj_list[0].dataframe["pg"])
    #         snapshots = pd.date_range(
    #             start=self.engine.start_time,
    #             periods=num_snapshots,
    #             freq="5T",
    #         )
    #         self.snapshots = snapshots

    #     # Set PyPSA snapshots
    #     self.network.set_snapshots(self.snapshots)

    #     # Time-varying p_max_pu per WEC generator
    #     p_max_pu_data = {}

    #     for wec in self.engine.wecObj_list:
    #         pg_mw = wec.dataframe["pg"]  # in MW (e.g., 0.016 for 16 kW)
    #         #p_nom = self.network.generators.at[wec.gen_name, "p_nom"]
    #         p_nom = 0.03

    #         # Normalize time series to p_nom to get per-unit curve
    #         p_max_pu_data[wec.gen_name] = (pg_mw / p_nom).clip(upper=1.0)

    #     # Assign per-unit availability
    #     self.network.generators_t.p_max_pu = pd.DataFrame(p_max_pu_data, index=self.snapshots)

    #     # (Optional) clear p_set to allow PyPSA to dispatch freely
    #     #self.network.generators_t.p_set = pd.DataFrame(index=self.snapshots)

    #     # Run power flow or optimization
    #     return self.pf()
            







    # def add_wec(self, model, from_bus, to_bus):
    # # def add_wec(self, model, ID, from_bus, to_bus):
    #     """
    #     Add Wave Energy Converter to network.

    #     Args:
    #         model (str): WEC model name
    #         ID (str): Unique WEC identifier
    #         from_bus (str): Source bus ID
    #         to_bus (str): Target bus ID

    #     Returns:
    #         None

    #     Notes:
    #         - Creates new bus if to_bus doesn't exist
    #         - Uses hardcoded line parameters (length=10, r=0.05, x=0.15)
    #     """

    #     name = f"{model}-{to_bus}"
        
    #     '''
    #     v_nom - kV 
        
    #     '''
    #     print("Adding WECs to pyPSA network")

    #     # Step 1: Add a new bus for the WEC system
    #     if str(to_bus) not in self.pypsa_object.buses.index:
    #         from_bus_voltage = self.pypsa_object.buses.loc[str(from_bus), "v_nom"]
    #         self.pypsa_object.add(
    #             "Bus",
    #             str(to_bus),
    #             v_nom=from_bus_voltage,  # Match from_bus voltage
    #             control="PV",  # WEC operates as a PV generator
    #             carrier="AC",  # Standard AC grid connection
    #             v_mag_pu_set=1.0,  # Set voltage at 1.0 p.u.
    #             v_mag_pu_min=0.95,  # Min voltage in p.u.
    #             v_mag_pu_max=1.05,  # Max voltage in p.u.
    #             p=0.0,
    #             q=0.0,
    #             v_ang=0.0,
    #         )
    #         print(f"Bus {to_bus} added successfully.")

    #     for i, wec_obj in enumerate(self.WecGridCore.wecObj_list):
    #         wec_obj.gen_id = f'G{i+1}' # this might not be needed
    #         name = f"{wec_obj.gen_id}-{wec_obj.model}-{wec_obj.ID}"
    #         self.pypsa_object.add(
    #             "Generator",
    #             name=name,
    #             bus=str(to_bus),
    #             control="PV",  # WEC operates as a PV generator
    #             p_nom_max=1.2,  # Maximum active power output (MW)
    #             p_set=0.0,
    #             p_nom_extendable=False,  # Fixed capacity, not expandable
    #             p_min_pu=0.0,  # No negative generation
    #             # p_min = 0.0,  # Minimum active power output (MW)
    #             # q_max = 0.0,
    #             # q_min = 0.0,
    #             # v_set_pu = 1.0,
    #             # mva_base = 1.0, # TODO: update this later
    #             #type="WEC",  # Type of generator
    #             #carrier="wind" # wind for now, should try solar or new carrier for WEC
                
    #             # sign=1 # power sign - probably should double check this
    #         )
    #         print(f"Generator {name} added successfully to bus {to_bus}.")

    #     self.pypsa_object.add(
    #         "Line",
    #         "Line-{}".format(name),
    #         bus0=str(from_bus),
    #         bus1=str(to_bus),
    #         length=10,
    #         r=0.05,
    #         x=0.15,
    #     )
    #     print(f"Branch from {from_bus} to {to_bus} added successfully.")
        
    #     # TODO: need to fix this hardcoded line length, r, x values

    #     self.pypsa_object.pf()
    #     self.dataframe = self.pypsa_object.df("Bus").copy()
    #     self.format_df()
    #     self.store_p_flow()
        
    #     print("pyPSA network updated with WECs \n")
    #     # Define a function to classify the generator types

    # def classify_generator(self, control):
    #     """
    #     Classify generator type based on control mode.

    #     Args:
    #         control (str): Generator control type ("Slack", "PV", "PQ", "WEC")

    #     Returns:
    #         int: Generator type code (0-4)
    #         - 3: Slack bus
    #         - 2: PV bus
    #         - 1: PQ bus
    #         - 4: WEC
    #         - 0: Other
    #     """
    #     if control == "Slack":
    #         return 3  # Type 3

    #     elif control == "PV":
    #         return 2

    #     elif control == "PQ":
    #         return 1

    #     elif control == "WEC":
    #         return 4
    #     else:
    #         return 0

    # def format_df(self):
    #     """
    #     Format network data for each snapshot.

    #     Creates a formatted DataFrame containing bus variables and generator types
    #     for each network snapshot. Updates bus types for WEC generators.

    #     Variables collected:
    #         - v_mag_pu_set: Voltage magnitude setpoint (per unit)
    #         - p: Active power
    #         - q: Reactive power
    #         - v_mag_pu: Actual voltage magnitude (per unit)
    #         - v_ang: Voltage angle

    #     Returns:
    #         None

    #     Notes:
    #         Updates self.pypsa_history with formatted data for each snapshot
    #     """

    #     snapshots = self.get_snapshots()
    #     # Specify the bus variables to collect
    #     variables = ["v_mag_pu_set", "p", "q", "v_mag_pu", "v_ang"]

    #     # Loop over each snapshot
    #     for snapshot in snapshots:
    #         # Initialize a DataFrame to store data for this snapshot
    #         snapshot_data = pd.DataFrame()

    #         # Loop over the variables and collect the data
    #         for var in variables:
    #             if var in self.pypsa_object.buses_t:
    #                 # Add the variable data as a column in the DataFrame
    #                 snapshot_data[var] = self.pypsa_object.buses_t[var].loc[snapshot]

    #         # combine snapshot_data to have control, generator
    #         bus_static_data = self.pypsa_object.df("Bus")[["control", "generator"]]
    #         merged_data = pd.merge(
    #             snapshot_data, bus_static_data.copy(), on="Bus", how="left"
    #         )

    #         merged_data["type"] = merged_data["control"].apply(self.classify_generator)

    #         # Add the snapshot data to the history dictionary

    #         # update WEC bus type

    #         for wec in self.WecGridCore.wecObj_list:
    #             name = "{}-{}".format(wec.model, wec.ID)
    #             merged_data.loc[merged_data["generator"] == str(name), "type"] = 4

    #         self.pypsa_history[snapshot] = merged_data.reset_index()

    #         # update WEC bus type

    # def ac_injection(self, snapshots=None):
    #     """
    #     Perform AC power injection simulation for WEC generators.

    #     This version builds a full generators_t.p_set time series
    #     so that each WEC really holds its own output, and the slack
    #     bus only makes up the small residual.
    #     """
    #     net = self.pypsa_object

    #     # 1) build or re‐use snapshots
    #     if snapshots is None:
    #         N = len(self.WecGridCore.wecObj_list[0].dataframe["pg"])
    #         snapshots = pd.date_range(
    #             start=self.timestamp_start + DateOffset(minutes=5),
    #             periods=N, freq="5T")
    #     net.set_snapshots(snapshots)

    #     # 2) initialize an all‐zero DataFrame for every generator
    #     p_set = pd.DataFrame(
    #         0.0,
    #         index=net.snapshots,
    #         columns=net.generators.index
    #     )

    #     # 3) fill in each WEC’s column with its pg curve (kW→MW)
    #     for wec in self.WecGridCore.wecObj_list:
    #         bus = str(wec.bus_location)
    #         # find the PV‐machine you attached at that bus
    #         gens = net.generators.query("bus == @bus and control == 'PV'").index
    #         curve_mw = wec.dataframe["pg"].values / 1000.0
    #         for g in gens:
    #             p_set[g] = curve_mw

    #     # 4) hand the completed time series to PyPSA
    #     net.generators_t["p_set"] = p_set

    #     # 5) build your load profile similarly...
    #     self.generate_load_curve(time=snapshots)
    #     net.loads_t["p_set"] = self.load_profiles

    #     # 6) solve all snapshots
    #     net.pf()

    #     # 7) record results
    #     self.format_df()
    #     self.store_p_flow()




    # def viz(self, dataframe=None):
    #     """
    #     Visualize network using PyPSAVisualizer.

    #     Args:
    #         dataframe (pd.DataFrame, optional): Custom data for visualization.
    #             If None, uses default network state.

    #     Returns:
    #         matplotlib.figure.Figure: Network visualization plot
    #     """

    #     visualizer = PyPSAVisualizer(pypsa_obj=self)  # need to pass this object itself?
    #     return visualizer.viz()

    # def store_p_flow(self):
    #     """
    #     Store active power flows for network components.

    #     Records p0 (active power flow) values for all lines and transformers
    #     at each network snapshot.

    #     Data Structure:
    #         self.flow_data = {
    #             timestamp: {
    #                 (source_bus, target_bus): power_flow_value,
    #                 ...
    #             }
    #         }

    #     Returns:
    #         None

    #     Raises:
    #         KeyError: If component not found in network
    #         IndexError: If power flow data unavailable

    #     Example:
    #         >>> store_p_flow()
    #         >>> print(flow_data[timestamp][(1, 2)])
    #         123.45  # MW
    #     """
    #     # Ensure flow_data dictionary exists
    #     if not hasattr(self, "flow_data"):
    #         self.flow_data = {}

    #     snapshots = self.get_snapshots()

    #     # Loop over snapshots
    #     for t in snapshots:
    #         # Create an empty dictionary for this particular timestamp
    #         p_flow_dict = {}

    #         try:
    #             # Iterate over all lines in the network
    #             for line in self.pypsa_object.lines.index:
    #                 # Get source and target buses
    #                 source = self.pypsa_object.lines.loc[line, "bus0"]
    #                 target = self.pypsa_object.lines.loc[line, "bus1"]

    #                 # Get the power flow value for p0 at the current snapshot
    #                 try:
    #                     p_flow = self.pypsa_object.lines_t["p0"].loc[t, line]
    #                 except KeyError:
    #                     print(f"Line {line} not found in lines_t.p0 for snapshot {t}.")
    #                     continue
    #                 except IndexError:
    #                     print(
    #                         f"No power flow data available for line {line} at snapshot {t}."
    #                     )
    #                     continue

    #                 # Store the power flow in the dictionary
    #                 p_flow_dict[(source, target)] = p_flow

    #             for transformer in self.pypsa_object.transformers.index:

    #                 source = self.pypsa_object.transformers.loc[transformer, "bus0"]
    #                 target = self.pypsa_object.transformers.loc[transformer, "bus1"]

    #                 try:
    #                     p_flow = self.pypsa_object.transformers_t["p0"].loc[
    #                         t, transformer
    #                     ]
    #                 except KeyError:
    #                     print(
    #                         f"Transformer {transformer} not found in t.p0 for snapshot {t}."
    #                     )
    #                     continue
    #                 except IndexError:
    #                     print(
    #                         f"No power flow data available for transformer {transformer} at snapshot {t}."
    #                     )
    #                     continue
    #                 p_flow_dict[(source, target)] = p_flow
    #             # Store the power flow data for this snapshot in the flow_data dictionary
    #             self.flow_data[t] = p_flow_dict

    #         except Exception as e:
    #             print(f"Error storing power flow data for snapshot {t}: {e}")

    # def plot_bus(self, bus_num, arg_1="p", arg_2="q"):
    #     """
    #     Description: This function plots the activate and reactive power for a given bus
    #     input:
    #         bus_num: the bus number we wanna viz (Int)
    #         time: a list with start and end time (list of Ints)
    #     output:
    #         matplotlib chart
    #     """
    #     visualizer = PyPSAVisualizer(pypsa_obj=self)
    #     visualizer.plot_bus(bus_num, arg_1, arg_2)

    # def bus_history(self, bus_num):
    #     """
    #     Description: this function grab all the data associated with a bus through the simulation
    #     input:
    #         bus_num: bus number (int)
    #     output:
    #         bus_dataframe: a pandas dateframe of the history
    #     """
    #     # maybe I should add a filering parameter?

    #     bus_dataframe = pd.DataFrame()
    #     for time, df in self.pypsa_history.items():
    #         temp = pd.DataFrame(df.loc[df["Bus"] == str(bus_num)])
    #         temp.insert(0, "time", time)
    #         bus_dataframe = bus_dataframe.append(temp)
    #     return bus_dataframe

         
    # def generate_load_curve(self, noise_level=0.002, time=None):
    #     """

    #     """
    #     if time is None:
    #         time_data = self.WecGridCore.wecObj_list[0].dataframe.time.to_list()
    #     else:
    #         time_data = time
    #     num_timesteps = len(time_data)

    #     p_load_values = self.pypsa_object.loads["p"] 
        
        
    #     # Bell curve time shape
    #     time_index = np.linspace(-1, 1, num_timesteps)
    #     bell_curve = np.exp(-4 * time_index**2)

    #     load_profiles = {}

    #     for load_id, base_load in p_load_values.items():
    #         if base_load == 0:
    #             load_profiles[load_id] = np.zeros(num_timesteps)
    #             continue

    #         curve = base_load * (1 + 0.05 * bell_curve)  # 5% peak bump
    #         noise = np.random.normal(0, noise_level * base_load, num_timesteps)
    #         curve += noise
    #         curve[0] = base_load  # Ensure first value = original

    #         load_profiles[load_id] = curve

    #     self.load_profiles = pd.DataFrame(load_profiles, index=time_data)
    
