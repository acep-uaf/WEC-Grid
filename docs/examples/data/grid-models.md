# Grid Models
WEC-Grid includes several IEEE standard test systems that provide well-characterized power grid models for research and validation.

## Available Models

### IEEE 14-Bus System
- **Description**: Simple approximation of the American Electric Power system as of February 1962 with 14 buses, 5 generators, 17 lines, 11 loads, and 3 transformers. Does not include line limits and has low base voltages compared to modern systems.
- **Download**: [IEEE 14](../jupyter_notebooks/grid_models/IEEE_14_bus.RAW)
- **Citation**: [Power System Test Case Archive (University of Washington)](https://labs.ece.uw.edu/pstca/pf14/pg_tca14bus.htm)

### IEEE 24-Bus System
- **Description**: IEEE Reliability Test System with 24 buses, 11 generators, 32 lines, 16 loads, 2 shunt impedances, and 6 transformers. Originally developed in 1979 for bulk power system reliability studies and planning applications.
- **Download**: [IEEE 24](../jupyter_notebooks/grid_models/IEEE_24_bus.RAW)
- **Citation**: [IEEE 24-bus reliability test system reference]

### IEEE 30-Bus System
- **Description**: Approximation of the American Electric Power system as of December 1961 with 30 buses, 6 generators, 37 lines, 21 loads, and 4 transformers. Does not include line limits.
- **Download**: [IEEE 30](../jupyter_notebooks/grid_models/IEEE_30_bus.RAW)
- **Citation**: [Power System Test Case Archive (University of Washington)](https://labs.ece.uw.edu/pstca/pf30/pg_tca30bus.htm)

### IEEE 39-Bus System
- **Description**: New England test system with 39 buses, 10 generators, 34 lines, 31 loads, and 12 transformers. Represents the New England power system and is widely used for transient stability studies.
- **Download**: [IEEE 39](../jupyter_notebooks/grid_models/IEEE_39_bus.RAW)
- **Citation**: T. Athay et al., "A Practical Method for the Direct Analysis of Transient Stability," IEEE Trans. on Power Apparatus and Systems, 1979 | [Electric Grid Test Case Repository](https://electricgrids.engr.tamu.edu/electric-grid-test-cases/ieee-39-bus-system/)

### RTS 96
- **Description**: Enhanced IEEE Reliability Test System with 73 buses, 33 generators, 110 lines, and 51 loads. Designed for bulk power system reliability evaluation studies and comparative benchmark studies for reliability evaluation techniques.
- **Download**: [RTS 96](../jupyter_notebooks/grid_models/RTS-96.RAW)
- **Citation**: [Power System Test Case Archive (University of Washington)](https://labs.ece.uw.edu/pstca/rts/pg_tcarts.htm) | [IEEE RTS-1996 Paper](https://home.engineering.iastate.edu/~jdm/ee553/IEEE-RTS1996.pdf)

### RTS-GMLC 96
- **Description**: Grid Modernization Laboratory Consortium version based on the 1979 and 1996 Reliability Test Systems with 73 buses, 98 generators, 105 lines, 51 loads, 3 shunt impedances, and 15 transformers. Features key changes to enable simulations of hourly and 5-minute operations for a full year with renewable energy integration.
- **Download**: [RTS-GMLC](../jupyter_notebooks/grid_models/RTS-GMLC_Hooman.raw)
- **Citation**: [RTS-GMLC 96 Github](https://github.com/GridMod/RTS-GMLC)

### IEEE 118
- **Description**: Approximation of the American Electric Power system (U.S. Midwest) as of December 1962 with 118 buses, 54 generators, 177 lines, 99 loads, and 9 transformers.
- **Download**: [IEEE 118](../jupyter_notebooks/grid_models/IEEE_118_bus.RAW)
- **Citation**: [Power System Test Case Archive (University of Washington)](https://labs.ece.uw.edu/pstca/pf118/pg_tca118bus.htm)

### IEEE 300
- **Description**: Large-scale test case developed by the IEEE Test Systems Task Force under Mike Adibi's direction in 1993 with 300 buses, 69 generators, 306 lines, 197 loads, and 105 transformers.
- **Download**: [IEEE 300](../jupyter_notebooks/grid_models/IEEE_300_bus.raw)
- **Citation**: [Power System Test Case Archive (University of Washington)](https://labs.ece.uw.edu/pstca/pf300/pg_tca300bus.htm)