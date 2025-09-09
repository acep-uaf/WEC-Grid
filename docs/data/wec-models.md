# WEC Models

WEC-Grid includes two pre-configured wave energy converter models for simulation studies. 

--- 

## RM3
<!-- TODO: Add 3D model visualization for RM3 -->
- **Description**: Two-body point absorber developed by Sandia National Laboratories
- **Type**: Point absorber with vertical motion
- **Download**: [RM3 Model (ZIP)](RM3.zip)
- **Citation**: [RM3](https://tethys-engineering.pnnl.gov/signature-projects/rm3-wave-point-absorber)

--- 

## LUPA

- **Description**: OSU Linear Model Two-body heave-only wave energy converter
- **Type**: Two-body heave-only, 20-meter diameter  
- **Developer**: Oregon State University PMEC Lab
- **Download**: [LUPA Model (ZIP)](LUPA.zip)
- **Citation**: [LUPA GitHub Repository](https://github.com/PMEC-OSU/LUPA_WEC-Sim/tree/main)
- **Version**: [20 m LUPA](https://github.com/PMEC-OSU/LUPA_WEC-Sim/tree/main/Additional%20Numerical%20Models/TEAMERLUPA2_inf_depth_20m)

---

## Wave-to-Wire Model Architecture 

### Wave-to-Wire Model Architecture

<!-- <div style="clear: both; text-align: center;">
  <img src="../../assets/lupa_simulink.png" alt="LUPA Wave-to-Wire Model Architecture" style="width: 100%; height: auto;">
  <p style="font-style: italic; margin-top: 8px; color: #666;">
    Figure 1: Complete wave-to-wire model architecture showing the integration of WEC-Sim hydrodynamic simulation with power take-off systems, electrical conversion, and grid interface components.
  </p>
</div> -->

<figure markdown="span">
  ![LUPA Wave-to-Wire Model Architecture](../../assets/lupa_simulink.png){ width="300" }
  <figcaption>Complete wave-to-wire model architecture showing the integration of WEC-Sim hydrodynamic simulation with power take-off systems, electrical conversion, and grid interface components.</figcaption>
</figure>


In the available models below we have a custom Wave-to-Wire model that captures the full energy conversion chain from ocean waves to grid-delivered electricity.  

At a high level, the model includes:
- **Wave Energy Converter (WEC-Sim):** simulates the hydrodynamic response of a floating device.  
- **Power Take-Off (PTO) Controller:** translates motion into generator force.  
- **Generator & Converter:** converts mechanical power into electrical power.  
- **Energy Storage:** smooths fluctuations and stabilizes voltage.  
- **Grid Controller:** manages power injection into the grid.  

This structure enables realistic studies of how wave energy devices interact with microgrids, while remaining flexible for different control strategies and system designs.

