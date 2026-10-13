# Web GUI

The coil generator as a web page: Basic and Advanced controls, a live preview, the generator's checks, and one
zip per run (`Stator.kicad_pcb`, `Rotor.kicad_pcb`, `Parameters.txt` and the four parameter files), named like
the desktop output folder.

The generator is not rewritten. The page loads Python (Pyodide) and numpy in the visitor's browser, fetches
`Generator/` and `Parameters/` from this repository, and runs them unchanged. Nothing is sent to a server.
For the same parameters the boards are byte-identical to `RunCoilGenerator.py` on a desktop.
One starting value differs on the web: the RX net names are `SIN_Signal` and `COS_Signal` (`WEB_DEFAULTS` in
`WebGenerator.py`); the parameter files keep `"2"` and `"1"`.

First release: generator only. No receiver IC, no optimizer, no analyser and no electrical estimate.

## Files

| File | What It Does |
| --- | --- |
| `index.html` | The page (works on its own, or inside the blog page) |
| `WebGUI.css` | The blog's look: colours, fonts, glass panels, Apple-style controls, silver switches |
| `WebGUI.js` | Controls, Basic / Advanced, share links, import / export, checks list |
| `BoardPreview.js` | Draws the sketch and the real boards (layer colours, zoom, pan, measure, rotor overlay) |
| `PyodideWorker.js` | Loads Python in a background thread and fetches the generator files |
| `WebGenerator.py` | The Python side: writes the parameter files, runs the checks and the generator, builds the zip |
| `BloggerPage.html` | The snippet for the Blogger page (hides the blog, full window, Back and Home buttons) |

The parameter list, defaults, help texts and "not used now" rules come from the parameter files and
`ParameterChecker.SPEC`, so new parameters appear in Advanced by themselves.

## Going Live

1. Push the V10 generator to `main` (`Generator/` and `Parameters/` at the repository root).
2. On GitHub: Settings > Pages > Source: **GitHub Actions**.
3. Actions > **Web GUI On GitHub Pages** > Run workflow. It also runs on every published release.
   The tool is then at `https://rolandthsive.github.io/Inductive-Encoder-Sinusoidal-Coil-Generator/WebGUI/`.
4. On Blogger: Pages > New Page, switch the editor to **HTML view**, paste all of `BloggerPage.html`, publish.

If a later version imports a new module from `Generator/`, add it to `FILES` in `PyodideWorker.js` and to the
check in `.github/workflows/WebGUI-Pages.yml`.

## Testing On A Computer

From the repository root: `python3 -m http.server 8000`, then open `http://localhost:8000/WebGUI/`.
Two query options help testing: `?pyodide=<url>/` loads Pyodide from another place, `?code=<url>/` fetches the
generator from another repository root.

Phones and small tablets (narrower than 1024 px, or touch only) get a short message instead of the tool.

Free for non-commercial use, like the generator.
