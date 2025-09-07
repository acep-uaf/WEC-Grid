# WECGridPlot

## Overview

The **WECGridPlot** module provides visualization capabilities for WEC-Grid simulation results. It offers a unified plotting interface that works across PSS®E and PyPSA backends for time-series analysis, cross-platform comparisons, and network diagrams.

---

## Core Plotting Functions

### Basic Grid Component Plots

- **Bus Plots**: Voltage magnitude, angle, and power injections
- **Generator Plots**: Active/reactive power output and status
- **Load Plots**: Consumption patterns and demand profiles  
- **Line Plots**: Thermal loading and transmission capacity

### WEC-Specific Analysis

- **WEC Farm Performance**: Individual farm power output over time
- **Grid Integration**: WEC contribution to total system load
- **Connection Point Analysis**: Voltage profiles at WEC farm buses

### Cross-Platform Comparison

- **Backend Validation**: Compare PSS®E vs PyPSA results side-by-side
- **Simulation Verification**: Overlay plots to validate modeling accuracy

---

## Quick Start

### Basic Grid Plotting

```python
from wecgrid import Engine

# Initialize and run simulation
engine = Engine()
engine.case("IEEE_14_bus.raw")
engine.load(["pypsa"])  # or ["psse"], or both
engine.simulate()

# Plot bus voltages
fig, ax = engine.plot.bus(software="pypsa", parameter="v_mag", bus=["Bus_1", "Bus_5"])

# Plot generator output
fig, ax = engine.plot.gen(software="psse", parameter="p", gen=["Gen_1", "Gen_2"])

# Plot line loading
fig, ax = engine.plot.line(software="pypsa", parameter="line_pct")
```

### WEC Farm Analysis

```python
# Comprehensive WEC analysis (creates 3-panel figure)
engine.plot.wec_analysis(farms=["North Coast Farm"], software="pypsa")

# Individual WEC farm power output
fig, ax = engine.plot.gen(software="pypsa", parameter="p", gen=["WEC_Farm_1"])
```

### Cross-Platform Comparison

```python
# Compare PSS®E vs PyPSA bus voltages
plotter = WECGridPlot(engine)
plotter.compare_modelers(
    grid_component="bus",
    name=["Bus_1", "Bus_5"],
    parameter="v_mag"
)
```

### Network Diagrams

```python
# Generate single-line diagram
fig, ax = engine.plot.sld(software="pypsa", figsize=(12, 8), show=True)
```

---

## Available Parameters

### Bus Parameters
- `v_mag`: Voltage magnitude (pu)
- `angle_deg`: Voltage angle (degrees)
- `p`, `q`: Active/reactive power injection (pu)

### Generator Parameters
- `p`, `q`: Active/reactive power output (pu)

### Load Parameters
- `p`, `q`: Active/reactive power demand (pu)

### Line Parameters
- `line_pct`: Percent of thermal rating

---

## Common Issues

### Missing Time-Series Data
**Problem**: Empty plots or KeyError exceptions  
**Solution**: Ensure `engine.simulate()` was called to populate time-series data

### Component Not Found
**Problem**: Components not found in plotting requests  
**Solution**: Check available component names in GridState DataFrames

### Cross-Platform Comparison Issues
**Problem**: Time indices don't match between PSS®E and PyPSA  
**Solution**: Ensure both backends use same `engine.time.snapshots` configuration

---

## See Also

- **[Engine](engine.md)**: Main simulation orchestration and `engine.plot` interface
- **[Database](database.md)**: Storing and retrieving simulation results for plotting
- **[PSS®E Integration](psse.md)**: PSS®E backend plotting capabilities
- **[PyPSA Integration](pypsa.md)**: PyPSA backend visualization features
