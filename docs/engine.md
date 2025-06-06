---
layout: default
title: WECGridEngine
permalink: /engine.html
---

# WECGridEngine

The `WECGridEngine` class is the central controller of the WEC-Grid framework. It manages the initialization of the simulation environment, coordinates the interaction between external power system solvers (PSS®E and PyPSA), integrates wave energy converter (WEC) devices, and handles simulation output and time-series data storage. It serves as the main entry point for most users and scripts.

---

## Overview

This class is implemented in `WECGrid/core.py` and is designed to:

- **Initialize Simulation Setup**  
  The engine is initialized with a power system “case” file, such as a PSS®E RAW file. It sets up a uniform simulation timespan using 5-minute intervals, producing a fixed number of time steps (snapshots) for the entire simulation day. It also prepares internal state tracking and ensures simulation directories and databases are ready.

- **Connect Software Wrappers**  
  Users can selectively enable one or more supported solvers. Internally, `WECGridEngine` loads wrapper classes for PSS®E and PyPSA (`PSSEInterface` and `PYPSAInterface`). Each wrapper is responsible for adapting the engine's commands to the native APIs of these simulators. When both tools are active, data consistency operations (e.g., reactive power limits) are enforced.

- **Apply WEC Devices**  
  WEC farms can be instantiated on a target bus with a user-specified size. Each farm comprises multiple `WEC` instances, all initialized with shared configuration parameters (e.g., wave height, period). Devices are automatically injected into each solver, and the engine tracks their placement for downstream operations.

- **Run Load Profile Simulations**  
  To simulate realistic demand, the engine can generate a double-peaking load shape (with morning and evening peaks). This shape is scaled per load object (in PyPSA) or per bus (in PSS®E) and stored as a full time-series. These profiles are used to test dynamic behavior across the grid under realistic daily conditions.

- **Run Simulations**  
  Once all systems are configured, the engine can execute full simulations in either or both solvers. It supports toggling load curve usage and automatic plotting of results. When both solvers are active, post-run comparisons (e.g., RMSE of voltage magnitudes or generator power) are optionally generated.

- **Save and Retrieve Results**  
  Results from each run are stored in a local SQLite database. The engine inserts data into `sim_runs`, `bus_timeseries`, and `gen_timeseries` tables. This storage supports auditing, future analysis, and reproducibility. Past simulations can be listed and selectively reloaded for further comparison or visualization.

---