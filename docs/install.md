# Installation

## System Requirements
- Python: 3.7+ (3.9 recommended)
- Operating System: Windows, macOS, or Linux
  - Windows recommended for full functionality with PSS®E (Windows‑only)
- Git: Required to clone the repository

### Power System Software (optional)
- PSS®E: Version 34 or later (commercial, Windows‑only)
- PyPSA: Installed via WEC‑Grid dependencies

### WEC Modeling Software (optional)
- MATLAB: R2021b (tested)
- WEC‑Sim: https://wec-sim.github.io/WEC-Sim/main/user/getting_started.html

---

## Choose Your OS

Use the tabs below to get tailored steps for your platform and environment manager.

=== "Windows"

    === "Conda"

        1. Clone the repo
           ```bash
           git clone https://github.com/acep-uaf/WEC-Grid
           cd WEC-Grid
           ```
        2. Create and activate env
           ```bash
           conda create -n wecgrid_env python=3.9
           conda activate wecgrid_env
           ```
        3. Upgrade pip
           ```bash
           python -m pip install --upgrade pip
           ```
        4. Install WEC‑Grid
           ```bash
           pip install -e .
           ```
        5. Optional extras
           ```bash
           pip install -e .[psse]   # PSS®E helper
           pip install -e .[dev]    # tests, tooling
           pytest -q
           ```
        6. Verify
           ```bash
           python -c "import wecgrid; print(wecgrid.__version__)"
           ```

    === "Python venv (PowerShell)"

        1. Clone the repo
            ```powershell
            git clone https://github.com/acep-uaf/WEC-Grid
            cd WEC-Grid
            ```
        2. Create and activate env
            ```powershell
            py -3.9 -m venv wecgrid_env
            .\wecgrid_env\Scripts\Activate.ps1
            ```
        3. Upgrade pip
            ```powershell
            python -m pip install --upgrade pip
            ```
        4. Install WEC‑Grid
            ```powershell
            pip install -e .
            ```
        5. Optional extras (same as above)

        6. Verify
            ```powershell
            python -c "import wecgrid; print(wecgrid.__version__)"
            ```

    === "Python venv (CMD)"

        1. Clone the repo
            ```bat
            git clone https://github.com/acep-uaf/WEC-Grid
            cd WEC-Grid
            ```
        2. Create and activate env
            ```bat
            py -3.9 -m venv wecgrid_env
            .\wecgrid_env\Scripts\activate.bat
            ```
        3. Upgrade pip
            ```bat
            python -m pip install --upgrade pip
            ```
        4. Install WEC‑Grid
            ```bat
            pip install -e .
            ```
        5. Optional extras (same as above)

        6. Verify
            ```bat
            python -c "import wecgrid; print(wecgrid.__version__)"
            ```

=== "macOS"

    === "Conda"

        1. Clone the repo
            ```bash
            git clone https://github.com/acep-uaf/WEC-Grid
            cd WEC-Grid
            ```
        2. Create and activate env
            ```bash
            conda create -n wecgrid_env python=3.9
            conda activate wecgrid_env
            ```
        3. Upgrade pip
            ```bash
            python -m pip install --upgrade pip
            ```
        4. Install WEC‑Grid
            ```bash
            pip install -e .
            ```
        5. Optional extras
            ```bash
            pip install -e .[dev]
            pytest -q
            ```
        6. Verify
            ```bash
            python -c "import wecgrid; print(wecgrid.__version__)"
            ```

    === "Python venv"

        1. Clone the repo
            ```bash
            git clone https://github.com/acep-uaf/WEC-Grid
            cd WEC-Grid
            ```
        2. Create and activate env
            ```bash
            python3 -m venv wecgrid_env
            source wecgrid_env/bin/activate
            ```
        3. Upgrade pip
            ```bash
            python -m pip install --upgrade pip
            ```
        4. Install WEC‑Grid
            ```bash
            pip install -e .
            ```
        5. Optional extras (same as above)

        6. Verify
            ```bash
            python -c "import wecgrid; print(wecgrid.__version__)"
            ```

