# Contributing

Thank you for your interest in the Sinusoidal Coil Generator. This is a research project. Researchers, students, hobbyists and curious engineers are completely welcome to use this open tool, and
contributions of every kind are welcome, from a measurement on a real board to a better field model.

> [!IMPORTANT]
> **Hardware validation is pending.** The first test boards have been ordered but have not yet been measured. Every
> voltage, frequency, inductance and accuracy figure in this project comes from its own models, so a measurement is the
> most valuable contribution there is.

## How Can You Help?

- **Measure real boards.** Boards made with the generator, measured with an RX voltage, TX inductance, oscillator
  frequency or angle-error test, show where the models are right and where they must be corrected.
- **Fund test boards and equipment.** Funds are being collected to order a wide range of coil PCBs and the test
  equipment to measure them.
- **Improve the models.** Better field, eddy-current and electrical models are welcome, including the field-compensated
  RX profile that is research underway.
- **Test the generator.** Generate boards with unusual settings, open them in KiCad and report anything that looks
  wrong or fails a check.
- **Improve the documentation and pictures.** Fix mistakes, clarify the wiki, or add examples.
- **Share knowledge.** Papers, datasheets and data on the encoders sold today are all useful.

## How Can You Get Involved?

1. Read the [README](README.md) and the [Wiki](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/wiki).
2. Run the generator from the `Single Generator` folder (see the Quick Start in the README) and look at what it builds.
3. Open an issue on GitHub to report a problem, ask a question or propose a change before starting larger work.
4. Send a pull request for a fix or improvement. Keep it focused, so that it is easy to review.
5. For measurements, hardware, funding or commercial use, get in touch by email:
   [rolandthsive@yahoo.com](mailto:rolandthsive@yahoo.com).

## Guidelines

- **Be honest about validation.** Say whether a number comes from a model or from a measurement, and keep the
  hardware-validation notice wherever figures are given.
- **Keep changes small and clear.** One topic per pull request, with a short description of what changed and why.
- **Check before you send.** Run the generator (`python Generator/Run/RunCoilGenerator.py --check` from the `Single
  Generator` folder) and make sure the parameter and geometry checks still pass.
- **Parameters stay in the parameter files.** The only files a user edits are in `Single Generator/Parameters/`.
- **Update the documentation with the code.** If a parameter, command or output changes, change the wiki and README to
  match.
- **Do not include secrets or personal data** in issues, pull requests or measurement files.
- **Be respectful.** Researchers, students, hobbyists and curious engineers are all welcome.

## License

The source code is licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/),
and the pictures and documentation under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). The Web
UI has its own license, [PolyForm Strict 1.0.0](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/blob/WebUI/WebGUI/LICENSE.md).
The full text and the required notices are in [LICENSE.md](LICENSE.md).

Any copy, fork or derived work must state clearly that it is derived from the Sinusoidal Coil Generator and link to the
original repository. **Commercial use, including of any output, requires written permission** from the author: contact
[rolandthsive@yahoo.com](mailto:rolandthsive@yahoo.com).
