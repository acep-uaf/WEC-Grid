# modeler

Plugin-style architecture for simulation backends. `ModelerManager` dynamically loads and coordinates modelers without tight coupling between them.

## Architecture Layer

**Application Layer** (`ModelerManager`) + **Infrastructure Layer** (concrete backends)

## Contents

| File | Class | Description |
|------|-------|-------------|
| `manager.py` | `ModelerManager` | Dynamic loader, farm propagation, simulation loop |
| `powersystem/base.py` | `PowerSystemModeler`, `SolveResult` | ABC contract for power-system backends |
| `powersystem/pypsa.py` | `PyPSAModeler` | PyPSA implementation with full component CRUD |
| `wecsim/wecsim.py` | `WECSimModeler` | MATLAB engine lifecycle, WEC-Sim execution |

## Key Concepts

### Factory Registry

`ModelerManager` maintains a private `_registry` dict mapping string names to lazy-import factory methods. Calling `load_modeler("pypsa")` triggers the import and instantiation only when needed:

```python
manager.load_modeler("pypsa")   # imports PyPSAModeler, creates instance
manager.load_modeler("wecsim")  # imports WECSimModeler, creates instance
```

### Time Propagation

When `set_time(time)` is called on the manager, the `Time` object is automatically forwarded to every loaded modeler that has a `set_time()` method. New modelers loaded afterward receive it on instantiation.

### Farm Propagation

Farms added via `add_farm()` are:
1. Stored in `manager.farms`
2. Propagated to every loaded power-system modeler via `add_wec_farm()`
3. Automatically forwarded to any modeler loaded later

### Simulation Loop

```
manager.simulate(gen_schedules, load_schedules)
    ├── Convert farms → gen_schedules (via farm.get_power_timeseries)
    └── For each timestep:
        └── For each power-system modeler:
            ├── Apply gen/load schedules
            ├── Solve power flow → SolveResult
            ├── Capture GridInstance
            └── Append to GridData
```

## Usage

```python
from marinegrid.modeler import ModelerManager

manager = ModelerManager()
manager.set_time(study.time)

# Load backends
manager.load_modeler("pypsa")
manager.pypsa.initialize(network)

# Add farms and simulate
manager.add_farm(wec_farm)
manager.simulate()

# Access results
data = manager.get_data("pypsa")
```

## See Also

- [../README.md](../README.md) — Package overview
- [../renewables/README.md](../renewables/README.md) — Farm classes that integrate with modelers
- [../util/README.md](../util/README.md) — `Time`, `GridData`, and `GridInstance`
