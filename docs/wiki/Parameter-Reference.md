# 15. Parameter Reference

Every setting lives in a parameter file in `Single Generator/Parameters/`. These are the only files you edit. Units are millimetres,
degrees and hertz unless a name says otherwise. The **Range** column is what the parameter checker accepts; "None"
means the generator works the value out itself. The Web Tool shows the same names in its Advanced mode.

`Parameters.py` only gathers the four parameter files and is not edited. `OptimizerParameters.py` belongs to the optimizer, which is
under construction on the [`analyser_and_optimizer` branch](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/tree/analyser_and_optimizer).

> [!NOTE]
> Defaults are those of the parameter files in `Single Generator/Parameters/` on `main`. Settings marked *only if* are greyed out ("not used now") in
> the Web Tool when the design does not use them.

## 15.1 Board (`Board_Parameters.py`)

### 15.1.1 Output

| Name | Default | Range | Meaning |
|---|---|---|---|
| `OUTPUT_DIR` | `"Output"` | text | Folder in which each run's `Coil_...` folder is made. A relative path is taken from the `Single Generator` folder; a full path is used as it is. |
| `STATOR_FILE`, `ROTOR_FILE` | `Stator.kicad_pcb`, `Rotor.kicad_pcb` | file names | Names of the two boards inside each run folder. They must differ and should end in `.kicad_pcb`. |
| `GENERATOR_MODE` | `"normal"` | `normal`, `strict` | What a clearance warning on the finished boards does. `normal`: a gap smaller than `MIN_CLEARANCE_MM` is a warning and the boards are written. `strict`: every such warning is an error and nothing is written. Copper that overlaps copper of another net (a short) is always an error. Capitals do not matter. |
| `CENTER_X_MM`, `CENTER_Y_MM` | 100, 100 | number | Position of the sensor axis on the KiCad page. |
| `PAGE_SIZE_MM` | (200, 200) | pair | KiCad "User" page size (the generator enlarges it so the title block never overlaps the board). |

### 15.1.2 Stator board

| Name | Default | Range | Meaning |
|---|---|---|---|
| `PCB_LAYERS` | 2 | 2 or 4 | Copper layers of the stator. All vias are through-hole. Keep layers without a coil free of copper pours under the coil area: a plane there acts like an extra target. |
| `VIA_DIAMETER_MM` | 0.8 | > 0 | Via pad diameter. |
| `VIA_DRILL_MM` | 0.4 | > 0, below the diameter | Via drill. |
| `MIN_CLEARANCE_MM` | 0.2 | > 0 | Copper-to-copper rule the generator must respect. |
| `INNER_EDGE_INSET_MM` | 1.2 | ≥ 0 | Centre hole radius = RX band start minus this, when `INNER_EDGE_RADIUS_MM` is None. |
| `INNER_EDGE_RADIUS_MM` | 15.0 | > 0 or None | Fixed centre-hole radius. When the RX band is given, both are used as given. |
| `OUTER_EDGE_OFFSET_MM` | 4.0 | ≥ 0 | Outer edge = RX band end plus this, when `OUTER_EDGE_RADIUS_MM` is None. |
| `OUTER_EDGE_RADIUS_MM` | 27.0 | > 0 or None | Fixed outer board radius. With None, the edge is the largest of the offset rule, the TX tail end plus the margin, and the bridging-finger tip plus the margin. |
| `OUTER_EDGE_TAIL_MARGIN_MM` | 0.7 | ≥ 0 | Margin used by the rule above. |
| `EDGE_LINE_WIDTH_MM` | 0.05 | 0 to 1 | Line width of the `Edge.Cuts` outline. |

### 15.1.3 Mechanical assumptions

| Name | Default | Range | Meaning |
|---|---|---|---|
| `AIR_GAP_MM` | 1.0 | > 0 | Stator top copper to rotor copper. |
| `PCB_THICKNESS_MM` | 1.6 | > 0 | Stator board thickness. |
| `EXCITATION_FREQ_HZ` | 3.5e6 | > 0 | TX oscillator frequency aimed for, with the rotor in place. The electrical estimate sizes the tank capacitors for it; the rotor summary uses it for the skin depth. A warning appears far outside 1 to 10 MHz. |

