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
from typing import Tuple

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
from WECGrid.viz import WECGridVisualizer


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
        self.sim_length = 288 # 5 min intervals
        self.snapshots = pd.date_range(
                start=self.start_time,
                periods= self.sim_length , # 288 5-minute intervals in a day
                freq="5T",  # 5-minute intervals
            )
        self.wecObj_list = []
        self.wec_buses = []
        self.software = [] 
        self.generator_compare = None
        self.bus_compare = None
        self.viz = WECGridVisualizer(self)
        
        self.initialize_simulation_db(DB_PATH)

    def initialize_simulation_db(self, path):
        #TODO: need to move this to DB wrapper handler 
        #TODO: needs to check if db exists, if not create it with tables, if there, should check if tables exist,
        #TODO: need a function to print a report of the contents of the database
        
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sim_runs (
                sim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sim_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                notes TEXT
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS bus_timeseries (
                sim_id INTEGER,
                timestamp TEXT,
                bus_id TEXT,
                p_mw REAL,
                v_pu REAL,
                source TEXT,
                FOREIGN KEY(sim_id) REFERENCES sim_runs(sim_id)
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS gen_timeseries (
                sim_id INTEGER,
                timestamp TEXT,
                gen_id TEXT,
                p_mw REAL,
                source TEXT,
                FOREIGN KEY(sim_id) REFERENCES sim_runs(sim_id)
            )
            """)

            conn.commit()
        
    def load(self, software):
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
            elif name == "pypsa":
                self.pypsa = PYPSAInterface(self.case_file, self)
                self.pypsa.init_api()
                if self.psse is not None:
                    self.psse.adjust_reactive_lim()
            else:
                raise ValueError(f"Unsupported software: '{name}'. Use 'psse' or 'pypsa'.")

    def apply_wecs(self, sim_id=None, model="RM3", farm_size=8, ibus=None, jbus=1, mbase=0.01, config=None):
        #TODO: need to confirm i and j bus are correct orientation
        """
        Creates a WEC device and adds it to both PSSE and PyPSA models.

        Args:
            ID (int): Identifier for the WEC device.
            model (str): Model type of the WEC device.
            from_bus (int): The bus number from which the WEC device is connected.
            to_bus (int): The bus number to which the WEC device is connected.
        """
        if config is None:
            config = {
                "simLength": (self.sim_length * 5 * 60), # Simulation length in seconds
                "Tsample": 300,  # Sampling time of 5 minutes
                "waveHeight": 2.5, # Wave height in meters
                "wavePeriod": 8, # Wave period in seconds
            }
        else:
            self.sim_length = config["simLength"] / 300
            self.snapshots = pd.date_range(
                start=self.start_time,
                periods= self.sim_length , # 288 5-minute intervals in a day
                freq="5T",  # 5-minute intervals
            )
        self.wec_buses.append(ibus)
        for i in range(farm_size):
            self.wecObj_list.append(
                wec_class.WEC(
                    engine=self,
                    sim_id=sim_id,
                    model=model,
                    bus_location=ibus,
                    MBASE=mbase,
                    config=config  
                )
            )
        if self.pypsa is not None:
            #TODO: this is not returning false if broken
            if self.pypsa.add_wec(model, ibus, jbus):
                print("WEC components added to PyPSA network.")
            else:
                print("Failed to add WEC to PyPSA network.")
            
        if self.psse is not None:
            if self.psse.add_wec(model, ibus, jbus):
                print("WEC components added to PSS®E network.")
            else:
                print("Failed to add WEC to PSS®E network.")

    def generate_load_profiles(self):
        """
        Create a unified double-peaking load curve profile, then split it for pyPSA and PSS®E.
        Stores results in self.load_profiles_pypsa and self.load_profiles_psse
        """
        # 1. Extract base loads for pyPSA (load ID → MW)
        pypsa_base = self.pypsa.network.loads[["bus", "p_set"]].copy()

        # 2. Extract base loads for PSS®E (bus number → MW)
        psse_base = (
            self.psse.loads_dataframe[["BUS_NUMBER", "P_MW"]]
            .drop_duplicates("BUS_NUMBER")
            .set_index("BUS_NUMBER")["P_MW"]
        )

        # 3. Create the normalized load shape over the day
        times = pd.to_datetime(self.snapshots)
        hours = times.hour + times.minute / 60.0

        def double_peak(hour):
            return 0.5 + 0.5 * (
                np.exp(-0.5 * ((hour - 8) / 2) ** 2) +
                np.exp(-0.5 * ((hour - 18) / 2) ** 2)
            )

        shape = double_peak(hours)

        # 4. Create time-indexed DataFrames
        df_pypsa = pd.DataFrame(index=self.snapshots)
        df_psse = pd.DataFrame(index=self.snapshots)

        # 5. Apply curve to pyPSA loads (column = load ID)
        for load_id, row in pypsa_base.iterrows():
            base = row["p_set"]
            if base > 0:
                df_pypsa[load_id] = base * shape

        # 6. Apply curve to PSS®E loads (column = bus number)
        for bus, base in psse_base.items():
            if base > 0:
                df_psse[bus] = base * shape

        # 7. Store
        self.pypsa.load_profiles = df_pypsa
        self.psse.load_profiles = df_psse
        
    def simulate(self, load_curve=True, plot=True):
        """
        Simulates the WEC devices and updates the PSSE and PyPSA models.

        Args:
            load_curve (bool): If True, simulates the load curve.
        """
        if self.psse is not None:
            print("Simulating on PSS®E...")
            start_time = time.time()
            if self.psse.simulate(load_curve=load_curve, plot=plot):
                print("PSS®E simulation complete in {} seconds. \n".format(time.time() - start_time))
            else:
                print("PSS®E simulation failed. \n")
            
        if self.pypsa is not None:
            print("Simulating on PyPSA...")
            start_time = time.time()
            if self.pypsa.simulate(load_curve=load_curve, plot=plot):
                print("PyPSA simulation complete in {} seconds. \n".format(time.time() - start_time))
            else:
                print("PyPSA simulation failed. \n")
        
        #self.compare_results()

    def compare_results(self, plot=True):
        if self.psse is not None and self.pypsa is not None and plot:
            self.viz.plot_comparison()

        def compute_rmse_corr(psse_df, pypsa_df, label_prefix=None, convert_cols=False):
            if convert_cols:
                psse_df.columns = psse_df.columns.map(str)
            common = sorted(set(psse_df.columns).intersection(set(pypsa_df.columns)), key=str)

            rows = []
            for key in common:
                psse_series = psse_df[key]
                pypsa_series = pypsa_df[key]
                rmse = np.sqrt(((psse_series - pypsa_series) ** 2).mean())

                # Only compute correlation if there is variance
                if psse_series.std() == 0 or pypsa_series.std() == 0:
                    corr = np.nan
                else:
                    corr = psse_series.corr(pypsa_series)

                rows.append({
                    "ID": key,
                    "Parameter": label_prefix,
                    "RMSE": rmse,
                })
            return pd.DataFrame(rows)

        # Compute generator comparison
        gen_df = compute_rmse_corr(
            self.psse.generator_dataframe_t.p.copy(),
            self.pypsa.network.generators_t.p.copy(),
            label_prefix="P"
        ).rename(columns={"ID": "Generator"})[["Generator", "Parameter", "RMSE"]]

        # Compute bus P and V comparison
        bus_p_df = compute_rmse_corr(
            self.psse.bus_dataframe_t.p.copy(),
            self.pypsa.network.buses_t.p.copy(),
            label_prefix="P",
            convert_cols=True
        )

        bus_v_df = compute_rmse_corr(
            self.psse.bus_dataframe_t.v_mag_pu.copy(),
            self.pypsa.network.buses_t.v_mag_pu.copy(),
            label_prefix="V_mag",
            convert_cols=True
        )

        bus_df = pd.concat([bus_p_df, bus_v_df]) \
                .rename(columns={"ID": "Bus"}) \
                [["Bus", "Parameter", "RMSE"]]

        # Save to attributes for inspection in notebook
        self.generator_compare = gen_df
        self.bus_compare = bus_df

    def save_simulation(self, sim_name="Unnamed Run", notes=""):
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sim_runs (sim_name, timestamp, notes)
                VALUES (?, ?, ?)
            """, (sim_name, timestamp, notes))
            sim_id = cursor.lastrowid

        if self.psse is not None:
            self.save_psse_run(sim_id)
        if self.pypsa is not None:
            self.save_pypsa_run(sim_id)

    def save_psse_run(self, sim_id):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        psse_bus = self.psse.bus_dataframe_t
        psse_gen = self.psse.generator_dataframe_t

        for timestamp in psse_bus.p.index:
            for bus in psse_bus.p.columns:
                cursor.execute("""
                    INSERT INTO bus_timeseries (sim_id, timestamp, bus_id, p_mw, v_pu, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sim_id, timestamp.isoformat(), str(bus),
                    psse_bus.p.at[timestamp, bus],
                    psse_bus.v_mag_pu.at[timestamp, bus],
                    "psse"))

            for gen in psse_gen.p.columns:
                cursor.execute("""
                    INSERT INTO gen_timeseries (sim_id, timestamp, gen_id, p_mw, source)
                    VALUES (?, ?, ?, ?, ?)
                """, (sim_id, timestamp.isoformat(), gen,
                    psse_gen.p.at[timestamp, gen],
                    "psse"))

        conn.commit()
        conn.close()

    def save_pypsa_run(self, sim_id):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        pypsa_bus = self.pypsa.network.buses_t
        pypsa_gen = self.pypsa.network.generators_t

        for timestamp in pypsa_bus.p.index:
            for bus in pypsa_bus.p.columns:
                cursor.execute("""
                    INSERT INTO bus_timeseries (sim_id, timestamp, bus_id, p_mw, v_pu, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sim_id, timestamp.isoformat(), str(bus),
                    pypsa_bus.p.at[timestamp, bus],
                    pypsa_bus.v_mag_pu.at[timestamp, bus],
                    "pypsa"))

            for gen in pypsa_gen.p.columns:
                cursor.execute("""
                    INSERT INTO gen_timeseries (sim_id, timestamp, gen_id, p_mw, source)
                    VALUES (?, ?, ?, ?, ?)
                """, (sim_id, timestamp.isoformat(), gen,
                    pypsa_gen.p.at[timestamp, gen],
                    "pypsa"))

        conn.commit()
        conn.close()

    def saved_runs(self):
        """
        Lists all simulation runs stored in the database.
        """
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql("SELECT * FROM sim_runs ORDER BY sim_id DESC", conn)
        return df
    
    def pull_sim(self, sim_id=None):
        """
        Loads the results of a previous simulation run.

        Args:
            sim_id (int, optional): If not provided, loads the most recent run.

        Returns:
            dict: A dictionary containing DataFrames:
                {
                    "psse_gen": ..., "pypsa_gen": ...,
                    "psse_bus": ..., "pypsa_bus": ...
                }
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            if sim_id is None:
                cursor.execute("SELECT MAX(sim_id) FROM sim_runs")
                sim_id = cursor.fetchone()[0]
                if sim_id is None:
                    raise ValueError("No simulation runs found in the database.")

            gen_df = pd.read_sql(
                "SELECT * FROM gen_timeseries WHERE sim_id = ?", conn, params=(sim_id,)
            )
            bus_df = pd.read_sql(
                "SELECT * FROM bus_timeseries WHERE sim_id = ?", conn, params=(sim_id,)
            )

        # Split by source
        gen_psse = gen_df[gen_df["source"] == "psse"].drop(columns=["sim_id", "source"])
        gen_pypsa = gen_df[gen_df["source"] == "pypsa"].drop(columns=["sim_id", "source"])
        bus_psse = bus_df[bus_df["source"] == "psse"].drop(columns=["sim_id", "source"])
        bus_pypsa = bus_df[bus_df["source"] == "pypsa"].drop(columns=["sim_id", "source"])

        # Timestamp to index
        for df in [gen_psse, gen_pypsa, bus_psse, bus_pypsa]:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)

        # Pivot helper (flexible to dropped columns)
        def pivot(df, id_col):
            return {
                col: df.pivot_table(index="timestamp", columns=id_col, values=col)
                for col in df.columns
                if col != id_col
            }

        return {
            "psse_gen": pivot(gen_psse, "gen_id"),
            "pypsa_gen": pivot(gen_pypsa, "gen_id"),
            "psse_bus": pivot(bus_psse, "bus_id"),
            "pypsa_bus": pivot(bus_pypsa, "bus_id"),
        }
    

#TODO: need to update the software to run without wec case 
#TODO: need a function to tell me all the wec-sim runs i have in my db
#TODO: need a function to store my simulation results in the db
#TODO: need a function to pull my simulation results from the db for analysis? 
 
            
            
            
