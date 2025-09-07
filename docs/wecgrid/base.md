# PowerSystemModeler

The **PowerSystemModeler** is the abstract foundation for all power system backends in WEC-Grid.  
It standardizes the interface between WEC-Grid and power system tools (PSS®E, PyPSA) while providing unified data structures for cross-platform validation and comparison.

---

## Responsibilities

- **Backend Abstraction**
  - Define common API for power system tools (PSS®E, PyPSA, future backends)
  - Standardize grid data formats and component schemas
  - Enable seamless backend switching for validation studies

- **Data Management**
  - Store current grid snapshots in standardized **`GridState`** format
  - Maintain time-series history for buses, generators, lines, and loads
  - Track simulation performance metrics via **`SolveReport`**

- **WEC Integration**
  - Add WEC farms as new generators in power system models
  - Update WEC power outputs during time-series simulations
  - Coordinate with WEC-Sim for device-level modeling

---

## Core Components

### **PowerSystemModeler (Abstract Base Class)**
The foundation class that all backend implementations must extend. Defines the standard API that enables WEC-Grid's backend-agnostic approach.

**Key Methods:**

- **`init_api()`** — Initialize backend tool and load case file  
- **`solve_powerflow()`** — Run power flow solution using backend solver  
- **`add_wec_farm()`** — Integrate WEC farm into power system model  
- **`simulate()`** — Execute time-series simulation with WEC updates  
- **`take_snapshot()`** — Capture current grid state at timestamp  

---

### **GridState (Standardized Data Container)**
Unified data structure for storing power system component states across different backends.  
Enables cross-platform validation by enforcing consistent schemas.

**Current Snapshots:**
- **`bus`** — Voltage magnitudes, angles, power injections  
- **`gen`** — Generator outputs, reactive power, operational status  
- **`line`** — Line flows, thermal loading percentages  
- **`load`** — Load consumption, power factor, connection status  

**Time-Series History:**
- **`bus_t`**, **`gen_t`**, **`line_t`**, **`load_t`** — Historical data indexed by timestamp  

---

### **SolveReport (Performance Tracking)**
Captures simulation timing, convergence status, and solver performance across all time steps.

**Metrics Tracked:**
- Power flow convergence status and iteration counts  
- Solve times per snapshot and overall simulation duration  
- Grid state snapshot timing and data extraction performance  

---

## Data Schema Standards

### **Standardized Units**
- **Power**: Per-unit on system MVA base (e.g., 100 MVA)  
- **Voltage**: Per-unit magnitudes, degrees for angles  
- **Loading**: Percentage of thermal rating for transmission lines  
- **Reactive**: Per-unit on system MVA base  

### **Component Naming**
- **IDs**: Sequential numbers starting from 1 (`bus=1`, `gen=1`, etc.)  
- **Names**: Descriptive labels (`"Bus_1"`, `"Gen_1"`, `"WEC_Farm_North"`)  
- **Types**: Standardized categories (`"Slack"`, `"PV"`, `"PQ"` for buses)  

### **Cross-Platform Consistency**
All backends must produce DataFrames with identical column names and units, enabling:
- Direct numerical comparison between PSS®E and PyPSA results  
- Unified plotting and analysis workflows  
- Validation of WEC integration across different solvers  

---


## SolveReport Data Schema

The **SolveReport** tracks solver performance and timing for each simulation run.

| Field          | Description                               | Type   | Units   |
|----------------|-------------------------------------------|--------|:-------:|
| simulation_time| Total simulation duration                 | float  | seconds |
| case           | Case name or identifier                   | str    | —       |
| software       | Backend modeler (`psse`, `pypsa`)         | str    | —       |
| iter_time      | Iteration timing per snapshot             | list   | seconds |
| converged      | Convergence status per snapshot           | list   | bool    |
| pf_solve_time  | Power flow solver time per snapshot       | list   | seconds |
| pf_solve_iter  | Iteration count per snapshot              | list   | int     |
| snapshot_time  | Grid state capture timing per snapshot    | list   | seconds |
| snapshot       | Snapshot identifiers (e.g., timestamps)   | list   | any     |
| message        | Solver status or error messages           | list   | str     |

_Convenience: `SolveReport.dataframe` returns a `pandas.DataFrame` for analysis._

## GridState Data Schema

Each schema below describes the standardized **DataFrame structure** used in `GridState`.  
- **Columns** → fields stored in the DataFrame  
- **Time-Series Dictionaries (`*_t`)** → keyed by snapshot `Datetime`, wide-format

---

### **Bus (`bus` DataFrame)**

