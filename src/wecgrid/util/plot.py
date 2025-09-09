"""Plotting utilities for WEC-Grid results."""

# Standard library
from typing import Any, List, Optional, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..modelers.power_system.base import GridState
    from ..util.database import WECGridDB

# Third-party
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle


class WECGridPlot:
    """Plot time series and diagrams from engine or stored GridState."""

    def __init__(self, engine: Any = None):
        """Initialize with an engine or use standalone GridState objects.

        Args:
            engine: WEC-Grid engine. If None, add GridState via ``add_grid``.
        """
        self.engine = engine
        self._standalone_grids = {}  # Store GridState objects for standalone usage

    def add_grid(self, software: str, grid_state: 'GridState'):
        """Register a GridState for standalone plotting.

        Args:
            software: Backend identifier ("psse", "pypsa").
            grid_state: GridState with snapshots and time series.
        """
        self._standalone_grids[software] = grid_state

    @classmethod
    def from_database(cls, database: 'WECGridDB', grid_sim_id: int, software: str = None) -> 'WECGridPlot':
        """Construct a plotter from stored simulation data.

        Args:
            database: Database interface.
            grid_sim_id: Simulation ID to load.
            software: Optional backend hint ("psse" or "pypsa").

        Returns:
            WECGridPlot instance with loaded GridState.
        """
        plotter = cls(engine=None)
        grid_state = database.pull_sim(grid_sim_id, software)
        plotter.add_grid(grid_state.software, grid_state)
        return plotter

    def _get_grid_obj(self, software: str):
        """Resolve a GridState from engine or standalone store.

        Args:
            software: Backend identifier.

        Returns:
            GridState or ``None`` if unavailable.
        """
        # First try standalone grids
        if software in self._standalone_grids:
            return self._standalone_grids[software]

        # Then try engine
        if self.engine and hasattr(self.engine, software):
            modeler = getattr(self.engine, software)
            if modeler and hasattr(modeler, "grid"):
                return modeler.grid

        return None

    def _plot_time_series(
        self,
        software: str,
        component_type: str,
        parameter: str,
        components: Optional[List[str]] = None,
        title: str = "",
        ax: Optional[plt.Axes] = None,
        ylabel: str = "",
        xlabel: str = "Time",
    ):
        """Internal helper to plot time-series data.

        Args:
            software: Backend identifier ("psse", "pypsa").
            component_type: Component group ("gen", "bus", "load", "line").
            parameter: Time-series variable to plot (must exist in ``*_t``).
            components: Optional subset of component names/IDs.
            title: Optional title override.
            ax: Optional Axes to draw on; creates new if None.
            ylabel: Optional y-axis label; defaults to ``parameter``.
            xlabel: X-axis label.

        Returns:
            (Figure, Axes) or (None, None) if data unavailable.
        """
        grid_obj = self._get_grid_obj(software)

        if grid_obj is None:
            print(
                f"Error: No grid data found for software '{software}'. "
                f"Use add_grid() for standalone GridState objects or ensure "
                f"the engine has '{software}' loaded."
            )
            return None, None
        component_data_t = getattr(grid_obj, f"{component_type}_t", None)

        if component_data_t is None or parameter not in component_data_t:
            print(
                f"Error: Parameter '{parameter}' not found for '{component_type}' in '{software}'."
            )
            return None, None

        data = component_data_t[parameter]

        if components:
            # Ensure components is a list
            if isinstance(components, str):
                components = [components]

            # Filter columns that exist in the dataframe
            available_components = [c for c in components if c in data.columns]
            if not available_components:
                print(
                    f"Warning: None of the specified components {components} found in data for {parameter}."
                )
                return None, None
            data = data[available_components]

        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 6))
        else:
            fig = ax.get_figure()

        data.plot(ax=ax, legend=True)
        ax.set_title(
            title
            or f"{software.upper()}: {component_type.capitalize()} {parameter.capitalize()}"
        )
        ax.set_ylabel(ylabel or parameter)
        ax.set_xlabel(xlabel)
        ax.grid(True)

        # Truncate legend if it's too long
        if len(data.columns) > 10:
            ax.legend().set_visible(False)

        return fig, ax

    def gen(
        self,
        software: str = "pypsa",
        parameter: str = "p",
        gen: Optional[List[str]] = None,
    ) -> Tuple[Any, Any]:
        """Plot a generator parameter.

        Args:
            software: The modeling software to use (``"psse"`` or ``"pypsa"``).
            parameter: Generator parameter to plot (e.g., ``"p"``, ``"q"``).
            gen: A list of generator names to plot. If ``None``, all generators are shown.

        Returns:
            (Figure, Axes).
        """
        if parameter == "p":
            title = f"{software.upper()}: Generator Active Power"
            ylabel = "Active Power [pu]"
        elif parameter == "q":
            title = f"{software.upper()}: Generator Reactive Power"
            ylabel = "Reactive Power [pu]"
        else:
            print("not a valid parameter")
            return None, None

        fig, ax = self._plot_time_series(
            software, "gen", parameter, components=gen, title=title, ylabel=ylabel
        )
        plt.show()
        return fig, ax

    def bus(
        self,
        software: str = "pypsa",
        parameter: str = "p",
        bus: Optional[List[str]] = None,
    ) -> Tuple[Any, Any]:
        """Plot a bus parameter.

        Args:
            software: The modeling software to use (``"psse"`` or ``"pypsa"``).
            parameter: Bus parameter to plot (e.g., ``"v_mag"``, ``"angle_deg"``).
            bus: A list of bus names to plot. If ``None``, all buses are shown.

        Returns:
            (Figure, Axes).
        """
        if parameter == "p":
            title = f"{software.upper()}: Bus Active Power (net)"
            ylabel = "Active Power [pu]"
        elif parameter == "q":
            title = f"{software.upper()}: Bus Reactive Power (net)"
            ylabel = "Reactive Power [pu]"
        elif parameter == "v_mag":
            title = f"{software.upper()}: Bus Voltage Magnitude"
            ylabel = "Voltage (pu)"
        elif parameter == "angle_deg":
            title = f"{software.upper()}: Bus Voltage Angle"
            ylabel = "Angle (degrees)"
        else:
            print("not a valid parameter")
            return None, None

        fig, ax = self._plot_time_series(
            software, "bus", parameter, components=bus, title=title, ylabel=ylabel
        )
        plt.show()
        return fig, ax

    def load(
        self,
        software: str = "pypsa",
        parameter: str = "p",
        load: Optional[List[str]] = None,
    ) -> Tuple[Any, Any]:
        """Plot a load parameter.

        Args:
            software: The modeling software to use (``"psse"`` or ``"pypsa"``).
            parameter: Load parameter to plot (e.g., ``"p"``, ``"q"``).
            load: A list of load names to plot. If ``None``, all loads are shown.

        Returns:
            (Figure, Axes).
        """
        if parameter == "p":
            title = f"{software.upper()}: Load Active Power"
            ylabel = "Active Power [pu]"
        elif parameter == "q":
            title = f"{software.upper()}: Load Reactive Power"
            ylabel = "Reactive Power [pu]"
        else:
            print("not a valid parameter")
            return None, None

        fig, ax = self._plot_time_series(
            software, "load", parameter, components=load, title=title, ylabel=ylabel
        )
        plt.show()
        return fig, ax

    def line(
        self,
        software: str = "pypsa",
        parameter: str = "line_pct",
        line: Optional[List[str]] = None,
    ) -> Tuple[Any, Any]:
        """Plot a line parameter.

        Args:
            software: The modeling software to use (``"psse"`` or ``"pypsa"``).
            parameter: Line parameter to plot. Defaults to ``"line_pct"``.
            line: A list of line names to plot. If ``None``, all lines are shown.

        Returns:
            (Figure, Axes).
        """
        if parameter == "line_pct":
            title = f"{software.upper()}: Line Percent Loading"
            ylabel = "Percent Loading [%]"
        else:
            print("not a valid parameter")
            return None, None

        fig, ax = self._plot_time_series(
            software, "line", parameter, components=line, title=title, ylabel=ylabel
        )
        plt.show()
        return fig, ax

    def sld(
        self, software: str = "pypsa", figsize=(14, 10), title=None, save_path=None, show: bool = False
    ) -> Tuple[Figure, Axes]:
        """Draw a single-line diagram using GridState.

        Args:
            software: Backend ("psse" or "pypsa").
            figsize: Figure size (width, height).
            title: Optional title.
            save_path: Optional file path to save image.
            show: If True, call ``plt.show()``.

        Returns:
            (Figure, Axes).
        """
        # Get the appropriate grid object
        grid_obj = self._get_grid_obj(software)

        if grid_obj is None:
            raise ValueError(
                f"No grid data found for software '{software}'. "
                f"Use add_grid() for standalone GridState objects or ensure "
                f"the engine has '{software}' loaded."
            )

        # Extract data from GridState
        bus_df = grid_obj.bus.copy()
        line_df = grid_obj.line.copy()
        gen_df = grid_obj.gen.copy()
        load_df = grid_obj.load.copy()

        if bus_df.empty:
            raise ValueError("No bus data available for SLD generation")

        print(f"SLD Data Summary:")
        print(f"  Buses: {len(bus_df)}")
        print(f"  Lines: {len(line_df)}")
        print(f"  Generators: {len(gen_df)}")
        print(f"  Loads: {len(load_df)}")

        # Check if required columns exist
        if "bus" not in bus_df.columns and bus_df.index.name != "bus":
            print(f"  ERROR: 'bus' column missing from bus DataFrame")
            print(f"  Available columns: {list(bus_df.columns)}")
            print(f"  Index name: {bus_df.index.name}")
            print(f"  Bus DataFrame head:\n{bus_df.head()}")

            # Check if bus numbers are in the index
            if bus_df.index.name == "bus" or "bus" in str(bus_df.index.name).lower():
                print("  Bus numbers found in DataFrame index, will use index values")
            else:
                raise ValueError("Bus DataFrame missing required 'bus' column or index")

        # Create network graph for layout
        G = nx.Graph()

        # Add buses as nodes - handle index vs column
        if "bus" in bus_df.columns:
            bus_numbers = bus_df["bus"]
        else:
            # Bus numbers are in the index
            bus_numbers = bus_df.index

        for bus_num in bus_numbers:
            G.add_node(bus_num)

        # Add lines as edges - handle potential column name variations
        ibus_col = "ibus" if "ibus" in line_df.columns else "from_bus"
        jbus_col = "jbus" if "jbus" in line_df.columns else "to_bus"
        status_col = "status" if "status" in line_df.columns else None

        for _, line_row in line_df.iterrows():
            if status_col is None or line_row[status_col] == 1:  # Only active lines
                if ibus_col in line_df.columns and jbus_col in line_df.columns:
                    G.add_edge(line_row[ibus_col], line_row[jbus_col])

        # Calculate layout using NetworkX
        try:
            pos = nx.kamada_kawai_layout(G)
        except:
            # Fallback to spring layout if kamada_kawai fails
            pos = nx.spring_layout(G, seed=42)

        # Normalize positions for better visualization
        if pos:
            pos_values = np.array(list(pos.values()))
            x_vals, y_vals = pos_values[:, 0], pos_values[:, 1]
            x_min, x_max = np.min(x_vals), np.max(x_vals)
            y_min, y_max = np.min(y_vals), np.max(y_vals)

            # Normalize to reasonable plotting range
            for node in pos:
                pos[node] = (
                    2 * (pos[node][0] - x_min) / (x_max - x_min) - 1,
                    1.5 * (pos[node][1] - y_min) / (y_max - y_min) - 0.5,
                )

        # Create figure
        fig, ax = plt.subplots(figsize=figsize)

        # Bus visualization parameters
        node_width, node_height = 0.12, 0.04

        # Bus type color mapping
        bus_colors = {
            "Slack": "#FF4500",  # Red-orange
            "PV": "#32CD32",  # Green
            "PQ": "#A9A9A9",  # Gray
        }

        # Draw transmission lines first (so they appear behind buses)
        for _, line_row in line_df.iterrows():
            if status_col is None or line_row[status_col] == 1:  # Only active lines
                if ibus_col in line_df.columns and jbus_col in line_df.columns:
                    ibus, jbus = line_row[ibus_col], line_row[jbus_col]
                    if ibus in pos and jbus in pos:
                        x1, y1 = pos[ibus]
                        x2, y2 = pos[jbus]
                        ax.plot([x1, x2], [y1, y2], "k-", linewidth=1.5, alpha=0.7)

        # Identify buses with generators and loads - handle column variations
        gen_bus_col = "bus" if "bus" in gen_df.columns else "connected_bus"
        load_bus_col = "bus" if "bus" in load_df.columns else "connected_bus"
        gen_status_col = "status" if "status" in gen_df.columns else None
        load_status_col = "status" if "status" in load_df.columns else None

        # Get active generators and loads
        if gen_status_col:
            gen_buses = set(gen_df[gen_df[gen_status_col] == 1][gen_bus_col])
        else:
            gen_buses = set(gen_df[gen_bus_col])

        if load_status_col:
            load_buses = set(load_df[load_df[load_status_col] == 1][load_bus_col])
        else:
            load_buses = set(load_df[load_bus_col])

        # Draw buses
        bus_type_col = "type" if "type" in bus_df.columns else "control"
        # Determine bus column name
        if "bus" in bus_df.columns:
            bus_col = "bus"
        else:
            # Bus numbers are in the index
            bus_col = None

        for _, bus_row in bus_df.iterrows():
            if bus_col:
                bus_num = bus_row[bus_col]
            else:
                bus_num = bus_row.name  # Use index value
            if bus_num not in pos:
                continue

            x, y = pos[bus_num]
            bus_type = bus_row[bus_type_col] if bus_type_col in bus_df.columns else "PQ"
            bus_color = bus_colors.get(bus_type, "#D3D3D3")  # Default light gray

            # Draw bus rectangle
            rect = Rectangle(
                (x - node_width / 2, y - node_height / 2),
                node_width,
                node_height,
                linewidth=1.5,
                edgecolor="black",
                facecolor=bus_color,
            )
            ax.add_patch(rect)

            # Add bus number label
            ax.text(
                x,
                y,
                str(bus_num),
                fontsize=8,
                fontweight="bold",
                ha="center",
                va="center",
            )

            # Draw generators (circles above bus)
            if bus_num in gen_buses:
                gen_x = x
                gen_y = y + node_height / 2 + 0.05
                gen_size = 0.02
                # Connection line from bus to generator
                ax.plot(
                    [x, gen_x],
                    [y + node_height / 2, gen_y - gen_size],
                    color="black",
                    linewidth=2,
                )
                # Generator circle
                ax.add_patch(
                    Circle(
                        (gen_x, gen_y),
                        gen_size,
                        color="none",
                        ec="black",
                        linewidth=1.5,
                    )
                )
                # Generator symbol 'G'
                ax.text(
                    gen_x,
                    gen_y,
                    "G",
                    fontsize=6,
                    fontweight="bold",
                    ha="center",
                    va="center",
                )

            # Draw loads (downward arrows)
            if bus_num in load_buses:
                load_x = x + node_width / 2 - 0.02
                load_y = y - node_height / 2
                ax.arrow(
                    load_x,
                    load_y,
                    0,
                    -0.04,
                    head_width=0.015,
                    head_length=0.015,
                    fc="black",
                    ec="black",
                )

        # Set up the plot
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)

        # Set title
        if title is None:
            case_name = getattr(self.engine, "case_name", "Power System")
            title = f"Single-Line Diagram - {case_name} ({software.upper()})"
        ax.set_title(title, fontsize=14, fontweight="bold")

        # Create legend
        legend_elements = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="black",
                markersize=8,
                label="Generator",
                markerfacecolor="none",
                markeredgecolor="black",
                linewidth=0,
            ),
            Line2D(
                [0],
                [0],
                marker="^",
                color="black",
                markersize=8,
                label="Load",
                markerfacecolor="black",
                linewidth=0,
            ),
            Line2D(
                [0],
                [0],
                marker="s",
                color="#FF4500",
                markersize=8,
                label="Slack Bus",
                markerfacecolor="#FF4500",
                linewidth=0,
            ),
            Line2D(
                [0],
                [0],
                marker="s",
                color="#32CD32",
                markersize=8,
                label="PV Bus",
                markerfacecolor="#32CD32",
                linewidth=0,
            ),
            Line2D(
                [0],
                [0],
                marker="s",
                color="#A9A9A9",
                markersize=8,
                label="PQ Bus",
                markerfacecolor="#A9A9A9",
                linewidth=0,
            ),
            Line2D([0], [0], color="black", linewidth=1.5, label="Transmission Line"),
        ]

        ax.legend(
            handles=legend_elements,
            loc="upper left",
            fontsize=10,
            frameon=True,
            edgecolor="black",
            title="Legend",
        )

        # Save if requested
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            print(f"SLD saved to: {save_path}")

        plt.tight_layout()
        if show:
            plt.show()
        return fig, ax

    def wec_analysis(self, farms: Optional[List[str]] = None, software: str = "pypsa"):
        """Create a 1×3 WEC farm analysis figure (power, contribution, voltage).

        Args:
            farms: Optional list of farm names to include.
            software: Backend identifier.
        """
        grid_obj = self._get_grid_obj(software)

        if grid_obj is None:
            print(
                f"Error: No grid data found for software '{software}'. "
                f"Use add_grid() for standalone GridState objects or ensure "
                f"the engine has '{software}' loaded."
            )
            return

        if not self.engine or not self.engine.wec_farms:
            print(
                f"Error: No WEC farms are defined in the engine. WEC analysis requires "
                f"engine with WEC farm data."
            )
            return

        target_farms = self.engine.wec_farms
        if farms:
            target_farms = [f for f in self.engine.wec_farms if f.farm_name in farms]

        if not target_farms:
            print("No matching WEC farms found.")
            return

        fig, axes = plt.subplots(1, 3, figsize=(20, 6))
        fig.suptitle("WEC Farm Analysis", fontsize=16)

        # 1. Active Power for each WEC farm
        wec_gen_names = [f.gen_name for f in target_farms]
        wec_power_df = grid_obj.gen_t.p[wec_gen_names]
        wec_power_df.plot(ax=axes[0])
        axes[0].set_title("WEC Farm Active Power Output")
        axes[0].set_ylabel("Active Power (pu)")
        axes[0].grid(True)

        # 2. WEC Farm total Contribution Percentage
        total_wec_power = wec_power_df.sum(axis=1)
        total_load_power = grid_obj.load_t.p.sum(axis=1)
        contribution_pct = (total_wec_power / total_load_power * 100).dropna()
        contribution_pct.plot(ax=axes[1])
        axes[1].set_title("WEC Power Contribution")
        axes[1].set_ylabel("Contribution to Total Load (%)")
        axes[1].grid(True)

        # 3. WEC-Farm Bus Voltage
        wec_bus_names = [f"Bus_{f.bus_location}" for f in target_farms]
        wec_bus_voltages = grid_obj.bus_t.v_mag[wec_bus_names]
        wec_bus_voltages.plot(ax=axes[2])
        axes[2].set_title("WEC Farm Bus Voltage")
        axes[2].set_ylabel("Voltage (pu)")
        axes[2].grid(True)

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()

    def compare_modelers(
        self,
        grid_component: str,
        name: List[str],
        parameter: str,
        annotate: bool = False,
        dataframe: bool = False,
        print_metrics: bool = True,
    ):
        """Compare a component parameter across PSS®E and PyPSA.

        Args:
            grid_component: Component type ("bus", "gen", "load", "line").
            name: Component name(s) to compare.
            parameter: Parameter to compare (e.g., "p", "v_mag").
            annotate: If True, overlay metrics text on the figure.
            dataframe: If True, return only a metrics DataFrame and do not show the plot.
            print_metrics: If True, print metrics to stdout.

        Returns:
            - If `dataframe` is False (default): `(Figure, Axes)` for the comparison plot.
            - If `dataframe` is True: a pandas `DataFrame` with columns
              ["component", "rmse", "mae", "max_abs_err", "mape_pct",
              "nrmse_mean", "nrmse_range", "r", "n"]. Returns `None` if
              metrics cannot be computed.
        """
        # Check for available software data
        available_software = []
        for software in ["psse", "pypsa"]:
            if self._get_grid_obj(software) is not None:
                available_software.append(software)

        if len(available_software) < 2:
            print(
                f"Error: Need at least 2 software backends for comparison. "
                f"Available: {available_software}. Use add_grid() to add GridState objects "
                f"or ensure both 'psse' and 'pypsa' are loaded in the engine."
            )
            return None if dataframe else (None, None)

        fig, ax = plt.subplots(figsize=(12, 6))

        # Storage for normalized time series per software for metrics
        ts_data = {}
        # Map of requested component name -> friendly display name per software
        friendly_names = {"psse": {}, "pypsa": {}}
        metrics_df = None

        for software in available_software:
            grid_obj = self._get_grid_obj(software)
            component_data_t = getattr(grid_obj, f"{grid_component}_t", None)

            if component_data_t is None or parameter not in component_data_t:
                print(
                    f"Error: Parameter '{parameter}' not found for '{grid_component}' in '{software}'."
                )
                continue

            data = component_data_t[parameter]

            # Ensure name is a list
            if isinstance(name, str):
                name = [name]

            # Try to find components by name first, then by ID
            available_components = []
            # Keep the requested names aligned with available_components order for metrics
            metric_cols = []
            component_df = getattr(grid_obj, grid_component, None)

            for comp_name in name:
                # First try direct column match (for live engine data)
                if comp_name in data.columns:
                    available_components.append(comp_name)
                    metric_cols.append(comp_name)
                # Then try to find by name->ID mapping (for pulled GridState data)
                elif component_df is not None:
                    # Try to find the component ID by name
                    name_col = f"{grid_component}_name"
                    id_col = grid_component

                    if (
                        name_col in component_df.columns
                        and id_col in component_df.columns
                    ):
                        # Find the ID for this name
                        matching_rows = component_df[
                            component_df[name_col] == comp_name
                        ]
                        if not matching_rows.empty:
                            comp_id = matching_rows.iloc[0][id_col]
                            # Check if this ID exists as a column in the time series
                            if comp_id in data.columns:
                                available_components.append(comp_id)
                                metric_cols.append(comp_name)
                            elif str(comp_id) in data.columns:
                                available_components.append(str(comp_id))
                                metric_cols.append(comp_name)

                    # Also try treating the name as an ID directly
                    elif comp_name in data.columns:
                        available_components.append(comp_name)
                        metric_cols.append(comp_name)
                    elif str(comp_name) in data.columns:
                        available_components.append(str(comp_name))
                        metric_cols.append(comp_name)

            if not available_components:
                print(f"Warning: Component(s) {name} not found in {software} data.")
                print(
                    f"  Available columns: {list(data.columns)[:10]}..."
                )  # Show first 10 columns
                continue

            df_to_plot = data[available_components].copy()

            # Convert index to time-of-day format (ignore dates, keep time)
            if hasattr(df_to_plot.index, "time"):
                # Extract time-of-day and create a new index with step numbers
                time_of_day = df_to_plot.index.time
                # Convert to datetime with common base date and time info
                import datetime

                base_date = datetime.date(2000, 1, 1)  # Common base date
                new_index = [
                    datetime.datetime.combine(base_date, t) for t in time_of_day
                ]
                df_to_plot.index = pd.DatetimeIndex(new_index)
            elif hasattr(df_to_plot.index, "hour"):
                # If already datetime, normalize to same base date
                import datetime

                base_date = datetime.date(2000, 1, 1)
                new_index = []
                for dt in df_to_plot.index:
                    time_part = dt.time()
                    new_dt = datetime.datetime.combine(base_date, time_part)
                    new_index.append(new_dt)
                df_to_plot.index = pd.DatetimeIndex(new_index)
            else:
                # If index is not datetime, use step numbers
                df_to_plot.index = range(len(df_to_plot))

            # Build metrics DataFrame keyed by requested component names
            df_metric = df_to_plot.copy()
            df_metric.columns = metric_cols

            # Create meaningful column names for the legend and map friendly names
            renamed_cols = []
            friendly_in_order = []
            for col in df_to_plot.columns:
                # Try to get the component name from the component DataFrame
                if component_df is not None:
                    name_col = f"{grid_component}_name"
                    id_col = grid_component

                    if (
                        name_col in component_df.columns
                        and id_col in component_df.columns
                    ):
                        # Find the name for this ID
                        if id_col in component_df.columns:
                            matching_rows = component_df[component_df[id_col] == col]
                            if (
                                not matching_rows.empty
                                and name_col in component_df.columns
                            ):
                                comp_title = matching_rows.iloc[0][name_col]
                                renamed_cols.append(f"{comp_title}_{software.upper()}")
                                friendly_in_order.append(str(comp_title))
                            else:
                                renamed_cols.append(f"{col}_{software.upper()}")
                                friendly_in_order.append(str(col))
                        else:
                            renamed_cols.append(f"{col}_{software.upper()}")
                            friendly_in_order.append(str(col))
                    else:
                        renamed_cols.append(f"{col}_{software.upper()}")
                        friendly_in_order.append(str(col))
                else:
                    renamed_cols.append(f"{col}_{software.upper()}")
                    friendly_in_order.append(str(col))

            # Rename columns for legend
            df_to_plot.columns = renamed_cols

            # Save normalized series for metrics and friendly name mapping
            ts_data[software] = df_metric
            # Map requested metric column names to friendly names
            try:
                friendly_names[software] = {
                    metric_cols[i]: friendly_in_order[i] for i in range(len(metric_cols))
                }
            except Exception:
                # Fallback to identity map if alignment fails
                friendly_names[software] = {c: str(c) for c in df_metric.columns}

            df_to_plot.plot(ax=ax, linestyle="--" if software == "psse" else "-")

        ax.set_title(
            f"Comparison for {grid_component.capitalize()} {name}: {parameter.capitalize()}"
        )
        ax.set_ylabel(parameter)
        ax.set_xlabel("Time of Day")
        ax.grid(True)
        ax.legend()

        # Compute and display metrics if both PSSE and PYPSA present
        if all(s in ts_data for s in ["psse", "pypsa"]):
            df_psse = ts_data["psse"].copy()
            df_pypsa = ts_data["pypsa"].copy()

            # Align on shared components and timestamps
            common_cols = [c for c in df_psse.columns if c in df_pypsa.columns]
            if common_cols:
                df_psse = df_psse[common_cols]
                df_pypsa = df_pypsa[common_cols]
                df_psse, df_pypsa = df_psse.align(df_pypsa, join="inner", axis=0)

                metrics_lines = []
                metrics_rows = []
                if print_metrics:
                    print("\nComparison metrics (PSSE vs PYPSA):")
                for col in common_cols:
                    s1 = df_psse[col]
                    s2 = df_pypsa[col]
                    mask = s1.notna() & s2.notna()
                    # Coerce to numeric and drop any non-numeric remnants
                    s1c = pd.to_numeric(s1[mask], errors="coerce")
                    s2c = pd.to_numeric(s2[mask], errors="coerce")
                    mask2 = s1c.notna() & s2c.notna()
                    s1v = s1c[mask2].to_numpy(dtype=float).ravel()
                    s2v = s2c[mask2].to_numpy(dtype=float).ravel()
                    if len(s1v) == 0:
                        rmse = np.nan
                        mae = np.nan
                        corr = np.nan
                        n = 0
                        max_abs_err = np.nan
                        mape_pct = np.nan
                        nrmse_mean = np.nan
                        nrmse_range = np.nan
                    else:
                        err = s1v - s2v
                        rmse = float(np.sqrt(np.mean(err ** 2)))
                        mae = float(np.mean(np.abs(err)))
                        max_abs_err = float(np.max(np.abs(err)))
                        # Normalizations (use PSSE as reference)
                        eps = 1e-12
                        denom_mean = float(np.mean(np.abs(s1v)))
                        if denom_mean < eps:
                            nrmse_mean = np.nan
                        else:
                            nrmse_mean = float(rmse / denom_mean)
                        rng = float(np.max(s1v) - np.min(s1v))
                        if rng < eps:
                            nrmse_range = np.nan
                        else:
                            nrmse_range = float(rmse / rng)
                        # MAPE in percent; ignore zero references
                        nonzero = np.abs(s1v) > eps
                        if np.any(nonzero):
                            mape_pct = float(100.0 * np.mean(np.abs(err[nonzero] / s1v[nonzero])))
                        else:
                            mape_pct = np.nan
                        # Pearson correlation (manual) with ddof=1
                        if len(s1v) < 2:
                            corr = np.nan
                        else:
                            sx = float(np.std(s1v, ddof=1))
                            sy = float(np.std(s2v, ddof=1))
                            if sx <= eps or sy <= eps:
                                corr = np.nan
                            else:
                                xm = float(np.mean(s1v))
                                ym = float(np.mean(s2v))
                                cov = float(np.sum((s1v - xm) * (s2v - ym)) / (len(s1v) - 1))
                                corr = float(cov / (sx * sy))
                        n = int(len(s1v))

                    # Prefer PSSE friendly name, then PYPSA, else the key
                    friendly = (
                        friendly_names.get("psse", {}).get(col)
                        or friendly_names.get("pypsa", {}).get(col)
                        or str(col)
                    )
                    line = (
                        f"{friendly}: RMSE={rmse:.4g}, MAE={mae:.4g}, MaxAE={max_abs_err:.4g}, "
                        f"MAPE%={mape_pct:.4g}, NRMSE(mean)={nrmse_mean:.4g}, NRMSE(range)={nrmse_range:.4g}, R={corr:.3f}"
                    )
                    metrics_lines.append(line)
                    if print_metrics:
                        print(line)
                    metrics_rows.append(
                        {
                            "component": friendly,
                            "rmse": rmse,
                            "mae": mae,
                            "max_abs_err": max_abs_err,
                            "mape_pct": mape_pct,
                            "nrmse_mean": nrmse_mean,
                            "nrmse_range": nrmse_range,
                            "r": corr,
                            "n": n,
                        }
                    )

                # Annotate on the figure if requested
                if metrics_lines and annotate:
                    ax.text(
                        0.01,
                        0.99,
                        "\n".join(metrics_lines),
                        transform=ax.transAxes,
                        ha="left",
                        va="top",
                        fontsize=9,
                        bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"),
                    )

                # Build metrics dataframe, preserve order of common_cols
                try:
                    metrics_df = pd.DataFrame(
                        metrics_rows,
                        columns=[
                            "component",
                            "rmse",
                            "mae",
                            "max_abs_err",
                            "mape_pct",
                            "nrmse_mean",
                            "nrmse_range",
                            "r",
                            "n",
                        ],
                    )
                except Exception:
                    metrics_df = pd.DataFrame(metrics_rows)

        # Format x-axis for better time display if datetime index
        try:
            if hasattr(ax.get_lines()[0].get_xdata(), "__iter__"):
                # Check if we have datetime data
                first_data = None
                for line in ax.get_lines():
                    if len(line.get_xdata()) > 0:
                        first_data = line.get_xdata()[0]
                        break

                if first_data is not None and hasattr(first_data, "hour"):
                    # Format x-axis to show time nicely
                    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
                    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        except:
            pass  # Fall back to default formatting if anything goes wrong

        plt.tight_layout()
        # Return depending on 'dataframe' flag
        if dataframe:
            # Do not display the figure when only metrics are requested
            return metrics_df
        else:
            plt.show()
            return fig, ax
