"""
PSSe visualizations module, 
"""
import os
import sys
import math

import bqplot as bq
import ipycytoscape
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.patches import Rectangle, Circle


from matplotlib.patches import Rectangle, Circle, FancyArrow
from matplotlib.lines import Line2D

import pandas as pd
import seaborn as sns
from ipywidgets import Dropdown, HTML, HBox, Layout, SelectionSlider, VBox, widgets


class PSSEVisualizer:
    def __init__(self, engine):
        self.engine = engine
    
    def plot_all(self, bus_num=None, gen_name=None):
        fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
        self.plot_bus_power(bus_num=bus_num, ax=axes[0], show_title=True, show_legend=False)
        self.plot_bus_vmag(bus_num=bus_num, ax=axes[1], show_title=True, show_legend=False)
        self.plot_generator_power(gen_name=gen_name, ax=axes[2], show_title=True, show_legend=False)

        handles, labels = [], []
        for ax in axes:
            h, l = ax.get_legend_handles_labels()
            handles.extend(h)
            labels.extend(l)

        unique = dict(zip(labels, handles))
        fig.suptitle("PSS®E: Simulation Results", fontsize=16)
        fig.legend(unique.values(), unique.keys(), ncol=8, loc='upper center', bbox_to_anchor=(0.5, -0.05))
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        plt.show()
        
    def plot_bus_power(self, bus_num=None, ax=None, show_title=True, show_legend=True):
        data = []
        for snap in self.engine.snapshot_history:
            gen_df = snap.generators
            grouped = gen_df.groupby("BUS_ID")["PGEN_MW"].sum()
            grouped.name = snap.snapshot
            data.append(grouped)

        df = pd.DataFrame(data)
        df.index.name = "Time"
        df = df.sort_index()

        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        if bus_num is not None:
            if bus_num in df.columns:
                ax.plot(df.index, df[bus_num], label=f"Bus {bus_num}", color='C0', linestyle=':', marker='o', linewidth=1.0, markersize=4)
            else:
                print(f"[plot_bus_power] Warning: Bus {bus_num} not found in data.")
                return
        else:
            for bus_id in df.columns:
                ax.plot(df.index, df[bus_id], label=f"Bus {bus_id}",linestyle=':', marker='o', linewidth=1.0, markersize=4)

        if show_title:
            ax.set_title(f"PSS®E: Active Power Over Time" + (f" — Bus {bus_num}" if bus_num else " (All Buses)"))
        ax.set_xlabel("Time")
        ax.set_ylabel("PGEN (MW)")
        ax.grid(True, linestyle="--", alpha=0.6)

        if show_legend:
            ax.legend(title="Bus ID", ncol=8, loc='upper center', bbox_to_anchor=(0.5, -0.05))

        if create_fig:
            plt.tight_layout()
            plt.show()

    def plot_bus_vmag(self, bus_num=None, ax=None, show_title=True, show_legend=True):
        data = []
        for snap in self.engine.snapshot_history:
            bus_df = snap.buses
            if bus_df is not None and not bus_df.empty:
                vmag_series = bus_df.set_index("BUS_ID")["V_PU"]
                vmag_series.name = snap.snapshot
                data.append(vmag_series)

        if not data:
            print("[plot_bus_vmag] No valid snapshot data found.")
            return

        df = pd.DataFrame(data)
        df.index.name = "Time"
        df = df.sort_index()

        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))

        if bus_num is not None:
            bus_id = int(bus_num)
            if bus_id in df.columns:
                ax.plot(df.index, df[bus_id], label=f"Bus {bus_id}", color="C1",  linestyle=':', marker='o', linewidth=1.0, markersize=4)
            else:
                print(f"[plot_bus_vmag] Warning: Bus {bus_id} not found in snapshot data.")
                return
        else:
            for col in df.columns:
                ax.plot(df.index, df[col], label=f"Bus {col}", linestyle=':', marker='o', linewidth=1.0, markersize=4)

        if show_title:
            ax.set_title(f"PSS®E: Bus Voltage Magnitude Over Time" + (f" — Bus {bus_num}" if bus_num else " (All Buses)"))
        ax.set_xlabel("Time")
        ax.set_ylabel("Voltage Magnitude [pu]")
        ax.axhline(1.0, color='gray', linestyle='--', linewidth=1, label="Nominal (1.0 pu)")
        ax.set_ylim(0.9, 1.1)
        ax.grid(True, linestyle="--", alpha=0.6)

        if show_legend:
            ax.legend(title="Bus ID", ncol=8, loc='upper center', bbox_to_anchor=(0.5, -0.05))

        if create_fig:
            plt.tight_layout()
            plt.show()
            
    def plot_generator_power(self, gen_name=None, ax=None, show_title=True, show_legend=True):
        self.plot_generator_parameter(gen_name, "p", ax=ax, show_title=show_title, show_legend=show_legend)

    def plot_generator_reactive_power(self, gen_key=None):
        self.plot_generator_parameter(gen_key, "QGEN_MVAR")
                
    def plot_generator_parameter(self, gen_name=None, parameter=None, ax=None, show_title=True, show_legend=True):
        
        
        
        if parameter is None:
            raise ValueError("Parameter must be specified.")

        if parameter == 'p':
            df = self.engine.generator_dataframe_t.p.copy()
            ylabel = "Pgen (MW)"
        elif parameter == 'q':
            df = self.engine.generator_dataframe_t.q.copy()
            ylabel = "Qgen (MVar)"
        else:
            raise ValueError("Parameter must be 'p' or 'q'")
        
        
        gen_df = self.engine.generator_dataframe
        create_fig = ax is None
        if create_fig:
            fig, ax = plt.subplots(figsize=(14, 6))
        
        if gen_name is not None:
            if gen_name not in df.columns:
                print(f"Warning: generator {gen_name} not found.")
                return
            to_plot = [gen_name]
            legend_title = "Generator"
            title = f"PSS®E: Generator {gen_name} {'Active' if parameter == 'p' else 'Reactive'} Power Over Time"
        else:
            to_plot = df.columns.tolist()
            legend_title = "Generator (Bus)"
            title = f"PSS®E: Generator {'Active' if parameter == 'p' else 'Reactive'} Power Over Time (All Generators)"
        
        for col in to_plot:
            bus = gen_df.at[col, "bus"] if col in gen_df.index else "?"
            label = f"{col} (Bus {bus})"
            ax.plot(df.index, df[col], label=label, linestyle=':', marker='o', linewidth=1.0, markersize=4)

        if show_title:
            ax.set_title(title)
        ax.set_xlabel("Time")
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle="--", alpha=0.6)

        if show_legend:
            ax.legend(title=legend_title, bbox_to_anchor=(1.05, 1), loc="upper left")

        if create_fig:
            plt.tight_layout()
            plt.show()
        
        
        
        
        # if parameter is None:
        #     raise ValueError("Parameter must be specified.")

        # data, times = [], []
        # for snap in self.engine.snapshot_history:
        #     gen_df = snap.generators
        #     if gen_df is None or gen_df.empty:
        #         continue
        #     gen_df = gen_df.copy()
        #     gen_df["GEN_KEY"] = list(zip(gen_df["BUS_ID"], gen_df["GEN_ID"]))
        #     s = gen_df.set_index("GEN_KEY")[parameter]
        #     data.append(s.to_dict())
        #     times.append(pd.to_datetime(snap.snapshot))

        # df = pd.DataFrame(data, index=pd.DatetimeIndex(times))
        # df.index.name = "Time"
        # df.sort_index(inplace=True)

        # create_fig = ax is None
        # if create_fig:
        #     fig, ax = plt.subplots(figsize=(14, 6))

        # if gen_key:
        #     if gen_key in df.columns:
        #         label = f"{gen_key[1]} (Bus {gen_key[0]})"
        #         ax.plot(df.index, df[gen_key], label=label, linestyle=':', marker='o', linewidth=1.0, markersize=4)
        #     else:
        #         print(f"[WARN] Generator {gen_key} not found.")
        #         return
        #     legend_title = "Generator"
        # else:
        #     legend_title = "Generator (Bus)"
        #     for col in df.columns:
        #         bus_id, gen_id = col
        #         label = f"{gen_id} (Bus {bus_id})"
        #         ax.plot(df.index, df[col], label=label, linestyle=':', marker='o', linewidth=1.0, markersize=4)

        # if parameter == "PGEN_MW":
        #     title = "PSS®E: Generator Active Power Over Time"
        #     ylabel = "PGEN (MW)"
        # elif parameter == "QGEN_MVAR":
        #     title = "PSS®E: Generator Reactive Power Over Time"
        #     ylabel = "QGEN (MVar)"
        # else:
        #     title = f"PSS®E: {parameter} Over Time"
        #     ylabel = parameter

        # if show_title:
        #     ax.set_title(title)
        # ax.set_xlabel("Time")
        # ax.set_ylabel(ylabel)
        # ax.grid(True, linestyle="--", alpha=0.6)

        # if show_legend:
        #     ax.legend(title=legend_title, bbox_to_anchor=(1.05, 1), loc="upper left")

        # if create_fig:
        #     plt.tight_layout()
        #     plt.show()

    def plot_branch_percent(self, branch_name=None, threshold=80.0):
        """
        Plot only those PSS®E branches whose percent‐loading exceeds `threshold`
        at any time in the recorded snapshots, unless a specific branch_name
        is given (then only that branch is shown).

        Parameters
        ----------
        branch_name : str, optional
            The PSSE branch NAME to plot. If None, all branches whose
            loading exceeds the threshold will be plotted.

        threshold : float, default=80.0
            The percent‐loading cutoff for auto‐filtering branches.
        """
        import pandas as pd
        import matplotlib.pyplot as plt

        records = []
        times   = []

        for snap in self.engine.snapshot_history:
            br = snap.branches
            if br is None or br.empty:
                continue
            bdf = br.copy().set_index("NAME")
            bdf = bdf[["PCT_RATE"]].apply(pd.to_numeric, errors="coerce")
            records.append(bdf["PCT_RATE"].to_dict())
            times.append(pd.to_datetime(snap.snapshot))

        if not records:
            print("[WARN] No branch data found in any snapshots.")
            return

        df = pd.DataFrame(records, index=pd.DatetimeIndex(times))
        df.index.name = "Time"
        df.sort_index(inplace=True)

        # 5) pick which branches to plot
        if branch_name:
            if branch_name not in df.columns:
                print(f"[WARN] Branch {branch_name!r} not found.")
                return
            to_plot = [branch_name]
            title   = f"PSS®E: Branch {branch_name} Loading (%)"
        else:
            hot     = df.max(axis=0) > threshold
            to_plot = list(hot[hot].index)
            if not to_plot:
                print(f"[INFO] No branches exceed {threshold}% loading.")
                return
            title   = f"PSS®E: Branches > {threshold}% Loading"

        # 6) plotting
        plt.figure(figsize=(14, 6))
        for br in to_plot:
            plt.plot(df.index, df[br], lw=2, label=br)

        # Draw the threshold line if plotting multiple
        if not branch_name:
            plt.axhline(threshold, color="k", ls="--", alpha=0.6)

        plt.title(title)
        plt.xlabel("Time")
        plt.ylabel("Loading (%)")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.legend(title="Branch NAME", bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.tight_layout()
        plt.ylim(bottom=threshold)
        plt.show()

    def draw_transformer_arrow(self, ax, path):
        """
        Draws a transformer arrow aligned to the second segment in the path.
        Arrow length is capped to avoid overlap with buses.
        """
        if len(path) < 4:
            return  # Not enough path to draw cleanly

        # Use the second segment (3rd → 4th point)
        x1, y1 = path[2]
        x2, y2 = path[3]

        # Full vector
        dx_full = x2 - x1
        dy_full = y2 - y1

        # Compute segment length
        segment_len = np.hypot(dx_full, dy_full)

        # Limit arrow length to avoid visual overlap
        max_arrow_len = 0.05
        scale = min(max_arrow_len / segment_len, 1.0)

        # Compute scaled vector
        dx = dx_full * scale
        dy = dy_full * scale

        # Start the arrow slightly before the final point to make it visible
        arrow_start_x = x2 - dx
        arrow_start_y = y2 - dy

        ax.add_patch(
            FancyArrow(
                arrow_start_x, arrow_start_y, dx, dy,
                width=0.004, head_width=0.015, head_length=0.02,
                color='blue', length_includes_head=True
            )
        )
                
    def determine_connection_sides(self, from_bus, to_bus, from_pos, to_pos, bus_connections, used_connections):
        """
        Determines the best connection points for a given bus pair while avoiding overlapping connections.
        - Uses x and y positions to determine if the connection is horizontal (left/right) or vertical (top/bottom).
        - Selects an available connection within that side (inner, middle, outer) to reduce overlap.
        """

        y_tuner = 0.1  # Controls how strict we are about vertical vs. horizontal
        x_tuner = 0.48  # Controls how strict we are about left/right priority

        x1, y1 = from_pos
        x2, y2 = to_pos

        # --- Step 1: Determine primary connection direction ---
        if abs(x1 - x2) > abs(y1 - y2):  
            primary_connection = "horizontal"  # Mostly horizontal movement
        else:  
            primary_connection = "vertical"  # Mostly vertical movement

        # Adjust with tuners
        if abs(y1 - y2) < y_tuner:
            primary_connection = "horizontal"
        elif abs(x1 - x2) < x_tuner:
            primary_connection = "vertical"

        # --- Step 2: Determine connection points ---
        if primary_connection == "horizontal":
            if x1 < x2:  # Moving left → right
                from_side = "right"
                to_side = "left"
            else:  # Moving right → left
                from_side = "left"
                to_side = "right"
        else:  # Vertical Connection
            if y1 > y2:  # Moving top → bottom
                from_side = "bottom"
                to_side = "top"
            else:  # Moving bottom → top
                from_side = "top"
                to_side = "bottom"

        # **Select the best available connection point within the side**
        for priority in ["middle", "inner", "outer"]:  # Prioritize middle, then fallback
            from_point_key = f"{from_side}_{priority}"
            to_point_key = f"{to_side}_{priority}"

            if from_point_key not in used_connections[from_bus] and to_point_key not in used_connections[to_bus]:
                used_connections[from_bus].add(from_point_key)
                used_connections[to_bus].add(to_point_key)
                return bus_connections[from_bus][from_point_key], bus_connections[to_bus][to_point_key], f"{from_side}-{to_side}"

        # Fallback (shouldn't reach here unless something is wrong)
        return bus_connections[from_bus]["right_middle"], bus_connections[to_bus]["left_middle"], "fallback"

    def route_line(self, p1, p2, connection_type):
        """
        Creates an L-shaped or Z-shaped path between two points using right-angle bends.
        - Left/Right: Midpoint in X first, then Y.
        - Top/Bottom: Midpoint in Y first, then X.
        """
        x1, y1 = p1
        x2, y2 = p2

        if x1 == x2 or y1 == y2:
            return [p1, p2]  # Direct connection

        if connection_type in ["left-right", "right-left"]:
            mid_x = (x1 + x2) / 2  # First bend in X direction
            return [p1, (mid_x, y1), (mid_x, y2), p2]  # Two bends: X first, then Y

        elif connection_type in ["top-bottom", "bottom-top"]:
            mid_y = (y1 + y2) / 2  # First bend in Y direction
            return [p1, (x1, mid_y), (x2, mid_y), p2]  # Two bends: Y first, then X

        return [p1, p2]  # Default (fallback)

    def get_bus_color(self, bus_type):
        """ Returns the color for a given bus type. """
        color_map = {
            1: "#A9A9A9",  # Gray
            2: "#32CD32",  # Green
            3: "#FF4500",  # Red
            4: "#1E90FF",  # Blue
        }
        return color_map.get(bus_type, "#D3D3D3")  # Default light gray if undefined

    def sld(self):
        """
        Generates a structured single-line diagram with correct bus connection logic and predictable bends.
        Includes:
        - Loads (downward arrows)
        - Generators (circles above bus)
        """

        # --- Step 1: Extract Bus, Load, and Generator Data ---
        ierr, bus_numbers = self.engine.psspy.abusint(-1, 1, "NUMBER")
        #ierr, bus_types = self.engine.psspy.abusint(-1, 1, "TYPE")
        bus_type_df = self.engine.bus_dataframe[["BUS_ID", "TYPE"]]
        
        ierr, (from_buses, to_buses) = self.engine.psspy.abrnint(sid=-1, flag=3, string=["FROMNUMBER", "TONUMBER"])
        ierr, load_buses = self.engine.psspy.aloadint(-1, 1, "NUMBER")  # Correct API for loads
        ierr, gen_buses = self.engine.psspy.amachint(-1, 4, "NUMBER")  # Correct API for generators
        ierr, (xfmr_from_buses, xfmr_to_buses) = self.engine.psspy.atrnint(
            sid=-1, owner=1, ties=3, flag=2, entry=1, string=["FROMNUMBER", "TONUMBER"]
        )
        xfmr_pairs = set(zip(xfmr_from_buses, xfmr_to_buses))

        # Convert lists to sets for quick lookup
        load_buses = set(load_buses[0]) if load_buses[0] else set()
        gen_buses = set(gen_buses[0]) if gen_buses[0] else set()

        # --- Step 2: Build Graph Representation ---
        G = nx.Graph()
        for bus in bus_numbers[0]:
            G.add_node(bus)
        for from_bus, to_bus in zip(from_buses, to_buses):
            G.add_edge(from_bus, to_bus)

        # --- Step 3: Compute Layout ---
        pos = nx.kamada_kawai_layout(G)

        # Normalize positions for even spacing
        pos_values = np.array(list(pos.values()))
        x_vals, y_vals = pos_values[:, 0], pos_values[:, 1]
        x_min, x_max = np.min(x_vals), np.max(x_vals)
        y_min, y_max = np.min(y_vals), np.max(y_vals)
        for node in pos:
            pos[node] = (
                2 * (pos[node][0] - x_min) / (x_max - x_min) - 1,
                1.5 * (pos[node][1] - y_min) / (y_max - y_min) - 0.5
            )

        # --- Step 4: Create Visualization ---
        fig, ax = plt.subplots(figsize=(14, 10))
        node_width, node_height = 0.12, 0.04

        # Store predefined connection points for each bus
        bus_connections = {}
        used_connections = {bus: set() for bus in bus_numbers[0]}  # Track used connections
        for bus in bus_numbers[0]:
            x, y = pos[bus]
            bus_connections[bus] = {
                # Left side (3 points)
                "left_inner": (x - node_width / 2, y - node_height / 3),
                "left_middle": (x - node_width / 2, y),
                "left_outer": (x - node_width / 2, y + node_height / 3),

                # Right side (3 points)
                "right_inner": (x + node_width / 2, y - node_height / 3),
                "right_middle": (x + node_width / 2, y),
                "right_outer": (x + node_width / 2, y + node_height / 3),

                # Top side (3 points)
                "top_inner": (x - node_width / 3, y + node_height / 2),
                "top_middle": (x, y + node_height / 2),
                "top_outer": (x + node_width / 3, y + node_height / 2),

                # Bottom side (3 points)
                "bottom_inner": (x - node_width / 3, y - node_height / 2),
                "bottom_middle": (x, y - node_height / 2),
                "bottom_outer": (x + node_width / 3, y - node_height / 2),
            }

        # Draw right-angle connections based on simplified logic
        for from_bus, to_bus in zip(from_buses, to_buses):
            from_pos = pos[from_bus]
            to_pos = pos[to_bus]

            try:
                p1, p2, ctype = self.determine_connection_sides(from_bus, to_bus, from_pos, to_pos, bus_connections, used_connections)
            except KeyError:
                continue

            path = self.route_line(p1, p2, ctype)

            # Draw path segments
            for i in range(len(path) - 1):
                ax.plot([path[i][0], path[i+1][0]], [path[i][1], path[i+1][1]], 'k', lw=1.5, linestyle="dashed")
            
            if (from_bus, to_bus) in xfmr_pairs or (to_bus, from_bus) in xfmr_pairs:
                self.draw_transformer_arrow(ax, path)  # Attach arrow to 2nd segment of the path
                #draw_transformer_marker(ax, path)  # Attach diamond marker to midpoint of the path

                
        # Draw bus rectangles
        for bus in bus_numbers[0]:
            x, y = pos[bus]
            #temp = bus_numbers[0].index(bus)
            
            bus_type = bus_type_df.loc[bus_type_df["BUS_ID"] == bus, "TYPE"].values[0]
            bus_color = self.get_bus_color(bus_type)
            
            #bus_color = self.get_bus_color()
            
            rect = Rectangle((x - node_width / 2, y - node_height / 2), node_width, node_height,
                            linewidth=1.5, edgecolor='black', facecolor=bus_color)
            ax.add_patch(rect)
            ax.text(x, y, str(bus), fontsize=8, fontweight="bold", ha='center', va='center')

            # Draw loads (right-offset downward arrows)
            if bus in load_buses:
                ax.arrow(x + node_width / 2 - 0.02, y + 0.02, 0, 0.05, head_width=0.02, head_length=0.02, fc='black', ec='black')

            # Draw generators (left-offset circles above bus)
            if bus in gen_buses:
                gen_x = x - node_width / 2 + 0.02  # Move generator left
                gen_y = y + node_height / 2 + 0.05
                gen_size = 0.02
                ax.plot([gen_x, gen_x], [y + node_height / 2 + 0.005, gen_y - gen_size ], color='black', lw=2)
                ax.add_patch(Circle((gen_x, gen_y), gen_size, color='none', ec='black', lw=1.5))
        
    


        ax.set_aspect('equal', adjustable='datalim')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)
        ax.set_title(f"Generated Single-Line Diagram of {self.engine.case_file}", fontsize=14)
        # Extract the final file name without path and extension
        case_file_name = os.path.splitext(os.path.basename(self.engine.case_file))[0]
        ax.set_title(f"Generated Single-Line Diagram of {case_file_name}", fontsize=14)
        # Define legend elements
        legend_elements = [
            Line2D([0], [0], marker='o', color='black', markersize=8, label="Generator", markerfacecolor='none', markeredgecolor='black', lw=0),
            Line2D([0], [0], marker=('^'), color='blue', markersize=10, label="Transformer", markerfacecolor='blue', lw=0),
            Line2D([0], [0], marker='^', color='black', markersize=10, label="Load", markerfacecolor='black', lw=0),
            Line2D([0], [0], marker='s', color='red', markersize=10, label="SwingBus", markerfacecolor='red', lw=0),
            Line2D([0], [0], marker='s', color='blue', markersize=10, label="WEC Bus", markerfacecolor='blue', lw=0),
            Line2D([0], [0], marker='s', color='green', markersize=10, label="PV Bus", markerfacecolor='green', lw=0),
            Line2D([0], [0], marker='s', color='gray', markersize=10, label="PQ Bus", markerfacecolor='gray', lw=0),
        ]

        # Add the legend at the bottom-right
        ax.legend(handles=legend_elements, loc="upper left", fontsize=10, frameon=True, edgecolor='black', title="Legend")
        plt.show()