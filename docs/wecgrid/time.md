# WECGridTime

## Overview

The **WECGridTime** module provides centralized time coordination for WEC-Grid simulations. It manages temporal aspects across power system modeling (PSS®E, PyPSA), WEC simulations (WEC-Sim), and data visualization with consistent temporal alignment and configurable time intervals.

---

## Responsibilities

- **Time Coordination**
  - Synchronize simulation time across all WEC-Grid components
  - Provide consistent temporal reference for power system and WEC modeling
  - Generate time snapshots for time-series data alignment

- **Simulation Scheduling**
  - Define simulation start time, duration, and sampling intervals
  - Calculate simulation end time based on configured parameters
  - Support flexible time window configuration for different study types

- **Cross-Platform Alignment**
  - Ensure temporal consistency between PSS®E and PyPSA simulations
  - Coordinate WEC-Sim high-resolution data with grid time steps
  - Align database time-series storage with simulation timestamps

---

## Key Features

- **Flexible Time Configuration**
  - Configurable start time, duration, and frequency
  - Support for pandas frequency strings (5min, 15min, 1H, etc.)
  - Automatic calculation of simulation end time and snapshot generation

- **Cross-Component Synchronization**
  - Consistent time reference for all simulation backends
  - Automatic time-series index generation for pandas DataFrames
  - Delta time conversion for different modeling requirements

- **Simulation Time Management**
  - Default 24-hour simulation at 5-minute intervals (288 steps)
  - Support for custom simulation periods and frequencies
  - Real-time parameter updates with automatic recalculation

---

## API Integration

### Basic Time Manager Setup

```python
from wecgrid.util.time import WECGridTime
from datetime import datetime

# Default configuration (24 hours, 5-minute intervals)
time_mgr = WECGridTime()
print(f"Steps: {time_mgr.num_steps}")     # 288 steps
print(f"Frequency: {time_mgr.freq}")     # 5min
print(f"Duration: {time_mgr.sim_stop}")  # 24 hours later

# Custom simulation period
time_mgr = WECGridTime(
    start_time=datetime(2024, 6, 15, 6, 0, 0),  # 6 AM start
    num_steps=144,                               # 12 hours
    freq="5min"                                  # 5-minute intervals
)
```

### Time Snapshot Generation

```python
# Generate time series index for data alignment
snapshots = time_mgr.snapshots
print(f"Time range: {snapshots[0]} to {snapshots[-1]}")
print(f"Total points: {len(snapshots)}")

# Use with pandas DataFrames
import pandas as pd
power_data = pd.DataFrame({
    'p': [1.5, 2.1, 1.8] * (len(snapshots) // 3),
    'q': [0.0, 0.0, 0.0] * (len(snapshots) // 3)
}, index=snapshots)
```

### Dynamic Time Configuration

```python
# Update simulation parameters
time_mgr.update(
    start_time=datetime(2024, 1, 1, 0, 0, 0),
    num_steps=672,      # Weekly simulation (7 days)
    freq="15min"        # 15-minute intervals
)

# Set simulation by end time
end_time = datetime(2024, 1, 2, 0, 0, 0)  # 24 hours later
time_mgr.set_end_time(end_time)
print(f"Steps calculated: {time_mgr.num_steps}")
```

### Integration with WEC-Grid Components

```python
from wecgrid import Engine

# Initialize engine with time configuration
engine = Engine()
engine.time = WECGridTime(
    start_time=datetime(2024, 3, 15, 0, 0, 0),
    num_steps=288,      # 24 hours
    freq="5min"         # 5-minute resolution
)

# Time manager automatically coordinates all components
engine.simulate()  # Uses configured time parameters

# Access time information from any component
print(f"Simulation time range: {engine.time.start_time} to {engine.time.sim_stop}")
```

---

## Time Configuration Patterns

### Power System Studies

```python
# Economic dispatch (hourly intervals)
economic_time = WECGridTime(
    start_time=datetime(2024, 1, 1, 0, 0, 0),
    num_steps=24,       # 24 hours
    freq="1H"           # Hourly intervals
)

# Stability analysis (sub-minute resolution)
stability_time = WECGridTime(
    start_time=datetime(2024, 6, 1, 12, 0, 0),
    num_steps=60,       # 5 minutes total
    freq="5S"           # 5-second intervals
)

# Load forecasting (daily aggregation)
forecast_time = WECGridTime(
    start_time=datetime(2024, 1, 1, 0, 0, 0),
    num_steps=365,      # Full year
    freq="1D"           # Daily intervals
)
```

### WEC Integration Studies