=== "Linux"

    === "Conda"

        1. Clone the repo
            ```bash
            git clone https://github.com/acep-uaf/WEC-Grid
            cd WEC-Grid
            ```
        2. Create and activate env
            ```bash
            conda create -n wecgrid_env python=3.9
            conda activate wecgrid_env
            ```
        3. Upgrade pip
            ```bash
            python -m pip install --upgrade pip
            ```
        4. Install WEC‑Grid
            ```bash
            pip install -e .
            ```
        5. Optional extras
            ```bash
            pip install -e .[dev]
            pytest -q
            ```
        6. Verify
            ```bash
            python -c "import wecgrid; print(wecgrid.__version__)"
            ```

    === "Python venv"

        1. Install venv if needed
            ```bash
            sudo apt-get update && sudo apt-get install -y python3-venv
            ```
        2. Clone the repo
            ```bash
            git clone https://github.com/acep-uaf/WEC-Grid
            cd WEC-Grid
            ```
        3. Create and activate env
            ```bash
            python3 -m venv wecgrid_env
            source wecgrid_env/bin/activate
            ```
        4. Upgrade pip
            ```bash
            python -m pip install --upgrade pip
            ```
        5. Install WEC‑Grid
            ```bash
            pip install -e .
            ```
        6. Optional extras (same as above)

        7. Verify
            ```bash
            python -c "import wecgrid; print(wecgrid.__version__)"
            ```

Notes
- If `python=3.9` is unavailable on your default conda channels, try: `conda create -n wecgrid_env -c conda-forge python=3.9`.
- On Linux, using conda is often simpler for scientific Python stacks with native libs.



## WEC‑Sim / MATLAB Setup (Optional)

1. Install MATLAB (R2021b recommended/tested).
2. Install WEC‑Sim: https://wec-sim.github.io/WEC-Sim/main/user/getting_started.html
3. Install the MATLAB Engine API for Python into your active environment:
   - Official guide: https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html
   - Typical flow (with env activated):
     ```bash
     # Replace <matlabroot> with your MATLAB install path
     cd <matlabroot>/extern/engines/python
     python -m pip install --upgrade pip
     python -m pip install .
     ```

---

## PSS®E Setup (Windows only)

1. Install PSS®E (commercial license).
2. Ensure your Python version matches your PSS®E version (see below).
3. Make PSS®E’s Python API importable. Easiest path is the helper:
   ```bash
   pip install -e .[psse]
   # or
   pip install pssepath
   ```
4. If needed, manually configure env vars/PATH per Siemens docs or community guides, e.g.:
   https://psspy.org/psse-help-forum/question/122/how-do-i-import-the-psspy-module-in-a-python-script/

Common issue
- “Bad magic number” when importing `psspy` usually indicates a Python version mismatch: https://psspy.org/psse-help-forum/question/9494/im-trying-to-use-psspy-and-always-i-get-the-same-error-bad-magic-number-in-psspy-bx03xf3rn-someone-can-help-me-to-fix-this-error/

PSS®E ↔ Python compatibility (typical)
- PSS®E 32: Python 2.5 (32‑bit)
- PSS®E 33: Python 2.7 (32‑bit)
- PSS®E 34: Python 2.7 / 3.4 / 3.7 (32‑bit)
- PSS®E 35: Python 3.9 (64‑bit)

---

## Troubleshooting
- Always upgrade `pip` inside your env: `python -m pip install --upgrade pip`.
- If pip builds fail on Linux/macOS, prefer conda to avoid compiler issues.
- On Debian/Ubuntu, if `python3 -m venv` fails, install: `sudo apt-get install python3-venv`.
- Quick verification: `python -c "import wecgrid; print(wecgrid.__version__)"`.
