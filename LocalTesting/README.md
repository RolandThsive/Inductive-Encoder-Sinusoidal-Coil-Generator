# Local Testing

This branch (`WebUI_LocalTesting`) is how the Web GUI is tried out on a desktop before it goes live.
It replaces the old test zip: the branch itself is the tester, and it always holds the latest Web GUI.

## Try it

1. Download or clone this branch.
2. Windows: double-click `LocalTesting/Start-Windows.bat`.
   Mac / Linux: run `LocalTesting/Start-Mac-Linux.command` (double-click, or in a terminal).
3. A small local web server starts (needs Python 3) and the page opens in your browser at `http://localhost:8000/WebGUI/`.
   If port 8000 is busy it uses the next free one; the window shows the address.
4. The first start downloads Python for the browser (Pyodide, about 20 MB) from the internet; later starts are cached.

Caching is switched off in the test server, so the browser always loads the files of this branch.

Why a server instead of double-clicking `WebGUI/index.html`: browsers block the background Python thread and file
loading on `file://` pages, so the page has to come from `http://`.

## How the tester is made

The tester is the repository itself. Nothing is built or copied.

- `serve.py` serves the repository root (the folder above `LocalTesting/`) so that `WebGUI/` and `Single Generator/`
  (the generator and its parameter files) sit side by side, as they do on GitHub Pages. The page finds the generator at
  `../Single Generator/` from `WebGUI/`.
- The Start scripts only run `serve.py`.
- Python for the browser (Pyodide) is loaded from a CDN, as on the live site.

The generator and parameter files are Roland's, unchanged; only the Web GUI (`WebGUI/`) and this folder are ours.

## Keeping it current

This branch is kept equal to the newest Web GUI work:

1. Pull the working branch into it: `git checkout WebUI_LocalTesting && git merge origin/WebUI_modifs`
   (and `origin/main` when the generator changes), then push.
2. Nothing else: there is no zip to rebuild.
3. Changes to `LocalTesting/` are made on this branch only; they never go into `WebUI` or `main`.

## How the screenshots were made

Screenshots for review (portrait and landscape) were taken with Playwright and the Chromium that ships with it:

1. Serve the repository root with any static server (the same `serve.py` works).
2. Open `WebGUI/index.html` in a headless Chromium at the wanted window size (for example 1600 x 950 landscape and
   1080 x 1920 portrait), wait until the Generate button is enabled and the progress bar is idle, then call
   `page.screenshot`.
3. To show a state, click the controls first: a `+` stepper makes the "Settings changed" notice appear; Advanced
   parameters are the fields `[data-name=NAME]` under the tabs `#adv-tabs button`; the layer chips are `.layer-chip`.
4. Tooltips hide on scroll, so move the mouse onto the info dot after the last scroll and wait about a second.

## Checks before a design goes live

- The default design generates with no warnings (about 0.2 to 0.4 s).
- Import then Export gives back the same parameter files.
- The page works at 1920, 1600, 1100 and 1080 px wide, and the top bar keeps one line.
