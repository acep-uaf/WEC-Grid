# WEC Module

## Overview

The WEC module provides the core data structures for representing Wave Energy Converter (WEC) devices and farms within WEC-Grid power system simulations. This module bridges high-fidelity WEC-Sim hydrodynamic modeling with power system integration requirements through hierarchical device and farm abstractions.

---

## Software Architecture

### Hierarchical Design Philosophy

WEC-Grid employs a two-tier hierarchy for wave energy integration:

**Individual Devices** (`WECDevice`):
    - Represent single wave energy converters with time-series power output
    - Contain simulation metadata, grid connection parameters, and performance data
    - Serve as building blocks for larger installations

**Farm Collections** (`WECFarm`):
    - Aggregate multiple identical WEC devices at common grid connection points
    - Coordinate power system integration for multi-device installations
    - Manage shared infrastructure and grid interface requirements

---

## Responsibilities

- **WECDevice Class**
    - Store and manage power output data from WEC-Sim simulations
    - Provide electrical parameters for power system modeling
    - Maintain simulation provenance and device characteristics
    - Support both high-resolution and grid-compatible time series

- **WECFarm Class**
    - Coordinate multiple WEC devices at shared connection points
    - Calculate total farm output for grid integration studies
    - Load WEC-Sim simulation results and distribute to devices
    - Align device data with power system simulation time steps

---

## Key Features

- **WECDevice Capabilities**
    - Dual resolution data: Primary dataframe (5-minute grid intervals) and full dataframe (high-resolution WEC-Sim output)
    - Automatic scaling to power system base values (typically 100 MVA)
    - Structured device identifiers for traceability (`{model}_{sim_id}_{index}`)
    - Bus location, base power rating, and connection metadata

- **WECFarm Capabilities**
    - Identical devices with linear power scaling
    - Automatic loading from WEC-Grid simulation database
    - Integration with WEC-Grid time coordination system
    - Adjustable farm size, scaling factors, and grid parameters

---

## API Integration

### Farm Data Loading and Device Creation

WECFarm automatically handles the complete data pipeline from database to individual devices:

```python
# Farm initialization triggers automatic data loading
farm = WECFarm(
    farm_name="Oregon Coast Array",
    database=wecgrid_db,           # WECGridDB interface
    time=time_manager,             # Time coordination
    wec_sim_id=101,                # Database simulation reference
    bus_location=14,               # Grid connection bus
    size=10                        # Number of devices to create
)
```

**Internal Data Flow Process:**

1. **Database Query**: Farm uses `wec_sim_id` to pull full-resolution data from `wec_power_results` table
2. **Data Processing**: Raw WEC-Sim data (Watts, high-frequency) loaded into pandas DataFrame
3. **Downsampling**: Full-resolution data averaged to 5-minute intervals for grid compatibility
4. **Per-Unit Conversion**: Power values converted to per-unit based on system base power (typically 100 MVA)
5. **Device Creation**: Farm creates `size` number of identical WECDevice objects, each with processed data
6. **Time Indexing**: Timestamps aligned with power system simulation time grid

```python
# Example of what happens internally during farm._prepare_farm()
power_query = """
    SELECT time_sec as time, p_w as p, q_var as q, wave_elevation_m as eta 
    FROM wec_power_results 
    WHERE wec_sim_id = ? 
    ORDER BY time_sec
"""
df_full = database.query(power_query, params=(wec_sim_id,), return_type="df")

# Downsample to 5-minute intervals
df_downsampled = farm.down_sample(df_full, time_manager.delta_time)

# Convert to per-unit and create devices
for i in range(farm.size):
    device = WECDevice(
        name=f"{model}_{wec_sim_id}_{i}",
        dataframe=df_downsampled.copy(),  # Each device gets independent copy
        bus_location=bus_location,
        model=model,
        wec_sim_id=wec_sim_id
    )
    farm.wec_devices.append(device)
```

### Database Schema Integration

The WEC module integrates with WEC-Grid's standardized database schema:

**WEC Simulations Table** (`wec_simulations`):
```sql
wec_sim_id (PRIMARY KEY)     -- Unique simulation identifier
model_type                   -- WEC device model ('RM3', 'LUPA')
sim_duration_sec            -- Simulation length
wave_height_m, wave_period_sec -- Wave conditions
simulation_hash             -- Unique parameter combination
```

**Power Results Table** (`wec_power_results`):
```sql
wec_sim_id (FOREIGN KEY)    -- Links to simulation metadata
time_sec                    -- Simulation time points
device_index               -- For multi-device simulations
p_w, q_var                 -- Active/reactive power [W, VAR]
wave_elevation_m           -- Synchronized wave data
```

---

## Data Resolution Management

### Primary vs. Full Resolution

**Primary DataFrame** (Grid Integration):
    - **Time step**: 5-minute intervals for power system compatibility
    - **Columns**: `time`, `p` [pu], `q` [pu], `base` [MVA]
    - **Purpose**: PSS®E/PyPSA integration, economic dispatch, stability studies
    - **Processing**: Downsampled and per-unit converted from WEC-Sim output

**Full DataFrame** (Research Analysis):
    - **Time step**: Native WEC-Sim resolution (typically 0.1-1.0 seconds)
    - **Columns**: `time`, `p` [MW], `q` [MVAr], `eta` [m], device states
    - **Purpose**: Detailed analysis, control development, performance validation
    - **Processing**: Direct WEC-Sim output with minimal processing

### Time Synchronization

```python
# Farm automatically handles time alignment
farm._prepare_farm()  # Internal method called during initialization

# Creates pandas datetime index for grid integration
df_downsampled["snapshots"] = pd.date_range(
    start=time_manager.start_time,    # Simulation start time
    periods=df_downsampled.shape[0],  # Number of time points
    freq=time_manager.freq,           # Typically '5min'
)
```

---

## Mathematical Formulations

### Power Aggregation

Total farm active power at time $t$:

$$P_{farm}(t) = \sum_{i=1}^{N_{devices}} P_{device,i}(t)$$


Where:
- $N_{devices}$ = Number of devices in farm
- $P_{device,i}(t)$ = Individual device power output [pu]
- All devices assumed identical: $P_{device,i}(t) = P_{device}(t)$

### Per-Unit Conversion

WEC-Sim power output (Watts) to per-unit:

$$P_{pu} = \frac{P_{watts}}{S_{base} \times 10^6}$$

Per-unit back to physical power (MW):

$$P_{MW} = P_{pu} \times S_{base}$$

Where:
- $P_{watts}$ = WEC-Sim power output [W]
- $S_{base}$ = Base power rating [MVA]
- $P_{pu}$ = Per-unit power on system base

### Downsampling Formula

For averaging high-frequency data to coarser time steps:

$$P_{avg}[k] = \frac{1}{N_{samples}} \sum_{j=0}^{N_{samples}-1} P_{original}[k \cdot N_{samples} + j]$$

Where:
- $N_{samples} = \frac{\Delta t_{new}}{\Delta t_{original}}$ = samples per averaging window
- $k$ = index of downsampled time point
- $\Delta t_{original}$ = Original time step (e.g., 0.1s from WEC-Sim)
- $\Delta t_{new}$ = Target time step (e.g., 300s for 5-minute intervals)

---

## See Also

- **[WEC-Sim Integration](wecsim.md)**: WECSimRunner for MATLAB/WEC-Sim interface
- **[Database Schema](database.md)**: WEC-Grid database structure and tables
- **[Engine Coordination](engine.md)**: Main simulation orchestration
- **[Time Management](time.md)**: Simulation time coordination system
