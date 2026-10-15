# 1. Parameter Reference

Every setting lives in a parameter file in `Parameters/`. These are the only files you edit. Units are millimetres,
degrees and hertz unless a name says otherwise. The **Range** column is what the parameter checker accepts; "None"
means the generator works the value out itself. The Web Tool shows the same names in its Advanced mode.

`Parameters.py` only gathers the four board files and is not edited. `OptimizerParameters.py` is read only by the
optimizer.

> [!NOTE]
> Defaults are those of the parameter files on `main`. Settings marked *only if* are greyed out ("not used now") in
> the Web Tool when the design does not use them.

## 1.1 Board (`Board_Parameters.py`)

### 1.1.1 Output

| Name | Default | Range | Meaning |
|---|---|---|---|
| `OUTPUT_DIR` | `"Output"` | text | Folder in which each run's `Coil_...` folder is made. A relative path is taken from the project folder. |
| `STATOR_FILE`, `ROTOR_FILE` | `Stator.kicad_pcb`, `Rotor.kicad_pcb` | file names | Names of the two boards inside each run folder. They must differ and should end in `.kicad_pcb`. |
| `CENTER_X_MM`, `CENTER_Y_MM` | 100, 100 | number | Position of the sensor axis on the KiCad page. |
| `PAGE_SIZE_MM` | (200, 200) | pair | KiCad "User" page size (the generator enlarges it so the title block never overlaps the board). |

### 1.1.2 Stator board

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

### 1.1.3 Mechanical assumptions

| Name | Default | Range | Meaning |
|---|---|---|---|
| `AIR_GAP_MM` | 1.0 | > 0 | Stator top copper to rotor copper. |
| `PCB_THICKNESS_MM` | 1.6 | > 0 | Stator board thickness. |
| `EXCITATION_FREQ_HZ` | 3.5e6 | > 0 | TX oscillator frequency aimed for, with the rotor in place. The electrical estimate sizes the tank capacitors for it; the rotor summary uses it for the skin depth. A warning appears far outside 1 to 10 MHz. |

### 1.1.4 Electrical estimate

| Name | Default | Range | Meaning |
|---|---|---|---|
| `RECEIVER_IC` | `"IPS2550"` | `"IPS2550"`, `"IPS2200"`, None | The IC the coil is checked against (see [Electrical Estimate](Electrical-Estimate.md)). None switches the checks off. |
| `COPPER_THICKNESS_UM` | 35 | 0 to 500 | Stator copper thickness (35 µm = 1 oz). Sets TX resistance and Q. |
| `TX_AMPLITUDE_VPP` | None | 0 to 100 or None | TX voltage across the coil, peak to peak, if you know it. None = the range from the IC datasheet. |

## 1.2 RX (`RX_Parameters.py`)

### 1.2.1 Size and periodicity

| Name | Default | Range | Meaning |
|---|---|---|---|
| `LOOPS` | 1 | 1 to 16 | Electrical periods per mechanical turn, and the number of rotor sectors. Unique range = 360° / `LOOPS`. |
| `INSIDE_RADIUS_MM`, `OUTSIDE_RADIUS_MM` | None, None | > 0 or None | The inner and outer radius of the RX band (centre line of the traces). With all four band values None (the default), the band is fitted to the board edges: it starts `INNER_EDGE_INSET_MM` outside the centre hole and ends where the TX turns, the TX tail and the margins leave room (15 and 27 mm board edges give a 16.2 to 22.4 mm band). |
| `RX_R_BASE_MM`, `RX_A_MM` | None, None | > 0 or None | The band by its centre (`r_base`) and swing (`A`): band = `r_base − A` to `r_base + A`. Signal grows about with `r_base × A`. |
| `RX_TRACE_WIDTH_MM` | 0.2 | > 0 | RX trace width. |
| `RX_NET_PHASE_0_2`, `RX_NET_PHASE_1_3` | `"2"`, `"1"` | text, different | Net names of the SIN pair (phases 0 and 2) and the COS pair (phases 1 and 3). |
| `RX_ZERO_OFFSET_LOOP_FRACTION` | −0.35 | number | Rotation of the whole RX pattern, as a fraction of one loop. −0.35 reproduces the original generator. |
| `RX_ZERO_OFFSET_DEG` | 0.0 | number | Extra rotation of the RX pattern in degrees. |

