"""
WEC Class module file
"""

import os
import pandas as pd
import numpy as np
import matlab.engine

# Updated local imports with relative paths
from ..utilities.util import read_paths, dbQuery  # Combine related imports
from ..database_handler.connection_class import DB_PATH  # Relative import for DB_PATH

# Initialize the PATHS dictionary
PATHS = read_paths()


class WEC:
    """
    This class represents a WEC (Wave Energy Converter).

    Attributes:
        sim_id (int): The ID of the WEC.
        bus_location (str): The location of the bus.
        model (str): The model of the WEC.
        dataframe (DataFrame): The pandas DataFrame holding WEC data.
        Pmax (float): The maximum P value, defaults to 9999.
        Pmin (float): The minimum P value, defaults to -9999.
        Qmax (float): The maximum Q value, defaults to 9999.
        Qmin (float): The minimum Q value, defaults to -9999.
    """

    def __init__(self, engine, sim_id, model, bus_location, Pmax=9999, Pmin=-9999, Qmax=9999, Qmin=-9999, MBASE=0.1,config=None):
        self.engine = engine
        self.ID = sim_id
        self.bus_location = bus_location
        self.model = model
        self.dataframe = pd.DataFrame()
        self.MBASE = MBASE # default value for MBASE is 10 KW 
        self.Pmax = Pmax
        self.Pmin = Pmin
        self.Qmax = Qmax
        self.Qmin = Qmin
        self.gen_id = ""
        self.gen_name = ""
        # Ensure config is a dictionary
        self.config = config if config is not None else {}

        #self.config["waveSeed"] = int(self.config.get("waveSeed",np.random.randint(0, 2**32 - 1)))
                
        if not self.pull_wec_data():
            print(f"Data for WEC {self.ID} not found in the database. Running simulation.")
            self.WEC_Sim()
        
        # add snapshots to dataframe
        snapshots = pd.date_range(
                start=self.engine.start_time,  # Add 5 minutes
                periods= self.dataframe.shape[0],
                freq="5T",  # 5-minute intervals
            )
        self.dataframe["snapshots"] = snapshots
        
    def pull_wec_data(self):
        """
        Pulls WEC data from the database. If wec_num is provided, pulls data for that specific wec.

        Args:
            wec_num (int, optional): The number of the specific wec to pull data for.

        Returns:
            bool: True if the data pull was successful, False otherwise.
        """

        #print("Pulling WEC data from the database")
        table_check_query = "SELECT name FROM sqlite_master WHERE type='table' AND name='WEC_output_{}'".format(
            self.ID
        )
        table_check_result = dbQuery(table_check_query)

        if (
            not table_check_result
            or table_check_result[0][0] != f"WEC_output_{self.ID}"
        ):
            return False

        data_query = f"SELECT * from WEC_output_{self.ID}"
        self.dataframe = dbQuery(data_query, return_type="df")
        return True

    def WEC_Sim(self):
        """
        Description: This function runs the WEC-SIM simulation for the model in the input folder.
        input:
            wec_id = Id number for your WEC (INT)
            sim_length = simulation length in seconds (INT)
            Tsample = The sample resolution in seconds (INT)
            waveHeight = wave height of the sim (FLOAT) // 2.5 is the default
            wavePeriod = wave period of the sim (FLOAT) // 8 is the default
            waveSeed = seed number for the simulation // np.random.randint(99999999999)

        output: output is the the SQL database, you can query the data with "SELECT * from WEC_output_{wec_id}"
        """

        table_name = f"WEC_output_{self.ID}"
        drop_table_query = f"DROP TABLE IF EXISTS {table_name};"
        dbQuery(drop_table_query)

        print("Starting MATLAB Engine")
        eng = matlab.engine.start_matlab()
        eng.cd(os.path.join(PATHS["wec_model"], self.model))
        eng.addpath(eng.genpath(PATHS["wec_sim"]), nargout=0)
        print(f"Running {self.model}")

        eng.workspace["wecId"] = self.ID
        for key, value in self.config.items():
            eng.workspace[key] = value
            
        #eng.workspace["waveSeed"] = self.waveSeed
        
        eng.workspace["DB_PATH"] = DB_PATH  # move to front end?
        if self.model == "LUPA":
            eng.eval(
                "m2g_out = w2gSim_LUPA(wecId,simLength,Tsample,waveHeight,wavePeriod);",
                nargout=0,
            )
        else:
            
            eng.eval(
                "m2g_out = w2gSim(wecId,simLength,Tsample,waveHeight,wavePeriod);",
                nargout=0,
            )
        eng.eval("WECsim_to_PSSe_dataFormatter", nargout=0)
        print("Sim Completed")
        print("==========")

        data_query = f"SELECT * from WEC_output_{self.ID}"
        self.dataframe = dbQuery(data_query, return_type="df")
