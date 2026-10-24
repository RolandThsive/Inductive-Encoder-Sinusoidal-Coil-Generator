# 10. Choosing A Rotor And Stator

- A **stator loop** is one full electrical period: one sine wave of the RX coils around the board.
- A **rotor lobe** is one copper sector on the rotor. The rotor must have as many lobes as the
  stator has loops (a custom rotor with another count gets a warning). Lobe can also mean half an
  RX period (see the [Glossary](Glossary.md)).
- The receiver IC reports the angle within one electrical period. With N loops, that period covers
  360°/N of mechanical rotation.

| Loops / Lobes | Unique Range | Encoding Type | Extra Resolution From The Coil | Typical Use |
|---|---|---|---|---|
| 1 | 360° | True absolute over the full turn | None (reference) | Absolute joint angle, steering, knobs, output shafts |
| 2 | 180° | Absolute within half a turn | ×2 (+1 bit) | Mechanisms with less than 180° of travel |
| 3 | 120° | Absolute within a third of a turn | ×3 (+1.6 bits) | Limited-travel joints |
| 4 | 90° | Absolute within a quarter turn | ×4 (+2 bits) | Motor commutation for 4 pole-pair motors |
| 8 | 45° | Absolute within 45°, turns counted | ×8 (+3 bits) | Motor commutation and speed control |
| 16 | 22.5° | Absolute within 22.5°, turns counted | ×16 (+4 bits) | High-resolution motor encoders |

**Absolute 0–360° Encoding.** Use 1 loop. The output is unique over the whole turn from power-up.

**Higher Resolution.** Use more loops. Each loop repeats the full electrical range, so the
resolution per mechanical degree rises by the number of loops. The position is then unique only
within one period, and the turn count must be tracked from a homing or index position.

**Motor Commutation.** Match the loop count to the motor's pole-pair count, so that each electrical
period of the sensor lines up with one electrical period of the motor.

**Absolute And High Resolution Together.** Combine a 1-loop track with a multi-loop track (coarse / fine). The
[Dual Generator](Stator-Features-Dual-Generator.md) builds exactly this: a coarse inner set (1 loop by default) and a
fine outer set (16 loops by default) on one stator, each read by its own receiver IC, and one rotor disc with a ring for
each set. The coarse angle says which period of the fine track the rotor is in, and the fine track gives the
resolution. This works as long as the coarse angle error stays below half a fine period: 180 / `LOOPS` of the fine set
mechanical degrees (±11.25° for 16 loops). Keep the coarse rotor ring away from the fine RX band, or it adds an error
once per turn that no fine-track calibration removes (see
[Rotor Features - Dual Generator](Rotor-Features-Dual-Generator.md#173-distances-between-the-rings)).

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.webp)

| Previous | Next |
|:---|---:|
| [TX Profiles](TX-Profiles.md) | [Stator Features](Stator-Features.md) |
