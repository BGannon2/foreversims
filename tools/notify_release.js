const fs = require('node:fs');
const path = require('node:path');
const { parseEnv } = require('node:util');
const ROOT = path.resolve(__dirname, '..');

function releaseInput(argv = process.argv.slice(2), env = process.env) {
  const fileIndex = argv.indexOf('--notes-file');
  const notes = (fileIndex >= 0 ? fs.readFileSync(path.resolve(ROOT, argv[fileIndex + 1]), 'utf8') : argv.join(' ') || env.RELEASE_NOTES || '').trim();
  if (!notes) throw new Error('Provide --notes-file <path> or RELEASE_NOTES before releasing.');
  if (notes.length > 4096) throw new Error('Release notes exceed Discord’s 4096-character embed limit.');
  let webhook = env.RELEASE_WEBHOOK_URL;
  if (!webhook && fs.existsSync(path.join(ROOT, '.dev.vars'))) webhook = parseEnv(fs.readFileSync(path.join(ROOT, '.dev.vars'), 'utf8')).RELEASE_WEBHOOK_URL;
  if (!webhook) throw new Error('RELEASE_WEBHOOK_URL is missing. Set it in the environment or local .dev.vars.');
  const url = new URL(webhook);
  if (url.protocol !== 'https:' || !['discord.com', 'discordapp.com'].includes(url.hostname) || !url.pathname.startsWith('/api/webhooks/')) throw new Error('Release webhook must be an HTTPS Discord webhook.');
  url.searchParams.set('wait', 'true');
  return { notes, url, version: fs.readFileSync(path.join(ROOT, 'VERSION'), 'utf8').trim() };
}

async function publishRelease(input, fetchImpl = fetch) {
  const body = { username: 'Forever Sims', allowed_mentions: { parse: [] }, embeds: [{ title: `Forever Sims v${input.version}`, url: 'https://foreversims.com', description: input.notes, color: 0x3fc6e8, timestamp: new Date().toISOString() }] };
  let response;
  try { response = await fetchImpl(input.url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: AbortSignal.timeout(30000) }); }
  catch { throw new Error('Discord request did not return a confirmation. Check the channel before retrying to avoid duplicates.'); }
  if (!response.ok) throw new Error(`Discord rejected the release announcement (HTTP ${response.status}).`);
  const message = await response.json();
  if (!message.id || !message.channel_id) throw new Error('Discord returned no message receipt; check the channel before retrying.');
  console.log(`Posted v${input.version} release notes. Discord message: ${message.id}`);
  return message;
}

if (require.main === module) {
  Promise.resolve().then(() => publishRelease(releaseInput())).catch(error => { console.error(error.message); process.exitCode = 1; });
}
module.exports = { ROOT, releaseInput, publishRelease };
