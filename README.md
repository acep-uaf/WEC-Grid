[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/acep-uaf/WEC-Grid/v1.0.0)
# WEC-Grid: Integrating Wave Energy Converters into Power Grid Simulations

<div style="clear: both; text-align: center;">
  <img src="./docs/assets/WEC-Grid_mini_white.png" alt="WEC-Grid Logo" style="width: 80%; height: auto;">
</div>

**WEC-Grid** is an open-source Python library crafted to simulate the integration of Wave Energy Converters (WECs) power grid simulators like [PSS®E](https://new.siemens.com/global/en/products/energy/services/transmission-distribution-smart-grid/consulting-and-planning/pss-software/pss-e.html) & [PyPSA](https://pypsa.org/).

**Documentation**: [acep-uaf.github.io/WEC-Grid](https://acep-uaf.github.io/WEC-Grid/)

---

### Software Setup

#### Optional (but encouraged) Software / Packages

1. **Install Miniconda**
   - Miniconda is a minimal installer for conda. It is recommended to manage your Python environments. Helpful for specifying python and other package versions.
   - Download and install [Miniconda (64-bit)](https://docs.conda.io/en/latest/miniconda.html) for Python environment management.

2. **MATLAB**
   - MATLAB 2021b for running our wave energy converter simulations via WEC-SIM. [Download MATLAB](https://www.mathworks.com/products/matlab.html). This is the only tested and supported version of MATLAB currently. Hold off on installing the MATLAB Engine API for Python until your conda environment is set up.

3. **WEC-SIM**
   - Install WEC-SIM. [Get WEC-SIM](https://wec-sim.github.io/WEC-Sim/).
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
3. Create an environment: (recommended)
   ```bash 
   py -3.9 -m venv wecgrid_env

   ``` or with conda
   ```bash
   conda create --name wecgrid_env python=3.9
   ```
4. Activate the environment:
   ```bash 
   .\wecgrid_env\Scripts\activate
   python -m pip install --upgrade pip

   ``` or with conda
   ```bash
   conda activate wecgrid_env
   ```
5. Install WEC-Grid!
   ```bash
   pip install -e .
   ```
6. (Optional) Install extra dependencies
   ```bash
   pip install wecgrid[psse]    # PSS®E path helper support
   ```
7. Run tests
   ```bash
   pytest -v
   ```

---

### Configuration

You can configure paths via code or environment variables.

- Database path
  - Quick (env var): set `WECGRID_DB_PATH` to your SQLite database
    - Windows (PowerShell): `$env:WECGRID_DB_PATH = "C:\\path\\to\\WECGrid.db"`
    - macOS/Linux (bash/zsh): `export WECGRID_DB_PATH=~/path/to/WECGrid.db`
  - Persistent (code): `engine.database.set_database_path("/path/to/WECGrid.db")`
    - This writes a JSON config into your user config directory (e.g., `~/.wecgrid/database_config.json`).

- WEC‑Sim path (MATLAB install)
  - Quick (env var): set `WECGRID_WECSIM_PATH` to the WEC‑Sim folder
  - Persistent (code): `engine.wecsim.set_wec_sim_path("/path/to/WEC-Sim")`
    - Stored in your user config directory (e.g., `~/.wecgrid/wecsim_config.json`).
