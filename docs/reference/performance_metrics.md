# Performance Metrics

This page summarizes the benchmarking results for **WEC-Grid**, evaluating scalability and performance across different grid sizes and WEC farm configurations using the **PSS®E** and **PyPSA** modelers.

---

## Test Environment
- **Operating System**: Windows 10  
- **Processor**: Intel i7 dual-core, 4 logical CPUs @ 2.6 GHz  
- **Memory**: 7.9 GB RAM  
- **Threading**: Linear algebra threading disabled (MKL/OPENBLAS/NUMEXPR = 1)  

Each datapoint represents the **average of 10 runs**, with warm-up iterations discarded. This ensures stable and reproducible results.

---

## Test Cases
- **IEEE standard grids**: 14, 24, 30, 39, 96 (RTS), 118, and 300 buses. These are widely used benchmark systems in power systems research.  
- **PSS®E**: limited to IEEE 14–39 bus systems (software constraint).  
- **PyPSA**: ran the full set up to IEEE 300 bus system.  

*What this means*: "Buses" represent electrical nodes in the grid (connection points for generators, loads, and lines). Scaling tests with different bus counts evaluate how runtime grows as the network size increases.

---

## Results

### Scaling with Grid Size
Simulation time grew approximately **linearly** with the number of buses for both modelers:
- **PSS®E**: ~0.50 seconds per bus, intercept ~8.9 s, R² = 0.97.  
- **PyPSA**: ~0.64 seconds per bus, intercept ~101.3 s, R² = 0.99.  
- **Memory demand**: ~0.0002 GB per bus (linear scaling).  
- **CPU utilization**: consistently >98%, confirming efficient single-core use.  

*What this means*: Doubling the number of buses roughly doubles the runtime. Both solvers behave predictably, which is important for planning large-scale studies.

<div style="clear: both; text-align: center;">
  <img src="assets/grid_scaling.png" alt="Simulation time vs. grid size" style="width: 100%; height: auto;">
</div>

---

### Scaling with WEC Farms
For the IEEE 39-bus system, simulations were run with 1–3 synthetic WEC farms:
- **PSS®E**: ~30% fixed runtime overhead when enabling WECs, with little change beyond the first farm.  
- **PyPSA**: smoother incremental growth (+3–6% across 1–3 farms).  
- **Memory overhead**: negligible (<5 MB per farm).  

*What this means*: Adding WEC farms increases runtime slightly, but overhead remains modest. The results show that scaling up the number of WECs is computationally feasible.

<div style="clear: both; text-align: center;">
  <img src="assets/wec_scaling.png" alt="Simulation time vs. number of WEC farms" style="width: 100%; height: auto;">
</div>

---


### Regression Fits
Runtime fits the linear model:

$T(N) \approx aN + b$

where:
- **a** = slope (runtime per bus) – how much extra time is needed for each additional bus.  
- **b** = fixed overhead – baseline runtime even for the smallest system (startup and initialization cost).  
- **R²** = fit quality – a value close to 1.0 means the linear model explains the data very well.  

| Backend       | Slope *a* (s/bus) | Intercept *b* (s) | R²   |
|---------------|-------------------|-------------------|------|
| PSS®E         | 0.50              | 8.9               | 0.97 |
| PyPSA         | 0.64              | 101.3             | 0.99 |

*What this means*: For example, with PSS®E, adding 10 more buses adds about 5 seconds to the runtime, while PyPSA adds about 6 seconds plus a higher startup cost. The very high R² confirms that scaling is highly predictable.

---

## Conclusions
- **WEC-Grid introduces modest runtime costs** compared to baseline power flow studies.  
- **PyPSA**: scales well to large grids (up to 300 buses), with small proportional WEC overheads.  
- **PSS®E**: faster for small grids, but shows a larger fixed overhead when WEC models are enabled.  
- Memory demand and CPU use remain efficient across both solvers.  

Overall, WEC-Grid provides **predictable, scalable performance** for integration studies, supporting both small and large network sizes with minimal overhead from WEC modeling.