The band is given in **one** of two ways (the other pair None), or from the board edges when all four are None, which is the default. The
two values of a pair go together. See [Web Tool](Web-Tool.md) for the None switches.

### 1.2.2 Shape

| Name | Default | Range | Meaning |
|---|---|---|---|
| `RX_PROFILE` | `"equal_area"` | `equal_area`, `cosine_r`, `field_compensated` | The shape of the RX curves. See [RX Profiles](RX-Profiles.md). `field_compensated` uses `AIR_GAP_MM`, `PCB_THICKNESS_MM` and the TX settings. |
| `STEPS_PER_LOOP` | `"auto"` | "auto" or an integer, a multiple of 8, 48 to 4096 | Chords (polyline segments) per electrical period. "auto" = the smallest multiple of 8 whose midpoint chord error is within `RX_CHORD_TOLERANCE_MM`, at most 1024 (a warning appears if that is not enough). Sub-coils may raise the count. A whole number is used exactly, and the tolerance then only drives the chord-error warning. |
| `RX_CHORD_TOLERANCE_MM` | 0.001 | ≥ 0.001 | How far a straight chord may lie from the true RX curve, in mm (0.001 = 1 micron, also the smallest value allowed; finer adds points, not accuracy). The old default was 0.005. The older name `CHORD_TOLERANCE_MM` is still read when this line is missing. |

### 1.2.3 Sub-coils

| Name | Default | Range | Meaning |
|---|---|---|---|
| `RX_SUBCOILS` | 1 | 1, 2 or 3 | Sub-coils per coil (distributed winding, as in the Renesas IPS2200 reference design). Each coil stays one closed series loop. |
| `RX_SUBCOIL_SPLIT_ELEC_DEG` | 45.0 | > 0 (*only if* sub-coils ≥ 2) | Electrical angle between sub-coils. Use 45 for 2, and 30 for 3. Two sub-coils give signal × 2·cos(d/2) (1.85× at 45°); harmonic *h* × 2·cos(h·d/2) (3rd and 5th down about 59 % at 45°, 3rd removed at 60°, 5th removed at 36°). |

### 1.2.4 Layers and vias

| Name | Default | Range | Meaning |
|---|---|---|---|
| `RX_LAYER_A`, `RX_LAYER_B` | 1, 2 | 1 to 4, different (*only if* 4 layers) | The two layers of the RX coils: 1 = Top, 2 = Inner-1, 3 = Inner-2, 4 = Bottom. A carries the rising edges, B the falling edges. Top + Inner-1 sit closest together in a standard stack-up. |
| `RX_RISING_EDGE_LAYER` | `"F.Cu"` | `F.Cu`, `B.Cu` (*only if* 2 layers) | Which layer carries the rising edges. |
| `RX_VIA_ELECTRICAL_DEG` | 90.0 | 50 to 130 | Electrical angle of the outer-tip layer-swap via (90 = exactly on the tip). |

### 1.2.5 Bridging fingers

| Name | Default | Range | Meaning |
|---|---|---|---|
| `RX_TABS` | `"all"` | `all`, `single`, `none` | Fingers that leave the RX band, cross over the TX turns and return, so the coils can be broken out outside the TX ring. `all` = every outer tip of every phase; `single` = one per coil, next to the TX tail; `none` = no fingers. |
| `RX_TAB_LAYER` | `"auto"` | auto, 1 to 4 | Layer of the fingers. "auto" = the RX layer nearest the top that carries no TX turn. |
| `RX_TAB_LENGTH_MM` | 3.0 | ≥ 0 | The finger reaches `OUTSIDE_RADIUS_MM` plus this (lengthened if needed to clear the outermost complete TX turn). |
| `RX_TAB_WIDTH_MM` | 1.0 | > 0 | Spacing of the finger's two legs. Keep at 0.6 or more for etching; narrower disturbs the signal less. |

