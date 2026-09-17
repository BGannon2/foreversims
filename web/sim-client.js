// Browser-side simulation client: a pool of Web Workers running the Rust/WASM
// engine.  Iterations are split across workers with the same per-iteration
// seeds the Python reference uses, so results are identical to a serial run.
(function () {
  const VERSION = "1";
  class SimPool {
    constructor() {
      this.size = Math.max(1, Math.min(8, navigator.hardwareConcurrency || 4));
      this.workers = [];
      this.pending = new Map();
      this.nextId = 1;
      this.supported = typeof Worker === "function" && typeof WebAssembly === "object";
    }
    worker(i) {
      if (!this.workers[i]) {
        const w = new Worker(`/sim-worker.js?v=${VERSION}`, { type: "module" });
        w.onmessage = e => this.onMessage(e.data);
        w.onerror = e => {
          const err = new Error(e.message || "The simulation worker failed to start.");
          for (const p of this.pending.values()) p.reject(err);
          this.pending.clear();
          this.workers[i] = null;
        };
        this.workers[i] = w;
      }
      return this.workers[i];
    }
    onMessage(m) {
      const p = this.pending.get(m.id);
      if (!p) return;
      if (m.type === "progress") { if (p.onProgress) p.onProgress(m.done); return; }
      this.pending.delete(m.id);
      if (m.type === "error") p.reject(new Error(m.error)); else p.resolve(m);
    }
    call(i, msg, onProgress) {
      return new Promise((resolve, reject) => {
        const id = this.nextId++;
        this.pending.set(id, { resolve, reject, onProgress });
        this.worker(i).postMessage({ ...msg, id });
      });
    }
    /** Warm up every worker (engine + catalog load) so the first run is fast. */
    warm() {
      if (!this.supported) return;
      for (let i = 0; i < this.size; i++) this.call(i, { type: "ping" }).catch(() => {});
    }
    /**
     * kind: "spec" (shared engine request) or "paladin" (Paladin profile).
     * Resolves to the same JSON the Python API returned.
     */
    async simulate(kind, request, iterations, onProgress) {
      if (!this.supported) throw new Error("This browser cannot run the simulator (Web Workers or WebAssembly unavailable).");
      const text = JSON.stringify(request);
      const n = Math.max(1, Math.floor(+iterations || 1));
      const workers = Math.min(this.size, n);
      const per = Math.ceil(n / workers);
      const done = new Array(workers).fill(0);
      let reported = -1;
      const report = () => {
        const total = done.reduce((a, b) => a + b, 0);
        if (onProgress && total !== reported) { reported = total; onProgress(total, n); }
      };
      const jobs = [];
      for (let w = 0; w < workers; w++) {
        const start = w * per, end = Math.min(n, start + per);
        if (start >= end) break;
        const chunk = Math.max(1, Math.min(25, Math.ceil(per / 4)));
        jobs.push(this.call(w, { type: "run", kind, request: text, start, end, chunk }, d => { done[w] = d; report(); }));
      }
      const partials = (await Promise.all(jobs)).map(m => m.partial);
      const fin = await this.call(0, { type: "finalize", kind, request: text, partials });
      return JSON.parse(fin.result);
    }
  }
  window.ForeverSim = new SimPool();
})();
