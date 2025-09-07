# WECSimRunner

The **WECSimRunner** provides the interface between WEC-Grid and WEC-Sim for high-fidelity device-level wave energy converter modeling.  
It manages MATLAB engine integration, executes WEC-Sim simulations, and stores detailed hydrodynamic results for grid integration studies.

---

## Responsibilities

- **MATLAB Integration**
    - Initialize and manage MATLAB engine for WEC-Sim execution
    - Configure WEC-Sim framework paths and simulation environment
    - Handle MATLAB workspace variable management and script execution

- **Device-Level Simulation**
    - Execute high-fidelity hydrodynamic simulations using WEC-Sim models
    - Configure wave conditions (height, period, spectrum type, seed)
    - Generate time-series power output and wave elevation data

- **Database Integration**
    - Store WEC-Sim simulation results in WEC-Grid database
    - Provide unique simulation IDs for farm-level power aggregation
    - Enable retrieval of device power profiles for grid analysis

---

## Key Features

### High-Fidelity WEC Modeling
- **Hydrodynamic Analysis** — Full 6-DOF body dynamics with radiation and diffraction effects
- **Power Take-Off Systems** — Realistic PTO modeling with efficiency and control strategies
- **Wave Generation** — JONSWAP, Pierson-Moskowitz, and custom wave spectra
- **Device Validation** — Proven models for RM3, LUPA, and custom WEC geometries

### MATLAB Engine Management
- **Automatic Configuration** — Interactive setup of WEC-Sim installation paths
- **Session Management** — Start/stop MATLAB engine with proper resource cleanup
- **Path Handling** — Automatic WEC-Sim framework path configuration
- **Error Recovery** — Robust error handling for MATLAB execution failures

### Simulation Workflow
- **Parameterized Runs** — Configurable wave conditions and simulation duration
- **Model Flexibility** — Support for any WEC-Sim model directory structure
- **Result Visualization** — Automatic power and wave elevation plotting
- **Database Storage** — Seamless integration with WEC-Grid data management

---

## WEC-Sim Integration

### Simulation Execution Sequence
```
MATLAB Engine → Model Directory → Set Parameters → w2gSim() → Results → Database
```

### Core Functions

- **Engine Management**
    - `start_matlab()` — Initialize MATLAB engine and configure WEC-Sim paths
    - `stop_matlab()` — Shutdown engine and free system resources
    - `set_wec_sim_path()` — Configure WEC-Sim installation location

- **Simulation Control**
    - `__call__()` — Execute complete WEC device simulation with parameters
    - Wave parameters: height [m], period [s], spectrum type, random seed
    - Simulation parameters: duration [s], time step [s], model path

- **Results Management**
    - `sim_results()` — Generate power and wave elevation visualization plots
    - Database storage of time-series power [W] and wave elevation [m]
    - Return simulation ID for integration with WEC farm aggregation

---

## WEC-Grid Integration Files

### Custom MATLAB Scripts for Database Integration

WEC-Grid includes specialized MATLAB scripts that bridge WEC-Sim simulations with the WEC-Grid database schema:

**`w2gSim.m` — Main Simulation Interface**
- Accepts parameters from Python via MATLAB workspace variables
- Configures WEC-Sim simulation settings (`simLength`, `dt`, wave parameters)
- Executes standard WEC-Sim workflow: `wecSimInputFile` → `initializeWecSim` → `sim()` → `stopWecSim`
- Packages results into structured output (`m2g_out`) for database storage

**`formatter.m` — Database Integration Script**
- Converts MATLAB WEC-Sim outputs to WEC-Grid database schema
- Creates two main database tables:
  - `wec_simulations` — Simulation metadata and parameters
  - `wec_power_results` — High-resolution time-series power and wave data
- Handles data type conversions (MATLAB doubles → SQLite compatible formats)
- Generates unique simulation IDs for grid integration reference

### Database Schema Integration

**Simulation Metadata Storage:**
```sql
wec_simulations:
├─ wec_sim_id (PRIMARY KEY)
├─ model_type ('LUPA', 'RM3', etc.)
├─ sim_duration_sec, delta_time
├─ wave_height_m, wave_period_sec, wave_spectrum
└─ simulation_hash (unique identifier)
```

