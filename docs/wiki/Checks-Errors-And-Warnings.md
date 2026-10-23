# 23. Checks, Errors And Warnings

Before and after a board is built, the generator checks it. The rules live in `Generator/Checks/`
(`ParameterRules.py`, `ConflictRules.py` and `DesignChecks.py`). The parameter rules can also be run alone, from the
`Single Generator` folder, to check the parameter files without generating anything:

```bash
python Generator/Run/CheckParameters.py
python Generator/Run/RunCoilGenerator.py --check    # check only, write nothing
```

Whether warnings about the finished boards stop the run is set by `GENERATOR_MODE` in `Board_Parameters.py`:
`"normal"` writes the boards anyway, `"strict"` treats every such warning as an error.

The Dual Generator runs all of these checks on each of its two sets, and adds its own; see
[23.6 Dual Generator](#236-dual-generator).

## 23.1 Levels

| Level | Meaning | What happens |
|---|---|---|
| Error | The board would be wrong or impossible. | Nothing is written. |
| Warning | The board can be made, but something is likely to be a problem. | The boards are written (unless `GENERATOR_MODE = "strict"`). |
| Info | Plain facts worth knowing. | Printed without colour. |

Errors are printed in red, warnings in yellow and success in green (`--no-color` switches the colours off).
Thresholds called "typical" in the messages are general PCB-fab rules of thumb, not the limits of any particular
manufacturer. Check yours.

Copper that overlaps copper of another net (a short) is always an error, in both generator modes. Warnings about the
parameter values themselves (ranges, estimates) stay warnings in both modes.

### 23.1.1 Named Conflicts

When settings cannot hold together, the message names them and explains why on the next line:

```text
ERROR   RX_TAB_LENGTH_MM conflicts with TX_OFFSET_MM, TX_TURNS and TX_PITCH_MM
        the fingers end at r = 24.40 mm, too close to the outermost TX copper ... Set RX_TAB_LENGTH_MM to at least 4.35, ...
```

The explanation says which value to change and, where it can be worked out, the value that is needed.

## 23.2 Two Stages

1. **Parameter rules** (`check_parameters`). They need only the values: types, ranges, and combinations that cannot
   work. Each parameter has a range (see the [Parameter Reference Single Generator](Parameter-Reference-Single-Generator.md)), and a misspelled or
   unknown name is reported as a warning, with a suggestion when a known name is close.
2. **Finished-geometry rules** (`check_design`). They need the built stator and rotor: the board edge against the
   copper it must contain, via clearances, and the page size.

A third check, the generator's own **TX self-clearance** check, exists because all TX turns are one net, so KiCad's
DRC cannot see a TX turn touching another TX turn.

## 23.3 What Is Checked

| Area | Examples of what the rules look for |
|---|---|
| RX band | Band narrower than one via (error) or very narrow for the vias (warning); a quarter loop with too little arc at the inner radius for the RX traces (warning); a board edge and the band set at once (info: each is used as given). |
| Fab limits | Trace widths below about 0.1 mm, `MIN_CLEARANCE_MM` tighter than typical, a via annular ring below about 0.1 mm; `VIA_DRILL_MM` not smaller than `VIA_DIAMETER_MM` (error). |
| RX layers | `RX_LAYER_A` and `RX_LAYER_B` equal (error); on a 4-layer board, RX on any layer pair other than Top + Inner-1 (warning). |
| Via type | `VIA_TYPE = "blind"` on a 2-layer board (error); with blind vias, a via pair that skips a layer (Top + Inner-2, Inner-1 + Bottom: not a one-step blind via) or `VIA_DRILL_MM` above about 0.15 mm (warnings); every via pair Top + Bottom, so that the setting changes nothing (warning); what each pair comes out as: blind, buried or through (info). |
| Sub-coils | A split so large that curves overlap, or that puts two curves on top of each other (errors); crowded tip vias with 3 sub-coils, or with 2 sub-coils and a split outside about 35 to 55; 2 sub-coils with too little arc per curve for the vias that join them, from 5 loops at the default radii; with 2 sub-coils, `RX_VIA_ELECTRICAL_DEG` outside about 57 + split / 2 to 123 − split / 2 (79.5 to 100.5 for a split of 45), where the via that joins the sub-coils does not fit and the build will probably stop (warnings). |
| Fingers | Finger legs closer than the clearance (error); `RX_TAB_WIDTH_MM` below about 0.6 mm (warning), or too wide for the loop count or the finger length (warning: the legs are moved closer, and the message gives the spacing used); a finger length that does not clear the outermost TX turn, or the outermost go-around bracket (error: `RX_TAB_LENGTH_MM` is the exact length and is never changed for you, and the message states the length it needs). |
| TX turns | Turns closer than the clearance (error) or practically equal to it (warning), also with one turn, because the outer tail runs one pitch outside the last turn; the first TX turn too close to the RX copper on the same layer (error); the terminal via too near the RX band or the next turns (warnings). The TX terminal itself has no setting: the generator searches the ring for the place with the largest gap to the RX copper (with `RX_TABS = "single"`, the place nearest the middle of the two fingers that keeps the clearance) and turns the board so that it ends up at 0°. With `RX_TABS = "single"`, if no place keeps the clearance, a note says so and the terminal goes where the gap is largest. |
| Resolution | A fixed `STEPS_PER_LOOP` or `TX_STEPS` giving a chord error above 0.01 mm, or a fixed `ROTOR_ARC_STEPS_PER_SECTOR` giving one above 0.05 mm (warning; the chord tolerances are not used for these). With "auto" the count is chosen from the chord tolerance instead; for the RX coils a warning appears if more than 1024 chords per loop would be needed (the count then stops at 1024). With S chords per loop the tip vias can only sit at about 45 + 720 / S to 135 − 720 / S electrical degrees. If `RX_VIA_ELECTRICAL_DEG` is outside that, the vias move to the nearest end, with a warning (with `GENERATOR_MODE = "strict"` the board is refused). |
| Board edge | `OUTER_EDGE_RADIUS_MM` cutting through the outermost TX turn, the fingers or the TX tail (errors); inner-tip vias running over the centre hole; a via touching copper of another net (error). |
| Rotor | Rotor metal fraction giving a weak fundamental (warning) or removing a harmonic (info); rotor copper with no width; custom rotor sector count different from `LOOPS`; custom radii out of order, copper too near the bore or the outline; solder-mask opening reaching the bore or outline; `ROTOR_ARC_STEPS_PER_SECTOR` giving a coarse arc (warning), or so few chords that the corners of the rotor copper cross the outline (error). |
| Files | Stator and rotor file names equal (error); names not ending in `.kicad_pcb` (warning); `OUTPUT_DIR` not a writable folder, or a missing folder that cannot be created (errors). |
| Chord tolerances | Each of `RX_CHORD_TOLERANCE_MM`, `TX_CHORD_TOLERANCE_MM` and `ROTOR_CHORD_TOLERANCE_MM` must be at least 0.001 mm (error below that). |
| IC limits | `IC_OSC_MIN_MHZ` not below `IC_OSC_MAX_MHZ` (error); a `RECEIVER_IC` line from an older version (warning: it is ignored, the receiver IC is now set in `IC_Parameters.py`). |
| Silkscreen | The lead-cutting suggestion, the last step of a run, never stops a generation. A wrong value in `SilkScreenSuggestion_Parameters.py` falls back to its default (warning); no spot with room for a break within `SILKSCREEN_SEARCH_SPAN_DEG`, no two via sites near the TX ends, or a missing font (warnings: that part is not drawn, the boards are written); no free place for a name (warning: the name is drawn at its default spot, where it may cover other marks or vias). See [Silkscreen](Silkscreen.md). |
| Page | The stator board, or a rotor board that reaches farther out than the stator, comes close to the top or left of its KiCad page (warning; the page grows right and down automatically). |

Each message names the setting, its value and the limit it broke, and many also say what to change. The Web Tool shows the same messages; see
[Web Tool](Web-Tool.md#46-errors-and-warnings).

### 23.3.1 TX Shape Checks

| Message | Level |
|---|---|
| `TX_STEPPED_ARC_RADIUS_MM` not larger than `TX_PITCH_MM` | Error: each arc must reach the next turn |
| `TX_STEPPED_ARC_RADIUS_MM` not smaller than `TX_PITCH_MM + TX_TAIL_EXTRA_MM` | Error: the last arc would pass the end of the tail |
| `TX_STEPPED_ARC_RADIUS_MM` below via radius + half a TX trace + clearance | Warning: the innermost arc comes within the clearance of the via (KiCad's DRC does not see it, all TX is one net) |
| Smallest gap between TX copper pieces around the via below `MIN_CLEARANCE_MM` | Warning |

## 23.4 Electrical Checks

The [electrical estimate](Electrical-Estimate.md) adds its own findings, checked against the receiver IC limits in
`IC_Parameters.py`: oscillator frequency out of range and tank resistance too low. When only the lower end of the tank resistance
range is below the limit, you get an info line that gives the range, not a warning.

## 23.5 Examples Of Boards The Generator Refuses

| Situation | Why |
|---|---|
| 16 loops on a very small board (outer radius below about 26 mm) | The tip vias crowd at small bore radii; a quarter loop needs at least 1.2 mm of arc at the RX inner edge. On many such boards a via touches copper of another net, which is an error; some only get via clearance warnings, and those are refused only with `GENERATOR_MODE = "strict"`. See the board size table in [Project Capabilities](Project-Capabilities.md#51-board-size-range). |
| 2 sub-coils at the default band, with 4 loops and fingers (`RX_TABS = "all"` or `"single"`), or with 5 or more loops | A via touches copper of another net, or the vias that join the sub-coils do not fit between the curves. Without fingers (`RX_TABS = "none"`) 4 loops build, with a via clearance warning. Use 1 sub-coil, fewer loops or a wider band. |
| `RX_TABS = "all"` on a small board when the TX turns go around the fingers (the fingers on a layer with TX turns) and there are several loops (on a board of 15 to 27 mm with a series TX on Top + Inner-1, 4 loops fail at the default 0.6 mm pitch, and a smaller pitch makes it worse) | A TX window under an RX finger would reach the TX terminal; the smaller the pitch, the farther the window reaches. Use `RX_TABS = "single"`, the fingers on a layer without TX turns (`RX_TAB_LAYER`), a parallel TX, fewer `TX_TURNS` or a bigger board. |

## 23.6 Dual Generator

The Dual Generator's rules live in `Dual Generator/Dual_Generator/Checks/`: `Dual_ParameterRules.py`, run by
`Dual_CheckParameters.py` before anything is built, and `Dual_DesignChecks.py`, run on the built copper. The checker on
its own builds nothing, so it does not measure the gap between the sets or the rotor rings; `--check` and a run do.
From the `Dual Generator` folder:

```bash
python Dual_Generator/Checks/Dual_CheckParameters.py
python Dual_Generator/Run/Dual_RunCoilGenerator.py --check    # check only, write nothing
```

The run checks in this order: the dual files and the dual rules, the layout mode, then the Single Generator's own
parameter checks on each set. After the build: the Single Generator's checks on each set's finished copper, then the
dual checks on the two sets together and on the two rotor rings. A message about one set names it: its explanation
line starts with `set 1:` or `set 2:`. `GENERATOR_MODE` in `Dual_Board_Parameters.py` works as on a single board.

| Area | What the rules look for |
|---|---|
| Files | A name in the wrong dual file (warning: ignored, the message names the file it belongs in); a name that is not a parameter, or one no longer used (warnings); a missing name (error); `OUTPUT_DIR` not a folder or not writable (errors), or not there yet (info: it will be created). |
| Fixed values | Any value in `Dual_Fixed_Parameters.py` other than its fixed one (error, saying why it is fixed). `TX_WIRING = "single"` (error: a dual board uses series or parallel). |
| Layout mode | A value `DUAL_MODE` needs that is `None`, or a value that must be `None` and is set (error naming every such value, and the mode that matches what is set when one does). A band given by half a pair, or by both pairs (error). A board too small for two bands in mode 1 (error, giving the outer radius it needs). Two sets that run into each other (error, giving the RX2 band start needed), or a bore with no room inside the RX1 band (error). In mode 4 each edge is held against its set's band and TX ring by the Single Generator's own edge rules. |
| Nets | A net name used twice across the two sets (error: KiCad would join the two coils). |
| Frequencies | `EXCITATION_FREQ_HZ` of the two sets closer than `TX_FREQ_SEPARATION_MIN` (warning), or within `TX_FREQ_RATIO_TOLERANCE` of a small integer ratio (warning). Whenever the separation is met, also an info that two free-running tanks have not been shown to work and must be proven on the first board. |
| Layers | Set 2 using all four layers, so no layer is free for set 1's leads (warning). |
| Rotor settings | `ROTOR_AUTO_COVER_TX = True` for ring 1, which puts the coarse half moon next to the fine band (warning). |
| Gap between the sets | Measured on the built copper: less than `TRACK_GAP_MM` (modes 1 and 3) or `MIN_CLEARANCE_MM` (modes 2 and 4) is an error that says how far to move the RX2 band out; a difference from the layout formulas larger than `LAYOUT_TOLERANCE_MM` is a warning. Copper of one set inside the other set's ring is always an error. |
| Rotor rings | The bare ring between the two rings below `ROTOR_TRACK_GAP_MM` (error naming the extension to change); ring 1 closer than `ROTOR_1_TO_RX2_MM` to the RX2 copper, or ring 2 closer than `ROTOR_2_TO_RX1_MM` to the RX1 copper (warnings); ring 1 reaching past the TX1 ring or over set 2, or ring 2 reaching in over set 1 (warnings). |
| Electrical | The estimate for each set, against that set's own IC in `Dual_IC1_Parameters.py` or `Dual_IC2_Parameters.py`. |
| Silkscreen | As on a single board, for each set; a set's message names its number. |

For example, the default board with a parallel TX at the default pitch:

```text
ERROR   TX_PITCH_MM conflicts with VIA_DIAMETER_MM and TX_WIRING
set 1: a pitch of 0.35 mm is too small for the stitching vias of the parallel TX (a turn next to a 0.6 mm via must bend 0.21 mm away and would then touch the turn beyond it). Raise TX_PITCH_MM to at least 0.43 or use smaller vias
```

See [Board Features - Dual Generator](Board-Features-Dual-Generator.md#185-checks-on-the-finished-boards) and
[Quick Guide To Parameters Selections - Dual Generator](Quick-Guide-To-Parameters-Selections-Dual-Generator.md#2011-what-the-checker-says).

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [Parameter Reference Dual Generator](Parameter-Reference-Dual-Generator.md) | [Electrical Estimate](Electrical-Estimate.md) |
