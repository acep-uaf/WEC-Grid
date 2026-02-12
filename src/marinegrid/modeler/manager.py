"""
Modeler manager for Marine-Grid.

File: src/marinegrid/modeler/manager.py
"""

# Standard library
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

# Third-party
import pandas as pd

# Local
if TYPE_CHECKING:
    from ..util.time import Time
    from ..renewables.wec import WECFarm


class ModelerManager:
    """
    Unified interface for managing multiple backend modelers.

    Provides dynamic loading and management of different modeler types
    (power system, WEC simulation, etc.). Enables plugin-style architecture
    where modelers can be loaded on-demand without tight coupling.

    Manages renewable energy farms and coordinates their integration with
    power system modelers during simulation.

    Attributes:
        modelers: Dictionary of instantiated modeler instances keyed by name.
        farms: List of registered renewable energy farms.
        time: Reference to the central Time object for simulation timeline.

    Example:
        >>> manager = ModelerManager()
        >>> manager.set_time(study.time)
        >>> pypsa = manager.load_modeler("pypsa")
        >>> pypsa.initialize(network)
        >>> manager.add_farm(wec_farm)
        >>> manager.simulate()  # Updates farm power at each timestep
    """

    def __init__(self):
        """
        Initialize the ModelerManager.

        Sets up the internal registry of available modeler factories
        and prepares storage for instantiated modelers and farms.
        """
        # Class objects
        self._time: Optional["Time"] = None

        # Class attributes
        self.modelers: Dict[str, Any] = {}
        self.farms: List["WECFarm"] = []
        self._registry = {
            "pypsa": self._load_pypsa,
            "wecsim": self._load_wecsim,
            # "pandapower": self._load_pandapower,  # Future implementation
        }

    def __repr__(self) -> str:
        """Return a formatted summary of the modeler manager state."""
        loaded = ", ".join(self.modelers.keys()) if self.modelers else "None"
        farm_count = len(self.farms)

        if self._time is not None:
            time_str = f"{len(self._time)} steps @ {self._time.freq}"
        else:
            time_str = "Not set"

        return (
            f"ModelerManager:\n"
            f"├─ Loaded: {loaded}\n"
            f"├─ Farms: {farm_count}\n"
            f"└─ Time: {time_str}"
        )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def time(self) -> Optional["Time"]:
        """Get the central Time object for simulation timeline."""
        return self._time

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
            TypeError: If time is not a Time instance.
        """
        self._time = time
        # Propagate time to all loaded modelers
        for modeler in self.modelers.values():
            if hasattr(modeler, "set_time"):
                modeler.set_time(time)

    # -------------------------------------------------------------------------
    # Farm Management
    # -------------------------------------------------------------------------

    def add_farm(self, farm: "WECFarm", add_to_network: bool = True) -> bool:
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
        self.farms.append(farm)

        # Propagate farm to ALL loaded power system modelers
        if add_to_network:
            for name, modeler in self.modelers.items():
                # Check if it's a power system modeler (has add_wec_farm method)
                if hasattr(modeler, "add_wec_farm"):
                    modeler.add_wec_farm(farm)

        return True

    def remove_farm(self, farm: "WECFarm") -> bool:
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
        then registers it in both the modelers dict and as a direct attribute.
        If a Time object is set, it will be automatically passed to the modeler.

        Args:
            name: Name of the modeler to load (e.g., "pypsa", "wecsim").
            **kwargs: Additional keyword arguments passed to modeler constructor.

        Returns:
            The instantiated modeler object.

        Raises:
            TypeError: If name is not a string.
            ValueError: If the modeler name is not supported.

        Example:
            >>> modeler.load_modeler("pypsa")
            >>> modeler.pypsa  # Access via attribute
            >>> modeler.modelers["pypsa"]  # Access via dict
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
        setattr(self, key, inst)

        # Pass time reference to the modeler if available
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
        gen_schedules: Optional[Dict[str, Union[pd.Series, pd.DataFrame]]] = None,
        load_schedules: Optional[Dict[str, Union[pd.Series, pd.DataFrame]]] = None,
    ) -> bool:
        """
        Execute simulation across all loaded power system modelers.

        For each timestep:
        1. Updates generator setpoints from gen_schedules and registered farms
        2. Updates load setpoints from load_schedules
        3. Solves power flow
        4. Captures grid state

        Uses the central Time object's snapshots as the simulation timeline.

        Args:
            gen_schedules: Dictionary mapping generator names/IDs to time series.
                Keys are generator identifiers (name or ID).
                Values are Series (p only) or DataFrame (p, q columns).
                Index should be timestamps matching time.snapshots.
                Power values in per-unit on system MVA base.
            load_schedules: Dictionary mapping load names/IDs to time series.
                Same format as gen_schedules.

        Returns:
            True if all modelers completed simulation successfully.

        Raises:
            RuntimeError: If no Time object is set.

        Example:
            >>> manager.load_modeler("pypsa")
            >>> manager.pypsa.initialize(network)
            >>> # Add a WEC farm (converted to gen schedule internally)
            >>> manager.add_farm(wec_farm)
            >>> # Or pass explicit schedules
            >>> manager.simulate(
            ...     gen_schedules={"G1": gen_power_series},
            ...     load_schedules={"LD1": load_power_df}
            ... )
        """
        if self._time is None:
            raise RuntimeError(
                "No Time object set. Call set_time() first or use Study.run()."
            )

        # Build combined generator schedules from farms + explicit schedules
        combined_gen_schedules = dict(gen_schedules) if gen_schedules else {}

        # Convert registered farms to generator schedules
        for farm in self.farms:
            gen_name = getattr(farm, "gen_name", None)
            if gen_name:
                # Get farm power time series as DataFrame
                farm_schedule = farm.get_power_timeseries()
                if farm_schedule is not None and not farm_schedule.empty:
                    combined_gen_schedules[gen_name] = farm_schedule

        success = True

        # Get power system modelers
        power_system_modelers = []
        for name, modeler in self.modelers.items():
            # Check if it's a power system modeler (has simulate method and network)
            if hasattr(modeler, "simulate") and hasattr(modeler, "network"):
                power_system_modelers.append((name, modeler))

        # Run simulation on each power system modeler with schedules
        for name, modeler in power_system_modelers:
            result = modeler.simulate(
                gen_schedules=combined_gen_schedules if combined_gen_schedules else None,
                load_schedules=load_schedules,
            )
            if result is False:
                success = False

        return success

    def loaded(self) -> List[str]:
        """
        Return a list of loaded modeler names.

        Returns:
            List of strings containing names of currently loaded modelers.

        Example:
            >>> modeler.loaded()
            ['pypsa', 'wecsim']
        """
        return list(self.modelers.keys())
