# Software Design

WEC-Grid is a bridge tool bringing together Wave Energy Converter Modeling and Grid Modeling.

Engine is the core component responsible for managing the interactions between the wave energy converters and the electrical grid. Manages the whole thing.

We have our modelers Power System Modelers (PyPSA & PSSE )and Wave Energy Converter Modeler (WEC-SIM)


<div style="clear: both; text-align: center;">
  <img src="assets/WEC_Grid_sequence.png" alt="UML Sequence Diagram" style="width: 30%; height: auto;">
</div>

<div style="clear: both; text-align: center;">
  <img src="assets/WEC_Grid_workflow.png" alt="UML Workflow Diagram" style="width: 30%; height: auto;">
</div>