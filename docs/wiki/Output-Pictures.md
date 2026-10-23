# 27. Output Pictures

Every run that writes both boards also draws two SVG pictures of them into the same output folder, next to
`Stator.kicad_pcb`, `Rotor.kicad_pcb` and `Parameters.txt`:

- `<folder name>_Representative.svg`: a picture of the board for people, with a title, a legend and the layers made
  easy to tell apart.
- `<folder name>_Actual.svg`: the copper of the board as it is, 1:1 in mm, with no text and nothing widened.

Both are drawn by `resources/RepresentativeSVGMaker.py` and `resources/ActualSVGMaker.py`. They read only the two
`.kicad_pcb` files the run wrote, need nothing but Python 3, and open in any browser. In both, the stator is on the
left and the rotor on the right, and the layers have the same colours: Top red, Inner 1 green, Inner 2 yellow,
Bottom blue.

## 27.1 Representative And Actual

| | Representative | Actual |
|---|---|---|
| Made for | Looking at a design, sharing it, documentation | Using the copper elsewhere: Inkscape, overlays, mechanical drawings |
| Size | Opens 2240 px wide and scales without loss | 1:1: width and height in mm, with 1 mm around the boards |
| Text | A title (loops, TX turns per layer, board radii, and the air gap when given), the names Stator and Rotor, a legend, and a line saying which layers carry the RX and the TX | None |
| Trace widths | Inner 2 and Bottom are drawn 1.9 times wider when Top has copper, so copper lying under Top shows as an edge on both sides of the Top trace | Every trace at its true width with round ends, as KiCad draws a track |
| Vias | Solid dots of the via size | A copper ring with the drill as a hole, on every copper layer the via passes through |
| Rotor copper | Top copper filled; the copper of each layer under Top as a dashed outline in its layer colour (Inner 1 green, Inner 2 amber, Bottom violet), heavier the deeper it lies | Filled, layer by layer |
| Board | The stator ring filled light green; both board edges drawn | Only the `Edge.Cuts` circles, at their own line width; no fill and no background |
| Layers in the file | One flat drawing | One group per board (`Stator`, `Rotor`), holding one Inkscape layer per copper layer with copper (`F_Cu`, `Inner_1`, `Inner_2`, `B_Cu`) and `Edge_Cuts`, stacked as on the board |
| Left out | Silkscreen and solder mask | Silkscreen, solder mask and anything else that is not copper or the board edge |

In short: open the Representative picture to see what was built. Use the Actual picture when you need the copper
itself, at its true size. Inkscape shows and hides its layers one by one, so you can, for example, look at Inner 2
alone.

## 27.2 Single Generator

The pictures of the default Single Generator board (`Coil_15_27_1_1_3_Single_SteppedDiagonal`: 1 loop, TX 3 turns per
layer, board radius 15 to 27 mm), as the generator writes them.

![Output Pictures 1: Single Generator, Representative](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/output_pictures_1_single_representative.png)

*Output Pictures 1. `Coil_15_27_1_1_3_Single_SteppedDiagonal_Representative.svg`. Bottom is drawn wider than it is, so
it stays visible where it lies under Top; the line under the legend says so.*

![Output Pictures 2: Single Generator, Actual](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/output_pictures_2_single_actual.png)

*Output Pictures 2. `Coil_15_27_1_1_3_Single_SteppedDiagonal_Actual.svg` of the same board, shown on white (the file
has no background). The copper is at its true width, and the vias are rings with their drill holes.*

![Output Pictures 3: Single Generator, the same area in both pictures](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/output_pictures_3_single_closeup.png)

*Output Pictures 3. The same 10 × 10 mm at the upper left of the stator, cut from both files. Representative: the
Bottom traces wider than they are, the vias as dots, the board filled. Actual: every trace at its width, every via a
copper ring.*

## 27.3 Dual Generator

The pictures of the default Dual Generator board (`DualCoil_7.25_26.875_1x16_4x4`: 1 and 16 loops, TX 4 + 4 turns per
layer, board radius 7.25 to 26.875 mm), as the generator writes them.

![Output Pictures 4: Dual Generator, Representative](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/output_pictures_4_dual_representative.png)

*Output Pictures 4. `DualCoil_7.25_26.875_1x16_4x4_Representative.svg`. The TX turns on Inner 2 lie exactly under those
on Top, so Inner 2 is drawn wider and shows as a yellow edge along each Top turn of both TX rings.*

![Output Pictures 5: Dual Generator, Actual](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/output_pictures_5_dual_actual.png)

*Output Pictures 5. `DualCoil_7.25_26.875_1x16_4x4_Actual.svg` of the same board, shown on white. At its true width,
Inner 2 is hidden under Top and shows only where the TX ends leave the rings.*

![Output Pictures 6: Dual Generator, the same area in both pictures](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/output_pictures_6_dual_closeup.png)

*Output Pictures 6. The same 10 × 10 mm at the outer TX terminal (0°, the right of the stator), cut from both files.
Representative: Inner 2 along every Top TX turn, the vias as dots. Actual: Inner 2 only where it leaves Top, the vias as
rings.*

## 27.4 When They Are Made

- At the end of every Single and Dual run that writes both boards, after `Parameters.txt` and the silkscreen
  suggestion. A run with `--stator` or `--rotor` writes one board and makes no pictures.
- A picture that cannot be made (a maker missing from `resources/`, or an error while drawing) is printed as a yellow
  warning, `WARNING picture not made by <file>: <reason>; the boards are not affected`, and counted in the run's
  warnings. The boards and `Parameters.txt` are already written, and the run still ends with `SUCCESS`, in either
  `GENERATOR_MODE`. See [Checks, Errors And Warnings](Checks-Errors-And-Warnings.md).
- The [Web Tool](Web-Tool.md) does not make them: its zip holds the boards, `Parameters.txt` and the parameter files.
  Unzip it and run the makers on the run's folder to get them.

## 27.5 Making Them By Hand

Both makers run on any folder that holds `Stator.kicad_pcb` and `Rotor.kicad_pcb`, or on the two files given stator
first. From the repository folder:

```bash
python resources/RepresentativeSVGMaker.py "Single Generator/Output/<folder>"
python resources/RepresentativeSVGMaker.py "Single Generator/Output/<folder>" --air-gap 1     # Air gap in the title
python resources/RepresentativeSVGMaker.py "Single Generator/Output/<folder>" --title "My title" --out picture.svg
python resources/RepresentativeSVGMaker.py Stator.kicad_pcb Rotor.kicad_pcb

python resources/ActualSVGMaker.py "Dual Generator/Output/<folder>"
python resources/ActualSVGMaker.py "Dual Generator/Output/<folder>" --out board.svg
```

Without `--out`, the picture is written into the folder of the stator file under the names above, replacing a
picture of the same name. The look of the Representative picture is set at the top of `RepresentativeSVGMaker.py`:
the colours (`COLOUR`, `ROTOR_COPPER`), and `UNDER_TOP_WIDTH` (1.9; set it to 1.0 to draw every trace at its true
width).

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [Project Output Organization](Project-Output-Organization.md) | [KiCad Compatibility](KiCad-Compatibility.md) |
