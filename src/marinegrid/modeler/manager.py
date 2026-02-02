"""
Modeler manager for Marine-Grid.

File: src/marinegrid/modeler/manager.py
"""

# Standard library
from typing import Dict, Any

# Third-party


# Local


class ModelerManager:
    """
    Unified interface for managing multiple backend modelers.

    Provides dynamic loading and management of different modeler types
    (power system, WEC simulation, etc.). Enables plugin-style architecture
    where modelers can be loaded on-demand without tight coupling.

    Attributes:
        modelers: Dictionary of instantiated modeler instances keyed by name.

    Example:
        >>> manager = ModelerManager()
        >>> pypsa = manager.load_modeler("pypsa", network=my_network)
        >>> wecsim = manager.load_modeler("wecsim")
        >>> manager.loaded()
        ['pypsa', 'wecsim']
    """

    def __init__(self):
        """
        Initialize the ModelerManager.

        Sets up the internal registry of available modeler factories
        and prepares storage for instantiated modelers.
        """
        # Class objects
        
        # Class attributes
        self.modelers: Dict[str, Any] = {}  # Store instantiated modelers
        self._registry = {
            "pypsa": self._load_pypsa,
            "wecsim": self._load_wecsim,
            # "pandapower": self._load_pandapower,  # Future implementation
        }
        
    
    def load_modeler(self, name: str, **kwargs):
        """
        Load and attach a backend modeler by name.
        
        Dynamically imports and instantiates the requested modeler class,
        then registers it in both the modelers dict and as a direct attribute.
        
        Args:
            name: Name of the modeler to load (e.g., "pypsa", "wecsim").
            **kwargs: Additional keyword arguments passed to modeler constructor.
        
        Returns:
            The instantiated modeler object.
        
        Raises:
            TypeError: If name is not a string.
            ValueError: If the modeler name is not supported.
        
        Example:
            >>> modeler.load_modeler("pypsa", network=my_network)
            >>> modeler.pypsa  # Access via attribute
            >>> modeler.modelers["pypsa"]  # Access via dict
        """
        if not isinstance(name, str):
            raise TypeError("modeler must be a string")
        
        key = name.lower()
        try:
            factory = self._registry[key]
        except KeyError as exc:
            raise ValueError(f"Unsupported modeler '{name}', supported: {list(self._registry)}") from exc
        
        cls = factory()
        inst = cls(**kwargs)
        self.modelers[key] = inst  # access via self.modelers["pypsa"]
        setattr(self, key, inst)   # enables s.pypsa / s.pandapower
        return inst
        
        
    def _load_pypsa(self):
        """
        Factory method for loading PyPSA modeler class.
        
        Returns:
            PyPSAModeler class (not instantiated).
        """
        from .powersystem.pypsa import PyPSAModeler
        return PyPSAModeler
    
    # def _load_pandapower(self):
    #     """
    #     Factory method for loading PandaPower modeler class.
    #     
    #     NOT YET IMPLEMENTED
    #     
    #     Returns:
    #         PandaPowerModeler class (not instantiated).
    #     """
    #     from .powersystem.pandapower import PandaPowerModeler
    #     return PandaPowerModeler
    
    def _load_wecsim(self):
        """
        Factory method for loading WEC-Sim modeler class.
        
        Returns:
            WECSimModeler class (not instantiated).
        """
        from .wecsim.wecsim import WECSimModeler
        return WECSimModeler
        
        
    def simulate(self):
        """
        Execute simulation across all loaded power system modelers.
        
        Iterates through all loaded modelers and calls their simulate method.
        This allows coordinated execution of multi-modeler simulations.
        """
        pass
    
    
    def loaded(self):
        """
        Return a list of loaded modeler names.
        
        Returns:
            List of strings containing names of currently loaded modelers.
        
        Example:
            >>> modeler.loaded()
            ['pypsa', 'wecsim']
        """
        return list(self.modelers.keys())
    
    