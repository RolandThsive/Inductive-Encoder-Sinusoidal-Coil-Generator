# Inductive Encoder Coil Generator: Web Tool

Design the stator and rotor boards of a sinusoidal inductive encoder in your browser, see them straight away,
and download them as KiCad files. No installation and no account: everything runs on your own computer, and
nothing is sent to a server. The web tool runs the same generator as the desktop version, so the same settings
give the same boards.

**[Open The Web Tool](https://ro-h-bots.blogspot.com/p/inductive-encoder-sinusoidal-coil.html)**

## Features

- **Basic and Advanced modes.** Basic has the main settings; Advanced has every parameter. Both use the same
  four tabs: Board, RX, TX and Rotor, and a change in one mode shows in the other.
- **Instant sketch:** the Sketch view redraws the board on every change, before you press Generate.
- **Live board preview** of the stator, the rotor, or both together, with each copper layer in its own colour
  (Top red, Bottom blue, Inner-1 green, Inner-2 dark yellow).
- **Design checks** before every board is made: errors and warnings, each with a plain explanation of what to
  change.
- **KiCad downloads:** the stator and rotor `.kicad_pcb` files, or one zip with both boards and all the settings.
- **Help on every setting:** hover the **i** next to a name for a short explanation, with formulas where they help.
- **Save and share:** export your settings, import them later (also from the desktop version), or copy a link
  that opens the page with your design.
- **Measuring and inspection tools** in the preview: zoom, highlight a layer or a coil, hide parts, measure
  distances, turn the rotor.

## Getting Started

1. Open the tool at [ro-h-bots.blogspot.com](https://ro-h-bots.blogspot.com/p/inductive-encoder-sinusoidal-coil.html). The first visit downloads the browser's Python engine (about 20 MB); later visits are quick.
2. The page starts with the default design, already generated.
3. Change settings in **Basic**, then press **Generate** (or Ctrl+Enter / Cmd+Enter).
4. Check the result in the preview and the **Checks** panel.
5. Press **Download Zip** to get your boards.

The tool needs a computer with a mouse or trackpad. Phones and tablets see a short message instead.

## Setting Up A Design

### Basic

| Tab | Settings |
| --- | --- |
| Board | Board inner and outer radius, 2 or 4 copper layers, air gap to the rotor |
| RX | Loops (sine periods per turn), RX sub-coils, and the RX band |
| TX | TX turns per layer, and the TX layout, picked from picture cards |
| Rotor | Automatic (sized from the stator) or Custom, with the metal fraction and sectors |

Every Basic setting is also in Advanced, under the same name.

### Advanced

Every parameter of the generator, grouped as in the parameter files. Each one shows its parameter name, and the
**↺** button puts it back to its starting value. Settings the current design does not use are greyed out and
marked "not used now". A changed setting gets a dot before its name.

### The RX Band And The None Switches

The RX band is the ring the receiver coils swing across. You can give it in one of three ways:

| How | Set | Leave None |
| --- | --- | --- |
| By its radii | RX Inside Radius and RX Outside Radius | R Base and Swing A |
| By its centre and width | R Base and Swing A | RX Inside Radius and RX Outside Radius |
| From the board | Board Inner Radius and Board Outer Radius | all four RX band values |

- Turn a **None** switch on to leave that value to the generator.
- The two values of a pair always change together.
- While one pair has numbers, the other pair is **locked** at None. To switch from one way to the other, set the
  pair in use to None first; both pairs are then unlocked.
- A board edge set to None is worked out from the RX band. A board edge with a number is used exactly, and the
  checks tell you if it leaves too little room.

## Generating And Downloading

- **Generate** makes the boards and runs the checks. After you change a setting, the preview is marked out of
  date until you generate again; the downloads always match the last generated board.
- **Strict** turns every warning into an error, so a design with any warning is not generated.
- **Checks** lists the errors and warnings. Turn on **Info** to also see the generator's notes.
- **Summary** shows the generator's full report on the stator and the rotor.
- **Download Zip** gives both boards, `Parameters.txt` and the four parameter files. **Download Stator** and
  **Download Rotor** give one `.kicad_pcb` each.

## The Preview

- **Sketch, Stator, Rotor, Overlay:** choose what to show. Overlay puts the rotor over the stator, and the
  **Rotor Angle** slider turns it.
- **Sketch** is drawn straight from the settings on every change, with no Generate needed: the RX curves on their
  layers, the gold vias, the fingers, the TX turns and tails, the board edges and the rotor. It is an estimate for
  trying settings quickly; the TX steps, the windows around the fingers and some junction vias are simplified, and
  Field Compensated is drawn as Equal Area. If the settings cannot make a board, the Sketch says why.
- **Layer buttons** (Top, Inner-1, Inner-2, Bottom, Vias): hover to highlight, click to hide or show. Hovering
  Vias makes small vias easier to see.
- **Sin Loops, Cos Loops, TX Loops:** the same for each coil.
- **Zoom and move:** the mouse wheel zooms, dragging moves the board, and **Fit** (or a double-click) shows the
  whole board again. The centre marker button shows or hides the board centre.
- **Full screen:** the preview fills the screen; Esc leaves.
- **Measure:** click two points to see the distance. Press **S** to keep the line and draw another, **Z** to
  undo the last line or point.

The preview tools only change what you see, never the boards.

## Saving, Sharing And Starting Over

- **Export Parameters** downloads the four parameter files, ready for the desktop version.
- **Import Parameters** loads a `Parameters.txt` from any run (web or desktop) or your own parameter files.
- **Share Link** copies a link that opens the tool with your design. Only your changes are in the link, and
  nothing is uploaded.
- **Reset** goes back to the default design, after asking.

## What The Web Tool Does Not Include

The web tool makes the boards only. The receiver IC support, the optimizer, the analyser and the electrical
estimate of the desktop project are not part of it.

## Publishing On The Blog

1. Merge the web tool into `main`.
2. On GitHub: Settings > Pages > Source: **GitHub Actions**.
3. Actions > **Web GUI On GitHub Pages** > Run workflow. It runs again on every published release.
   The tool is then at `https://rolandthsive.github.io/Inductive-Encoder-Sinusoidal-Coil-Generator/WebGUI/`.
4. On Blogger: Pages > New Page, switch the editor to **HTML view**, paste all of `WebGUI/BloggerPage.html`,
   and publish.

To try it on your own computer, run `python3 -m http.server 8000` in the repository folder and open
`http://localhost:8000/WebGUI/`.

## License

The web tool is under the PolyForm Strict License 1.0.0, separate from the generator's license: see
[WebGUI/LICENSE.md](WebGUI/LICENSE.md). It may be used for noncommercial purposes only, and may not be changed or
redistributed. The core generator it runs stays under the repository's own [LICENSE.md](LICENSE.md).
