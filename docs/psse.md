---
layout: default
title: PSSEInterface
permalink: /psse.html
---

# PSSEInterface

The `PSSEInterface` class is the internal software wrapper that enables WEC-Grid to interact with the PSS®E simulation environment. It provides a high-level, Pythonic interface for initializing simulations, modifying grid elements, running power flow calculations, and extracting time-series data.

---

## Overview

Implemented in `WECGrid/wrappers/psse_wrapper.py`, this class is responsible for:

- **API Initialization**  
  Loads and configures the PSS®E API dynamically using `psspy`, ensuring output is suppressed and the case is correctly parsed. Supports `.raw` and `.sav` case files.

- **Snapshot Architecture**  
  Collects structured snapshots of the full grid state—buses, branches, transformers, generators, etc.—at each simulation step. These are stored for time-series analysis.

- **Generator and Bus Time-Series**  
  Internally builds `p` and `q` dictionaries of generator output and bus power/voltage magnitudes over time, mimicking PyPSA’s data model.

- **Simulation Execution**  
  Runs iterative power flow simulations with or without dynamic load profiles, recording results at each timestep. Output is saved and optionally visualized.

- **WEC Injection Support**  
  Adds new buses, generators, and interconnecting lines for WEC devices. Each WEC instance is given a unique identifier and injected into the PSS®E network.

- **Post-Simulation Analysis**  
  Collects results, performs validations, and updates internal data structures. Optionally visualizes voltage and power behavior across the network.

---