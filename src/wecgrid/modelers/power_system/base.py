# src/wecgrid/modelers/power_system/base.py
"""Base interfaces and data containers for power-system modelers."""

# Standard library
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Third-party
import numpy as np
import pandas as pd

# Local
from ...wec.farm import WECFarm


class AttrDict(dict):
    """Dict with attribute-style access (``d.key``) to keys.

    Raises:
        AttributeError: If the attribute is not present.
    """

    def __getattr__(self, name):
        """Map attribute access to dictionary lookup.

        Raises:
            AttributeError: If the key is absent.
        """
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'AttrDict' has no attribute '{name}'")

    def __setattr__(self, name, value):
        """Map attribute assignment to setting a dictionary key."""
        self[name] = value


@dataclass
class SolveReport:
    """Lightweight performance log for a simulation run.

    Attributes:
        simulation_time: Total wall time in seconds.
        case: Case name/identifier.
        software: Backend name ("psse", "pypsa").
        iter_time: Per-step iteration time [s].
        converged: Per-step convergence flags.
        pf_solve_time: Powerflow solve time [s] per step.
        pf_solve_iter: Solver iterations per step.
        snapshot_time: Snapshot capture time [s] per step.
        snapshot: Snapshot identifiers (timestamps).
        message: Solver status messages.
    """
    simulation_time: float = 0.0
    case: str = ""
    software: str = ""
    iter_time: list = field(default_factory=list)  # float
    converged: list = field(default_factory=list)  # bool
    pf_solve_time: list = field(default_factory=list)  # float
    pf_solve_iter: list = field(default_factory=list)  # int
    snapshot_time: list = field(default_factory=list)  # float
    snapshot: list = field(default_factory=list)  # time index
    message: list = field(default_factory=list)  # str

    def __repr__(self) -> str:
        """Return a one-line summary of solve status and timing."""
        if not self.converged:
            status = "Unknown"
        else:
            status = "Successful" if all(self.converged) else "Failed"
        return (
            f"SolveReport: {status}, steps={len(self.snapshot)}, time={self.simulation_time:.2f}s, case={self.case}, sw={self.software}"
        )

    def add_iteration_time(self, time_val: float):
        """Record iteration timing for current simulation snapshot.
        
        Args:
            time_val (float): Iteration execution time in seconds.
        """
        self.iter_time.append(time_val)

    def add_pf_solve_data(
        self, solve_time: float, iterations: int, converged: bool, msg: str
    ):
        """Record power flow solver performance data for current snapshot.
        
        Args:
            solve_time (float): Power flow solution time in seconds.
            iterations (int): Number of solver iterations required.
            converged (bool): Whether power flow converged successfully.
            msg (str): Solver status or error message.
        """
        self.converged.append(converged)
        self.pf_solve_time.append(solve_time)
        self.pf_solve_iter.append(iterations)
        self.message.append(msg)

    def add_snapshot_data(self, snapshot_time: float):
        """Record grid state snapshot capture timing.
        
        Args:
            snapshot_time (float): Time required to capture grid state in seconds.
        """
        self.snapshot_time.append(snapshot_time)

    def add_snapshot(self, snapshot_id):
        """Record snapshot identifier for simulation tracking.
        
        Args:
            snapshot_id: Timestamp or identifier for the simulation snapshot.
        """
        self.snapshot.append(snapshot_id)

    @property
    def dataframe(self) -> pd.DataFrame:
        """Convert performance metrics to DataFrame for analysis.
        
        Returns:
            pd.DataFrame: Performance data with columns for timing, convergence,
                and solver statistics. Missing values padded with None.
        """
        # Pad shorter lists with None to match longest list
        max_len = max(
            len(getattr(self, attr))
            for attr in [
                "iter_time",
                "converged",
                "pf_solve_time",
                "pf_solve_iter",
                "snapshot_time",
                "snapshot",
                "message",
            ]
        )

        data = {}
        for attr in [
            "iter_time",
            "converged",
            "pf_solve_time",
            "pf_solve_iter",
            "snapshot_time",
            "snapshot",
            "message",
        ]:
            values = getattr(self, attr)
            # Pad with None if shorter than max_len
            data[attr] = values + [None] * (max_len - len(values))

        return pd.DataFrame(data)


