"""
Modeler manager for Marine-Grid.

File: src/marinegrid/modeler/manager.py
"""

# Standard library
import warnings
from typing import Any, TYPE_CHECKING
# Third-party
import pandas as pd

# Local
from ..util.grid_data import GridData
from ..util.grid_instance import GridInstance
from .powersystem.base import PowerSystemModeler, SolveResult

if TYPE_CHECKING:
    from ..util.time import Time
    from ..renewables.farm import RenewableEnergyFarm


class ModelerManager:
    """
    Unified interface for managing multiple backend modelers.

    Provides dynamic loading and management of different modeler types
    (power system, WEC simulation, etc.). Enables plugin-style architecture
    where modelers can be loaded on-demand without tight coupling.

    Owns the simulation timeline (Time) and grid history (GridData) for
    each power system backend. Manages renewable energy farms and
    coordinates their integration during simulation.

    Attributes:
        modelers: Dictionary of instantiated modeler instances keyed by name.
        farms: List of registered renewable energy farms.

    Example:
        >>> manager = ModelerManager()
        >>> manager.set_time(study.time)
        >>> pypsa = manager.load_modeler("pypsa")
        >>> pypsa.initialize(network)
        >>> manager.add_farm(wec_farm)
        >>> manager.simulate()
        >>> manager.get_data("pypsa")  # Access results
    """

    def __init__(self):
        """
        Initialize the ModelerManager.

        Sets up the internal registry of available modeler factories
        and prepares storage for instantiated modelers, farms, and data.
        """
        # Class objects
        self._time: "Time | None" = None
        self._grid_data: dict[str, GridData] = {}

        # Class attributes
        self.modelers: dict[str, Any] = {}
        self.farms: list["RenewableEnergyFarm"] = []
        self._registry = {
            "pypsa": self._load_pypsa,
            "wecsim": self._load_wecsim,
        }

    def __repr__(self) -> str:
        """Return a formatted summary of the modeler manager state."""
        loaded = ", ".join(self.modelers.keys()) if self.modelers else "None"
        farm_count = len(self.farms)

        if self._time is not None:
            time_str = f"{len(self._time)} steps @ {self._time.freq}"
        else:
            time_str = "Not set"

        # GridData summary
        data_parts = []
        for name, data in self._grid_data.items():
            data_parts.append(f"{name}: {len(data)} snapshots")
        data_str = ", ".join(data_parts) if data_parts else "No data"

        return (
            f"ModelerManager:\n"
            f"├─ Loaded: {loaded}\n"
            f"├─ Farms: {farm_count}\n"
            f"├─ Data: {data_str}\n"
            f"└─ Time: {time_str}"
        )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def time(self) -> "Time | None":
        """Get the central Time object for simulation timeline."""
        return self._time

    @property
    def grid_data(self) -> dict[str, GridData]:
        """Get all GridData instances keyed by backend name."""
        return self._grid_data

    @property
    def pypsa(self):
        """Get the PyPSA modeler if loaded."""
        return self.modelers.get("pypsa")

    @property
    def wecsim(self):
        """Get the WEC-Sim modeler if loaded."""
        return self.modelers.get("wecsim")


    # -------------------------------------------------------------------------
    # Time Management
    # -------------------------------------------------------------------------

    def set_time(self, time: "Time") -> None:
        """
        Set the central Time object for simulation timeline.

        Args:
            time: Time object to use as the simulation timeline.

        Raises:
            ValueError: If time is None.
        """
        if time is None:
            raise ValueError("time cannot be None")
        self._time = time
        # Propagate time to modelers that accept it (e.g., WECSimModeler)
        for modeler in self.modelers.values():
            if hasattr(modeler, "set_time"):
                modeler.set_time(time)

    # -------------------------------------------------------------------------
    # Data Access
    # -------------------------------------------------------------------------

    def get_data(self, name: str) -> GridData | None:
        """
        Get the GridData for a specific backend.

        Args:
            name: Backend name (e.g., "pypsa").

        Returns:
            GridData instance for that backend, or None if not found.
        """
        return self._grid_data.get(name)

    # -------------------------------------------------------------------------
    # Farm Management
    # -------------------------------------------------------------------------

    def add_farm(self, farm: "RenewableEnergyFarm", add_to_network: bool = True) -> bool:
        """
        Register a renewable energy farm for simulation.

        Adds the farm to the manager's list and propagates the farm's
        electrical infrastructure to ALL loaded power system modelers.

        Args:
            farm: WECFarm instance to register.
            add_to_network: If True and power system modelers are loaded,
                add the farm's bus, line, and generator to each network.

        Returns:
            True if farm was added successfully.

        Example:
            >>> manager.add_farm(wec_farm)
            >>> manager.simulate()  # Farm power updated each timestep
        """
        if farm in self.farms:
            warnings.warn(
                f"Farm {getattr(farm, 'farm_name', repr(farm))} already registered, skipping",
                stacklevel=2,
            )
            return False

        self.farms.append(farm)

        # Propagate farm to ALL loaded power system modelers
        if add_to_network:
            for name, modeler in self.modelers.items():
                if hasattr(modeler, "add_wec_farm"):
                    modeler.add_wec_farm(farm)

        return True

    def remove_farm(self, farm: "RenewableEnergyFarm") -> bool:
        """
        Remove a farm from the manager and all loaded power system modelers.

        Removes the farm's electrical infrastructure (bus, line, generator)
        from each power system modeler's network.

        Args:
            farm: WECFarm instance to remove.

        Returns:
            True if farm was removed, False if not found.
        """
        if farm not in self.farms:
            return False

        # Remove from all power system modelers
        for name, modeler in self.modelers.items():
            if hasattr(modeler, "remove_wec_farm"):
                modeler.remove_wec_farm(farm)

        # Remove from manager's list
        self.farms.remove(farm)
        return True

    def clear_farms(self) -> None:
        """Remove all registered farms."""
        self.farms.clear()

    # -------------------------------------------------------------------------
    # Modeler Loading
    # -------------------------------------------------------------------------

    def load_modeler(self, name: str, **kwargs) -> Any:
        """
        Load and attach a backend modeler by name.

        Dynamically imports and instantiates the requested modeler class,
        then registers it in the modelers dict. If a Time object is set,
        it will be automatically passed to modelers that accept it.

        For power system modelers, a GridData instance is created and
        stored in grid_data[name] for tracking simulation history.

        Args:
            name: Name of the modeler to load (e.g., "pypsa", "wecsim").
            **kwargs: Additional keyword arguments passed to modeler constructor.

        Returns:
            The instantiated modeler object.

        Raises:
            ValueError: If the modeler name is not supported.

        Example:
            >>> manager.load_modeler("pypsa")
            >>> manager.pypsa  # Access via property
            >>> manager.modelers["pypsa"]  # Access via dict
            >>> manager.get_data("pypsa")  # Access GridData
        """
        key = name.lower()
        try:
            factory = self._registry[key]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported modeler '{name}', supported: {list(self._registry)}"
            ) from exc

        cls = factory()
        inst = cls(**kwargs)
        self.modelers[key] = inst

        # Create GridData for power system modelers
        if isinstance(inst, PowerSystemModeler):
            self._grid_data[key] = GridData()

        # Pass time to modelers that accept it (e.g., WECSimModeler)
        if self._time is not None and hasattr(inst, "set_time"):
            inst.set_time(self._time)

        # Propagate existing farms to newly loaded power system modeler
        if hasattr(inst, "add_wec_farm"):
            for farm in self.farms:
                inst.add_wec_farm(farm)

        return inst

    def _load_pypsa(self) -> type:
        """Factory method for loading PyPSA modeler class."""
        from .powersystem.pypsa import PyPSAModeler
        return PyPSAModeler

    def _load_wecsim(self) -> type:
        """Factory method for loading WEC-Sim modeler class."""
        from .wecsim.wecsim import WECSimModeler
        return WECSimModeler

    # -------------------------------------------------------------------------
    # Simulation
    # -------------------------------------------------------------------------

    def simulate(
        self,
        gen_schedules: dict[str, pd.DataFrame] | None = None,
        load_schedules: dict[str, pd.DataFrame] | None = None,
    ) -> bool:
        """
        Run time-series simulation across all loaded power system modelers.

        For each timestep from the Time object:
            1. Update components from schedules
            2. Solve power flow on each backend
            3. Collect grid state from each backend
            4. Store GridInstance in that backend's GridData

        Args:
            gen_schedules: Dict mapping generator name to schedule DataFrame.
                Index should be timestamps, columns: p (and optionally q)
                in per-unit on system MVA base.
            load_schedules: Dict mapping load name to schedule DataFrame.
                Same format as gen_schedules.

        Returns:
            True if simulation completed successfully.

        Raises:
            RuntimeError: If Time is not configured.
        """
        if self._time is None:
            raise RuntimeError("Time not set. Call set_time() before simulate().")

        snapshots = self._time.snapshots
        gen_schedules = gen_schedules or {}
        load_schedules = load_schedules or {}

        # Validate schedule DataFrames
        snapshot_set = set(snapshots)
        for label, schedules in [("gen_schedules", gen_schedules), ("load_schedules", load_schedules)]:
            for name, schedule in schedules.items():
                if schedule.isnull().any().any():
                    raise ValueError(
                        f"{label}[{name!r}] contains NaN values"
                    )
                overlap = set(schedule.index) & snapshot_set
                if not overlap:
                    warnings.warn(
                        f"{label}[{name!r}] has no timestamps overlapping "
                        f"with simulation snapshots",
                        stacklevel=2,
                    )

        # Convert farms to generator schedules
        for farm in self.farms:
            if hasattr(farm, "get_power_timeseries") and getattr(farm, "gen_name", None):
                farm_schedule = farm.get_power_timeseries()
                if farm_schedule is not None and not farm_schedule.empty:
                    gen_schedules[farm.gen_name] = farm_schedule

        # Identify power system modelers
        ps_modelers = {
            name: m for name, m in self.modelers.items()
            if isinstance(m, PowerSystemModeler)
        }

        # Clear previous history for fresh simulation
        for name in ps_modelers:
            if name in self._grid_data:
                self._grid_data[name].clear()

        for ts in snapshots:
            for name, modeler in ps_modelers.items():

                # 1. Apply generator schedules
                for gen_name, schedule in gen_schedules.items():
                    if ts in schedule.index:
                        row = schedule.loc[ts]
                        modeler.update_generator(
                            gen_name,
                            p_set=float(row.get("p", 0.0)),
                            q_set=float(row.get("q", 0.0)),
                        )

                # 2. Apply load schedules
                for load_name, schedule in load_schedules.items():
                    if ts in schedule.index:
                        row = schedule.loc[ts]
                        modeler.update_load(
                            load_name,
                            p_set=float(row.get("p", 0.0)),
                            q_set=float(row.get("q", 0.0)),
                        )

                # 3. Solve
                result = modeler.solve()

                # 4. Collect grid state
                state = GridInstance()
                state.timestamp = ts
                state.solve_result = result
                state.bus = modeler.get_bus_data()
                state.gen = modeler.get_generator_data()
                state.load = modeler.get_load_data()
                state.line = modeler.get_line_data()
                state.transformer = modeler.get_transformer_data()

                # 5. Store
                self._grid_data[name].append_state(state)

        return True

    def loaded(self) -> list[str]:
        """
        Return a list of loaded modeler names.

        Returns:
            List of strings containing names of currently loaded modelers.

        Example:
            >>> modeler.loaded()
            ['pypsa', 'wecsim']
        """
        return list(self.modelers.keys())
