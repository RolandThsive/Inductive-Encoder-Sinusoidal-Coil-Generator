/* PyodideWorker.js - runs the Python generator in a background thread, so the page never freezes.

   The page sends {id, cmd, args}; the worker answers {id, ok, result} or {id, ok: false, error},
   and sends {type: "progress", text} while it loads.  The commands:
     init      {pyodideBase, codeBase}  ->  {description, seconds}
     inactive  {values}                 ->  [names of the parameters the generator ignores]
     generate  {values, strict}         ->  {ok, items, name, files, summaries, rx, edges, center, seconds, zipBytes}
                                            (on a failed run: ok false, items and failed; no zipBytes)
     exportZip {values}                 ->  {zipBytes}
     readValues {text}                  ->  {name: value}

   On start ("init") it loads Pyodide and numpy, then fetches the generator's own .py files from the
   repository (codeBase: the repository root as served by GitHub Pages) into its in-memory file system. */

let pyodide = null;
const ROOT = "/coilgen";
const FILES = {
  "Generator": ["ParameterChecker.py", "StatorGenerator.py", "RotorGenerator.py", "TXLayout.py",
                "OutputDirectoryManager.py"],
  "Parameters_Default": ["Board_Parameters.py", "RX_Parameters.py", "TX_Parameters.py",
                         "Rotor_Parameters.py", "Parameters.py"],
  "WebGUI": ["WebGenerator.py"],
};
const SOURCE_FOLDER = { "Generator": "Generator", "Parameters_Default": "Parameters", "WebGUI": "WebGUI" };

function progress(text) { postMessage({ type: "progress", text }); }

async function fetchText(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.text();
}

async function init({ pyodideBase, codeBase }) {
  const t0 = performance.now();
  progress("Loading Python (Pyodide)…");
  const { loadPyodide } = await import(pyodideBase + "pyodide.mjs");   // Pyodide 314 runs in module workers only
  pyodide = await loadPyodide({ indexURL: pyodideBase });
  progress("Loading numpy…");
  await pyodide.loadPackage("numpy");
  progress("Fetching the generator from the repository…");
  const jobs = [];
  for (const [dir, names] of Object.entries(FILES)) {
    pyodide.FS.mkdirTree(`${ROOT}/${dir}`);
    for (const n of names) {
      const url = new URL(`${SOURCE_FOLDER[dir]}/${n}`, codeBase).href;
      jobs.push(fetchText(url).then((t) => pyodide.FS.writeFile(`${ROOT}/${dir}/${n}`, t)));
    }
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
      result = call("generate", JSON.stringify(args.values), !!args.strict);
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