@dataclass
class GridHealthMetrics:
    """Grid stability and health metrics for power system analysis.

    Tracks thermal stress, voltage security, reactive adequacy, inertia proxy,
    and other key performance indicators at each simulation timestep and in aggregate.

    Attributes:
        v_min (float): Minimum acceptable voltage [pu]. Default 0.95.
        v_max (float): Maximum acceptable voltage [pu]. Default 1.05.
        line_loading_warning (float): Line loading warning threshold [%]. Default 90.
        line_loading_critical (float): Line loading critical threshold [%]. Default 100.
        q_loading_threshold (float): Q-limit warning threshold [fraction]. Default 0.8.
        timestep_metrics (List[Dict]): Per-timestep metric snapshots.
        _line_stress_accumulator (Dict): Tracks cumulative stress per line.
        _bus_voltage_accumulator (Dict): Tracks voltage violations per bus.
    """

    v_min: float = 0.95
    v_max: float = 1.05
    line_loading_warning: float = 90.0
    line_loading_critical: float = 100.0
    q_loading_threshold: float = 0.80
    timestep_metrics: List[Dict] = field(default_factory=list)
    _line_stress_accumulator: Dict = field(default_factory=dict)
    _bus_voltage_accumulator: Dict = field(default_factory=dict)
    _gen_q_accumulator: Dict = field(default_factory=dict)

    def __repr__(self) -> str:
        """Return summary of grid health status."""
        if not self.timestep_metrics:
            return "GridHealthMetrics: No data collected"
        
        summary = self.summary
        status = "✓ Healthy" if summary["overall_healthy"] else "⚠ Issues Detected"
        return (
            f"GridHealthMetrics ({len(self.timestep_metrics)} timesteps):\n"
            f"├─ Status: {status}\n"
            f"├─ Thermal Stress:\n"
            f"│   ├─ Max Line Loading: {summary['worst_line_loading_pct']:.1f}%\n"
            f"│   └─ Time Above 90%: {summary['frac_time_line_above_90']*100:.1f}%\n"
            f"├─ Voltage Security:\n"
            f"│   ├─ Violations: {summary['total_voltage_violations']} (under: {summary['total_undervoltage']}, over: {summary['total_overvoltage']})\n"
            f"│   ├─ Voltage Range: [{summary['worst_min_voltage']:.4f}, {summary['worst_max_voltage']:.4f}] pu\n"
            f"│   └─ Min Margin: {summary['worst_voltage_margin']:.4f} pu\n"
            f"├─ Reactive Adequacy:\n"
            f"│   ├─ Max Q Loading: {summary['worst_q_loading']*100:.1f}%\n"
            f"│   └─ Time Q-Limited: {summary['frac_time_q_limited']*100:.1f}%\n"
            f"├─ Inertia Proxy:\n"
            f"│   ├─ Min Sync Gen Share: {summary['min_sync_gen_share']*100:.1f}%\n"
            f"│   └─ Min System Inertia: {summary['min_system_inertia']:.1f} MWs\n"
            f"└─ Convergence Failures: {summary['convergence_failures']}"
        )

    def compute_timestep_metrics(
        self,
        timestamp: datetime,
        bus_df: pd.DataFrame,
        line_df: pd.DataFrame,
        gen_df: pd.DataFrame = None,
        load_df: pd.DataFrame = None,
        converged: bool = True,
        network: Any = None,  # PyPSA network for additional data
        sbase: float = 100.0,
    ) -> Dict:
        """Compute and store health metrics for a single timestep.

        Args:
            timestamp: Simulation timestamp.
            bus_df: Bus state DataFrame with 'v_mag' column.
            line_df: Line state DataFrame with 'line_pct' column.
            gen_df: Generator state DataFrame (optional).
            load_df: Load state DataFrame (optional).
            converged: Whether power flow converged at this timestep.
            network: PyPSA network object for Q limits and inertia (optional).
            sbase: System base MVA for inertia calculations.

        Returns:
            Dict containing all computed metrics for this timestep.
        """
        metrics = {
            "timestamp": timestamp,
            "converged": converged,
        }

        # =====================================================================
        # 1. THERMAL STRESS
        # =====================================================================
        if line_df is not None and "line_pct" in line_df.columns:
            # Work with the full dataframe to avoid index alignment issues
            line_pct_series = line_df["line_pct"].fillna(0)
            
            # Basic statistics (excluding zeros/NaN for meaningful stats)
            valid_line_pct = line_df["line_pct"].dropna()
            metrics["line_loading_max"] = float(valid_line_pct.max()) if len(valid_line_pct) > 0 else np.nan
            metrics["line_loading_mean"] = float(valid_line_pct.mean()) if len(valid_line_pct) > 0 else np.nan
            metrics["line_loading_std"] = float(valid_line_pct.std()) if len(valid_line_pct) > 0 else np.nan
            
            # Count lines above thresholds (use filled series for counting)
            above_90_mask = line_pct_series >= 90.0
            above_100_mask = line_pct_series >= 100.0
            metrics["num_lines_above_90_pct"] = int(above_90_mask.sum())
            metrics["num_lines_above_100_pct"] = int(above_100_mask.sum())
            
            # Warning/critical based on configurable thresholds
            warning_mask = (line_pct_series >= self.line_loading_warning) & (line_pct_series < self.line_loading_critical)
            critical_mask = line_pct_series >= self.line_loading_critical
            metrics["line_warning_count"] = int(warning_mask.sum())
            metrics["line_overload_count"] = int(critical_mask.sum())
            
            # Track stressed lines with their loading values
            line_name_col = "line_name" if "line_name" in line_df.columns else "line"
            if line_name_col in line_df.columns:
                # Store line loading for accumulator and get warning/overload lists
                warning_lines = []
                overload_lines = []
                
                for idx, row in line_df.iterrows():
                    line_name = row[line_name_col]
                    loading = row["line_pct"] if not pd.isna(row["line_pct"]) else 0
                    
                    if line_name not in self._line_stress_accumulator:
                        self._line_stress_accumulator[line_name] = {"max": 0, "sum": 0, "count": 0, "above_90_count": 0}
                    self._line_stress_accumulator[line_name]["max"] = max(self._line_stress_accumulator[line_name]["max"], loading)
                    self._line_stress_accumulator[line_name]["sum"] += loading
                    self._line_stress_accumulator[line_name]["count"] += 1
                    if loading >= 90:
                        self._line_stress_accumulator[line_name]["above_90_count"] += 1
                    
                    # Collect warning and overload lines
                    if loading >= self.line_loading_critical:
                        overload_lines.append(line_name)
                    elif loading >= self.line_loading_warning:
                        warning_lines.append(line_name)
                
                metrics["line_warnings"] = warning_lines
                metrics["line_overloads"] = overload_lines
            else:
                metrics["line_warnings"] = []
                metrics["line_overloads"] = []
        else:
            metrics.update({
                "line_loading_max": np.nan, "line_loading_mean": np.nan, "line_loading_std": np.nan,
                "num_lines_above_90_pct": 0, "num_lines_above_100_pct": 0,
                "line_warning_count": 0, "line_overload_count": 0,
                "line_warnings": [], "line_overloads": []
            })

        # =====================================================================
        # 2. VOLTAGE SECURITY
        # =====================================================================
        if bus_df is not None and "v_mag" in bus_df.columns:
            v_mag = bus_df["v_mag"].dropna()
            
            # Basic statistics
            metrics["v_min"] = float(v_mag.min()) if len(v_mag) > 0 else np.nan
            metrics["v_max"] = float(v_mag.max()) if len(v_mag) > 0 else np.nan
            metrics["v_mean"] = float(v_mag.mean()) if len(v_mag) > 0 else np.nan
            metrics["v_std"] = float(v_mag.std()) if len(v_mag) > 0 else np.nan
            
            # Voltage margin: min(V - v_min, v_max - V) for each bus
            # Negative means violation
            margin_low = v_mag - self.v_min
            margin_high = self.v_max - v_mag
            voltage_margins = np.minimum(margin_low, margin_high)
            metrics["min_voltage_margin"] = float(voltage_margins.min()) if len(voltage_margins) > 0 else np.nan
            metrics["mean_voltage_margin"] = float(voltage_margins.mean()) if len(voltage_margins) > 0 else np.nan
            
            # Track per-bus voltage stats and collect violations
            bus_name_col = "bus_name" if "bus_name" in bus_df.columns else "bus"
            undervoltage_buses = []
            overvoltage_buses = []
            undervoltage_count = 0
            overvoltage_count = 0
            
            for idx, row in bus_df.iterrows():
                v = row["v_mag"] if not pd.isna(row["v_mag"]) else 1.0
                bus_name = row.get(bus_name_col, idx) if bus_name_col in bus_df.columns else idx
                margin = min(v - self.v_min, self.v_max - v)
                
                # Check violations
                if v < self.v_min:
                    undervoltage_count += 1
                    undervoltage_buses.append(bus_name)
                elif v > self.v_max:
                    overvoltage_count += 1
                    overvoltage_buses.append(bus_name)
                
                # Accumulate per-bus voltage data
                if bus_name not in self._bus_voltage_accumulator:
                    self._bus_voltage_accumulator[bus_name] = {
                        "min_v": float('inf'), "max_v": float('-inf'),
                        "min_margin": float('inf'), "violation_count": 0, "count": 0
                    }
                self._bus_voltage_accumulator[bus_name]["min_v"] = min(self._bus_voltage_accumulator[bus_name]["min_v"], v)
                self._bus_voltage_accumulator[bus_name]["max_v"] = max(self._bus_voltage_accumulator[bus_name]["max_v"], v)
                self._bus_voltage_accumulator[bus_name]["min_margin"] = min(self._bus_voltage_accumulator[bus_name]["min_margin"], margin)
                self._bus_voltage_accumulator[bus_name]["count"] += 1
                if v < self.v_min or v > self.v_max:
                    self._bus_voltage_accumulator[bus_name]["violation_count"] += 1
            
            metrics["undervoltage_count"] = undervoltage_count
            metrics["overvoltage_count"] = overvoltage_count
            metrics["voltage_violation_count"] = undervoltage_count + overvoltage_count
            metrics["undervoltage_buses"] = undervoltage_buses
            metrics["overvoltage_buses"] = overvoltage_buses
            
            # Voltage deviation from nominal (1.0 pu)
            metrics["v_deviation_max"] = float(np.abs(v_mag - 1.0).max()) if len(v_mag) > 0 else np.nan
            
        else:
            metrics.update({
                "v_min": np.nan, "v_max": np.nan, "v_mean": np.nan, "v_std": np.nan,
                "undervoltage_count": 0, "overvoltage_count": 0, "voltage_violation_count": 0,
                "undervoltage_buses": [], "overvoltage_buses": [],
                "min_voltage_margin": np.nan, "mean_voltage_margin": np.nan, "v_deviation_max": np.nan
            })

        # =====================================================================
        # 3. REACTIVE ADEQUACY (Q-limits)
        # =====================================================================
        metrics["max_q_loading"] = np.nan
        metrics["mean_q_loading"] = np.nan
        metrics["num_gen_q_limited"] = 0
        metrics["any_gen_q_limited"] = False
        metrics["q_limited_gens"] = []
        
        if gen_df is not None and "q" in gen_df.columns:
            q_gen = gen_df["q"].dropna()
            metrics["total_q_generation_pu"] = float(q_gen.sum()) if len(q_gen) > 0 else np.nan
            
            # Try to get Q limits from network if available
            q_loadings = []
            gen_name_col = "gen_name" if "gen_name" in gen_df.columns else "gen"
            
            if network is not None and hasattr(network, 'generators'):
                for idx, row in gen_df.iterrows():
                    gen_name = row.get(gen_name_col, idx)
                    q_out = abs(row["q"]) if not pd.isna(row["q"]) else 0
                    
                    # Try to get Q limits from PyPSA network
                    q_max = np.nan
                    try:
                        # PyPSA generator naming: try to match
                        pypsa_gen_names = network.generators.index.tolist()
                        # Find matching generator
                        for pg_name in pypsa_gen_names:
                            if str(gen_name) in str(pg_name) or str(pg_name) in str(gen_name):
                                # Get q_max from network (if exists)
                                if 'q_max_pu' in network.generators.columns:
                                    q_max_pu = network.generators.at[pg_name, 'q_max_pu']
                                    p_nom = network.generators.at[pg_name, 'p_nom']
                                    q_max = abs(q_max_pu * p_nom / sbase) if not pd.isna(q_max_pu) else np.nan
                                break
                    except:
                        pass
                    
                    # If no Q limit found, estimate from apparent power capability
                    if pd.isna(q_max) or q_max == 0:
                        # Use p_nom as proxy for S rating, estimate Q_max ~ 0.5 * S
                        p_out = abs(row.get("p", 0)) if not pd.isna(row.get("p", 0)) else 0
                        q_max = max(0.5 * (p_out + 0.1), 0.1)  # Minimum 0.1 pu
                    
                    q_loading = q_out / q_max if q_max > 0 else 0
                    q_loadings.append(q_loading)
                    
                    # Track per-generator Q loading
                    if gen_name not in self._gen_q_accumulator:
                        self._gen_q_accumulator[gen_name] = {"max": 0, "sum": 0, "count": 0, "limited_count": 0}
                    self._gen_q_accumulator[gen_name]["max"] = max(self._gen_q_accumulator[gen_name]["max"], q_loading)
                    self._gen_q_accumulator[gen_name]["sum"] += q_loading
                    self._gen_q_accumulator[gen_name]["count"] += 1
                    if q_loading >= self.q_loading_threshold:
                        self._gen_q_accumulator[gen_name]["limited_count"] += 1
                        metrics["q_limited_gens"].append(str(gen_name))
            
            if q_loadings:
                q_loadings = np.array(q_loadings)
                metrics["max_q_loading"] = float(q_loadings.max())
                metrics["mean_q_loading"] = float(q_loadings.mean())
                metrics["num_gen_q_limited"] = int((q_loadings >= self.q_loading_threshold).sum())
                metrics["any_gen_q_limited"] = metrics["num_gen_q_limited"] > 0

        # Generation totals
        if gen_df is not None and "p" in gen_df.columns:
            p_gen = gen_df["p"].dropna()
            metrics["total_generation_pu"] = float(p_gen.sum()) if len(p_gen) > 0 else np.nan
            metrics["gen_count_active"] = int((p_gen.abs() > 1e-6).sum())
        else:
            metrics["total_generation_pu"] = np.nan
            metrics["gen_count_active"] = 0

        # =====================================================================
        # 4. INERTIA PROXY
        # =====================================================================
        metrics["system_inertia_mws"] = np.nan
        metrics["sync_gen_share"] = np.nan
        metrics["total_online_capacity_mw"] = np.nan
        
        if gen_df is not None and network is not None:
            try:
                total_p_online = 0.0
                sync_p_online = 0.0
                total_inertia = 0.0
                
                # Identify synchronous vs non-synchronous (wind, solar, wave)
                non_sync_carriers = ['wind', 'solar', 'wave', 'battery', 'storage']
                
                for idx, row in gen_df.iterrows():
                    p_out = row.get("p", 0)
                    if pd.isna(p_out) or p_out <= 1e-6:
                        continue
                    
                    p_mw = p_out * sbase
                    total_p_online += p_mw
                    
                    # Check carrier type
                    gen_name_col = "gen_name" if "gen_name" in gen_df.columns else "gen"
                    gen_name = row.get(gen_name_col, idx)
                    
                    carrier = "other"
                    try:
                        # Try to find in PyPSA network
                        for pg_name in network.generators.index:
                            if str(gen_name) in str(pg_name) or str(pg_name) in str(gen_name):
                                carrier = network.generators.at[pg_name, 'carrier'] if 'carrier' in network.generators.columns else 'other'
                                break
                    except:
                        pass
                    
                    is_sync = carrier.lower() not in non_sync_carriers
                    
                    if is_sync:
                        sync_p_online += p_mw
                        
                        # Inertia calculation: H * S_rated
                        # Default H = 4 seconds for conventional generators if not specified
                        H = 4.0  # Default inertia constant
                        try:
                            for pg_name in network.generators.index:
                                if str(gen_name) in str(pg_name) or str(pg_name) in str(gen_name):
                                    if 'inertia' in network.generators.columns:
                                        H = network.generators.at[pg_name, 'inertia']
                                    elif 'H' in network.generators.columns:
                                        H = network.generators.at[pg_name, 'H']
                                    break
                        except:
                            pass
                        
                        # Get rated capacity
                        s_rated = p_mw * 1.1  # Assume S_rated ~ 1.1 * P for typical power factor
                        try:
                            for pg_name in network.generators.index:
                                if str(gen_name) in str(pg_name) or str(pg_name) in str(gen_name):
                                    if 'p_nom' in network.generators.columns:
                                        s_rated = network.generators.at[pg_name, 'p_nom']
                                    break
                        except:
                            pass
                        
                        # System inertia contribution: 2 * H * S_online (in MWs)
                        total_inertia += 2 * H * s_rated
                
                metrics["total_online_capacity_mw"] = total_p_online
                metrics["sync_gen_share"] = sync_p_online / total_p_online if total_p_online > 0 else 1.0
                metrics["system_inertia_mws"] = total_inertia
                
            except Exception as e:
                # If inertia calculation fails, just use sync share
                pass

        # =====================================================================
        # LOAD METRICS
        # =====================================================================
        if load_df is not None and "p" in load_df.columns:
            p_load = load_df["p"].dropna()
            metrics["total_load_pu"] = float(p_load.sum()) if len(p_load) > 0 else np.nan
        else:
            metrics["total_load_pu"] = np.nan

        # =====================================================================
        # POWER BALANCE
        # =====================================================================
        if not np.isnan(metrics.get("total_generation_pu", np.nan)) and not np.isnan(metrics.get("total_load_pu", np.nan)):
            metrics["power_balance_pu"] = metrics["total_generation_pu"] - metrics["total_load_pu"]
        else:
            metrics["power_balance_pu"] = np.nan

        # =====================================================================
        # OVERALL HEALTH FLAG
        # =====================================================================
        metrics["is_healthy"] = (
            converged and
            metrics["voltage_violation_count"] == 0 and
            metrics["line_overload_count"] == 0 and
            not metrics["any_gen_q_limited"]
        )

        # Store and return
        self.timestep_metrics.append(metrics)
        return metrics

    @property
    def summary(self) -> Dict:
        """Compute comprehensive aggregate metrics across all timesteps.

        Returns:
            Dict with overall simulation health statistics including:
            - Fraction of time above thresholds
            - Worst values for each metric
            - Top 5 most stressed components
        """
        if not self.timestep_metrics:
            return self._empty_summary()

        df = self.dataframe
        n_timesteps = len(self.timestep_metrics)

        summary = {
            # Overall
            "overall_healthy": df["is_healthy"].all() if "is_healthy" in df else True,
            "total_timesteps": n_timesteps,
            "healthy_timesteps": int(df["is_healthy"].sum()) if "is_healthy" in df else n_timesteps,
            "unhealthy_timesteps": int((~df["is_healthy"]).sum()) if "is_healthy" in df else 0,
            "convergence_failures": int((~df["converged"]).sum()) if "converged" in df else 0,
            
            # Thermal Stress
            "worst_line_loading_pct": float(df["line_loading_max"].max()) if "line_loading_max" in df else np.nan,
            "mean_line_loading_pct": float(df["line_loading_mean"].mean()) if "line_loading_mean" in df else np.nan,
            "frac_time_line_above_90": float((df["num_lines_above_90_pct"] > 0).sum() / n_timesteps) if "num_lines_above_90_pct" in df else 0,
            "frac_time_line_above_100": float((df["num_lines_above_100_pct"] > 0).sum() / n_timesteps) if "num_lines_above_100_pct" in df else 0,
            "total_line_overloads": int(df["line_overload_count"].sum()) if "line_overload_count" in df else 0,
            "total_line_warnings": int(df["line_warning_count"].sum()) if "line_warning_count" in df else 0,
            
            # Voltage Security
            "worst_min_voltage": float(df["v_min"].min()) if "v_min" in df else np.nan,
            "worst_max_voltage": float(df["v_max"].max()) if "v_max" in df else np.nan,
            "worst_voltage_margin": float(df["min_voltage_margin"].min()) if "min_voltage_margin" in df else np.nan,
            "mean_voltage_margin": float(df["mean_voltage_margin"].mean()) if "mean_voltage_margin" in df else np.nan,
            "frac_time_voltage_violation": float((df["voltage_violation_count"] > 0).sum() / n_timesteps) if "voltage_violation_count" in df else 0,
            "total_voltage_violations": int(df["voltage_violation_count"].sum()) if "voltage_violation_count" in df else 0,
            "total_undervoltage": int(df["undervoltage_count"].sum()) if "undervoltage_count" in df else 0,
            "total_overvoltage": int(df["overvoltage_count"].sum()) if "overvoltage_count" in df else 0,
            
            # Reactive Adequacy
            "worst_q_loading": float(df["max_q_loading"].max()) if "max_q_loading" in df else np.nan,
            "mean_q_loading": float(df["mean_q_loading"].mean()) if "mean_q_loading" in df else np.nan,
            "frac_time_q_limited": float((df["any_gen_q_limited"]).sum() / n_timesteps) if "any_gen_q_limited" in df else 0,
            "total_q_limit_events": int(df["num_gen_q_limited"].sum()) if "num_gen_q_limited" in df else 0,
            
            # Inertia
            "min_sync_gen_share": float(df["sync_gen_share"].min()) if "sync_gen_share" in df else np.nan,
            "mean_sync_gen_share": float(df["sync_gen_share"].mean()) if "sync_gen_share" in df else np.nan,
            "min_system_inertia": float(df["system_inertia_mws"].min()) if "system_inertia_mws" in df else np.nan,
            "mean_system_inertia": float(df["system_inertia_mws"].mean()) if "system_inertia_mws" in df else np.nan,
            
            # Legacy compatibility
            "min_voltage_pu": float(df["v_min"].min()) if "v_min" in df else np.nan,
            "max_voltage_pu": float(df["v_max"].max()) if "v_max" in df else np.nan,
            "max_line_loading_pct": float(df["line_loading_max"].max()) if "line_loading_max" in df else np.nan,
        }
        
        # Add top 5 stressed components
        summary["top_5_stressed_lines"] = self.top_stressed_lines(5)
        summary["top_5_voltage_stressed_buses"] = self.top_voltage_stressed_buses(5)
        summary["top_5_q_stressed_gens"] = self.top_q_stressed_generators(5)
        
        return summary

    def _empty_summary(self) -> Dict:
        """Return empty summary dict when no data collected."""
        return {
            "overall_healthy": True,
            "total_timesteps": 0,
            "healthy_timesteps": 0,
            "unhealthy_timesteps": 0,
            "convergence_failures": 0,
            "worst_line_loading_pct": np.nan,
            "mean_line_loading_pct": np.nan,
            "frac_time_line_above_90": 0,
            "frac_time_line_above_100": 0,
            "total_line_overloads": 0,
            "total_line_warnings": 0,
            "worst_min_voltage": np.nan,
            "worst_max_voltage": np.nan,
            "worst_voltage_margin": np.nan,
            "mean_voltage_margin": np.nan,
            "frac_time_voltage_violation": 0,
            "total_voltage_violations": 0,
            "total_undervoltage": 0,
            "total_overvoltage": 0,
            "worst_q_loading": np.nan,
            "mean_q_loading": np.nan,
            "frac_time_q_limited": 0,
            "total_q_limit_events": 0,
            "min_sync_gen_share": np.nan,
            "mean_sync_gen_share": np.nan,
            "min_system_inertia": np.nan,
            "mean_system_inertia": np.nan,
            "min_voltage_pu": np.nan,
            "max_voltage_pu": np.nan,
            "max_line_loading_pct": np.nan,
            "top_5_stressed_lines": [],
            "top_5_voltage_stressed_buses": [],
            "top_5_q_stressed_gens": [],
        }

    def top_stressed_lines(self, n: int = 5) -> List[Dict]:
        """Get the n most thermally stressed lines across the simulation.

        Args:
            n: Number of lines to return.

        Returns:
            List of dicts with line name, max loading, mean loading, time above 90%.
        """
        if not self._line_stress_accumulator:
            return []
        
        results = []
        for line_name, stats in self._line_stress_accumulator.items():
            if stats["count"] > 0:
                results.append({
                    "line": line_name,
                    "max_loading_pct": stats["max"],
                    "mean_loading_pct": stats["sum"] / stats["count"],
                    "frac_time_above_90": stats["above_90_count"] / stats["count"],
                })
        
        # Sort by max loading descending
        results.sort(key=lambda x: x["max_loading_pct"], reverse=True)
        return results[:n]

    def top_voltage_stressed_buses(self, n: int = 5) -> List[Dict]:
        """Get the n most voltage-stressed buses across the simulation.

        Args:
            n: Number of buses to return.

        Returns:
            List of dicts with bus name, min/max voltage, min margin, violation fraction.
        """
        if not self._bus_voltage_accumulator:
            return []
        
        results = []
        for bus_name, stats in self._bus_voltage_accumulator.items():
            if stats["count"] > 0:
                results.append({
                    "bus": bus_name,
                    "min_voltage_pu": stats["min_v"],
                    "max_voltage_pu": stats["max_v"],
                    "min_margin_pu": stats["min_margin"],
                    "frac_time_violation": stats["violation_count"] / stats["count"],
                })
        
        # Sort by min margin ascending (worst first)
        results.sort(key=lambda x: x["min_margin_pu"])
        return results[:n]

    def top_q_stressed_generators(self, n: int = 5) -> List[Dict]:
        """Get the n most Q-stressed generators across the simulation.

        Args:
            n: Number of generators to return.

        Returns:
            List of dicts with gen name, max Q loading, mean Q loading, time Q-limited.
        """
        if not self._gen_q_accumulator:
            return []
        
        results = []
        for gen_name, stats in self._gen_q_accumulator.items():
            if stats["count"] > 0:
                results.append({
                    "generator": gen_name,
                    "max_q_loading": stats["max"],
                    "mean_q_loading": stats["sum"] / stats["count"],
                    "frac_time_q_limited": stats["limited_count"] / stats["count"],
                })
        
        # Sort by max Q loading descending
        results.sort(key=lambda x: x["max_q_loading"], reverse=True)
        return results[:n]

    @property
    def dataframe(self) -> pd.DataFrame:
        """Convert timestep metrics to DataFrame for analysis.

        Returns:
            pd.DataFrame: Time-indexed DataFrame with all metric columns.
        """
        if not self.timestep_metrics:
            return pd.DataFrame()

        # Exclude list columns for the main dataframe
        list_cols = ["undervoltage_buses", "overvoltage_buses", "line_warnings", "line_overloads", "q_limited_gens"]
        records = []
        for m in self.timestep_metrics:
            record = {k: v for k, v in m.items() if k not in list_cols}
            records.append(record)

        df = pd.DataFrame(records)
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        return df

    def get_violations_at(self, timestamp: datetime) -> Dict:
        """Get detailed violation info for a specific timestep.

        Args:
            timestamp: The timestamp to query.

        Returns:
            Dict with lists of violating buses, lines, and Q-limited generators.
        """
        for m in self.timestep_metrics:
            if m["timestamp"] == timestamp:
                return {
                    "undervoltage_buses": m.get("undervoltage_buses", []),
                    "overvoltage_buses": m.get("overvoltage_buses", []),
                    "line_warnings": m.get("line_warnings", []),
                    "line_overloads": m.get("line_overloads", []),
                    "q_limited_gens": m.get("q_limited_gens", []),
                }
        return {"undervoltage_buses": [], "overvoltage_buses": [], "line_warnings": [], "line_overloads": [], "q_limited_gens": []}

    def worst_timesteps(self, n: int = 5, sort_by: str = "total_violations") -> pd.DataFrame:
        """Get the n timesteps with the most violations.

        Args:
            n: Number of worst timesteps to return.
            sort_by: Column to sort by. Options: "total_violations", "line_loading_max", 
                     "min_voltage_margin", "max_q_loading".

        Returns:
            DataFrame sorted by specified metric (descending for loading, ascending for margin).
        """
        df = self.dataframe.copy()
        if df.empty:
            return df

        if sort_by == "total_violations":
            df["total_violations"] = (
                df.get("voltage_violation_count", 0) + 
                df.get("line_overload_count", 0) +
                df.get("num_gen_q_limited", 0) +
                (~df.get("converged", True)).astype(int)
            )
            return df.nlargest(n, "total_violations")
        elif sort_by == "line_loading_max":
            return df.nlargest(n, "line_loading_max")
        elif sort_by == "min_voltage_margin":
            return df.nsmallest(n, "min_voltage_margin")
        elif sort_by == "max_q_loading":
            return df.nlargest(n, "max_q_loading")
        else:
            return df.head(n)

    def voltage_profile(self) -> pd.DataFrame:
        """Get voltage statistics over time.

        Returns:
            DataFrame with v_min, v_max, v_mean, min_voltage_margin columns indexed by timestamp.
        """
        df = self.dataframe
        if df.empty:
            return df
        cols = ["v_min", "v_max", "v_mean", "min_voltage_margin"]
        available = [c for c in cols if c in df.columns]
        return df[available].copy()

    def line_loading_profile(self) -> pd.DataFrame:
        """Get line loading statistics over time.

        Returns:
            DataFrame with line loading metrics indexed by timestamp.
        """
        df = self.dataframe
        if df.empty:
            return df
        cols = ["line_loading_max", "line_loading_mean", "num_lines_above_90_pct", "num_lines_above_100_pct", "line_warning_count", "line_overload_count"]
        available = [c for c in cols if c in df.columns]
        return df[available].copy()

    def reactive_profile(self) -> pd.DataFrame:
        """Get reactive power / Q-limit statistics over time.

        Returns:
            DataFrame with Q loading metrics indexed by timestamp.
        """
        df = self.dataframe
        if df.empty:
            return df
        cols = ["max_q_loading", "mean_q_loading", "num_gen_q_limited", "any_gen_q_limited"]
        available = [c for c in cols if c in df.columns]
        return df[available].copy()

    def inertia_profile(self) -> pd.DataFrame:
        """Get inertia and synchronous generation statistics over time.

        Returns:
            DataFrame with inertia metrics indexed by timestamp.
        """
        df = self.dataframe
        if df.empty:
            return df
        cols = ["sync_gen_share", "system_inertia_mws", "total_online_capacity_mw"]
        available = [c for c in cols if c in df.columns]
        return df[available].copy()

    def clear(self):
        """Clear all collected metrics."""
        self.timestep_metrics = []
        self._line_stress_accumulator = {}
        self._bus_voltage_accumulator = {}
        self._gen_q_accumulator = {}


