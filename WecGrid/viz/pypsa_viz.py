"""
PyPSA visualizations module, 
"""
import math

import bqplot as bq
import ipycytoscape
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import networkx as nx
import pandas as pd
import seaborn as sns
from ipywidgets import Dropdown, HTML, HBox, Layout, SelectionSlider, VBox, widgets

class PyPSAVisualizer:
    def __init__(self, engine):
        self.engine = engine

    def plot_all(self, bus_num=None, gen_name=None):
        fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
        self.plot_bus_power(bus_num=bus_num, ax=axes[0], show_title=True, show_legend=False)
        self.plot_bus_vmag(bus_num=bus_num, ax=axes[1], show_title=True, show_legend=False)
        self.plot_generator_power(gen_name=gen_name, ax=axes[2], show_title=True, show_legend=False)

        # ─── 1) Instead of generator_dataframe_t.index (which doesn't exist),
        # grab the DataFrame inside TimeSeriesDict (e.g. .p for active power):
        df_p = self.engine.network.generators_t.p
        # Ensure it's a real DatetimeIndex (it likely already is, but just to be safe):
        df_p.index = pd.to_datetime(df_p.index)
        start_time = df_p.index.min()
        end_time   = df_p.index.max()

        # ─── 2) Force each subplot to use exactly that time range ───
        for ax in axes:
            ax.set_xlim(start_time, end_time)

            # ─── Reapply hour‐only ticks/formatter ───
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H'))
            ax.tick_params(axis='x', rotation=0, labelsize=9)

        # ─── 3) Build the combined legend on the right ───
        handles, labels = [], []
        for ax in axes:
            h, l = ax.get_legend_handles_labels()
            handles.extend(h)
            labels.extend(l)
        unique = dict(zip(labels, handles))

        #fig.suptitle("PSS®E: Simulation Results", fontsize=20)
        fig.legend(
            unique.values(),
            unique.keys(),
            ncol=1,
            loc="center right",
            bbox_to_anchor=(1.0, 0.5),
            #borderaxespad=0.5,
            frameon=True,
        )

        # ─── 4) Leave extra room on the right for the legend ───
        plt.tight_layout(rect=[0, 0, 0.85, 0.95])
        plt.show()
        
    def plot_bus_power(self, bus_num=None, ax=None, show_title=True, show_legend=True):
        p_df = self.engine.network.buses_t.p.copy()
        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        if bus_num is not None:
            bus_col = str(bus_num)
            if bus_col in p_df.columns:
                ax.plot(p_df.index, p_df[bus_col], label=f"Bus {bus_col}", color='C0', linestyle=':', marker='^', linewidth=1.0, markersize=4)
            else:
                print(f"[plot_bus_power] Warning: Bus {bus_col} not found.")
                return
        else:
            for col in p_df.columns:
                ax.plot(p_df.index, p_df[col], label=f"Bus {col}", linestyle=':', marker='^', linewidth=1.0, markersize=4)

        title = f"PyPSA: Bus Active Power Over Time" + (f" — Bus {bus_num}" if bus_num else " (All Buses)")
        if show_title:
            ax.set_title(title)
        ax.set_xlabel("Time")
        ax.set_ylabel("Active Power [MW]")
        ax.grid(True, linestyle="--", alpha=0.6)
        
                # 4) Force x‐limits, hourly ticks, and formatting
        start_time = p_df.index.min()
        end_time   = p_df.index.max()
        ax.set_xlim(start_time, end_time)
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))
        ax.tick_params(axis="x", rotation=0, labelsize=9)

        if show_legend:
            # ax.legend(title="Bus ID", ncol=8, loc='upper center', bbox_to_anchor=(0.5, -0.05))
            ax.legend(title="Bus ID", ncol=8, loc='upper center')

        if create_fig:
            plt.tight_layout()
            plt.show()
        
    def plot_bus_vmag(self, bus_num=None, ax=None,  show_title=True, show_legend=True):
        vmag_df = self.engine.network.buses_t.v_mag_pu.copy()
        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        if bus_num is not None:
            bus_col = str(bus_num)
            if bus_col in vmag_df.columns:
                ax.plot(vmag_df.index, vmag_df[bus_col], label=f"Bus {bus_col}", color="C1", linestyle=':', marker='^', linewidth=1.0, markersize=4)
            else:
                print(f"[plot_bus_vmag] Warning: Bus {bus_col} not found.")
                return
        else:
            for col in vmag_df.columns:
                ax.plot(vmag_df.index, vmag_df[col], label=f"Bus {col}", linestyle=':', marker='^', linewidth=1.0, markersize=4)

        title = f"PyPSA: Bus Voltage Magnitude Over Time" + (f" — Bus {bus_num}" if bus_num else " (All Buses)")
        if show_title:
            ax.set_title(title)
        ax.set_xlabel("Time")
        ax.set_ylabel("Voltage Magnitude [pu]")
        #ax.axhline(1.0, color='gray', linestyle='--', linewidth=1, label="Nominal (1.0 pu)")
        #ax.set_ylim(0.9, 1.1)
        ax.grid(True, linestyle="--", alpha=0.6)
        
        start_time = vmag_df.index.min()
        end_time   = vmag_df.index.max()
        ax.set_xlim(start_time, end_time)
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))
        ax.tick_params(axis="x", rotation=0, labelsize=9)

        if show_legend:
            #ax.legend(title="Bus ID", ncol=8, loc='upper center', bbox_to_anchor=(0.5, -0.05))
            ax.legend(title="Bus ID", ncol=8, loc='upper center')

        if create_fig:
            plt.tight_layout()
            plt.show()
        
    def plot_generator_power(self, gen_name=None, ax=None, show_title=True, show_legend=True):
        self.plot_generator_parameter(gen_name=gen_name, parameter='p', ax=ax, show_title=show_title, show_legend=show_legend)
     
    def plot_generator_reactive_power(self, gen_key=None):
        self.plot_generator_parameter(gen_key=gen_key, parameter='q')

    def plot_generator_parameter(self, gen_name=None, parameter=None, ax=None,  show_title=True, show_legend=True):
        if parameter is None:
            raise ValueError("Parameter must be specified.")

        if parameter == 'p':
            df = self.engine.network.generators_t.p.copy()
            ylabel = "Pgen (MW)"
        elif parameter == 'q':
            df = self.engine.network.generators_t.q.copy()
            ylabel = "Qgen (MVar)"
        else:
            raise ValueError("Parameter must be 'p' or 'q'")

        gen_df = self.engine.network.generators
        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        if gen_name is not None:
            if gen_name not in df.columns:
                print(f"Warning: generator {gen_name} not found.")
                return
            to_plot = [gen_name]
            legend_title = "Generator"
            title = f"PyPSA: Generator {gen_name} {'Active' if parameter == 'p' else 'Reactive'} Power Over Time"
        else:
            to_plot = df.columns.tolist()
            legend_title = "Generator (Bus)"
            title = f"PyPSA: Generator {'Active' if parameter == 'p' else 'Reactive'} Power Over Time (All Generators)"

        for col in to_plot:
            bus = gen_df.at[col, "bus"] if col in gen_df.index else "?"
            label = f"{col} (Bus {bus})"
            ax.plot(df.index, df[col], label=label, linestyle=':', marker='^', linewidth=1.0, markersize=4)

        if show_title:
            ax.set_title(title)
        ax.set_xlabel("Time")
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle="--", alpha=0.6)
        
        start_time = df.index.min()
        end_time   = df.index.max()
        ax.set_xlim(start_time, end_time)
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))
        ax.tick_params(axis="x", rotation=0, labelsize=9)
    

        if show_legend:
            # ax.legend(title=legend_title, bbox_to_anchor=(1.05, 1), loc="upper left")
            ax.legend(title=legend_title, loc="upper left")
        if create_fig:
            plt.tight_layout()
            plt.show()
    
    def plot_branch_percent(self, line_name=None, threshold=80.0):
        """
        Plot only those lines whose percent‐loading exceeds `threshold`
        at any time in the recorded snapshots, unless a specific line_name
        is given (then only that line is shown).

        Parameters
        ----------
        line_name : str, optional
            The PyPSA line index to plot. If None, all lines whose
            percent‐loading ever > threshold will be plotted.

        threshold : float, default=80.0
            The percent‐loading cutoff for auto‐filtering lines.
        """
        import numpy as np
        import pandas as pd
        import matplotlib.pyplot as plt

        # 1) grab the time‐series flows from lines_t
        lines_t = self.engine.network.lines_t.copy()
        lines   = self.engine.network.lines

        # 1a) end‐0 apparent power (MVA), DataFrame (time × lines)
        S0 = np.hypot(lines_t["p0"], lines_t["q0"])

        # 1b) end‐1 apparent power (MVA)
        S1 = np.hypot(lines_t["p1"], lines_t["q1"])

        # 2) pick the heavier‐loaded end, elementwise max -> still DataFrame
        S  = S0.combine(S1, np.maximum)

        # 3) get each line’s rating (MVA), Series indexed by line
        rating = lines["s_nom"].replace(0, np.nan) * lines["s_max_pu"]

        # 4) percent‐loading, broadcast divide by rating across columns
        loading_pct = S.div(rating, axis=1) * 100

        # 5) pick which lines to plot
        if line_name:
            if line_name not in loading_pct.columns:
                print(f"[WARN] Line {line_name!r} not found.")
                return
            to_plot = [line_name]
            title   = f"PyPSA: Line {line_name} Loading (%)"

        else:
            hot     = loading_pct.max(axis=0) > threshold
            to_plot = list(hot[hot].index)
            if not to_plot:
                print(f"[INFO] No lines exceed {threshold}% loading.")
                return
            title   = f"PyPSA: Lines > {threshold}% Loading"

        # 6) plotting
        plt.figure(figsize=(14,6))
        for ln in to_plot:
            plt.plot(loading_pct.index, loading_pct[ln], lw=2, label=ln)

        # draw the threshold line (only in multi‐line mode)
        if not line_name:
            plt.axhline(threshold, color="k", ls="--", alpha=0.6)

        plt.title(title)
        plt.xlabel("Time")
        plt.ylabel("Loading (%)")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.legend(title="Line ID", bbox_to_anchor=(1.05,1), loc="upper left")
        plt.tight_layout()
        plt.ylim(bottom=threshold)
        plt.show()

