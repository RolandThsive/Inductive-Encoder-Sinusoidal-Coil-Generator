# 16. Checks, Errors And Warnings

Before and after a board is built, the generator checks it. The rules live in `Generator/Checks/`
(`ParameterRules.py`, `ConflictRules.py` and `DesignChecks.py`). The parameter rules can also be run alone, from the
`Single Generator` folder, to check the parameter files without generating anything:

```bash
python Generator/Run/CheckParameters.py
python Generator/Run/RunCoilGenerator.py --check    # check only, write nothing
```

Whether warnings about the finished boards stop the run is set by `GENERATOR_MODE` in `Board_Parameters.py`:
`"normal"` writes the boards anyway, `"strict"` treats every such warning as an error.

## 16.1 Levels

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

### 16.1.1 Named Conflicts

When settings cannot hold together, the message names them and explains why on the next line:

```text
ERROR   RX_TAB_LENGTH_MM conflicts with TX_OFFSET_MM, TX_TURNS and TX_PITCH_MM
        the fingers end at r = 24.40 mm, too close to the outermost TX turn ... Set RX_TAB_LENGTH_MM to at least 4.35, ...
```

The explanation says which value to change and, where it can be worked out, the value that is needed.

## 16.2 Two Stages

1. **Parameter rules** (`check_parameters`). They need only the values: types, ranges, and combinations that cannot
   work. Each parameter has a range (see the [Parameter Reference](Parameter-Reference.md)), and a misspelled or
   unknown name is reported with a suggestion.
2. **Finished-geometry rules** (`check_design`). They need the built stator and rotor: the board edge against the
   copper it must contain, via clearances, and the page size.

A third check, the generator's own **TX self-clearance** check, exists because all TX turns are one net, so KiCad's
DRC cannot see a TX turn touching another TX turn.

## 16.3 What Is Checked

| Area | Examples of what the rules look for |
|---|---|
| RX band | Band narrower than one via (error) or very narrow for the vias (warning); a quarter loop with too little arc at the inner radius for the tip vias; both board edges and the band set at once (info: each is used as given). |
| Fab limits | Trace widths below about 0.1 mm, `MIN_CLEARANCE_MM` tighter than typical, a via annular ring below about 0.1 mm; `VIA_DRILL_MM` not smaller than `VIA_DIAMETER_MM` (error). |
| RX layers | `RX_LAYER_A` and `RX_LAYER_B` equal (error); RX on layers far apart in the stack-up (warning). |
| Sub-coils | A split so large that curves overlap, or that puts two curves on top of each other (errors); crowded tip vias with 3 sub-coils, or 2 sub-coils with 13 to 16 loops at the default radii (warnings). |
| Fingers | Finger legs closer than the clearance (error); `RX_TAB_WIDTH_MM` below about 0.6 mm (warning); a finger length that does not clear the outermost TX turn, or the outermost go-around bracket (error: `RX_TAB_LENGTH_MM` is the exact length and is never changed for you, and the message states the length it needs). |
| TX turns | Turns closer than the clearance (error) or practically equal to it (warning); the first TX turn too close to the RX copper on the same layer (error); the terminal via too near the RX band or the next turns (warnings). The TX terminal itself has no setting: the generator searches the ring for the place with the largest gap to the RX copper and turns the board so that it ends up at 0°; if no place keeps the clearance, a note says so. |
| Resolution | A fixed `STEPS_PER_LOOP`, `TX_STEPS` or `ROTOR_ARC_STEPS_PER_SECTOR` giving a chord error above its chord tolerance (warning). With "auto" the count is chosen from the tolerance instead; for the RX coils a warning appears if more than 1024 chords per loop would be needed (the count then stops at 1024). |
| Board edge | `OUTER_EDGE_RADIUS_MM` cutting through the outermost TX turn, the fingers or the TX tail (errors); inner-tip vias running over the centre hole; a via touching copper of another net (error). |
| Rotor | Rotor metal fraction giving a weak fundamental (warning) or removing a harmonic (info); rotor copper with no width; custom rotor sector count different from `LOOPS`; custom radii out of order, copper too near the bore or the outline; solder-mask opening reaching the bore or outline; `ROTOR_ARC_STEPS_PER_SECTOR` giving a coarse arc. |
| Files | Stator and rotor file names equal (error); names not ending in `.kicad_pcb`; `OUTPUT_DIR` not a writable folder. |
| Chord tolerances | Each of `RX_CHORD_TOLERANCE_MM`, `TX_CHORD_TOLERANCE_MM` and `ROTOR_CHORD_TOLERANCE_MM` must be at least 0.001 mm (error below that). |
| Page | The board comes close to the top or left of the KiCad page (the page grows right and down automatically). |

Each message names the setting, its value and the limit it broke. The Web Tool adds the "what to change" advice; see
[Web Tool](Web-Tool.md#46-errors-and-warnings).

## 16.4 Electrical Checks

The [electrical estimate](Electrical-Estimate.md) adds its own findings, checked against the receiver IC's datasheet
limits: oscillator frequency out of range and tank resistance too low. When only the lower end of the tank resistance
range is below the limit, you get an info line that gives the range, not a warning.

### 16.4.1 TX Shape Checks

| Message | Level |
|---|---|
| `TX_STEPPED_ARC_RADIUS_MM` not larger than `TX_PITCH_MM` | Error: each arc must reach the next turn |
| `TX_STEPPED_ARC_RADIUS_MM` not smaller than `TX_PITCH_MM + TX_TAIL_EXTRA_MM` | Error: the last arc would pass the end of the tail |
| `TX_STEPPED_ARC_RADIUS_MM` below via radius + half a TX trace + clearance | Warning: the innermost arc comes within the clearance of the via (KiCad's DRC does not see it, all TX is one net) |
| Smallest gap between TX copper pieces around the via below `MIN_CLEARANCE_MM` | Warning |

## 16.5 Examples Of Boards The Generator Refuses

| Situation | Why |
|---|---|
| 16 loops on a very small board (outer radius below about 26 mm) | The tip vias crowd at small bore radii; a quarter loop needs about 1.3 mm of arc at the RX inner edge. See the board size table in [Board Features](Board-Features.md). |
| 2 sub-coils with 13 to 16 loops at the default band | The tip vias of neighbouring coils get too close. Use 1 sub-coil or a wider band. |
| `RX_TABS = "all"` on a small board at a wide TX pitch (above about 1.2 mm on a board of 15 to 27 mm) | A TX window under an RX finger would reach the TX terminal. Use `RX_TABS = "single"`, a smaller pitch or a bigger board. A longer pitch also needs longer fingers; the message states the `RX_TAB_LENGTH_MM` needed. |
| `TX_STEPPED_ANGLE_DEG` very steep with a tight pitch (`stepped_diagonal`) | Neighbouring steps would be closer than the clearance; the generator staggers them and prints the gap it got. |

| Previous | Next |
|:---|---:|
| [Parameter Reference](Parameter-Reference.md) | [Electrical Estimate](Electrical-Estimate.md) |