@dataclass
class GridState:
    """Snapshot and time-series container for grid components.

    Power quantities are per-unit on system base unless noted.

    Attributes:
        software: Backend identifier.
        case: Case identifier.
        bus: Current bus snapshot DataFrame.
        gen: Current generator snapshot DataFrame.
        line: Current line snapshot DataFrame.
        load: Current load snapshot DataFrame.
        bus_t: Time series by bus variable.
        gen_t: Time series by generator variable.
        line_t: Time series by line variable.
        load_t: Time series by load variable.
    """

    software: str = ""
    case: str = ""
    bus: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    gen: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    line: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    load: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    bus_t: AttrDict = field(default_factory=AttrDict)
    gen_t: AttrDict = field(default_factory=AttrDict)
    line_t: AttrDict = field(default_factory=AttrDict)
    load_t: AttrDict = field(default_factory=AttrDict)

    # todo: need to add a way to identify WECs on a grid, 'G7' is a wecfarm

    def __repr__(self) -> str:
        """Return a compact summary with component counts."""

        def ts_info(component_t):
            """Format time-series information with variable count and snapshot count."""
            if not component_t:
                return "none"
            variables = list(component_t.keys())
            if variables:
                # Get snapshot count from first variable's DataFrame
                snapshot_count = (
                    len(component_t[variables[0]])
                    if len(component_t[variables[0]]) > 0
                    else 0
                )
                var_str = ", ".join(variables)
                return f"{var_str} ({snapshot_count} snapshots)"
            return "none"

        def backend_name(software):
            """Convert software code to descriptive name."""
            names = {
                "psse": "PSS®E Modeler",
                "pypsa": "PyPSA Modeler",
                "": "No backend specified",
            }
            return names.get(software.lower(), f"{software} simulation modeler")

        return (
            f"GridState:\n"
            f"├─ Components:\n"
            f"│   ├─ bus:   {len(self.bus)} components\n"
            f"│   ├─ gen:   {len(self.gen)} components\n"
            f"│   ├─ line:  {len(self.line)} components\n"
            f"│   └─ load:  {len(self.load)} components\n"
            f"├─ Case: {self.case}\n"
            f"└─ Modeler: {self.software}"
        )

    def update(self, component: str, timestamp: pd.Timestamp, df: pd.DataFrame):
        """Set current snapshot and append to time series for a component.

        Args:
            component: One of "bus", "gen", "line", "load".
            timestamp: Snapshot timestamp.
            df: Component DataFrame. Must define ``df.attrs['df_type']`` and
                include an ID column (e.g., "bus", "gen").

        Raises:
            ValueError: If the component or ID mapping cannot be determined.
        """

        if df is None or df.empty:
            return

        # --- figure out the ID column for this df_type ---
        df_type = df.attrs.get("df_type", None)
        id_map = {"BUS": "bus", "GEN": "gen", "LINE": "line", "LOAD": "load"}
        id_col = id_map.get(df_type)
        if id_col is None:
            raise ValueError(f"Cannot determine ID column from df_type='{df_type}'")

        # --- ensure the ID is a real column and set as the index for alignment ---
        if id_col in df.columns:
            pass
        elif df.index.name == id_col:
            df = df.reset_index()
        else:
            raise ValueError(
                f"'{id_col}' not found in columns or as index for df_type='{df_type}'"
            )

        df = df.copy()
        # df.set_index(id_col, inplace=True)   # now index = IDs (bus #, gen ID, etc.)

        # keep snapshot (indexed by ID)
        if not hasattr(self, component):
            raise ValueError(f"No snapshot attribute for component '{component}'")
        setattr(self, component, df)

        # --- write into the time-series store ---
        t_attr = getattr(self, f"{component}_t", None)
        if t_attr is None:
            raise ValueError(f"No time-series attribute for component '{component}'")

        # for each measured variable, maintain a DataFrame with:
        #   rows    = timestamps
        #   columns = component names (not IDs)
        for var in df.columns:
            series = df[var]  # index = IDs, values = this variable for this snapshot

            if var not in t_attr:
                t_attr[var] = pd.DataFrame()

            tdf = t_attr[var]

            # Use component names as column headers instead of IDs
            name_col = f"{component}_name"
            if name_col in df.columns:
                # Create mapping from ID to name
                id_to_name = dict(zip(df.index, df[name_col]))
                # Convert series index from IDs to names
                series_with_names = series.copy()
                series_with_names.index = [
                    id_to_name.get(idx, str(idx)) for idx in series.index
                ]

                # add any new component names as columns
                missing = series_with_names.index.difference(tdf.columns)
                if len(missing) > 0:
                    for col in missing:
                        tdf[col] = pd.NA

                # set the row for this timestamp, one component at a time to avoid alignment issues
                for comp_name, value in series_with_names.items():
                    tdf.loc[timestamp, comp_name] = value
            else:
                # Fallback to using IDs if no name column available
                # add any new IDs as columns
                missing = series.index.difference(tdf.columns)
                if len(missing) > 0:
                    for col in missing:
                        tdf[col] = pd.NA

                # set the row for this timestamp, one component at a time
                for comp_id, value in series.items():
                    tdf.loc[timestamp, comp_id] = value

            t_attr[var] = tdf


