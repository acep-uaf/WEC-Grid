<p align="center">
  <img src="./docs/images/logo.jpeg" alt="WEC-Grid Logo">
</p>

## WEC-Grid: Integrating Wave Energy Converters into Power Grid Simulations

**WEC-Grid** is an open-source Python library crafted to simulate the integration of Wave Energy Converters (WECs) and Current Energy Converters (CECs) into renowned power grid simulators like [PSS®E](https://new.siemens.com/global/en/products/energy/services/transmission-distribution-smart-grid/consulting-and-planning/pss-software/pss-e.html) & [PyPSA](https://pypsa.org/).

You can find the full documentation [here](https://acep-uaf.github.io/WEC-GRID/).

### Introduction

Amidst the global shift towards sustainable energy solutions, Wave Energy Converters (WECs) and Current Energy Converters (CECs) emerge as groundbreaking innovations. These tools harbor the potential to tap into the boundless energy reserves of our oceans. Yet, to weave them into intricate systems like microgrids, a profound modeling, testing, and analysis regimen is indispensable. WEC-Grid, presented through this Jupyter notebook, is a beacon of both demonstration and guidance, capitalizing on an open-source software to transcend these integration impediments.

### Overview

<p align="center">
  <img src="./docs/images/flowchart.png">
</p>

WEC-Grid is in its nascent stages, yet it presents a Python Jupyter Notebook that successfully establishes a PSSe API connection. It can solve both static AC & DC power flows, injecting data from a WEC/CEC device. Additionally, WEC-Grid comes equipped with rudimentary formatting tools for data analytics. The modular design ensures support for a selected power flow solving software and WEC/CEC devices.

For the current implementations, WEC-Grid is compatible with PSSe and [WEC-SIM](https://wec-sim.github.io/WEC-Sim/). The widespread application of PSSe in the power systems industry, coupled with its robust API, makes it an ideal choice.

<p align="center">
  <img src="./docs/images/sld.png" alt="WEC-Grid SLD Visualization">
</p>

---

### Software Requirements and Setup

#### Prerequisites

1. **Install Miniconda**
   - Download and install [Miniconda (64-bit)](https://docs.conda.io/en/latest/miniconda.html) for Python environment management.
   - TODO: add instructions to add miniconda to path and other trouble shooting 

2. **MATLAB**
   - Ensure MATLAB 2021b is installed. [Download MATLAB](https://www.mathworks.com/products/matlab.html). This is the only tested and supported version of MATLAB currently. Hold off on installing the MATLAB Engine API for Python until your conda environment is set up.

3. **WEC-SIM**
   - Install WEC-SIM (latest version). [Get WEC-SIM](https://wec-sim.github.io/WEC-Sim/).
   - Expose MATLAB to Python by installing the MATLAB Engine API for Python. Follow instructions [here](https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html). Instructions are also provided below.

4. **PSSe API**
   - Obtain and configure the PSSe API. Details and licensing are available on the [PSS®E website](https://new.siemens.com/global/en/products/energy/services/transmission-distribution-smart-grid/consulting-and-planning/pss-software/pss-e.html).

---

### Installation Sequence

#### Step 0: Prerequisites
1. Install Miniconda, MATLAB, WEC-SIM, and the PSSe API.
2. Clone the WEC-Grid repository:
   ```bash
   git clone https://github.com/acep-uaf/WEC-GRID
3. Confirm conda is installed:
   ```bash
   conda --version
   ```
4. navigate to the WEC-Grid directory:
   ```bash
   cd WEC-GRID
   ```
#### Step 1: Set up the Conda Environment
1. Create the environment using the provided `.yml` file:
   ```bash
   conda env create -f wec_grid_env.yml
   ```
2. Activate the environment:
   ```bash
   conda activate WEC_GRID_ENV
   ```

#### Step 2: Install WEC-Grid
Run the following to install the `WEC-Grid` package in editable mode:
```bash
pip install -e .
```

#### Step 3: MATLAB Engine API Installation
1. Navigate to the MATLAB Engine installation directory:
   ```bash
   cd "C:\Program Files\MATLAB\R2021b\extern\engines\python"
   this will most likely be different for your installation
   ```
2. Run the following command to install the MATLAB Engine API:
   ```bash
   python -m pip install . 

   #todo format the above command to be more clear about using the dot 
   ```

Currently MATLAB Engine API is only supported on python 3.8, if you run into install issues confirm you are using your conda environment with python 3.8. You can test this using the Jupyter notebook in examples/Environment_Testing.ipynb
   ```
#### Step 3.5: Naviagte to the WEC-Grid directory

#### Step 4: Configure the PSSe python API

#TODO: Add instructions for configuring the PSSe API
---

### Testing the Setup

1. Activate the `WEC_GRID_ENV` environment:
   ```bash
   conda activate WEC_GRID_ENV
   ```
2. Launch Jupyter Lab:
   ```bash
   jupyter lab
   ```
3. Run the example notebooks to verify compatibility with:
   - PSSe
   - WEC-SIM
   - MATLAB API

---

### Version Number
TODO: Add version number beta 1.0.0
TODO: list all tested and working functions, dynamics and not working forsure. 

### Contributing

Feel free to contribute or raise issues on our [GitHub repository](https://github.com/acep-uaf/WEC-GRID). Your feedback and collaboration drive the future of WEC-Grid. 🚀
