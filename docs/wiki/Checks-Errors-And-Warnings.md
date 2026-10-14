# Checks, Errors And Warnings

Before and after a board is built, the generator checks it. `ParameterChecker.py` holds every rule in one place. It
can also be run alone to check the parameter files without generating anything:

```bash
python Generator/ParameterChecker.py
python Generator/RunCoilGenerator.py --check    # check only, write nothing
python Generator/RunCoilGenerator.py --strict   # treat warnings as errors
```

## Levels

| Level | Meaning | What happens |
|---|---|---|
| Error | The board would be wrong or impossible. | Nothing is written. |
| Warning | The board can be made, but something is likely to be a problem. | The boards are written (unless `--strict`). |
| Info | Plain facts worth knowing. | Printed without colour. |

Thresholds called "typical" in the messages are general PCB-fab rules of thumb, not the limits of any particular
manufacturer. Check yours.

## Two Stages

1. **Parameter rules** (`check_parameters`). They need only the values: types, ranges, and combinations that cannot
   work. Each parameter has a range (see the [Parameter Reference](Parameter-Reference.md)), and a misspelled or
   unknown name is reported with a suggestion.
2. **Finished-geometry rules** (`check_design`). They need the built stator and rotor: the board edge against the
   copper it must contain, via clearances, and the page size.

A third check, the generator's own **TX self-clearance** check, exists because all TX turns are one net, so KiCad's
DRC cannot see a TX turn touching another TX turn.

## What Is Checked

| Area | Examples of what the rules look for |
|---|---|
| RX band | Band narrower than one via (error) or very narrow for the vias (warning); a quarter loop with too little arc at the inner radius for the tip vias; both board edges and the band set at once (info: each is used as given). |
| Fab limits | Trace widths below about 0.1 mm, `MIN_CLEARANCE_MM` tighter than typical, a via annular ring below about 0.1 mm; `VIA_DRILL_MM` not smaller than `VIA_DIAMETER_MM` (error). |
| RX layers | `RX_LAYER_A` and `RX_LAYER_B` equal (error); RX on layers far apart in the stack-up (warning). |
| Sub-coils | A split so large that curves overlap, or that puts two curves on top of each other (errors); crowded tip vias with 3 sub-coils, or 2 sub-coils with 13 to 16 loops at the default radii (warnings). |
| Fingers | Finger legs closer than the clearance (error); `RX_TAB_WIDTH_MM` below about 0.6 mm (warning); a finger length that does not clear the outermost TX turn (info). |
| TX turns | Turns closer than the clearance (error) or practically equal to it (warning); the first TX turn too close to the RX copper on the same layer (error); the terminal via too near the RX band or the next turns (warnings). |
| Resolution | A fixed `STEPS_PER_LOOP`, `TX_STEPS` or `ROTOR_ARC_STEPS_PER_SECTOR` giving a chord error above its chord tolerance (warning). With "auto" the count is chosen from the tolerance instead; for the RX coils a warning appears if more than 1024 chords per loop would be needed (the count then stops at 1024). |
| Board edge | `OUTER_EDGE_RADIUS_MM` cutting through the outermost TX turn, the fingers or the TX tail (errors); inner-tip vias running over the centre hole; a via touching copper of another net (error). |
| Rotor | Rotor metal fraction giving a weak fundamental (warning) or removing a harmonic (info); rotor copper with no width; custom rotor sector count different from `LOOPS`; custom radii out of order, copper too near the bore or the outline; solder-mask opening reaching the bore or outline; `ROTOR_ARC_STEPS_PER_SECTOR` giving a coarse arc. |
| Files | Stator and rotor file names equal (error); names not ending in `.kicad_pcb`; `OUTPUT_DIR` not a writable folder. |
| Chord tolerances | Each of `RX_CHORD_TOLERANCE_MM`, `TX_CHORD_TOLERANCE_MM` and `ROTOR_CHORD_TOLERANCE_MM` must be at least 0.001 mm (error below that). |
| Page | The board comes close to the top or left of the KiCad page (the page grows right and down automatically). |

Each message names the setting, its value and the limit it broke. The Web Tool adds the "what to change" advice; see
[Web Tool](Web-Tool.md#errors-and-warnings).

## Electrical Checks

The [electrical estimate](Electrical-Estimate.md) adds its own findings, checked against the receiver IC's datasheet
limits: oscillator frequency out of range, tank resistance too low, receiver signal too small or too large, receiver
signal varying too much, and TX voltage out of range.

## Examples Of Boards The Generator Refuses

| Situation | Why |
|---|---|
| 16 loops on a very small board (outer radius below about 26 mm) | The tip vias crowd at small bore radii; a quarter loop needs about 1.3 mm of arc at the RX inner edge. See the board size table in [Board Features](Board-Features.md). |
| 2 sub-coils with 13 to 16 loops at the default band | The tip vias of neighbouring coils get too close. Use 1 sub-coil or a wider band. |
| Sub-coils or `RX_TABS = "all"` at a wide TX pitch | The README's wider-pitch stator pictures (1.5 mm and 2.5 mm) only exist for the loop examples; the sub-coil and finger examples stay at 0.6 mm because the generator will not build those boards at a wider pitch. |
| `TX_STEPPED_ANGLE_DEG` very steep with a tight pitch | Neighbouring steps would be closer than the clearance; the generator staggers them and prints the gap it got. |
