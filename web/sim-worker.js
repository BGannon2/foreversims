// Simulation worker: loads the Rust/WebAssembly engine once, then runs iteration
// ranges on request.  Several workers run in parallel (see sim-client.js).
import init, { set_catalog, run_spec_iterations, finalize_spec, run_paladin_iterations, finalize_paladin, engine_version } from "./engine/forever_engine.js?v=9198396";

const ENGINE_WASM = "/engine/forever_engine_bg.wasm?v=9198396";
const CATALOG_FILES = ["/data/items.json?v=9198396", "/data/engine-items-extra.json?v=9198396", "/data/enchants.json?v=9198396", "/data/forever-sets.json?v=9198396"];
let ready = null;

async function load() {
  await init(ENGINE_WASM);
  const texts = await Promise.all(CATALOG_FILES.map(async url => {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`Could not load ${url} (${r.status}).`);
    return r.text();
  }));
  set_catalog(...texts);
}

function checkError(text) {
  if (text.startsWith('{"error"')) throw new Error(JSON.parse(text).error);
  return text;
}

self.onmessage = async event => {
  const msg = event.data;
  try {
    if (!ready) ready = load();
    await ready;
    if (msg.type === "ping") {
      self.postMessage({ type: "pong", id: msg.id, version: engine_version() });
    } else if (msg.type === "run") {
      const runRange = msg.kind === "paladin" ? run_paladin_iterations : run_spec_iterations;
      const parts = [];
      for (let start = msg.start; start < msg.end; start += msg.chunk) {
        const end = Math.min(msg.end, start + msg.chunk);
        const text = checkError(runRange(msg.request, start, end));
        const inner = text.slice(1, -1);
        if (inner) parts.push(inner);
        self.postMessage({ type: "progress", id: msg.id, done: end - msg.start });
      }
      self.postMessage({ type: "done", id: msg.id, partial: `[${parts.join(",")}]` });
    } else if (msg.type === "finalize") {
      const finalize = msg.kind === "paladin" ? finalize_paladin : finalize_spec;
      const text = checkError(finalize(msg.request, `[${msg.partials.join(",")}]`));
      self.postMessage({ type: "result", id: msg.id, result: text });
    }
  } catch (err) {
    self.postMessage({ type: "error", id: msg.id, error: err && err.message ? err.message : String(err) });
  }
};