| Column    | Description                          | Type  | Units   | Base                |
|-----------|--------------------------------------|-------|:-------:|:-------------------:|
| bus       | Bus number (unique identifier)       | int   | —       | —                   |
| bus_name  | Bus name/label (e.g., `Bus_1`)       | str   | —       | —                   |
| type      | Bus type: `Slack`, `PV`, `PQ`        | str   | —       | —                   |
| p         | Net active power injection (Gen-Load)| float | pu      | **Sbase** (MVA)     |
| q         | Net reactive power injection         | float | pu      | **Sbase** (MVA)     |
| v_mag     | Voltage magnitude                    | float | pu      | **Vbase** (kV LL)   |
| angle_deg | Voltage angle                        | float | degrees | —                   |
| Vbase     | Bus nominal voltage (line-to-line)   | float | kV      | —                   |

---

### **Bus Time-Series (`bus_t` Dictionary)**

| Key        | Description                               | Units   | Base              |
|------------|-------------------------------------------|---------|:-----------------:|
| p          | Active power injection per bus            | pu      | **Sbase** (MVA)   |
| q          | Reactive power injection per bus          | pu      | **Sbase** (MVA)   |
| v_mag      | Voltage magnitude per bus                 | pu      | **Vbase** (kV LL) |
| angle_deg  | Voltage angle per bus                     | degrees | —                 |

_Time-series schema: index = `Datetime`, columns = `Bus_i`, values = floats (pu/deg)._

---

### **Generator (`gen` DataFrame)**

| Column    | Description                    | Type  | Units | Base                      |
|-----------|--------------------------------|-------|:-----:|:-------------------------:|
| gen       | Generator ID                   | int   | —     | —                         |
| gen_name  | Generator name (e.g., `Gen_1`) | str   | —     | —                         |
| bus       | Connected bus number           | int   | —     | —                         |
| p         | Active power output            | float | pu    | **Sbase** (MVA)           |
| q         | Reactive power output          | float | pu    | **Sbase** (MVA)           |
| Mbase     | Machine rating                 | float | MVA   | **Mbase** (per generator) |
| status    | Online/offline flag (1/0)      | int   | —     | —                         |

---

### **Generator Time-Series (`gen_t` Dictionary)**

| Key    | Description                | Units | Base            |
|--------|----------------------------|-------|:---------------:|
| p      | Active power per generator | pu    | **Sbase** (MVA) |
| q      | Reactive power per generator| pu   | **Sbase** (MVA) |
| status | Online/offline flag (1/0)  | —     | —               |

_Time-series schema: index = `Datetime`, columns = `Gen_i`, values = floats (p/q) or int (status)._

---

### **Load (`load` DataFrame)**

| Column    | Description                  | Type  | Units | Base            |
|-----------|------------------------------|-------|:-----:|:---------------:|
| load      | Load ID                      | int   | —     | —               |
| load_name | Load name (e.g., `Load_1`)   | str   | —     | —               |
| bus       | Connected bus number         | int   | —     | —               |
| p         | Active power demand          | float | pu    | **Sbase** (MVA) |
| q         | Reactive power demand        | float | pu    | **Sbase** (MVA) |
| status    | Connected/offline flag (1/0) | int   | —     | —               |

---

### **Load Time-Series (`load_t` Dictionary)**

| Key    | Description                 | Units | Base            |
|--------|-----------------------------|-------|:---------------:|
| p      | Active power per load       | pu    | **Sbase** (MVA) |
| q      | Reactive power per load     | pu    | **Sbase** (MVA) |
| status | Connected/offline flag (1/0)| —     | —               |

_Time-series schema: index = `Datetime`, columns = `Load_i`, values = floats (p/q) or int (status)._

---

### **Line (`line` DataFrame)**

| Column    | Description                     | Type  | Units | Base |
|-----------|---------------------------------|-------|:-----:|:----:|
| line      | Line ID                         | int   | —     | —    |
| line_name | Line name (e.g., `Line_1_2`)    | str   | —     | —    |
| ibus      | From bus number                 | int   | —     | —    |
| jbus      | To bus number                   | int   | —     | —    |
| line_pct  | Percent of thermal rating in use| float | %     | —    |
| status    | Online/offline flag (1/0)       | int   | —     | —    |

---

### **Line Time-Series (`line_t` Dictionary)**

| Key       | Description                         | Units | Base |
|-----------|-------------------------------------|-------|:----:|
| line_pct  | % thermal rating in use per line    | %     | —    |
| status    | Online/offline flag (1/0) per line  | —     | —    |

_Time-series schema: index = `Datetime`, columns = `Line_i` (or `Line_ibus_jbus`), values = floats (line_pct) or int (status)._

---
