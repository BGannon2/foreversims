# Hosting Forever Sims

The site is fully static. Every simulation runs in the visitor's browser through the Rust engine
compiled to WebAssembly (`web/engine/`), split across a pool of Web Workers. Nothing is computed
server-side except the small feedback endpoint below, so hosting costs are the domain and
nothing else.

Production (foreversims.com) runs on **Cloudflare Workers with Static Assets**, fronted by a
small Worker (`worker.js`) for HTTP Basic auth on preview URLs and the feedback form. Deploys go
out with [Wrangler](https://developers.cloudflare.com/workers/wrangler/).

## What gets deployed

`wrangler.jsonc` publishes the `web/` directory as static assets and routes every request through
`worker.js` first (`assets.run_worker_first: true`), which handles `/api/feedback` and
`/feedback-admin` itself and otherwise falls through to the static files.

| Path | Purpose |
| --- | --- |
| `*.html`, `*.js`, `*.css`, `fonts/`, `*-icons/` | the UI |
| `sim-client.js`, `sim-worker.js` | worker pool that drives the engine |
| `engine/forever_engine.js`, `engine/forever_engine_bg.wasm` | the engine (built from `engine-rs/`) |
| `data/*.json` | item catalog, talents, gear presets, benchmarks (exported from Python) |

Regenerate `web/data` and `web/engine` with `tools/build_engine.sh` whenever the Python data
tables or the Rust engine change, then re-export with `python tools/export_static_data.py`.
`tests/test_parity.py` fails if the exported data is stale or the Rust engine drifts from the
Python reference — run it before every deploy.

`web/sim-worker.js`'s engine/catalog URLs carry a `?v=<commit-hash>` cache-busting suffix that
`tools/stamp_version.js` (Node) or `tools/stamp_version.py` (Python) rewrites on every build.
This matters: without it, a returning visitor's browser can keep serving a stale cached engine
indefinitely even after a successful deploy. Always run one of those before `wrangler deploy`.

## Deploying

1. Install [Wrangler](https://developers.cloudflare.com/workers/wrangler/) and authenticate
   (`npx wrangler login`).
2. Create a D1 database for the feedback form (optional — the site works without it, feedback
   submission just returns an error) and put its `database_id` in `wrangler.jsonc`. Run the
   migrations in `migrations/` against it.
3. Set secrets the Worker reads from `env` (all optional; each feature no-ops without its
   secret): `SITE_USER` / `SITE_PASSWORD` (HTTP Basic auth on the `*.workers.dev` preview host
   and `/feedback-admin`), `FEEDBACK_WEBHOOK` (a Discord webhook URL for new feedback), and
   `GITHUB_TOKEN` / `GITHUB_REPO` (auto-file a GitHub issue per feedback submission).
   `npx wrangler secret put <NAME>` for each.
4. Point `wrangler.jsonc`'s `routes` at your own domain(s), or drop that key to deploy only to
   the `*.workers.dev` subdomain.
5. Build and validate the engine, regenerate benchmarks when needed, and commit the release.
6. Write the Discord announcement to a versioned Markdown file, then run:
   `npm run release -- --notes-file docs/release-notes-v0.22.0.md`
   (use the new version's notes path for later releases). This validates notes and the webhook,
   stamps assets, runs `wrangler deploy`, and posts the full notes only if deployment succeeds.
   Set `RELEASE_WEBHOOK_URL` in the shell environment or local ignored `.dev.vars`.
7. If deployment succeeded but notification failed, inspect Discord before retrying. Recover
   with `npm run announce-release -- --notes-file <notes-path>`; do not redeploy just to retry.

Direct `wrangler deploy` remains a low-level command and does not announce anything. Use
`npm run release` for normal releases. PR merges no longer announce undeployed changes.
The GitHub **Announce an existing release** workflow is manual recovery only; supply the
notes file for an already deployed release. It uses the repository webhook secret.

## Discord release announcements

`#releases` in the community Discord is an Announcement channel where `@everyone` has `Send
Messages` (and thread creation) denied — only a webhook can post there. `tools/notify_release.js`
posts an embed (version, build commit, your notes) to it via the webhook URL in
`RELEASE_WEBHOOK_URL`, read from your shell environment — it's a local var for a script you run
by hand, not a Cloudflare Worker secret. Get the URL from the channel's Integrations settings
("Forever Sims Release Notes" webhook) and keep it out of version control, same as any other
secret in this project.

## Deploying elsewhere

Nothing about the simulator itself requires Cloudflare — it's static files plus WebAssembly. Any
static host works (Netlify, GitHub Pages, a plain CDN bucket) as long as `.wasm` is served with
`application/wasm` and module Web Workers are allowed (same-origin scripts). You'll lose the
feedback form (`worker.js`'s job) unless you reimplement it for that platform; everything else —
`web/` as a static folder — is portable as-is.

## Local development

`python server.py` serves the site locally (`http://127.0.0.1:8765` by default) and also exposes
the same JSON API the Python reference engine uses for tests and benchmark generation
(`/api/*`). The deployed site's UI never calls `/api/simulate*`; it loads `/data/*.json` and runs
the WebAssembly engine entirely client-side, so `server.py` is a dev/test tool, not part of the
production path. `Dockerfile`/`compose.yaml` containerize this same server (`docker compose up
-d --build`) if you'd rather self-host the Python reference server than run it bare.

## Regenerating benchmarks

Benchmarks are precomputed by the Python reference engine (`python tools/generate_benchmarks.py`,
parallelized across CPU cores via `ProcessPoolExecutor` — a few minutes for the full race matrix
at every target count, 300 iterations each), then exported to `web/data/benchmarks.json` by
`tools/export_static_data.py`. A CI job or a local run before deploying is enough; no
server-side compute is needed in production.