## 1.3 TX (`TX_Parameters.py`)

Layers are numbered 1 = Top, 2 = Inner-1, 3 = Inner-2, 4 = Bottom (a 2-layer board has 1 and 4).

### 1.3.1 Turns

| Name | Default | Range | Meaning |
|---|---|---|---|
| `TX_NET` | `"TX"` | text | Net name of the TX coil. |
| `TX_TURNS` | 3 | 1 to 50 | Complete turns **per TX layer**. |
| `TX_OFFSET_MM` | 1.1 | > 0 | First turn radius = RX outside radius plus this. |
| `TX_PITCH_MM` | 0.6 | > 0 | Radial pitch between turns. |
| `TX_TRACE_WIDTH_MM` | 0.2 | > 0 | TX trace width. |
| `TX_STEPS` | `"auto"` | "auto" or a whole number, 12 to 20000 | Polyline points per TX turn. "auto" = as many as `TX_CHORD_TOLERANCE_MM` needs on the outermost full turn (the worst case), rounded up to a multiple of 8, at least 48. A whole number is used exactly; the old default was 300. |
| `TX_CHORD_TOLERANCE_MM` | 0.001 | ≥ 0.001 | How far a straight chord of a TX turn may lie from the true circle, in mm (1 micron, also the smallest value allowed). |
| `TX_TAIL_EXTRA_MM` | 1.0 | ≥ 0 | Radial tail that carries the TX terminal. |
| `TX_TURN_SHAPE` | `"stepped"` | `stepped`, `spiral` | Concentric circles joined by short steps, or one smooth Archimedean spiral (use it when the pitch is tight). |
| `TX_STEPPED_ANGLE_DEG` | 45 | "auto" or 5 to 90 (*only if* stepped) | Angle of the steps, measured from the turn: 90 = radial, smaller = a longer slope. "auto" = the original two-piece step (about 40°). Neighbouring steps have a gap of pitch × cos(angle) − width; above about 45° with the defaults that is below `MIN_CLEARANCE_MM`, and the steps are staggered automatically. |
| `TX_INSIDE_VIA_DISTANCE_MM` | 0.3 | −3 to 3 | Moves the TX terminal via towards the centre (negative = outwards). 0 = on the trace ends, which is closer to the next turn than the clearance allows with the default via and pitch. Keep below `TX_OFFSET_MM` − via radius − half an RX trace − clearance (0.4 mm with the defaults). |
| `TX_START_ANGLE_DEG` | 0.0 | number or "auto" | Azimuth of the TX tail and via. "auto" = the widest gap between RX fingers (use with many loops or sub-coils). |

### 1.3.2 TX layers

| Name | Default | Range | Meaning |
|---|---|---|---|
| `TX_LAYERS` | 1 | 1 or 2 | One TX layer, or two. |
| `TX_LAYER_A` | 4 | 1 to 4 | The TX layer (or the spiral that runs inwards from the terminal). |
| `TX_LAYER_B` | 1 | 1 to 4, different (*only if* 2 layers) | The second TX layer (or the spiral that runs back out). |
| `TX_SERIES` | True | True or False | Two layers wired in series (two spirals joined by a via at the inner end, same sense, fields add) or in parallel (the same turns on both layers, stitched through vias; about 6 % more signal and twice the Q in the model). Put `TX_LAYER_A` on Top for parallel. |
| `TX_SERIES_UNDERPASS_LAYER` | `"auto"` | auto, 1 to 4 (*only if* series) | Layer of the inner tail and go-around brackets. |
| `TX_PARALLEL_BREAK_STYLE` | `"staggered"` | `stitched`, `staggered` (*only if* parallel) | How the turns make way for a finger. `stitched`: the turns stop at vias on each side of the finger and the other layer carries the current past it. `staggered`: go-around, with brackets on the other layer. |

