# Choosing A Rotor And Stator

- A **stator loop** is one full electrical period: one sine wave of the RX coils around the board.
- A **rotor lobe** is one copper sector on the rotor. The rotor always has as many lobes as the
  stator has loops.
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

**Absolute And High Resolution Together.** Combine a 1-loop track with a multi-loop track
(vernier or coarse/fine). This needs two receiver ICs and is planned as the dual-IC version.

## Previous

[TX Profiles](TX-Profiles.md)

## Next

[Stator Features](Stator-Features.md)
