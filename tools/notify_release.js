// Posts a release announcement to the Forever Sims Discord #releases channel via webhook.
// Run as the last step of a deploy, after `wrangler deploy` succeeds:
//   node tools/notify_release.js "What changed in this release, in a sentence or two."
// Or, if no argument is given, falls back to the RELEASE_NOTES env var — this is how
// .github/workflows/release-notify.yml calls it automatically on every PR merge to main.
//
// Reads the webhook URL from the RELEASE_WEBHOOK_URL environment variable — never hardcode it.
// Get the URL from Discord: #releases channel settings -> Integrations -> Webhooks
// ("Forever Sims Release Notes") -> Copy Webhook URL.
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

function main() {
  const notes = (process.argv.slice(2).join(" ") || process.env.RELEASE_NOTES || "").trim();
  if (!notes) {
    console.error("Usage: node tools/notify_release.js \"Release notes for this deploy.\"");
    console.error("(or set the RELEASE_NOTES env var)");
    process.exit(1);
  }
  const webhookUrl = process.env.RELEASE_WEBHOOK_URL;
  if (!webhookUrl) {
    console.error("RELEASE_WEBHOOK_URL is not set — skipping Discord notification.");
    console.error("Set it locally: export RELEASE_WEBHOOK_URL=... (see .dev.vars.example)");
    process.exit(1);
  }

  const version = fs.readFileSync(path.join(ROOT, "VERSION"), "utf8").trim();
  let commit = "local";
  try {
    commit = execSync("git rev-parse --short HEAD", { cwd: ROOT }).toString().trim();
  } catch { /* not a git checkout */ }

  const fields = [{ name: "Build", value: commit, inline: true }];
  if (process.env.PR_URL) fields.push({ name: "Pull Request", value: process.env.PR_URL, inline: true });

  const embed = {
    title: `Forever Sims v${version}`,
    url: "https://foreversims.com",
    description: notes,
    color: 0x3fc6e8, // matches the site's teal accent
    fields,
    timestamp: new Date().toISOString(),
  };

  const body = JSON.stringify({ username: "Forever Sims", embeds: [embed] });
  fetch(webhookUrl, { method: "POST", headers: { "Content-Type": "application/json" }, body })
    .then((res) => {
      if (!res.ok) {
        return res.text().then((text) => {
          throw new Error(`Discord webhook returned ${res.status}: ${text}`);
        });
      }
      console.log(`Posted release notes for v${version} (${commit}) to #releases.`);
    })
    .catch((err) => {
      console.error("Failed to post release notes:", err.message);
      process.exit(1);
    });
}

main();
