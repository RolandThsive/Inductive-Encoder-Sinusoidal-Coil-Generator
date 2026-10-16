# 19. Project Output Organization

![Output 1: Project Organisation](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/output_1_organisation.png)

*Output 1. You edit only the parameter files. The generator checks them and writes one new folder
per run.*

```text
Sinusoidal Coil Generator/
├── Parameters/                 Every setting: the only files you edit
│   ├── Board_Parameters.py       Output, PCB layers, vias, clearance, board outline, air gap, receiver IC
│   ├── RX_Parameters.py          Loops, radii, profile, sub-coils, layers, fingers
│   ├── TX_Parameters.py          Turns, pitch, shape, layers, series / parallel, break style
│   ├── Rotor_Parameters.py       The rotor (metal target)
│   └── Parameters.py             Gathers the four board files (do not edit)
├── Generator/
│   ├── RunCoilGenerator.py       The program to run; the only one that writes files
│   ├── StatorGenerator.py        Stator geometry
│   ├── RotorGenerator.py         Rotor geometry
│   ├── TXLayout.py               Resolves the TX layout
│   ├── ParameterChecker.py       Rules for parameters and finished geometry
│   ├── OutputDirectoryManager.py Output folders and Parameters.txt
│   └── CoilElectrics.py          Electrical estimate
└── Output/
    └── Coil_<Inner Radius>_<Outer Radius>_<Loops>_<Sub-Coils>_<TX Turns>_<Single|Series|Parallel>_<SteppedDiagonal|SteppedArc|Spiral>/
        ├── Stator.kicad_pcb
        ├── Rotor.kicad_pcb
        └── Parameters.txt
```

A run never overwrites anything: if a folder name already exists, `__1`, `__2` and so on are added.

The analyser and optimizer (`Analyser_And_Optimizer/` and `OptimizerParameters.py`) are not on main. They are under construction on the [`analyser_and_optimizer` branch](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/tree/analyser_and_optimizer).

## 19.1 Quick Start

```bash
pip install numpy matplotlib

python Generator/RunCoilGenerator.py              # Check, then write Stator + Rotor
python Generator/RunCoilGenerator.py --check      # Check only, write nothing
python Generator/RunCoilGenerator.py --strict     # Treat warnings as errors
```

Every program runs from any folder; it finds the other folders itself.

| Previous | Next |
|:---|---:|
| [Suggestive Analysis And Optimization](Suggestive-Analysis-And-Optimization.md) | [KiCad Compatibility](KiCad-Compatibility.md) |
