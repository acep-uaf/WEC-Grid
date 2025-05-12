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
from WECGrid.cec import cec_class
from WECGrid.wec import wec_class
from WECGrid.utilities.util import dbQuery, read_paths
from WECGrid.database_handler.connection_class import DB_PATH
from WECGrid.pypsa import PYPSAInterface
from WECGrid.psse import PSSEInterface
#from WECGrid.viz import PSSEVisualizer


# Initialize the PATHS dictionary
PATHS = read_paths()
CURR_DIR = os.path.dirname(os.path.abspath(__file__))


class WECGridEngine:
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
        self.psse = None
        self.pypsa = None
        self.start_time = datetime(1997, 11, 3, 0, 0, 0)
        self.wecObj_list = [] 
        
    def use(self, software):
        """
        Enables one or more supported power system software tools.

        Args:
            software (str or list of str): Name(s) of supported software to initialize.
                                        Options: "psse", "pypsa"
        """
        if isinstance(software, str):
            software = [software]

        for name in software:
            name = name.lower()
            if name == "psse":
                self.psse = PSSEInterface(self.case_file, self)
                self.psse.init_api()
                print(f"Initialized: PSSE with case {self.case_file_name}")
            elif name == "pypsa":
                self.pypsa = PYPSAInterface(self.case_file, self)
                self.pypsa.initialize()
                print(f"Initialized: PyPSA with case {self.case_file_name}")
            else:
                raise ValueError(f"Unsupported software: '{name}'. Use 'psse' or 'pypsa'.")

    def create_wec(self, ID, model, farm_size, ibus, jbus, run_sim=True, mbase=0.01, config=None):
        #TODO: need to confirm i and j bus are correct orientation
        """
        Creates a WEC device and adds it to both PSSE and PyPSA models.

        Args:
            ID (int): Identifier for the WEC device.
            model (str): Model type of the WEC device.
            from_bus (int): The bus number from which the WEC device is connected.
            to_bus (int): The bus number to which the WEC device is connected.
        """
        for i in range(farm_size):
            self.wecObj_list.append(
                wec_class.WEC(
                    engine=self,
                    ID=ID,
                    model=model,
                    bus_location=ibus,
                    MBASE=mbase,
                    config=config  
                )
            )
        if self.pypsa is not None:
            self.pypsa.add_wec(model, ibus, jbus)
            
        if self.psse is not None:
            self.psse.add_wec(model, ibus, jbus)
            