### 15.1.4 Electrical estimate

| Name | Default | Range | Meaning |
|---|---|---|---|
| `RECEIVER_IC` | `"IPS2550"` | `"IPS2550"`, `"IPS2200"`, None | The IC the coil is checked against (see [Electrical Estimate](Electrical-Estimate.md)). None switches the checks off. |
| `COPPER_THICKNESS_UM` | 35 | 0 to 500 | Stator copper thickness (35 µm = 1 oz). Sets TX resistance and Q. |

## 15.2 RX (`RX_Parameters.py`)

### 15.2.1 Size and periodicity

| Name | Default | Range | Meaning |
|---|---|---|---|
| `LOOPS` | 1 | 1 to 16 | Electrical periods per mechanical turn, and the number of rotor sectors. Unique range = 360° / `LOOPS`. |
| `INSIDE_RADIUS_MM`, `OUTSIDE_RADIUS_MM` | 16.2, 21.4 | > 0 or None | The inner and outer radius of the RX band (centre line of the traces). With all four band values None, the band is fitted to the board edges: it starts `INNER_EDGE_INSET_MM` outside the centre hole and ends where the TX turns, the TX tail and the margins leave room. |
| `RX_R_BASE_MM`, `RX_A_MM` | None, None | > 0 or None | The band by its centre (`r_base`) and swing (`A`): band = `r_base − A` to `r_base + A`. Signal grows about with `r_base × A`. |
| `RX_TRACE_WIDTH_MM` | 0.2 | > 0 | RX trace width. |
| `RX_NET_PHASE_0_2`, `RX_NET_PHASE_1_3` | `"2"`, `"1"` | text, different | Net names of the SIN pair (phases 0 and 2) and the COS pair (phases 1 and 3). |

The band is given in **one** of two ways (the other pair None), or from the board edges when all four are None. The
two values of a pair go together. See [Web Tool](Web-Tool.md) for the None switches.

### 15.2.2 Shape

| Name | Default | Range | Meaning |
|---|---|---|---|
| `RX_PROFILE` | `"equal_area"` | `equal_area`, `cosine_r` | The shape of the RX curves. See [RX Profiles](RX-Profiles.md). A field-compensated profile is a research topic and is not offered now. |
| `STEPS_PER_LOOP` | `"auto"` | "auto" or an integer, a multiple of 8, 48 to 4096 | Chords (polyline segments) per electrical period. "auto" = the smallest multiple of 8 whose midpoint chord error is within `RX_CHORD_TOLERANCE_MM`, at most 1024 (a warning appears if that is not enough). Sub-coils may raise the count. A whole number is used exactly, and the tolerance then only drives the chord-error warning. |
| `RX_CHORD_TOLERANCE_MM` | 0.001 | ≥ 0.001 | How far a straight chord may lie from the true RX curve, in mm (0.001 = 1 micron, also the smallest value allowed; finer adds points, not accuracy). |

### 15.2.3 Sub-coils

| Name | Default | Range | Meaning |
|---|---|---|---|
| `RX_SUBCOILS` | 1 | 1, 2 or 3 | Sub-coils per coil (distributed winding, as in the Renesas IPS2200 reference design). Each coil stays one closed series loop. |
| `RX_SUBCOIL_SPLIT_ELEC_DEG` | 45.0 | > 0 (*only if* sub-coils ≥ 2) | Electrical angle between sub-coils. Use 45 for 2, and 30 for 3. Two sub-coils give signal × 2·cos(d/2) (1.85× at 45°); harmonic *h* × 2·cos(h·d/2) (3rd and 5th down about 59 % at 45°, 3rd removed at 60°, 5th removed at 36°). |

### 15.2.4 Layers and vias

