[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/acep-uaf/Marine-Grid/v2.0.0)
# Marine-Grid: Integrating Marine Renewable Energy into Power Grid Simulations

<div style="clear: both; text-align: center;">
  <img src="./docs/assets/WEC-Grid_mini_white.png" alt="Marine-Grid Logo" style="width: 80%; height: auto;">
</div>

**Marine-Grid** is an open-source Python library crafted to simulate the integration of marine renewable energy sources (including Wave Energy Converters, tidal, and other ocean energy systems) with power grid simulators like [PSS®E](https://new.siemens.com/global/en/products/energy/services/transmission-distribution-smart-grid/consulting-and-planning/pss-software/pss-e.html) & [PyPSA](https://pypsa.org/).

**Documentation**: [acep-uaf.github.io/Marine-Grid](https://acep-uaf.github.io/Marine-Grid/)

---

### Quick Install (macOS, Python venv)

We recommend Python 3.9 to match pinned dependencies.

1) Clone the repo
```bash
git clone https://github.com/acep-uaf/Marine-Grid
cd Marine-Grid
```

2) Create and activate a virtual environment

<!-- For conda-based setup, see docs/install.md -->

Using Python venv
- macOS (bash/zsh):
  ```bash
  python3 -m venv marinegrid_env
  source marinegrid_env/bin/activate
  ```

3) Upgrade pip
```bash
python -m pip install --upgrade pip
```

4) Install Marine-Grid
```bash
pip install -e .
```

5) Optional (dev tools + tests)
```bash
pip install -e .[dev]
pytest -q
```

Need Windows, Linux, or conda instructions? See the full guide: `docs/install.md`.

---

### Configuration

You can configure paths via code or environment variables.

- Database path
  - Quick (env var): set `MARINEGRID_DB_PATH` to your SQLite database
    - Windows (PowerShell): `$env:MARINEGRID_DB_PATH = "C:\\path\\to\\MarineGrid.db"`
    - macOS/Linux (bash/zsh): `export MARINEGRID_DB_PATH=~/path/to/MarineGrid.db`
  - Persistent (code): `engine.database.set_database_path("/path/to/MarineGrid.db")`
    - This writes a JSON config into your user config directory (e.g., `~/.marinegrid/database_config.json`).

- WEC‑Sim path (MATLAB install)
  - Quick (env var): set `MARINEGRID_WECSIM_PATH` to the WEC‑Sim folder
  - Persistent (code): `engine.wecsim.set_wec_sim_path("/path/to/WEC-Sim")`
    - Stored in your user config directory (e.g., `~/.marinegrid/wecsim_config.json`).

---

### Optional Tools

- Miniconda: Recommended for managing Python versions and binary packages. Download: https://docs.conda.io/en/latest/miniconda.html
- MATLAB + WEC‑Sim: For WEC simulations. Install MATLAB R2021b and WEC‑Sim, then add the MATLAB Engine API for Python to your active environment: https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html
- PSS®E API (Windows): Commercial license required. See: https://new.siemens.com/global/en/products/energy/services/transmission-distribution-smart-grid/consulting-and-planning/pss-software/pss-e.html
