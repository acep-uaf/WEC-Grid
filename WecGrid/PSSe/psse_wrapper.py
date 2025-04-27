"""
PSSe Class Module file
"""

# Standard Libraries
import os
import sys

# 3rd Party Libraries
import pandas as pd
import cmath
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
from collections import defaultdict
from matplotlib.patches import Rectangle, Circle, FancyArrow
from matplotlib.lines import Line2D
from collections import namedtuple
import time
import time as time_module


# Local Libraries (updated with relative imports)
from ..utilities.util import read_paths  # Relative import for utilities/util.py
from ..viz.psse_viz import PSSEVisualizer  # Relative import for viz/psse_viz.py

# Initialize the PATHS dictionary
# PATHS = read_paths()
CURR_DIR = os.path.dirname(os.path.abspath(__file__))

Snapshot = namedtuple("Snapshot", ["time", "buses", "generators","metadata"])   

# TODO: the PSSE is sometimes blowing up but not returning and error so the sim continues. Need to fix ASAP
class PSSeWrapper:
    """
    Wrapper class for PSSE functionalities.

    Attributes:
        case_file (str): Path to the case file.
        wec_grid (WecGrid): Instance of the WecGrid class.
        dataframe (pd.DataFrame): Dataframe to store PSSE data.
    """

    def __init__(self, case, WecGridCore):
        """
        Initializes the PSSeWrapper class with the given case file and WecGrid instance.

        Args:
            case_file (str): Path to the case file.
            wec_grid (WecGrid): Instance of the WecGrid class.
        """
        self.case_file = case
        self.bus_dataframe = pd.DataFrame()
        self.gen_dataframe = pd.DataFrame()
        self.snapshot_history = []
        self.flow_data = {}
        self.WecGridCore = WecGridCore  # Reference to the parent WecGrid
        self.load_profiles = pd.DataFrame()
        self.solver = None  # unneeded?
        

    def initialize(self, solver="fnsl"):  # TODO: miss spelling
        """
        Description: Initializes a PSSe case, uses the topology passed at original initialization
        input:
            solver: the solver you want to use supported by PSSe, "fnsl" is a good default (str)
        output: None
        """
        try:
            import psspy
            import psse35
            import redirect

            psse35.set_minor(3)
            psspy.psseinit(50)
            
            # # Silence unnecessary outputs
            psspy.prompt_output(6, "", [])    # no interactive prompts
            psspy.alert_output(6, "", [])     # no alerts
            psspy.progress_output(6, "", [])  # no progress messages
            #psspy.report_output(2, "", [])    # enable only report (results/errors) to screen
                        
                        
        except ModuleNotFoundError as e:
            print(
                "Error: PSSE modules not found. Ensure PSSE is installed and paths are configured."
            )
            raise e

        # Initialize PSSE object
        PSSeWrapper.psspy = psspy
        psspy.report_output(islct=2, filarg="NUL", options=[0])

        #self.lst_param = ["BASE", "PU", "ANGLE", "P", "Q"]
        self.solver = solver
        self.dynamic_case_file = ""

        # self.dataframe = pd.DataFrame()
        self._i = psspy.getdefaultint()
        self._f = psspy.getdefaultreal()
        self._s = psspy.getdefaultchar()

        ext = self.case_file.lower()
        if ext.endswith(".sav"):
            ierr = PSSeWrapper.psspy.case(self.case_file)
        elif ext.endswith(".raw"):
            ierr = PSSeWrapper.psspy.read(1, self.case_file)
        else:
            print("Unsupported case file format.")
            return 0

        if ierr >= 1:
            print("Error reading the case file.")
            return 0

        if not self.run_powerflow(solver): # 0 return is good
            self.take_snapshot()
            return 1
        else:
            print("Error running power flow.")
            return 0

    def get_sbase(self):
        return PSSeWrapper.psspy.sysmva()
    
    def take_snapshot(self, time=None, metadata=None):
        """
        Takes a snapshot of the PSSE system state.
        
        Args:
            time (float, optional): Timestamp to assign to snapshot. Defaults to `time.time()`.
            metadata (any, optional): Optional metadata to tag with the snapshot. Can be string or dict.
        
        Returns:
            Snapshot: Namedtuple containing time, buses, generators, and metadata.
        """
        if metadata is None:
            metadata = {}

        snapshot = Snapshot(
            time=time if time is not None else time_module.time(),  # Avoid shadowing 'time'
            buses=self.snapshot_buses(),
            generators=self.snapshot_generators(),
            metadata=metadata
        )

        print(f"[Snapshot] t={snapshot.time:.2f}, note={metadata}")
        self.snapshot_history.append(snapshot)
        self.bus_dataframe = snapshot.buses
        self.gen_dataframe = snapshot.generators
        return snapshot
    
    
    def snapshot_generators(self):
        """Snapshots generator state across the entire grid using amach* calls."""
        ierr1, bus_numbers = PSSeWrapper.psspy.amachint(-1, 4, "NUMBER")
        ierr2, gen_ids = PSSeWrapper.psspy.amachchar(-1, 4, "ID")
        ierr3, pg_values = PSSeWrapper.psspy.amachreal(-1, 4, "PGEN")
        ierr4, qg_values = PSSeWrapper.psspy.amachreal(-1, 4, "QGEN")
        ierr5, mbase_values = PSSeWrapper.psspy.amachreal(-1, 4, "MBASE")
        ierr6, status_vals = PSSeWrapper.psspy.amachint(-1, 4, "STATUS")
        ierr7, mismatch_vals = PSSeWrapper.psspy.agenbusreal(-1,1,'MISMATCH') # Bus mismatch, in MVA 
        ierr8, percent_vals = PSSeWrapper.psspy.agenbusreal(-1,1,'PERCENT') # Bus mismatch, in MVA 

        if any(ierr != 0 for ierr in [ierr1, ierr2, ierr3, ierr4, ierr5, ierr6, ierr7, ierr8]):
            raise RuntimeError("One or more PSSE API calls failed.")

        data = [
            {
                "BUS_ID": b,
                "GEN_ID": g,
                "Pg": p,
                "Qg": q,
                "MBASE": m,
                "STATUS": s,
                "MISMATCH": mi,
                "PERCENT": pe,
            }
            for b, g, p, q, m, s, mi, pe in zip(
                bus_numbers[0], gen_ids[0], pg_values[0], qg_values[0], mbase_values[0], status_vals[0], mismatch_vals[0], percent_vals[0]
            )
        ]

        return pd.DataFrame(data)
    
    def snapshot_buses(self, bus_ids=None):
        """
        Robust bus snapshot for:
        - Pd, Qd: real/reactive load
        - Pg, Qg: real/reactive gen
        - P: net injection (Pg - Pd)
        - Voltage magnitude and angle
        NaN values used where data is unavailable.
        """
        if bus_ids is None:
            ierr, bus_ids = PSSeWrapper.psspy.abusint(-1, 1, 'NUMBER')  # in-service buses
            bus_ids = bus_ids[0]

        data = []
        ierr, rarray = PSSeWrapper.psspy.abusreal(-1,1,'MISMATCH') # Bus mismatch, in MVA 

        for i in range(len(bus_ids)):
            bus = bus_ids[i]
            # Load (MW / MVAr)
            ierr, cmpval = PSSeWrapper.psspy.busdt2(bus, 'TOTAL', 'ACT')
            Pd = cmpval.real if ierr == 0 else 0.0
            Qd = cmpval.imag if ierr == 0 else 0.0

            # Generation (MW / MVAr)
            ierr, cmpval_gen = PSSeWrapper.psspy.gendat(bus)
            Pg = cmpval_gen.real if ierr == 0 else 0.0
            Qg = cmpval_gen.imag if ierr == 0 else 0.0

            # Voltage and angle
            v_pu        = PSSeWrapper.psspy.busdat(bus, 'PU')[1]
            base_kv   = PSSeWrapper.psspy.busdat(bus, 'BASE')[1]
            v_mag_kv    = PSSeWrapper.psspy.busdat(bus, 'KV')[1]
            v_angle_deg = PSSeWrapper.psspy.busdat(bus, 'ANGLED')[1]
            v_angle_rad = PSSeWrapper.psspy.busdat(bus, 'ANGLE')[1]
            bus_type = PSSeWrapper.psspy.busint(bus, 'TYPE')[1]

            data.append({
                'BUS_ID': bus,
                'TYPE': bus_type,
                'Pd': Pd,
                'Qd': Qd,
                'Pg': Pg,
                'Qg': Qg,
                'P': Pg - Pd,
                'Q': Qg - Qd,
                'V_PU': v_pu,
                'V_KV': v_mag_kv,
                'BASE_KV': base_kv,
                'ANGLE_DEG': v_angle_deg,
                'ANGLE_RAD': v_angle_rad,
                'MISMATCH': rarray[0][i],
            })

        return pd.DataFrame(data)

    def get_all_buses_df(self):
        return pd.concat([
            snap.buses.assign(timestamp=snap.time, metadata=str(snap.metadata))
            for snap in self.snapshot_history
        ], ignore_index=True)

    def add_wec(self, model, from_bus, to_bus):
        """
        Adds a WEC system to the PSSE model by:
        1. Adding a new bus.
        2. Adding a generator to the bus.
        3. Adding a branch (line) connecting the new bus to an existing bus.

        Parameters:
        - model (str): Model identifier for the WEC system.
        - ID (int): Unique identifier for the WEC system.
        - from_bus (int): Existing bus ID to connect the line from.
        - to_bus (int): New bus ID for the WEC system.
        """
        print("Adding WECs to PSS/E network")
        # Create a name for this WEC system
        name = f"{model}-{to_bus}"

        from_bus_voltage = PSSeWrapper.psspy.busdat(from_bus, "BASE")[1]

        # Step 1: Add a new bus
        
        ierr = PSSeWrapper.psspy.bus_data_4(
            ibus=to_bus, 
            inode=0, 
            intgar1=2, # Bus type (2 = PV bus ), area, zone, owner
            realar1=from_bus_voltage, # Base voltage of the from bus in kV
            name=name
        )
        if ierr != 0:
            print(f"Error adding bus {to_bus}. PSS®E error code: {ierr}")
            return

        print(f"Bus {to_bus} added successfully.")

        # Step 2: Add plant data
        ierr = PSSeWrapper.psspy.plant_data_4(
            ibus=to_bus, 
            inode=0
        )
        if ierr == 0:
            print(f"Plant data added successfully to bus {to_bus}.")
        else:
            print(f"Error adding plant data to bus {to_bus}. PSS®E error code: {ierr}")
            return

        for i, wec_obj in enumerate(self.WecGridCore.wecObj_list):
            # Step 3: Add a generator at the new bus
            wec_obj.gen_id = f'G{i+1}'
            ierr = PSSeWrapper.psspy.machine_data_4(
                ibus=to_bus, 
                id=wec_obj.gen_id,
                realar1= 0.02,# PG, machine active power (0.0 by default)
                realar7=wec_obj.MBASE # 1 MVA typically
            )

            if ierr > 0:
                print(
                    f"Error adding generator {wec_obj.gen_id} to bus {to_bus}. PSS®E error code: {ierr}"
                )
                return

            print(f"Generator {wec_obj.gen_id} added successfully to bus {to_bus}.")

        # Step 4: Add a branch (line) connecting the existing bus to the new bus
        ierr = PSSeWrapper.psspy.branch_data_3(
            ibus=from_bus, 
            jbus=to_bus, 
        )
        if ierr != 0:
            print(
                f"Error adding branch from {from_bus} to {to_bus}. PSS®E error code: {ierr}"
            )
            return

        print(f"Branch from {from_bus} to {to_bus} added successfully.")

        # Step 5: Run load flow and log voltages
        ierr = PSSeWrapper.psspy.fnsl()
        if ierr != 0:
            print(f"Error running load flow analysis. PSS®E error code: {ierr}")
        self.run_powerflow(self.solver)
        self.take_snapshot()

    def generate_load_curve(self, noise_level=0.002, time=None):
        """
        Generate a simple bell curve load profile.

        - Starts at initial P Load from the raw file.
        - Peaks slightly (~5% higher).
        - Returns to the original value.
        - No noise.

        Returns:
        - None (updates self.load_profiles).
        """

        df = self.bus_dataframe  # Get main dataframe
        if time is None:
            time_data = self.WecGridCore.wecObj_list[0].dataframe.time.to_list()
        else:
            time_data = time
        num_timesteps = len(time_data)

        # Get initial P Load values from raw file
        p_load_values = df.set_index("BUS_ID")["Pd"].fillna(0)

        # Set bell curve shape
        midpoint = num_timesteps // 2  # Peak at midpoint
        time_index = np.linspace(-1, 1, num_timesteps)  # Range from -1 to 1
        bell_curve = np.exp(-4 * time_index**2)  # Standard bell curve

        load_profiles = {}

        for bus_id, base_load in p_load_values.items():
            if base_load == 0:
                load_profiles[bus_id] = np.zeros(num_timesteps)
                continue

            # Scale bell curve: Peaks at ~5% higher than base load
            curve = base_load * (1 + 0.05 * bell_curve)
            
            noise = np.random.normal(0, noise_level * base_load, num_timesteps)
            curve += noise

            # Ensure first time step matches initial P Load exactly
            curve[0] = base_load

            # Store the generated curve
            load_profiles[bus_id] = curve

        # Create DataFrame with time as index and buses as columns
        self.load_profiles = pd.DataFrame(load_profiles, index=time_data)
    
    def run_powerflow(self, solver):
        """
        Description: This function runs the powerflow for PSSe for the given solver passed for the case in memory
        input:
             solver: the solver you want to use supported by PSSe, "fnsl" is a good default (str)
        output: None
        """
        sim_ierr = 1  # default there is an error

        if solver == "fnsl":
            sim_ierr = PSSeWrapper.psspy.fnsl()
        elif solver == "GS":
            sim_ierr = PSSeWrapper.psspy.solv()
        elif solver == "DC":
            sim_ierr = PSSeWrapper.psspy.dclf_2(1, 1, [1, 0, 1, 2, 1, 1], [0, 0, 0], "1")
        else:
            print("not a valid solver")
            return 0

        if sim_ierr == 0:  # no error in solving
            return PSSeWrapper.psspy.solved()
        else:
            print("Error while solving")
            return 1

        if ierr == 1:  # no error while grabbing values
            return 1
        else:
            print("Error while grabbing values")
            return 0

    # def store_p_flow(self, t):
    #     """
    #     Function to store the p_flow values of a grid network in a dictionary.

    #     Parameters:
    #     - t (float): Time at which the p_flow values are to be retrieved.
    #     """
    #     # Create an empty dictionary for this particular time
    #     p_flow_dict = {}

    #     try:
    #         ierr, (fromnumber, tonumber) = PSSeWrapper.psspy.abrnint(
    #             sid=-1, flag=3, string=["FROMNUMBER", "TONUMBER"]
    #         )

    #         for index in range(len(fromnumber)):
    #             ierr, p_flow = PSSeWrapper.psspy.brnmsc(
    #                 int(fromnumber[index]), int(tonumber[index]), "1", "P"
    #             )

    #             source = str(fromnumber[index]) if p_flow >= 0 else str(tonumber[index])
    #             target = str(tonumber[index]) if p_flow >= 0 else str(fromnumber[index])
    #             # print("{} -> {}".format(source, target))

    #             p_flow_dict[(source, target)] = p_flow

    #         # Store the p_flow data for this time in the flow_data dictionary
    #         self.flow_data[t] = p_flow_dict

    #     except Exception as e:
    #         print(f"Error fetching data: {e}")

    # def update_type(self):
    #     for wec in self.WecGridCore.wecObj_list:
    #         self.dataframe.loc[self.dataframe["BUS_ID"] == wec.bus_location, "Type"] = 4

    def update_load(self, time_step):
        """
        Update the load at each bus using `load_profiles` for a given time step.

        Parameters:
        - time_step (int): The time step index in `load_profiles`.

        Returns:
        - int: Error code from PSS/E API call.
        """
        
    
        if time_step not in self.load_profiles.index:
            print(f"Time step {time_step} not found in load_profiles.")
            return -1  # Error code

        for bus_id in self.load_profiles.columns:
            load_value = self.load_profiles.at[time_step, bus_id]  # Load in MW

            if np.isnan(load_value):
                load_value = 0.0  # Avoid NaN issues
                
            if load_value > 0:
                # Default load parameters
                _id = "1"
                realar = [load_value, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                lodtyp = "CONSTP"
                intgar = [1, 1, 1, 1, 1, 0, 0]


                # Update the load in PSS/E
                ierr = PSSeWrapper.psspy.load_data_6(ibus=int(bus_id), realar1=load_value)

                if ierr > 0:
                    print(f"Error updating load at bus {bus_id} for time step {time_step}")
                    return ierr

        return 0  # Success


    def ac_injection(self, start=None, end=None, p=None, v=None, time=None):
        # TODO: There has to be a better way to do this.
        # I think we should create a marine models obj list or dict and then iterate over that instead
        # of having two list?
        # WecGridCore.create_marine_model(type="wec", ID=11, model="RM3", bus_location=7)
        # instead of the list we have something like
        # marine_models = {11: {"type": "wec", "model": "RM3", "bus_location": 7} ,
        #                  12: {"type": "cec", "model": "Water Horse", "bus_location": 8}}
        """
        Description: WEC AC injection for PSSe powerflow solver
        input:
            p - a vector of active power values in order of bus num
            v - a vector of voltage mag PU values in order of bus num
            pf_solver - Power flow solving algorithm  (Default-"fnsl")
            time: (Int)
        output:
            no output but dataframe is updated and so is history
        """

        num_wecs = len(self.WecGridCore.wecObj_list)

        if time is None:
            time = self.WecGridCore.wecObj_list[0].dataframe.time.to_list()
        if start is None:
            start = time[0]
        if end is None:
            end = time[-1]
        for t in time:
            print(f"Running powerflow for time: {t}")
            if t >= start and t <= end:
                if num_wecs > 0:
                    for idx, wec_obj in enumerate(self.WecGridCore.wecObj_list):
                        bus = wec_obj.bus_location
                        machine_id = wec_obj.gen_id
                        
                        # get activate power from wec at time t
                        pg = float(wec_obj.dataframe.loc[wec_obj.dataframe.time == t].pg) 
                        # adjust activate power 
                        ierr = PSSeWrapper.psspy.machine_chng_4(
                            bus, machine_id, realar1=pg #, realar7=wec_obj.MBASE
                        )
                        if ierr > 0:
                            raise Exception("Error in adjust activate power")
                        
                        # ierr, rval = PSSeWrapper.psspy.macdat(bus, machine_id, 'MBASE')
                        # print(f"Machine {machine_id} MBASE: {rval}")
                        # ierr, rval = PSSeWrapper.psspy.macdat(bus, machine_id, 'P')
                        # print(f"Machine {machine_id} P: {rval}")
                self.update_load(t) 
                sim_ierr = PSSeWrapper.psspy.fnsl()
                
                ierr = PSSeWrapper.psspy.solved()
                self.take_snapshot(metadata={"Solver output": sim_ierr, "Solved Status": ierr})
                
            if t > end:
                break
        return

    def bus_history(self, bus_num):
        pass
        #TODO: update to work with new snapshat datatype

    def plot_bus(self, bus_num, time, arg_1="P", arg_2="Q"):
        """
        Description: This function plots the activate and reactive power for a given bus
        input:
            bus_num: the bus number we wanna viz (Int)
            time: a list with start and end time (list of Ints)
        output:
            matplotlib chart
        """
        #TODO: update to work with new snapshot datatype
        visualizer = PSSEVisualizer(psse_obj=self)
        visualizer.plot_bus(bus_num, time, arg_1, arg_2)

    # def plot_load_curve(self, bus_id):
    #     """
    #     Description: This function plots the load curve for a given bus
    #     input:
    #         bus_id: the bus number we want to visualize (Int)
    #     output:
    #         matplotlib chart
    #     """
    #     #TODO: update to work with new snapshot datatype
    #     # Check if the bus_id exists in load_profiles
    #     viz = PSSEVisualizer(
    #         dataframe=self.dataframe,
    #         history=self.history,
    #     )
    #     viz.plot_load_curve(bus_id)

    # def viz(self, dataframe=None):
    #     """ """
    #     #TODO: update to work with new snapshot datatype
    #     visualizer = PSSEVisualizer(psse_obj=self)  # need to pass this object itself?
    #     return visualizer.viz()

    # def get_flow_data(self, t=None):
    #     """
    #     Description:
    #     This method retrieves the power flow data for all branches in the power system at a given timestamp.
    #     If no timestamp is provided, the method fetches the data from PSS/E and returns it.
    #     If a timestamp is provided, the method retrieves the corresponding data from the dictionary and returns it.

    #     Inputs:
    #     - t (float): timestamp for which to retrieve the power flow data (optional)

    #     Outputs:
    #     - flow_data (dict): dictionary containing the power flow data for all branches in the power system
    #     """
    #     # If t is not provided, fetch data from PSS/E
    #     if t is None:
    #         flow_data = {}

    #         try:
    #             ierr, (fromnumber, tonumber) = self.psspy.abrnint(
    #                 sid=-1, flag=3, string=["FROMNUMBER", "TONUMBER"]
    #             )

    #             for index in range(len(fromnumber)):
    #                 ierr, p_flow = self.psspy.brnmsc(
    #                     int(fromnumber[index]), int(tonumber[index]), "1", "P"
    #                 )

    #                 edge_data = {
    #                     "source": str(fromnumber[index])
    #                     if p_flow >= 0
    #                     else str(tonumber[index]),
    #                     "target": str(tonumber[index])
    #                     if p_flow >= 0
    #                     else str(fromnumber[index]),
    #                     "p_flow": p_flow,
    #                 }

    #                 # Use a tuple (source, target) as a unique identifier for each edge
    #                 edge_identifier = (edge_data["source"], edge_data["target"])
    #                 flow_data[edge_identifier] = edge_data["p_flow"]
    #         except Exception as e:
    #             print(f"Error fetching data: {e}")

    #         # Assign the fetched data to the current timestamp and return it
    #         # self.flow_data[time.time()] = flow_data
    #         return flow_data

    #     # If t is provided, retrieve the corresponding data from the dictionary
    #     else:
    #         return self.flow_data.get(t, {})
        
        
    # '''
    # TODO: these function below need to be moved into PSSE-VIZ soon
    # '''
    def draw_transformer_arrow(self, ax, path):
        """
        Draws an arrow along the transformer connection path.
        The arrow direction follows the second movement segment.
        Adds "^^^" symbol above the arrow at the arrow tip.
        """
        if len(path) < 4:
            return  # Not enough points to draw an arrow

        # Select second segment for placing the arrow
        x1, y1 = path[2]
        x2, y2 = path[3]

        dx = (x2 - x1) * 0.3  # Scale down arrow length
        dy = (y2 - y1) * 0.3

        # **Compute arrow tip**
        arrow_tip_x = x1 + dx
        arrow_tip_y = y1 + dy

        # **Draw arrow**
        ax.add_patch(FancyArrow(x1, y1, dx, dy, width=0.005, head_width=0.02, head_length=0.02, color='blue'))

        # # **Place "^^^" symbol at arrow tip**
        # if dy == 0:  # Horizontal transformer
        #     ax.text(arrow_tip_x - 0.01, arrow_tip_y + 0.008, "^^^", fontsize=8, fontweight="bold", ha='center', va='center',rotation=90, color='blue')
        # else:  # Vertical transformer
        #     ax.text(arrow_tip_x - 0.005, arrow_tip_y - 0.01, "^^^", fontsize=8, fontweight="bold", ha='center', va='center', rotation=180, color='blue')
            
    def determine_connection_sides(self, from_bus, to_bus, from_pos, to_pos, bus_connections, used_connections):
        """
        Determines the best connection points for a given bus pair while avoiding overlapping connections.
        - Uses x and y positions to determine if the connection is horizontal (left/right) or vertical (top/bottom).
        - Selects an available connection within that side (inner, middle, outer) to reduce overlap.
        """

        y_tuner = 0.1  # Controls how strict we are about vertical vs. horizontal
        x_tuner = 0.48  # Controls how strict we are about left/right priority

        x1, y1 = from_pos
        x2, y2 = to_pos

        # --- Step 1: Determine primary connection direction ---
        if abs(x1 - x2) > abs(y1 - y2):  
            primary_connection = "horizontal"  # Mostly horizontal movement
        else:  
            primary_connection = "vertical"  # Mostly vertical movement

        # Adjust with tuners
        if abs(y1 - y2) < y_tuner:
            primary_connection = "horizontal"
        elif abs(x1 - x2) < x_tuner:
            primary_connection = "vertical"

        # --- Step 2: Determine connection points ---
        if primary_connection == "horizontal":
            if x1 < x2:  # Moving left → right
                from_side = "right"
                to_side = "left"
            else:  # Moving right → left
                from_side = "left"
                to_side = "right"
        else:  # Vertical Connection
            if y1 > y2:  # Moving top → bottom
                from_side = "bottom"
                to_side = "top"
            else:  # Moving bottom → top
                from_side = "top"
                to_side = "bottom"

        # **Select the best available connection point within the side**
        for priority in ["middle", "inner", "outer"]:  # Prioritize middle, then fallback
            from_point_key = f"{from_side}_{priority}"
            to_point_key = f"{to_side}_{priority}"

            if from_point_key not in used_connections[from_bus] and to_point_key not in used_connections[to_bus]:
                used_connections[from_bus].add(from_point_key)
                used_connections[to_bus].add(to_point_key)
                return bus_connections[from_bus][from_point_key], bus_connections[to_bus][to_point_key], f"{from_side}-{to_side}"

        # Fallback (shouldn't reach here unless something is wrong)
        return bus_connections[from_bus]["right_middle"], bus_connections[to_bus]["left_middle"], "fallback"

    def route_line(self, p1, p2, connection_type):
        """
        Creates an L-shaped or Z-shaped path between two points using right-angle bends.
        - Left/Right: Midpoint in X first, then Y.
        - Top/Bottom: Midpoint in Y first, then X.
        """
        x1, y1 = p1
        x2, y2 = p2

        if x1 == x2 or y1 == y2:
            return [p1, p2]  # Direct connection

        if connection_type in ["left-right", "right-left"]:
            mid_x = (x1 + x2) / 2  # First bend in X direction
            return [p1, (mid_x, y1), (mid_x, y2), p2]  # Two bends: X first, then Y

        elif connection_type in ["top-bottom", "bottom-top"]:
            mid_y = (y1 + y2) / 2  # First bend in Y direction
            return [p1, (x1, mid_y), (x2, mid_y), p2]  # Two bends: Y first, then X

        return [p1, p2]  # Default (fallback)

    def get_bus_color(self, bus_type):
        """ Returns the color for a given bus type. """
        color_map = {
            1: "#A9A9A9",  # Gray
            2: "#32CD32",  # Green
            3: "#FF4500",  # Red
            4: "#1E90FF",  # Blue
        }
        return color_map.get(bus_type, "#D3D3D3")  # Default light gray if undefined

    def sld(self):
        """
        Generates a structured single-line diagram with correct bus connection logic and predictable bends.
        Includes:
        - Loads (downward arrows)
        - Generators (circles above bus)
        """

        # --- Step 1: Extract Bus, Load, and Generator Data ---
        ierr, bus_numbers = self.psspy.abusint(-1, 1, "NUMBER")
        #ierr, bus_types = self.psspy.abusint(-1, 1, "TYPE")
        bus_type_df = self.bus_dataframe[["BUS_ID", "TYPE"]]
        
        ierr, (from_buses, to_buses) = self.psspy.abrnint(sid=-1, flag=3, string=["FROMNUMBER", "TONUMBER"])
        ierr, load_buses = self.psspy.aloadint(-1, 1, "NUMBER")  # Correct API for loads
        ierr, gen_buses = self.psspy.amachint(-1, 4, "NUMBER")  # Correct API for generators
        ierr, (xfmr_from_buses, xfmr_to_buses) = self.psspy.atrnint(
            sid=-1, owner=1, ties=3, flag=2, entry=1, string=["FROMNUMBER", "TONUMBER"]
        )
        xfmr_pairs = set(zip(xfmr_from_buses, xfmr_to_buses))

        # Convert lists to sets for quick lookup
        load_buses = set(load_buses[0]) if load_buses[0] else set()
        gen_buses = set(gen_buses[0]) if gen_buses[0] else set()

        # --- Step 2: Build Graph Representation ---
        G = nx.Graph()
        for bus in bus_numbers[0]:
            G.add_node(bus)
        for from_bus, to_bus in zip(from_buses, to_buses):
            G.add_edge(from_bus, to_bus)

        # --- Step 3: Compute Layout ---
        pos = nx.kamada_kawai_layout(G)

        # Normalize positions for even spacing
        pos_values = np.array(list(pos.values()))
        x_vals, y_vals = pos_values[:, 0], pos_values[:, 1]
        x_min, x_max = np.min(x_vals), np.max(x_vals)
        y_min, y_max = np.min(y_vals), np.max(y_vals)
        for node in pos:
            pos[node] = (
                2 * (pos[node][0] - x_min) / (x_max - x_min) - 1,
                1.5 * (pos[node][1] - y_min) / (y_max - y_min) - 0.5
            )

        # --- Step 4: Create Visualization ---
        fig, ax = plt.subplots(figsize=(14, 10))
        node_width, node_height = 0.12, 0.04

        # Store predefined connection points for each bus
        bus_connections = {}
        used_connections = {bus: set() for bus in bus_numbers[0]}  # Track used connections
        for bus in bus_numbers[0]:
            x, y = pos[bus]
            bus_connections[bus] = {
                # Left side (3 points)
                "left_inner": (x - node_width / 2, y - node_height / 3),
                "left_middle": (x - node_width / 2, y),
                "left_outer": (x - node_width / 2, y + node_height / 3),

                # Right side (3 points)
                "right_inner": (x + node_width / 2, y - node_height / 3),
                "right_middle": (x + node_width / 2, y),
                "right_outer": (x + node_width / 2, y + node_height / 3),

                # Top side (3 points)
                "top_inner": (x - node_width / 3, y + node_height / 2),
                "top_middle": (x, y + node_height / 2),
                "top_outer": (x + node_width / 3, y + node_height / 2),

                # Bottom side (3 points)
                "bottom_inner": (x - node_width / 3, y - node_height / 2),
                "bottom_middle": (x, y - node_height / 2),
                "bottom_outer": (x + node_width / 3, y - node_height / 2),
            }

        # Draw right-angle connections based on simplified logic
        for from_bus, to_bus in zip(from_buses, to_buses):
            from_pos = pos[from_bus]
            to_pos = pos[to_bus]

            try:
                p1, p2, ctype = self.determine_connection_sides(from_bus, to_bus, from_pos, to_pos, bus_connections, used_connections)
            except KeyError:
                continue

            path = self.route_line(p1, p2, ctype)

            # Draw path segments
            for i in range(len(path) - 1):
                ax.plot([path[i][0], path[i+1][0]], [path[i][1], path[i+1][1]], 'k-', lw=1.5, linestyle="dashed")
            
            if (from_bus, to_bus) in xfmr_pairs or (to_bus, from_bus) in xfmr_pairs:
                self.draw_transformer_arrow(ax, path)  # Attach arrow to 2nd segment of the path
                #draw_transformer_marker(ax, path)  # Attach diamond marker to midpoint of the path

                
        # Draw bus rectangles
        for bus in bus_numbers[0]:
            x, y = pos[bus]
            #temp = bus_numbers[0].index(bus)
            
            bus_type = bus_type_df.loc[bus_type_df["BUS_ID"] == bus, "TYPE"].values[0]
            bus_color = self.get_bus_color(bus_type)
            
            #bus_color = self.get_bus_color()
            
            rect = Rectangle((x - node_width / 2, y - node_height / 2), node_width, node_height,
                            linewidth=1.5, edgecolor='black', facecolor=bus_color)
            ax.add_patch(rect)
            ax.text(x, y, str(bus), fontsize=8, fontweight="bold", ha='center', va='center')

            # Draw loads (right-offset downward arrows)
            if bus in load_buses:
                ax.arrow(x + node_width / 2 - 0.02, y + 0.02, 0, 0.05, head_width=0.02, head_length=0.02, fc='black', ec='black')

            # Draw generators (left-offset circles above bus)
            if bus in gen_buses:
                gen_x = x - node_width / 2 + 0.02  # Move generator left
                gen_y = y + node_height / 2 + 0.05
                gen_size = 0.02
                ax.plot([gen_x, gen_x], [y + node_height / 2 + 0.005, gen_y - gen_size ], color='black', lw=2)
                ax.add_patch(Circle((gen_x, gen_y), gen_size, color='none', ec='black', lw=1.5))
        
    


        ax.set_aspect('equal', adjustable='datalim')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)
        ax.set_title(f"Generated Single-Line Diagram of {self.case_file}", fontsize=14)
        # Extract the final file name without path and extension
        case_file_name = os.path.splitext(os.path.basename(self.case_file))[0]
        ax.set_title(f"Generated Single-Line Diagram of {case_file_name}", fontsize=14)
        # Define legend elements
        legend_elements = [
            Line2D([0], [0], marker='o', color='black', markersize=8, label="Generator", markerfacecolor='none', markeredgecolor='black', lw=0),
            Line2D([0], [0], marker=('^'), color='blue', markersize=10, label="Transformer", markerfacecolor='blue', lw=0),
            Line2D([0], [0], marker='^', color='black', markersize=10, label="Load", markerfacecolor='black', lw=0),
            Line2D([0], [0], marker='s', color='red', markersize=10, label="SwingBus", markerfacecolor='red', lw=0),
            Line2D([0], [0], marker='s', color='blue', markersize=10, label="WEC Bus", markerfacecolor='blue', lw=0),
            Line2D([0], [0], marker='s', color='green', markersize=10, label="PV Bus", markerfacecolor='green', lw=0),
            Line2D([0], [0], marker='s', color='gray', markersize=10, label="PQ Bus", markerfacecolor='gray', lw=0),
        ]

        # Add the legend at the bottom-right
        ax.legend(handles=legend_elements, loc="upper left", fontsize=10, frameon=True, edgecolor='black', title="Legend")
        plt.show()