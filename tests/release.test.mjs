import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { release } = require('../tools/release.js');
const { publishRelease } = require('../tools/notify_release.js');
test('deployment failure never publishes an announcement', async () => {
  let announced = false;
  await assert.rejects(release({}, () => { throw Error('failed'); }, async () => { announced = true; }));
  assert.equal(announced, false);
});
test('announcement follows successful deployment and retains full notes', async () => {
  const calls = []; const input = { notes: 'First change\nSecond change' };
  await release(input, (_, args) => calls.push(args.join(' ')), async value => { assert.equal(value.notes, input.notes); calls.push('announce'); });
  assert.deepEqual(calls, ['tools/stamp_version.js', 'wrangler deploy', 'announce']);
});
test('Discord receipt confirms publication and mentions are disabled', async () => {
  const receipt = await publishRelease({ url: new URL('https://discord.com/api/webhooks/test/test?wait=true'), notes: 'Notes', version: 'test' }, async (_, options) => {
    const body = JSON.parse(options.body);
    assert.deepEqual(body.allowed_mentions, { parse: [] });
    assert.equal(body.embeds[0].description, 'Notes');
    return { ok: true, json: async () => ({ id: 'test-message', channel_id: 'test-channel' }) };
  });
  assert.equal(receipt.id, 'test-message');
});
test('failed announcement is reported as post-deploy failure without redeploy', async () => {
  let count = 0;
  await assert.rejects(release({}, () => count++, async () => { throw Error('rejected'); }), /Deployment succeeded/);
  assert.equal(count, 2);
});
