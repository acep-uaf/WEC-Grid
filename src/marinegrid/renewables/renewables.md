# renewables

Domain Layer classes for renewable energy devices and their farm containers.

## Architecture Layer

**Domain Layer** — core business objects with no external dependencies beyond pandas/numpy.

## Contents

| File | Class(es) | Description |
|------|-----------|-------------|
| `base.py` | `RenewableDevice` | ABC for all device types |
| `farm.py` | `RenewableEnergyFarm` | Generic mixed-device farm container |
| `wec.py` | `WECDevice`, `WECFarm` | Wave energy converter with database loading |
| `wind.py` | `WindDevice` | Wind turbine data container |
| `solar.py` | `SolarDevice` | Solar panel data container |
| `tidal.py` | `TidalDevice` | Tidal generator data container |
| `storage.py` | `StorageDevice` | Energy storage data container |

## Key Concepts

### Device Hierarchy

```
RenewableDevice (ABC)
├── WECDevice      — per-unit power from WEC-Sim
├── WindDevice     — wind turbine output
├── SolarDevice    — solar panel output
├── TidalDevice    — tidal generator output
└── StorageDevice  — charge/discharge profiles
```

Every device stores time-series data in a `data` DataFrame indexed by timestamp with `p` and `q` columns in per-unit on the system MVA base.

### Farm Hierarchy

```
RenewableEnergyFarm
└── WECFarm  — adds database loading, downsampling, scaling
```

`RenewableEnergyFarm` is a generic container that can hold mixed device types. It computes aggregate power via `power_at_snapshot()` and `get_power_timeseries()`.

`WECFarm` extends the base with:
- Automatic loading of WEC-Sim results from the `Database`
- Downsampling from sub-second WEC-Sim resolution to the grid timestep
- Per-unit conversion (Watts → MW → per-unit on sbase)
- Device scaling via `size` and `scaling_factor`

### Per-Unit Convention

All power values stored on devices and returned by farms are in **per-unit on the system MVA base** (`sbase`, typically 100 MVA). Conversion from physical units happens in `WECFarm._prepare_farm()`.

## Usage

```python
from marinegrid.renewables import WECFarm, WindDevice

# WEC farm loaded from database
farm = WECFarm(
    farm_name="Humboldt_WEC",
    database=study.database,
    time=study.time,
    wec_sim_id=1,
    bus_location=100,
    connecting_bus=1,
    size=10,
)

# Generic farm with mixed devices
from marinegrid.renewables import RenewableEnergyFarm
hybrid = RenewableEnergyFarm(farm_name="Hybrid", bus_location=200)
hybrid.add_device(wind_device)
hybrid.add_device(solar_device)
total_p = hybrid.power_at_snapshot(timestamp)
```

## See Also

- [../README.md](../README.md) — Package overview
- [../modeler/README.md](../modeler/README.md) — How farms are propagated to modelers
- [../util/README.md](../util/README.md) — `Time` class that drives snapshot alignment
