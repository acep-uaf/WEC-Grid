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

# Local Libraries (updated with relative imports)
from ..utilities.util import read_paths  # Relative import for utilities/util.py
from ..viz.psse_viz import PSSEVisualizer  # Relative import for viz/psse_viz.py

# Initialize the PATHS dictionary
# PATHS = read_paths()
CURR_DIR = os.path.dirname(os.path.abspath(__file__))

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
        self.dataframe = pd.DataFrame()
        self.history = {}
        self.z_history = {}
        self.flow_data = {}
        self.WecGridCore = WecGridCore  # Reference to the parent WecGrid
        self.lst_param = ["BASE", "PU", "ANGLE", "MISMATCH", "P", "Q"]
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
            import psse35
            import psspy

            psse35.set_minor(3)
            psspy.psseinit(50)
        except ModuleNotFoundError as e:
            print(
                "Error: PSSE modules not found. Ensure PSSE is installed and paths are configured."
            )
            raise e

        # Initialize PSSE object
        PSSeWrapper.psspy = psspy
        psspy.report_output(islct=2, filarg="NUL", options=[0])

        self.history = {}
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
            self.history[-1] = self.dataframe
            self.z_values(time=-1)
            self.store_p_flow(t=-1)
            return 1
        else:
            print("Error running power flow.")
            return 0

    def clear(self):
        """
        Description: This function clears all the data and resets the variables of the PSSe valuables
        input: None
        output: None
        """
        # initalized variables and files
        self.lst_param = ["PU", "P", "Q"]
        self.dataframe = pd.DataFrame()
        self.history = {}
        # initialization functions
        PSSeWrapper.psspy.read(1, self.case_file)
        self.run_powerflow(self.solver)
        # program variables
        # self.history['Start'] = self.dataframe
        
    def get_sbase(self):
        return PSSeWrapper.psspy.sysmva()

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
        # Create a name for this WEC system
        name = f"{model}-{to_bus}"

        from_bus_voltage = PSSeWrapper.psspy.busdat(from_bus, "BASE")[1]

        # Step 1: Add a new bus
        intgar_bus = [2, 1, 1, 1]  # Bus type, area, zone, owner
        realar_bus = [
            from_bus_voltage,
            1.0,
            0.0,
            1.05,
            0.95,
            1.1,
            0.9,
        ]  # Base voltage, magnitude, etc.
        ierr = PSSeWrapper.psspy.bus_data_4(
            to_bus, inode=0, intgar=intgar_bus, realar=realar_bus, name=name
        )
        if ierr != 0:
            print(f"Error adding bus {to_bus}. PSS®E error code: {ierr}")
            return

        print(f"Bus {to_bus} added successfully.")

        # Step 2: Add plant data
        intgar_plant = [0, 0]  # No remote voltage regulation
        realar_plant = [
            1.0,
            10.0,
        ]  # Scheduled voltage = 1.0, max reactive contribution = 10 MVar
        ierr = PSSeWrapper.psspy.plant_data_4(to_bus, 0, intgar_plant, realar_plant)
        if ierr == 0:
            print(f"Plant data added successfully to bus {to_bus}.")
        else:
            print(f"Error adding plant data to bus {to_bus}. PSS®E error code: {ierr}")
            return

        for i, wec_obj in enumerate(self.WecGridCore.wecObj_list):
            # Step 3: Add a generator at the new bus
            intgar_gen = [1, 1, 0, 0, 0, 0, 0]  # Generator status, ownership
            # realar_gen = [
            #     0.0,  # PG: Active power generation
            #     0.0,  # QG: Reactive power generation
            #     1.0,  # QT (upper reactive power limit)
            #     -1.0,  # QB (lower reactive power limit)
            #     3.0,  # PT (upper active power limit)
            #     -0.0,  # PB (lower active power limit, 0 means no negative generation)
            #     #self.WecGridCore.wecObj_list[0].MBASE,  #this is a hack, this should be added per wec. 
            #     0.,  # MBASE: MVA base for generator TODO: Check this value, should be passed in ??
            #     0.005,  # ZR: Small internal resistance (pu)
            #     0.1,  # ZX: Small reactance (pu)
            #     0.0,  # RT: Step-up transformer resistance (optional)
            #     0.0,  # XT: Step-up transformer reactance (optional)
            #     1.0,  # GTAP: Tap ratio (1.0 means no change)
            #     1.0,  # F1: First owner fraction
            #     0.0,  # F2: Second owner fraction
            #     0.0,  # F3: Third owner fraction
            #     0.0,  # F4: Fourth owner fraction
            #     0.0,  # WPF: Non-conventional machine power factor (0 for conventional)
            # ]
            realar_gen = [
                0.0,    # PG: Active power generation (pu)
                0.0,    # QG: Reactive power generation (pu)
                1.0,    # QT (upper reactive power limit)
                -1.0,   # QB (lower reactive power limit)
                3.0,    # PT (upper active power limit)
                0.0,    # PB (lower active power limit)
                wec_obj.MBASE,   # MBASE: Machine base power in MVA (10 kW)
                0.005,  # ZR: Small internal resistance (pu)
                0.1,    # ZX: Small reactance (pu)
                0.0,    # RT: Transformer resistance (optional)
                0.0,    # XT: Transformer reactance (optional)
                1.0,    # GTAP: Tap ratio (1.0 means no change)
                1.0,    # F1: First owner fraction
                0.0,    # F2: Second owner fraction
                0.0,    # F3: Third owner fraction
                0.0,    # F4: Fourth owner fraction
                0.0,    # WPF: Non-conventional machine power factor (0 for conventional)
            ]
            wec_obj.gen_id = f'G{i+1}'
            ierr = PSSeWrapper.psspy.machine_data_4(to_bus, wec_obj.gen_id, intgar_gen, realar_gen)
            #wec_obj.gen_id = str(i+1)

            if ierr != 0:
                print(
                    f"Error adding generator {wec_obj.gen_id} to bus {to_bus}. PSS®E error code: {ierr}"
                )
                return

            print(f"Generator {wec_obj.gen_id} added successfully to bus {to_bus}.")

        # Step 4: Add a branch (line) connecting the existing bus to the new bus
        ckt_id = "1"  # Circuit identifier
        intgar_branch = [1, 1, 0, 0, 0, 0]  # Owner, branch status, metered end, etc.
        realar_branch = [
            0.05,  # R (resistance)
            0.15,  # X (reactance)
            0.0,  # B (line charging)
            0.0,  # GI (real line shunt at from bus)
            0.0,  # BI (reactive line shunt at from bus)
            0.0,  # GJ (real line shunt at to bus)
            0.0,  # BJ (reactive line shunt at to bus)
            0.0,  # LEN (line length)
            1.0,  # F1 (owner fraction)
            0.0,  # F2 (second owner fraction)
            0.0,  # F3 (third owner fraction)
            0.0,  # F4 (fourth owner fraction)
        ]
        ierr = PSSeWrapper.psspy.branch_data_3(from_bus, to_bus, ckt_id)
        if ierr != 0:
            print(
                f"Error adding branch from {from_bus} to {to_bus}. PSS®E error code: {ierr}"
            )
            return

        print(f"Branch from {from_bus} to {to_bus} added successfully.")

        # Step 5: Run load flow and log voltages
        ierr = PSSeWrapper.psspy.fnsl()
        if ierr == 0:
            _, from_bus_voltage = PSSeWrapper.psspy.busdat(from_bus, "PU")
            _, to_bus_voltage = PSSeWrapper.psspy.busdat(to_bus, "PU")
            print(f"Voltage at bus {from_bus}: {from_bus_voltage:.4f} p.u.")
            print(f"Voltage at bus {to_bus}: {to_bus_voltage:.4f} p.u.")
        else:
            print(f"Error running load flow analysis. PSS®E error code: {ierr}")

        self.run_powerflow(self.solver)

        t = -1
        self.update_type()  # TODO: check if I need this still. I think i update the type when I create the models
        self.history[t] = self.dataframe
        self.z_values(time=t)
        self.store_p_flow(t)
        
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

        df = self.dataframe  # Get main dataframe
        if time is None:
            time_data = self.WecGridCore.wecObj_list[0].dataframe.time.to_list()
        else:
            time_data = time
        num_timesteps = len(time_data)

        # Get initial P Load values from raw file
        p_load_values = df.set_index("Bus")["P Load"].fillna(0)

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
            ierr = self.get_values()
            return 0 # all good 
        else:
            print("Error while solving")
            return 1

        if ierr == 1:  # no error while grabbing values
            return 1
        else:
            print("Error while grabbing values")
            return 0

    def get_values(self):
        """
        Description: This function grabs all the important values we want in our dataframe
        input: None, uses lst_param tho
        output: Dataframe of the selected parameters for each bus.
        """
        lst = self.lst_param
        temp_dict = {}
        for bus_parameter in lst:
            if bus_parameter != "P" and bus_parameter != "Q":
                # grabs the bus parameter values for the specified parameter - list
                ierr, bus_parameter_values = PSSeWrapper.psspy.abusreal(
                    -1, string=bus_parameter
                )
                if ierr != 0:
                    print("error in get_values function")
                    return 0
                bus_add = {}
                for bus_index, value in enumerate(
                    bus_parameter_values[0]
                ):  # loops over those values to create bus num & value pairs
                    bus_add["BUS {}".format(bus_index + 1)] = value
                temp_dict[bus_parameter] = bus_add

        self.dataframe = pd.DataFrame.from_dict(temp_dict)
        self.dataframe = self.dataframe.reset_index()
        self.dataframe = self.dataframe.rename(columns={"index": "Bus"})
        # gets the bus type (3 = swing)
        self.dataframe["Type"] = PSSeWrapper.psspy.abusint(-1, string="TYPE")[1][0]
        self.dataframe.insert(0, "BUS_ID", range(1, 1 + len(self.dataframe)))
        self.addGeninfo()
        self.addLoadinfo()

        if "P" in lst:
            self.get_p_or_q("P")
        if "Q" in lst:
            self.get_p_or_q("Q")

        # Check if column exists, if not then initialize
        if "ΔP" not in self.dataframe.columns:
            self.dataframe["ΔP"] = 0.0  # default value
        if "ΔQ" not in self.dataframe.columns:
            self.dataframe["ΔQ"] = 0.0  # default value
        if "M_Angle" not in self.dataframe.columns:
            self.dataframe["M_Angle"] = 0.0  # default value
        if "M_Mag" not in self.dataframe.columns:
            self.dataframe["M_Mag"] = 0.0  # default value

        # Your loop remains unchanged
        for index, row in self.dataframe.iterrows():
            mismatch = PSSeWrapper.psspy.busmsm(row["BUS_ID"])[1]
            self.dataframe.at[index, "ΔP"] = mismatch.real  # should be near zero
            self.dataframe.at[index, "ΔQ"] = mismatch.imag
            self.dataframe.at[index, "M_Angle"] = abs(mismatch)
            self.dataframe.at[index, "M_Mag"] = cmath.phase(mismatch)
        return 1

    def get_p_or_q(self, letter):
        """
        Description: retrieves P (activate) or Q (reactive) Voltage (in PU) and Voltage Angle for each Bus in the current loaded case
        input:
            letter: either P or Q as a string
        output: None
        """
        gen_values = self.dataframe["{} Gen".format(letter)]  #
        load_values = self.dataframe["{} Load".format(letter)]
        letter_list = [None] * len(self.dataframe)

        for i in range(len(letter_list)):
            gen = gen_values[i]
            load = load_values[i]
            if (not pd.isnull(gen)) and (not pd.isnull(load)):
                letter_list[i] = gen - load
            else:
                if not pd.isnull(gen):
                    letter_list[i] = gen
                if not pd.isnull(load):
                    letter_list[i] = 0 - load  # gen is
        self.dataframe["{}".format(letter)] = letter_list

    def busNum(self):
        """
        Description: Returns the number of Buses in the currently loaded case
        input: None
        output: Number of Buses
        """
        PSSeWrapper.psspy.bsys(0, 0, [0.0, 0.0], 1, [1], 0, [], 0, [], 0, [])
        ierr, all_bus = PSSeWrapper.psspy.abusint(0, 1, ["number"])
        return all_bus[0]

    def addGeninfo(self):
        """
        Description: This function grabs the generator values from the PSSe system and updates the dataframe with the generator data.
        Input: None
        Output: None but updates dataframe with generator data
        """
        machine_bus_nums = PSSeWrapper.psspy.amachint(-1, 4, "NUMBER")[1][
            0
        ]  # get the bus numbers of the machines - list
        # grabs the complex values for the machine
        ierr, machine_bus_values = PSSeWrapper.psspy.amachcplx(-1, 1, "PQGEN")
        if ierr != 0:
            raise Exception("Error in grabbing PGGEN values in addgen function")
        p_gen_df_list = [None] * len(self.dataframe)
        q_gen_df_list = [None] * len(self.dataframe)
        # iterate over the machine values
        for list_index, value in enumerate(machine_bus_values[0]):
            p_gen_df_list[
                machine_bus_nums[list_index] - 1
            ] = value.real  # -1 is for the offset
            q_gen_df_list[machine_bus_nums[list_index] - 1] = value.imag

        self.dataframe["P Gen"] = p_gen_df_list
        self.dataframe["Q Gen"] = q_gen_df_list

    def addLoadinfo(self):
        """
        Description: this function grabs the load values from the PSSe system
        input: None
        output: None but updates dataframe with load data
        """
        load_bus_nums = PSSeWrapper.psspy.aloadint(-1, 4, "NUMBER")[1][
            0
        ]  # get the bus numbers of buses with loads - list
        ierr, load_bus_values = PSSeWrapper.psspy.aloadcplx(
            -1, 1, "MVAACT"
        )  # load values
        if ierr != 0:
            raise Exception("Error in grabbing PGGEN values in addgen function")
        p_load_df_list = [None] * len(self.dataframe)
        q_load_df_list = [None] * len(self.dataframe)

        # iterate over the machine values
        for list_index, value in enumerate(load_bus_values[0]):
            p_load_df_list[
                load_bus_nums[list_index] - 1
            ] = value.real  # -1 is for the offset
            q_load_df_list[load_bus_nums[list_index] - 1] = value.imag
        self.dataframe["P Load"] = p_load_df_list
        self.dataframe["Q Load"] = q_load_df_list

    def z_values(self, time):
        """
        Retrieve the impedance values for each branch in the power grid at a given time.

        Parameters:
        - time (float): The time at which to retrieve the impedance values.

        Returns:
        - None. The impedance values are stored in the `z_history` attribute of the object.
        """
        # Retrieve FROMNUMBER and TONUMBER for all branches
        ierr, (from_numbers, to_numbers) = PSSeWrapper.psspy.abrnint(
            sid=-1, flag=3, string=["FROMNUMBER", "TONUMBER"]
        )
        assert ierr == 0, "Error retrieving branch data"

        # Create a dictionary to store the impedance values for each branch
        impedances = {}

        for from_bus, to_bus in zip(from_numbers, to_numbers):
            ickt = "1"  # Assuming a default circuit identifier; might need adjustment for your system

            ierr, cmpval = PSSeWrapper.psspy.brndt2(from_bus, to_bus, ickt, "RX")
            if ierr == 0:
                impedances[
                    (from_bus, to_bus)
                ] = cmpval  # Store the complex impedance value directly
            else:
                print(f"Error fetching impedance data for branch {from_bus}-{to_bus}")

        # The impedances dictionary contains impedance for each branch
        self.z_history[time] = impedances

    def store_p_flow(self, t):
        """
        Function to store the p_flow values of a grid network in a dictionary.

        Parameters:
        - t (float): Time at which the p_flow values are to be retrieved.
        """
        # Create an empty dictionary for this particular time
        p_flow_dict = {}

        try:
            ierr, (fromnumber, tonumber) = PSSeWrapper.psspy.abrnint(
                sid=-1, flag=3, string=["FROMNUMBER", "TONUMBER"]
            )

            for index in range(len(fromnumber)):
                ierr, p_flow = PSSeWrapper.psspy.brnmsc(
                    int(fromnumber[index]), int(tonumber[index]), "1", "P"
                )

                source = str(fromnumber[index]) if p_flow >= 0 else str(tonumber[index])
                target = str(tonumber[index]) if p_flow >= 0 else str(fromnumber[index])
                # print("{} -> {}".format(source, target))

                p_flow_dict[(source, target)] = p_flow

            # Store the p_flow data for this time in the flow_data dictionary
            self.flow_data[t] = p_flow_dict

        except Exception as e:
            print(f"Error fetching data: {e}")

    def update_type(self):
        for wec in self.WecGridCore.wecObj_list:
            self.dataframe.loc[self.dataframe["BUS_ID"] == wec.bus_location, "Type"] = 4

    def run_dynamics(self, dyr_file=""):
        import numpy as np

        """
        Description: This function is a wrapper around the dynamic modeling process in PSSe, this function checks for .dyr file and
        then proceeds to run a simple simulations.
        input: you can add dyr file path or the function will just ask you via CL
        output: None
        """

        output_file = "./simulation_output_file.out"
        solved_case = "solved_case.sav"

        # check if dynamic file is loaded
        if self.dynamic_case_file == "":
            self.c = input("Dynamic File location")

        PSSeWrapper.psspy.dyre_new(dyrefile=dyr_file)
        PSSeWrapper.psspy.fnsl()
        PSSeWrapper.psspy.save(solved_case)

        # Setup for dynamic simulation
        PSSeWrapper.psspy.cong(0)
        PSSeWrapper.psspy.ordr(0)
        PSSeWrapper.psspy.fact()
        PSSeWrapper.psspy.tysl(0)

        # Add channels (e.g., bus voltage, machine speed)
        PSSeWrapper.psspy.chsb(
            sid=0, all=1, status=[-1, -1, -1, 1, 13, 0]
        )  # Bus voltage
        PSSeWrapper.psspy.chsb(
            sid=0, all=1, status=[-1, -1, -1, 1, 7, 0]
        )  # Machine speed
        PSSeWrapper.psspy.chsb(sid=0, all=1, status=[-1, -1, -1, 1, 1, 0])  # ANGLE
        PSSeWrapper.psspy.chsb(sid=0, all=1, status=[-1, -1, -1, 1, 12, 0])  # bus freq

        # Start recording to output file and run dynamic simulation
        PSSeWrapper.psspy.strt(outfile=output_file)
        end_time = 10  #
        time_step = 0.01 / end_time  # Half-cycle step
        for current_time in np.arange(0, end_time, time_step):
            PSSeWrapper.psspy.run(tpause=current_time)
            # if current_time == 1.0:
            #     psspy.dist_branch_trip(1, 5, '1')
            # if current_time == 5.0:
            #     psspy.dist_branch_close(1, 5,'1')

        PSSeWrapper.psspy.save("final_state_after_dynamic_sim.sav")

    def plot_simulation_results(self, output_file, channels):
        import dyntools
        import numpy as np

        chnf_obj = dyntools.CHNF(output_file)
        _, channel_ids, channel_data = chnf_obj.get_data()
        base_frequency = 60.0  # Hz

        plt.figure(figsize=(10, 6))

        # Assuming channels for generator frequencies are correctly numbered

        for ch in channels:
            frequency_deviation = np.array(channel_data[ch])
            time_array = np.array(channel_data["time"])
            actual_frequency = 60.0 * (1 + frequency_deviation)

            plt.plot(time_array, actual_frequency, label=f"Channel {ch} Frequency")

        plt.xlabel("Time (s)")
        plt.ylabel("Frequency (Hz)")
        plt.title("Generator Frequency Over Time")
        plt.legend()
        plt.grid(True)
        plt.ylim(59.96, 60.012)
        plt.show()
        return plt

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
                ierr = PSSeWrapper.psspy.load_data_6(ibus=int(bus_id.split()[1]), realar1=load_value)

                if ierr > 0:
                    print(f"Error updating load at bus {bus_id} for time step {time_step}")
                    return ierr

        return 0  # Success

    def steady_state(self, gen, load, time, solver):

        for bus, gen_values in gen.items():
            pg = gen_values[0]  # pg
            ierr = PSSeWrapper.psspy.machine_data_4(
                bus, "1", realar1=pg, realar3=gen_values[2], realar4=gen_values[3]
            )  # adjust activate power
            if ierr > 0:
                raise Exception("Error in AC injection")
            vs = gen_values[1]  # vs
            ierr = PSSeWrapper.psspy.bus_chng_4(
                bus, 0, realar2=vs
            )  # adjsut voltage mag PU
            if ierr > 0:
                raise Exception("Error in AC injection")
            print("gen at bus {} is {} at time {}".format(bus, pg, time))

        for bus, load_value in load.items():
            ierr = PSSeWrapper.psspy.load_data_6(
                bus, "1", realar1=load_value["P"], realar2=load_value["Q"]
            )

        self.run_powerflow(solver)
        self.update_type()
        self.history[time] = self.dataframe

    def ac_injection(self, start, end, p=None, v=None, time=None):
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
        num_cecs = len(self.WecGridCore.cecObj_list)

        if time is None:
            time = self.WecGridCore.wecObj_list[0].dataframe.time.to_list()
        for t in time:
            # print("time: {}".format(t))
            if t >= start and t <= end:
                if num_wecs > 0:
                    for idx, wec_obj in enumerate(self.WecGridCore.wecObj_list):
                        bus = wec_obj.bus_location
                        machine_id = wec_obj.gen_id
                        pg = float(
                            wec_obj.dataframe.loc[wec_obj.dataframe.time == t].pg
                        ) 
                        
                        # adjust activate power
                        ierr = PSSeWrapper.psspy.machine_data_4(
                            bus, machine_id, realar1=pg
                        )  # adjust activate power
                        if ierr > 0:
                            raise Exception("Error in AC injection")
                        
                                # adjust activate power
                        ierr = PSSeWrapper.psspy.machine_data_4(
                            bus, machine_id, realar5=pg
                        )  # adjust activate power
                        
                        if ierr > 0:
                            raise Exception("Error in AC injection")
                        
                        
                        vs = float(
                            wec_obj.dataframe.loc[wec_obj.dataframe.time == t].vs
                        )
                        ierr = PSSeWrapper.psspy.bus_chng_4(
                            bus, 0, realar2=vs
                        )  # adjsut voltage mag PU
                        if ierr > 0:
                            raise Exception("Error in AC injection")

                        # self.run_powerflow(self.solver)
                        
                        print("===============")
                if num_cecs > 0:  # TODO: Issue with the CEC data
                    if t in self.WecGridCore.wecObj_list[0].dataframe["time"].values:
                        for idx, cec_obj in enumerate(self.WecGridCore.cecObj_list):
                            bus = cec_obj.bus_location
                            pg = cec_obj.dataframe.loc[
                                cec_obj.dataframe.time == t
                            ].pg  # adjust activate power
                            ierr = PSSeWrapper.psspy.machine_data_2(
                                bus, "1", realar1=pg
                            )  # adjust activate power
                            if ierr > 0:
                                raise Exception("Error in AC injection")
                            vs = wec_obj.dataframe.loc[wec_obj.dataframe.time == t].vs
                            ierr = PSSeWrapper.psspy.bus_chng_4(
                                bus, 0, realar2=vs
                            )  # adjsut voltage mag PU
                            if ierr > 0:
                                raise Exception("Error in AC injection")

                            # self.run_powerflow(self.solver)
                        #     #print("=======")
                self.update_load(t) 
                ierr = self.run_powerflow(self.solver)
                if ierr > 0:
                    raise Exception("Error in AC injection")
                    return ierr # ierr code
                self.update_type()  # TODO: check if I need this still. I think i update the type when I create the models
                self.history[t] = self.dataframe
                self.z_values(time=t)
                self.store_p_flow(t)
                print("time: {} - error code: {}".format(t, ierr))
            if t > end:
                break
        return

    def bus_history(self, bus_num):
        """
        Description: this function grab all the data associated with a bus through the simulation
        input:
            bus_num: bus number (Int)
        output:
            bus_dataframe: a pandas dateframe of the history
        """
        # maybe I should add a filering parameter?

        bus_dataframe = pd.DataFrame()
        for time, df in self.history.items():
            temp = pd.DataFrame(df.loc[df["BUS_ID"] == bus_num])
            temp.insert(0, "time", time)
            bus_dataframe = bus_dataframe.append(temp)
        return bus_dataframe

    def plot_bus(self, bus_num, time, arg_1="P", arg_2="Q"):
        """
        Description: This function plots the activate and reactive power for a given bus
        input:
            bus_num: the bus number we wanna viz (Int)
            time: a list with start and end time (list of Ints)
        output:
            matplotlib chart
        """
        visualizer = PSSEVisualizer(psse_obj=self)
        visualizer.plot_bus(bus_num, time, arg_1, arg_2)

    def plot_load_curve(self, bus_id):
        """
        Description: This function plots the load curve for a given bus
        input:
            bus_id: the bus number we want to visualize (Int)
        output:
            matplotlib chart
        """
        # Check if the bus_id exists in load_profiles
        viz = PSSEVisualizer(
            dataframe=self.dataframe,
            history=self.history,
            # load_profiles=self.load_profiles,
            # flow_data=self.flow_data,
        )
        viz.plot_load_curve(bus_id)

    def viz(self, dataframe=None):
        """ """
        visualizer = PSSEVisualizer(psse_obj=self)  # need to pass this object itself?
        return visualizer.viz()

    def adjust_gen(self, bus_num, p=None, v=None, q=None):
        """
        Description: Given a generator bus number. Adjust the values based on the parameters passed.
        input:
        output:
        """

        if p is not None:
            ierr = PSSeWrapper.psspy.machine_data_2(
                bus_num, "1", realar1=p
            )  # adjust activate power
            if ierr > 0:
                raise Exception("Error in AC injection")

        if v is not None:
            ierr = PSSeWrapper.psspy.bus_chng_4(
                bus_num, 0, realar2=v
            )  # adjsut voltage mag PU
            if ierr > 0:
                raise Exception("Error in AC injection")

        if q is not None:
            ierr = PSSeWrapper.psspy.machine_data_2(
                bus_num, "1", realar2=q
            )  # adjust Reactivate power
            if ierr > 0:
                raise Exception("Error in AC injection")

    def get_flow_data(self, t=None):
        """
        Description:
        This method retrieves the power flow data for all branches in the power system at a given timestamp.
        If no timestamp is provided, the method fetches the data from PSS/E and returns it.
        If a timestamp is provided, the method retrieves the corresponding data from the dictionary and returns it.

        Inputs:
        - t (float): timestamp for which to retrieve the power flow data (optional)

        Outputs:
        - flow_data (dict): dictionary containing the power flow data for all branches in the power system
        """
        # If t is not provided, fetch data from PSS/E
        if t is None:
            flow_data = {}

            try:
                ierr, (fromnumber, tonumber) = self.psspy.abrnint(
                    sid=-1, flag=3, string=["FROMNUMBER", "TONUMBER"]
                )

                for index in range(len(fromnumber)):
                    ierr, p_flow = self.psspy.brnmsc(
                        int(fromnumber[index]), int(tonumber[index]), "1", "P"
                    )

                    edge_data = {
                        "source": str(fromnumber[index])
                        if p_flow >= 0
                        else str(tonumber[index]),
                        "target": str(tonumber[index])
                        if p_flow >= 0
                        else str(fromnumber[index]),
                        "p_flow": p_flow,
                    }

                    # Use a tuple (source, target) as a unique identifier for each edge
                    edge_identifier = (edge_data["source"], edge_data["target"])
                    flow_data[edge_identifier] = edge_data["p_flow"]
            except Exception as e:
                print(f"Error fetching data: {e}")

            # Assign the fetched data to the current timestamp and return it
            # self.flow_data[time.time()] = flow_data
            return flow_data

        # If t is provided, retrieve the corresponding data from the dictionary
        else:
            return self.flow_data.get(t, {})

    def _psse_dc_injection(self, ibus, p, pf_solver, time):
        """
        Description: preforms the DC injection of the wec buses
        input:
            p: a list of active power set point in order(list)
            pf_solver: supported PSSe solver (Str)
            time: (Int)
        output: None
        """
        ierr = WecGridCore.psspy.machine_chng_3(ibus, "1", [], [p])
        if ierr > 0:
            print("Failed | machine_chng_3 code = {}".format(ierr))
        # psspy.dclf_2(status4=2)
        ierr = WecGridCore.psspy.dclf_2(1, 1, [1, 0, 1, 2, 0, 1], [0, 0, 1], "1")
        if ierr > 0:
            raise Exception("Error in DC injection")
        self._psse_get_values()
        self.history[time] = self.dataframe
