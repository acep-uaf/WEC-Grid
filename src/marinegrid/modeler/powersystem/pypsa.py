"""
PyPSA Modeler Module.

File: src/marinegrid/modeler/powersystem/pypsa.py
"""

# Standard library
from typing import Optional

# Third-party
import pypsa
import pandas as pd
import numpy as np


# Local
from .base import PowerSystemModeler
from ...util.convert import Converter
from ...util.grid_instance import GridInstance


class PyPSAModeler(PowerSystemModeler):
    """
    PyPSA power system modeling backend.
    
    Implements the PowerSystemModeler interface for PyPSA, providing
    power flow solving, state capture, and component-level data access
    for PyPSA networks.
    
    Attributes:
        network: PyPSA Network object containing the grid model.
        sbase: System base power in MVA.
    """
    
    def __init__(self):
        """
        Initialize the PyPSA modeler.
        
        Sets up the PyPSA backend with no network loaded. Network must
        be provided via initialize() method.
        """
        # Class objects
        super().__init__(backend="pypsa")
        
        # Class attributes
        self.network: Optional[pypsa.Network] = None
        self.sbase: Optional[float] = None
        
        
    def initialize(self, network: pypsa.Network) -> bool:
        """
        Initialize the PyPSA modeler with a network.
        
        Args:
            network: PyPSA Network object to use for simulations.
        
        Returns:
            True if initialization succeeded, False otherwise.
            
        Raises:
            TypeError: If network is not a pypsa.Network instance.
        """
        if not isinstance(network, pypsa.Network):
            raise TypeError("network must be a pypsa.Network instance.")
        
        self.network = network
        
        # Extract base power from network metadata
        self.sbase = self.network.meta.get("psse_sbase_mva", 100.0)
        
        # Run initial power flow
        self.solve()
        
        return True
    
    def solve(self) -> bool:
        """
        Run PyPSA power flow calculation.
        
        Returns:
            True if power flow converged, False otherwise.
        """
        if self.network is None:
            return False
        
        result = self.network.pf()
        return result.get("converged", False) if isinstance(result, dict) else False
    
    
    def getState(self, timestamp: pd.Timestamp) -> bool:
        """
        Capture current grid state at specified timestamp.
        
        Creates a GridInstance with all component data and appends
        it to the GridData history.
        
        Args:
            timestamp: Timestamp for this grid state snapshot.
        
        Returns:
            True if state capture succeeded, False otherwise.
            
        Raises:
            TypeError: If timestamp is not a pandas Timestamp.
        """
        if not isinstance(timestamp, pd.Timestamp):
            raise TypeError("timestamp must be a pandas Timestamp instance.")
        
        new_state = GridInstance()
        new_state.timestamp = timestamp
        new_state.bus = self.getBusData()
        new_state.line = self.getLineData()
        new_state.gen = self.getGeneratorData()
        new_state.load = self.getLoadData()
        new_state.transformer = self.getTransformerData()
        
        self.data.appendState(new_state)
        
        return True
    
    def simulate(self) -> None:
        """
        Run PyPSA time-series simulation.
        
        Executes power flow calculations across all snapshots in the
        network and captures state at each time step.
        """
        # TODO: Implement time-series simulation logic
        pass
    
    def getBusData(self) -> pd.DataFrame:
        """
        
        """

        # choose the latest snapshot (or change to a passed-in timestamp)
        if len(self.network.snapshots) > 0:
            ts = self.network.snapshots[-1]
            p_MW = (
                getattr(self.network.buses_t, "p", pd.DataFrame())
                .reindex(index=[ts], columns=self.network.buses.index)
                .iloc[0]
                .fillna(0.0)
            )
            q_MVAr = (
                getattr(self.network.buses_t, "q", pd.DataFrame())
                .reindex(index=[ts], columns=self.network.buses.index)
                .iloc[0]
                .fillna(0.0)
            )
            vmag_pu = (
                getattr(self.network.buses_t, "v_mag_pu", pd.DataFrame())
                .reindex(index=[ts], columns=self.network.buses.index)
                .iloc[0]
                .fillna(1.0)
            )
            vang_rad = (
                getattr(self.network.buses_t, "v_ang", pd.DataFrame())
                .reindex(index=[ts], columns=self.network.buses.index)
                .iloc[0]
                .fillna(0.0)
            )
        else:
            # no time series yet
            idx = self.network.buses.index
            p_MW = pd.Series(0.0, index=idx)
            q_MVAr = pd.Series(0.0, index=idx)
            vmag_pu = pd.Series(1.0, index=idx)
            vang_rad = pd.Series(0.0, index=idx)

        df = pd.DataFrame(
            {
                "bus": self.network.buses.index.astype(int),
                "bus_name": [f"Bus_{int(bus_id)}" for bus_id in self.network.buses.index],
                "type": self.network.buses.get("control", pd.Series("PQ", index=self.network.buses.index)).fillna(
                    "PQ"
                ),
                "p": (p_MW / self.sbase).astype(float),
                "q": (q_MVAr / self.sbase).astype(float),
                "v_mag": vmag_pu.astype(float),
                "angle_deg": np.degrees(vang_rad.astype(float)),
                "vbase": self.network.buses.get(
                    "v_nom", pd.Series(np.nan, index=self.network.buses.index)
                ).astype(float),
            }
        )

        df.attrs["df_type"] = "BUS"
        df.index = pd.RangeIndex(start=0, stop=len(df))
        return df
    
    def getLineData(self) -> pd.DataFrame:
        """Capture current transmission line state from PyPSA.

        Builds a Pandas DataFrame of the current transmission line state for the loaded
        PyPSA network. The DataFrame includes line loading percentages and connection
        information.

        Returns:
            pd.DataFrame: DataFrame with columns: line, ibus, jbus, line_pct, status.
                Line names are formatted as "Line_ibus_jbus_count".

        Notes:
            The following PyPSA network data is used to create line snapshots:

            Line Information:
            - Line bus connections (bus0, bus1) [dimensionless]
            - Line thermal ratings (s_nom) [MVA]
            - Line status (assumed active = 1)

            Power Flow Data:
            - Active power flow at both ends [MW]
            - Reactive power flow at both ends [MVAr]
            - Apparent power calculated from P and Q [MVA]
            - Line loading as percentage of thermal rating [%]

            Naming Convention:
            - Lines named as "Line_ibus_jbus_count" for consistency
            - Per-bus-pair counter for multiple parallel lines
            - Bus numbers converted from PyPSA string indices
        """

        # choose latest snapshot if available
        if len(self.network.snapshots) > 0:
            ts = self.network.snapshots[-1]
            p0 = (
                getattr(self.network.lines_t, "p0", pd.DataFrame())
                .reindex(index=[ts], columns=self.network.lines.index)
                .iloc[0]
                .fillna(0.0)
            )
            q0 = (
                getattr(self.network.lines_t, "q0", pd.DataFrame())
                .reindex(index=[ts], columns=self.network.lines.index)
                .iloc[0]
                .fillna(0.0)
            )
            p1 = (
                getattr(self.network.lines_t, "p1", pd.DataFrame())
                .reindex(index=[ts], columns=self.network.lines.index)
                .iloc[0]
                .fillna(0.0)
            )
            q1 = (
                getattr(self.network.lines_t, "q1", pd.DataFrame())
                .reindex(index=[ts], columns=self.network.lines.index)
                .iloc[0]
                .fillna(0.0)
            )
        else:
            # no time series → assume zero flow
            idx = self.network.lines.index
            p0 = pd.Series(0.0, index=idx)
            q0 = pd.Series(0.0, index=idx)
            p1 = pd.Series(0.0, index=idx)
            q1 = pd.Series(0.0, index=idx)

        rows = []

        for i, (line_name, line) in enumerate(self.network.lines.iterrows()):
            ibus_name, jbus_name = line.bus0, line.bus1

            ibus = int(ibus_name)
            jbus = int(jbus_name)

            line_id = i + 1

            # apparent power (MVA) at each end
            S0 = np.hypot(p0[line_name], q0[line_name])
            S1 = np.hypot(p1[line_name], q1[line_name])
            Smax = max(S0, S1)

            s_nom = float(line.s_nom) if pd.notna(line.s_nom) else np.nan
            line_pct = float(100.0 * Smax / s_nom) if s_nom and s_nom > 0 else np.nan

            rows.append(
                {
                    "line": line_id,
                    "line_name": f"Line_{line_id}",
                    "ibus": ibus,
                    "jbus": jbus,
                    "line_pct": line_pct,  # % of s_nom at latest snapshot
                    "status": 1,  # hard coded
                }
            )

        df = pd.DataFrame(rows)
        df.attrs["df_type"] = "LINE"
        df.index = pd.RangeIndex(start=0, stop=len(df))
        return df
    
    def getGeneratorData(self) -> pd.DataFrame:
        """
        Retrieve generator data from PyPSA network.
        
        Returns:
            DataFrame containing generator data with power output and status.
        """
        # TODO: Implement generator data extraction
        return pd.DataFrame()
    
    def getLoadData(self) -> pd.DataFrame:
        """
        Retrieve load data from PyPSA network.
        
        Returns:
            DataFrame containing load data with power consumption and status.
        """
        # TODO: Implement load data extraction
        return pd.DataFrame()
    
    def getTransformerData(self) -> pd.DataFrame:
        """
        Retrieve transformer data from PyPSA network.
        
        Returns:
            DataFrame containing transformer data with flows and tap ratios.
        """
        # TODO: Implement transformer data extraction
        return pd.DataFrame()
    
    def updateGenerator(self, gen_data: pd.DataFrame) -> bool:
        """
        Update generator parameters in PyPSA network.
        
        Args:
            gen_data: DataFrame containing generator data to update.
        
        Returns:
            True if update succeeded, False otherwise.
        """
        # TODO: Implement generator update logic
        return True
    
    def updateBus(self, bus_data: pd.DataFrame) -> bool:
        """
        Update bus parameters in PyPSA network.
        
        Args:
            bus_data: DataFrame containing bus data to update.
        
        Returns:
            True if update succeeded, False otherwise.
        """
        # TODO: Implement bus update logic
        return True
    
    def updateLoad(self, load_data: pd.DataFrame) -> bool:
        """
        Update load parameters in PyPSA network.
        
        Args:
            load_data: DataFrame containing load data to update.
        
        Returns:
            True if update succeeded, False otherwise.
        """
        # TODO: Implement load update logic
        return True
    
    def updateLine(self, line_data: pd.DataFrame) -> bool:
        """
        Update transmission line parameters in PyPSA network.
        
        Args:
            line_data: DataFrame containing line data to update.
        
        Returns:
            True if update succeeded, False otherwise.
        """
        # TODO: Implement line update logic
        return True
    
    def updateTransformer(self, transformer_data: pd.DataFrame) -> bool:
        """
        Update transformer parameters in PyPSA network.
        
        Args:
            transformer_data: DataFrame containing transformer data to update.
        
        Returns:
            True if update succeeded, False otherwise.
        """
        # TODO: Implement transformer update logic
        return True