| Name | Default | Range | Meaning |
|---|---|---|---|
| `RX_LAYER_A`, `RX_LAYER_B` | 1, 2 | 1 to 4, different (*only if* 4 layers) | The two layers of the RX coils: 1 = Top, 2 = Inner-1, 3 = Inner-2, 4 = Bottom. A carries the rising edges, B the falling edges. Top + Inner-1 sit closest together in a standard stack-up. |
| `RX_RISING_EDGE_LAYER` | `"F.Cu"` | `F.Cu`, `B.Cu` (*only if* 2 layers) | Which layer carries the rising edges. |
| `RX_VIA_ELECTRICAL_DEG` | 90.0 | 50 to 130 | Electrical angle of the outer-tip layer-swap via (90 = exactly on the tip). |

### 15.2.5 Bridging fingers

| Name | Default | Range | Meaning |
|---|---|---|---|
| `RX_TABS` | `"all"` | `all`, `single`, `none` | Fingers that leave the RX band, cross over the TX turns and return, so the coils can be broken out outside the TX ring. `all` = every outer tip of every phase; `single` = one per coil (two fingers in all), on neighbouring outer tips, with the TX terminal placed as close to them as the clearances allow; `none` = no fingers. |
| `RX_TAB_LAYER` | `"auto"` | auto, 1 to 4 | Layer of the fingers. "auto" = the RX layer nearest the top that carries no TX turn. |
| `RX_TAB_LENGTH_MM` | 3.0 | ≥ 0 | The exact finger length: the finger reaches `OUTSIDE_RADIUS_MM` plus this. It is never changed for you. When it is too short to clear the outermost TX turn (or the outermost go-around bracket) the generator stops and names the length it needs ("Set RX_TAB_LENGTH_MM to at least ..."). A longer TX pitch needs longer fingers. |
| `RX_TAB_WIDTH_MM` | 1.0 | > 0 | Spacing of the finger's two legs. Keep at 0.6 or more for etching; narrower disturbs the signal less. |

## 15.3 TX (`TX_Parameters.py`)

Layers are numbered 1 = Top, 2 = Inner-1, 3 = Inner-2, 4 = Bottom (a 2-layer board has 1 and 4).

**The TX terminal has no setting.** The generator builds a probe TX at 0°, sweeps the terminal (tail, via, steps or arcs, windows) round the ring against the real RX copper and keeps the place with the largest gap (with `RX_TABS = "single"`, the place nearest the two fingers that keeps `MIN_CLEARANCE_MM`). The whole board is then rotated so that the terminal sits at 0° (to the right). The rotation is printed and written to `Parameters.txt`.

### 15.3.1 Turns

| Name | Default | Range | Meaning |
|---|---|---|---|
| `TX_NET` | `"TX"` | text | Net name of the TX coil. |
| `TX_TURNS` | 3 | 1 to 50 | Complete turns **per TX layer**. |
| `TX_OFFSET_MM` | 1.1 | > 0 | First turn radius = RX outside radius plus this. |
| `TX_PITCH_MM` | 0.6 | > 0 | Radial pitch between turns. |
| `TX_TRACE_WIDTH_MM` | 0.2 | > 0 | TX trace width. |
| `TX_STEPS` | `"auto"` | "auto" or a whole number, 12 to 20000 | Polyline points per TX turn. "auto" = as many as `TX_CHORD_TOLERANCE_MM` needs on the outermost full turn (the worst case), rounded up to a multiple of 8, at least 48. A whole number is used exactly. |
| `TX_CHORD_TOLERANCE_MM` | 0.001 | ≥ 0.001 | How far a straight chord of a TX turn may lie from the true circle, in mm (1 micron, also the smallest value allowed). |
| `TX_TAIL_EXTRA_MM` | 2.0 | ≥ 0 | Radial tail that carries the TX terminal. |
| `TX_SHAPE` | `"stepped_diagonal"` | `stepped_diagonal`, `stepped_arc`, `spiral` | Concentric circles joined by straight steps, concentric circles joined by arcs centred on the terminal via (as on the Renesas reference boards), or one smooth Archimedean spiral (use it when the pitch is tight). Capitals do not matter. |
| `TX_STEPPED_ARC_RADIUS_MM` | `"auto"` | "auto" or a number above 0, up to 20 (*only if* stepped_arc) | Radius of the innermost arc, from the centre of the terminal via. Arc `n` has the radius this + n × `TX_PITCH_MM`. "auto" = the larger of `TX_PITCH_MM` and via radius + half a TX trace + `MIN_CLEARANCE_MM`, plus 0.02 mm and the chord sag (0.72 mm on the example board). A number must be larger than `TX_PITCH_MM` and smaller than `TX_PITCH_MM + TX_TAIL_EXTRA_MM` (errors otherwise); below the via clearance radius it warns. |
| `TX_STEPPED_ANGLE_DEG` | 45 | 5 to 90 (*only if* stepped_diagonal) | Angle of the steps, measured from the turn: 90 = radial, smaller = a longer slope. Neighbouring steps have a gap of pitch × cos(angle) − width; above about 45° with the defaults that is below `MIN_CLEARANCE_MM`, and the steps are staggered automatically. |
| `TX_INSIDE_VIA_DISTANCE_MM` | 0.3 | −3 to 3 (*not used by* stepped_arc) | Moves the TX terminal via towards the centre (negative = outwards). 0 = on the trace ends, which is closer to the next turn than the clearance allows with the default via and pitch. Keep below `TX_OFFSET_MM` − via radius − half an RX trace − clearance (0.4 mm with the defaults). |

