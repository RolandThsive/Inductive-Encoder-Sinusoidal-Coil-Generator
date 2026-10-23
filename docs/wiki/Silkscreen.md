# 14. Silkscreen

The generator's coils have no terminals. Every RX coil (SIN and COS) is one closed loop, and the two ends of the TX coil
lie on top of each other at the end of its tail, one on each of its two layers. To connect the coils to the receiver IC
you break each RX loop at one place, set a via at each side of the cut, extend each TX end to a via of its own, and
route from those vias to the IC.

The last step of every generation draws a **suggestion for these cuts on the silkscreen** of the finished
`Stator.kicad_pcb`. The silkscreen is there for **guidance only**: it shows where the breaks and the via sites have room
on every layer, so you can make the cuts in KiCad without searching for a free spot by hand. It changes no copper. The
marks are plain drawings on `F.SilkS` and `B.SilkS`; you may follow them, move them, or delete them once the leads are
routed.

## 14.1 What Is Drawn

| Coil | Marks | Lead Names |
|---|---|---|
| RX coil (SIN, COS) | A dashed box around the break and a filled dot at each of the two via sites. Cut the trace between the two dots and put one via on each dot | `SIN_1`, `SIN_2`, `COS_1`, `COS_2` |
| TX coil | A filled dot at each of the two via sites beside the stacked end, and a dashed line from the end to each site. Extend each end along its dashed line to its dot | `TX_1 TOP`, `TX_2 BOT`: each end with its layer |
| Option | A dot on every via the generator placed (`SILKSCREEN_DOT_ON_ALL_VIAS = True`) | |

The names are drawn with the repository's own stroke font (`resources/SilkscreenFont.py`: capitals, digits and a few
signs), not as KiCad text, and each name is placed where it covers no other mark, name or via. The text on `B.SilkS` is
mirrored, so it reads correctly from the bottom.

![Silkscreen 1: Lead-Cutting Suggestion On A Single Generator Board](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/silkscreen_single_zoom.png)

*Silkscreen 1. The suggestion as written into `Stator.kicad_pcb` on a Single Generator board (RX on Top and Bottom, TX
on Bottom, its tail end on Top). Top row: the top view with `F.SilkS`, the whole board and the area at the TX terminal enlarged. Bottom row:
the bottom view, mirrored, with `B.SilkS` and the copper seen through. RX: cut the trace between the two dots, one via
per dot. TX: extend each end along the dashed line to its dot.*

## 14.2 Where The Breaks Go

The step reads the written board and looks for a spot on each coil where both vias have room on every layer:

- The break is looked for on the coil's traces within `SILKSCREEN_SEARCH_SPAN_DEG` (30°) of the TX terminal, which the
  generator turns to 0° (the right), so all leads come together at one place.
- The two vias of a break sit `SILKSCREEN_BREAK_VIA_GAP_MM` (1.2 mm) apart along the trace; the piece between them is
  what you cut. The gap must be at least `VIA_DIAMETER_MM + MIN_CLEARANCE_MM`.
- The layers in `SILKSCREEN_BREAK_LAYERS` (`F.Cu`, then `B.Cu`) are tried in order; the first with a spot that has room
  is used.
- Every via of the suggestion keeps `MIN_CLEARANCE_MM` from all copper on every layer, and
  `SILKSCREEN_VIA_EDGE_CLEARANCE_MM` (0.25 mm) from the bore and the outline.
- The two breaks and the TX end stay at least `SILKSCREEN_BREAK_SEPARATION_MM` (4 mm) apart, so the marks and names do
  not land on each other.
- The two via sites of the TX end are looked for up to `SILKSCREEN_TX_SITE_REACH_MM` (2 mm) from the stacked end.

The result is printed in the run and appended to `Parameters.txt` under "LEAD CUTTING SILKSCREEN SUGGESTION", with the
coordinates of every cut and via site on the KiCad page, for example:

```text
SIN (2): cut the Top trace at (115.9631, 95.5137) (r = 16.58 mm, 344.3 deg); vias SIN_1 at (116.1705, 96.0767) and SIN_2 at (115.7558, 94.9506), clearance 0.41 mm (at least 0.2 needed)
TX (TX): both ends at (126.3, 100) (r = 26.30 mm, 0.0 deg), Top and Bottom; extend the Top end to a via TX_1 at (126.0153, 101.0625) and the Bottom end to a via TX_2 at (126.0153, 98.9375), clearance 0.51 mm (at least 0.2 needed)
```

## 14.3 Settings

The settings are in `Single Generator/Parameters/SilkScreenSuggestion_Parameters.py`; each one is described in the
[Parameter Reference Single Generator](Parameter-Reference-Single-Generator.md#216-silkscreen-suggestion-silkscreensuggestion_parameterspy).
The step never stops a generation: a wrong value falls back to its default with a warning, and anything the step cannot
do (no spot with room, no free place for a name, a missing font) is printed as a warning while the boards are written
as usual.

| Setting | Default | Effect |
|---|---|---|
| `SILKSCREEN_SUGGESTION` | `True` | `False` leaves the stator file without silkscreen |
| `SILKSCREEN_SIDES` | `"both"` | `"both"`, `"top"` (`F.SilkS` only) or `"bottom"` (`B.SilkS` only) |
| `SILKSCREEN_COLOR` | `"#FFFFFF"` | Colour of every mark in KiCad; the fab prints in its own ink regardless |
| `SILKSCREEN_LABELS` | `True` | Write the lead names next to the via sites |
| `SILKSCREEN_TEXT_SIZE_MM` | `0.5` | Height of a capital (mm) |

Most fabs need silkscreen lines of at least 0.1 to 0.15 mm and text of about 0.8 mm height to print it readably;
raise `SILKSCREEN_TEXT_SIZE_MM` and `SILKSCREEN_TEXT_STROKE_MM` if the marks are to be printed and not only read in KiCad.

## 14.4 Related Pages

- [Silkscreen - Dual Generator](Silkscreen-Dual-Generator.md): the same suggestion for both coil sets of a dual board.
- [Board Features](Board-Features.md): what else the generator writes into the board.

| Previous | Next |
|:---|---:|
| [Board Features](Board-Features.md) | [Quick Guide To Parameters Selections](Quick-Guide-To-Parameters-Selections.md) |
