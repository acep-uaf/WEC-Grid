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
from ..viz.psse_viz import PSSEVisualizer  # Relative import for viz/psse_viz.py


Snapshot = namedtuple("Snapshot", ["snapshot", "buses", "generators", "branches", "branch_flows", "loads", "plants", "TwoWinding", "ThreeWinding", "metadata"])   

class PSSEInterface:
    def __init__(self, case_file: str, engine: "WECGridEngine"):
        self.case_file = case_file
        self.engine = engine
        
        #Grid dfs
        self.bus_dataframe = pd.DataFrame()
        self.generator_dataframe = pd.DataFrame()
        self.branches_dataframe = pd.DataFrame()
        self.branch_flows_dataframe = pd.DataFrame()
        self.plants_dataframe = pd.DataFrame()
        self.loads_dataframe = pd.DataFrame()
        self.two_winding_dataframe = pd.DataFrame()
        self.three_winding_dataframe = pd.DataFrame()
    
        self.snapshot = None
        self.snapshot_history = []
        self.load_profiles = pd.DataFrame()
        self.viz = PSSEVisualizer(self)
        
        #  PSSE stuff
        self._i = None
        self._f = None
        self._s = None
    
    def init_api(self, solver="fnsl", silence=False) -> bool:
        try:
            import psspy
            import psse35
            import redirect

            psse35.set_minor(3)
            psspy.psseinit(50)

            if silence:
                psspy.prompt_output(6, "", [])
                psspy.alert_output(6, "", [])
                psspy.progress_output(6, "", [])

            PSSEInterface.psspy = psspy
            self._i = psspy.getdefaultint()
            self._f = psspy.getdefaultreal()
            self._s = psspy.getdefaultchar()

        except ModuleNotFoundError as e:
            raise ImportError("PSSE not found or not configured correctly.") from e

        ext = self.case_file.lower()
        if ext.endswith(".sav"):
            ierr = psspy.case(self.case_file)
        elif ext.endswith(".raw"):
            ierr = psspy.read(1, self.case_file)
        else:
            print("Unsupported case file format.")
            return False

        if ierr != 0:
            print(f"PSSE failed to load case. ierr={ierr}")
            return False

        if self.psspy.fnsl() != 0:
            print("Powerflow solution failed.")
            return False
            
        self.take_snapshot(snapshot=self.engine.start_time, metadata={"step": "initial"})
        
        return True
    
    def pf(self) -> int:
        ierr = self.psspy.fnsl()
        if ierr == 0:
            # ierr == 0 means no error occured 
            return 1 # return True/Sucess
        else:
            print("Error while solving powerflow")
            return ierr

    def take_snapshot(self, snapshot, metadata):
        metadata = metadata or {}
        snapshot = Snapshot(
            snapshot=snapshot,
            buses=self.snapshot_Buses(),
            generators=self.snapshot_Generators(),
            branches=self.snapshot_Branches(),
            branch_flows=self.snapshot_BranchFlows(),
            loads=self.snapshot_Loads(),
            plants=self.snapshot_Plants(),
            TwoWinding=self.snapshot_TwoWindings(),
            ThreeWinding=self.snapshot_ThreeWindings(),
            metadata=metadata
        )
        self.snapshot_history.append(snapshot)
        self.bus_dataframe = snapshot.buses
        self.generator_dataframe = snapshot.generators
        self.branches_dataframe = snapshot.branches
        self.branch_flows_dataframe = snapshot.branch_flows
        self.plants_dataframe = snapshot.plants
        self.loads_dataframe = snapshot.loads
        self.two_winding_dataframe = snapshot.TwoWinding
        self.three_winding_dataframe = snapshot.ThreeWinding
        
        return snapshot

    def snapshot_TwoWindings(self) -> pd.DataFrame:
        """
        Snapshot of all in-service two-winding transformers, capturing key electrical metrics.
        """
        # --- Integer data
        ierr, iarray = self.psspy.atrnint(string=[
            "FROMNUMBER", "TONUMBER", "STATUS", 
            "METERNUMBER", "WIND1NUMBER", "WIND2NUMBER"
        ])
        ibus, jbus, status, meter_bus, wind1, wind2 = iarray

        # --- Real data
        ierr, rarray = self.psspy.atrnreal(string=[
            "P", "Q", "PLOSS", "QLOSS", "MVA", "RATE", "RATEA", "AMPS", 
            "RATIO", "RATIO2", "ANGLE", "STEP", "SBASE1", "NOMV1", "NOMV2",
            "PCTCRPRATE", "PUCUR", "PCTRATE"
        ])
        p, q, ploss, qloss, mva, rate, ratea, amps, ratio1, ratio2, angle, step, sbase1, nomkv1, nomkv2, pctcrprate, pucur, pctrate = rarray

        # --- Character data
        ierr, carray = self.psspy.atrnchar(string=["XFRNAME"])
        names = carray[0]

        # --- Fill in blank names
        for i, name in enumerate(names):
            names[i] = f"TX{i}" if name.strip() == "" else name.strip()

        # --- Assemble DataFrame
        rows = []
        for i in range(len(ibus)):
            rows.append({
                "ID":            names[i],
                "IBUS":          ibus[i],
                "JBUS":          jbus[i],
                "STATUS":        status[i],
                "P_MW":          p[i],
                "Q_MVAR":        q[i],
                "PLOSS_MW":      ploss[i],
                "QLOSS_MVAR":    qloss[i],
                "MVA":           mva[i],
                "RATE_MVA":      rate[i],
                "RATE_A":        ratea[i],
                "AMPS":          amps[i],
                "PUCUR":         pucur[i],
                "PCTRATE":       pctrate[i],
                "PCTCRPRATE":    pctcrprate[i],
                "RATIO1":        ratio1[i],
                "RATIO2":        ratio2[i],
                "ANGLE":         angle[i],
                "STEP":          step[i],
                "SBASE1":        sbase1[i],
                "NOMKV1":        nomkv1[i],
                "NOMKV2":        nomkv2[i],
                "METER_BUS":     meter_bus[i],
                "WIND1":         wind1[i],
                "WIND2":         wind2[i],
            })

        return pd.DataFrame(rows)
    
    def snapshot_ThreeWindings(self) -> pd.DataFrame:
        """
        Snapshot of all in-service three-winding transformers, capturing impedance and power loss metrics.
        """
        # --- Character data: transformer names and windings
        ierr, carray = self.psspy.atr3char(string=["ID", "WIND1NAME", "WIND2NAME", "NMETERNAME", "XFRNAME"])
        ids, w1_names, w2_names, meter_names, xfr_names = carray

        # --- Integer data: bus numbers and status
        ierr, iarray = self.psspy.atr3int(string=["WIND1NUMBER", "WIND2NUMBER", "WIND3NUMBER", "STATUS", "NMETERNUMBER"])
        w1, w2, w3, status, meter_bus = iarray

        # --- Real data: losses and star bus info
        ierr, rarray = self.psspy.atr3real(string=["PLOSS", "QLOSS", "ANSTAR", "VMSTAR"])
        ploss, qloss, anstar, vmstar = rarray

        # --- Complex data: RX impedances between winding pairs
        ierr, xarray = self.psspy.atr3cplx(string=[
            "RX1-2ACT", "RX1-2NOM",
            "RX2-3ACT", "RX2-3NOM",
            "RX3-1ACT", "RX3-1NOM",
            "PQLOSS"
        ])
        rx12a, rx12n, rx23a, rx23n, rx31a, rx31n, _ = xarray  # ignore PQLOSS (already covered)

        # --- Fix any blank transformer names
        for i, name in enumerate(xfr_names):
            xfr_names[i] = f"TX3W_{i}" if name.strip() == "" else name.strip()

        # --- Assemble DataFrame
        rows = []
        for i in range(len(w1)):
            rows.append({
                "ID":           xfr_names[i],
                "WIND1":        w1[i],
                "WIND2":        w2[i],
                "WIND3":        w3[i],
                "STATUS":       status[i],
                "METER_BUS":    meter_bus[i],
                "PLOSS_MW":     ploss[i],
                "QLOSS_MVAR":   qloss[i],
                "ANSTAR_DEG":   anstar[i],
                "VMSTAR_PU":    vmstar[i],
                "RX12_ACT":     rx12a[i],
                "RX12_NOM":     rx12n[i],
                "RX23_ACT":     rx23a[i],
                "RX23_NOM":     rx23n[i],
                "RX31_ACT":     rx31a[i],
                "RX31_NOM":     rx31n[i],
            })

        return pd.DataFrame(rows)
    
    def snapshot_Loads(self) -> pd.DataFrame:
        """
        Snapshot of all in-service loads on the system, capturing actual/nominal values for power,
        current, and distributed generation.
        """
        # --- Character data: bus name and load ID
        ierr, carray = self.psspy.aloadchar(string=["NAME", "ID"])
        bus_names, load_ids = carray

        # --- Complex values: MW + jMvar for actual/nominal load, current, and DG
        ierr, xarray = self.psspy.aloadcplx(string=[
            "MVAACT", "MVANOM", "ILACT", "ILNOM",
            "TOTALACT", "TOTALNOM", "LDGNACT", "LDGNNOM"
        ])
        mva_act, mva_nom, il_act, il_nom, total_act, total_nom, dg_act, dg_nom = xarray

        # --- Integer values: bus number, load status
        ierr, iarray = self.psspy.aloadint(string=["NUMBER", "STATUS"])
        bus_nums, status = iarray

        # --- Real values: magnitude of all above (already returned separately from cplx)
        ierr, rarray = self.psspy.aloadreal(string=[
            "MVAACT", "MVANOM", "ILACT", "ILNOM",
            "TOTALACT", "TOTALNOM", "LDGNACT", "LDGNNOM"
        ])
        mva_act_r, mva_nom_r, il_act_r, il_nom_r, total_act_r, total_nom_r, dg_act_r, dg_nom_r = rarray

        rows = []
        for i in range(len(bus_nums)):
            rows.append({
                "BUS_NAME":       bus_names[i].strip(),
                "LOAD_ID":        load_ids[i].strip(),
                "BUS_NUMBER":     bus_nums[i],
                "STATUS":         status[i],
                "MVAACT":         mva_act[i],
                "MVANOM":         mva_nom[i],
                "ILACT":          il_act[i],
                "ILNOM":          il_nom[i],
                "TOTALACT":       total_act[i],
                "TOTALNOM":       total_nom[i],
                "LDGNACT":        dg_act[i],
                "LDGNNOM":        dg_nom[i],
                "MVAACT_MAG":     mva_act_r[i],
                "MVANOM_MAG":     mva_nom_r[i],
                "ILACT_MAG":      il_act_r[i],
                "ILNOM_MAG":      il_nom_r[i],
                "TOTALACT_MAG":   total_act_r[i],
                "TOTALNOM_MAG":   total_nom_r[i],
                "LDGNACT_MAG":    dg_act_r[i],
                "LDGNNOM_MAG":    dg_nom_r[i],
            })

        return pd.DataFrame(rows)
   
    def snapshot_Buses(self) -> pd.DataFrame:
        """
        Snapshot of all buses, capturing voltage, angle, and basic shunt/mismatch metrics.
        """
        # --- Character data: bus names
        ierr1, carray = self.psspy.abuschar(string=["NAME"])
        bus_names = carray[0]

        # --- Complex values
        ierr3, xarray = self.psspy.abuscplx(string=["VOLTAGE", "SHUNTACT", "SHUNTNOM", "MISMATCH"])
        voltage, shunt_act, shunt_nom, mismatch_cplx = xarray

        # --- Integer values
        ierr4, iarray = self.psspy.abusint(string=["NUMBER", "TYPE"])
        numbers, types = iarray

        # --- Real values
        ierr5, rarray = self.psspy.abusreal(string=["BASE", "PU", "KV", "ANGLE", "ANGLED", "MISMATCH"])
        base_kv, pu, kv, angle_rad, angle_deg, mismatch_mag = rarray

        # Check for any error
        if any(ierr != 0 for ierr in [ierr1, ierr3, ierr4, ierr5]):
            raise RuntimeError("Error retrieving bus snapshot data from PSSE.")

        rows = []
        for i in range(len(numbers)):
            rows.append({
                "BUS_ID":       numbers[i],
                "BUS_NAME":     bus_names[i].strip(),
                "TYPE":         types[i],
                "V_PU":         pu[i],
                "V_KV":         kv[i],
                "BASE_KV":      base_kv[i],
                "ANGLE_RAD":    angle_rad[i],
                "ANGLE_DEG":    angle_deg[i],
                "MISMATCH_MVA": mismatch_mag[i],
                "MISMATCH_CPLX": mismatch_cplx[i],   # Optional for debugging
                "SHUNT_ACT":    shunt_act[i],
                "SHUNT_NOM":    shunt_nom[i],
            })

        return pd.DataFrame(rows)
      
    def snapshot_Branches(self) -> pd.DataFrame:
        """Snapshot of branch configuration and electrical parameters."""
        ierr1, carray = self.psspy.abrnchar(string=["ID", "FROMNAME", "TONAME", "BRANCHNAME"])
        ids, fromnames, tonames, brnames = carray

        ierr2, xarray = self.psspy.abrncplx(string=["RX", "PQ", "PQLOSS", "FROMSHNT", "TOSHNT"])
        rx, pq, pqloss, fromshnt, toshnt = xarray

        ierr3, iarray = self.psspy.abrnint(string=["FROMNUMBER", "TONUMBER", "STATUS"])
        ibus, jbus, status = iarray

        ierr4, rarray = self.psspy.abrnreal(string=[
            "RATE", "RATEA", "AMPS", "PUCUR", "PCTRATE"
        ])
        rate, ratea, amps, pucur, pctrate = rarray

        if any(ierr != 0 for ierr in [ierr1, ierr2, ierr3, ierr4]):
            raise RuntimeError("Error fetching branch static data.")

        rows = []
        for i in range(len(ibus)):
            name = brnames[i].strip() or f"Br{i}"
            rows.append({
                "ID": ids[i].strip(),
                "NAME": name,
                "IBUS": ibus[i],
                "JBUS": jbus[i],
                "FROM_NAME": fromnames[i].strip(),
                "TO_NAME": tonames[i].strip(),
                "STATUS": status[i],
                "RX_PU": rx[i],
                "SHUNT_FROM": fromshnt[i],
                "SHUNT_TO": toshnt[i],
                "RATE": rate[i],
                "RATEA": ratea[i],
                "AMPS": amps[i],
                "PUCUR": pucur[i],
                "PCT_RATE": pctrate[i],
            })

        return pd.DataFrame(rows)
    
    def snapshot_BranchFlows(self) -> pd.DataFrame:
        """Snapshot of directional branch power flows and losses."""
        ierr1, carray = self.psspy.aflowchar(string=["ID", "FROMNAME", "TONAME"])
        ids, fromnames, tonames = carray

        ierr2, xarray = self.psspy.aflowcplx(string=["PQ", "PQLOSS"])
        pq, pqloss = xarray

        ierr3, iarray = self.psspy.aflowint(string=["FROMNUMBER", "TONUMBER", "STATUS"])
        ibus, jbus, status = iarray

        ierr4, rarray = self.psspy.aflowreal(string=[
            "P", "Q", "PLOSS", "QLOSS", "MVA", "RATE", "RATEA",
            "AMPS", "PCTCORPRATE", "PCTRATE", "PUCUR"
        ])
        p, q, ploss, qloss, mva, rate, ratea, amps, pctcorrate, pctrate, pucur = rarray

        if any(ierr != 0 for ierr in [ierr1, ierr2, ierr3, ierr4]):
            raise RuntimeError("Error fetching branch flow data.")

        rows = []
        for i in range(len(ibus)):
            name = ids[i].strip() or f"F{i}"
            rows.append({
                "ID": name,
                "FROM_BUS": ibus[i],
                "TO_BUS": jbus[i],
                "FROM_NAME": fromnames[i].strip(),
                "TO_NAME": tonames[i].strip(),
                "STATUS": status[i],
                "P_MW": p[i],
                "Q_MVAR": q[i],
                "PLOSS_MW": ploss[i],
                "QLOSS_MVAR": qloss[i],
                "MVA": mva[i],
                "RATE": rate[i],
                "RATEA": ratea[i],
                "AMPS": amps[i],
                "PUCUR": pucur[i],
                "PCT_RATE": pctrate[i],
                "PCT_CORP_RATE": pctcorrate[i],
            })

        return pd.DataFrame(rows)    

    def snapshot_Plants(self) -> pd.DataFrame:
        """Snapshot of plant-level data (aggregated generator buses)."""

        ierr1, name_arr = self.psspy.agenbuschar(string="NAME")
        ierr2 = self.psspy.agenbuscount()[0]
        ierr3, cplx_arr = self.psspy.agenbuscplx(string=["VOLTAGE", "PQGEN", "MISMATCH"])
        ierr4, int_arr = self.psspy.agenbusint(string=["NUMBER", "STATUS", "TYPE"])
        ierr5, real_arr = self.psspy.agenbusreal(string=[
            "BASE", "PU", "KV", "ANGLE", "ANGLED", "PERCENT", "MISMATCH", "PGEN", "QGEN",
            "IREGBASE", "IREGPU", "IREGKV", "VSPU", "VSKV", "RMPCT", "MVA"
        ])

        if any(ierr != 0 for ierr in [ierr1, ierr2, ierr3, ierr4, ierr5]):
            raise RuntimeError("Error fetching plant-level bus data.")

        names = name_arr[0]
        voltage, pqgen, mismatch = cplx_arr
        numbers, status, btypes = int_arr
        base_kv, pu, kv, angle, angled, percent, mmw, pgen, qgen, iregbase, iregpu, iregkv, vspu, vskv, rmpct, mva = real_arr

        rows = []
        for i in range(len(numbers)):
            rows.append({
                "NAME":        names[i].strip(),
                "BUS_ID":      numbers[i],
                "STATUS":      status[i],
                "TYPE":        btypes[i],
                "VOLT_PU":     pu[i],
                "KV":          kv[i],
                "BASE_KV":     base_kv[i],
                "ANGLE_RAD":   angle[i],
                "ANGLE_DEG":   angled[i],
                "PGEN":        pgen[i],
                "QGEN":        qgen[i],
                "MVA":         mva[i],
                "MISMATCH_MVA": mmw[i],
                "PERCENT_LOAD": percent[i],
                "IREG_PU":     iregpu[i],
                "IREG_KV":     iregkv[i],
                "IREG_BASE":   iregbase[i],
                "VSPU":        vspu[i],
                "VSKV":        vskv[i],
                "RMPCT":       rmpct[i],
            })

        return pd.DataFrame(rows)

    def snapshot_Generators(self) -> pd.DataFrame:
        """Snapshot of generator (machine) data at individual unit level."""

        ierr1, char_arr = self.psspy.amachchar(string=["ID", "NAME"])
        ierr2 = self.psspy.amachcount()[0]
        ierr3, cplx_arr = self.psspy.amachcplx(string=["ZSORCE", "XTRAN", "PQGEN"])
        ierr4, int_arr = self.psspy.amachint(string=["NUMBER", "STATUS"])
        ierr5, real_arr = self.psspy.amachreal(string=["PGEN", "QGEN", "MBASE", "MVA", "GENTAP", "PERCENT"])

        if any(ierr != 0 for ierr in [ierr1, ierr2, ierr3, ierr4, ierr5]):
            raise RuntimeError("Error fetching generator (machine) data.")

        gen_ids, gen_names = char_arr
        zsource, xtran, pqgen = cplx_arr
        bus_numbers, statuses = int_arr
        pgen, qgen, mbase, mva, tap, pct = real_arr

        rows = []
        for i in range(len(bus_numbers)):
            rows.append({
                "GEN_ID":     gen_ids[i].strip(),
                "BUS_ID":     bus_numbers[i],
                "BUS_NAME":   gen_names[i].strip(),
                "STATUS":     statuses[i],
                "PGEN_MW":    pgen[i],
                "QGEN_MVAR":  qgen[i],
                "MBASE":      mbase[i],
                "MVA":        mva[i],
                "ZSOURCE":    zsource[i],
                "XTRAN":      xtran[i],
                "TAP":        tap[i],
                "PCT_LOAD":   pct[i]
            })

        return pd.DataFrame(rows)
    
    def add_wec(self, model, ibus, jbus):
        """
        Adds a WEC system to the PSSE model by:
        1. Adding a new bus.
        2. Adding a generator to the bus.
        3. Adding a branch (line) connecting the new bus to an existing bus.

        Parameters:
        - model (str): Model identifier for the WEC system.
        - ID (int): Unique identifier for the WEC system.
        - ibus (int): New bus ID for the WEC system. (WEC BUS)
        - jbus (int): Existing bus ID to connect the line from.
        """
    
        from_bus_voltage = self.psspy.busdat(jbus, "BASE")[1]

        # Step 1: Add a new bus
        
        ierr = self.psspy.bus_data_4(
            ibus=ibus, 
            inode=0, 
            intgar1=2, # Bus type (2 = PV bus ), area, zone, owner
            realar1=from_bus_voltage, # Base voltage of the from bus in kV
            name= f"WEC BUS {ibus}", # Name of the bus
        )
        if ierr > 0:
            print(f"Error adding bus {ibus}. PSS®E error code: {ierr}")
            return 

        # Step 2: Add plant data
        ierr = self.psspy.plant_data_4(
            ibus=ibus, # add plant a wec bus 
            inode=0
        )
        if ierr > 0:
            print(f"Error adding plant data to bus {ibus}. PSS®E error code: {ierr}")
            return

        for i, wec_obj in enumerate(self.engine.wecObj_list):
            # Step 3: Add a generator at the new bus
            wec_obj.gen_id = f'G{i+1}'
            ierr = self.psspy.machine_data_4(
                ibus=ibus, 
                id=wec_obj.gen_id, # maybe should just be a number? come back
                realar1= 0.0, # PG, machine active power (0.0 by default)
                realar7=wec_obj.MBASE # 1 MVA typically
            )

            if ierr > 0:
                print(
                    f"Error adding generator {wec_obj.gen_id} to bus {ibus}. PSS®E error code: {ierr}"
                )
                return

        # Step 4: Add a branch (line) connecting the existing bus to the new bus
        ierr = self.psspy.branch_data_3(
            ibus=ibus, # from bus
            jbus=jbus  # to bus
        )
        if ierr > 0:
            print(
                f"Error adding branch from {ibus} to {jbus}. PSS®E error code: {ierr}"
            )
            return

        self.pf()
        self.take_snapshot(snapshot=self.engine.start_time, metadata={"step": "added wec components"})
    
  
    def simulate(self, snapshots=None, sim_length=None, load_curve=False, plot=True):


        # Determine snapshots if not provided
        if snapshots is None:
            # Use the initial timestamp and create a range of snapshots
            num_snapshots = len(self.engine.wecObj_list[0].dataframe["pg"])

            snapshots = pd.date_range(
                start=self.engine.start_time,  # Add 5 minutes
                periods=num_snapshots,
                freq="5T",  # 5-minute intervals
            )
            self.snapshots = snapshots  # Store the snapshots for later use
            
        # if load_curve == True and self.load_profiles.empty == False:
        #     self.generate_load_curve()
            
        for snapshot in snapshots: 
            for idx, wec_obj in enumerate(self.engine.wecObj_list):
                bus = wec_obj.bus_location
                machine_id = wec_obj.gen_id
                # get pg value
                pg = float(wec_obj.dataframe.loc[wec_obj.dataframe.snapshots == snapshot].pg)
                realar_array = [self._f] * 17
                realar_array[0] = pg
                ierr = self.psspy.machine_chng_4(
                            ibus=bus, 
                            id=wec_obj.gen_id, 
                            realar=realar_array)
                if ierr > 0:
                    raise Exception("Error in adjust activate power")
            
            ierr = self.pf()
            self.take_snapshot(snapshot=snapshot, metadata={"Snapshot": snapshot,"Solver output": ierr, "Solved Status": self.psspy.solved()})
                
                
        # num_wecs = len(self.WecGridCore.wecObj_list)

        # if time is None:
        #     time = self.WecGridCore.wecObj_list[0].dataframe.time.to_list()
        # if start is None:
        #     start = time[0]
        # if end is None:
        #     end = time[-1]
        # for t in time:
        #     print(f"Running powerflow for time: {t}")
        #     if t >= start and t <= end:
        #         if num_wecs > 0:
        #             for idx, wec_obj in enumerate(self.WecGridCore.wecObj_list):
        #                 bus = wec_obj.bus_location
        #                 machine_id = wec_obj.gen_id
                        
        #                 # get activate power from wec at time t
        #                 pg = float(wec_obj.dataframe.loc[wec_obj.dataframe.time == t].pg) 
        #                 # adjust activate power 
        #                 ierr = PSSEInterface.psspy.machine_chng_4(
        #                     bus, machine_id, realar1=pg #, realar7=wec_obj.MBASE
        #                 )
        #                 if ierr > 0:
        #                     raise Exception("Error in adjust activate power")
                        
        #                 # ierr, rval = PSSEInterface.psspy.macdat(bus, machine_id, 'MBASE')
        #                 # print(f"Machine {machine_id} MBASE: {rval}")
        #                 # ierr, rval = PSSEInterface.psspy.macdat(bus, machine_id, 'P')
        #                 # print(f"Machine {machine_id} P: {rval}")
        #         self.update_load(t) 
        #         sim_ierr = PSSEInterface.psspy.fnsl()
                
        #         ierr = PSSEInterface.psspy.solved()
        #         self.take_snapshot(metadata={"Solver output": sim_ierr, "Solved Status": ierr})
                
        #     if t > end:
        #         break
        # return
    
    
    
    # def snapshot_lines(self) -> pd.DataFrame:
    #     """
    #     Snapshot of all in-service branches (lines), capturing loading and flow metrics.
    #     """
    #     # --- Integer data: ibus, jbus, status
    #     ierr, iarray = self.psspy.abrnint(string=["FROMNUMBER", "TONUMBER", "STATUS"])
    #     ibus, jbus, status = iarray[0], iarray[1], iarray[2]

    #     # --- Real data: flows, ratings, amps, loading
    #     ierr, rarray = self.psspy.abrnreal(string=[
    #         "P", "Q", "PLOSS", "QLOSS", "MVA", "RATE", "RATEA", 
    #         "AMPS", "MAXPCTRATE", "PCTCRPRATE"
    #     ])
    #     p, q, ploss, qloss, mva, rate, ratea, amps, max_pct, pct_mva = (
    #         rarray[0], rarray[1], rarray[2], rarray[3], rarray[4], 
    #         rarray[5], rarray[6], rarray[7], rarray[8], rarray[9]
    #     )
        
    #     ierr, carray = self.psspy.abrnchar(string=["BRANCHNAME"])
    #     br_name = carray[0]
       
    #     count = 0
    #     for name in br_name:
    #         if name.strip() == "":
    #             br_name[count] = "L" + str(count)
    #             count += 1
    #         else:
    #             br_name[count] = name.strip()
    #             # --- Build DataFrame
        
    #     rows = []
    #     for i in range(len(ibus)):
    #         rows.append({
    #             "ID":          br_name[i],
    #             "IBUS":         ibus[i],
    #             "JBUS":         jbus[i],
    #             "STATUS":       status[i],
    #             "P_MW":         p[i],
    #             "Q_MVAR":       q[i],
    #             "PLOSS_MW":     ploss[i],
    #             "QLOSS_MVAR":   qloss[i],
    #             "MVA":          mva[i],
    #             "RATE_MVA":     rate[i],
    #             "RATE_A":       ratea[i],
    #             "AMPS":         amps[i],
    #             "MAX_PCTRATE":  max_pct[i],     # % of higher-loaded terminal
    #             "PCT_MVA_LOAD": pct_mva[i],     # loading from one terminal
    #         })

    #     return pd.DataFrame(rows)
        
    # def snapshot_generators(self):
    #     """Snapshots generator state across the entire grid using amach* calls."""
    #     ierr1, bus_numbers = PSSEInterface.psspy.amachint(-1, 4, "NUMBER")
    #     ierr2, gen_ids = PSSEInterface.psspy.amachchar(-1, 4, "ID")
    #     ierr3, pg_values = PSSEInterface.psspy.amachreal(-1, 4, "PGEN")
    #     ierr4, qg_values = PSSEInterface.psspy.amachreal(-1, 4, "QGEN")
    #     ierr5, mbase_values = PSSEInterface.psspy.amachreal(-1, 4, "MBASE")
    #     ierr6, status_vals = PSSEInterface.psspy.amachint(-1, 4, "STATUS")
    #     ierr7, mismatch_vals = PSSEInterface.psspy.agenbusreal(-1,1,'MISMATCH') # Bus mismatch, in MVA 
    #     ierr8, percent_vals = PSSEInterface.psspy.agenbusreal(-1,1,'PERCENT') # Bus mismatch, in MVA 

    #     if any(ierr != 0 for ierr in [ierr1, ierr2, ierr3, ierr4, ierr5, ierr6, ierr7, ierr8]):
    #         raise RuntimeError("One or more PSSE API calls failed.")

    #     data = [
    #         {
    #             "BUS_ID": b,
    #             "GEN_ID": g,
    #             "Pg": p,
    #             "Qg": q,
    #             "MBASE": m,
    #             "STATUS": s,
    #             "MISMATCH": mi,
    #             "PERCENT": pe,
    #         }
    #         for b, g, p, q, m, s, mi, pe in zip(
    #             bus_numbers[0], gen_ids[0], pg_values[0], qg_values[0], mbase_values[0], status_vals[0], mismatch_vals[0], percent_vals[0]
    #         )
    #     ]

    #     return pd.DataFrame(data)
    
    # def snapshot_buses(self, bus_ids=None):
    #     """
    #     Robust bus snapshot for:
    #     - Pd, Qd: real/reactive load
    #     - Pg, Qg: real/reactive gen
    #     - P: net injection (Pg - Pd)
    #     - Voltage magnitude and angle
    #     NaN values used where data is unavailable.
    #     """
    #     if bus_ids is None:
    #         ierr, bus_ids = PSSEInterface.psspy.abusint(-1, 1, 'NUMBER')  # in-service buses
    #         bus_ids = bus_ids[0]

    #     data = []
    #     ierr, rarray = PSSEInterface.psspy.abusreal(-1,1,'MISMATCH') # Bus mismatch, in MVA 

    #     for i in range(len(bus_ids)):
    #         bus = bus_ids[i]
    #         # Load (MW / MVAr)
    #         ierr, cmpval = PSSEInterface.psspy.busdt2(bus, 'TOTAL', 'ACT')
    #         Pd = cmpval.real if ierr == 0 else 0.0
    #         Qd = cmpval.imag if ierr == 0 else 0.0

    #         # Generation (MW / MVAr)
    #         ierr, cmpval_gen = PSSEInterface.psspy.gendat(bus)
    #         Pg = cmpval_gen.real if ierr == 0 else 0.0
    #         Qg = cmpval_gen.imag if ierr == 0 else 0.0

    #         # Voltage and angle
    #         v_pu        = PSSEInterface.psspy.busdat(bus, 'PU')[1]
    #         base_kv   = PSSEInterface.psspy.busdat(bus, 'BASE')[1]
    #         v_mag_kv    = PSSEInterface.psspy.busdat(bus, 'KV')[1]
    #         v_angle_deg = PSSEInterface.psspy.busdat(bus, 'ANGLED')[1]
    #         v_angle_rad = PSSEInterface.psspy.busdat(bus, 'ANGLE')[1]
    #         bus_type = PSSEInterface.psspy.busint(bus, 'TYPE')[1]

    #         data.append({
    #             'BUS_ID': bus,
    #             'TYPE': bus_type,
    #             'Pd': Pd,
    #             'Qd': Qd,
    #             'Pg': Pg,
    #             'Qg': Qg,
    #             'P': Pg - Pd,
    #             'Q': Qg - Qd,
    #             'V_PU': v_pu,
    #             'V_KV': v_mag_kv,
    #             'BASE_KV': base_kv,
    #             'ANGLE_DEG': v_angle_deg,
    #             'ANGLE_RAD': v_angle_rad,
    #             'MISMATCH': rarray[0][i],
    #         })

    #     return pd.DataFrame(data)

    # def get_all_buses_df(self):
    #     return pd.concat([
    #         snap.buses.assign(timestamp=snap.time, metadata=str(snap.metadata))
    #         for snap in self.snapshot_history
    #     ], ignore_index=True)

    # def add_wec(self, model, ibus, jbus):
    #     """
    #     Adds a WEC system to the PSSE model by:
    #     1. Adding a new bus.
    #     2. Adding a generator to the bus.
    #     3. Adding a branch (line) connecting the new bus to an existing bus.

    #     Parameters:
    #     - model (str): Model identifier for the WEC system.
    #     - ID (int): Unique identifier for the WEC system.
    #     - ibus (int): New bus ID for the WEC system.
    #     - jbus (int): Existing bus ID to connect the line from.
    #     """
    #     print("Adding WECs to PSS/E network")
    #     # Create a name for this WEC system
    #     name = f"{model}-{ibus}"

    #     from_bus_voltage = PSSEInterface.psspy.busdat(jbus, "BASE")[1]

    #     # Step 1: Add a new bus
        
    #     ierr = PSSEInterface.psspy.bus_data_4(
    #         ibus=ibus, 
    #         inode=0, 
    #         intgar1=2, # Bus type (2 = PV bus ), area, zone, owner
    #         realar1=from_bus_voltage, # Base voltage of the from bus in kV
    #         name=name
    #     )
    #     if ierr != 0:
    #         print(f"Error adding bus {ibus}. PSS®E error code: {ierr}")
    #         return

    #     print(f"Bus {ibus} added successfully.")

    #     # Step 2: Add plant data
    #     ierr = PSSEInterface.psspy.plant_data_4(
    #         ibus=ibus, # add plant a wec bus 
    #         inode=0
    #     )
    #     if ierr == 0:
    #         print(f"Plant data added successfully to bus {ibus}.")
    #     else:
    #         print(f"Error adding plant data to bus {ibus}. PSS®E error code: {ierr}")
    #         return

    #     for i, wec_obj in enumerate(self.WecGridCore.wecObj_list):
    #         # Step 3: Add a generator at the new bus
    #         wec_obj.gen_id = f'G{i+1}'
    #         ierr = PSSEInterface.psspy.machine_data_4(
    #             ibus=ibus, 
    #             id=wec_obj.gen_id,
    #             realar1= 0.02,# PG, machine active power (0.0 by default)
    #             realar7=wec_obj.MBASE # 1 MVA typically
    #         )

    #         if ierr > 0:
    #             print(
    #                 f"Error adding generator {wec_obj.gen_id} to bus {jbus}. PSS®E error code: {ierr}"
    #             )
    #             return

    #         print(f"Generator {wec_obj.gen_id} added successfully to bus {jbus}.")

    #     # Step 4: Add a branch (line) connecting the existing bus to the new bus
    #     ierr = PSSEInterface.psspy.branch_data_3(
    #         ibus=ibus, 
    #         jbus=jbus 
    #     )
    #     if ierr != 0:
    #         print(
    #             f"Error adding branch from {ibus} to {jbus}. PSS®E error code: {ierr}"
    #         )
    #         return

    #     print(f"Branch from {ibus} to {jbus} added successfully.")

    #     # Step 5: Run load flow and log voltages
    #     ierr = PSSEInterface.psspy.fnsl()
    #     if ierr != 0:
    #         print(f"Error running load flow analysis. PSS®E error code: {ierr}")
    #     self.run_powerflow(self.solver)
    #     self.take_snapshot()

    # def generate_load_curve(self, noise_level=0.002, time=None):
    #     """
    #     Generate a simple bell curve load profile.

    #     - Starts at initial P Load from the raw file.
    #     - Peaks slightly (~5% higher).
    #     - Returns to the original value.
    #     - No noise.

    #     Returns:
    #     - None (updates self.load_profiles).
    #     """

    #     df = self.bus_dataframe  # Get main dataframe
    #     if time is None:
    #         time_data = self.WecGridCore.wecObj_list[0].dataframe.time.to_list()
    #     else:
    #         time_data = time
    #     num_timesteps = len(time_data)

    #     # Get initial P Load values from raw file
    #     p_load_values = df.set_index("BUS_ID")["Pd"].fillna(0)

    #     # Set bell curve shape
    #     midpoint = num_timesteps // 2  # Peak at midpoint
    #     time_index = np.linspace(-1, 1, num_timesteps)  # Range from -1 to 1
    #     bell_curve = np.exp(-4 * time_index**2)  # Standard bell curve

    #     load_profiles = {}

    #     for bus_id, base_load in p_load_values.items():
    #         if base_load == 0:
    #             load_profiles[bus_id] = np.zeros(num_timesteps)
    #             continue

    #         # Scale bell curve: Peaks at ~5% higher than base load
    #         curve = base_load * (1 + 0.05 * bell_curve)
            
    #         noise = np.random.normal(0, noise_level * base_load, num_timesteps)
    #         curve += noise

    #         # Ensure first time step matches initial P Load exactly
    #         curve[0] = base_load

    #         # Store the generated curve
    #         load_profiles[bus_id] = curve

    #     # Create DataFrame with time as index and buses as columns
    #     self.load_profiles = pd.DataFrame(load_profiles, index=time_data)
    

    # def update_load(self, time_step):
    #     """
    #     Update the load at each bus using `load_profiles` for a given time step.

    #     Parameters:
    #     - time_step (int): The time step index in `load_profiles`.

    #     Returns:
    #     - int: Error code from PSS/E API call.
    #     """
        
    
    #     if time_step not in self.load_profiles.index:
    #         print(f"Time step {time_step} not found in load_profiles.")
    #         return -1  # Error code

    #     for bus_id in self.load_profiles.columns:
    #         load_value = self.load_profiles.at[time_step, bus_id]  # Load in MW

    #         if np.isnan(load_value):
    #             load_value = 0.0  # Avoid NaN issues
                
    #         if load_value > 0:
    #             # Default load parameters
    #             _id = "1"
    #             realar = [load_value, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    #             lodtyp = "CONSTP"
    #             intgar = [1, 1, 1, 1, 1, 0, 0]


    #             # Update the load in PSS/E
    #             ierr = PSSEInterface.psspy.load_data_6(ibus=int(bus_id), realar1=load_value)

    #             if ierr > 0:
    #                 print(f"Error updating load at bus {bus_id} for time step {time_step}")
    #                 return ierr

    #     return 0  # Success

    # def simulate(self, snapshots=None, plot=True):

    #     num_wecs = len(self.WecGridCore.wecObj_list)

    #     if time is None:
    #         time = self.WecGridCore.wecObj_list[0].dataframe.time.to_list()
    #     if start is None:
    #         start = time[0]
    #     if end is None:
    #         end = time[-1]
    #     for t in time:
    #         print(f"Running powerflow for time: {t}")
    #         if t >= start and t <= end:
    #             if num_wecs > 0:
    #                 for idx, wec_obj in enumerate(self.WecGridCore.wecObj_list):
    #                     bus = wec_obj.bus_location
    #                     machine_id = wec_obj.gen_id
                        
    #                     # get activate power from wec at time t
    #                     pg = float(wec_obj.dataframe.loc[wec_obj.dataframe.time == t].pg) 
    #                     # adjust activate power 
    #                     ierr = PSSEInterface.psspy.machine_chng_4(
    #                         bus, machine_id, realar1=pg #, realar7=wec_obj.MBASE
    #                     )
    #                     if ierr > 0:
    #                         raise Exception("Error in adjust activate power")
                        
    #                     # ierr, rval = PSSEInterface.psspy.macdat(bus, machine_id, 'MBASE')
    #                     # print(f"Machine {machine_id} MBASE: {rval}")
    #                     # ierr, rval = PSSEInterface.psspy.macdat(bus, machine_id, 'P')
    #                     # print(f"Machine {machine_id} P: {rval}")
    #             self.update_load(t) 
    #             sim_ierr = PSSEInterface.psspy.fnsl()
                
    #             ierr = PSSEInterface.psspy.solved()
    #             self.take_snapshot(metadata={"Solver output": sim_ierr, "Solved Status": ierr})
                
    #         if t > end:
    #             break
    #     return

    # def bus_history(self, bus_num):
    #     pass
    #     #TODO: update to work with new snapshat datatype

    # def plot_bus(self, bus_num, time, arg_1="P", arg_2="Q"):
    #     """
    #     Description: This function plots the activate and reactive power for a given bus
    #     input:
    #         bus_num: the bus number we wanna viz (Int)
    #         time: a list with start and end time (list of Ints)
    #     output:
    #         matplotlib chart
    #     """
    #     #TODO: update to work with new snapshot datatype
    #     visualizer = PSSEVisualizer(psse_obj=self)
    #     visualizer.plot_bus(bus_num, time, arg_1, arg_2)

        
    # # '''
    # # TODO: these function below need to be moved into PSSE-VIZ soon
    # # '''
    # def draw_transformer_arrow(self, ax, path):
    #     """
    #     Draws an arrow along the transformer connection path.
    #     The arrow direction follows the second movement segment.
    #     Adds "^^^" symbol above the arrow at the arrow tip.
    #     """
    #     if len(path) < 4:
    #         return  # Not enough points to draw an arrow

    #     # Select second segment for placing the arrow
    #     x1, y1 = path[2]
    #     x2, y2 = path[3]

    #     dx = (x2 - x1) * 0.3  # Scale down arrow length
    #     dy = (y2 - y1) * 0.3

    #     # **Compute arrow tip**
    #     arrow_tip_x = x1 + dx
    #     arrow_tip_y = y1 + dy

    #     # **Draw arrow**
    #     ax.add_patch(FancyArrow(x1, y1, dx, dy, width=0.005, head_width=0.02, head_length=0.02, color='blue'))

    #     # # **Place "^^^" symbol at arrow tip**
    #     # if dy == 0:  # Horizontal transformer
    #     #     ax.text(arrow_tip_x - 0.01, arrow_tip_y + 0.008, "^^^", fontsize=8, fontweight="bold", ha='center', va='center',rotation=90, color='blue')
    #     # else:  # Vertical transformer
    #     #     ax.text(arrow_tip_x - 0.005, arrow_tip_y - 0.01, "^^^", fontsize=8, fontweight="bold", ha='center', va='center', rotation=180, color='blue')
            
    # def determine_connection_sides(self, from_bus, to_bus, from_pos, to_pos, bus_connections, used_connections):
    #     """
    #     Determines the best connection points for a given bus pair while avoiding overlapping connections.
    #     - Uses x and y positions to determine if the connection is horizontal (left/right) or vertical (top/bottom).
    #     - Selects an available connection within that side (inner, middle, outer) to reduce overlap.
    #     """

    #     y_tuner = 0.1  # Controls how strict we are about vertical vs. horizontal
    #     x_tuner = 0.48  # Controls how strict we are about left/right priority

    #     x1, y1 = from_pos
    #     x2, y2 = to_pos

    #     # --- Step 1: Determine primary connection direction ---
    #     if abs(x1 - x2) > abs(y1 - y2):  
    #         primary_connection = "horizontal"  # Mostly horizontal movement
    #     else:  
    #         primary_connection = "vertical"  # Mostly vertical movement

    #     # Adjust with tuners
    #     if abs(y1 - y2) < y_tuner:
    #         primary_connection = "horizontal"
    #     elif abs(x1 - x2) < x_tuner:
    #         primary_connection = "vertical"

    #     # --- Step 2: Determine connection points ---
    #     if primary_connection == "horizontal":
    #         if x1 < x2:  # Moving left → right
    #             from_side = "right"
    #             to_side = "left"
    #         else:  # Moving right → left
    #             from_side = "left"
    #             to_side = "right"
    #     else:  # Vertical Connection
    #         if y1 > y2:  # Moving top → bottom
    #             from_side = "bottom"
    #             to_side = "top"
    #         else:  # Moving bottom → top
    #             from_side = "top"
    #             to_side = "bottom"

    #     # **Select the best available connection point within the side**
    #     for priority in ["middle", "inner", "outer"]:  # Prioritize middle, then fallback
    #         from_point_key = f"{from_side}_{priority}"
    #         to_point_key = f"{to_side}_{priority}"

    #         if from_point_key not in used_connections[from_bus] and to_point_key not in used_connections[to_bus]:
    #             used_connections[from_bus].add(from_point_key)
    #             used_connections[to_bus].add(to_point_key)
    #             return bus_connections[from_bus][from_point_key], bus_connections[to_bus][to_point_key], f"{from_side}-{to_side}"

    #     # Fallback (shouldn't reach here unless something is wrong)
    #     return bus_connections[from_bus]["right_middle"], bus_connections[to_bus]["left_middle"], "fallback"

    # def route_line(self, p1, p2, connection_type):
    #     """
    #     Creates an L-shaped or Z-shaped path between two points using right-angle bends.
    #     - Left/Right: Midpoint in X first, then Y.
    #     - Top/Bottom: Midpoint in Y first, then X.
    #     """
    #     x1, y1 = p1
    #     x2, y2 = p2

    #     if x1 == x2 or y1 == y2:
    #         return [p1, p2]  # Direct connection

    #     if connection_type in ["left-right", "right-left"]:
    #         mid_x = (x1 + x2) / 2  # First bend in X direction
    #         return [p1, (mid_x, y1), (mid_x, y2), p2]  # Two bends: X first, then Y

    #     elif connection_type in ["top-bottom", "bottom-top"]:
    #         mid_y = (y1 + y2) / 2  # First bend in Y direction
    #         return [p1, (x1, mid_y), (x2, mid_y), p2]  # Two bends: Y first, then X

    #     return [p1, p2]  # Default (fallback)

    # def get_bus_color(self, bus_type):
    #     """ Returns the color for a given bus type. """
    #     color_map = {
    #         1: "#A9A9A9",  # Gray
    #         2: "#32CD32",  # Green
    #         3: "#FF4500",  # Red
    #         4: "#1E90FF",  # Blue
    #     }
    #     return color_map.get(bus_type, "#D3D3D3")  # Default light gray if undefined

    # def sld(self):
    #     """
    #     Generates a structured single-line diagram with correct bus connection logic and predictable bends.
    #     Includes:
    #     - Loads (downward arrows)
    #     - Generators (circles above bus)
    #     """

    #     # --- Step 1: Extract Bus, Load, and Generator Data ---
    #     ierr, bus_numbers = self.psspy.abusint(-1, 1, "NUMBER")
    #     #ierr, bus_types = self.psspy.abusint(-1, 1, "TYPE")
    #     bus_type_df = self.bus_dataframe[["BUS_ID", "TYPE"]]
        
    #     ierr, (from_buses, to_buses) = self.psspy.abrnint(sid=-1, flag=3, string=["FROMNUMBER", "TONUMBER"])
    #     ierr, load_buses = self.psspy.aloadint(-1, 1, "NUMBER")  # Correct API for loads
    #     ierr, gen_buses = self.psspy.amachint(-1, 4, "NUMBER")  # Correct API for generators
    #     ierr, (xfmr_from_buses, xfmr_to_buses) = self.psspy.atrnint(
    #         sid=-1, owner=1, ties=3, flag=2, entry=1, string=["FROMNUMBER", "TONUMBER"]
    #     )
    #     xfmr_pairs = set(zip(xfmr_from_buses, xfmr_to_buses))

    #     # Convert lists to sets for quick lookup
    #     load_buses = set(load_buses[0]) if load_buses[0] else set()
    #     gen_buses = set(gen_buses[0]) if gen_buses[0] else set()

    #     # --- Step 2: Build Graph Representation ---
    #     G = nx.Graph()
    #     for bus in bus_numbers[0]:
    #         G.add_node(bus)
    #     for from_bus, to_bus in zip(from_buses, to_buses):
    #         G.add_edge(from_bus, to_bus)

    #     # --- Step 3: Compute Layout ---
    #     pos = nx.kamada_kawai_layout(G)

    #     # Normalize positions for even spacing
    #     pos_values = np.array(list(pos.values()))
    #     x_vals, y_vals = pos_values[:, 0], pos_values[:, 1]
    #     x_min, x_max = np.min(x_vals), np.max(x_vals)
    #     y_min, y_max = np.min(y_vals), np.max(y_vals)
    #     for node in pos:
    #         pos[node] = (
    #             2 * (pos[node][0] - x_min) / (x_max - x_min) - 1,
    #             1.5 * (pos[node][1] - y_min) / (y_max - y_min) - 0.5
    #         )

    #     # --- Step 4: Create Visualization ---
    #     fig, ax = plt.subplots(figsize=(14, 10))
    #     node_width, node_height = 0.12, 0.04

    #     # Store predefined connection points for each bus
    #     bus_connections = {}
    #     used_connections = {bus: set() for bus in bus_numbers[0]}  # Track used connections
    #     for bus in bus_numbers[0]:
    #         x, y = pos[bus]
    #         bus_connections[bus] = {
    #             # Left side (3 points)
    #             "left_inner": (x - node_width / 2, y - node_height / 3),
    #             "left_middle": (x - node_width / 2, y),
    #             "left_outer": (x - node_width / 2, y + node_height / 3),

    #             # Right side (3 points)
    #             "right_inner": (x + node_width / 2, y - node_height / 3),
    #             "right_middle": (x + node_width / 2, y),
    #             "right_outer": (x + node_width / 2, y + node_height / 3),

    #             # Top side (3 points)
    #             "top_inner": (x - node_width / 3, y + node_height / 2),
    #             "top_middle": (x, y + node_height / 2),
    #             "top_outer": (x + node_width / 3, y + node_height / 2),

    #             # Bottom side (3 points)
    #             "bottom_inner": (x - node_width / 3, y - node_height / 2),
    #             "bottom_middle": (x, y - node_height / 2),
    #             "bottom_outer": (x + node_width / 3, y - node_height / 2),
    #         }

    #     # Draw right-angle connections based on simplified logic
    #     for from_bus, to_bus in zip(from_buses, to_buses):
    #         from_pos = pos[from_bus]
    #         to_pos = pos[to_bus]

    #         try:
    #             p1, p2, ctype = self.determine_connection_sides(from_bus, to_bus, from_pos, to_pos, bus_connections, used_connections)
    #         except KeyError:
    #             continue

    #         path = self.route_line(p1, p2, ctype)

    #         # Draw path segments
    #         for i in range(len(path) - 1):
    #             ax.plot([path[i][0], path[i+1][0]], [path[i][1], path[i+1][1]], 'k-', lw=1.5, linestyle="dashed")
            
    #         if (from_bus, to_bus) in xfmr_pairs or (to_bus, from_bus) in xfmr_pairs:
    #             self.draw_transformer_arrow(ax, path)  # Attach arrow to 2nd segment of the path
    #             #draw_transformer_marker(ax, path)  # Attach diamond marker to midpoint of the path

                
    #     # Draw bus rectangles
    #     for bus in bus_numbers[0]:
    #         x, y = pos[bus]
    #         #temp = bus_numbers[0].index(bus)
            
    #         bus_type = bus_type_df.loc[bus_type_df["BUS_ID"] == bus, "TYPE"].values[0]
    #         bus_color = self.get_bus_color(bus_type)
            
    #         #bus_color = self.get_bus_color()
            
    #         rect = Rectangle((x - node_width / 2, y - node_height / 2), node_width, node_height,
    #                         linewidth=1.5, edgecolor='black', facecolor=bus_color)
    #         ax.add_patch(rect)
    #         ax.text(x, y, str(bus), fontsize=8, fontweight="bold", ha='center', va='center')

    #         # Draw loads (right-offset downward arrows)
    #         if bus in load_buses:
    #             ax.arrow(x + node_width / 2 - 0.02, y + 0.02, 0, 0.05, head_width=0.02, head_length=0.02, fc='black', ec='black')

    #         # Draw generators (left-offset circles above bus)
    #         if bus in gen_buses:
    #             gen_x = x - node_width / 2 + 0.02  # Move generator left
    #             gen_y = y + node_height / 2 + 0.05
    #             gen_size = 0.02
    #             ax.plot([gen_x, gen_x], [y + node_height / 2 + 0.005, gen_y - gen_size ], color='black', lw=2)
    #             ax.add_patch(Circle((gen_x, gen_y), gen_size, color='none', ec='black', lw=1.5))
        
    


    #     ax.set_aspect('equal', adjustable='datalim')
    #     ax.set_xticks([])
    #     ax.set_yticks([])
    #     ax.set_frame_on(False)
    #     ax.set_title(f"Generated Single-Line Diagram of {self.case_file}", fontsize=14)
    #     # Extract the final file name without path and extension
    #     case_file_name = os.path.splitext(os.path.basename(self.case_file))[0]
    #     ax.set_title(f"Generated Single-Line Diagram of {case_file_name}", fontsize=14)
    #     # Define legend elements
    #     legend_elements = [
    #         Line2D([0], [0], marker='o', color='black', markersize=8, label="Generator", markerfacecolor='none', markeredgecolor='black', lw=0),
    #         Line2D([0], [0], marker=('^'), color='blue', markersize=10, label="Transformer", markerfacecolor='blue', lw=0),
    #         Line2D([0], [0], marker='^', color='black', markersize=10, label="Load", markerfacecolor='black', lw=0),
    #         Line2D([0], [0], marker='s', color='red', markersize=10, label="SwingBus", markerfacecolor='red', lw=0),
    #         Line2D([0], [0], marker='s', color='blue', markersize=10, label="WEC Bus", markerfacecolor='blue', lw=0),
    #         Line2D([0], [0], marker='s', color='green', markersize=10, label="PV Bus", markerfacecolor='green', lw=0),
    #         Line2D([0], [0], marker='s', color='gray', markersize=10, label="PQ Bus", markerfacecolor='gray', lw=0),
    #     ]

    #     # Add the legend at the bottom-right
    #     ax.legend(handles=legend_elements, loc="upper left", fontsize=10, frameon=True, edgecolor='black', title="Legend")
    #     plt.show()