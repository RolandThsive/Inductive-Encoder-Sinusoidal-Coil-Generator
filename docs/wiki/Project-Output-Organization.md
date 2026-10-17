# 19. Project Output Organization

![Output 1: Project Organisation](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/output_1_organisation.png)

*Output 1. You edit only the parameter files. The generator checks them and writes one new folder
per run.*

```text
Single Generator/
├── Parameters/                 Every setting: the only files you edit
│   ├── Board_Parameters.py       Output, generator mode, PCB layers, vias, clearance, board outline, air gap, receiver IC
│   ├── RX_Parameters.py          Loops, radii, profile, sub-coils, layers, fingers
│   ├── TX_Parameters.py          Turns, pitch, shape, wiring, layers, break style
│   ├── Rotor_Parameters.py       The rotor (metal target)
│   └── Parameters.py             Gathers the four parameter files (do not edit)
├── Generator/
│   ├── Run/                      RunCoilGenerator.py (the program to run; the only one that writes files),
│   │                             CheckParameters.py, OutputFolders.py
│   ├── Checks/                   ParameterRules.py, ConflictRules.py, DesignChecks.py
│   ├── Stator/
│   │   ├── RX/                   RX_Builder, RX_Coils, RX_Profiles, RX_Fingers
│   │   ├── TX/                   TX_Builder, TX_Shapes, TX_Wiring, TX_Windows, TX_Terminal, TX_Electrics
│   │   └── StatorAssembly.py     The finished stator, turned so the TX terminal sits at 0°
│   ├── Rotor/                    RotorBuilder.py
│   └── Core/                     Geometry, layers, copper, KiCad writer, conflict messages
└── Output/
    └── Coil_<Inner Radius>_<Outer Radius>_<Loops>_<Sub-Coils>_<TX Turns>_<Single|Series|Parallel>_<SteppedDiagonal|SteppedArc|Spiral>/
        ├── Stator.kicad_pcb
        ├── Rotor.kicad_pcb
        └── Parameters.txt
```

The folder name carries the board radii, the RX loops and sub-coils, the TX turns, the TX wiring and the TX shape, for example `Coil_15_27_1_1_3_Single_SteppedDiagonal`. A run never overwrites anything: if a folder name already exists, `__1`, `__2` and so on are added. `Parameters.txt` lists every value used, marks the parameters that this design does not use, and records the angle the board was turned by to put the TX terminal at 0°.

The analyser and optimizer (`Analyser_And_Optimizer/` and `OptimizerParameters.py`) are not on main. They are under construction on the [`analyser_and_optimizer` branch](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/tree/analyser_and_optimizer).

## 19.1 Quick Start

```bash
pip install numpy matplotlib

cd "Single Generator"
python Generator/Run/RunCoilGenerator.py              # Check, then write Stator + Rotor
python Generator/Run/RunCoilGenerator.py --check      # Check only, write nothing
```

The generator runs from any folder; it finds the other folders itself. To treat clearance warnings as errors, set `GENERATOR_MODE = "strict"` in `Board_Parameters.py`.

| Previous | Next |
|:---|---:|
| [Suggestive Analysis And Optimization](Suggestive-Analysis-And-Optimization.md) | [KiCad Compatibility](KiCad-Compatibility.md) |
