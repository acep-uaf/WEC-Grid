---
layout: default
title: PYPSAInterface
permalink: /pypsa.html
---

# PYPSAInterface

The `PYPSAInterface` class provides WEC-Grid with an internal wrapper around PyPSA, enabling power flow simulations and network manipulation for wave energy converter (WEC) studies. It bridges the parsed PSS®E case data with PyPSA’s data model, builds a valid network structure, and executes simulation workflows.

---

## Overview

Implemented in `WECGrid/pypsa/pypsa_wrapper.py`, this class supports:

- **Raw File Parsing and Import**  
  Uses the GRG parser to convert a PSS®E `.raw` file into a PyPSA `Network` object. Converts buses, branches, generators, loads, and transformers into physical units appropriate for PyPSA.

- **Network Initialization**  
  Builds buses, lines, loads, generators, and shunts from the parsed data and initializes control and operating points.

- **Power Flow Execution**  
  Runs power flow calculations using PyPSA’s solver and silently handles convergence logging. Captures snapshots of voltage, power, and network states for each simulation step.

- **WEC Integration**  
  Supports injecting WEC generators into the network by creating a new bus, connecting it to an existing bus via a line, and attaching WEC generators with appropriate parameters.

- **Load Profile and WEC Assignment**  
  Applies realistic time-varying load profiles and WEC generation curves for each simulation timestep.

- **Visualization**  
  Interfaces with `PyPSAVisualizer` for generating plots of voltage, power, and comparison metrics across time.

---