```python
# High-resolution WEC analysis
wec_detailed = WECGridTime(
    start_time=datetime(2024, 7, 4, 0, 0, 0),  # July 4th (holiday load)
    num_steps=1440,     # 24 hours
    freq="1min"         # 1-minute resolution
)

# Multi-day resource assessment
resource_study = WECGridTime(
    start_time=datetime(2024, 3, 1, 0, 0, 0),   # March (stormy season)
    num_steps=1488,     # 31 days
    freq="30min"        # 30-minute intervals
)

# Seasonal analysis
seasonal_time = WECGridTime(
    start_time=datetime(2024, 1, 1, 0, 0, 0),
    num_steps=52,       # Full year
    freq="1W"           # Weekly aggregation
)
```

---

## Time Synchronization Details

### Cross-Platform Alignment

The time manager ensures consistent temporal reference across all simulation backends:

```python
# PSS®E and PyPSA use same time snapshots
psse_results = engine.psse.grid.bus_t['v_mag']  # Time-indexed voltages
pypsa_results = engine.pypsa.grid.bus_t['v_mag'] # Same time index

# Compare results at same timestamps
time_match = psse_results.index.equals(pypsa_results.index)  # True
```

### WEC Data Downsampling

WEC-Sim simulations often run at higher frequency than grid studies:

```python
# WEC-Sim: 0.1s time step (high resolution)
# Grid study: 5min time step (grid compatible)

# Time manager coordinates downsampling in WECFarm
farm = WECFarm(
    database=db,
    time=time_mgr,      # 5-minute grid resolution
    wec_sim_id=101      # High-resolution WEC data
)

# Automatic downsampling during farm creation
print(f"WEC data points: {len(full_resolution_data)}")     # ~36,000 points
print(f"Grid data points: {len(farm.wec_devices[0].dataframe)}")  # 288 points
```

### Database Time Storage

```python
# Time manager provides consistent timestamp format
timestamps = [ts.isoformat() for ts in time_mgr.snapshots]

# Database stores ISO-8601 strings for platform independence
db.store_gridstate_data(
    grid_sim_id=123,
    timestamp=timestamps[0],  # "2024-06-15T06:00:00"
    grid_state=current_state,
    software="psse"
)
```

---

## System Requirements

### Python Dependencies
- **datetime**: Standard library time handling
- **pandas**: Time series indexing and frequency strings
- **dataclasses**: Clean configuration object structure

### Time Zone Considerations
- **Naive Timestamps**: WECGridTime uses timezone-naive datetime objects
- **Local Time**: Assumes local timezone unless explicitly configured
- **UTC Coordination**: Users responsible for timezone conversion if needed

### Performance Characteristics
- **Memory Usage**: Linear scaling with number of time steps
- **Snapshot Generation**: Lazy evaluation via pandas date_range
- **Update Efficiency**: Automatic recalculation only when parameters change

---

## Common Issues

### Frequency String Format
**Symptom**: Invalid frequency specification errors
```python
# Correct pandas frequency formats
time_mgr = WECGridTime(freq="5min")   # ✓ 5 minutes
time_mgr = WECGridTime(freq="1H")     # ✓ 1 hour  
time_mgr = WECGridTime(freq="30S")    # ✓ 30 seconds

# Incorrect formats
time_mgr = WECGridTime(freq="5 min")  # ✗ Space not allowed
time_mgr = WECGridTime(freq="1 hour") # ✗ Use "1H" instead
```

### End Time Calculation
**Symptom**: Simulation duration doesn't match expected end time
```python
# Verify calculated end time
print(f"Expected duration: {time_mgr.num_steps * 5} minutes")
print(f"Actual end time: {time_mgr.sim_stop}")

# Adjust if needed
time_mgr.set_end_time(datetime(2024, 6, 16, 0, 0, 0))  # Explicit end time
```

### Time Alignment Issues
**Symptom**: Misaligned time series between components
```python
# Check time manager consistency across components
print(f"Engine time steps: {len(engine.time.snapshots)}")
print(f"WEC farm data points: {len(farm.wec_devices[0].dataframe)}")
print(f"Grid results length: {len(engine.psse.grid.bus_t['v_mag'])}")

# All should match for proper alignment
```

### Delta Time Conversion
**Symptom**: Incorrect time step conversion between systems
```python
# Verify delta_time matches frequency
freq_to_seconds = {
    "5min": 300, "15min": 900, "1H": 3600, "1D": 86400
}
expected_delta = freq_to_seconds[time_mgr.freq]
print(f"Configured delta_time: {time_mgr.delta_time}")
print(f"Expected for {time_mgr.freq}: {expected_delta}")
```

---


## See Also

- **[Database Integration](database.md)**: Time-series data storage and retrieval
- **[WEC Module](wec.md)**: WEC farm time synchronization and downsampling
- **[Engine Coordination](engine.md)**: Cross-component time management
- **[PowerSystemModeler](base.md)**: GridState time-series alignment