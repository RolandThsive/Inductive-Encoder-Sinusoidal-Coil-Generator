# 31. Future Upgrades And Planning

| Upgrade | Description |
|---|---|
| **Desktop GUI** | A graphical interface in its own folder, built on top of the existing code without changing it. It will preview the coils as the parameters change and generate the KiCad boards. |
| ~~**Web Tool**~~ | ~~A browser version on my website that generates and downloads KiCad boards.~~ |
| **Field-Compensated RX Profile** | An RX shape bent by the modelled TX field. Research underway; the profile was removed from the generator in V18 and returns with the field model. |
| **Better Models From Real Hardware** | Measured boards will be used to correct the field, eddy-current and electrical models. Contributors with test equipment are very welcome. |
| **Custom IC Section** | A more robust analyser with a configurable IC section, so that any receiver IC can be described and the generated coils checked against it. |
| ~~**Dual-IC Version**~~ | ~~Coils for two receiver ICs, giving redundancy and higher resolution (for example a 1-loop and a multi-loop track).~~ Now the [Dual Generator](Stator-Features-Dual-Generator.md). |
| **Arc Board Rotary Generator** | A generator for arc-shaped boards that cover part of a turn. |
| **Linear Board Generator** | A generator for linear (straight) inductive encoders. |
| **KiCad Plugin** | Packaging the generator as a KiCad add-on through the Plugin and Content Manager. |

*Strike-through means done.*

The generators, their testing and their examples are also the project's milestones, listed in
[`MILESTONES.md`](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/blob/main/MILESTONES.md).
When every milestone is done, the commercial fee stops and the project opens under a new license, the same as the GPL (see
[License](License.md#322-commercial-use)).

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [Immediate Next Steps](Immediate-Next-Steps.md) | [License](License.md) |
