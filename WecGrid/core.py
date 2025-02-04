"""
WEC-GRID source code
Author: Alexander Barajas-Ritchie
Email: barajale@oreogonstate.edu

core.py
"""

# Standard Libraries
import os
import sys
import re
import time
import json
from datetime import datetime, timezone, timedelta

# Third-party Libraries
import pandas as pd
import numpy as np
import sqlite3
import pypsa
import pypower.api as pypower
import matlab.engine
import cmath
import matplotlib.pyplot as plt

# local libraries
from WecGrid.cec import cec_class
from WecGrid.wec import wec_class
from WecGrid.utilities.util import dbQuery, read_paths
from WecGrid.database_handler.connection_class import DB_PATH
from WecGrid.pyPSA import pyPSAWrapper
from WecGrid.PSSe import PSSeWrapper
from WecGrid.viz import PSSEVisualizer


# Initialize the PATHS dictionary
PATHS = read_paths()
CURR_DIR = os.path.dirname(os.path.abspath(__file__))


class WecGrid:
    """
    Main class for coordinating between PSSE and PyPSA functionality and managing WEC devices.

    Attributes:
        case (str): Path to the case file.
        psseObj (PSSEWrapper): Instance of the PSSE wrapper class.
        pypsaObj (PyPSAWrapper): Instance of the PyPSA wrapper class.
        wecObj_list (list): List of WEC objects.
    """

    def __init__(self, case):
        """
        Initializes the WecGrid class with the given case file.

        Args:
            case (str): Path to the case file.
        """
        self.case_file = case  # TODO: need to verify file exist
        self.case_file_name = os.path.basename(case)
        self.psseObj = None
        self.pypsaObj = None
        # self.dbObj = None
        self.wecObj_list = []  # list of the WEC Model objects for the simulations
        self.cecObj_list = []  # list of the WEC Model objects for the simulations
        # these list could probably be combined? ^^^

    def initialize_psse(self, solver_args=None):
        """
        Initializes the PSSE solver.

        Args:
            solver_args (dict): Optional arguments for the PSSE initialization.
        """
        solver_args = solver_args or {}  # Use empty dict if no args are provided
        self.psseObj = PSSeWrapper(self.case_file, self)
        self.psseObj.initialize(solver_args)
        print(
            f"PSSE initialized with case file: {self.case_file_name}."
        )  # TODO: this shoould be a check not a print

    def initialize_pypsa(self, solver_args=None):
        """
        Initializes the PyPSA solver.

        Args:
            solver_args (dict): Optional arguments for the PyPSA initialization.
        """
        solver_args = solver_args or {}  # Use empty dict if no args are provided
        self.pypsaObj = pyPSAWrapper(self.case_file, self)
        self.pypsaObj.initialize(solver_args)
        print(
            f"PyPSA initialized with case file: {self.case_file_name}."
        )  # TODO: this shoould be a check not a print

    def create_wec(self, ID, model, farm_size, from_bus, to_bus, run_sim=True, mbase=0.01, config=None):
        """
        Creates a WEC device and adds it to both PSSE and PyPSA models.

        Args:
            ID (int): Identifier for the WEC device.
            model (str): Model type of the WEC device.
            from_bus (int): The bus number from which the WEC device is connected.
            to_bus (int): The bus number to which the WEC device is connected.
        """

        # self.psseObj.dataframe.loc[
        #     self.psseObj.dataframe["BUS_ID"] == bus_location, "Type"
        # ] = 4  # This updated the Grid Model for the grid to know that the bus now has a WEC/CEC on it.
        # self.psseObj.wecObj_list = self.wecObj_list
        # TODO: need to update pyPSA obj too if exists? maybe not
        if self.pypsaObj is not None:
            self.pypsaObj.add_wec(model, ID, farm_size, from_bus, to_bus)

        if self.psseObj is not None:
            # get SBASE from PSSE
            sbase = self.psseObj.get_sbase()
            #mbase = 0.1 # hard coded for now. for a system with an sbse of 100 MVA, this would be 10 KW (0.01 MVA)
            
            for i in range(farm_size):
                self.wecObj_list.append(
                    wec_class.WEC(
                        ID=ID,
                        model=model,
                        bus_location=to_bus,
                        MBASE=mbase,
                        config=config  
                    )
                )
            self.psseObj.add_wec(model, from_bus, to_bus)

    def create_cec(self, ID, model, bus_location, run_sim=True):
        self.cecObj_list.append(cec_class.CEC(ID, model, bus_location, run_sim))
        # self.psseObj.dataframe.loc[
        #     self.psseObj.dataframe["BUS_ID"] == bus_location, "Type"
        # ] = 4  # This updated the Grid Model for the grid to know that the bus now has a WEC/CEC on it.
        # TODO: need to update pyPSA obj too
