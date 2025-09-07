The **Engine** is the orchestration layer of WEC‑Grid. It coordinates grid modelers (PSS®E / PyPSA), WEC‑Sim runs, time management, persistence to the SQLite database, and plotting. This page explains **how the Engine works conceptually** and then embeds the API reference via **mkdocstrings**, which is generated from your docstrings.

---

## Responsibilities
- **Configuration & Setup**
  - Select and initialize power‑system backends (PSS®E, PyPSA)
  - Connect to / initialize the WEC‑Grid SQLite database (`WECGridDB`)
  - Set the simulation timeline (`WECGridTime`)
- **Model Management**
  - Load a grid case (IEEE test systems or custom `.RAW`)
  - Apply one or more **WEC farms** at target buses; resolve device metadata from the DB
- **Simulation Orchestration**
  - For each snapshot: update generator/load setpoints, ask each backend to solve power flow, collect snapshots into a standardized **`GridState`**
  - Optionally persist results to the DB and trigger comparisons/plots
- **Visualization**
  - Provide a single plotting surface (`WECGridPlot`) that works across modelers

---

## Functionality 

1. **Create** an engine and (optionally) set the database path
2. **Load**: initialize one or more power‑system modelers (PSS®E/PyPSA)
3. **Case**: load a grid case into each enabled modeler
4. **Apply WEC**: attach a WEC farm to a bus (pull cached WEC‑Sim results or trigger runs via `WECSimRunner`)
5. **Simulate**: run the time‑series (quasi‑steady‑state) loop; collect `GridState` snapshots
6. **Persist / Plot**: save results to DB; generate time‑series, comparisons, and SLDs

---

## Key Concepts

- **`PowerSystemModeler` (ABC)**  
  An abstract interface implemented by `PSSEModeler` and `PyPSAModeler`. The Engine only calls the standard methods (e.g., `init_api()`, `add_wec_farm()`, `solve_powerflow()`, `take_snapshot()`), which keeps user experience consistent across backends.

- **`GridState`**  
  A standardized container for results. It defines consistent DataFrame schemas for `bus`, `gen`, `line`, and `load` snapshots, plus wide‑format time‑series dictionaries (`*_t`). This enables cross‑backend comparisons and unified plotting.

- **`WECFarm` / `WECDevice`**  
  A farm aggregates one or more WEC devices. The farm‑to‑grid mapping is **one generator per farm** (not per device). Device‑level time‑series are downsampled to the grid resolution and aggregated.

- **`WECGridDB`**  
  Encapsulates all DB operations (initialize schema, save simulations, query WEC‑Sim runs, etc.). The Engine delegates all persistence here.

- **`WECGridTime`**  
  Stores start/end/resolution, and exposes `update()` to adjust the simulation window.

- **`WECGridPlot`**  
  Unified plotting API for per‑bus, per‑generator, and backend‑comparison plots.

---
<!-- 
## API Reference

::: wecgrid.engine.Engine -->
