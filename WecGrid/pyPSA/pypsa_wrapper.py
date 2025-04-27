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

# 3rd Party Libraries
import pypsa
import pandas as pd
import cmath
import numpy as np
import matlab.engine
import pypower.api as pypower
from pandas.tseries.offsets import DateOffset
from grg_pssedata.io import parse_psse_case_file

# Local Libraries (updated with relative imports)
from ..utilities.util import read_paths  # Relative import for utilities/util.py
from ..viz.pypsa_viz import PyPSAVisualizer

# Initialize the PATHS dictionary
PATHS = read_paths()
CURR_DIR = os.path.dirname(os.path.abspath(__file__))


class pyPSAWrapper:
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

    def __init__(self, case, WecGridCore):
        """
        Initialize PyPSA wrapper.

        Args:
            case (str): Path to case file
            WecGridCore (object): Reference to parent WecGridCore object

        Returns:
            None
        """
        self.case_file = case
        self.pypsa_history = {}
        self.pypsa_object_history = {}
        self.dataframe = pd.DataFrame()
        self.flow_data = {}
        self.WecGridCore = WecGridCore  # Reference to the parent
        self.timestamp_start = datetime.now()
        self.load_profiles = pd.DataFrame()
        self.snapshots = pd.DatetimeIndex([])  # Initialize snapshots as an empty DatetimeIndex
        self.sbase = 1e6  # System base power in VA (1 MVA)

    def get_snapshots(self):
        """
        Get network snapshots.

        Returns:
            pd.Index: Index of network snapshots
        """

        return self.pypsa_object.snapshots

    def initialize_og(self, solver):
        """
        Initialize PyPSA case from PSS/E raw file.

        Args:
            solver (str): Power flow solver name (e.g. "fnsl")

        Returns:
            None

        Notes:
            - Only supports .raw files
            - Uses MATPOWER -> PyPOWER -> PyPSA conversion
        """

        eng = matlab.engine.start_matlab()
        eng.workspace["case_path"] = self.case_file
        eng.eval("mpc = psse2mpc(case_path)", nargout=0)
        eng.eval("savecase('here.mat',mpc,1.0)", nargout=0)

        # Load the MATPOWER case file from a .mat file
        ppc = pypower.loadcase(
            "./here.mat"
        )  # TODO: this is hardcode, should be passing the mat file, tbh I forgot what this is for.

        # Convert Pandapower network to PyPSA network
        # pypsa_network = pypsa.Network()
        self.pypsa_object = pypsa.Network()
        self.pypsa_object.import_from_pypower_ppc(ppc, overwrite_zero_s_nom=True)
        self.pypsa_object.set_snapshots(
            [self.timestamp_start]
        )  # Set the initial snapshot

        # self.run_powerflow()
        self.pypsa_object.pf()

        self.dataframe = self.pypsa_object.df("Bus").copy()
        self.format_df()
        # self.pypsa_object = pypsa_network
        # self.pypsa_history[self.timestamp_start] = self.dataframe # TODO: need to replace with snapshot
        # self.pypsa_object_history[]] = self.pypsa_object
        # self.format_df()
        self.store_p_flow()  # not storing init p flow i guess?
        print("pyPSA initialized")


    def initialize(self, solver):
        # """
        # Builds a PyPSA Network from a parsed PSS/E RAW case file.
        # Only sets necessary fields for a valid power flow.
        # """
        # case = parse_psse_case_file(self.case_file)
        # self.pypsa_object = pypsa.Network(s_n_mva=case.sbase)
        # self.sbase = case.sbase

        # # PSS/E ide to PyPSA control mapping
        # ide_to_ctrl = {1: "PQ", 2: "PV", 3: "Slack"}

        # # Quick bus lookup
        # bus_map = {b.i: b for b in case.buses}

        # # Add Buses
        # for bus in case.buses:
        #     self.pypsa_object.add("Bus",
        #         name          = str(bus.i),
        #         v_nom         = bus.basekv,
        #         v_mag_pu_set  = bus.vm,
        #         v_mag_pu_min  = bus.nvlo,
        #         v_mag_pu_max  = bus.nvhi,
        #         control       = ide_to_ctrl.get(bus.ide, "PQ"),
        #     )

        # # Add Lines (Branches)
        # for idx, br in enumerate(case.branches):
        #     lname = f"L{idx}"
        #     V_bus  = self.pypsa_object.buses.at[str(br.i), "v_nom"] * 1e3
        #     S_base = case.sbase * 1e6
        #     Z_base = V_bus**2 / S_base

        #     self.pypsa_object.add("Line",
        #         name         = lname,
        #         bus0         = str(br.i),
        #         bus1         = str(br.j),
        #         r            = br.r * Z_base,
        #         x            = br.x * Z_base,
        #         s_nom        = br.ratea,
        #     )

        # # Add Generators
        # for idx, g in enumerate(case.generators):
        #     if g.stat != 1:
        #         continue

        #     gname = f"G{idx}"
        #     ctrl  = ide_to_ctrl.get(bus_map[g.i].ide, "PQ")

        #     self.pypsa_object.add("Generator",
        #         name      = gname,
        #         bus       = str(g.i),
        #         control   = ctrl,
        #         p_nom     = g.pt,
        #         p_set     = g.pg,
        #         q_set     = g.qg,
        #     )

        # # Add Transformers
        # for idx, tx in enumerate(case.transformers):
        #     tname = f"T{idx}"
        #     s_nom = tx.w1.rata

        #     r_pu = tx.p2.r12 * (tx.p2.sbase12 / s_nom)
        #     x_pu = tx.p2.x12 * (tx.p2.sbase12 / s_nom)

        #     self.pypsa_object.add("Transformer",
        #         name         = tname,
        #         bus0         = str(tx.p1.i),
        #         bus1         = str(tx.p1.j),
        #         r            = r_pu,
        #         x            = x_pu,
        #         s_nom        = s_nom,
        #         tap_ratio    = tx.w1.windv,
        #         phase_shift  = tx.w1.ang,
        #     )

        # # Add Loads
        # for idx, L in enumerate(case.loads):
        #     if L.status != 1:
        #         continue

        #     lname = f"Load{idx}"
        #     self.pypsa_object.add("Load",
        #         name  = lname,
        #         bus   = str(L.i),
        #         p_set = L.pl,
        #         q_set = L.ql,
        #     )

        # # Add Switched Shunts (as ShuntImpedances)
        # for idx, ss in enumerate(case.switched_shunts):
        #     if ss.stat != 1:
        #         continue

        #     bus_name    = str(ss.i)
        #     V_nom_V     = self.pypsa_object.buses.at[bus_name, "v_nom"] * 1e3
        #     b_siemens   = (ss.binit * 1e6) / V_nom_V**2

        #     self.pypsa_object.add("ShuntImpedance",
        #         name = f"Sh{idx}",
        #         bus  = bus_name,
        #         b    = b_siemens,
        #     )
        
        self.import_raw_to_pypsa()
        # Solve power flow and format
        self.pypsa_object.pf()
        self.dataframe = self.pypsa_object.df("Bus").copy()
        self.format_df()
        self.store_p_flow()

        print("pyPSA initialized")
        
        
    def import_raw_to_pypsa(self):
        """
        Builds a PyPSA Network from a parsed PSS/E RAW case file.
        Only sets necessary fields for a valid power flow.
        """

        case = parse_psse_case_file(self.case_file)
        self.pypsa_object = pypsa.Network(s_n_mva=case.sbase)

        
        case.bus_lookup = {bus.i: bus for bus in case.buses}

        # Mapping PSS/E bus types to PyPSA control types
        ide_to_ctrl = {1: "PQ", 2: "PV", 3: "Slack"}

        # --- Add Buses ---
        for bus in case.buses:
            self.pypsa_object.add("Bus",
                name          = str(bus.i),
                v_nom         = bus.basekv,        # [kV]
                v_mag_pu_set  = bus.vm,             # [pu]
                v_mag_pu_min  = bus.nvlo,           # [pu]
                v_mag_pu_max  = bus.nvhi,           # [pu]
                control       = ide_to_ctrl.get(bus.ide, "PQ"),
            )

        # --- Add Lines (Branches) ---
        for idx, br in enumerate(case.branches):
            lname = f"L{idx}"
            V_bus_kV = self.pypsa_object.buses.at[str(br.i), "v_nom"]
            V_bus_V = V_bus_kV * 1e3  # Convert to [V]
            S_base_VA = case.sbase * 1e6
            Z_base = V_bus_V**2 / S_base_VA

            self.pypsa_object.add("Line",
                name         = lname,
                bus0         = str(br.i),
                bus1         = str(br.j),
                r            = br.r * Z_base,  # [Ohm]
                x            = br.x * Z_base,  # [Ohm]
                s_nom        = br.ratea,        # [MVA]
                s_nom_extendable = False,
            )

        # --- Add Transformers ---
        for idx, tx in enumerate(case.transformers):
            tname = f"T{idx}"
            s_nom = tx.w1.rata  # Base rating on winding 1 [MVA]

            r_pu = tx.p2.r12 * (tx.p2.sbase12 / s_nom)
            x_pu = tx.p2.x12 * (tx.p2.sbase12 / s_nom)

            self.pypsa_object.add("Transformer",
                name          = tname,
                bus0          = str(tx.p1.i),
                bus1          = str(tx.p1.j),
                r             = r_pu,      # [pu on s_nom]
                x             = x_pu,      # [pu on s_nom]
                s_nom         = s_nom,     # [MVA]
                tap_ratio     = tx.w1.windv,  # Tap [pu]
                phase_shift   = tx.w1.ang,     # [deg]
                s_nom_extendable = False,
            )

        # --- Add Generators ---
        for idx, g in enumerate(case.generators):
            if g.stat != 1:
                continue

            gname = f"G{idx}"
            ctrl = ide_to_ctrl.get(case.bus_lookup[g.i].ide, "PQ")

            self.pypsa_object.add("Generator",
                name       = gname,
                bus        = str(g.i),
                control    = ctrl,
                p_nom      = g.pt,
                p_set      = g.pg,
                q_set      = g.qg,
                p_min_pu   = (g.pb / g.pt) if g.pt else 0.0,
                p_max_pu   = 1.0,
            )

        # --- Add Loads ---
        for idx, load in enumerate(case.loads):
            if load.status != 1:
                continue

            lname = f"L{idx}"
            self.pypsa_object.add("Load",
                name  = lname,
                bus   = str(load.i),
                p_set = load.pl,
                q_set = load.ql,
            )

        # --- Add Switched Shunts (as ShuntImpedance) ---
        for idx, ss in enumerate(case.switched_shunts):
            if ss.stat != 1:
                continue

            bus_name = str(ss.i)
            V_nom_kV = self.pypsa_object.buses.at[bus_name, "v_nom"]
            V_nom_V = V_nom_kV * 1e3
            b_S = (ss.binit * 1e6) / V_nom_V**2  # Susceptance in Siemens

            self.pypsa_object.add("ShuntImpedance",
                name = f"Sh{idx}",
                bus  = bus_name,
                b    = b_S,
            )




    def add_wec(self, model: str, from_bus: int, to_bus: int, p_nom=5.0, bus_voltage_kv=34.5,line_r_pu=0.01, line_x_pu=0.05):

        # 
        self.pypsa_object.add("Bus",
            name=str(to_bus),
            v_nom=bus_voltage_kv,
            carrier="AC",
        )
        
        V_nom_V = self.pypsa_object.buses.at[str(to_bus), "v_nom"] * 1e3
        S_base_VA = self.pypsa_object.s_n_mva * 1e6
        Z_base = V_nom_V**2 / S_base_VA

        self.pypsa_object.add("Line",
            name="WEC_line",
            bus0=str(to_bus),
            bus1=str(from_bus),
            r=line_r_pu * Z_base,
            x=line_x_pu * Z_base,
            s_nom=len(self.WecGridCore.wecObj_list) * p_nom,  # scale line nominal power
        )
        
        #for wec in self.WecGridCore.wecObj_list:
        for i, wec in enumerate(self.WecGridCore.wecObj_list):
            wec.gen_id = f'G{i}' # this might not be needed
            wec_gen = f"{wec.gen_id}-{wec.model}-{wec.ID}",
            self.pypsa_object.add("Generator",
                name=wec_gen,
                bus=str(to_bus),
                carrier="wave",
                p_nom=p_nom,
                p_set=p_nom * 0.0, 
                marginal_cost=0.0,
                control="PQ",
                efficiency=1.0,
            )
        
        

        # # 1) Make sure the tap‐in bus exists
        # if bus25 not in net.buses.index:
        #     kv = net.buses.at[bus0, "v_nom"]
        #     net.add("Bus",
        #         name         = bus25,
        #         v_nom        = kv,
        #         carrier      = "AC",
        #         v_mag_pu_min = 0.95,
        #         v_mag_pu_max = 1.05,
        #         unit          = "MW",
        #         control       = "PV",
                
        #     )
            
        #     # 2) Tie it back with a near‐zero impedance line
        #     net.add("Line",
        #         name = f"wec_bridge_{bus0}_{bus25}",
        #         bus0 = bus0,
        #         bus1 = bus25,
        #     )

        # # 3) Place each WEC as a PQ‐mode injector on the tap‐in bus
        # for i, wec in enumerate(self.WecGridCore.wecObj_list, start=1):
        #     net.add("Generator",
        #         name = f"{wec.gen_id}-{wec.model}-{wec.ID}",
        #         bus        = bus25,
        #         control    = "PV",        # fixed P & fixed Q
        #         p_nom      = 0.05,        # MW rated
        #         p_set      = 0.02,  # your injection profile (MW)
        #         q_set      = 0.0,         # hold Q at zero
        #         p_min_pu   = 0.0,         # always run at p_set fraction of p_nom
        #         p_max_pu   = 1.0,
        #         marginal_cost = 0.0,
        #     )

        self.pypsa_object.pf()
        self.dataframe = self.pypsa_object.df("Bus")
        self.format_df()
        self.store_p_flow()


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

    def classify_generator(self, control):
        """
        Classify generator type based on control mode.

        Args:
            control (str): Generator control type ("Slack", "PV", "PQ", "WEC")

        Returns:
            int: Generator type code (0-4)
            - 3: Slack bus
            - 2: PV bus
            - 1: PQ bus
            - 4: WEC
            - 0: Other
        """
        if control == "Slack":
            return 3  # Type 3

        elif control == "PV":
            return 2

        elif control == "PQ":
            return 1

        elif control == "WEC":
            return 4
        else:
            return 0

    def format_df(self):
        """
        Format network data for each snapshot.

        Creates a formatted DataFrame containing bus variables and generator types
        for each network snapshot. Updates bus types for WEC generators.

        Variables collected:
            - v_mag_pu_set: Voltage magnitude setpoint (per unit)
            - p: Active power
            - q: Reactive power
            - v_mag_pu: Actual voltage magnitude (per unit)
            - v_ang: Voltage angle

        Returns:
            None

        Notes:
            Updates self.pypsa_history with formatted data for each snapshot
        """

        snapshots = self.get_snapshots()
        # Specify the bus variables to collect
        variables = ["v_mag_pu_set", "p", "q", "v_mag_pu", "v_ang"]

        # Loop over each snapshot
        for snapshot in snapshots:
            # Initialize a DataFrame to store data for this snapshot
            snapshot_data = pd.DataFrame()

            # Loop over the variables and collect the data
            for var in variables:
                if var in self.pypsa_object.buses_t:
                    # Add the variable data as a column in the DataFrame
                    snapshot_data[var] = self.pypsa_object.buses_t[var].loc[snapshot]

            # combine snapshot_data to have control, generator
            bus_static_data = self.pypsa_object.df("Bus")[["control", "generator"]]
            merged_data = pd.merge(
                snapshot_data, bus_static_data.copy(), on="Bus", how="left"
            )

            merged_data["type"] = merged_data["control"].apply(self.classify_generator)

            # Add the snapshot data to the history dictionary

            # update WEC bus type

            for wec in self.WecGridCore.wecObj_list:
                name = "{}-{}".format(wec.model, wec.ID)
                merged_data.loc[merged_data["generator"] == str(name), "type"] = 4

            self.pypsa_history[snapshot] = merged_data.reset_index()

            # update WEC bus type

    def current_df(self):
        """
        Retrieve the current DataFrame from the pypsa_history.
        This method returns the DataFrame corresponding to the most recent snapshot
        in the pypsa_history.
        Returns:
            pandas.DataFrame: The DataFrame corresponding to the latest snapshot.
        """

        return self.pypsa_history[self.get_snapshots()[-1]]
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
    def ac_injection(self, snapshots=None):
        """
        Perform AC power injection simulation for WEC generators.

        Args:
            snapshots (pd.DatetimeIndex, optional): Timestamps for simulation.
                If None, creates 5-minute intervals based on first WEC's data length.

        Returns:
            None

        Notes:
            - Assumes one WEC generator per bus
            - Updates power flow results in self.pypsa_history
            - Creates snapshots starting 5 minutes after initial timestamp
        """
        # Initialize empty dictionaries for generator active power (p_set)
        p_set_data = {}

        # Determine snapshots if not provided
        if snapshots is None:
            # Use the initial timestamp and create a range of snapshots
            num_snapshots = len(self.WecGridCore.wecObj_list[0].dataframe["pg"])

            snapshots = pd.date_range(
                start=self.timestamp_start + DateOffset(minutes=5),  # Add 5 minutes
                periods=num_snapshots,
                freq="5T",  # 5-minute intervals
            )
            self.snapshots = snapshots  # Store the snapshots for later use
            
        # # Iterate over load profiles
        
        # for idx, load in enumerate(self.load_profile):
            
        

        # Iterate over all WEC objects to gather data
        for idx, wec_obj in enumerate(self.WecGridCore.wecObj_list):
            bus = wec_obj.bus_location

            # Ensure the generator exists for the bus
            generator_row = self.pypsa_object.generators.loc[
                self.pypsa_object.generators.bus == str(bus)
            ]

            #generator_name = generator_row.index[0]  # Get the generator name (index)
 
            #generator_name = "{}-{}".format(wec_obj.model, wec_obj.ID)
            
            generator_name = f"{wec_obj.gen_id}-{wec_obj.model}-{wec_obj.ID}"

            # Fetch pg (active power) data and assume it's aligned with snapshots
            #pg_data = wec_obj.dataframe["pg"]  # Scale pg as needed
            '''
            This is assuming the WEC output is in kW, so we convert it to MW. 
            0.016 from wec-sim is = 16kW, so we divide by 1000 to get MW.
            '''
            pg_data = wec_obj.dataframe["pg"]
            #pg_data_MW = pg_data * (wec_obj.MBASE / 1000.0)

            # Store active power values for this generator
            p_set_data[generator_name] = pg_data.to_list()
        # Set snapshots in the PyPSA network
        self.pypsa_object.set_snapshots(snapshots)

        p_set_df = pd.DataFrame(p_set_data, index=snapshots)

        # Assign active power values to the generators in the PyPSA network
        self.pypsa_object.generators_t.p_set = p_set_df
        

    #     # TODO: should try using p instead of p_set?
        
        #  update the load
        self.generate_load_curve(time=snapshots)
        self.pypsa_object.loads_t.p_set = self.load_profiles.copy()
        

        # Run power flow for all snapshots
        self.pypsa_object.pf()

        self.format_df()  # also saves in history

        self.store_p_flow()
        
 

    def run_powerflow(self):
        """
        Execute power flow calculation.

        Runs power flow analysis using PyPSA solver and stores results
        in instance dataframe.

        Returns:
            None

        Notes:
            Updates self.dataframe with current network state
        """
        self.pypsa_object.pf()
        self.dataframe = self.pypsa_object.df("Bus").copy()

    def viz(self, dataframe=None):
        """
        Visualize network using PyPSAVisualizer.

        Args:
            dataframe (pd.DataFrame, optional): Custom data for visualization.
                If None, uses default network state.

        Returns:
            matplotlib.figure.Figure: Network visualization plot
        """

        visualizer = PyPSAVisualizer(pypsa_obj=self)  # need to pass this object itself?
        return visualizer.viz()

    def store_p_flow(self):
        """
        Store active power flows for network components.

        Records p0 (active power flow) values for all lines and transformers
        at each network snapshot.

        Data Structure:
            self.flow_data = {
                timestamp: {
                    (source_bus, target_bus): power_flow_value,
                    ...
                }
            }

        Returns:
            None

        Raises:
            KeyError: If component not found in network
            IndexError: If power flow data unavailable

        Example:
            >>> store_p_flow()
            >>> print(flow_data[timestamp][(1, 2)])
            123.45  # MW
        """
        # Ensure flow_data dictionary exists
        if not hasattr(self, "flow_data"):
            self.flow_data = {}

        snapshots = self.get_snapshots()

        # Loop over snapshots
        for t in snapshots:
            # Create an empty dictionary for this particular timestamp
            p_flow_dict = {}

            try:
                # Iterate over all lines in the network
                for line in self.pypsa_object.lines.index:
                    # Get source and target buses
                    source = self.pypsa_object.lines.loc[line, "bus0"]
                    target = self.pypsa_object.lines.loc[line, "bus1"]

                    # Get the power flow value for p0 at the current snapshot
                    try:
                        p_flow = self.pypsa_object.lines_t["p0"].loc[t, line]
                    except KeyError:
                        print(f"Line {line} not found in lines_t.p0 for snapshot {t}.")
                        continue
                    except IndexError:
                        print(
                            f"No power flow data available for line {line} at snapshot {t}."
                        )
                        continue

                    # Store the power flow in the dictionary
                    p_flow_dict[(source, target)] = p_flow

                for transformer in self.pypsa_object.transformers.index:

                    source = self.pypsa_object.transformers.loc[transformer, "bus0"]
                    target = self.pypsa_object.transformers.loc[transformer, "bus1"]

                    try:
                        p_flow = self.pypsa_object.transformers_t["p0"].loc[
                            t, transformer
                        ]
                    except KeyError:
                        print(
                            f"Transformer {transformer} not found in t.p0 for snapshot {t}."
                        )
                        continue
                    except IndexError:
                        print(
                            f"No power flow data available for transformer {transformer} at snapshot {t}."
                        )
                        continue
                    p_flow_dict[(source, target)] = p_flow
                # Store the power flow data for this snapshot in the flow_data dictionary
                self.flow_data[t] = p_flow_dict

            except Exception as e:
                print(f"Error storing power flow data for snapshot {t}: {e}")

    def plot_bus(self, bus_num, arg_1="p", arg_2="q"):
        """
        Description: This function plots the activate and reactive power for a given bus
        input:
            bus_num: the bus number we wanna viz (Int)
            time: a list with start and end time (list of Ints)
        output:
            matplotlib chart
        """
        visualizer = PyPSAVisualizer(pypsa_obj=self)
        visualizer.plot_bus(bus_num, arg_1, arg_2)

    def bus_history(self, bus_num):
        """
        Description: this function grab all the data associated with a bus through the simulation
        input:
            bus_num: bus number (int)
        output:
            bus_dataframe: a pandas dateframe of the history
        """
        # maybe I should add a filering parameter?

        bus_dataframe = pd.DataFrame()
        for time, df in self.pypsa_history.items():
            temp = pd.DataFrame(df.loc[df["Bus"] == str(bus_num)])
            temp.insert(0, "time", time)
            bus_dataframe = bus_dataframe.append(temp)
        return bus_dataframe

         
    def generate_load_curve(self, noise_level=0.002, time=None):
        """

        """
        if time is None:
            time_data = self.WecGridCore.wecObj_list[0].dataframe.time.to_list()
        else:
            time_data = time
        num_timesteps = len(time_data)

        p_load_values = self.pypsa_object.loads["p"] 
        
        
        # Bell curve time shape
        time_index = np.linspace(-1, 1, num_timesteps)
        bell_curve = np.exp(-4 * time_index**2)

        load_profiles = {}

        for load_id, base_load in p_load_values.items():
            if base_load == 0:
                load_profiles[load_id] = np.zeros(num_timesteps)
                continue

            curve = base_load * (1 + 0.05 * bell_curve)  # 5% peak bump
            noise = np.random.normal(0, noise_level * base_load, num_timesteps)
            curve += noise
            curve[0] = base_load  # Ensure first value = original

            load_profiles[load_id] = curve

        self.load_profiles = pd.DataFrame(load_profiles, index=time_data)
    