Examples: TX on Bottom with the tail on Top is the original layout (the default). TX on Top gives about 15 % (0.8 mm
board) to 30 % (1.6 mm board) more receiver signal per TX volt in the model. Series on layers 1 and 4 is the 2-layer
layout of Hoxha et al. 2022 (Fig. 2); series on 1 and 3 follows the Renesas IPS2200 reference (4-layer board, RX on 1
and 2).

A series TX always makes way for fingers by going around them ("staggered"). All TX turns are one net, so KiCad's DRC
cannot see a TX turn touching another: the generator checks the clearance itself and warns.

## 1.4 Rotor (`Rotor_Parameters.py`)

| Name | Default | Range | Meaning |
|---|---|---|---|
| `ROTOR_MODE` | `"according_to_stator"` | `according_to_stator`, `custom` | Generate the rotor from the stator, or use only the `ROTOR_CUSTOM_*` values. |

### 1.4.1 According to stator

| Name | Default | Range | Meaning |
|---|---|---|---|
| `ROTOR_AUTO_DUTY` | 0.5 | 0 to 1, exclusive | Metal fraction of each period. A fraction k/h has no h-th harmonic in the pattern, but copper edges crowd the field, which moves the best value; use `OptimizeCoil.py`. |
| `ROTOR_AUTO_START_ANGLE_DEG` | 0.0 | number | Mechanical angle of the first sector edge. |
| `ROTOR_AUTO_COVER_TX` | True | True or False | True: the copper runs over the TX turns and ends `ROTOR_AUTO_TX_OVERHANG_MM` past the outermost turn, as in Renesas reference designs (5 to 8 % more signal in the model). False: the older rule below. |
| `ROTOR_AUTO_TX_OVERHANG_MM` | 0.5 | −20 to 20 (*only if* cover) | Millimetres past the outer edge of the outermost TX turn (negative = ends over the TX turns). |
| `ROTOR_AUTO_EXTENSION_MM` | None | number or None | How far the copper reaches past the RX band on both edges. None = `AIR_GAP_MM`. |
| `ROTOR_AUTO_EXTENSION_INNER_MM` | None | number or None | Inner edge only. None = `ROTOR_AUTO_EXTENSION_MM`. |
| `ROTOR_AUTO_EXTENSION_OUTER_MM` | None | number or None (*only if* not cover) | Outer edge only. |
| `ROTOR_AUTO_TX_CLEARANCE_MM` | 0.1 | ≥ 0 (*only if* not cover) | Copper stays this far inside the TX ring. |
| `ROTOR_AUTO_EDGE_CLEARANCE_MM` | 0.5 | ≥ 0 | Copper stays this far from the bore edge and the outline. |
| `ROTOR_AUTO_COPPER_LAYERS` | `["F.Cu"]` | layer list | Layer(s) carrying the metal sectors. Mount the copper side towards the stator. |

### 1.4.2 Custom

| Name | Default | Range | Meaning |
|---|---|---|---|
| `ROTOR_CUSTOM_SECTORS` | 1 | 1 to 64 | Number of sectors. It should equal `LOOPS`. |
| `ROTOR_CUSTOM_DUTY` | 0.5 | 0 to 1, exclusive | Metal fraction. |
| `ROTOR_CUSTOM_START_ANGLE_DEG` | 0.0 | number | Mechanical angle of the first sector edge. |
| `ROTOR_CUSTOM_INNER_RADIUS_MM`, `ROTOR_CUSTOM_OUTER_RADIUS_MM` | 37.1, 51.9 | > 0 | Copper inner and outer radius. |
| `ROTOR_CUSTOM_COPPER_LAYERS` | `["F.Cu"]` | layer list | Layer(s) carrying the copper. |
| `ROTOR_CUSTOM_OUTLINE_RADIUS_MM` | 55.0 | > 0 or None | Outer board edge (None = no outline). |
| `ROTOR_CUSTOM_BORE_RADIUS_MM` | 36.8 | > 0 or None | Centre hole (None = no hole). |

