// Canonical release command: validate notes/credentials before deploying, announce only on success.
const { spawnSync } = require('node:child_process');
const { ROOT, releaseInput, publishRelease } = require('./notify_release.js');
function command(program, args, shell = false) {
  const result = spawnSync(program, args, { cwd: ROOT, stdio: 'inherit', shell });
  if (result.error || result.status !== 0) throw new Error('Release command failed; no Discord announcement was sent.');
}
async function release(input, run = command, announce = publishRelease) {
  run(process.execPath, ['tools/stamp_version.js']);
  run(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['wrangler', 'deploy'], process.platform === 'win32');
  try { return await announce(input); }
  catch (error) { throw new Error(`Deployment succeeded, but announcement needs attention: ${error.message} Use npm run announce-release -- --notes-file <path> after checking Discord; do not redeploy merely to retry the announcement.`); }
}
if (require.main === module) Promise.resolve().then(() => release(releaseInput())).catch(error => { console.error(error.message); process.exitCode = 1; });
module.exports = { release };
