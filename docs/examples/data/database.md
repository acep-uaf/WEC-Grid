# Database 

## Schema

<div style="clear: both; text-align: center;">
  <img src="../../../assets/database_diagram.png" alt="Database Table Diagram" style="width: 100%; height: auto;">
</div>


## Pre-Load Database Information

### Grid Simulation

#### PSSE: RTS-GMLC

- **Flat Run** (ID = 1)  
  - Duration: 24 hours  
  - Resolution: 5 min (288 steps)  
  - Load curve: none  

- **WEC Run** (ID = 2)  
  - Duration: 24 hours  
  - Resolution: 5 min (288 steps)  
  - Configuration: RM3 Farm with 10 devices at Bus 326  
  - Load curve: none  


### WEC-Sim Runs

#### RM3 (ID = 1)

- Simulation length: 24 hours (86,400 s)  
- Time step: 0.1 s  
- Spectrum type: PM (Pierson–Moskowitz)  
- Wave class: irregular  
- Wave height: 2.5 m  
- Wave period: 8.0 s  
- Wave seed: randomized  

<div style="clear: both; text-align: center;">
  <img src="../../../assets/rm3_powerw.png" alt="WEC-SIM RM3 Results" style="width: 70%; height: auto;">
</div>


#### LUPA (ID = 2)

- Simulation length: 24 hours (86,400 s)  
- Time step: 0.1 s  
- Spectrum type: PM (Pierson–Moskowitz)  
- Wave class: irregular  
- Wave height: 2.5 m  
- Wave period: 8.0 s  
- Wave seed: randomized  

<div style="clear: both; text-align: center;">
  <img src="../../../assets/lupa_powerw.png" alt="WEC-SIM LUPA Results" style="width: 70%; height: auto;">
</div>


## Pre-Load Database Download

You can download the database file here: [WECGrid.db](WECGrid.db)