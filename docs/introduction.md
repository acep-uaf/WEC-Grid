---
layout: default
title: Introduction
permalink: /introduction.html
---

# Introduction

Amidst the global shift toward sustainable energy, Wave Energy Converters (WECs) and Current Energy Converters (CECs) stand out as promising technologies. They tap the ocean’s vast potential, but integrating them into complex power-grid environments (e.g., microgrids or large transmission networks) demands robust modeling, testing, and analysis.

**WEC-Grid** bridges that gap by providing an open-source, modular framework—delivered here as a set of Jupyter notebooks and Python/Julia wrappers—that seamlessly links marine hydrodynamic models (WEC-SIM) with industry‐standard power system solvers (PSS®E, PyPSA).

<p align="center">
  <img src="/WEC-Grid/images/example_viz.png" alt="WEC-Grid Data Visualization" width="600">
</p>

Figure: Example of WEC-Grid’s data-visualization pipeline (voltage & power over time).

## Motivation & Significance

1. **Gap in Modeling**  
   - Traditional grid simulation tools (PSS®E, PowerFactory, PyPSA) do not natively model hydrodynamic interactions of WECs.  
   - WEC-SIM (MATLAB) captures wave physics but lacks direct coupling to power flows.  
   - Without integration, researchers often resort to oversimplified “dispatch curves” or static look-ups, which can misrepresent true WEC dynamics.

2. **WEC-Grid’s Contribution**  
   - Provides a “bridge” pattern: wrappers that translate WEC outputs (from WEC-SIM) into per-unit injections for PSS®E/PyPSA.  
   - Supports benchmarking across multiple solvers (commercial vs open-source).  
   - Facilitates quasi–steady-state (QSS) studies of WEC integration, enabling preliminary grid stability analyses under realistic wave conditions.

3. **Scientific & Future Research Outlook**  
   - Enables new research on wave energy integration at scale (fault analysis, high-penetration studies).  
   - Lays the foundation for future transient/dynamic coupling (e.g., using PowerDynamics.jl for frequency-domain simulations).  
   - Opens doors for site-specific optimization, hybrid-renewable co-simulation, and reproducible workflows.

> *“WEC-Grid uniquely bridges hydrodynamics and electrical system simulation, supporting academic exploration and real-world industry evaluations.”*  
> — Excerpt from Barajas-Ritchie & Cotilla-Sanchez, *WEC-Grid: A Software Tool for Integrating Wave Energy Converter Models*, SoftwareX, 2025.