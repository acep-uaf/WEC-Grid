# IBR Proxy Method for PSS/E Dynamic Simulation

**Author:** WEC-GRID Research Team  
**Date:** November 2025  
**Version:** 1.0

---

## Overview

This document describes a methodology for integrating Inverter-Based Resources (IBRs) into PSS/E dynamic simulations using a **proxy load approach**. This enables co-simulation with external models (FMUs, WEC-Sim, etc.) where the IBR behavior is computed outside of PSS/E and injected at each time step.

### Key Concept

Instead of using PSS/E's built-in IBR models, we:
1. Create a **load element** at the point of interconnection
2. Update the load's P and Q values at each simulation time step
3. Use **negative load values** to represent generation (power injection)

This approach allows any external model to control the IBR's power output while PSS/E handles the grid dynamics (voltage, frequency, generator response).

### Reference

Based on the NREL co-simulation framework:
- **Paper:** [Grid Integration of Marine Energy](https://docs.nrel.gov/docs/fy25osti/91114.pdf)
- **Code:** `cpds_cosim/machine_1/Transmission/TransmissionSim.py`

---

## Method Comparison

| Approach | Files Required | Pros | Cons |
|----------|---------------|------|------|
| **Snapshot Method** | `.cnv` + `.snp` | Pre-initialized, fast startup | Requires offline preparation |
| **RAW/DYR Method** | `.raw` + `.dyr` | More flexible, standard formats | Requires initialization step |

---

## Part 1: Using RAW and DYR Files (Recommended)

This approach uses standard PSS/E file formats and is more portable.

### Required Files

| File | Description | How to Obtain |
|------|-------------|---------------|
| `.raw` | Power flow case (buses, loads, generators, branches) | Export from PSS/E GUI or create programmatically |
| `.dyr` | Dynamic model data (generator models, exciters, governors) | Export from PSS/E GUI or create manually |

### Step 1: Load Power Flow Case

```python
import psspy

# Initialize PSS/E
psspy.psseinit(1000)

# Load the RAW file (power flow data)
raw_file = "path/to/case.raw"
ierr = psspy.read(0, raw_file)
print(f"Load RAW file: ierr = {ierr}")  # 0 = success
```

### Step 2: Solve Initial Power Flow

```python
# Solve power flow to establish initial conditions
ierr = psspy.fnsl([0, 0, 0, 1, 1, 0, 99, 0])
print(f"Power flow solution: ierr = {ierr}")

# Verify convergence
ierr, solved = psspy.solved()
print(f"Converged: {solved == 0}")
```

### Step 3: Load Dynamic Models

```python
# Load dynamic model data
dyr_file = "path/to/models.dyr"
ierr = psspy.dyre_new([1, 1, 1, 1], dyr_file, "", "", "")
print(f"Load DYR file: ierr = {ierr}")
```

### Step 4: Convert and Initialize Dynamics

```python
# Convert generators for dynamic simulation
ierr = psspy.cong(0)  # Convert generators
print(f"Convert generators: ierr = {ierr}")

# Order network for dynamics
ierr = psspy.ordr(0)  # Order network
print(f"Order network: ierr = {ierr}")

# Factorize network
ierr = psspy.fact()  # Factorize
print(f"Factorize: ierr = {ierr}")

# Initialize dynamic simulation
ierr = psspy.tysl(0)  # Time-step initialization
print(f"Initialize dynamics: ierr = {ierr}")
```

### Step 5: Set Up Output Channels

```python
# Add voltage channels for all buses
psspy.chsb(0, 1, [-1, -1, -1, 1, 13, 0])

# Add frequency channels for all buses
psspy.chsb(0, 1, [-1, -1, -1, 1, 12, 0])

# Set up simulation monitoring
psspy.set_osscan(1, 0)
psspy.set_vltscn(1, 1.2, 0.5)
```

### Step 6: Start Dynamic Simulation

```python
# Output file for results
out_file = "path/to/output.out"

# Initialize dynamic simulation
# [0, 0] = normal start, .out format
ierr = psspy.strt_2([0, 0], out_file)
print(f"Start dynamics: ierr = {ierr}")

# Run flat start (1 second stabilization)
ierr = psspy.run(0, 1.0, 1, 1, 0)
print(f"Flat start: ierr = {ierr}")
```

---

## Part 2: Adding an IBR Proxy Load

If your case doesn't have a load at the desired bus, you need to add one.

### Option A: Add Load to Existing Bus

```python
def add_ibr_proxy_load(bus_number, load_id='99'):
    """
    Add a proxy load to an existing bus for IBR injection.
    
    Parameters:
    -----------
    bus_number : int
        The bus number where IBR will connect
    load_id : str
        Unique identifier for the load (default '99' to avoid conflicts)
    
    Returns:
    --------
    int : Error code (0 = success)
    """
    
    # Load data parameters
    # INTGAR: [I, STATUS, AREA, ZONE, OWNER, SCALE, INTRPT, DESSION, LOESSION]
    intgar = [
        bus_number,  # I - Bus number
        1,           # STATUS - In-service (1) or out-of-service (0)
        1,           # AREA - Area number
        1,           # ZONE - Zone number  
        1,           # OWNER - Owner number
        1,           # SCALE - Scalable flag
        0,           # INTRPT - Interruptible flag
        0,           # Not used
        0            # Not used
    ]
    
    # REALAR: [PL, QL, IP, IQ, YP, YQ, OWNER1, ...]
    # Start with zero load - will be updated during simulation
    realar = [
        0.0,  # PL - Active power (MW) - constant power component
        0.0,  # QL - Reactive power (Mvar) - constant power component
        0.0,  # IP - Active current component
        0.0,  # IQ - Reactive current component
        0.0,  # YP - Active admittance component
        0.0,  # YQ - Reactive admittance component
    ]
    
    # Add the load using load_data_6
    ierr = psspy.load_data_6(
        bus_number,    # Bus number
        load_id,       # Load ID (string, 1-2 characters)
        intgar,        # Integer array
        realar         # Real array
    )
    
    if ierr == 0:
        print(f"✓ Added IBR proxy load '{load_id}' at bus {bus_number}")
    else:
        print(f"✗ Error adding load: ierr = {ierr}")
    
    return ierr
```

### Option B: Add New Bus and Load (for offshore connection)

```python
def add_ibr_bus_and_load(new_bus_number, connect_to_bus, bus_name="IBR_BUS", 
                          line_r=0.01, line_x=0.1, line_b=0.02):
    """
    Add a new bus for IBR connection with transmission line to existing grid.
    
    Parameters:
    -----------
    new_bus_number : int
        Number for the new IBR bus
    connect_to_bus : int
        Existing bus to connect to
    bus_name : str
        Name for the new bus
    line_r, line_x, line_b : float
        Transmission line parameters (pu on system base)
    """
    
    # Get base kV from the connection bus
    ierr, base_kv = psspy.busdat(connect_to_bus, 'BASE')
    
    # Add new bus
    # bus_data_4(I, INTGAR, REALAR, NAME)
    ierr = psspy.bus_data_4(
        new_bus_number,
        [1, 1, 1, 1],           # INTGAR: [IDE, AREA, ZONE, OWNER] - Type 1 = load bus
        [base_kv, 1.0, 0.0, 1.1, 0.9, 1.1, 0.9],  # REALAR: [BASKV, VM, VA, NVHI, NVLO, EVHI, EVLO]
        bus_name
    )
    print(f"Add bus {new_bus_number}: ierr = {ierr}")
    
    # Add transmission line connecting new bus to grid
    # branch_data_3(I, J, CKT, INTGAR, REALAR, RATINGAR, CHARAR)
    ierr = psspy.branch_data_3(
        connect_to_bus,    # From bus
        new_bus_number,    # To bus
        '1',               # Circuit ID
        [1, connect_to_bus, 0, 0, 0, 0],  # INTGAR
        [line_r, line_x, line_b, 0, 0, 0, 0, 0, 0, 0, 0, 0, 100, 100, 100],  # REALAR
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # RATINGAR
        ""                 # CHARAR
    )
    print(f"Add branch: ierr = {ierr}")
    
    # Add proxy load at new bus
    add_ibr_proxy_load(new_bus_number, load_id='1')
    
    return ierr
```

### Verifying the Load Was Added

```python
def verify_load_exists(bus_number, load_id):
    """Check if a load exists at the specified bus."""
    ierr, load_data = psspy.aloadint(bus_number, 4, 'NUMBER')
    if ierr == 0 and bus_number in load_data[0]:
        print(f"✓ Load verified at bus {bus_number}")
        return True
    else:
        print(f"✗ Load not found at bus {bus_number}")
        return False
```

---

## Part 3: Dynamic Simulation Loop

### Updating the IBR Proxy During Simulation

```python
def run_ibr_dynamic_simulation(ibr_bus, load_id, power_time_series, sim_step=0.1):
    """
    Run dynamic simulation with IBR power injection.
    
    Parameters:
    -----------
    ibr_bus : int
        Bus number where IBR proxy load is located
    load_id : str
        Load ID of the proxy load
    power_time_series : dict
        {'time': [...], 'p_mw': [...], 'q_mvar': [...]}
    sim_step : float
        Simulation time step (seconds)
    """
    
    results = {'time': [], 'voltage_pu': [], 'frequency_hz': [], 'p_mw': []}
    
    for i, t in enumerate(power_time_series['time']):
        # Get IBR power at this time step
        p_mw = power_time_series['p_mw'][i]
        q_mvar = power_time_series.get('q_mvar', [0]*len(power_time_series['time']))[i]
        
        # Inject as NEGATIVE load (generation)
        ierr = psspy.load_chng_5(
            ibr_bus, 
            load_id, 
            [],                    # Integer parameters (unchanged)
            [-p_mw, -q_mvar]       # [P, Q] - Negative = injection
        )
        
        # Advance simulation
        ierr = psspy.run(0, t, 1, 1, 0)
        
        # Record voltage at IBR bus
        ierr, voltage = psspy.busdat(ibr_bus, 'PU')
        
        # Store results
        results['time'].append(t)
        results['voltage_pu'].append(voltage)
        results['p_mw'].append(p_mw)
    
    return results
```

### Extracting Frequency from Output File

```python
import dyntools

def extract_frequency(out_file, bus_number):
    """
    Extract frequency data from PSS/E output file.
    
    Parameters:
    -----------
    out_file : str
        Path to .out or .outx file
    bus_number : int
        Bus number for frequency extraction
    """
    chnfobj = dyntools.CHNF(out_file)
    short_title, chanid, chandata = chnfobj.get_data()
    
    # Find frequency channel for specified bus
    freq_channel = None
    for ch_num, ch_name in chanid.items():
        if ch_num != 'time' and str(bus_number) in str(ch_name) and 'FREQ' in str(ch_name).upper():
            freq_channel = ch_num
            break
    
    if freq_channel:
        time = chandata['time']
        freq_pu = chandata[freq_channel]
        freq_hz = [(1 + f) * 60 for f in freq_pu]  # Convert pu deviation to Hz
        return time, freq_hz
    else:
        return None, None
```

---

## Part 4: FMU Integration (Future Work)

### Conceptual Architecture

```
┌─────────────────┐     V, f      ┌─────────────────┐
│                 │ ───────────►  │                 │
│   PSS/E Grid    │               │   WEC FMU       │
│   (Dynamics)    │  ◄───────────  │   (P, Q out)    │
│                 │     P, Q      │                 │
└─────────────────┘               └─────────────────┘
         │                                 │
         │  psspy.run()                    │  fmu.doStep()
         │  psspy.load_chng_5()            │  fmu.setReal(V, f)
         │  psspy.busdat('PU')             │  fmu.getReal(P, Q)
         ▼                                 ▼
    Grid State                        IBR Response
```

### FMU Interface Requirements

For the WEC FMU to participate in co-simulation, it should:

**Inputs:**
- `voltage_pu` - Bus voltage magnitude (per-unit)
- `frequency_hz` - System frequency (Hz)

**Outputs:**
- `p_mw` - Active power output (MW)
- `q_mvar` - Reactive power output (Mvar)

### Pseudo-code for FMU Co-simulation

```python
from fmpy import read_model_description, extract, instantiate_fmu

def run_cosimulation_with_fmu(fmu_path, ibr_bus, load_id, sim_end, sim_step):
    """
    Run PSS/E dynamic simulation co-simulated with FMU.
    """
    
    # Initialize FMU
    model_desc = read_model_description(fmu_path)
    fmu = instantiate_fmu(fmu_path, model_desc)
    fmu.setupExperiment()
    fmu.enterInitializationMode()
    fmu.exitInitializationMode()
    
    current_time = 0.0
    
    while current_time < sim_end:
        # 1. Get grid state from PSS/E
        ierr, voltage_pu = psspy.busdat(ibr_bus, 'PU')
        frequency_hz = get_current_frequency(out_file, ibr_bus)
        
        # 2. Pass grid state to FMU
        fmu.setReal([voltage_input_ref], [voltage_pu])
        fmu.setReal([frequency_input_ref], [frequency_hz])
        
        # 3. Advance FMU
        fmu.doStep(current_time, sim_step)
        
        # 4. Get IBR output from FMU
        p_mw = fmu.getReal([p_output_ref])[0]
        q_mvar = fmu.getReal([q_output_ref])[0]
        
        # 5. Update proxy load in PSS/E
        psspy.load_chng_5(ibr_bus, load_id, [], [-p_mw, -q_mvar])
        
        # 6. Advance PSS/E
        current_time += sim_step
        psspy.run(0, current_time, 1, 1, 0)
    
    fmu.terminate()
```

---

## Part 5: Complete Example

### Full Workflow from RAW/DYR Files

```python
"""
Complete IBR proxy dynamic simulation example.
"""

import os
import sys
import numpy as np
import pandas as pd

# Initialize PSS/E
import pssepath
pssepath.add_pssepath()
import psse35
import psspy
import dyntools

psspy.psseinit(1000)

# === Configuration ===
RAW_FILE = "ieee14.raw"
DYR_FILE = "ieee14.dyr"
OUT_FILE = "ibr_simulation.out"
IBR_BUS = 11
LOAD_ID = '99'
SIM_END = 30.0
SIM_STEP = 0.1

# === Step 1: Load Power Flow Case ===
psspy.read(0, RAW_FILE)
psspy.fnsl([0, 0, 0, 1, 1, 0, 99, 0])

# === Step 2: Add IBR Proxy Load ===
psspy.load_data_6(
    IBR_BUS, LOAD_ID,
    [IBR_BUS, 1, 1, 1, 1, 1, 0, 0, 0],
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
)

# === Step 3: Re-solve Power Flow ===
psspy.fnsl([0, 0, 0, 1, 1, 0, 99, 0])

# === Step 4: Load Dynamic Models ===
psspy.dyre_new([1, 1, 1, 1], DYR_FILE, "", "", "")

# === Step 5: Initialize Dynamics ===
psspy.cong(0)
psspy.ordr(0)
psspy.fact()
psspy.tysl(0)

# === Step 6: Set Up Output Channels ===
psspy.chsb(0, 1, [-1, -1, -1, 1, 13, 0])  # Voltage
psspy.chsb(0, 1, [-1, -1, -1, 1, 12, 0])  # Frequency

# === Step 7: Start Dynamic Simulation ===
psspy.strt_2([0, 0], OUT_FILE)
psspy.run(0, 1.0, 1, 1, 0)  # Flat start

# === Step 8: Generate IBR Power Profile ===
# (Replace this with FMU output or database query)
time_points = np.arange(1.0, SIM_END, SIM_STEP)
p_mw = 10.0 + 2.0 * np.sin(2 * np.pi * 0.1 * time_points)  # Example oscillating power

# === Step 9: Run Simulation Loop ===
results = []
for t, p in zip(time_points, p_mw):
    # Update proxy load (negative = generation)
    psspy.load_chng_5(IBR_BUS, LOAD_ID, [], [-p])
    
    # Advance simulation
    psspy.run(0, t, 1, 1, 0)
    
    # Record voltage
    ierr, v = psspy.busdat(IBR_BUS, 'PU')
    results.append({'time': t, 'p_mw': p, 'voltage_pu': v})

# === Step 10: Extract Frequency and Analyze ===
df = pd.DataFrame(results)
print(df.describe())
```

---

## Appendix A: PSS/E API Quick Reference

### Case Loading

| Function | Description |
|----------|-------------|
| `psspy.read(0, raw_file)` | Load RAW file |
| `psspy.case(sav_file)` | Load SAV/CNV file |
| `psspy.rstr(snp_file)` | Restore snapshot |

### Dynamic Initialization

| Function | Description |
|----------|-------------|
| `psspy.dyre_new([1,1,1,1], dyr_file, "", "", "")` | Load DYR file |
| `psspy.cong(0)` | Convert generators |
| `psspy.ordr(0)` | Order network |
| `psspy.fact()` | Factorize |
| `psspy.tysl(0)` | Initialize dynamics |
| `psspy.strt_2([0,0], out_file)` | Start simulation |

### Load Modification

| Function | Description |
|----------|-------------|
| `psspy.load_data_6(bus, id, intgar, realar)` | Add new load |
| `psspy.load_chng_5(bus, id, intgar, realar)` | Modify existing load |

### Simulation Control

| Function | Description |
|----------|-------------|
| `psspy.run(0, time, 1, 1, 0)` | Advance to time |
| `psspy.busdat(bus, 'PU')` | Get bus voltage |
| `psspy.abusreal(-1, 2, 'PU')` | Get all bus voltages |

---

## Appendix B: Error Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid parameter |
| 2 | Bus not found |
| 3 | No swing bus in island |
| 4 | Inconsistent data |

---

## Appendix C: File Format Notes

### RAW File Structure
```
0,   100.00, 35, 0, 0, 60.00     / PSS/E-35.0
GENERAL, RATE1, RATE2, RATE3
/ BUS DATA FOLLOWS
1,'Bus 1', 138.000,1, 1, 1, 1, 1.0000, 0.0000
...
/ LOAD DATA FOLLOWS
1,'1',1, 1, 1, 50.000, 30.000, 0.0, 0.0, 0.0, 0.0
...
```

### DYR File Structure
```
/ Generator models
1 'GENROU' 1  8.0  0.03  0.4  0.04  6.0  0.0  1.8  1.7  0.3  0.55  0.25  0.2  0.039  0.027 /
/ Exciter models
1 'ESST1A' 1  0  1.0  10.0  1.0  -1.0  ... /
/ Governor models  
1 'TGOV1' 1  0.05  0.5  0.1  1.0  0.0  2.0 /
```
