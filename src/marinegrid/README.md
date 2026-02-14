# marinegrid

Marine-Grid is a Python library for simulating the integration of marine renewable energy devices with power grid simulators. It bridges WEC-Sim (MATLAB-based hydrodynamic simulator) with power system backends like PyPSA.

## Architecture

The package is organized into three layers:

```
┌─────────────────────────────────────────────────┐
│              Application Layer                  │
│   Study · ModelerManager · Converter            │
├─────────────────────────────────────────────────┤
│               Domain Layer                      │
│   RenewableDevice · WECDevice · WECFarm         │
│   GridInstance · GridData · Time · SolveResult   │
├─────────────────────────────────────────────────┤
│            Infrastructure Layer                 │
│   PyPSAModeler · WECSimModeler · Database       │
│   Plot (stub) · Analysis (stub)                 │
└─────────────────────────────────────────────────┘
```

| Layer | Purpose |
|-------|---------|
| **Application** | Orchestrates simulation workflow, manages modeler lifecycle |
| **Domain** | Core business objects — devices, farms, grid state, time |
| **Infrastructure** | External system interfaces — solvers, MATLAB, SQLite |

## Package Map

| Directory | Contents | Key Classes |
|-----------|----------|-------------|
| [`modeler/`](modeler/) | Plugin architecture and solver backends | `ModelerManager`, `PyPSAModeler`, `WECSimModeler` |
| [`renewables/`](renewables/) | Device models and farm containers | `RenewableDevice`, `WECFarm`, `WindDevice` |
| [`util/`](util/) | Simulation timeline, grid state, conversion | `Time`, `GridInstance`, `GridData`, `Converter` |
| [`tool/`](tool/) | Database, plotting, analysis | `Database`, `Plot`, `Analysis` |

## Quick Start

```python
from marinegrid import Study
from marinegrid.util import Converter
from datetime import datetime

study = Study()
study.case_path = "path/to/case.RAW"

study.time.configure(
    start_time=datetime(2024, 1, 1),
    num_steps=24,
    freq="1h",
)

converter = Converter()
network = converter.raw_to_pypsa(study.case_path)

study.modeler.load_modeler("pypsa")
study.modeler.pypsa.initialize(network)
study.modeler.simulate()

results = study.modeler.get_data("pypsa")
```

## Entry Point

The primary entry point is the `Study` class exported from `marinegrid/__init__.py`. All other components are accessed through `Study` attributes or imported directly from their subpackages.

## See Also

- [CLAUDE.md](../../../CLAUDE.md) — Full project documentation and implementation status
- [modeler/README.md](modeler/README.md) — Plugin architecture details
- [renewables/README.md](renewables/README.md) — Device and farm hierarchy
- [util/README.md](util/README.md) — Time, grid state, and conversion utilities
- [tool/README.md](tool/README.md) — Database and analysis tools
