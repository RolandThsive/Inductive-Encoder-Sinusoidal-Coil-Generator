# 19. Silkscreen - Dual Generator

A dual board has six coils to break out: the SIN and COS coils and the TX ring of each set. None of them has terminals.
Every RX coil is one closed loop, and the two ends of each series TX ring lie on top of each other one pitch outside its
last turn (the Top end and the Inner-2 end at the same point). You break each RX loop at one place and set a via at each
side of the cut, extend each TX end to a via of its own, and route from those vias to the set's IC.

As on a single board, the last step of the run draws a **suggestion for these cuts on the silkscreen** of the finished
`Stator.kicad_pcb`, for both sets. The silkscreen is there for **guidance only**: it shows where the vias of each break
have room on every layer, next to each set's TX ends, so all leads of a set come together. It changes no copper; the
marks are drawings on `F.SilkS` and `B.SilkS` that you may follow, move or delete. The step is
`Dual_LeadCutting_SilkscreenSuggestion.py`, and the [Silkscreen](Silkscreen.md) page describes how the search works.

## 19.1 What Is Drawn

| Coil | Marks | Lead Names |
|---|---|---|
| RX coils of set 1 | A dashed box around each break and a dot at each of its two via sites | `SIN1_1`, `SIN1_2`, `COS1_1`, `COS1_2` |
| TX ring of set 1 | A dot at each of the two via sites beside the stacked end and a dashed line from the end to each site | `TX1_1 TOP` (the Top end), `TX1_2 IN2` (the Inner-2 end) |
| RX coils of set 2 | As set 1 | `SIN2_1`, `SIN2_2`, `COS2_1`, `COS2_2` |
| TX ring of set 2 | As set 1 | `TX2_1 TOP`, `TX2_2 IN2` |

![Silkscreen Dual 1: Lead-Cutting Suggestion On A Dual Generator Board](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/silkscreen_dual_zoom.png)

*Silkscreen Dual 1. The suggestion as written into `Stator.kicad_pcb` on the default dual board (inner set 1 loop with its
TX ends at 180°, outer set 16 loops with its TX ends at 0°). Top row: the top view with `F.SilkS`: the whole board, then
set 1 and set 2 enlarged. Bottom row: the bottom view, mirrored, with `B.SilkS` and the copper seen through. RX: cut the
trace between the two dots, one via per dot. TX: extend each end along the dashed line to its dot.*

## 19.2 What Differs From The Single Generator

- **Two searches, one per set.** Each set's breaks are looked for within `SILKSCREEN_SEARCH_SPAN_DEG` (30°) of that set's
  own terminal angle, `TERMINAL_1_DEG` or `TERMINAL_2_DEG`, where its TX ends are.
- **The break layers** are `F.Cu`, then `In1.Cu` (`SILKSCREEN_BREAK_LAYERS`), the two RX layers of the default dual
  board.
- **The separation** `SILKSCREEN_BREAK_SEPARATION_MM` (4 mm) holds between the two breaks of a set and its TX end.
- **The clearance** is the dual board's `MIN_CLEARANCE_MM` (0.15 mm) from all copper on every layer, so a via of the
  suggestion also keeps clear of the other set.

On the default board the run prints, and appends to `Parameters.txt`, six suggestions:

```text
SIN1 (SIN_1): cut the Top trace at (91.1058, 96.5691) (r = 9.53 mm, 201.1 deg); vias SIN1_1 at (91.235, 95.9832) and SIN1_2 at (90.9766, 97.1551), clearance 0.42 mm (at least 0.15 needed)
COS1 (COS_1): cut the Top trace at (90.1566, 104.3633) (r = 10.77 mm, 156.1 deg); vias COS1_1 at (89.8507, 103.8471) and COS1_2 at (90.4625, 104.8795), clearance 0.35 mm (at least 0.15 needed)
TX1 (TX_1): both ends at (86.1, 100) (r = 13.90 mm, 180.0 deg), Top and In2; extend the Top end to a via TX1_1 at (85.1989, 99.3691) and the In2 end to a via TX1_2 at (85.1989, 100.6309), clearance 0.54 mm (at least 0.15 needed)
SIN2 (SIN_2): cut the Top trace at (122.1345, 106.7134) (r = 23.13 mm, 16.9 deg); vias SIN2_1 at (122.4775, 107.2057) and SIN2_2 at (121.7916, 106.2211), clearance 0.20 mm (at least 0.15 needed)
COS2 (COS_2): cut the Top trace at (122.6856, 95.4865) (r = 23.13 mm, 348.7 deg); vias COS2_1 at (123.2201, 95.759) and COS2_2 at (122.151, 95.214), clearance 0.20 mm (at least 0.15 needed)
TX2 (TX_2): both ends at (126.1, 100) (r = 26.10 mm, 0.0 deg), Top and In2; extend the Top end to a via TX2_1 at (126.291, 101.0833) and the In2 end to a via TX2_2 at (126.291, 98.9167), clearance 0.15 mm (at least 0.15 needed)
```

Route set 1's leads out across set 2 on the free Bottom layer (see
[Board Features - Dual Generator](Board-Features-Dual-Generator.md#182-layers)).

## 19.3 Settings

The settings are in `Dual Generator/Parameters/Dual_SilkScreenSuggestion_Parameters.py`. They have the same names, defaults
and ranges as the Single Generator's (see
[Parameter Reference Single Generator](Parameter-Reference-Single-Generator.md#216-silkscreen-suggestion-silkscreensuggestion_parameterspy)),
except `SILKSCREEN_BREAK_LAYERS` (`["F.Cu", "In1.Cu"]`). `SILKSCREEN_SUGGESTION = False` leaves the stator file
without silkscreen; every picture on the other Dual Generator pages is made that way. The step never stops a
generation: a wrong value falls back to its default with a warning.

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.webp)

| Previous | Next |
|:---|---:|
| [Board Features - Dual Generator](Board-Features-Dual-Generator.md) | [Quick Guide To Parameters Selections - Dual Generator](Quick-Guide-To-Parameters-Selections-Dual-Generator.md) |
