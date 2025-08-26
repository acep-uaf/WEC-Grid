
## WEC-Grid: Integrating Wave Energy Converters into Power Grid Simulations

**WEC-Grid** is an open-source Python library crafted to simulate the integration of Wave Energy Converters (WECs) power grid simulators like [PSS®E](https://new.siemens.com/global/en/products/energy/services/transmission-distribution-smart-grid/consulting-and-planning/pss-software/pss-e.html) & [PyPSA](https://pypsa.org/).

**Documentation**: [acep-uaf.github.io/WEC-Grid](https://acep-uaf.github.io/WEC-Grid/)


### Introduction

<!-- Amidst the global shift towards sustainable energy solutions, Wave Energy Converters (WECs) emerge as groundbreaking innovations. These tools harbor the potential to tap into the energy reserves of our oceans. Yet, to weave them into intricate systems like microgrids, a profound modeling, testing, and analysis regimen is indispensable. WEC-Grid, presented through this Jupyter notebook, is a beacon of both demonstration and guidance, capitalizing on an open-source software to transcend these integration impediments. -->

### Overview


<!-- WEC-Grid is in its nascent stages, yet it presents a Python Jupyter Notebook that successfully establishes a PSSe API connection. It can solve both static AC & DC power flows, injecting data from a WEC device. Additionally, WEC-Grid comes equipped with rudimentary formatting tools for data analytics. The modular design ensures support for a selected power flow solving software and WEC devices.

For the current implementations, WEC-Grid is compatible with PSSe and [WEC-SIM](https://wec-sim.github.io/WEC-Sim/). The widespread application of PSSe in the power systems industry, coupled with its robust API, makes it an ideal choice. -->

---

### Software Setup

#### Optional (but encouraged) Software / Packages

1. **Install Miniconda**
   - Miniconda is a minimal installer for conda. It is recommended to manage your Python environments. Helpful for specifying python and other package verisons.
   - Download and install [Miniconda (64-bit)](https://docs.conda.io/en/latest/miniconda.html) for Python environment management.

2. **MATLAB**
   - MATLAB 2021b for running our wave energy converter simulations via WEC-SIM. [Download MATLAB](https://www.mathworks.com/products/matlab.html). This is the only tested and supported version of MATLAB currently. Hold off on installing the MATLAB Engine API for Python until your conda environment is set up.

3. **WEC-SIM**
   - Install WEC-SIM (UNKNOWN). [Get WEC-SIM](https://wec-sim.github.io/WEC-Sim/).
   - Expose MATLAB to Python by installing the MATLAB Engine API for Python. Follow instructions [here](https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html). Instructions are also provided below.

4. **PSSe API**
   - Obtain and configure the PSSe API. Details and licensing are available on the [PSS®E website](https://new.siemens.com/global/en/products/energy/services/transmission-distribution-smart-grid/consulting-and-planning/pss-software/pss-e.html).

---

### Install 

1. Clone WEC-Grid
   ```bash
   git clone https://github.com/acep-uaf/WEC-Grid
   ```
2. Navigate to the WEC-Grid directory:
   ```bash
   cd WEC-Grid
   ```
3. Create a conda environment: (recommended)
   ```bash
   conda create --name wec_grid_env python=3.7
   ```
4. Activate the conda environment:
   ```bash
   conda activate wec_grid_env
   ```
5. Install WEC-Grid (includes `grg-pssedata` for PSS\u00aeE RAW parsing)
   ```bash
   pip install -e .
   ```
6. (Optional) Install extra dependencies
   ```bash
   pip install wecgrid[psse]    # PSS\u00aeE API support
   pip install wecgrid[matlab]  # MATLAB engine integration
   pip install wecgrid[wecsim]  # WEC-Sim interface
   ```
7. Run tests
   ```bash
   pytest /test -v
   ```