### 15.3.2 TX layers

| Name | Default | Range | Meaning |
|---|---|---|---|
| `TX_WIRING` | `"single"` | `single`, `series`, `parallel` | How many layers carry TX turns and how they are joined. `single`: `TX_TURNS` turns on `TX_LAYER_A`, the inner tail on the underpass layer. `series`: `TX_TURNS` turns on each of two layers, joined by a via at the inner end (two spirals, same sense, fields add). `parallel`: the same turns on both layers, stitched through vias around the terminal (about 6 % more signal and twice the Q in the model). Put `TX_LAYER_A` on Top for parallel. Capitals do not matter. |
| `TX_LAYER_A` | 4 | 1 to 4 | The TX layer (or, for series, the spiral that runs inwards from the terminal). |
| `TX_LAYER_B` | 1 | 1 to 4, different (*only if* series or parallel) | The second TX layer (or the spiral that runs back out). |
| `TX_SERIES_UNDERPASS_LAYER` | `"auto"` | auto, 1 to 4 (*only if* single or series) | Layer of the inner tail (single) and of the go-around brackets. |
| `TX_PARALLEL_BREAK_STYLE` | `"stitched"` | `stitched`, `staggered` (*only if* parallel) | How the turns make way for a finger. `stitched`: the turns stop at vias on each side of the finger and the other layer carries the current past it. `staggered`: go-around, with brackets on the other layer. |

Examples: TX on Bottom with the tail on Top is the original layout (the default). TX on Top gives about 15 % (0.8 mm
board) to 30 % (1.6 mm board) more receiver signal per TX volt in the model. Series on layers 1 and 4 is the 2-layer
layout of Hoxha et al. 2022 (Fig. 2); series on 1 and 3 follows the Renesas IPS2200 reference (4-layer board, RX on 1
and 2).

A series TX always makes way for fingers by going around them ("staggered"). All TX turns are one net, so KiCad's DRC
cannot see a TX turn touching another: the generator checks the clearance itself and warns.

## 15.4 Rotor (`Rotor_Parameters.py`)

| Name | Default | Range | Meaning |
|---|---|---|---|
| `ROTOR_MODE` | `"according_to_stator"` | `according_to_stator`, `custom` | Generate the rotor from the stator, or use only the `ROTOR_CUSTOM_*` values. |

### 15.4.1 According to stator

