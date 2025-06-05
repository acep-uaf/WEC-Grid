from .core import WECGridEngine as Engine

__version__ = "0.1.0"

# Software interfaces
from .psse.psse_interface import PSSEInterface
from .pypsa.pypsa_interface import PYPSAInterface


from .cec.cec_class import CEC
from .database_handler.connection_class import SQLiteConnection
from .utilities.util import dbQuery, read_paths
from .viz.psse_viz import PSSEVisualizer
from .viz.pypsa_viz import PyPSAVisualizer
from .wec.wec_class import WEC

# # WecGrid/__init__.py

# # Import the WecGrid class from core.py and explicitly expose it
# from .core import WecGrid as WecGridClass

# # Assign the class to the package namespace
# WecGrid = WecGridClass  # Now `WecGrid` at the package level is the class

# # Define what is exported when `from WecGrid import *` is used
# __all__ = ["WecGrid"]

# # Add version information
# __version__ = "0.1.0"

# # Import other submodules if needed (optional)
# from .PSSe.psse_wrapper import PSSeWrapper
# from .cec.cec_class import CEC
# from .database_handler.connection_class import SQLiteConnection
# from .pyPSA.pypsa_wrapper import pyPSAWrapper
# from .utilities.util import dbQuery, read_paths
# from .viz.psse_viz import PSSEVisualizer
# from .viz.pypsa_viz import PyPSAVisualizer
# from .wec.wec_class import WEC
