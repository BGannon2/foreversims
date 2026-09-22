import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const read = path => readFile(new URL(path, root));
const source = await read('web/engine/forever_engine.js');
const engine = await import('data:text/javascript;base64,' + source.toString('base64'));
await engine.default({module_or_path: await read('web/engine/forever_engine_bg.wasm')});
engine.set_catalog(...await Promise.all(['items', 'engine-items-extra', 'enchants', 'forever-sets'].map(async name => (await read(`web/data/${name}.json`)).toString())));
const cases = JSON.parse(await readFile(process.argv[2], 'utf8'));
let checked = 0;
function compare(expected, actual, path) {
  if (typeof expected === 'number') {
    const tolerance = path.includes('.log.') ? (path.endsWith('.resource') ? .100000001 : path.endsWith('.time') ? .010000001 : .001000001) : 1e-6;
    assert.ok(typeof actual === 'number' && Number.isFinite(actual) && Math.abs(expected-actual) <= tolerance, `${path}: expected ${expected}, got ${actual}`);
    checked++;
  } else if (typeof expected === 'string' && path.includes('.log.')) {
    assert.equal(actual, expected, path);
  } else if (expected && typeof expected === 'object') {
    if (Array.isArray(expected)) assert.equal(actual?.length, expected.length, path);
    for (const [key, value] of Object.entries(expected)) compare(value, actual?.[key], `${path}.${key}`);
  }
}
for (const c of cases) {
  const request = JSON.stringify(c.request), paladin = c.kind === 'paladin';
  const result = JSON.parse((paladin ? engine.simulate_paladin : engine.simulate_spec)(request));
  assert.equal(result.error, undefined, `${c.name}: ${result.error}`);
  const run = paladin ? engine.run_paladin_iterations : engine.run_spec_iterations;
  const finalize = paladin ? engine.finalize_paladin : engine.finalize_spec;
  const merged = JSON.parse(finalize(request, `[${run(request, 0, 1)},${run(request, 1, 3)}]`));
  assert.equal(merged.error, undefined, `${c.name}: ${merged.error}`);
  // Every numeric metric, per-ability amount, resource and event timestamp is checked.
  // Rounded log fields allow one display unit for Python/Rust rounding ties.
  // Event strings/counts must agree; unrounded totals retain the strict tolerance.
  for (const key of Object.keys(c.python).filter(k => !['configuration', 'profile', 'gear_summary', 'effective_character', 'spec'].includes(k))) {
    compare(c.python[key], result[key], `${c.name}.${key}`);
    compare(result[key], merged[key], `${c.name}.merge.${key}`);
  }
}
console.log(`${cases.length} browser profiles and split-worker merges passed; ${checked} numeric checks.`);
