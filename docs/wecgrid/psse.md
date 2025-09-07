# PSSEModeler

The **PSSEModeler** provides the interface between WEC-Grid and Siemens PSS®E software.  
It implements commercial-grade power system analysis with industry-standard modeling capabilities and comprehensive licensing management.

---

## Responsibilities

- **PSS®E Integration**
    - Initialize PSS®E Python API and manage licensing requirements
    - Load power system cases (`.sav` and `.raw` formats) 
    - Execute Newton–Raphson power flow solutions with convergence checking

- **WEC Farm Implementation**
    - Create new buses for WEC connections in PSS®E model
    - Add WEC generators with time-varying power output profiles
    - Build transmission lines connecting WEC farms to existing grid

- **Grid State Management**
    - Extract comprehensive grid data using PSS®E API calls
    - Convert PSS®E data formats to standardized **GridState** schema
    - Capture bus voltages, generator outputs, line flows, and load consumption

---

## Key Features

### Commercial Power System Analysis
- **Industry Standard** — Proven algorithms used by utilities worldwide
- **Professional Modeling** — Detailed generator, load, and transmission line parameters
- **Advanced Solvers** — Robust Newton–Raphson with validated convergence properties
- **Comprehensive Analysis** — Voltage stability, thermal limits, reactive power management

### WEC-Specific Adaptations
- **Generator Reactive Limits** — Removes Q limits to align with PyPSA modeling assumptions
- **Dynamic Updates** — Per-snapshot generator power updates from WEC-Sim time series
- **Grid Connection Modeling** — Automatic creation of collection buses and transmission lines

---

## PSS®E API Integration

### Initialization Sequence

```
psseinit() → case()/read() → sysmva() → fnsl() → solved()
```

### Core API Calls

- **Power Flow Solution**
    - `fnsl()` — Full Newton–Raphson power flow solution  
    - `solved()` — Convergence status check (0 = converged)  
    - `iterat()` — Iteration count from last solution attempt  

- **Data Extraction**
    - `abuschar()`, `abusint()`, `abusreal()` — Bus names, numbers, voltages [pu/deg/kV]
    - `amachint()`, `amachreal()` — Generator locations, power output [MW/MVAr]
    - `aloadint()`, `aloadcplx()` — Load locations, power consumption [MW/MVAr]
    - `abrnchar()`, `abrnint()`, `abrnreal()` — Line IDs, connections, loading [%]  

- **Grid Modification**
    - `bus_data_4()` — Add new buses for WEC connections  
    - `plant_data_4()` — Add plant records to buses  
    - `branch_data_3()` — Create transmission lines between buses  

---

## Technical Specifications

### System Requirements

- **PSS®E Software:** Version 35.3 or later with valid commercial license  
- **Python Integration:** PSS®E Python API (`psspy`, `psse35`, `redirect`)  
- **File Formats:** `.sav` (saved cases) and `.raw` (raw data)  
- **Operating System:** Windows (PSS®E is Windows-only)


### Data Schema Compliance

All PSS®E data is converted to WEC-Grid’s standardized format:

- **Units:** Per-unit on system MVA base; angles in degrees; line loading in %  
- **Naming:** Sequential IDs with descriptive names (`Bus_1`, `Gen_1`, …)  
- **Time-Series:** Consistent timestamps and component indexing across snapshots  
- **Cross-Platform:** Identical schemas enable direct comparison with PyPSA results

---

## Error Handling and Troubleshooting

### Common PSS®E Error Codes

- **ierr = 1** — Invalid OPTIONS value or parameter out of range  
- **ierr = 3** — Island without swing bus (check generator/bus types)  
- **ierr = 4** — Bus type inconsistencies (verify load/generator connections)

### License Issues

- Ensure the PSS®E license server is accessible  
- Verify Python API modules are on `PYTHONPATH` (or use `pssepath.add_pssepath()`)  
- Check PSS®E version compatibility with your Python version

