# Inductive Encoder Sinusoidal Coil Generator Wiki

An open, all-in-one coil generator for rotary inductive encoders: set the parameters, get a stator and rotor as KiCad boards, and check them with the built-in analyser and optimizer.

The goal is to make 20-bit and higher rotary encoding available to anyone, with nothing more than KiCad and a PCB order, and to bring the price of such encoders down from hundreds or thousands of dollars to tens.

## Why This Project

Inductive position sensors measure angle with nothing more than copper traces on printed circuit boards. They have no
magnets, no optics and no contact, so they tolerate dust, oil, vibration, stray magnetic fields and wide temperature
swings. The difficult part has always been the coil design. This project automates it: it generates complete,
ready-to-open KiCad boards for the stator and the rotor from a small set of parameter files, checks the design, and
estimates how it will perform.

> [!IMPORTANT]
> Hardware validation is still pending. Every voltage, frequency, inductance and accuracy figure in this wiki is a
> model estimate.

## Links

- [Repository README](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator#readme)
- [Web Tool](https://ro-h-bots.blogspot.com/p/inductive-encoder-sinusoidal-coil.html)

## Next

[Contents](Contents.md)
