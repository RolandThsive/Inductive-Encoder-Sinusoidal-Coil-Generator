/* PyodideWorker.js - runs the Python generator in a background thread, so the page never freezes.

   The page sends {id, cmd, args}; the worker answers {id, ok, result} or {id, ok: false, error},
   and sends {type: "progress", text} while it loads.  The commands:
     init      {pyodideBase, codeBase}  ->  {description, seconds}
     inactive  {values}                 ->  [names of the parameters the generator ignores]
     generate  {values}                 ->  {ok, items, name, files, summaries, rx, edges, center, seconds, zipBytes}
                                            (on a failed run: ok false, items and failed; no zipBytes)
     exportZip {values}                 ->  {zipBytes}
     readValues {text}                  ->  {name: value}

   On start ("init") it loads Pyodide and numpy, then fetches the generator's own .py files from the
   repository (codeBase: the repository root as served by GitHub Pages) into its in-memory file system. */

let pyodide = null;
const ROOT = "/coilgen";
// The generator is a package ("Single Generator/Generator"); GitHub Pages cannot list a folder, so the files are named
// here.  Not fetched: RunCoilGenerator.py (the desktop program) and TX_Electrics.py (the electrical estimate is not
// made on the web).  Each name is a path inside "Single Generator".
const GENERATOR_FILES = [
  "__init__.py",
  "Checks/__init__.py", "Checks/ConflictRules.py", "Checks/DesignChecks.py", "Checks/ParameterRules.py",
  "Core/__init__.py", "Core/BoardLayout.py", "Core/Conflict.py", "Core/Copper.py", "Core/Geometry.py",
  "Core/KiCadWriter.py", "Core/Layers.py",
  "Rotor/__init__.py", "Rotor/RotorBuilder.py",
  "Run/__init__.py", "Run/CheckParameters.py", "Run/OutputFolders.py",
  "Stator/__init__.py", "Stator/StatorAssembly.py",
  "Stator/RX/__init__.py", "Stator/RX/RX_Builder.py", "Stator/RX/RX_Coils.py", "Stator/RX/RX_Fingers.py",
  "Stator/RX/RX_Profiles.py",
  "Stator/TX/__init__.py", "Stator/TX/TX_Builder.py", "Stator/TX/TX_Shapes.py", "Stator/TX/TX_Terminal.py",
  "Stator/TX/TX_Windows.py", "Stator/TX/TX_Wiring.py",
];
const PARAMETER_FILES = ["Board_Parameters.py", "RX_Parameters.py", "TX_Parameters.py", "Rotor_Parameters.py", "IC_Parameters.py",
  "Parameters.py"];
const SOURCE = "Single Generator/";            // the generator's folder in the repository
// [file in the repository, file in the browser's in-memory file system]
const FETCH = [
  ...GENERATOR_FILES.map((f) => [`${SOURCE}Generator/${f}`, `Generator/${f}`]),
  ...PARAMETER_FILES.map((f) => [`${SOURCE}Parameters/${f}`, `Parameters_Default/${f}`]),
  ["WebGUI/WebGenerator.py", "WebGUI/WebGenerator.py"],
];

let step = "";                                   // what init is doing now, named in the message if it fails
function progress(text) { step = text; postMessage({ type: "progress", text }); }

// A dropped connection is tried again (twice) before it is reported, and the report names the file.
async function fetchText(url) {
  for (let tries = 1; ; tries++) {
    let r;
    try { r = await fetch(url, { cache: "no-cache" }); }
    catch (e) {
      if (tries < 3) { await new Promise((done) => setTimeout(done, 400 * tries)); continue; }
      throw new Error(`${url} could not be downloaded (${e.message})`);
    }
    if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
    return r.text();
  }
}

async function init({ pyodideBase, codeBase }) {
  const t0 = performance.now();
  try {
    progress("Loading Python (Pyodide)…");
    const { loadPyodide } = await import(pyodideBase + "pyodide.mjs");   // Pyodide 314 runs in module workers only
    pyodide = await loadPyodide({ indexURL: pyodideBase });
    progress("Loading numpy…");
    await pyodide.loadPackage("numpy");
    progress("Fetching the generator from the repository…");
    const jobs = [];
    for (const [from, to] of FETCH) {
      const dir = to.slice(0, to.lastIndexOf("/"));
      pyodide.FS.mkdirTree(`${ROOT}/${dir}`);
      const url = new URL(from, codeBase).href;
      jobs.push(fetchText(url).then((t) => pyodide.FS.writeFile(`${ROOT}/${to}`, t)));
    }
    await Promise.all(jobs);
    pyodide.runPython(`
import sys
sys.path.insert(0, "${ROOT}/WebGUI")
import WebGenerator as WG
WG.ROOT = "${ROOT}"
`);
    progress("Reading the parameters…");
    const description = JSON.parse(pyodide.runPython("WG.describe()"));
    return { description, seconds: (performance.now() - t0) / 1000 };
  } catch (e) {
    const early = /^Loading/.test(step) ? ` from ${pyodideBase}` : "";
    throw new Error(`${e && e.message || e} [${step.replace("…", "")}${early}]`);
  }
}

// Reads a file of the in-memory file system as a copy of exactly its bytes, so it can be transferred to the page.
function readFileBuffer(path) {
  const bytes = pyodide.FS.readFile(path);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function call(fn, ...args) {
  const f = pyodide.globals.get("WG")[fn];
  const out = f(...args);
  return JSON.parse(out);
}

onmessage = async (ev) => {
  const { id, cmd, args } = ev.data;
  try {
    let result;
    if (cmd === "init") result = await init(args);
    else if (cmd === "inactive") result = call("inactive", JSON.stringify(args.values));
    else if (cmd === "generate") {
      const t0 = performance.now();
      result = call("generate", JSON.stringify(args.values));
      result.seconds = (performance.now() - t0) / 1000;
      if (result.ok) {
        result.zipBytes = readFileBuffer(result.zip);
      }
    } else if (cmd === "exportZip") {
      const r = call("export_zip", JSON.stringify(args.values));
      result = { zipBytes: readFileBuffer(r.zip) };
    } else if (cmd === "readValues") result = call("read_values", args.text);
    else throw new Error("unknown command " + cmd);
    const transfer = result && result.zipBytes ? [result.zipBytes] : [];
    postMessage({ id, ok: true, result }, transfer);
  } catch (e) {
    postMessage({ id, ok: false, error: String(e && e.message || e) });
  }
};
