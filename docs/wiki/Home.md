<div align="center">

<img src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_200px.gif" alt="Sinusoidal Coil Generator logo: a rotor turning over stator coils" width="200">

</div>

# 1. Inductive Encoder Sinusoidal Coil Generator Wiki

An open, all-in-one coil generator for rotary inductive encoders: set the parameters, get a stator and rotor as KiCad boards, and, once finished, check them with the analyser and optimizer (under construction on the [`analyser_and_optimizer` branch](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/tree/analyser_and_optimizer)).

There are two generators. The **Single Generator** builds one coil set on a stator. The **Dual Generator** builds two
coil sets on one stator, a coarse absolute track and a fine track, each read by its own IC, and one rotor disc with two
rings; see [Stator Features - Dual Generator](Stator-Features-Dual-Generator.md).

The goal is to make 20-bit and higher rotary encoding available to anyone, with nothing more than KiCad and a PCB order, and to bring the price of such encoders down from hundreds or thousands of dollars to tens.

## 1.1 Why This Project

Inductive position sensors measure angle with nothing more than copper traces on printed circuit boards. They have no
magnets, no optics and no contact, so they tolerate dust, oil, vibration, stray magnetic fields and wide temperature
swings. The difficult part has always been the coil design. This project automates it: it generates complete,
ready-to-open KiCad boards for the stator and the rotor from a small set of parameter files, checks the design, and
estimates how it will perform.

> [!IMPORTANT]
> No output of the tool (boards, KiCad and manufacturing files, pictures) may be used commercially unless you accept
> the [commercial terms](License.md#322-commercial-use) (0.2 % of the net sale price, all of it invested back into the
> project and on record) or have the author's written permission. See [License](License.md#321-output-of-the-tool).

> [!IMPORTANT]
> Hardware validation is still pending. Every voltage, frequency, inductance and accuracy figure in this wiki is a
> model estimate.

## 1.2 Links

- [Repository README](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator#readme)
- [Web Tool](https://ro-h-bots.blogspot.com/p/inductive-encoder-sinusoidal-coil.html)

| Previous | Next |
|:---|---:|
|  | [Contents](Contents.md) |
