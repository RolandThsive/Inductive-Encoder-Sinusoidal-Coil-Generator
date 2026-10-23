# 4. Web Tool

Design the stator and rotor boards of a sinusoidal inductive encoder in your browser, see them straight away,
and download them as KiCad files. No installation and no account: everything runs on your own computer, and
nothing is sent to a server. The web tool runs the Single Generator unchanged, so the same settings give the same
boards. It runs the copy on the `WebUI` branch, which is older than `main`: it has no silkscreen suggestion and no blind
vias.

**[Open The Web Tool](https://ro-h-bots.blogspot.com/p/inductive-encoder-sinusoidal-coil.html)**

**[Open Quick Parameter Selection Guide](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/wiki/Quick-Guide-To-Parameters-Selections)**

> The Web Tool lives on the `WebUI` branch until it is merged; this page follows its [readme](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/blob/WebUI/WEBUIReadme.md).

## 4.1 Screenshots

The tool adapts to both landscape and portrait monitors. Both pictures show a generated 2-layer design: a board from 15 to 27 mm, 4 loops and 3 TX turns on Bottom.

![Web Tool 1: Landscape](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/webui_landscape.png)

*Web Tool 1. The Web Tool on a landscape monitor.*

![Web Tool 2: Portrait](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/images/webui_portrait.png)

*Web Tool 2. The Web Tool on a portrait monitor.*

## 4.2 Features

- **Basic and Advanced modes.** Basic has the main settings; Advanced has every parameter except the output settings and the ten that only feed the electrical estimate. Both use the same
  four tabs: Board, RX, TX and Rotor, and a change in one mode shows in the other.
- **Live board preview** of the stator, the rotor, or both together, with each copper layer in its own colour
  (Top red, Bottom blue, Inner-1 green, Inner-2 dark yellow), the same colours as the pictures in this wiki except a lighter blue for Bottom.
- **Design checks** before every board is made: errors and warnings that say what is wrong, why it matters and
  which settings to change.
- **KiCad downloads:** the stator and rotor `.kicad_pcb` files, or one zip with both boards and all the settings.
- **Help on every setting:** hover the **i** next to a name for a short explanation, with formulas where they help.
- **Save and share:** export your settings, import them later (also from the desktop version), or copy a link
  that opens the page with your design.
- **Measuring and inspection tools** in the preview: zoom, highlight a layer or a coil, hide parts, measure
  distances, turn the rotor.

## 4.3 Getting Started

1. Open the tool at [ro-h-bots.blogspot.com](https://ro-h-bots.blogspot.com/p/inductive-encoder-sinusoidal-coil.html). The first visit downloads the browser's Python engine (about 20 MB); later visits are quick.
2. The page starts with the default design, already generated.
3. Change settings in **Basic**, then press **Generate** (or Ctrl+Enter / Cmd+Enter).
4. Check the result in the preview and the **Checks** panel.
5. Press **Download Zip** to get your boards.

The tool needs a computer with a mouse or trackpad. Phones and tablets see a short message instead.

## 4.4 Setting Up A Design

### 4.4.1 Basic

| Tab | Settings |
| --- | --- |
| Board | Board inner and outer radius, 2 or 4 copper layers, air gap to the rotor |
| RX | Loops (sine periods per turn), RX sub-coils, and the RX band |
| TX | TX turns per layer, and the TX layout (wiring and layers), picked from picture cards |
| Rotor | Automatic (sized from the stator) or Custom, with the metal fraction and sectors |

Every Basic setting is also in Advanced, under the same name.

### 4.4.2 Advanced

Every parameter of the generator, grouped as in the parameter files, with two exceptions. The Output block of `Board_Parameters.py` (folder, file names, board centre, page size and `GENERATOR_MODE`, which is the **Strict** switch) is not shown. Neither are the ten settings that only feed the electrical estimate: `COPPER_THICKNESS_UM`, `COPPER_CONDUCTIVITY_S_M`, `TX_AC_RESISTANCE_FACTOR`, `STACKUP_PREPREG_MM`, `TANK_CAP_SERIES` and the five of `IC_Parameters.py` (`IC_NAME`, `IC_OSC_MIN_MHZ`, `IC_OSC_MAX_MHZ`, `IC_MIN_RP_OHM`, `IC_SPLIT_TANK_CAPS`). Each one shows its parameter name, and the
**↺** button puts it back to its starting value. Settings the current design does not use are greyed out and
marked "not used now". A changed setting gets a dot before its name.

### 4.4.3 The RX Band And The None Switches

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

## 4.5 Generating And Downloading

- **Generate** makes the boards and runs the checks. After you change a setting, the preview is marked out of
  date until you generate again; the downloads always match the last generated board.
- **Strict** (`GENERATOR_MODE = "strict"`) turns every warning about the finished boards into an error, so such a design is not generated.
- **Checks** lists the errors and warnings. Turn on **Info** to also see the generator's notes.
- **Summary** shows the generator's full report on the stator and the rotor.
- **Download Zip** gives both boards, `Parameters.txt` and the five parameter files (Board, RX, TX, Rotor and IC). **Download Stator** and
  **Download Rotor** give one `.kicad_pcb` each.

## 4.6 Errors And Warnings

The checks do more than say that something is wrong: each message tells you what to change to fix it.

- **What is wrong, with the numbers.** A message names the setting, its value and the limit it broke, for
  example that OUTER_EDGE_RADIUS_MM is too small, and the radius the board needs instead.
- **Why it matters.** It says what would go wrong on the board, such as vias overlapping, traces too close
  together, or no room left for the TX turns.
- **What to change.** It lists the settings that fix it and which way to move them, for example "raise
  OUTER_EDGE_RADIUS_MM, move the RX band in, or lower OUTER_EDGE_OFFSET_MM". The names are the parameter names
  shown in Advanced, so each one is easy to find.
- **Where it came from.** Each line is marked Error, Warning or Info, with the step that found it: the
  settings check, the stator or the rotor.

**Errors** stop the run. No board is made, the preview keeps the last board marked out of date, and the downloads
stay off until a run works. **Warnings** still make the boards but point at something to look at, often a
manufacturing limit such as a very fine trace or a small via ring. Turn on **Strict** to treat every warning about
the finished boards as an error. Settings that cannot hold together are named in the message ("A conflicts with B")
and the line below says why.

Some mistakes are blocked before they can happen: the RX band pairs lock each other, settings the design does not
use are greyed out, and a pair that must change together always does.

## 4.7 The Preview

- **Stator, Rotor, Overlay:** choose what to show. Overlay puts the rotor over the stator, and the **Rotor Angle**
  slider turns it.
- **Layer buttons** (Top, Inner-1, Inner-2, Bottom, Vias): hover to highlight, click to hide or show. Hovering
  Vias makes small vias easier to see.
- **Sin Loops, Cos Loops, TX Loops:** the same for each coil.
- **Zoom and move:** the mouse wheel zooms, dragging moves the board, and **Fit** (or a double-click) shows the
  whole board again. The centre marker button shows or hides the board centre.
- **Full screen:** the preview fills the screen; Esc leaves.
- **Measure:** click two points to see the distance. Press **S** to keep the line and draw another, **Z** to
  undo the last line or point.

The preview tools only change what you see, never the boards.

## 4.8 Saving, Sharing And Starting Over

- **Export Parameters** downloads the five parameter files, ready for the desktop version.
- **Import Parameters** loads a `Parameters.txt` from any run (web or desktop) or your own parameter files.
- **Share Link** copies a link that opens the tool with your design. Only your changes are in the link, and
  nothing is uploaded.
- **Reset** goes back to the default design, after asking.

## 4.9 What The Web Tool Does Not Include

The web tool makes the boards only. The receiver IC support, the electrical estimate, the optimizer and the analyser of the desktop project are not part of it, and neither are the silkscreen suggestion, blind vias (`VIA_TYPE`) and the Dual Generator.

## 4.10 How It Runs

The Web Tool is a static site (`WebGUI/` on the `WebUI` branch): `index.html`, `WebGUI.js`, `WebGUI.css`,
`BoardPreview.js`, `Tooltips.js`, `PyodideWorker.js` and `WebGenerator.py`. There is no server. The browser loads
Pyodide (Python and numpy compiled to WebAssembly) from the jsDelivr CDN, fetches the generator (`Single Generator/Generator/` and `Single Generator/Parameters/`)
from the same site, and runs them unchanged in a Web Worker. For the same settings the KiCad output is
byte-identical to a desktop run of the same generator copy. The generator is never modified for the web.

The tool is published with GitHub Pages and embedded in a page on the blog. Visitors' browsers fetch the
generator's `.py` files from Pages, so a new release updates the tool.

## 4.11 Run It Locally

Run `python3 -m http.server 8000` in the repository folder and open `http://localhost:8000/WebGUI/`.

Two URL parameters let you self-host the parts: `?pyodide=<url>` sets where the Python engine is loaded from, and
`?code=<url>` sets where the generator and its parameters are fetched from (default: the repository root).

## 4.12 Troubleshooting

- **Slow first load.** The first visit downloads about 20 MB (the Python engine); later visits are quick.
- **Old version after an update.** Hard-refresh the page (Ctrl+Shift+R / Cmd+Shift+R).
- **A message instead of the tool.** Touch-only devices (phones, tablets) are not supported; use a computer with a
  mouse or trackpad.

## 4.13 Privacy

The tool runs in the browser and sends nothing you enter to any server. Loading it does contact three outside
services, and each of them sees the visitor's IP address, as with any web page that loads files from them:

- **Google Fonts** (`fonts.googleapis.com`, `fonts.gstatic.com`) for the page's fonts,
- **jsDelivr** (`cdn.jsdelivr.net`) for the Python engine (Pyodide),
- **GitHub Pages**, which hosts the tool and the generator's files, and the blog that embeds it.

The fonts and the Python engine will be hosted on the tool's own site, so that Google and jsDelivr no longer see the
visitors. Until then, this is the case for every visit.

## 4.14 License

The web tool is under the PolyForm Strict License 1.0.0, separate from the generator's license: see
[WebGUI/LICENSE.md](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/blob/WebUI/WebGUI/LICENSE.md). It may be used for noncommercial purposes only, and may not be changed or
redistributed. The core generator it runs stays under the repository's own [LICENSE.md](https://github.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/blob/main/LICENSE.md).

[<img align="right" src="https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2.png" alt="Sinusoidal Coil Generator logo, click to see it spin" width="72">](https://raw.githubusercontent.com/RolandThsive/Inductive-Encoder-Sinusoidal-Coil-Generator/main/docs/logo/Logo_1_V2_rotor_spin_400px.gif)

| Previous | Next |
|:---|---:|
| [Getting Started](Getting-Started.md) | [Project Capabilities](Project-Capabilities.md) |
