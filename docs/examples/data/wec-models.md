# WEC Models

WEC-Grid includes two pre-configured wave energy converter models for simulation studies. 

## Wave to Wire Model 

<div style="clear: both; text-align: center;">
  <img src="assets/lupa_simulink.png" alt="Wave-to-Wire" style="width: 70%; height: auto;">
</div>

In the available models below we have a custom Wave-to-Wire model that captures the full energy conversion chain from ocean waves to grid-delivered electricity.  

At a high level, the model includes:
- **Wave Energy Converter (WEC-Sim):** simulates the hydrodynamic response of a floating device.  
- **Power Take-Off (PTO) Controller:** translates motion into generator force.  
- **Generator & Converter:** converts mechanical power into electrical power.  
- **Energy Storage:** smooths fluctuations and stabilizes voltage.  
- **Grid Controller:** manages power injection into the grid.  

This structure enables realistic studies of how wave energy devices interact with microgrids, while remaining flexible for different control strategies and system designs.


## Available Models

### RM3 Reference Model
- **Description**: Two-body point absorber developed by Sandia National Laboratories
- **Type**: Point absorber with vertical motion
- **Download**: [RM3 Model (ZIP)](./wec_models/RM3.zip)
- **Citation**: [RM3](https://tethys-engineering.pnnl.gov/signature-projects/rm3-wave-point-absorber)


### LUPA Model
- **Description**: [Add description of LUPA model]
- **Type**: Two body Heave only 14 meter 
- **Download**: [LUPA Model (ZIP)](./wec_models/LUPA.zip)
- **Citation**: [LUPA Github](https://github.com/PMEC-OSU/LUPA_WEC-Sim/tree/main)

