"""
WEC-Grid high-level plotting interface

This module provides comprehensive visualization capabilities for WEC-GRID simulation
results, supporting cross-platform comparison between PSS®E and PyPSA modeling backends.
"""

# Standard library
from typing import Any, List, Optional, Tuple, Union

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
    """
    A focused plotting interface for WEC-GRID simulation visualization.

    This class provides methods to plot time-series data for various grid
    components, create single-line diagrams, and compare results from different
    modeling backends (PSS®E and PyPSA). Can work with live engine data or
    standalone GridState objects from database pulls.
    """

    def __init__(self, engine: Any = None):
        """
        Initialize the plotter with a WEC-GRID Engine instance or for standalone use.

        Args:
            engine: The WEC-GRID Engine containing simulation data. Can be None for
                   standalone usage with GridState objects.
        """
        self.engine = engine
        self._standalone_grids = {}  # Store GridState objects for standalone usage

    def add_grid(self, software: str, grid_state):
        """Add a GridState object for standalone plotting.
        
        Allows plotting of simulation data without requiring the original modeling
        software to be installed. Useful for analyzing database-pulled simulations.
        
        Args:
            software (str): Software identifier ("psse", "pypsa", etc.)
            grid_state: GridState object containing simulation data
            
        Example:
            >>> plotter = WECGridPlot()
            >>> psse_grid = engine.database.pull_sim(grid_sim_id=1, software='psse')
            >>> plotter.add_grid('psse', psse_grid)
            >>> plotter.gen(software='psse', parameter='p')
        """
        self._standalone_grids[software] = grid_state
    
    @classmethod
    def from_database(cls, database, grid_sim_id: int, software: str = None):
        """Create a standalone plotter from database simulation data.
        
        Convenience method to create a plotter with GridState data pulled from
        the database, without requiring the original modeling software.
        
        Args:
            database: WECGridDB instance
            grid_sim_id (int): Grid simulation ID to retrieve
            software (str, optional): Software backend ("psse" or "pypsa").
                If None, auto-detects from database.
                
        Returns:
            WECGridPlot: Plotter instance with GridState data loaded
            
        Example:
            >>> plotter = WECGridPlot.from_database(
            ...     engine.database, grid_sim_id=1, software='psse'
            ... )
            >>> plotter.gen(software='psse', parameter='p')
        """
        plotter = cls(engine=None)
        grid_state = database.pull_sim(grid_sim_id, software)
        plotter.add_grid(grid_state.software, grid_state)
        return plotter
        
    def _get_grid_obj(self, software: str):
        """Get GridState object from engine or standalone storage.
        
        Args:
            software (str): Software identifier ("psse", "pypsa", etc.)
            
        Returns:
            GridState object or None if not found
        """
        # First try standalone grids
        if software in self._standalone_grids:
            return self._standalone_grids[software]
            
        # Then try engine
        if self.engine and hasattr(self.engine, software):
            modeler = getattr(self.engine, software)
            if modeler and hasattr(modeler, 'grid'):
                return modeler.grid
                
        return None

    def _plot_time_series(self, software: str, component_type: str, parameter: str,
                          components: Optional[List[str]] = None,
                          title: str = "", ax: Optional[plt.Axes] = None,
                          ylabel: str = "", xlabel: str = "Time"):
        """Internal helper to plot time-series data for any component.

        Args:
            software (str):
                Modeling backend identifier (e.g., ``"psse"`` or ``"pypsa"``).
                Can reference engine modelers or standalone GridState objects.
            component_type (str):
                Grid component group to plot (``"gen"``, ``"bus"``,
                ``"load"``, ``"line"``, etc.).
            parameter (str):
                Name of the time-series parameter to visualize. This must
                exist within ``<component_type>_t``.
            components (Optional[List[str]]):
                Specific components to include. If ``None``, all available
                components are plotted.
            title (str):
                Plot title. When empty, a default title is generated from the
                ``software``, ``component_type`` and ``parameter`` values.
            ax (Optional[plt.Axes]):
                Matplotlib axes on which to draw the plot. A new figure and
                axes are created when ``None``.
            ylabel (str):
                Label for the y-axis. Defaults to ``parameter`` when empty.
            xlabel (str):
                Label for the x-axis. Defaults to ``"Time"``.

        Returns:
            Tuple[plt.Figure, plt.Axes] | Tuple[None, None]:
                A tuple containing the Matplotlib ``Figure`` and ``Axes`` for
                the generated plot. Returns ``(None, None)`` when the required
                data are missing or none of the requested components are
                available.
        """
        grid_obj = self._get_grid_obj(software)
        
        if grid_obj is None:
            print(f"Error: No grid data found for software '{software}'. "
                  f"Use add_grid() for standalone GridState objects or ensure "
                  f"the engine has '{software}' loaded.")
            return None, None
        component_data_t = getattr(grid_obj, f"{component_type}_t", None)

        if component_data_t is None or parameter not in component_data_t:
            print(f"Error: Parameter '{parameter}' not found for '{component_type}' in '{software}'.")
            return None, None

        data = component_data_t[parameter]

        if components:
            # Ensure components is a list
            if isinstance(components, str):
                components = [components]
            
            # Filter columns that exist in the dataframe
            available_components = [c for c in components if c in data.columns]
            if not available_components:
                print(f"Warning: None of the specified components {components} found in data for {parameter}.")
                return None, None
            data = data[available_components]

        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 6))
        else:
            fig = ax.get_figure()

        data.plot(ax=ax, legend=True)
        ax.set_title(title or f"{software.upper()}: {component_type.capitalize()} {parameter.capitalize()}")
        ax.set_ylabel(ylabel or parameter)
        ax.set_xlabel(xlabel)
        ax.grid(True)
        
        # Truncate legend if it's too long
        if len(data.columns) > 10:
            ax.legend().set_visible(False)

        return fig, ax

    def gen(self, software: str = 'pypsa', parameter: str = 'p', gen: Optional[List[str]] = None):
        """Plot a generator parameter.

        Args:
            software: The modeling software to use (``"psse"`` or ``"pypsa"``).
            parameter: Generator parameter to plot (e.g., ``"p"``, ``"q"``).
            gen: A list of generator names to plot. If ``None``, all generators are shown.

        Returns:
            tuple[matplotlib.figure.Figure, matplotlib.axes.Axes]: The displayed
            figure and axes for further customization.
        """
        if parameter == 'p':
            title = f"{software.upper()}: Generator Active Power"
            ylabel = "Active Power [pu]"
        elif parameter == 'q':
            title = f"{software.upper()}: Generator Reactive Power"
            ylabel = "Reactive Power [pu]"
        else:
            print("not a valid parameter")
            return None, None

        fig, ax = self._plot_time_series(
            software, 'gen', parameter, components=gen, title=title, ylabel=ylabel
        )
        plt.show()
        return fig, ax

    def bus(self, software: str = 'pypsa', parameter: str = 'p', bus: Optional[List[str]] = None):
        """Plot a bus parameter.

        Args:
            software: The modeling software to use (``"psse"`` or ``"pypsa"``).
            parameter: Bus parameter to plot (e.g., ``"v_mag"``, ``"angle_deg"``).
            bus: A list of bus names to plot. If ``None``, all buses are shown.

        Returns:
            tuple[matplotlib.figure.Figure, matplotlib.axes.Axes]: The displayed
            figure and axes for further customization.
        """
        if parameter == 'p':
            title = f"{software.upper()}: Bus Active Power (net)"
            ylabel = "Active Power [pu]"
        elif parameter == 'q':
            title = f"{software.upper()}: Bus Reactive Power (net)"
            ylabel = "Reactive Power [pu]"
        elif parameter == 'v_mag':
            title = f"{software.upper()}: Bus Voltage Magnitude"
            ylabel = "Voltage (pu)"
        elif parameter == 'angle_deg':
            title = f"{software.upper()}: Bus Voltage Angle"
            ylabel = "Angle (degrees)"
        else:
            print("not a valid parameter")
            return None, None

        fig, ax = self._plot_time_series(
            software, 'bus', parameter, components=bus, title=title, ylabel=ylabel
        )
        plt.show()
        return fig, ax

    def load(self, software: str = 'pypsa', parameter: str = 'p', load: Optional[List[str]] = None):
        """Plot a load parameter.

        Args:
            software: The modeling software to use (``"psse"`` or ``"pypsa"``).
            parameter: Load parameter to plot (e.g., ``"p"``, ``"q"``).
            load: A list of load names to plot. If ``None``, all loads are shown.

        Returns:
            tuple[matplotlib.figure.Figure, matplotlib.axes.Axes]: The displayed
            figure and axes for further customization.
        """
        if parameter == 'p':
            title = f"{software.upper()}: Load Active Power"
            ylabel = "Active Power [pu]"
        elif parameter == 'q':
            title = f"{software.upper()}: Load Reactive Power"
            ylabel = "Reactive Power [pu]"
        else:
            print("not a valid parameter")
            return None, None

        fig, ax = self._plot_time_series(
            software, 'load', parameter, components=load, title=title, ylabel=ylabel
        )
        plt.show()
        return fig, ax

    def line(self, software: str = 'pypsa', parameter: str = 'line_pct', line: Optional[List[str]] = None):
        """Plot a line parameter.

        Args:
            software: The modeling software to use (``"psse"`` or ``"pypsa"``).
            parameter: Line parameter to plot. Defaults to ``"line_pct"``.
            line: A list of line names to plot. If ``None``, all lines are shown.

        Returns:
            tuple[matplotlib.figure.Figure, matplotlib.axes.Axes]: The displayed
            figure and axes for further customization.
        """
        if parameter == 'line_pct':
            title = f"{software.upper()}: Line Percent Loading"
            ylabel = "Percent Loading [%]"
        else:
            print("not a valid parameter")
            return None, None

        fig, ax = self._plot_time_series(
            software, 'line', parameter, components=line, title=title, ylabel=ylabel
        )
        plt.show()
        return fig, ax

    def sld(self, software: str = 'pypsa', figsize=(14, 10), title=None, save_path=None):
        """Generate single-line diagram using GridState data.
        
        Creates a single-line diagram visualization using the standardized GridState
        component data. Works with both PSS®E and PyPSA backends by using the unified
        data schema from GridState snapshots.
        
        Args:
            software (str): Backend software ("psse" or "pypsa")
            figsize (tuple): Figure size as (width, height)
            title (str, optional): Custom title for the diagram
            save_path (str, optional): Path to save the figure
            show (bool): Whether to display the figure (default: False)
            
        Returns:
            matplotlib.figure.Figure: The generated SLD figure
            
        Notes:
            Uses NetworkX for automatic layout calculation since GridState doesn't
            include geographical bus positions. The diagram includes:
            
            - Buses: Colored rectangles based on type (Slack=red, PV=green, PQ=gray)
            - Lines: Black dashed lines connecting buses
            - Generators: Circles above buses with generators
            - Loads: Downward arrows on buses with loads
            
            Limitations:
            - No transformer identification (would need additional data)
            - Layout is algorithmic, not geographical
            - No shunt devices (not in GridState schema)
        """
        # Get the appropriate grid object
        grid_obj = self._get_grid_obj(software)
        
        if grid_obj is None:
            raise ValueError(f"No grid data found for software '{software}'. "
                           f"Use add_grid() for standalone GridState objects or ensure "
                           f"the engine has '{software}' loaded.")
        
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
        if 'bus' not in bus_df.columns and bus_df.index.name != 'bus':
            print(f"  ERROR: 'bus' column missing from bus DataFrame")
            print(f"  Available columns: {list(bus_df.columns)}")
            print(f"  Index name: {bus_df.index.name}")
            print(f"  Bus DataFrame head:\n{bus_df.head()}")
            
            # Check if bus numbers are in the index
            if bus_df.index.name == 'bus' or 'bus' in str(bus_df.index.name).lower():
                print("  Bus numbers found in DataFrame index, will use index values")
            else:
                raise ValueError("Bus DataFrame missing required 'bus' column or index")
        
        # Create network graph for layout
        G = nx.Graph()
        
        # Add buses as nodes - handle index vs column
        if 'bus' in bus_df.columns:
            bus_numbers = bus_df['bus']
        else:
            # Bus numbers are in the index
            bus_numbers = bus_df.index
            
        for bus_num in bus_numbers:
            G.add_node(bus_num)
        
        # Add lines as edges - handle potential column name variations  
        ibus_col = 'ibus' if 'ibus' in line_df.columns else 'from_bus'
        jbus_col = 'jbus' if 'jbus' in line_df.columns else 'to_bus'
        status_col = 'status' if 'status' in line_df.columns else None
        
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
                    1.5 * (pos[node][1] - y_min) / (y_max - y_min) - 0.5
                )
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Bus visualization parameters
        node_width, node_height = 0.12, 0.04
        
        # Bus type color mapping
        bus_colors = {
            "Slack": "#FF4500",  # Red-orange
            "PV": "#32CD32",     # Green  
            "PQ": "#A9A9A9",     # Gray
        }
        
        # Draw transmission lines first (so they appear behind buses)
        for _, line_row in line_df.iterrows():
            if status_col is None or line_row[status_col] == 1:  # Only active lines
                if ibus_col in line_df.columns and jbus_col in line_df.columns:
                    ibus, jbus = line_row[ibus_col], line_row[jbus_col]
                    if ibus in pos and jbus in pos:
                        x1, y1 = pos[ibus]
                        x2, y2 = pos[jbus]
                        ax.plot([x1, x2], [y1, y2], 'k-', linewidth=1.5, alpha=0.7)
        
        # Identify buses with generators and loads - handle column variations
        gen_bus_col = 'bus' if 'bus' in gen_df.columns else 'connected_bus'
        load_bus_col = 'bus' if 'bus' in load_df.columns else 'connected_bus'
        gen_status_col = 'status' if 'status' in gen_df.columns else None
        load_status_col = 'status' if 'status' in load_df.columns else None
        
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
        bus_type_col = 'type' if 'type' in bus_df.columns else 'control'
        # Determine bus column name
        if 'bus' in bus_df.columns:
            bus_col = 'bus'
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
                node_width, node_height,
                linewidth=1.5, 
                edgecolor='black', 
                facecolor=bus_color
            )
            ax.add_patch(rect)
            
            # Add bus number label
            ax.text(x, y, str(bus_num), fontsize=8, fontweight="bold", 
                   ha='center', va='center')
            
            # Draw generators (circles above bus)
            if bus_num in gen_buses:
                gen_x = x
                gen_y = y + node_height / 2 + 0.05
                gen_size = 0.02
                # Connection line from bus to generator
                ax.plot([x, gen_x], [y + node_height / 2, gen_y - gen_size], 
                       color='black', linewidth=2)
                # Generator circle
                ax.add_patch(Circle((gen_x, gen_y), gen_size, 
                                  color='none', ec='black', linewidth=1.5))
                # Generator symbol 'G'
                ax.text(gen_x, gen_y, 'G', fontsize=6, fontweight="bold",
                       ha='center', va='center')
            
            # Draw loads (downward arrows)
            if bus_num in load_buses:
                load_x = x + node_width / 2 - 0.02
                load_y = y - node_height / 2
                ax.arrow(load_x, load_y, 0, -0.04, 
                        head_width=0.015, head_length=0.015, 
                        fc='black', ec='black')
        
        # Set up the plot
        ax.set_aspect('equal', adjustable='datalim')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)
        
        # Set title
        if title is None:
            case_name = getattr(self.engine, 'case_name', 'Power System')
            title = f"Single-Line Diagram - {case_name} ({software.upper()})"
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        # Create legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='black', markersize=8, 
                   label="Generator", markerfacecolor='none', 
                   markeredgecolor='black', linewidth=0),
            Line2D([0], [0], marker='^', color='black', markersize=8, 
                   label="Load", markerfacecolor='black', linewidth=0),
            Line2D([0], [0], marker='s', color='#FF4500', markersize=8, 
                   label="Slack Bus", markerfacecolor='#FF4500', linewidth=0),
            Line2D([0], [0], marker='s', color='#32CD32', markersize=8, 
                   label="PV Bus", markerfacecolor='#32CD32', linewidth=0),
            Line2D([0], [0], marker='s', color='#A9A9A9', markersize=8, 
                   label="PQ Bus", markerfacecolor='#A9A9A9', linewidth=0),
            Line2D([0], [0], color='black', linewidth=1.5, 
                   label="Transmission Line"),
        ]
        
        ax.legend(handles=legend_elements, loc="upper left", fontsize=10, 
                 frameon=True, edgecolor='black', title="Legend")
        
        # Save if requested
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"SLD saved to: {save_path}")
        
        plt.tight_layout()
        plt.show()
        #return fig, ax

    def wec_analysis(self, farms: Optional[List[str]] = None, software: str = 'pypsa'):
        """
        Creates a 1x3 figure analyzing WEC farm performance.

        Args:
            farms (Optional[List[str]]): A list of farm names to analyze. If None, all farms are analyzed.
            software (str): The modeling software to use. Defaults to 'pypsa'.
        """
        grid_obj = self._get_grid_obj(software)
        
        if grid_obj is None:
            print(f"Error: No grid data found for software '{software}'. "
                  f"Use add_grid() for standalone GridState objects or ensure "
                  f"the engine has '{software}' loaded.")
            return
            
        if not self.engine or not self.engine.wec_farms:
            print(f"Error: No WEC farms are defined in the engine. WEC analysis requires "
                  f"engine with WEC farm data.")
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

    def compare_modelers(self, grid_component: str, name: List[str], parameter: str):
        """
        Compares a parameter for a specific component between PSS®E and PyPSA.
        
        Works with both live engine data and standalone GridState objects added
        via add_grid().

        Args:
            grid_component (str): The type of component ('bus', 'gen', 'load', 'line').
            name (List[str]): The name(s) of the component(s) to compare.
            parameter (str): The parameter to compare.
        """
        # Check for available software data
        available_software = []
        for software in ['psse', 'pypsa']:
            if self._get_grid_obj(software) is not None:
                available_software.append(software)
        
        if len(available_software) < 2:
            print(f"Error: Need at least 2 software backends for comparison. "
                  f"Available: {available_software}. Use add_grid() to add GridState objects "
                  f"or ensure both 'psse' and 'pypsa' are loaded in the engine.")
            return

        fig, ax = plt.subplots(figsize=(12, 6))

        for software in available_software:
            grid_obj = self._get_grid_obj(software)
            component_data_t = getattr(grid_obj, f"{grid_component}_t", None)
            
            if component_data_t is None or parameter not in component_data_t:
                print(f"Error: Parameter '{parameter}' not found for '{grid_component}' in '{software}'.")
                continue

            data = component_data_t[parameter]
            
            # Ensure name is a list
            if isinstance(name, str):
                name = [name]
            
            # Try to find components by name first, then by ID
            available_components = []
            component_df = getattr(grid_obj, grid_component, None)
            
            for comp_name in name:
                # First try direct column match (for live engine data)
                if comp_name in data.columns:
                    available_components.append(comp_name)
                # Then try to find by name->ID mapping (for pulled GridState data)
                elif component_df is not None:
                    # Try to find the component ID by name
                    name_col = f"{grid_component}_name"
                    id_col = grid_component
                    
                    if name_col in component_df.columns and id_col in component_df.columns:
                        # Find the ID for this name
                        matching_rows = component_df[component_df[name_col] == comp_name]
                        if not matching_rows.empty:
                            comp_id = matching_rows.iloc[0][id_col]
                            # Check if this ID exists as a column in the time series
                            if comp_id in data.columns:
                                available_components.append(comp_id)
                            elif str(comp_id) in data.columns:
                                available_components.append(str(comp_id))
                    
                    # Also try treating the name as an ID directly
                    elif comp_name in data.columns:
                        available_components.append(comp_name)
                    elif str(comp_name) in data.columns:
                        available_components.append(str(comp_name))
            
            if not available_components:
                print(f"Warning: Component(s) {name} not found in {software} data.")
                print(f"  Available columns: {list(data.columns)[:10]}...")  # Show first 10 columns
                continue
            
            df_to_plot = data[available_components].copy()
            
            # Convert index to time-of-day format (ignore dates, keep time)
            if hasattr(df_to_plot.index, 'time'):
                # Extract time-of-day and create a new index with step numbers
                time_of_day = df_to_plot.index.time
                # Convert to datetime with common base date and time info
                import datetime
                base_date = datetime.date(2000, 1, 1)  # Common base date
                new_index = [datetime.datetime.combine(base_date, t) for t in time_of_day]
                df_to_plot.index = pd.DatetimeIndex(new_index)
            elif hasattr(df_to_plot.index, 'hour'):
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
            
            # Create meaningful column names for the legend
            renamed_cols = []
            for col in df_to_plot.columns:
                # Try to get the component name from the component DataFrame
                if component_df is not None:
                    name_col = f"{grid_component}_name"
                    id_col = grid_component
                    
                    if name_col in component_df.columns and id_col in component_df.columns:
                        # Find the name for this ID
                        if id_col in component_df.columns:
                            matching_rows = component_df[component_df[id_col] == col]
                            if not matching_rows.empty and name_col in component_df.columns:
                                comp_name = matching_rows.iloc[0][name_col]
                                renamed_cols.append(f"{comp_name}_{software.upper()}")
                            else:
                                renamed_cols.append(f"{col}_{software.upper()}")
                        else:
                            renamed_cols.append(f"{col}_{software.upper()}")
                    else:
                        renamed_cols.append(f"{col}_{software.upper()}")
                else:
                    renamed_cols.append(f"{col}_{software.upper()}")
            
            # Rename columns for legend
            df_to_plot.columns = renamed_cols
            
            df_to_plot.plot(ax=ax, linestyle='--' if software == 'psse' else '-')

        ax.set_title(f"Comparison for {grid_component.capitalize()} {name}: {parameter.capitalize()}")
        ax.set_ylabel(parameter)
        ax.set_xlabel("Time of Day")
        ax.grid(True)
        ax.legend()
        
        # Format x-axis for better time display if datetime index
        try:
            if hasattr(ax.get_lines()[0].get_xdata(), '__iter__'):
                # Check if we have datetime data
                first_data = None
                for line in ax.get_lines():
                    if len(line.get_xdata()) > 0:
                        first_data = line.get_xdata()[0]
                        break
                
                if first_data is not None and hasattr(first_data, 'hour'):
                    # Format x-axis to show time nicely
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        except:
            pass  # Fall back to default formatting if anything goes wrong
        
        plt.tight_layout()
        plt.show()