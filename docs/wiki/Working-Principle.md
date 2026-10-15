# Induction Encoding - Rotary Working Principle

![Introduction 1: Working Principle](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/intro_1_working_principle.png)

*Introduction 1. A: Side view of the sensor. B: A generated 1-loop stator with its rotor. C: The
receiver signals over one rotor turn, from the project's analyser. D: The angle recovered from the
two signals.*

1. **Excitation.** The transmitter coil (TX) on the stator carries an alternating current, usually
   between 2 and 5 MHz, set by an LC oscillator in the receiver IC.
2. **Target.** The rotor is a PCB with copper lobes. The TX field induces eddy currents in the
   copper, and these currents push the field away from the area each lobe covers.
3. **Reception.** Two receiver coils (RX) sit inside the TX ring. Each is a sinusoidal loop,
   wound so that it picks up no voltage from a uniform field. As the rotor turns, the uncovered
   area under each coil changes, so the induced voltage follows a sine (SIN coil) and a cosine
   (COS coil) of the rotor angle.
4. **Decoding.** The receiver IC (for example the Renesas IPS2550 or IPS2200) demodulates both
   signals. The angle within one electrical period is `atan2(SIN, COS)`.

The generator works with **four phases only: two SIN/COS pairs, each with a positive and a negative
half** (phases 0/2 form the SIN coil, phases 1/3 the COS coil). This differential arrangement
cancels the direct coupling from the TX and common-mode interference.

## Previous

[Examples](Examples.md)

## Next

[RX Profiles](RX-Profiles.md)
