# 1. KiCad Compatibility

| Item | Detail |
|---|---|
| File Format | KiCad 7 board format (`version 20221018`) |
| Opens In | KiCad 7, 8, 9 and 10. Newer versions convert the file when it is saved |
| Contents | Tracks, vias, board outline (`Edge.Cuts`), rotor copper polygons and solder mask openings |
| Libraries | None needed: no footprints, symbols or 3D models are referenced |
| Nets | `TX`, SIN (`2`) and COS (`1`), so KiCad's ratsnest and DRC understand the coils |
| Layers | `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu` (Top, Inner-1, Inner-2, Bottom) |
| Title Block | Filled in automatically on every board |
| DRC | Clean apart from two expected `track_dangling` reports (the coils have no terminals yet) |

![KiCad 1: Title Blocks](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/kicad_1_title_block.png)

*KiCad 1. The title blocks of a generated stator and rotor, filled in `Keyword: Value` style.*

Because every TX turn is on the same net, KiCad's DRC cannot detect a TX turn touching another TX
turn. The generator runs this check itself and reports the smallest gap it found.

A KiCad plugin built on the same code is planned (see [Future Upgrades](Future-Upgrades-And-Planning.md)).

| Previous | Next |
|:---|---:|
| [Project Output Organization](Project-Output-Organization.md) | [Glossary](Glossary.md) |
