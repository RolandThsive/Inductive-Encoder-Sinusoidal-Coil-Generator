# 26. Project Output Organization

![Output 1: Project Organisation](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/output_1_organisation.png)

*Output 1. You edit only the parameter files. The generator checks them and writes one new folder
per run.*

```text
Single Generator/
├── Parameters/                 Every setting: the only files you edit
│   ├── Board_Parameters.py       Output, generator mode, PCB layers, vias, clearance, board outline, air gap, electrical estimate
│   ├── RX_Parameters.py          Loops, radii, profile, sub-coils, layers, fingers
│   ├── TX_Parameters.py          Turns, pitch, shape, wiring, layers, break style
│   ├── Rotor_Parameters.py       The rotor (metal target)
│   ├── IC_Parameters.py          The receiver IC limits for the electrical estimate
│   ├── SilkScreenSuggestion_Parameters.py   The lead-cutting suggestion on the silkscreen
│   └── Parameters.py             Gathers the five coil parameter files (do not edit)
├── Generator/
│   ├── Run/                      RunCoilGenerator.py (the program to run; the only one that writes files),
│   │                             CheckParameters.py, OutputFolders.py
│   ├── Checks/                   ParameterRules.py, ConflictRules.py, DesignChecks.py
│   ├── Stator/
│   │   ├── RX/                   RX_Builder, RX_Coils, RX_Profiles, RX_Fingers
│   │   ├── TX/                   TX_Builder, TX_Shapes, TX_Wiring, TX_Windows, TX_Terminal, TX_Electrics
│   │   ├── StatorAssembly.py     The finished stator, turned so the TX terminal sits at 0°
│   │   └── LeadCutting_SilkscreenSuggestion.py   The last step: the silkscreen suggestion
│   ├── Rotor/                    RotorBuilder.py
│   └── Core/                     Geometry, board layout, layers, copper, KiCad writer, conflict messages
├── Regression Testing/           run_regression.py, the tests and their References/
└── Output/
    └── Coil_<Inner Radius>_<Outer Radius>_<Loops>_<Sub-Coils>_<TX Turns>_<Single|Series|Parallel>_<SteppedDiagonal|SteppedArc|Spiral>/
        ├── Stator.kicad_pcb
        ├── Rotor.kicad_pcb
        ├── Parameters.txt
        ├── <Folder Name>_Representative.svg   The boards as a picture to look at
        └── <Folder Name>_Actual.svg           The copper 1:1 in mm, one Inkscape layer per copper layer

Dual Generator/
├── Parameters/                 Every dual setting: the only files you edit
│   ├── Dual_Board_Parameters.py  Output, vias, clearance, DUAL_MODE, edges, gap, TX ends, frequency rules, rotor disc
│   ├── Dual_RX1_Parameters.py    RX of set 1 (inner); Dual_RX2_Parameters.py for set 2 (outer)
│   ├── Dual_TX1_Parameters.py    TX ring and frequency of set 1; Dual_TX2_Parameters.py for set 2
│   ├── Dual_Rotor1_Parameters.py Ring 1 of the rotor; Dual_Rotor2_Parameters.py for ring 2
│   ├── Dual_IC1_Parameters.py    IC limits of set 1; Dual_IC2_Parameters.py for set 2
│   ├── Dual_SilkScreenSuggestion_Parameters.py   The lead-cutting suggestion for both sets
│   ├── Dual_Fixed_Parameters.py  What every dual board fixes (do not change)
│   └── Dual_Parameters.py        Gathers the files (do not edit)
├── Dual_Generator/
│   ├── Run/                      Dual_RunCoilGenerator.py (the program to run), Dual_OutputFolders.py
│   ├── Checks/                   Dual_CheckParameters.py, Dual_ParameterRules.py, Dual_DesignChecks.py
│   ├── Core/                     Dual_SetParameters.py (one Single Generator parameter set per coil set), Dual_TrackLayout.py (DUAL_MODE)
│   ├── Stator/                   Dual_StatorAssembler.py, Dual_LeadCutting_SilkscreenSuggestion.py
│   └── Rotor/                    Dual_RotorBuilder.py
├── Regression Testing/           run_regression.py, the tests and their References/
└── Output/
    └── DualCoil_<Bore Radius>_<Outline Radius>_<Set 1 Loops>x<Set 2 Loops>_<Set 1 TX Turns>x<Set 2 TX Turns>/
        ├── Stator.kicad_pcb
        ├── Rotor.kicad_pcb
        ├── Parameters.txt
        ├── <Folder Name>_Representative.svg   The boards as a picture to look at
        └── <Folder Name>_Actual.svg           The copper 1:1 in mm, one Inkscape layer per copper layer

resources/                      Shared by both generators
├── SilkscreenFont.py             The stroke font of the silkscreen lead names
├── RegressionTools.py            The parser and measuring code of both test suites
├── RepresentativeSVGMaker.py     Draws <Folder Name>_Representative.svg from the written boards
└── ActualSVGMaker.py             Draws <Folder Name>_Actual.svg from the written boards
```

The Dual Generator imports the Single Generator's `Generator` package from the `Single Generator` folder next to it,
so the two folders must stay side by side. It changes nothing in the Single Generator and leaves no `__pycache__` there.
Its folder name carries the radii, the loops of both sets and the TX turns of both sets, for example
`DualCoil_7.25_26.875_1x16_4x4`.

The Single Generator's folder name carries the board radii, the RX loops and sub-coils, the TX turns, the TX wiring and the TX shape, for example `Coil_15_27_1_1_3_Single_SteppedDiagonal`. A run never overwrites anything: if a folder name already exists, `__1`, `__2` and so on are added. `Parameters.txt` lists every value used, marks the parameters that this design does not use, and records the angle the board was turned by to put the TX terminal at 0°. The two SVG pictures are drawn from the written boards at the end of the run; see [Output Pictures](Output-Pictures.md).

The analyser and optimizer (`Analyser_And_Optimizer/` and `OptimizerParameters.py`) are not on main. They are under construction on the [`analyser_and_optimizer` branch](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/tree/analyser_and_optimizer).

## 26.1 Quick Start

```bash
pip install numpy

cd "Single Generator"
python Generator/Run/RunCoilGenerator.py              # Check, then write Stator + Rotor
python Generator/Run/RunCoilGenerator.py --check      # Check only, write nothing

cd "../Dual Generator"
python Dual_Generator/Run/Dual_RunCoilGenerator.py    # The Dual Generator: check, then write Stator + Rotor
```

The generator runs from any folder; it finds the other folders itself. To treat every warning about the finished boards (clearances, the board edge, the page, the rotor) as an error, set `GENERATOR_MODE = "strict"` in `Board_Parameters.py`.

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [Suggestive Analysis And Optimization](Suggestive-Analysis-And-Optimization.md) | [Output Pictures](Output-Pictures.md) |
