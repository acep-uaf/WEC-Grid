**WEC-Grid** is an open-source software framework that bridges **Wave Energy Converter (WEC) modeling** and **electrical power system modeling**. It enables researchers and practitioners to perform quasi-steady-state integration studies, capturing interactions between hydrodynamic WEC simulations (via WEC-Sim) and grid analysis tools (PSS®E and PyPSA).  

The system is modular, extensible, and built to support flexibility across grid scenarios, farm layouts, and solver configurations. It provides standardized APIs, a relational database backend, and visualization capabilities.

---

## Architecture Overview

At the highest level, **WEC-Grid** employs a **bridge pattern**:  
- **Engine**: central orchestrator that synchronizes simulation timeline, solver calls, WEC injections, and result management.  
- **Modelers**: encapsulated wrappers for **PSS®E**, **PyPSA**, and **WEC-Sim**, providing a uniform API despite differing underlying software.  
- **Utilities**: database, time, and plotting modules that manage persistence, scheduling, and visualization.  
- **WEC Farm and Devices**: abstractions for configuring farms of WEC units, mapping them into the grid.

<!-- <div style="clear: both; text-align: center;">
  <img src="../assets/WEC_Grid_workflow.png" alt="Workflow Diagram" style="width: 100%; height: auto;">
</div> -->

---
## Class Design

The UML class diagram highlights the modular structure:

- **Engine**: entry point API, exposes `load()`, `apply_wec()`, `simulate()`, and manages solvers.  
- **Modelers**
    + `PowerSystemModeler` (abstract base) with implementations for `PSSERunner` and `PyPSARunner`.
    + `WECsimRunner` interfaces with MATLAB/WEC-Sim.  
- **WECFarm / WECDevice**: represent farms of WECs, their bus locations, and simulation identifiers.  
- **Utilities**:  
    + `WECGridDB` for SQLite persistence,  
    + `WECGridTime` for aligned simulation timesteps,  
    + `WECGridPlot` for visualization.  

<div style="clear: both; text-align: center;">
  <img src="../assets/WEC-Grid_uml_class.png" alt="UML Class Diagram" style="width: 100%; height: auto;">
</div>

---

## Sequence of Operations

A typical user workflow:  
1. Instantiate `Engine` and configure database path.  
2. Load power system cases (IEEE test systems or custom RAW).  
3. Apply WEC farms with size, location, and model.  
4. Run **WEC-Sim** simulations or pull cached results.  
5. Synchronize and run power flow analysis via **PSS®E** and/or **PyPSA**.  
6. Store results in database and generate plots.  

<div style="clear: both; text-align: center;">
  <img src="../assets/WEC-GRID_uml_sequence.png" alt="Sequence Diagram" style="width: 100%; height: auto;">
</div>

---

## Database Schema

Simulation results are stored in an **SQLite3 database** for reproducibility and cross-solver benchmarking. The schema includes:

- **grid_simulations**: metadata for grid-level runs.  
- **wec_simulations** and **wec_power_results**: WEC-Sim metadata and timeseries outputs.  
- **pypa/psse_bus, load, line, generator_results**: solver-specific simulation results.  
- **wec_integrations**: mapping between grid and WEC runs.  

This schema supports efficient querying, comparison, and long-term storage.

<div style="clear: both; text-align: center;">
  <img src="../assets/database_diagram.png" alt="Database Schema" style="width: 100%; height: auto;">
</div>

---

## Key Features

- **Unified API**: abstracting away solver differences (`simulate()`, `apply_wec()`, `compare_results()`).  
- **Cross-solver comparisons**: results can be validated between PSS®E and PyPSA.  
- **Visualization**: time-series plots, single-line diagrams, and cross-platform comparisons.  
- **Reproducibility**: simulation caching and SQL persistence.  
- **Scalability**: supports microgrids to large systems, configurable timestep and scenario setup.  

---