### 1.4.3 Both modes

| Name | Default | Range | Meaning |
|---|---|---|---|
| `ROTOR_ARC_STEPS_PER_SECTOR` | `"auto"` | "auto" or a whole number, 8 to 5000 | Polygon points on every circular arc of a sector. "auto" = as many as `ROTOR_CHORD_TOLERANCE_MM` needs (at least 8). A whole number is used exactly; the old default was 48. |
| `ROTOR_CHORD_TOLERANCE_MM` | 0.001 | ≥ 0.001 | The largest overshoot of the polygon beyond the true circle, in mm (1 micron, also the smallest value allowed). The vertices sit slightly outside the nominal radius, so the copper is never smaller than requested. |
| `ROTOR_SOLDER_MASK_EXPANSION_MM` | 0.05 | up to 5 | Mask opening over the rotor copper: above 0 = opening that much wider than the copper; 0 = exactly the copper outline; −1 = no opening (mask stays over the copper). No other negative value is accepted. |

## 1.5 Optimizer (`OptimizerParameters.py`)

Used only by `OptimizeCoil.py`. These settings change what the optimizer tries; they never change a board.

| Name | Default | Meaning |
|---|---|---|
| `PROFILES` | all three | RX profiles tried. |
| `SUBCOIL_COUNTS` | (1, 2) | Sub-coil counts tried. |
| `SUBCOIL_SPLITS_DEG` | 36, 40, 45, 50, 55, 60 | Splits tried for two or more sub-coils. |
| `DUTY_RANGE` | (0.25, 0.50) | Rotor metal fraction searched. |
| `SEARCH_ROTOR_OUTER_EDGE` | True | Also search where the rotor copper ends on the outside. |
| `OUTER_RANGE_MM` | (−0.2, 0.5) | Outer-edge range for the older screen model only. |
| `COMPARE_FINGERS` | False | Try `all`, `single` and `none` fingers and compare (about three times the run time). |
| `GAP_TOLERANCE_MM` | 0.2 | Air gap ± that every candidate must stay good within. |
| `DUTY_TOLERANCE` | 0.005 | Metal fraction ± (etching). |
| `OUTER_TOLERANCE_MM` | 0.05 | Rotor outer edge ± (screen model only). |
| `ECCENTRICITY_MM` | 0.2 | Rotor axis offset from the stator axis. |
| `TILT_DEG` | 0.3 | Rotor plane tilt. |
| `ECC_DIRECTIONS` | 3 | Eccentricity directions tried over one loop pitch. |
| `MIN_SIGNAL` | 0.8 | Smallest allowed signal, as a fraction of the current design's. |
| `ALLOW_WARNINGS` | False | Whether candidates that trigger generator warnings may be recommended. |
| `FINALISTS` | 6 | Candidates re-checked over the full tolerance window. |
| `ROTOR_MODEL` | `"eddy"` | `eddy` (eddy currents in the rotor copper, slower, sees copper over the TX) or `screen` (older, much faster). |
| `TRUE_3D_GEOMETRY` | True | Every receiver trace at its real layer depth and the TX from its real copper. |
| `SCREEN_SHARP_EDGES` | False | Screen model only: perfectly sharp rotor edges. |
| `JOBS` | 0 | Worker processes (0 = automatic, at most 4). |
| `RX_BASE_AND_AMPLITUDE_FINDER` | True | When only the board edges are given, search the best `RX_R_BASE_MM` and `RX_A_MM`. |
| `BAND_WIDTH_LIMIT_PERCENT` | 70.0 | Narrowest band tried, as a percentage of the widest. |
| `BAND_STEP_PERCENT` | 10.0 | Step of the band search, in percent (1 = finest). |
| `BAND_BOARDS` | 3 | How many of the best boards get the band finder. |

| Previous | Next |
|:---|---:|
| [Quick Guide To Parameters Selections](Quick-Guide-To-Parameters-Selections.md) | [Checks, Errors And Warnings](Checks-Errors-And-Warnings.md) |
