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
    - `simulate()` — Execute complete WEC device simulation with parameters
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

### Example Run

elow is an example of running a full 24 wec simulation of the RM3 wave energy model.

# Run WEC-Sim simulation of the RM3 wave energy model 

```python 

runner.wecsim(
    model_path="./wec/RM3",
    sim_length=3600 * 24,  # 24 hours in seconds
    delta_time=0.1,
    spectrum_type='PM',
    wave_class='irregular',
    wave_height=2.5,
    wave_period=8.0,
    wave_seed = random.randint(1, 100),
)

```
```bash

⠀              WEC-SIM⠀⠀⠀⠀     ⣠⣴⣶⠾⠿⠿⠯⣷⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⣾⠛⠁⠀⠀⠀⠀⠀⠀⠈⢻⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⠿⠁⠀⠀⠀⢀⣤⣾⣟⣛⣛⣶⣬⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⠟⠃⠀⠀⠀⠀⠀⣾⣿⠟⠉⠉⠉⠉⠛⠿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⡟⠋⠀⠀⠀⠀⠀⠀⠀⣿⡏⣤⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⠀⠀⣠⡿⠛⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣷⡍⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⣤⣤⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
            ⠀⠀⠀⠀⠀⣠⣼⡏⠀⠀           ⠈⠙⠷⣤⣤⣠⣤⣤⡤⡶⣶⢿⠟⠹⠿⠄⣿⣿⠏⠀⣀⣤⡦⠀⠀⠀⠀⣀⡄
            ⢀⣄⣠⣶⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠓⠚⠋⠉⠀⠀⠀⠀⠀⠀⠈⠛⡛⡻⠿⠿⠙⠓⢒⣺⡿⠋⠁
            ⠉⠉⠉⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠁⠀
            
Starting MATLAB Engine... MATLAB engine started.
Adding WEC-SIM to path... WEC-SIM path added.
Starting WEC-SIM simulation...
	 Model: RM3
	 Model Path: ./wec/RM3
	 Simulation Length: 86400 seconds
	 Time Step: 0.1 seconds
	 Wave class: irregular
	 Wave Height: 2.5 m
	 Wave Period: 8.0 s

simulation complete... writing to database at 
	c:\Users\alexb\research\WEC-GRID\examples\WECGrid.db
WEC-SIM complete: model = RM3, wec_sim_id = 1, duration = 86400s
MATLAB Output:
==========
WEC-Sim: An open-source code for simulating wave energy converters
Version: 5.0.1

Initializing the Simulation Class...
	Case Dir: C:\Users\alexb\research\WEC-GRID\examples\wec\RM3 

WEC-Sim Input From Standard wecSimInputFile.m Of Case Directory... 
WEC-Sim: An open-source code for simulating wave energy converters
Version: 5.0.1

Initializing the Simulation Class...
	Case Dir: C:\Users\alexb\research\WEC-GRID\examples\wec\RM3 
Elapsed time is 0.399332 seconds.

WEC-Sim Pre-processing ...   
	Infinite water depth specified in BEM and "waves.waterDepth" not specified in input file.
Set water depth to 200m for visualization.
Elapsed time is 24.918356 seconds.

WEC-Sim Simulation Settings:
	Start Time                     (sec) = 0
	End Time                       (sec) = 86400
	Time Step Size                 (sec) = 0.1
	Ramp Function Time             (sec) = 0
	Convolution Integral Interval  (sec) = 60
	 Number of Time Steps     = 864000 

Wave Environment: 
	Wave Type                            = Irregular Waves (Predefined Random Phase)
	Spectrum Type                        = Pierson-Moskowitz  
	Significant Wave Height, Hs      (m) = 2.5
	Peak Wave Period, Tp           (sec) = 8

List of Body: Number of Bodies = 2 

	***** Body Number 1, Name: float *****
	Body CG                          (m) = [0,0,-0.72]
	Body Mass                       (kg) = 725834 
	Body Diagonal MOI              (kgm2)= [2.09073E+07,2.13061E+07,3.70855E+07]

	***** Body Number 2, Name: spar *****
	Body CG                          (m) = [0,0,-21.29]
	Body Mass                       (kg) = 886691 
	Body Diagonal MOI              (kgm2)= [9.44196E+07,9.44071E+07,2.85422E+07]

List of PTO(s): Number of PTOs = 1 

	***** PTO Name: PTO1 *****
	PTO Stiffness           (N/m;Nm/rad) = 0
	PTO Damping           (Ns/m;Nsm/rad) = 0

List of Constraint(s): Number of Constraints = 1 

	***** Constraint Name: Constraint1 *****


Simulating the WEC device defined in the SimMechanics model C:\Users\alexb\research\WEC-GRID\examples\wec\RM3\W2G_ss_RM3.slx...   
Elapsed time is 5.154023 seconds.
Elapsed time is 802.377574 seconds.

Post-processing and saving...   
Elapsed time is 8.199315 seconds.
Inserting simulation metadata...
  model_type: RM3 (class: char)
  wave_spectrum: PM (class: char)
  wave_class: irregular (class: char)
  sim_hash: RM3_2.5m_8.0s_94 (class: char)
WEC-Sim data stored: wec_sim_id = 1, 864001 time points

==========
MATLAB engine stopped.

```