class PowerSystemModeler(ABC):
    """Abstract base class for power system modeling backends.

    Defines standardized interface for PSS®E, PyPSA, and other power system tools
    in WEC-GRID framework. Provides grid analysis, WEC integration, and time-series
    simulation capabilities through common API.

    Args:
        engine: WEC-GRID Engine with case_file, time, and wec_farms attributes.

    Attributes:
        engine: Reference to simulation engine.
        grid (GridState): Time-series data for buses, generators, lines, loads.
        report (SolveReport): Performance tracking for simulation runs.
        sbase (float, optional): System base power [MVA].

    Notes:
        - Abstract class - use concrete implementations (PSSEModeler, PyPSAModeler)
        - Grid state data follows standardized schema for cross-platform comparison
        - All abstract methods must be implemented by subclasses
    """

    def __init__(self, engine: Any):
        """Initialize PowerSystemModeler with simulation engine.

        Args:
            engine: WEC-GRID Engine with case_file, time, and wec_farms attributes.

        Note:
            Call init_api() after construction to initialize backend tool.
        """
        self.engine = engine
        self.grid = GridState()
        self.report = SolveReport()
        self._health = GridHealthMetrics()
        self.grid.case = engine.case_name
        self.report.case = engine.case_name

        self.sbase: Optional[float] = None

    @property
    def health(self) -> GridHealthMetrics:
        """Access grid health metrics collected during simulation.

        Returns:
            GridHealthMetrics: Object containing per-timestep and aggregate health data.

        Example:
            >>> engine.pypsa.health
            GridHealthMetrics (288 timesteps):
            ├─ Status: ⚠ Issues Detected
            ├─ Voltage Violations: 12 (under: 8, over: 4)
            ...
        """
        return self._health

    def compute_health_metrics(self, timestamp: datetime = None, converged: bool = True, network: Any = None) -> Dict:
        """Compute and store health metrics for the current grid state.

        Call this after each power flow solve to track grid health over time.

        Args:
            timestamp: Timestamp for this snapshot. Uses current time if None.
            converged: Whether the power flow converged.
            network: Optional PyPSA network object for Q limits and inertia data.

        Returns:
            Dict containing all computed metrics for this timestep.
        """
        if timestamp is None:
            timestamp = datetime.now()

        return self._health.compute_timestep_metrics(
            timestamp=timestamp,
            bus_df=self.grid.bus,
            line_df=self.grid.line,
            gen_df=self.grid.gen,
            load_df=self.grid.load,
            converged=converged,
            network=network,
            sbase=self.sbase if self.sbase else 100.0,
        )

    def __repr__(self) -> str:
        """Return a formatted string representation of the PowerSystemModeler.

        Provides summary of modeler state, case information, and grid statistics.

        Returns:
            str: Multi-line string representation showing modeler configuration and status.

        Example:
            >>> print(modeler)
            PSSEModeler:
            ├─ Case: IEEE_30_bus.raw (100.0 MVA base)
            ├─ Grid Components: 30 buses, 6 generators, 21 loads, 41 lines
            ├─ Time Configuration: 2025-08-23 10:00:00 → 2025-08-23 12:00:00 (5 min steps)
            ├─ WEC Farms: 2 farms, 15 total devices
            └─ Status: ✓ Initialized, ✓ Power flow converged
        """
        # Get class name (e.g., "PSSEModeler", "PyPSAModeler")
        class_name = self.__class__.__name__

        # Case information
        case_name = getattr(self.engine, "case_name", "No case loaded")
        if hasattr(self.engine, "case_file") and self.engine.case_file:
            case_file = (
                str(self.engine.case_file).split("\\")[-1].split("/")[-1]
            )  # Get filename
            case_name = case_file

        sbase_info = f" ({self.sbase} MVA base)" if self.sbase else ""
        case_line = f"├─ Case: {case_name}{sbase_info}"

        # Grid component counts
        grid_line = (
            f"├─ Grid Components: {len(self.grid.bus)} buses, "
            f"{len(self.grid.gen)} generators, {len(self.grid.load)} loads, "
            f"{len(self.grid.line)} lines"
        )

        # Time configuration
        time_line = "├─ Time Configuration: Not configured"
        if hasattr(self.engine, "time") and self.engine.time:
            time_mgr = self.engine.time
            if hasattr(time_mgr, "start_time") and hasattr(time_mgr, "delta_time"):
                start = getattr(time_mgr, "start_time", "Unknown")
                end = getattr(time_mgr, "sim_stop", "Unknown")
                delta = getattr(time_mgr, "delta_time", "Unknown")

                if start != "Unknown" and end != "Unknown":
                    time_line = (
                        f"├─ Time Configuration: {start} → {end} ({delta} min steps)"
                    )
                elif start != "Unknown":
                    time_line = (
                        f"├─ Time Configuration: Starting {start} ({delta} min steps)"
                    )

        # WEC farm information
        wec_line = "├─ WEC Farms: None"
        if hasattr(self.engine, "wec_farms") and self.engine.wec_farms:
            num_farms = len(self.engine.wec_farms)
            total_devices = sum(
                len(farm.wec_devices) for farm in self.engine.wec_farms
            )
            wec_line = f"├─ WEC Farms: {num_farms} farms, {total_devices} total devices"

        # Status indicators (this would be implemented by subclasses with more specific info)
        status_line = "└─ Status: ⚠ Not initialized"

        return (
            f"{class_name}:\n"
            f"{case_line}\n"
            f"{grid_line}\n"
            f"{time_line}\n"
            f"{wec_line}\n"
            f"{status_line}"
        )

    @abstractmethod
    def init_api(self) -> bool:
        """Initialize backend power system tool and load case file.

        Returns:
            bool: True if initialization successful, False otherwise.

        Raises:
            ImportError: If backend tool not found or configured.
            ValueError: If case file invalid or cannot be loaded.

        Notes:
            Implementation should initialize backend API/environment, load case
            file (.sav, .raw, etc.), set system base MVA (self.sbase), perform
            initial power flow solution, and take initial grid state snapshot.
        """
        pass

    @abstractmethod
    def solve_powerflow(self) -> bool:
        """Run power flow solution using backend solver.

        Returns:
            bool: True if power flow converged, False otherwise.

        Notes:
            Implementation should call backend's power flow solver, check
            convergence status, handle solver-specific parameters, and
            suppress verbose output if needed.
        """
        pass

    @abstractmethod
    def add_wec_farm(self, farm: WECFarm) -> bool:
        """Add WEC farm to power system model.

        Args:
            farm (WECFarm): WEC farm with connection details and power characteristics.

        Returns:
            bool: True if farm added successfully, False otherwise.

        Raises:
            ValueError: If WEC farm parameters invalid.

        Notes:
            Implementation should create new bus for WEC connection, add WEC
            generator with power characteristics, create transmission line to
            existing grid, update grid state after modifications, and solve
            power flow to validate changes.
        """
        pass

    @abstractmethod
    def simulate(self, load_curve: Optional[pd.DataFrame] = None) -> bool:
        """Run time-series simulation with WEC and load updates.

        Args:
            load_curve (pd.DataFrame, optional): Load values for each bus at each snapshot.
                Index: snapshots, columns: bus IDs. If None, loads remain constant.

        Returns:
            bool: True if simulation completes successfully, False otherwise.

        Raises:
            Exception: If error updating components or solving power flow.

        Notes:
            Implementation should iterate through all time snapshots from engine.time,
            update WEC generator power outputs [MW] from farm data, update bus loads
            [MW] if load_curve provided, solve power flow at each time step, capture
            grid state snapshots for analysis, and handle convergence failures gracefully.
        """
        pass

    @abstractmethod
    def take_snapshot(self, timestamp: datetime) -> None:
        """Capture current grid state at specified timestamp.

        Args:
            timestamp (datetime): Timestamp for the snapshot.

        Notes:
            Implementation should extract bus data (voltages [p.u.], [degrees], power
            [MW], [MVAr]), generator data (power outputs [MW], [MVAr], status), line
            data (power flows [MW], [MVAr], loading [%]), and load data (power
            consumption [MW], [MVAr]), convert to standardized WEC-GRID schema,
            and store in self.grid with timestamp indexing.
        """
        pass

    # Convenience accessors
    @property
    def bus(self) -> Optional[pd.DataFrame]:
        """Current bus state with columns: bus, bus_name, type, p, q, v_mag, angle_deg, base.

        Returns:
            pd.DataFrame: Bus state data [p.u. on system MVA base] or None if no snapshots.
        """
        return self.grid.bus

    @property
    def gen(self) -> Optional[pd.DataFrame]:
        """Current generator state with columns: gen, bus, p, q, base, status.

        Returns:
            pd.DataFrame: Generator state data [p.u. on generator MVA base] or None if no snapshots.
        """
        return self.grid.gen

    @property
    def load(self) -> Optional[pd.DataFrame]:
        """Current load state with columns: load, bus, p, q, base, status.

        Returns:
            pd.DataFrame: Load state data [p.u. on system MVA base] or None if no snapshots.
        """
        return self.grid.load

    @property
    def line(self) -> Optional[pd.DataFrame]:
        """Current line state with columns: line, ibus, jbus, line_pct, status.

        Returns:
            pd.DataFrame: Line state data [line_pct as % of thermal rating] or None if no snapshots.
        """
        return self.grid.line

    @property
    def bus_t(self) -> Dict[str, pd.DataFrame]:
        """Time-series bus data for all snapshots.

        Returns:
            Dict[str, pd.DataFrame]: Keys: timestamp strings, Values: bus state DataFrames.
        """
        return self.grid.bus_t

    @property
    def gen_t(self) -> Dict[str, pd.DataFrame]:
        """Time-series generator data for all snapshots.

        Returns:
            Dict[str, pd.DataFrame]: Keys: timestamp strings, Values: generator state DataFrames.
        """
        return self.grid.gen_t

    @property
    def load_t(self) -> Dict[str, pd.DataFrame]:
        """Time-series load data for all snapshots.

        Returns:
            Dict[str, pd.DataFrame]: Keys: timestamp strings, Values: load state DataFrames.
        """
        return self.grid.load_t

    @property
    def line_t(self) -> Dict[str, pd.DataFrame]:
        """Time-series line data for all snapshots.

        Returns:
            Dict[str, pd.DataFrame]: Keys: timestamp strings, Values: line state DataFrames.
        """
        return self.grid.line_t
