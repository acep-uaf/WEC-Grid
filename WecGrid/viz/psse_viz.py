"""
PSSe visualizations module, 
"""
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


# Parameterizing constants at the class level
_COLOR_MAP = {1: "grey", 2: "lightgreen", 3: "red", 4: "lightblue"}
_LABEL_MAP = {1: "PQ Bus", 2: "PV Bus", 3: "Swing Bus", 4: "WEC Bus"}
_THRESHOLD = 50


class PSSEVisualizer:
    def __init__(self, psse_obj):
        self.psse_obj = psse_obj  # passing the psse object to the visualizer, this is the parent object

    def plot_bus(self, bus_num, time, arg_1, arg_2):
        """
        Description: This function plots the activate and reactive power for a given bus
        input:
            bus_num: the bus number we wanna viz (Int)
            time: a list with start and end time (list of Ints)
        output:
            matplotlib chart
        """
        ylabel = ""

        # Enhancements for better visualization
        sns.set_style("whitegrid")
        plt.rcParams["font.size"] = 12

        fig, (ax1, ax2) = plt.subplots(2, figsize=(10, 6))
        fig.suptitle(f"Bus {bus_num} Data Visualization", fontsize=16, y=1.05)

        bus_df = self.psse_obj.bus_history(bus_num)
        bus_df = bus_df.loc[(bus_df["time"] >= time[0]) & (bus_df["time"] <= time[1])]

        ax1.plot(
            bus_df.time,
            bus_df[arg_1],
            marker="o",
            markersize=4,
            markerfacecolor="green",
            color="green",
            linestyle="-",
            lw=2,
        )
        ax2.plot(
            bus_df.time,
            bus_df[arg_2],
            marker="o",
            markersize=4,
            markerfacecolor="green",
            color="green",
            linestyle="-",
            lw=2,
        )

        if arg_1 == "P":
            ylabel = " pu"
        else:
            ylabel = " pu" # todo fix this later

        ax1.set(xlabel="", ylabel=f"{arg_1} - {ylabel}")
        ax2.set(xlabel="Time (seconds)", ylabel=f"{arg_2} - {ylabel}")

        ax1.grid(True, which="both", linestyle="--", linewidth=0.5)
        ax2.grid(True, which="both", linestyle="--", linewidth=0.5)

        plt.tight_layout()
        plt.show()
        return [bus_df[arg_1], bus_df[arg_2]]

    def _setup_cyto_graph(self, dataframe=None):
        """Setup the Cytoscape graph with nodes and edges."""
        # if dataframe is None:
        #     dataframe = self.psse_obj.dataframe

        dataframe = self.psse_obj.dataframe

        dataframe[dataframe.select_dtypes(include=["number"]).columns] = (
            dataframe.select_dtypes(include=["number"])
            .fillna(0)
            .clip(-1.0e100, 1.0e100)
        )

        cyto_graph = ipycytoscape.CytoscapeWidget()
        cyto_graph.max_zoom, cyto_graph.min_zoom = 1.1, 0.5

        nx_graph = nx.Graph()

        # Add nodes
        for _, row in dataframe.iterrows():
            node_data = {
                "id": str(row["BUS_ID"]),
                "label": str(row["BUS_ID"]),
                "type": row["Type"],
                "classes": _COLOR_MAP[row["Type"]],
                "P": row["P"],
                "Q": row["Q"],
                "angle": row["ANGLE"],
            }
            cyto_graph.graph.add_node(ipycytoscape.Node(data=node_data))
            nx_graph.add_node(str(row["BUS_ID"]), **node_data)

        # Fetch the flow data
        flow_data = self.psse_obj.flow_data

        # Add edges using the fetched flow data
        try:
            # Get the specific flow data for the current time (-1 here)
            time_flow_data = self.psse_obj.flow_data.get(-1, {})

            # Iterate over the inner dictionary
            for (source, target), p_flow in time_flow_data.items():
                arrow_color = "green" if p_flow >= 0 else "red"
                edge_data = {
                    "source": source if p_flow >= 0 else target,
                    "target": target if p_flow >= 0 else source,
                    "arrow_color": arrow_color,
                }
                cyto_graph.graph.add_edge(ipycytoscape.Edge(data=edge_data))
                nx_graph.add_edge(edge_data["source"], edge_data["target"])
        except Exception as e:
            print(f"Error adding edges: {e}")

        pos = nx.circular_layout(nx_graph)

        # Add nodes to the Cytoscape graph using the computed positions
        for node, position in pos.items():
            node_data = nx_graph.nodes[node]
            node_data["position"] = {"x": position[0], "y": position[1]}
            cyto_graph.graph.add_node(ipycytoscape.Node(data=node_data))

        return cyto_graph, nx_graph

    def _setup_styles(self, cyto_graph):
        """Define and set the styles for the Cytoscape graph."""
        cyto_styles = [
            {
                "selector": "node",
                "css": {
                    "background-color": "data(classes)",
                    "label": "data(label)",
                    "text-wrap": "wrap",
                    "text-valign": "center",
                    "text-halign": "center",
                    "font-size": "16px",
                    "color": "white",
                    "text-outline-color": "black",
                    "text-outline-width": "1px",
                    "width": "50px",
                    "height": "20px",
                    "border-color": "black",
                    "border-width": "2px",
                    "shape": "square",
                },
            },
            {"selector": "node.hide", "style": {"display": "none"}},
            {
                "selector": "edge",
                "style": {
                    "width": 4,
                    "line-color": "black",
                    "target-arrow-shape": "triangle",
                    "target-arrow-color": "data(arrow_color)",
                    "arrow-scale": 1.5,
                    "curve-style": "bezier",
                    "target-arrow-direction": "none",
                },
            },
        ]

        cyto_graph.set_style(cyto_styles)

    def _handle_node_click(self, event, info_html, time_slider):
        """Handle the node click event and update the information box."""
        self.selected_bus_id = int(
            event["data"]["id"]
        )  # Store the selected bus_id for later use

        # Update the information box
        info_html.value = self._update_info_box(self.selected_bus_id, time_slider.value)

    def _update_info_box(self, node_id, t):
        """Update the information box based on the clicked node's data."""

        # Get the dataframe for the specified time from psse_history
        dataframe = self.psse_obj.history.get(t, None)
        if dataframe is None:
            return f"No data available for time: {t}s"

        row = dataframe[dataframe["BUS_ID"] == node_id].iloc[0]

        # Calculate P and Q using the provided columns
        P = row["P"]
        Q = row["Q"]

        # Update the HTML widget with the relevant details using string formatting for 3 decimal places
        info_content = (
            f"<strong>Bus Details:</strong><br>"
            f"<strong>Bus ID:</strong> {node_id}<br>"
            f"<strong>P:</strong> {P:.3f}<br>"  # Format to 3 decimal places
            f"<strong>Q:</strong> {Q:.3f}<br>"  # Format to 3 decimal places
            f"<strong>Angle:</strong> {row['ANGLE']:.3f}<br>"
            f"<strong>Magnitude:</strong> {row['M_Mag']:.3f}<br>"
            f"<strong>Time:</strong> {t}s<br>"  # Display the time
        )
        return info_content

    def _layout_widgets(self, cyto_graph, time_slider, info_html):
        """Arrange and layout widgets for the final visualization."""

        # Dropdown for Bus Types
        bus_type_dropdown = Dropdown(
            options=[("All", 0)] + [(_LABEL_MAP[i], i) for i in range(1, 5)],
            value=0,
            description="Bus Type:",
        )

        # Legend
        color_html = "".join(
            [
                f'<div style="background: {_COLOR_MAP[bus_type]}; width: 15px; height: 15px; display: inline-block; margin: 2px;"></div>{_LABEL_MAP[bus_type]}<br>'
                for bus_type in _COLOR_MAP
            ]
        )
        legend = widgets.HTML(
            f"<div style='border: solid; padding: 5px; height: 150px; width: 120px; font-size: 10pt;'><strong>Legend:</strong><br>{color_html}</div>"
        )

        # Set the dimensions of the cyto_graph
        cyto_graph.layout.width = "660px"
        cyto_graph.layout.height = "500px"

        # Adjust the dimensions of the legend and info boxes
        legend.layout.width = "138px"
        legend.layout.height = "250px"
        info_html.layout.width = "138px"
        info_html.layout.height = "250px"

        # Define the HBox layout
        hbox_layout = widgets.Layout(width="800px", height="500px")

        # Define the VBox layout
        vbox_layout = widgets.Layout(width="800px", height="540px")

        # Apply the layouts
        legend_info_layout = VBox([legend, info_html])
        final_layout = VBox(
            [
                bus_type_dropdown,
                time_slider,
                HBox([cyto_graph, legend_info_layout], layout=hbox_layout),
            ],
            layout=vbox_layout,
        )

        return final_layout

    def viz(self, dataframe=None):
        # Setup Cytoscape graph with nodes and edges
        cyto_graph, nx_graph = self._setup_cyto_graph(self.psse_obj.dataframe)

        # Apply styles to the graph
        self._setup_styles(cyto_graph)

        # Bind the node click event
        # Bind the node click event
        cyto_graph.on(
            "node",
            "click",
            lambda event: self._handle_node_click(event, info_html, time_slider),
        )

        # Create a time slider
        valid_times = sorted(self.psse_obj.history.keys())
        time_slider = widgets.SelectionSlider(
            options=valid_times,
            description="Time:",
            disabled=False,
            continuous_update=False,
            orientation="horizontal",
            readout=True,
        )

        def update_flow(change):
            t = change["new"]
            flow_data = self.psse_obj.flow_data.get(t, {})

            for edge in cyto_graph.graph.edges:
                source = edge.data["source"]
                target = edge.data["target"]

                # Fetch the p_flow value for this edge from the flow_data
                p_flow = flow_data.get((source, target), 0)  # Default to 0 if not found

                arrow_color = "green" if p_flow >= 0 else "red"
                edge.data["arrow_color"] = arrow_color

                # Assuming you still want to use the thickness to represent magnitude:
                edge.classes = "thick" if abs(p_flow) > _THRESHOLD else "thin"

        time_slider.observe(update_flow, names="value")

        # Information box
        info_html = widgets.HTML(
            value="Click a node for details",
            layout=widgets.Layout(
                height="250px", width="138px", border="solid", padding="5px"
            ),
        )

        # Arrange and layout the widgets
        layout = self._layout_widgets(cyto_graph, time_slider, info_html)

        return layout
    

