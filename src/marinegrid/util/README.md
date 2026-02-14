# util

Shared utilities for time management, grid state representation, and case file conversion.

## Architecture Layer

**Domain Layer** (`Time`, `GridInstance`, `GridData`) + **Application Layer** (`Converter`)

## Contents

| File | Class(es) | Description |
|------|-----------|-------------|
| `time.py` | `Time` | Simulation timeline with lazy snapshot generation |
| `grid_instance.py` | `GridInstance`, `ComponentSchema` | Single-timestamp grid state container |
| `grid_data.py` | `GridData` | Ordered time-series of GridInstance snapshots |
| `convert.py` | `Converter` | PSS/E RAW → PyPSA network conversion |

## Key Concepts

### Time Management

`Time` provides a single source of truth for the simulation timeline. All backends and farms align to the same set of snapshots.

- Configure via `num_steps` or `end_time` (mutually exclusive)
- Supports any pandas frequency string (`"5min"`, `"1h"`, `"15s"`)
- Snapshots are lazily generated and cached; cache invalidates on parameter change
- Supports iteration, indexing, and containment (`ts in time`)

```python
time = Time()
time.configure(start_time=datetime(2024, 1, 1), num_steps=288, freq="5min")
for ts in time:
    ...
```

### Grid State Snapshots

`GridInstance` stores DataFrames for five component types at a single timestamp:

| Component | ID Column | Key Columns |
|-----------|-----------|-------------|
| `bus` | `bus` | p, q, v_mag, angle_deg, vbase |
| `gen` | `gen` | p, q, p_nom, status |
| `load` | `load` | p, q, status |
| `line` | `line` | p0, p1, loading_pct, s_nom |
| `transformer` | `transformer` | p0, p1, tap_ratio, loading_pct |

All power values (p, q) are in **per-unit on the system MVA base**.

`ComponentSchema` defines required/optional columns and units for each type. DataFrames are validated on assignment.

### Grid History

`GridData` is an ordered collection of `GridInstance` objects. It provides time-series extraction, summary statistics, and voltage/loading violation detection across the simulation window.

### RAW Conversion

`Converter.raw_to_pypsa()` parses PSS/E RAW files using `grg-pssedata` and builds a PyPSA `Network` with buses, branches, generators, loads, two-winding transformers, and shunt impedances.

## See Also

- [../README.md](../README.md) — Package overview
- [../modeler/README.md](../modeler/README.md) — How `Time` and `GridData` are used in simulation
- [../renewables/README.md](../renewables/README.md) — Devices use `Time` for snapshot alignment
