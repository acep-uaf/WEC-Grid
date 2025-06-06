---
layout: default
title: WEC Wrapper
permalink: /wec-wrapper.html
---

# WEC Wrapper

The `WEC` class provides a high-level interface for managing Wave Energy Converter (WEC) devices within the WEC-Grid framework. It automates the connection between WEC-Sim and the WEC-Grid simulation engine, manages database interactions, and ensures seamless integration of WEC output into power system simulations.

---

## Overview

This component is implemented in `WECGrid/wec/wec_class.py` and is responsible for:

- **WEC Initialization**  
  Each instance of the `WEC` class is associated with a unique simulation ID, bus location, and model configuration. Upon initialization, the class checks if previous WEC-Sim results exist in the database. If not, it triggers a new simulation.

- **WEC-Sim Execution**  
  Automatically launches a MATLAB engine and runs WEC-Sim using parameters such as wave height, period, duration, and timestep. The appropriate simulation script is selected based on the WEC model.

- **Database Storage**  
  After simulation, results are stored in an SQLite table named `WEC_output_{sim_id}` and include power output over time.

- **Snapshot Management**  
  Simulation outputs are timestamped using the shared simulation clock defined in the `WECGridEngine`, allowing integration with PSS®E and PyPSA snapshots.

- **Reuse and Caching**  
  If WEC data already exists in the database for a given simulation ID, it is reused instead of rerunning MATLAB.

This wrapper simplifies the interface between WEC-Sim and the rest of the WEC-Grid framework, enabling repeatable, modular wave energy simulation pipelines.