| Name | Default | Range | Meaning |
|---|---|---|---|
| `ROTOR_AUTO_DUTY` | 0.5 | 0 to 1, exclusive | Metal fraction of each period. A fraction k/h has no h-th harmonic in the pattern, but copper edges crowd the field, which moves the best value; finding it needs an eddy-current model or a test rotor. |
| `ROTOR_AUTO_START_ANGLE_DEG` | 0.0 | number | Mechanical angle of the first sector edge. |
| `ROTOR_AUTO_COVER_TX` | True | True or False | True: the copper runs over the TX turns and ends `ROTOR_AUTO_TX_OVERHANG_MM` past the outermost turn, as in Renesas reference designs (5 to 8 % more signal in the model). False: the older rule below. |
| `ROTOR_AUTO_TX_OVERHANG_MM` | 0.5 | −20 to 20 (*only if* cover) | Millimetres past the outer edge of the outermost TX turn (negative = ends over the TX turns). |
| `ROTOR_AUTO_EXTENSION_MM` | None | number or None | How far the copper reaches past the RX band on both edges. None = `AIR_GAP_MM`. |
| `ROTOR_AUTO_EXTENSION_INNER_MM` | None | number or None | Inner edge only. None = `ROTOR_AUTO_EXTENSION_MM`. |
| `ROTOR_AUTO_EXTENSION_OUTER_MM` | None | number or None (*only if* not cover) | Outer edge only. |
| `ROTOR_AUTO_TX_CLEARANCE_MM` | 0.1 | ≥ 0 (*only if* not cover) | Copper stays this far inside the TX ring. |
| `ROTOR_AUTO_EDGE_CLEARANCE_MM` | 0.5 | ≥ 0 | Copper stays this far from the bore edge and the outline. |
| `ROTOR_AUTO_COPPER_LAYERS` | `["F.Cu"]` | layer list | Layer(s) carrying the metal sectors. Mount the copper side towards the stator. |

### 15.4.2 Custom

| Name | Default | Range | Meaning |
|---|---|---|---|
| `ROTOR_CUSTOM_SECTORS` | 1 | 1 to 64 | Number of sectors. It should equal `LOOPS`. |
| `ROTOR_CUSTOM_DUTY` | 0.5 | 0 to 1, exclusive | Metal fraction. |
| `ROTOR_CUSTOM_START_ANGLE_DEG` | 0.0 | number | Mechanical angle of the first sector edge. |
| `ROTOR_CUSTOM_INNER_RADIUS_MM`, `ROTOR_CUSTOM_OUTER_RADIUS_MM` | 15.53, 24.3 | > 0 | Copper inner and outer radius. |
| `ROTOR_CUSTOM_COPPER_LAYERS` | `["F.Cu"]` | layer list | Layer(s) carrying the copper. |
| `ROTOR_CUSTOM_OUTLINE_RADIUS_MM` | 27.0 | > 0 or None | Outer board edge (None = no outline). |
| `ROTOR_CUSTOM_BORE_RADIUS_MM` | 15.0 | > 0 or None | Centre hole (None = no hole). |

### 15.4.3 Both modes

| Name | Default | Range | Meaning |
|---|---|---|---|
| `ROTOR_PCB_THICKNESS_MM` | None | > 0 up to 20, or None | Thickness of the rotor board written into the KiCad file. None = the stator's `PCB_THICKNESS_MM`. It changes nothing in the copper. |
| `ROTOR_ARC_STEPS_PER_SECTOR` | `"auto"` | "auto" or a whole number, 8 to 5000 | Polygon points on every circular arc of a sector. "auto" = as many as `ROTOR_CHORD_TOLERANCE_MM` needs (at least 8). A whole number is used exactly. |
| `ROTOR_CHORD_TOLERANCE_MM` | 0.001 | ≥ 0.001 | The largest overshoot of the polygon beyond the true circle, in mm (1 micron, also the smallest value allowed). The vertices sit slightly outside the nominal radius, so the copper is never smaller than requested. |
| `ROTOR_SOLDER_MASK_EXPANSION_MM` | 0.05 | up to 5 | Mask opening over the rotor copper: above 0 = opening that much wider than the copper; 0 = exactly the copper outline; −1 = no opening (mask stays over the copper). No other negative value is accepted. |

## 15.5 Optimizer (`OptimizerParameters.py`)

> [!NOTE]
> **Under construction.** The optimizer and its parameter file are not on main. They live on the [`analyser_and_optimizer` branch](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/tree/analyser_and_optimizer).

| Previous | Next |
|:---|---:|
| [Quick Guide To Parameters Selections](Quick-Guide-To-Parameters-Selections.md) | [Checks, Errors And Warnings](Checks-Errors-And-Warnings.md) |
