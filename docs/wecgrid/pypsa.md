# PyPSAModeler

The **PyPSAModeler** provides the interface between WEC-Grid and the open-source [PyPSA](https://pypsa.org) library.  
It implements open-source power system analysis with modern Python algorithms and cross-platform validation capabilities.

---

## Responsibilities

- **PyPSA Integration**
    - Parse PSS®E RAW case files via GRG parser
    - Build PyPSA `Network` objects with buses, lines, generators, loads, transformers
    - Execute AC power flow solutions using PyPSA's solver

- **WEC Farm Implementation**
    - Create new buses for WEC connections
    - Add WEC generators with `carrier="wave"` designation
    - Connect WEC farms to existing grid via transmission lines

- **Grid State Management**
    - Extract comprehensive grid data from PyPSA network components
    - Convert PyPSA data formats to standardized **GridState** schema
    - Capture bus voltages, generator outputs, line flows, and load consumption

---

## Key Features

### Open-Source Power System Analysis
- **Accessible Research** — No licensing requirements; reproducible scientific workflows
- **Modern Algorithms** — Python-based optimization with SciPy/NumPy integration
- **Cross-Validation** — Direct comparison with PSS®E results using identical case files
- **Flexible Modeling** — Lightweight data structures and pandas integration

### WEC-Specific Adaptations
- **Wave Energy Carriers** — WEC generators tagged with `carrier="wave"`
- **Dynamic Updates** — Per-snapshot generator power updates from WEC-Sim time series
- **Collection Systems** — Automatic bus and line creation for WEC farms

---

## PyPSA API Integration

### Initialization Sequence
```
parse_psse_case_file() → pypsa.Network() → add components → network.pf()
```

### Core API Calls

- **Power Flow**
    - `network.pf()` — Solve AC power flow with optimization backend
    - `network.snapshots` — Time index for simulation periods

- **Data Access**
    - `network.buses[['v_nom','control']]` — Bus voltages and control types [kV]
    - `network.generators[['p_set','q_set','carrier']]` — Generator setpoints [MW/MVAr]
    - `network.loads[['p_set','q_set']]` — Load consumption [MW/MVAr]
    - `network.lines[['bus0','bus1','s_nom']]` — Line connections and ratings [MVA]

- **Grid Modification**
    - `network.add("Bus")` — Add new buses for WEC connections
    - `network.add("Generator")` — Add WEC generators with wave carrier
    - `network.add("Line")` — Create transmission lines between buses

---

## Function Spotlight — `import_raw_to_pypsa()`

The core function that converts PSS®E `.raw` cases into PyPSA `Network` objects using the GRG parser.

### Key Operations
- **Impedance Conversion:** R_Ω = R_pu × (V_base² / S_base), X_Ω = X_pu × (V_base² / S_base)
- **Control Mapping:** PSS®E IDE codes → PyPSA control types (`PQ`, `PV`, `Slack`)
- **Component Creation:** Buses, lines, generators, loads, transformers, shunts

### Usage
```python
eng = Engine()
eng.case("ieee_39.raw")
eng.load(["pypsa"])  # Calls import_raw_to_pypsa() internally
```

---

## System Requirements

- **PyPSA:** Version 0.20.1 (as pinned) with pandas, NumPy, SciPy
- **GRG parser:** `grg-pssedata` package for PSS®E RAW import
- **Python:** 3.7+ (3.9 recommended)
- **Operating System:** Cross-platform (Windows, macOS, Linux)

---

## Common Issues

### Case Import Problems
- Ensure `grg_pssedata` can parse the RAW file format
- Verify voltage bases and transformer ratings are present
- Check for well-formed PSS®E RAW structure (versions 33-35)

### Convergence Issues
- Inspect network topology for islands and missing slack buses
- Verify generator `p_set` and system load balance
- Confirm transformer taps and line ratings are reasonable

### Performance and Logging
- Reduce console output by raising PyPSA logger level
- Use vectorized operations for time-series updates
- Consider smaller snapshot windows for testing workflows
