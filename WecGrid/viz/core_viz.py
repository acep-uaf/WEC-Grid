"""
WECGrid Engine Visualization Module
"""
import math

import bqplot as bq
import ipycytoscape
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
import pandas as pd
import seaborn as sns
from ipywidgets import Dropdown, HTML, HBox, Layout, SelectionSlider, VBox, widgets


class WECGridVisualizer:
    def __init__(self, engine):
        self.engine = engine


import matplotlib.pyplot as plt

class WECGridVisualizer:
    def __init__(self, engine):
        self.engine = engine
        
    def sld(self):
        if self.engine.psse is not None:
            self.engine.psse.viz.sld()
        else:
            print("PSS®E not initialized. Cannot generate SLD.")

    def plot_comparison(self):
        fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
        
        self._plot_all_generator_comparison(ax=axes[0], show_title=True, show_legend=False)
        self._plot_all_bus_power_comparison(ax=axes[1], show_title=True, show_legend=False)
        self._plot_all_bus_vmag_comparison(ax=axes[2], show_title=True, show_legend=False)

        handles, labels = [], []
        for ax in axes:
            h, l = ax.get_legend_handles_labels()
            handles.extend(h)
            labels.extend(l)

        unique = dict(zip(labels, handles))
        fig.suptitle("PSS®E vs PyPSA: Comparison Results", fontsize=16)
        fig.legend(unique.values(), unique.keys(), ncol=8, loc='upper center', bbox_to_anchor=(0.5, -0.05))
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        plt.show()
        
    def plot_generator_comparison(self, *args, **kwargs):
        total = len(args) + len(kwargs)
        if total == 1:
            return self._plot_single_generator_comparison(*args, **kwargs)
        elif total == 0:
            return self._plot_all_generator_comparison(*args, **kwargs)
        else:
            raise TypeError("plot_generator_comparison requires one (single) or two (all) arguments")

    def plot_bus_power_comparison(self, *args, **kwargs):
        total = len(args) + len(kwargs)
        if total == 1:
            return self._plot_single_bus_power_comparison(*args, **kwargs)
        elif total == 0:
            return self._plot_all_bus_power_comparison(*args, **kwargs)
        else:
            raise TypeError("plot_bus_power_comparison requires zero (all) or one (single) argument")

    def plot_bus_vmag_comparison(self, *args, **kwargs):
        total = len(args) + len(kwargs)
        if total == 1:
            return self._plot_single_bus_vmag_comparison(*args, **kwargs)
        elif total == 0:
            return self._plot_all_bus_vmag_comparison(*args, **kwargs)
        else:
            raise TypeError("plot_bus_vmag_comparison requires zero (all) or one (single) argument")     
        
    def _plot_all_generator_comparison(self, ax=None, show_title=True, show_legend=True):
        # pull full active‐power time series
        psse_gen = self.engine.psse.generator_dataframe_t.p.copy()
        pypsa_gen = self.engine.pypsa.network.generators_t.p.copy()

        # find generators common to both
        common = sorted(set(psse_gen.columns) & set(pypsa_gen.columns))
        if not common:
            print("[WARN] No common generator names between PSS®E and PyPSA.")
            return

        # create figure/axis if none passed
        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        # plot each gen with same color but different markers; only label once
        colors = plt.cm.tab10.colors
        handles = []
        for i, gen in enumerate(common):
            c = colors[i % len(colors)]
            # PSS®E: circle marker
            line, = ax.plot(
                psse_gen.index, psse_gen[gen],
                linestyle='-', marker='o', color=c, markersize=4, label=gen
            )
            # PyPSA: triangle marker, no label (shares legend entry)
            ax.plot(
                pypsa_gen.index, pypsa_gen[gen],
                linestyle='--', marker='^', color=c, markersize=4
            )
            handles.append(line)

        if show_title:
            ax.set_title("Generator Active Power Comparison — PSS®E ● PyPSA ▲")
        ax.set_xlabel("Time")
        ax.set_ylabel("P (MW)")
        ax.grid(True, linestyle="--", alpha=0.6)

        if show_legend:
            ax.legend(handles=handles, title="Generator", bbox_to_anchor=(1.05, 1), loc="upper left")

        if create_fig:
            plt.tight_layout()
            plt.show()

    def _plot_single_generator_comparison(self, gen_name, ax=None, show_title=True, show_legend=True):
        # pull full active‐power time series
        psse_gen = self.engine.psse.generator_dataframe_t.p.copy()
        pypsa_gen = self.engine.pypsa.network.generators_t.p.copy()

        # ensure this generator exists in both
        common = set(psse_gen.columns) & set(pypsa_gen.columns)
        if gen_name not in common:
            print(f"[WARN] Generator {gen_name} not found in both datasets.")
            return

        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        # fixed colors
        psse_color = 'blue'
        pypsa_color = 'red'

        # PSS®E
        p_line, = ax.plot(
            psse_gen.index, psse_gen[gen_name],
            linestyle='-', marker='o', color=psse_color, markersize=5, label="PSS®E"
        )
        # PyPSA
        py_line, = ax.plot(
            pypsa_gen.index, pypsa_gen[gen_name],
            linestyle='--', marker='^', color=pypsa_color, markersize=5, label="PyPSA"
        )

        if show_title:
            ax.set_title(f"Generator {gen_name} Comparison")
        ax.set_xlabel("Time")
        ax.set_ylabel("P (MW)")
        ax.grid(True, linestyle="--", alpha=0.6)

        if show_legend:
            ax.legend(handles=[p_line, py_line], title=gen_name, bbox_to_anchor=(1.05, 1), loc="upper left")

        if create_fig:
            plt.tight_layout()
            plt.show()

    def _plot_all_bus_power_comparison(self, ax=None, show_title=True, show_legend=True):
        # pull PSS®E & PyPSA time series
        psse_bus = self.engine.psse.bus_dataframe_t.p.copy()
        pypsa_bus = self.engine.pypsa.network.buses_t.p.copy()

        # figure out which bus columns (as strings) are in both
        psse_cols = set(map(str, psse_bus.columns))
        pypsa_cols = set(map(str, pypsa_bus.columns))
        common_keys = sorted(psse_cols & pypsa_cols, key=lambda x: int(x))
        if not common_keys:
            print("[WARN] No common bus numbers between PSS®E and PyPSA.")
            return

        # make a new figure only if none passed
        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        colors = plt.cm.tab10.colors
        handles = []
        for i, key in enumerate(common_keys):
            color = colors[i % len(colors)]

            # PSS®E: solid circle
            psse_line, = ax.plot(
                psse_bus.index, psse_bus[int(key)],
                linestyle=':', marker='o', color=color, alpha=1.0,
                linewidth=1.0, markersize=4, label=f"Bus {key}"
            )
            # PyPSA: dashed triangle (no extra legend entry)
            ax.plot(
                pypsa_bus.index, pypsa_bus[key],
                linestyle=':', marker='^', color=color, alpha=1.0,
                linewidth=1.0, markersize=4
            )

            handles.append(psse_line)

        if show_title:
            ax.set_title("Bus Active Power Comparison — PSS®E ● vs PyPSA ▲")
        ax.set_xlabel("Time")
        ax.set_ylabel("P (MW)")
        ax.grid(True, linestyle="--", alpha=0.6)

        if show_legend and create_fig:
            fig.legend(
                handles=handles,
                title="Bus",
                ncol=10,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.05)
            )

        if create_fig:
            plt.tight_layout(rect=[0, 0, 1, 0.95])
            plt.show()

    def _plot_single_bus_power_comparison(self, bus_num, ax=None, show_title=True, show_legend=True):
        # pull PSS®E & PyPSA time series
        psse_bus = self.engine.psse.bus_dataframe_t.p.copy()
        pypsa_bus = self.engine.pypsa.network.buses_t.p.copy()

        # ensure this bus exists
        psse_cols = set(map(str, psse_bus.columns))
        pypsa_cols = set(map(str, pypsa_bus.columns))
        common = psse_cols & pypsa_cols
        if str(bus_num) not in common:
            print(f"[WARN] Bus {bus_num} not found in both datasets.")
            return

        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        # psse blue, pypsa red
        p_line, = ax.plot(
            psse_bus.index, psse_bus[int(bus_num)],
            linestyle=':', marker='o', color='blue', alpha=1.0,
            linewidth=1.0, markersize=5, label="PSS®E"
        )
        py_line, = ax.plot(
            pypsa_bus.index, pypsa_bus[str(bus_num)],
            linestyle=':', marker='^', color='red', alpha=1.0,
            linewidth=1.0, markersize=5, label="PyPSA"
        )

        if show_title:
            ax.set_title(f"Bus {bus_num} Power Comparison")
        ax.set_xlabel("Time")
        ax.set_ylabel("P (MW)")
        ax.grid(True, linestyle="--", alpha=0.6)

        if show_legend:
            ax.legend(
                handles=[p_line, py_line],
                title=f"Bus {bus_num}",
                bbox_to_anchor=(1.05, 1),
                loc="upper left"
            )

        if create_fig:
            plt.tight_layout()
            plt.show()
            
    def _plot_all_bus_vmag_comparison(self, ax=None, show_title=True, show_legend=True):
        # pull PSS®E & PyPSA voltage‐pu time series
        psse_bus = self.engine.psse.bus_dataframe_t.v_mag_pu.copy()
        pypsa_bus = self.engine.pypsa.network.buses_t.v_mag_pu.copy()

        # columns in common (as strings), sorted numerically
        psse_cols = set(map(str, psse_bus.columns))
        pypsa_cols = set(map(str, pypsa_bus.columns))
        common_keys = sorted(psse_cols & pypsa_cols, key=lambda x: int(x))
        if not common_keys:
            print("[WARN] No common bus numbers between PSS®E and PyPSA.")
            return

        # new figure if needed
        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        colors = plt.cm.tab10.colors
        handles = []
        for i, key in enumerate(common_keys):
            color = colors[i % len(colors)]

            # PSS®E: circle
            line, = ax.plot(
                psse_bus.index, psse_bus[int(key)],
                linestyle=':', marker='o', color=color, alpha=1.0,
                linewidth=1.0, markersize=4, label=f"Bus {key}"
            )
            # PyPSA: triangle (no extra legend entry)
            ax.plot(
                pypsa_bus.index, pypsa_bus[key],
                linestyle=':', marker='^', color=color, alpha=1.0,
                linewidth=1.0, markersize=4
            )
            handles.append(line)

        if show_title:
            ax.set_title("Bus Voltage Magnitude Comparison — PSS®E ● vs PyPSA ▲")
        ax.set_xlabel("Time")
        ax.set_ylabel("Voltage (pu)")
        ax.grid(True, linestyle="--", alpha=0.6)

        if show_legend and create_fig:
            fig.legend(
                handles=handles,
                title="Bus",
                ncol=10,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.05)
            )

        if create_fig:
            plt.tight_layout(rect=[0,0,1,0.95])
            plt.show()

    def _plot_single_bus_vmag_comparison(self, bus_num, ax=None, show_title=True, show_legend=True):
        # pull PSS®E & PyPSA voltage‐pu time series
        psse_bus = self.engine.psse.bus_dataframe_t.v_mag_pu.copy()
        pypsa_bus = self.engine.pypsa.network.buses_t.v_mag_pu.copy()

        # check existence
        psse_cols = set(map(str, psse_bus.columns))
        pypsa_cols = set(map(str, pypsa_bus.columns))
        if str(bus_num) not in (psse_cols & pypsa_cols):
            print(f"[WARN] Bus {bus_num} not found in both datasets.")
            return

        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        # fixed colors
        p_color = 'blue'
        py_color = 'red'

        p_line, = ax.plot(
            psse_bus.index, psse_bus[int(bus_num)],
            linestyle=':', marker='o', color=p_color, alpha=1.0,
            linewidth=1.0, markersize=5, label="PSS®E"
        )
        py_line, = ax.plot(
            pypsa_bus.index, pypsa_bus[str(bus_num)],
            linestyle=':', marker='^', color=py_color, alpha=1.0,
            linewidth=1.0, markersize=5, label="PyPSA"
        )

        if show_title:
            ax.set_title(f"Bus {bus_num} Voltage Comparison")
        ax.set_xlabel("Time")
        ax.set_ylabel("Voltage (pu)")
        ax.grid(True, linestyle="--", alpha=0.6)

        if show_legend:
            ax.legend(
                handles=[p_line, py_line],
                title=f"Bus {bus_num}",
                bbox_to_anchor=(1.05, 1),
                loc="upper left"
            )

        if create_fig:
            plt.tight_layout()
            plt.show()
      
            
        # psse_bus = self.psse.bus_dataframe_t.v_mag_pu.copy()
        # pypsa_bus = self.pypsa.network.buses_t.v_mag_pu.copy()

        # psse_cols = set(map(str, psse_bus.columns))
        # pypsa_cols = set(map(str, pypsa_bus.columns))
        # common_keys = sorted(psse_cols & pypsa_cols, key=lambda x: int(x))

        # if bus_num is not None:
        #     if str(bus_num) not in common_keys:
        #         print(f"[WARN] Bus {bus_num} not found in both datasets.")
        #         return
        #     common_keys = [str(bus_num)]

        # if not common_keys:
        #     print("[WARN] No common bus numbers between PSS®E and PyPSA.")
        #     return

        # create_fig = ax is None
        # if create_fig:
        #     fig, ax = plt.subplots(figsize=(14, 6))

        # colors = plt.cm.tab10.colors
        # handles = []

        # for i, key in enumerate(common_keys):
        #     color_psse = "blue" if bus_num is not None else colors[i % len(colors)]
        #     color_pypsa = "red" if bus_num is not None else colors[i % len(colors)]

        #     psse_line, = ax.plot(
        #         psse_bus.index, psse_bus[int(key)],
        #         linestyle='-', marker='o', color=color_psse, alpha=1.0,
        #         linewidth=1.5, markersize=4,
        #     )

        #     ax.plot(
        #         pypsa_bus.index, pypsa_bus[key],
        #         linestyle='--', marker='^', color=color_pypsa, alpha=1.0,
        #         linewidth=1.5, markersize=4,
        #     )

        #     if bus_num is not None:
        #         handles.append((psse_line, f"Bus {key} (PSS®E)"))
        #     else:
        #         handles.append((psse_line, f"Bus {key}"))

        # if show_title:
        #     ax.set_title("Bus Voltage Magnitude Comparison — PSS®E ●  vs  PyPSA ▲")
        # ax.set_xlabel("Time")
        # ax.set_ylabel("Voltage [pu]")
        # ax.grid(True, linestyle="--", alpha=0.6)

        # if show_legend:
        #     legend_handles = [h for h, _ in handles]
        #     legend_labels = [l for _, l in handles]
        #     ax.legend(legend_handles, legend_labels, title="Bus", ncol=10 if len(handles) > 10 else 1,
        #             loc="upper center", bbox_to_anchor=(0.5, -0.05))

        # if create_fig:
        #     plt.tight_layout(rect=[0, 0, 1, 0.95])
        #     plt.show()