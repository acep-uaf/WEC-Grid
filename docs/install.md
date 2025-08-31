# Installation

## System Requirements
- **Python**: 3.7 + 
- **Operating System**: Windows recommended for full functionality (PSS®E is Windows-only). Core features compatiable with most platforms.

### Power System Software 
- **PSS®E**: Version 34 or later (commercial license required)
- **PyPSA**: PyPSA link here

### WEC Modeling Software
- **MATLAB**: R2021b + 
- **WEC-Sim**: Install separately ([WEC-Sim Installation Guide](https://wec-sim.github.io/WEC-Sim/main/user/getting_started.html))

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
   pip install wecgrid[psse]    # PSS\u00aeE API support
   pip install wecgrid[matlab]  # MATLAB engine integration
   pip install wecgrid[wecsim]  # WEC-Sim interface
   ```