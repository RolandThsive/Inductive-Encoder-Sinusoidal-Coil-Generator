# 24. License

The project uses three licenses, one for each kind of content, and an extra term on everything the tool produces
(24.1).

| Content | License | What it allows |
|---|---|---|
| Generator code (`Generator/`, `Parameters/`, and `Analyser_And_Optimizer/` on the analyser_and_optimizer branch) | [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) | Use, change and share, for noncommercial purposes |
| Documentation and images (`docs/images/` except the Web Tool pictures, `docs/wiki/` and this wiki, `README.md`, `CONTRIBUTING.md`) | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) | Share and adapt with credit, noncommercial, under the same license |
| Web Tool (`WebGUI/` and `.github/workflows/WebGUI-Pages.yml` on the `WebUI` branch, the published tool, its design, and the `docs/images/webui_*.png` pictures) | [PolyForm Strict 1.0.0](https://polyformproject.org/licenses/strict/1.0.0/) | Noncommercial use only; no changes and no redistribution |

The Web Tool's license covers the tool and every aspect of it: its code, design, layout, look and feel, colours,
controls, icons, preview and measuring tools, wording, help texts, and pictures and recordings of it. It does not
cover the core generator the tool runs, which stays under the code license above.

Commercial use of anything here needs the author's written permission. See the
[repository `LICENSE.md`](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/blob/main/LICENSE.md)
for an overview, the links to the full license texts and the contact details.

## 24.1 Output Of The Tool

**No output of the tool may be used commercially without the author's written permission.** This is an extra term,
in addition to the licenses above, and it applies to everything the generator, the analyser or the Web Tool produces,
whether run unchanged or from a changed copy, whole or in part:

- the KiCad board and project files and the board layouts,
- Gerber, drill and other manufacturing files made from them,
- the parameter records, pictures, reports and estimates the tool writes,
- and every printed circuit board, sensor or product made from any of these.

Commercial use means selling them or offering them for sale, building them into a product or service, using them
inside a company or startup for its business, or manufacturing them for a customer. Output may be used and shared for
noncommercial research, study, education and personal use. When you share output, keep the attribution and say that
it was made with the Sinusoidal Coil Generator, with a link to the repository. The term applies to anyone who uses the
generator or the Web Tool, and using them means accepting it. The same term is in the
[repository `LICENSE.md`](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/blob/main/LICENSE.md#output-of-the-generator).

## 24.2 Contributions

Contributions are welcome. This is the contributor agreement from the repository's
[`CONTRIBUTING.md`](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/blob/main/CONTRIBUTING.md#contributor-agreement).

By sending a pull request, patch, issue text, measurement, picture or any other contribution ("Contribution"), you
agree to the following, and you confirm it by adding the line `Signed-off-by: Your Name <email>` to every commit and to
the pull request description.

1. **You own it, or you may share it.** The Contribution is your own work, or you have the right to submit it under
   this agreement. It is not copied from a source whose terms forbid this (other projects, papers, datasheets,
   manufacturer designs, fonts, icons or code of unknown origin). If part of it comes from elsewhere, you name the
   source and its license in the pull request.
2. **No employer or third-party claim.** Your employer, school, client or anyone else has no claim to it, or has
   allowed you in writing to submit it.
3. **License to the project.** You grant the author (Roland / Ro-H-Bots) a worldwide, perpetual, irrevocable,
   royalty-free, non-exclusive license to use, copy, change, publish, distribute and sublicense the Contribution, in
   whole or in part, under this project's licenses or any other license the author chooses later, including a
   different or commercial license. You keep your own copyright.
4. **Patents.** You grant the author and every user of the project a perpetual, irrevocable, royalty-free license under
   any patent you own or control that the Contribution necessarily infringes. If you know of a patent that covers the
   Contribution, you say so in the pull request.
5. **Moral rights.** Where the law allows, you waive or will not enforce moral rights against the author and users of
   the project, except the right to be named: contributors are credited in the history and may be listed in the
   README.
6. **Same terms for output.** Your Contribution and everything made from it follow the project's terms, including the
   rule that no output may be used commercially without written permission (24.1).
7. **No obligation.** The author may refuse, change or remove any Contribution. The Contribution is given as is, without
   warranty.
8. **Public record.** Your name and email are kept in the public history of the repository.

Contributions that do not carry the sign-off are not merged.

## 24.3 KiCad

The generator writes boards that open in KiCad. This section explains why the project may name KiCad and write
KiCad's file format, and why that does not conflict with the terms above. It is the project's reading of KiCad's own
published statements, listed at the end. It is not legal advice and is not a statement by the KiCad project.

### 24.3.1 The Name "KiCad"

- **Who owns it.** "KICAD" is a registered United States trademark (registration 6568683, 23 November 2021) owned by
  LF Projects, LLC, for electronic design automation software and its documentation.
- **How this project uses it.** Only to say what the generator works with: "generates KiCad boards", "opens in KiCad
  7, 8, 9 and 10", "KiCad 7 board format". This is a descriptive use of the name, which is the ordinary way to state
  compatibility with another product. It does not suggest that the KiCad project made, checked or supports this tool.
- **What this project does not do.** It does not use the KiCad name in its own name, does not use the KiCad logo, and
  does not present the generator, the Web Tool or their boards as part of KiCad.
- **No affiliation.** KiCad is a trademark of LF Projects, LLC. This project is not affiliated with, sponsored by or
  endorsed by KiCad or LF Projects, LLC.

### 24.3.2 The File Format

- **The format is published.** KiCad documents its file formats openly for developers, including the board format the
  generator writes (the s-expression `.kicad_pcb` format, used by every KiCad version from 6.0). The documentation sets
  no license condition on reading or writing the format.
- **The generator writes the format from scratch.** Its writer (`Generator/Core/PCBWriter.py`) builds the text of
  the file itself, using only Python's standard library and NumPy. It does not contain, copy or link any KiCad source
  code, does not use KiCad's Python interface, and does not use any KiCad library (symbols, footprints or 3D models).
  Every board is made only of tracks, vias, outlines and polygons drawn by the generator, on KiCad's standard layer
  names, which the format itself defines.
- **Using `.kicad_pcb`.** The file extension and the format are what let KiCad open the board. Using them describes
  what the file is, and makes no claim that KiCad produced it.

### 24.3.3 KiCad's License And The Generated Boards

- **KiCad's license covers KiCad.** KiCad is licensed under the GNU General Public License version 3 or later. That
  license governs KiCad's own source code and copies of KiCad. It does not apply to a separate program that only
  writes files KiCad can read, and it does not apply to those files.
- **KiCad places no license on designs.** On the KiCad forum, KiCad's project leader is quoted as saying that using
  KiCad's libraries does not make the project the owner of a design, and its maintainers and users agree that KiCad's
  license does not reach the boards people make. KiCad's libraries are under CC BY-SA 4.0 with an exception that frees designs and generated files
  that use them. The generator does not use those libraries at all, so nothing from KiCad is carried into its boards.
- **So the terms of this project apply.** Because neither KiCad's license nor its libraries reach the generator's
  boards, the boards and files the generator makes are under this project's terms alone, including the extra term
  on output in 24.1. Opening, editing or saving such a board in KiCad does not change that.
- **KiCad itself stays free.** Nothing here limits anyone's use of KiCad. The terms on this page apply to this
  project's code, documentation, Web Tool and output, not to KiCad.

### 24.3.4 Sources

- KiCad trademark: United States trademark registration 6568683, "KICAD", owner LF Projects, LLC
  ([record](https://trademarks.justia.com/904/76/kicad-90476958.html)).
- KiCad's license: [About KiCad](https://www.kicad.org/about/kicad/) ("licensed under GNU GPL v3") and
  [KiCad licenses](https://www.kicad.org/about/licenses/).
- File format: [KiCad file formats](https://dev-docs.kicad.org/en/file-formats/) and the
  [board file format](https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/index.html).
- Libraries and designs: [KiCad library license](https://www.kicad.org/libraries/license/) ("Use of the library data
  in a project does not (by itself) require that the design or any files generated from the design are licensed under
  the CC-BY-SA 4.0 License.").
- Designs and KiCad's license, as discussed by KiCad's maintainers and users:
  [KiCad forum, "License for project made with KiCad"](https://forum.kicad.info/t/license-for-project-made-with-kicad/6552).

| Previous | Next |
|:---|---:|
| [Future Upgrades And Planning](Future-Upgrades-And-Planning.md) |  |
