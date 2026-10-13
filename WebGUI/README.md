# Web GUI

The coil generator as a web page: Basic and Advanced controls, a preview of the generated boards, the generator's checks, and one
zip per run (`Stator.kicad_pcb`, `Rotor.kicad_pcb`, `Parameters.txt` and the four parameter files), named like
the desktop output folder.

The generator is not rewritten. The page loads Python (Pyodide) and numpy in the visitor's browser, fetches
`Generator/` and `Parameters/` from this repository, and runs them unchanged. Nothing is sent to a server.
For the same parameters the boards are byte-identical to `RunCoilGenerator.py` on a desktop.
The page starts from the defaults in the parameter files, so its first board is the desktop's default board.

First release: generator only. No receiver IC, no optimizer, no analyser and no electrical estimate.

## Files

| File | What It Does |
| --- | --- |
| `index.html` | The page (works on its own, or inside the blog page) |
| `WebGUI.css` | The blog's look: colours, fonts, glass panels, Apple-style controls, silver switches with metal knobs, metal scrollbar |
| `WebGUI.js` | Controls (Basic / Advanced), preview buttons and keys, generate, downloads, Summary, share links, import / export, checks list |
| `BoardPreview.js` | Draws the generated boards (layer colours, zoom, pan, layer / loop highlight, via enlarge, origin marker, measure (S / Z), rotor overlay) |
| `PyodideWorker.js` | Loads Python in a background thread and fetches the generator files |
| `WebGenerator.py` | The Python side: writes the parameter files, runs the checks and the generator, builds the zip |
| `FutureConsiderations.md` | Features kept for later (the hidden Output block) |
| `BloggerPage.html` | The snippet for the Blogger page (hides the blog, full window, Back and Home buttons) |

The parameter list, defaults, help texts and "not used now" rules come from the parameter files and
`ParameterChecker.SPEC`, so new parameters appear in Advanced by themselves.

## Using The Page

- **Generate** runs the checks and the generator (Ctrl+Enter or Cmd+Enter does the same). Changing a setting
  afterwards marks the board as out of date until you press Generate again. The preview and the downloads
  only change on Generate.
- **Strict** treats warnings as errors, like `--strict` on the desktop: a design with any warning is not generated.
- **Stator / Rotor / Overlay** pick what the preview shows. Overlay draws the rotor over the stator, and the
  Rotor Angle slider turns it.
- **Layer chips** (F.Cu, In1.Cu, In2.Cu, B.Cu, Vias): hover to highlight a layer, click to hide or show it.
  A layer with no copper on this board is greyed out. Hovering Vias enlarges small vias to at least 6 px.
  This only changes the preview, never the boards.
- **Sin Loops, Cos Loops, TX Loops** work the same way for the SIN coil, the COS coil and the TX coil.
  The rotor has no coils, so they are not shown in the Rotor view.
- **Origin** (the circle icon beside Fit) shows or hides the board centre marker. Hover to highlight it.
- **Zoom and pan:** mouse wheel zooms, drag moves the board. **Fit** (or a double-click on the board) shows
  the whole board again.
- **Fullscreen** shows the preview full screen. Esc leaves it.
- **Measure:** click two points to get the distance between them. While Measure is on, press **S** to keep
  the line and draw another (up to 256), and **Z** to remove the last line or point. Switching Measure off or
  on clears every line.
- **Info** also lists the generator's information notes in Checks, not only warnings and errors.
- **Summary** shows the generator's full text summary of the stator and the rotor.
- **Download Zip** gives the whole run. **Download Stator** and **Download Rotor** give one `.kicad_pcb` each.
  All three work for the last run, and only while the settings are unchanged since then.
- **Share Link** copies a link that opens the page with your design. Only the values that differ from the
  starting design are in the link (after `#d=`), and nothing is uploaded.
- **Import Parameters** loads a `Parameters.txt` from any run (web or desktop) or your own `.py` parameter files.
  **Export Parameters** downloads `Parameter_Files.zip` with the four parameter files, ready for
  `RunCoilGenerator.py` on a desktop.
- **Reset** asks first, then goes back to the starting design.

## Going Live

1. Push the V10 generator to `main` (`Generator/` and `Parameters/` at the repository root).
2. On GitHub: Settings > Pages > Source: **GitHub Actions**.
3. Actions > **Web GUI On GitHub Pages** > Run workflow. It also runs on every published release.
   The tool is then at `https://rolandthsive.github.io/Inductive-Encoder-Sinusoidal-Coil-Generator/WebGUI/`.
4. On Blogger: Pages > New Page, switch the editor to **HTML view**, paste all of `BloggerPage.html`, publish.

If a later version imports a new module from `Generator/`, add it to `FILES` in `PyodideWorker.js`, to `GENERATOR_MODULES` in `WebGenerator.py` (so it is re-imported
with fresh parameters on every run) and to the check in `.github/workflows/WebGUI-Pages.yml`.

## Testing On A Computer

From the repository root: `python3 -m http.server 8000`, then open `http://localhost:8000/WebGUI/`.
Two query options help testing: `?pyodide=<url>/` loads Pyodide from another place, `?code=<url>/` fetches the
generator from another repository root.

Phones and small tablets (narrower than 1024 px, or touch only) get a short message instead of the tool.

Free for non-commercial use, like the generator.
