# Installation

## System Requirements
- **Python**: 3.7+  
- **Operating System**: Windows recommended for full functionality (PSS®E is Windows-only). Core features are compatible with most platforms.

### Power System Software
- **PSS®E**: Version 34 or later (commercial license required)
- **PyPSA**: [PyPSA GitHub](https://github.com/PyPSA/PyPSA)

### WEC Modeling Software
- **MATLAB**: R2021b or later
- **WEC-Sim**: [WEC-Sim Getting Started Guide](https://wec-sim.github.io/WEC-Sim/main/user/getting_started.html)

---

## Install WEC-Grid

1. Clone the repository:
   ```bash
   git clone https://github.com/acep-uaf/WEC-Grid
   ```
2. Navigate into the project directory:
   ```bash
   cd WEC-Grid
   ```
3. Create a virtual environment (recommended):
   ```bash
   py -3.9 -m venv wecgrid_env
   ```
   Or with Conda:
   ```bash
   conda create --name wecgrid_env python=3.9
   ```
4. Activate the environment:
   ```bash
   .\wecgrid_env\Scripts\activate
   python -m pip install --upgrade pip
   ```
   Or with Conda:
   ```bash
   conda activate wecgrid_env
   ```
5. Install WEC-Grid:
   ```bash
   pip install -e .
   ```
6. (Optional) Install extra dependencies:
   ```bash
   pip install wecgrid[psse]   # PSS®E API support
   ```

---

## WEC-Sim / MATLAB Setup

1. Install MATLAB.
2. Install WEC-Sim ([instructions here](https://wec-sim.github.io/WEC-Sim/main/user/getting_started.html)) and add it to your MATLAB path.
3. Add the MATLAB Python Engine API to your Python environment ([guide](https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html)).

> **Note**: Remember where you downloaded WEC-Sim so you can correctly set the path in WEC-Grid.

---

## PSS®E Setup

1. Install PSS®E (commercial license required).
2. Ensure the PSS®E Python API is accessible in your Python environment. This may involve setting environment variables or modifying the Python path.
3. The easiest method is to use the [pssepath](https://github.com/danifus/pssepath) package:
   ```bash
   pip install wecgrid[psse]
   # or
   pip install pssepath
   ```
4. If this does not work, you can manually configure PSS®E following [this guide](https://psspy.org/psse-help-forum/question/122/how-do-i-import-the-psspy-module-in-a-python-script/).

### Common Issues
- **Bad magic number error**: This typically means the Python version you are using is not compatible with your installed version of PSS®E. See [this forum post](https://psspy.org/psse-help-forum/question/9494/im-trying-to-use-psspy-and-always-i-get-the-same-error-bad-magic-number-in-psspy-bx03xf3rn-someone-can-help-me-to-fix-this-error/) for more details.

Version compatibility:
- **PSS®E 32**: Requires Python 2.5 (32-bit).
- **PSS®E 33**: Requires Python 2.7 (32-bit).
- **PSS®E 34**: Supports Python 2.7, 3.4, 3.7 (all 32-bit).
- **PSS®E 35**: Supports Python 3.9 (64-bit).
