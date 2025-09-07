"""Data model for a single Wave Energy Converter device."""

# Standard library
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

# Third-party
import pandas as pd


@dataclass
class WECDevice:
    """Wave Energy Converter with time-series power output.

    Attributes:
        name: Device identifier, usually ``"{model}_{sim_id}_{index}"``.
        dataframe: 5-minute power time series with ``p`` and ``q`` columns
            in per unit.
        bus_location: Bus number for grid connection.
        model: WEC model name (e.g., ``"RM3"``).
        wec_sim_id: Simulation identifier in the database.
    """

    name: str
    dataframe: pd.DataFrame = field(default_factory=pd.DataFrame)
    bus_location: Optional[int] = None
    model: Optional[str] = None
    wec_sim_id: Optional[int] = None

    def __repr__(self) -> str:
        """Return a compact string describing the device."""
        return (
            f"WECDevice:\n"
            f"├─ name: {self.name!r}\n"
            f"├─ model: {self.model!r}\n"
            f"├─ bus_location: {self.bus_location}\n"
            f"├─ sim_id: {self.wec_sim_id}\n"
            f"└─ rows: {len(self.dataframe)}"
        )
