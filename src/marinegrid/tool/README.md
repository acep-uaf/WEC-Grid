# tool

Infrastructure Layer services for persistent storage, visualization, and post-simulation analysis.

## Architecture Layer

**Infrastructure Layer** — external system interfaces (SQLite, matplotlib).

## Contents

| File | Class | Status | Description |
|------|-------|--------|-------------|
| `database.py` | `Database` | Implemented | SQLite interface for WEC-Sim results and grid state |
| `plot.py` | `Plot` | Stub | Visualization of simulation results |
| `analysis.py` | `Analysis` | Stub | Post-simulation metrics and statistics |

## Key Concepts

### Database Configuration

The database path is resolved in priority order:

1. `MARINEGRID_DB_PATH` environment variable
2. User config file at `<platform-config>/marinegrid/database_config.json`
3. Explicit call to `database.set_database_path()`

Once configured, the path persists across sessions via the JSON config file.

### Database Schema

The database stores three categories of data:

- **WEC simulations** — metadata (model type, wave parameters) and time-series power results
- **Grid simulations** — metadata (case name, sbase, time range) and per-component results
- **WEC integrations** — mapping between grid simulations and WEC farms

### Plot (Stub)

Planned visualization methods:

- `gen()` — Generator dispatch time series
- `bus()` — Bus voltage profiles
- `load()` — Load consumption curves
- `line()` — Line loading and power flow
- `sld()` — Single-line diagram via NetworkX
- `wec_analysis()` — 3-panel WEC farm analysis

### Analysis (Stub)

Planned analysis capabilities:

- Voltage stability indices
- Congestion detection (overloaded lines/transformers)
- Network loss analysis
- Statistical summaries of time-series GridData

## Usage

```python
# Database
study.database.set_database_path("path/to/marinegrid.db")
results = study.database.query("SELECT * FROM wec_simulations", return_type="df")

# Convenience queries
wec_sims = study.database.get_wec_simulations()
grid_sims = study.database.get_grid_simulations()
```

## See Also

- [../README.md](../README.md) — Package overview
- [../renewables/README.md](../renewables/README.md) — `WECFarm` uses `Database` to load WEC-Sim data
- [../modeler/README.md](../modeler/README.md) — `WECSimModeler` stores results in `Database`