**Power Time-Series Storage:**
```sql
wec_power_results:
├─ wec_sim_id (FOREIGN KEY)
├─ time_sec (simulation time points)
├─ device_index (for multi-device arrays)
├─ p_w (active power in Watts)
├─ q_var (reactive power in VAR)
└─ wave_elevation_m (synchronized wave data)
```

### Data Flow Process

1. **Python → MATLAB:** Parameters passed via `matlab_engine.workspace`
2. **MATLAB Execution:** `w2gSim()` runs complete WEC-Sim simulation
3. **Result Packaging:** Simulation outputs stored in `m2g_out` structure
4. **Database Export:** `formatter.m` converts and stores data with proper schema
5. **Python Return:** `wec_sim_id` returned for farm-level power aggregation

### Model Directory Requirements

Each WEC model directory must contain:
```
model_path/
├── wecSimInputFile.m        # Standard WEC-Sim configuration
├── w2gSim.m                 # WEC-Grid integration wrapper
├── formatter.m              # Database export script
├── geometry/                # STL geometry files
├── hydroData/               # BEM coefficient files (.h5)
└── *.slx                    # Simulink model file
```

This integration allows seamless execution of detailed WEC-Sim physics while maintaining compatibility with WEC-Grid's power system analysis workflows.

- **MATLAB:** R2021b+ with valid license for WEC-Sim execution
- **WEC-Sim:** Latest version from [WEC-Sim GitHub](https://github.com/WEC-Sim/WEC-Sim)
- **MATLAB Python API:** Installed for engine integration
- **Python:** 3.8+ with matplotlib for result visualization

---

## Configuration and Setup

### Initial Configuration
```python
from wecgrid.engine import Engine

engine = Engine()
wecsim = engine.wecsim

# Interactive path setup (first time only)
wecsim.set_wec_sim_path("/path/to/WEC-Sim")
wecsim.show_config()  # Verify configuration
```

Alternatively, configure via environment variable (overrides config file):

```text
# Windows PowerShell
$env:WECGRID_WECSIM_PATH = "C:\\path\\to\\WEC-Sim"

# macOS/Linux
export WECGRID_WECSIM_PATH=~/path/to/WEC-Sim
```

WECSimRunner stores persistent configuration in a user‑writable directory (e.g., `~/.wecgrid/wecsim_config.json`).

### Model Directory Structure
```
model_path/
├── wecSimInputFile.m     # WEC-Sim configuration
├── userDefinedFunctions.m # Custom functions
├── geometry/             # Body geometry files
└── w2gSim.m             # WEC-Grid integration script
```

---

## Simulation Parameters

### Wave Conditions
- **Wave Height:** Significant wave height [m] (default: 2.5)
- **Wave Period:** Peak wave period [s] (default: 8.0)
- **Spectrum Type:** Wave spectrum ('PM', 'JS', 'irregular') (default: 'PM')
- **Wave Seed:** Random seed for wave generation (default: random 1-100)

### Simulation Settings
- **Duration:** Simulation length [s] (default: 86400 = 24 hours)
- **Time Step:** Simulation time step [s] (default: 0.1)
- **Model Path:** Directory containing WEC-Sim model files

### Example Usage
```python
# Execute WEC simulation with custom parameters
wec_sim_id = wecsim(
    model_path="examples/data/wec_models/RM3",
    wave_height=3.0,      # 3m significant wave height
    wave_period=10.0,     # 10s peak period
    sim_length=7200,      # 2 hour simulation
    delta_time=0.05       # 0.05s time step
)
```

---

## Common Issues

### MATLAB Integration Problems
- Ensure MATLAB Python API is properly installed
- Verify WEC-Sim path points to valid installation directory
- Check MATLAB license availability for simultaneous WEC-Grid sessions

### Simulation Failures
- Validate model directory contains required WEC-Sim files (`wecSimInputFile.m`)
- Ensure wave parameters are within realistic ranges
- Check available disk space for large simulation datasets

### Performance Considerations
- Reduce simulation length for testing workflows
- Increase time step for faster execution (trade-off with accuracy)
- Use smaller wave heights to avoid numerical instabilities
