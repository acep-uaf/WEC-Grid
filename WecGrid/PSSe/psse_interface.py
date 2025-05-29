"""
PSSe Class Module file
"""

# Standard Libraries
import os
import sys
import contextlib

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

import subprocess
import sys

@contextlib.contextmanager
def silence_stdout():
    new_target = open(os.devnull, 'w')
    old_stdout = sys.stdout
    sys.stdout = new_target
    try:
        yield
    finally:
        sys.stdout = old_stdout

class PSSEInterface:
    
    def __init__(self, case_file: str, engine: "WECGridEngine"):
        self.case_file = case_file
        self.engine = engine
        
        #Grid dfs
        self.bus_dataframe = pd.DataFrame()
        self.bus_dataframe_t = None
        self.generator_dataframe = pd.DataFrame()
        self.generator_dataframe_t = None
        self.branches_dataframe = pd.DataFrame()
        self.branch_flows_dataframe = pd.DataFrame()
        self.plants_dataframe = pd.DataFrame()
        self.loads_dataframe = pd.DataFrame()
        self.two_winding_dataframe = pd.DataFrame()
        self.three_winding_dataframe = pd.DataFrame()
    
        self.snapshots = engine.snapshots
        self.snapshot_history = []
        self.load_profiles = pd.DataFrame()
        self.viz = PSSEVisualizer(self)
        
        #  PSSE stuff
        self._i = None
        self._f = None
        self._s = None
            
    def init_api(self, solver="fnsl", Debug=False) -> bool:
        try:
            with silence_stdout():
                import psspy
                import psse35
                import redirect
                redirect.psse2py() 
                psse35.set_minor(3)
                psspy.psseinit(50)

            if not Debug:
                psspy.prompt_output(6, "", [])
                psspy.alert_output(6, "", [])
                psspy.progress_output(6, "", [])

            PSSEInterface.psspy = psspy
            self._i = psspy.getdefaultint()
            self._f = psspy.getdefaultreal()
            self._s = psspy.getdefaultchar()

        except ModuleNotFoundError as e:
            raise ImportError("PSS®E not found or not configured correctly.") from e

        ext = self.case_file.lower()
        if ext.endswith(".sav"):
            ierr = psspy.case(self.case_file)
        elif ext.endswith(".raw"):
            ierr = psspy.read(1, self.case_file)
        else:
            print("Unsupported case file format.")
            return False

        if ierr != 0:
            print(f"PSS®E failed to load case. ierr={ierr}")
            return False
    

        if self.psspy.fnsl() != 0:
            print("Powerflow solution failed.")
            return False
            
        self.take_snapshot(snapshot=self.engine.start_time, metadata={"step": "initial"})
        print("PSS®E software initialized")
        return True

    class TimeSeriesDict(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            for key, val in kwargs.items():
                self[key] = val
                setattr(self, key, val)

        def __setitem__(self, key, value):
            super().__setitem__(key, value)
            setattr(self, key, value)
            
    def collect_gen_data(self):
        """
        Mimics PyPSA's generators_t dictionary behavior
        """
        p_data, q_data = [], []
        times = []

        for snap in self.snapshot_history:
            gen_df = snap.generators
            if gen_df is None or gen_df.empty:
                continue

            gen_df = gen_df.copy()
            gen_df["GEN_NAME"] = gen_df["GEN_ID"]

            p_row = gen_df.set_index("GEN_NAME")["PGEN_MW"].to_dict()
            q_row = gen_df.set_index("GEN_NAME")["QGEN_MVAR"].to_dict()

            p_data.append(p_row)
            q_data.append(q_row)
            times.append(pd.to_datetime(snap.snapshot))

        p_df = pd.DataFrame(p_data, index=pd.DatetimeIndex(times)).sort_index()
        q_df = pd.DataFrame(q_data, index=pd.DatetimeIndex(times)).sort_index()
        
        p_df.index.name = "snapshot"
        q_df.index.name = "snapshot"

        self.generator_dataframe_t = self.TimeSeriesDict(p=p_df, q=q_df)
        
    def collect_bus_data(self):
        """
        Mimics PyPSA's generators_t dictionary behavior
        """
        p_data, vmag_data = [], []
        times = []

        for snap in self.snapshot_history:
            bus_df = snap.buses
            if bus_df is None or bus_df.empty:
                continue

            bus_df = bus_df.copy()

            p_row = bus_df.set_index("BUS_ID")["PGEN_MW"].to_dict()
            v_row = bus_df.set_index("BUS_ID")["V_PU"].to_dict()

            p_data.append(p_row)
            vmag_data.append(v_row)
            times.append(pd.to_datetime(snap.snapshot))

        p_df = pd.DataFrame(p_data, index=pd.DatetimeIndex(times)).sort_index()
        vmag_df = pd.DataFrame(vmag_data, index=pd.DatetimeIndex(times)).sort_index()
        
        p_df.index.name = "snapshot"
        vmag_df.index.name = "snapshot"

        self.bus_dataframe_t = self.TimeSeriesDict(p=p_df, v_mag_pu=vmag_df)
    
    def pf(self) -> int:
        ierr = self.psspy.fnsl()
        if ierr == 0:
            # ierr == 0 means no error occured 
            return 1 # return True/Sucess
        else:
            print("Error while solving powerflow")
            return ierr

    def adjust_reactive_lim(self) -> bool:
        """
        Adjusts all generators in the PSSE case to remove reactive power limits
        by setting QT = +9999 and QB = -9999.
        """
        ierr, gen_buses = self.psspy.amachint(string=["NUMBER"])
        if ierr > 0:
            print("[ERROR] Failed to retrieve generator bus numbers.")
            return False

        for bus_num in gen_buses[0]:
            # Only modify QT (index 2) and QB (index 3)
            realar_array = [self._f] * 17
            realar_array[2] = 9999.0  # QT (Q max)
            realar_array[3] = -9999.0 # QB (Q min)

            ierr = self.psspy.machine_chng_4(ibus=bus_num, realar=realar_array)
            if ierr > 0:
                print(f"[WARN] Failed to update Q limits at bus {bus_num}.")
        self.take_snapshot(snapshot=self.engine.start_time, metadata={"step": "initial with no Q limits"})
        return True

    def take_snapshot(self, snapshot, metadata):
        metadata = metadata or {}
        # Remove any previous snapshot with this exact timestamp
        self.snapshot_history = [
            snap for snap in self.snapshot_history
            if pd.to_datetime(snap.snapshot) != pd.to_datetime(snapshot)
        ]
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
                "P_MW":           total_act[i].real,
                "Q_MVAR":         total_act[i].imag,
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
        Snapshot of all buses, capturing voltage, angle, shunt, mismatch, and net P/Q.
        Includes total generation and load per bus.
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

        # --- Generator data
        ierr_g, gen_bus_ids = self.psspy.amachint(string=["NUMBER"])
        ierr_pg, pgens = self.psspy.amachreal(string=["PGEN"])
        ierr_qg, qgens = self.psspy.amachreal(string=["QGEN"])
        gen_map = defaultdict(lambda: [0.0, 0.0])
        for b, p, q in zip(gen_bus_ids[0], pgens[0], qgens[0]):
            gen_map[b][0] += p
            gen_map[b][1] += q

        # --- Load data
        ierr_l, load_bus_ids = self.psspy.aloadint(string=["NUMBER"])
        ierr_pl, ploads = self.psspy.aloadcplx(string=["TOTALACT"])
        load_map = defaultdict(lambda: [0.0, 0.0])
        for b, pql in zip(load_bus_ids[0], ploads[0]):
            load_map[b][0] += pql.real
            load_map[b][1] += pql.imag

        # Error check
        if any(ierr != 0 for ierr in [ierr1, ierr3, ierr4, ierr5, ierr_g, ierr_pg, ierr_qg, ierr_l, ierr_pl]):
            raise RuntimeError("Error retrieving bus snapshot data from PSSE.")

        rows = []
        for i in range(len(numbers)):
            bus = numbers[i]
            pgen, qgen = gen_map[bus]
            pload, qload = load_map[bus]
            rows.append({
                "BUS_ID":       bus,
                "BUS_NAME":     bus_names[i].strip(),
                "TYPE":         4 if bus in self.engine.wec_buses else types[i],
                "V_PU":         pu[i],
                "V_KV":         kv[i],
                "BASE_KV":      base_kv[i],
                "PGEN_MW":      pgen,
                "QGEN_MVAR":    qgen,
                "PLOAD_MW":     pload,
                "QLOAD_MVAR":   qload,
                "P_MW":         pgen - pload,
                "Q_MVAR":       qgen - qload,
                "ANGLE_RAD":    angle_rad[i],
                "ANGLE_DEG":    angle_deg[i],
                "MISMATCH_MVA": mismatch_mag[i],
                "MISMATCH_CPLX": mismatch_cplx[i],
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
            name = brnames[i].strip() or f"L{i}"
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
        
        static_branches = self.snapshot_Branches()
        static_branches["KEY"] = list(zip(static_branches["IBUS"], static_branches["JBUS"], static_branches["ID"]))
        name_lookup = static_branches.set_index("KEY")["NAME"]

        rows = []
        for i in range(len(ibus)):
            key = (ibus[i], jbus[i], ids[i].strip())
            name = name_lookup.get(key, f"L{i}")
            rows.append({
                "ID": ids[i].strip(),
                "NAME": name,
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
                "GEN_ID":     f"G{i}" if gen_ids[i].strip() == '1' else gen_ids[i].strip(),
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
    
    def add_wec(self, model, ibus, jbus)->bool:
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
            return False

        # Step 2: Add plant data
        ierr = self.psspy.plant_data_4(
            ibus=ibus, # add plant a wec bus 
            inode=0
        )
        if ierr > 0:
            print(f"Error adding plant data to bus {ibus}. PSS®E error code: {ierr}")
            return False

        for i, wec_obj in enumerate(self.engine.wecObj_list):
            # Step 3: Add a generator at the new bus
            wec_obj.gen_id = f"W{i}"
            wec_obj.gen_name = f"{wec_obj.gen_id}-{wec_obj.model}-{wec_obj.ID}"
            ierr = self.psspy.machine_data_4(
                ibus=ibus, 
                id= f"W{i}", # maybe should just be a number? come back
                realar1= 0.1, # PG, machine active power (0.0 by default)
                realar5= 3.0, # PT 30 kW
                realar6= 0.0, #PB
                realar7=wec_obj.MBASE # 1 MVA typically
            )

            if ierr > 0:
                print(
                    f"Error adding generator {wec_obj.gen_id} to bus {ibus}. PSS®E error code: {ierr}"
                )
                return False

        # Step 4: Add a branch (line) connecting the existing bus to the new bus
        realar_array = [0.0] * 12
        realar_array[0] = 0.0452  # R
        realar_array[1] = 0.1652  # X
        ratings_array = [0.0] * 12
        ratings_array[0] = 130.00  # RATEA
        ierr = self.psspy.branch_data_3(
            ibus=ibus, # from bus
            jbus=jbus,  # to bus
            realar=realar_array,
            namear="WEC Line"
        )
        if ierr > 0:
            print(
                f"Error adding branch from {ibus} to {jbus}. PSS®E error code: {ierr}"
            )
            return False

        self.pf()
        self.take_snapshot(snapshot=self.engine.start_time, metadata={"step": "added wec components"})
        return True
  
    def simulate(self, snapshots=None, sim_length=None, load_curve=False, plot=True)->bool:
        
        if load_curve:
            if self.load_profiles is None or self.load_profiles.empty:
                self.engine.generate_load_profiles()
            
            
        for snapshot in self.snapshots: 
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
        
            if load_curve:
                for bus in self.load_profiles.columns:
                    pl = float(self.load_profiles.loc[snapshot, bus])
                    #intgar_array = [self._i] * 7
                    realar_array = [self._f] * 8
                    realar_array[0] = pl  # active power load in MW

                    ierr = self.psspy.load_data_6(
                        ibus=bus,
                        realar=realar_array
                    )

                    if ierr != 0:
                        print(f"[WARN] Failed to update load at bus {bus} on snapshot {snapshot}")
                        
            ierr = self.pf()
            ival = self.psspy.solved()
            
            if ival == 0:
                self.take_snapshot(snapshot=snapshot, metadata={"Snapshot": snapshot,"Solver output": ierr, "Solved Status": ival})
            else:
                print(f"Powerflow not solved for snapshot {snapshot}. PSS®E error code: {ival}")
                raise Exception("Powerflow not solved")
                return False
        self.collect_gen_data()
        self.collect_bus_data()
        if plot:
            self.viz.plot_all()
        return True 
                
