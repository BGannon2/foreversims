import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { webcrypto, timingSafeEqual } from 'node:crypto';
import test from 'node:test';

Object.defineProperty(globalThis, 'crypto', { value: webcrypto });
crypto.subtle.timingSafeEqual = (a, b) => timingSafeEqual(Buffer.from(a), Buffer.from(b));
const source = await readFile(new URL('../worker.js', import.meta.url), 'utf8');
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const origin = 'https://foreversims.com';
const authorization = `Basic ${btoa('test:fixture-only')}`;

function fixture(rows = []) {
  const writes = [];
  const DB = { prepare(sql) {
    return { bind(...values) { this.values = values; return this; }, async first() { return 0; }, async run() { writes.push({sql, values: this.values}); return {meta:{last_row_id:1}}; }, async all() { return {results: rows}; } };
  } };
  return { env: {DB, SITE_USER:'test', SITE_PASSWORD:'fixture-only'}, writes };
}

test('feedback retains contact privately and excludes it from both outbound destinations', async () => {
  const {env, writes} = fixture();
  Object.assign(env, {GITHUB_TOKEN:'fixture', GITHUB_REPO:'test/test', FEEDBACK_WEBHOOK:'https://example.invalid/webhook'});
  const sent = [], oldFetch = globalThis.fetch;
  globalThis.fetch = async (_url, options) => { sent.push(JSON.parse(options.body)); return Response.json({html_url:'https://github.com/test/test/issues/1'}); };
  try {
    const response = await worker.fetch(new Request(`${origin}/api/feedback`, {method:'POST', body:JSON.stringify({message:'My spell damage is wrong', category:'data', contact:'private@example.invalid', page:`${origin}/all-specs?spec=mage-fire&token=private-token#private-fragment`})}), env);
    assert.equal(response.status, 200);
    assert.ok(writes.some(w => w.values?.includes('private@example.invalid')));
    assert.equal(sent.length, 2);
    for (const payload of sent) {
      assert.doesNotMatch(JSON.stringify(payload), /private@example|private-token|private-fragment/);
    }
  } finally { globalThis.fetch = oldFetch; }
});

test('stored legacy script links are neutralized on admin render', async () => {
  const rows = ['javascript:alert(1)', 'data:text/html,test', 'https://evil.invalid/', `${origin}/all-specs?spec=mage-fire`].map((page, id) => ({id:id+1, created_at:'2026-09-22T00:00:00Z', category:'bug', message:'<script>test</script>', contact:'', page, spec:'Mage', version:'test', status:'new', issue_url:'javascript:alert(1)'}));
  const {env} = fixture(rows);
  const response = await worker.fetch(new Request(`${origin}/feedback-admin`, {headers:{Authorization:authorization}}), env);
  const html = await response.text();
  assert.equal(response.status, 200);
  assert.doesNotMatch(html, /href="(?:javascript:|data:|https:\/\/evil)/);
  assert.ok(html.includes(`href="${origin}/all-specs?spec=mage-fire"`));
  assert.ok(html.includes('&lt;script&gt;'));
  assert.match(response.headers.get('Content-Security-Policy'), /default-src 'none'/);
});

test('feedback rejects JSON primitives and cross-origin admin writes', async () => {
  const {env, writes} = fixture();
  for (const value of [null, [], 42, 'test']) {
    const response = await worker.fetch(new Request(`${origin}/api/feedback`, {method:'POST', body:JSON.stringify(value)}), env);
    assert.equal(response.status,400);
  }
  const response = await worker.fetch(new Request(`${origin}/feedback-admin`, {method:'POST', headers:{Authorization:authorization,Origin:'https://evil.invalid'},body:new URLSearchParams({id:'1',status:'done'})}),env);
  assert.equal(response.status,403);
  assert.equal(writes.length,0);
});
