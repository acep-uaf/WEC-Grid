"""
PyPSA Modeler Module.

File: src/marinegrid/modeler/powersystem/pypsa.py
"""

# Third-party
import pypsa
import pandas as pd
import numpy as np


# Local
from .base import PowerSystemModeler, SolveResult

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
        self.network: pypsa.Network | None = None
        self.sbase: float | None = None

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
        self.network = network

        # Extract base power from network metadata
        self.sbase = self.network.meta.get("psse_sbase_mva", 100.0)

        # Run initial power flow
        result = self.solve()

        return result.converged

    def solve(self) -> SolveResult:
        """
        Run a single PyPSA power flow calculation.

        Returns:
            SolveResult with convergence status, timing, and iteration count.
        """
        import time as time_module

        if self.network is None:
            return SolveResult(converged=False, message="Network not initialized")

        start = time_module.time()
        result = self.network.pf()
        elapsed = time_module.time() - start

        if isinstance(result, dict):
            converged_val = result.get("converged", False)
            if hasattr(converged_val, "all"):
                converged = bool(converged_val.all())
            else:
                converged = bool(converged_val)

            n_iter_val = result.get("n_iter", 0)
            if hasattr(n_iter_val, "iloc"):
                iterations = int(n_iter_val.iloc[-1])
            else:
                iterations = int(n_iter_val) if n_iter_val else 0
        else:
            converged = False
            iterations = 0

        return SolveResult(
            converged=converged,
            solve_time=elapsed,
            iterations=iterations,
            message="Converged" if converged else "Did not converge",
        )

    def get_bus_data(self) -> pd.DataFrame:
        """
        Retrieve bus data from PyPSA network.

        Captures the current bus state including voltage magnitudes and angles.

        Returns:
            DataFrame with columns:
                - bus: Bus number
                - bus_name: Bus name
                - type: Control type ('PQ', 'PV', 'Slack')
                - p: Net active power injection [per-unit]
                - q: Net reactive power injection [per-unit]
                - v_mag: Voltage magnitude [per-unit]
                - angle_deg: Voltage angle [degrees]
                - vbase: Base voltage [kV]
        """
        if self.network is None:
            return pd.DataFrame()
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
    
    def get_line_data(self) -> pd.DataFrame:
        """
        Retrieve transmission line data from PyPSA network.

        Captures the current line state including power flows and loading.

        Returns:
            DataFrame with columns:
                - line: Line index (1-based)
                - line_name: Line name
                - ibus: From bus number
                - jbus: To bus number
                - p0: Active power flow at ibus [per-unit]
                - p1: Active power flow at jbus [per-unit]
                - loading_pct: Loading as percentage of s_nom
                - s_nom: Thermal rating [MVA]
                - status: Line status (1=in-service, 0=out-of-service)
        """
        if self.network is None:
            return pd.DataFrame()
        n = self.network
        lines = n.lines
        sbase = float(self.sbase) if self.sbase else 100.0

        if lines.empty:
            df = pd.DataFrame()
            df.attrs["df_type"] = "LINE"
            return df

        # choose latest snapshot if available
        if len(n.snapshots) > 0:
            ts = n.snapshots[-1]
            p0_MW = (
                getattr(n.lines_t, "p0", pd.DataFrame())
                .reindex(index=[ts], columns=lines.index)
                .iloc[0]
                .fillna(0.0)
            )
            q0_MVAr = (
                getattr(n.lines_t, "q0", pd.DataFrame())
                .reindex(index=[ts], columns=lines.index)
                .iloc[0]
                .fillna(0.0)
            )
            p1_MW = (
                getattr(n.lines_t, "p1", pd.DataFrame())
                .reindex(index=[ts], columns=lines.index)
                .iloc[0]
                .fillna(0.0)
            )
            q1_MVAr = (
                getattr(n.lines_t, "q1", pd.DataFrame())
                .reindex(index=[ts], columns=lines.index)
                .iloc[0]
                .fillna(0.0)
            )
        else:
            # no time series → assume zero flow
            idx = lines.index
            p0_MW = pd.Series(0.0, index=idx)
            q0_MVAr = pd.Series(0.0, index=idx)
            p1_MW = pd.Series(0.0, index=idx)
            q1_MVAr = pd.Series(0.0, index=idx)

        # Get status from 'active' column if present
        has_active = "active" in lines.columns
        status_series = (
            lines["active"].astype(bool)
            if has_active
            else pd.Series(True, index=lines.index)
        )

        rows = []
        for i, (line_name, line) in enumerate(lines.iterrows()):
            try:
                ibus = int(line.bus0)
            except (ValueError, TypeError):
                ibus = line.bus0

            try:
                jbus = int(line.bus1)
            except (ValueError, TypeError):
                jbus = line.bus1

            line_id = i + 1

            # apparent power (MVA) at each end for loading calculation
            S0 = np.hypot(p0_MW.get(line_name, 0.0), q0_MVAr.get(line_name, 0.0))
            S1 = np.hypot(p1_MW.get(line_name, 0.0), q1_MVAr.get(line_name, 0.0))
            Smax = max(S0, S1)

            s_nom = float(line.s_nom) if pd.notna(line.get("s_nom")) else np.nan
            loading_pct = float(100.0 * Smax / s_nom) if s_nom and s_nom > 0 else np.nan

            rows.append({
                "line": line_id,
                "line_name": line_name,
                "ibus": ibus,
                "jbus": jbus,
                "p0": float(p0_MW.get(line_name, 0.0)) / sbase,
                "p1": float(p1_MW.get(line_name, 0.0)) / sbase,
                "loading_pct": loading_pct,
                "s_nom": s_nom,
                "status": 1 if bool(status_series.get(line_name, True)) else 0,
            })

        df = pd.DataFrame(rows)
        df.attrs["df_type"] = "LINE"
        df.index = pd.RangeIndex(start=0, stop=len(df))
        return df
    
    def get_generator_data(self) -> pd.DataFrame:
        """
        Retrieve generator data from PyPSA network.

        Captures the current generator state including power output and status.

        Returns:
            DataFrame with columns:
                - gen: Generator index (1-based)
                - gen_name: Generator name
                - bus: Bus number the generator is connected to
                - p: Active power output [per-unit]
                - q: Reactive power output [per-unit]
                - p_nom: Nominal power capacity [MW]
                - status: Generator status (1=in-service, 0=out-of-service)
        """
        if self.network is None:
            return pd.DataFrame()
        n = self.network
        gens = n.generators
        sbase = float(self.sbase) if self.sbase else 100.0

        # Get time-series data from latest snapshot
        if len(n.snapshots) > 0:
            ts = n.snapshots[-1]
            p_MW = (
                getattr(n.generators_t, "p", pd.DataFrame())
                .reindex(index=[ts], columns=gens.index)
                .iloc[0]
                .fillna(0.0)
            )
            q_MVAr = (
                getattr(n.generators_t, "q", pd.DataFrame())
                .reindex(index=[ts], columns=gens.index)
                .iloc[0]
                .fillna(0.0)
            )
            # Get status from time-series if available
            stat = (
                getattr(n.generators_t, "status", pd.DataFrame())
                .reindex(index=[ts], columns=gens.index)
                .iloc[0]
            )
            if stat.isna().all() and "active" in gens.columns:
                stat = gens["active"].astype(int).reindex(gens.index).fillna(1)
            else:
                stat = stat.fillna(1).astype(int)
        else:
            idx = gens.index
            p_MW = pd.Series(0.0, index=idx)
            q_MVAr = pd.Series(0.0, index=idx)
            stat = pd.Series(1, index=idx, dtype=int)

        # Build output DataFrame
        rows = []
        for i, (gen_name, gen) in enumerate(gens.iterrows()):
            try:
                bus_num = int(gen.bus)
            except (ValueError, TypeError):
                bus_num = gen.bus

            rows.append({
                "gen": i + 1,
                "gen_name": gen_name,
                "bus": bus_num,
                "p": float(p_MW.get(gen_name, 0.0)) / sbase,
                "q": float(q_MVAr.get(gen_name, 0.0)) / sbase,
                "p_nom": float(gen.get("p_nom", 0.0)) if pd.notna(gen.get("p_nom")) else 0.0,
                "status": int(stat.get(gen_name, 1)),
            })

        df = pd.DataFrame(rows)
        df.attrs["df_type"] = "GEN"
        df.index = pd.RangeIndex(start=0, stop=len(df))
        return df
    
    def get_load_data(self) -> pd.DataFrame:
        """
        Retrieve load data from PyPSA network.

        Captures the current load state including power consumption and status.

        Returns:
            DataFrame with columns:
                - load: Load index (1-based)
                - load_name: Load name
                - bus: Bus number the load is connected to
                - p: Active power consumption [per-unit]
                - q: Reactive power consumption [per-unit]
                - status: Load status (1=in-service, 0=out-of-service)
        """
        if self.network is None:
            return pd.DataFrame()
        n = self.network
        loads = n.loads
        sbase = float(self.sbase) if self.sbase else 100.0

        # Get time-series data from latest snapshot
        if len(n.snapshots) > 0 and hasattr(n.loads_t, "p") and hasattr(n.loads_t, "q"):
            ts = n.snapshots[-1]
            p_MW = (
                n.loads_t.p.reindex(index=[ts], columns=loads.index)
                .iloc[0]
                .fillna(0.0)
            )
            q_MVAr = (
                n.loads_t.q.reindex(index=[ts], columns=loads.index)
                .iloc[0]
                .fillna(0.0)
            )
        else:
            idx = loads.index
            p_MW = pd.Series(0.0, index=idx)
            q_MVAr = pd.Series(0.0, index=idx)

        # Get status from 'active' column if present
        has_active = "active" in loads.columns
        status_series = (
            loads["active"].astype(bool)
            if has_active
            else pd.Series(True, index=loads.index)
        )

        # Build output DataFrame
        rows = []
        for i, (load_name, load) in enumerate(loads.iterrows()):
            try:
                bus_num = int(load.bus)
            except (ValueError, TypeError):
                bus_num = load.bus

            rows.append({
                "load": i + 1,
                "load_name": load_name,
                "bus": bus_num,
                "p": float(p_MW.get(load_name, 0.0)) / sbase,
                "q": float(q_MVAr.get(load_name, 0.0)) / sbase,
                "status": 1 if bool(status_series.get(load_name, True)) else 0,
            })

        df = pd.DataFrame(rows)
        df.attrs["df_type"] = "LOAD"
        df.index = pd.RangeIndex(start=0, stop=len(df))
        return df
    
    def get_transformer_data(self) -> pd.DataFrame:
        """
        Retrieve transformer data from PyPSA network.

        Captures the current transformer state including power flows and tap settings.

        Returns:
            DataFrame with columns:
                - transformer: Transformer index (1-based)
                - transformer_name: Transformer name
                - bus0: From bus number
                - bus1: To bus number
                - p0: Active power flow at bus0 [per-unit]
                - p1: Active power flow at bus1 [per-unit]
                - tap_ratio: Tap ratio
                - phase_shift: Phase shift angle [degrees]
                - s_nom: Thermal rating [MVA]
                - loading_pct: Loading as percentage of s_nom
                - status: Transformer status (1=in-service, 0=out-of-service)
        """
        if self.network is None:
            return pd.DataFrame()
        n = self.network
        transformers = n.transformers
        sbase = float(self.sbase) if self.sbase else 100.0

        if transformers.empty:
            df = pd.DataFrame()
            df.attrs["df_type"] = "TRANSFORMER"
            return df

        # Get time-series data from latest snapshot
        if len(n.snapshots) > 0:
            ts = n.snapshots[-1]
            p0 = (
                getattr(n.transformers_t, "p0", pd.DataFrame())
                .reindex(index=[ts], columns=transformers.index)
                .iloc[0]
                .fillna(0.0)
            )
            p1 = (
                getattr(n.transformers_t, "p1", pd.DataFrame())
                .reindex(index=[ts], columns=transformers.index)
                .iloc[0]
                .fillna(0.0)
            )
            q0 = (
                getattr(n.transformers_t, "q0", pd.DataFrame())
                .reindex(index=[ts], columns=transformers.index)
                .iloc[0]
                .fillna(0.0)
            )
            q1 = (
                getattr(n.transformers_t, "q1", pd.DataFrame())
                .reindex(index=[ts], columns=transformers.index)
                .iloc[0]
                .fillna(0.0)
            )
        else:
            idx = transformers.index
            p0 = pd.Series(0.0, index=idx)
            p1 = pd.Series(0.0, index=idx)
            q0 = pd.Series(0.0, index=idx)
            q1 = pd.Series(0.0, index=idx)

        # Get status from 'active' column if present
        has_active = "active" in transformers.columns
        status_series = (
            transformers["active"].astype(bool)
            if has_active
            else pd.Series(True, index=transformers.index)
        )

        # Build output DataFrame
        rows = []
        for i, (tx_name, tx) in enumerate(transformers.iterrows()):
            try:
                bus0_num = int(tx.bus0)
            except (ValueError, TypeError):
                bus0_num = tx.bus0

            try:
                bus1_num = int(tx.bus1)
            except (ValueError, TypeError):
                bus1_num = tx.bus1

            # Calculate apparent power and loading
            S0 = np.hypot(p0.get(tx_name, 0.0), q0.get(tx_name, 0.0))
            S1 = np.hypot(p1.get(tx_name, 0.0), q1.get(tx_name, 0.0))
            Smax = max(S0, S1)

            s_nom = float(tx.s_nom) if pd.notna(tx.get("s_nom")) else np.nan
            loading_pct = float(100.0 * Smax / s_nom) if s_nom and s_nom > 0 else np.nan

            rows.append({
                "transformer": i + 1,
                "transformer_name": tx_name,
                "bus0": bus0_num,
                "bus1": bus1_num,
                "p0": float(p0.get(tx_name, 0.0)) / sbase,
                "p1": float(p1.get(tx_name, 0.0)) / sbase,
                "tap_ratio": float(tx.get("tap_ratio", 1.0)) if pd.notna(tx.get("tap_ratio")) else 1.0,
                "phase_shift": float(tx.get("phase_shift", 0.0)) if pd.notna(tx.get("phase_shift")) else 0.0,
                "s_nom": s_nom,
                "loading_pct": loading_pct,
                "status": 1 if bool(status_series.get(tx_name, True)) else 0,
            })

        df = pd.DataFrame(rows)
        df.attrs["df_type"] = "TRANSFORMER"
        df.index = pd.RangeIndex(start=0, stop=len(df))
        return df
    
    def update_generator(self, name: str, **kwargs) -> bool:
        """
        Update generator parameters in PyPSA network.

        Args:
            name: Generator identifier (matches PyPSA index).
            **kwargs: Parameters to update. Common options:
                - p_set: Active power setpoint [per-unit on sbase]
                - q_set: Reactive power setpoint [per-unit on sbase]
                - p_nom: Nominal power [MW]
                - status: Generator status 0/1

        Returns:
            True if update succeeded, False otherwise.
        """
        if self.network is None:
            return False

        gen_id = str(name)
        if gen_id not in self.network.generators.index:
            return False

        sbase = float(self.sbase) if self.sbase else 100.0

        for key, value in kwargs.items():
            if key == "p_set":
                self.network.generators.at[gen_id, "p_set"] = float(value) * sbase
            elif key == "q_set":
                self.network.generators.at[gen_id, "q_set"] = float(value) * sbase
            elif key == "p_nom":
                self.network.generators.at[gen_id, "p_nom"] = float(value)
            elif key == "status":
                if "active" in self.network.generators.columns:
                    self.network.generators.at[gen_id, "active"] = bool(value)
            else:
                self.network.generators.at[gen_id, key] = value

        return True
    
    def update_bus(self, name: str, **kwargs) -> bool:
        """
        Update bus parameters in PyPSA network.

        Args:
            name: Bus identifier (matches PyPSA index).
            **kwargs: Parameters to update. Common options:
                - v_mag_pu_set: Voltage magnitude setpoint [per-unit]
                - v_mag_pu_min: Minimum voltage magnitude [per-unit]
                - v_mag_pu_max: Maximum voltage magnitude [per-unit]
                - control: Control mode ('PQ', 'PV', 'Slack')

        Returns:
            True if update succeeded, False otherwise.
        """
        if self.network is None:
            return False

        bus_id = str(name)
        if bus_id not in self.network.buses.index:
            return False

        for key, value in kwargs.items():
            if key == "control":
                control = str(value).upper()
                if control in ("PQ", "PV", "SLACK"):
                    self.network.buses.at[bus_id, "control"] = control
            else:
                self.network.buses.at[bus_id, key] = value

        return True
    
    def update_load(self, name: str, **kwargs) -> bool:
        """
        Update load parameters in PyPSA network.

        Args:
            name: Load identifier (matches PyPSA index).
            **kwargs: Parameters to update. Common options:
                - p_set: Active power consumption [per-unit on sbase]
                - q_set: Reactive power consumption [per-unit on sbase]
                - status: Load status 0/1

        Returns:
            True if update succeeded, False otherwise.
        """
        if self.network is None:
            return False

        load_id = str(name)
        if load_id not in self.network.loads.index:
            return False

        sbase = float(self.sbase) if self.sbase else 100.0

        for key, value in kwargs.items():
            if key == "p_set":
                self.network.loads.at[load_id, "p_set"] = float(value) * sbase
            elif key == "q_set":
                self.network.loads.at[load_id, "q_set"] = float(value) * sbase
            elif key == "status":
                if "active" in self.network.loads.columns:
                    self.network.loads.at[load_id, "active"] = bool(value)
            else:
                self.network.loads.at[load_id, key] = value

        return True
    
    def update_line(self, name: str, **kwargs) -> bool:
        """
        Update transmission line parameters in PyPSA network.

        Args:
            name: Line identifier (matches PyPSA index).
            **kwargs: Parameters to update. Common options:
                - s_nom: Thermal rating [MVA]
                - s_max_pu: Maximum loading as fraction of s_nom
                - status: Line status 0/1

        Returns:
            True if update succeeded, False otherwise.
        """
        if self.network is None:
            return False

        line_id = str(name)
        if line_id not in self.network.lines.index:
            return False

        for key, value in kwargs.items():
            if key == "status":
                if "active" in self.network.lines.columns:
                    self.network.lines.at[line_id, "active"] = bool(value)
            else:
                self.network.lines.at[line_id, key] = value

        return True
    
    def update_transformer(self, name: str, **kwargs) -> bool:
        """
        Update transformer parameters in PyPSA network.

        Args:
            name: Transformer identifier (matches PyPSA index).
            **kwargs: Parameters to update. Common options:
                - tap_ratio: Tap ratio
                - phase_shift: Phase shift angle [degrees]
                - s_nom: Thermal rating [MVA]
                - status: Transformer status 0/1

        Returns:
            True if update succeeded, False otherwise.
        """
        if self.network is None:
            return False

        tx_id = str(name)
        if tx_id not in self.network.transformers.index:
            return False

        for key, value in kwargs.items():
            if key == "status":
                if "active" in self.network.transformers.columns:
                    self.network.transformers.at[tx_id, "active"] = bool(value)
            else:
                self.network.transformers.at[tx_id, key] = value

        return True

    # -------------------------------------------------------------------------
    # Component add/remove methods
    # -------------------------------------------------------------------------

    def add_bus(
        self,
        name: str,
        v_nom: float,
        **kwargs,
    ) -> bool:
        """
        Add a bus to the PyPSA network.

        Args:
            name: Unique bus identifier/name.
            v_nom: Nominal voltage in kV.
            **kwargs: Additional parameters passed to network.add().
                Common options: v_mag_pu_set, v_mag_pu_min, v_mag_pu_max, control, carrier.

        Returns:
            True if bus was added successfully, False otherwise.
        """
        if self.network is None:
            return False
        try:
            # Set defaults
            params = {"carrier": "AC"}
            params.update(kwargs)

            self.network.add("Bus", name=str(name), v_nom=v_nom, **params)
            return True
        except Exception as e:
            print(f"[PyPSA ERROR] Failed to add bus '{name}': {e}")
            return False

    def remove_bus(self, name: str) -> bool:
        """
        Remove a bus from the PyPSA network.

        Also removes all components connected to this bus.

        Args:
            name: Bus identifier/name to remove.

        Returns:
            True if bus was removed successfully, False otherwise.
        """
        if self.network is None:
            return False
        bus_name = str(name)
        if bus_name not in self.network.buses.index:
            return False

        try:
            # Remove connected generators
            connected_gens = self.network.generators[
                self.network.generators.bus == bus_name
            ].index.tolist()
            for gen in connected_gens:
                self.network.remove("Generator", gen)

            # Remove connected loads
            connected_loads = self.network.loads[
                self.network.loads.bus == bus_name
            ].index.tolist()
            for load in connected_loads:
                self.network.remove("Load", load)

            # Remove connected lines (bus0 or bus1)
            connected_lines = self.network.lines[
                (self.network.lines.bus0 == bus_name) |
                (self.network.lines.bus1 == bus_name)
            ].index.tolist()
            for line in connected_lines:
                self.network.remove("Line", line)

            # Remove connected transformers (bus0 or bus1)
            connected_tx = self.network.transformers[
                (self.network.transformers.bus0 == bus_name) |
                (self.network.transformers.bus1 == bus_name)
            ].index.tolist()
            for tx in connected_tx:
                self.network.remove("Transformer", tx)

            # Remove the bus itself
            self.network.remove("Bus", bus_name)
            return True
        except Exception as e:
            print(f"[PyPSA ERROR] Failed to remove bus '{name}': {e}")
            return False

    def add_generator(
        self,
        name: str,
        bus: str,
        p_nom: float,
        **kwargs,
    ) -> bool:
        """
        Add a generator to the PyPSA network.

        Args:
            name: Unique generator identifier/name.
            bus: Bus name where generator connects.
            p_nom: Nominal power capacity in MW.
            **kwargs: Additional parameters passed to network.add().
                Common options: p_set, q_set, p_min_pu, p_max_pu, control, carrier.

        Returns:
            True if generator was added successfully, False otherwise.
        """
        if self.network is None:
            return False
        try:
            # Set defaults
            params = {"carrier": "AC", "control": "PQ"}
            params.update(kwargs)

            self.network.add(
                "Generator",
                name=str(name),
                bus=str(bus),
                p_nom=p_nom,
                **params,
            )
            return True
        except Exception as e:
            print(f"[PyPSA ERROR] Failed to add generator '{name}': {e}")
            return False

    def remove_generator(self, name: str) -> bool:
        """
        Remove a generator from the PyPSA network.

        Args:
            name: Generator identifier/name to remove.

        Returns:
            True if generator was removed successfully, False otherwise.
        """
        if self.network is None:
            return False
        gen_name = str(name)
        if gen_name not in self.network.generators.index:
            return False

        try:
            self.network.remove("Generator", gen_name)
            return True
        except Exception as e:
            print(f"[PyPSA ERROR] Failed to remove generator '{name}': {e}")
            return False

    def add_load(
        self,
        name: str,
        bus: str,
        p_set: float,
        **kwargs,
    ) -> bool:
        """
        Add a load to the PyPSA network.

        Args:
            name: Unique load identifier/name.
            bus: Bus name where load connects.
            p_set: Active power consumption in MW.
            **kwargs: Additional parameters passed to network.add().
                Common options: q_set, carrier.

        Returns:
            True if load was added successfully, False otherwise.
        """
        if self.network is None:
            return False

        try:
            # Set defaults
            params = {"carrier": "AC"}
            params.update(kwargs)

            self.network.add(
                "Load",
                name=str(name),
                bus=str(bus),
                p_set=p_set,
                **params,
            )
            return True
        except Exception as e:
            print(f"[PyPSA ERROR] Failed to add load '{name}': {e}")
            return False

    def remove_load(self, name: str) -> bool:
        """
        Remove a load from the PyPSA network.

        Args:
            name: Load identifier/name to remove.

        Returns:
            True if load was removed successfully, False otherwise.
        """
        if self.network is None:
            return False

        load_name = str(name)
        if load_name not in self.network.loads.index:
            return False

        try:
            self.network.remove("Load", load_name)
            return True
        except Exception as e:
            print(f"[PyPSA ERROR] Failed to remove load '{name}': {e}")
            return False

    def add_line(
        self,
        name: str,
        bus0: str,
        bus1: str,
        **kwargs,
    ) -> bool:
        """
        Add a transmission line to the PyPSA network.

        Args:
            name: Unique line identifier/name.
            bus0: From bus name.
            bus1: To bus name.
            **kwargs: Additional parameters passed to network.add().
                Common options: r, x, b, g, s_nom, length, carrier.

        Returns:
            True if line was added successfully, False otherwise.
        """
        if self.network is None:
            return False

        try:
            # Set defaults
            params = {"carrier": "AC"}
            params.update(kwargs)

            self.network.add(
                "Line",
                name=str(name),
                bus0=str(bus0),
                bus1=str(bus1),
                **params,
            )
            return True
        except Exception as e:
            print(f"[PyPSA ERROR] Failed to add line '{name}': {e}")
            return False

    def remove_line(self, name: str) -> bool:
        """
        Remove a transmission line from the PyPSA network.

        Args:
            name: Line identifier/name to remove.

        Returns:
            True if line was removed successfully, False otherwise.
        """
        if self.network is None:
            return False

        line_name = str(name)
        if line_name not in self.network.lines.index:
            return False

        try:
            self.network.remove("Line", line_name)
            return True
        except Exception as e:
            print(f"[PyPSA ERROR] Failed to remove line '{name}': {e}")
            return False

    def add_transformer(
        self,
        name: str,
        bus0: str,
        bus1: str,
        s_nom: float,
        **kwargs,
    ) -> bool:
        """
        Add a transformer to the PyPSA network.

        Args:
            name: Unique transformer identifier/name.
            bus0: Primary bus name.
            bus1: Secondary bus name.
            s_nom: Nominal apparent power rating [MVA].
            **kwargs: Additional parameters passed to network.add().
                Common options: r, x, tap_ratio, phase_shift.

        Returns:
            True if transformer was added successfully, False otherwise.
        """
        if self.network is None:
            return False

        try:
            self.network.add(
                "Transformer",
                name=str(name),
                bus0=str(bus0),
                bus1=str(bus1),
                s_nom=s_nom,
                **kwargs,
            )
            return True
        except Exception as e:
            print(f"[PyPSA ERROR] Failed to add transformer '{name}': {e}")
            return False

    def remove_transformer(self, name: str) -> bool:
        """
        Remove a transformer from the PyPSA network.

        Args:
            name: Transformer identifier/name to remove.

        Returns:
            True if transformer was removed successfully, False otherwise.
        """
        if self.network is None:
            return False

        tx_name = str(name)
        if tx_name not in self.network.transformers.index:
            return False

        try:
            self.network.remove("Transformer", tx_name)
            return True
        except Exception as e:
            print(f"[PyPSA ERROR] Failed to remove transformer '{name}': {e}")
            return False

    # -------------------------------------------------------------------------
    # WEC Farm Integration
    # -------------------------------------------------------------------------

    def add_wec_farm(self, farm) -> bool:
        """
        Add a WEC farm to the PyPSA network.

        Creates the necessary electrical infrastructure for a WEC farm:
        a new bus at the farm location, a generator representing the farm,
        and a transmission line connecting it to the existing grid.

        Args:
            farm: WECFarm instance containing connection details including
                bus_location, connecting_bus, and device data.

        Returns:
            True if the farm was added successfully, False otherwise.

        Notes:
            - Bus: Created at farm.bus_location with same voltage as connecting_bus
            - Line: Connects WEC bus to grid (hardcoded impedance, TODO: calculate)
            - Generator: Wave carrier type, PV control mode, p_nom from device data
        """
        if self.network is None:
            return False

        try:
            poi_bus_name = str(farm.bus_location)
            conn_bus_name = str(farm.connecting_bus)

            # Get nominal voltage from connecting bus
            poi_v_nom = float(self.network.buses.at[conn_bus_name, "v_nom"])

            # Estimate generator nameplate from WEC data (per-unit on sbase)
            max_pu = 0.0
            for device in farm.devices:
                df = getattr(device, "data", None)
                if df is not None and not df.empty and "p" in df.columns:
                    max_pu = max(max_pu, float(df["p"].abs().max()))

            max_pu_total = max_pu * farm.size if max_pu > 0.0 else 1.0
            sbase_mva = float(self.sbase or farm.sbase or 100.0)
            p_nom_mw = max_pu_total * sbase_mva

            # Generate component names
            gen_name = f"WEC_{farm.farm_id}" if farm.farm_id else f"WEC_{farm.bus_location}"
            line_name = f"WEC_Line_{farm.bus_location}"

            # Add bus for WEC farm
            if not self.add_bus(poi_bus_name, v_nom=poi_v_nom):
                return False

            # Add transmission line connecting WEC to grid
            # TODO: Calculate impedance based on farm specs and distance
            if not self.add_line(
                line_name,
                bus0=poi_bus_name,
                bus1=conn_bus_name,
                r=0.01,
                x=0.05,
                s_nom=130.0,
            ):
                # Rollback: remove bus
                self.remove_bus(poi_bus_name)
                return False

            # Add generator for WEC farm
            if not self.add_generator(
                gen_name,
                bus=poi_bus_name,
                p_nom=p_nom_mw,
                p_set=0.0,
                carrier="wave",
                control="PV",
            ):
                # Rollback: remove line and bus
                self.remove_line(line_name)
                self.remove_bus(poi_bus_name)
                return False

            # Store component names on farm for later reference
            farm.gen_name = gen_name
            farm.bus_name = poi_bus_name
            farm.line_name = line_name

            # Register farm for simulation updates
            if not hasattr(self, "_wec_farms"):
                self._wec_farms = []
            self._wec_farms.append(farm)

            return True

        except Exception as e:
            print(f"[PyPSA ERROR] Failed to add WEC farm: {e}")
            return False

    def remove_wec_farm(self, farm) -> bool:
        """
        Remove a WEC farm from the PyPSA network.

        Removes the generator, line, and bus associated with the farm.

        Args:
            farm: WECFarm instance to remove, or farm identifier (farm_id).

        Returns:
            True if farm was removed successfully, False otherwise.
        """
        if self.network is None:
            return False

        # Handle farm identifier
        if isinstance(farm, (int, str)):
            # Find farm by id
            farm_id = farm
            if not hasattr(self, "_wec_farms"):
                return False
            farm = None
            for f in self._wec_farms:
                if getattr(f, "farm_id", None) == farm_id:
                    farm = f
                    break
            if farm is None:
                return False

        try:
            # Get component names from farm
            gen_name = getattr(farm, "gen_name", None)
            line_name = getattr(farm, "line_name", None)
            bus_name = getattr(farm, "bus_name", None)

            # Remove generator
            if gen_name:
                self.remove_generator(gen_name)

            # Remove line
            if line_name:
                self.remove_line(line_name)

            # Remove bus (will also remove any remaining connected components)
            if bus_name:
                self.remove_bus(bus_name)

            # Remove from internal registry
            if hasattr(self, "_wec_farms") and farm in self._wec_farms:
                self._wec_farms.remove(farm)

            return True

        except Exception as e:
            print(f"[PyPSA ERROR] Failed to remove WEC farm: {e}")
            return False

