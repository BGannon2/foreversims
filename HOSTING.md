# Hosting Forever Sims at foreversims.com

The site is fully static. Every simulation runs in the visitor's browser through
the Rust engine compiled to WebAssembly (`web/engine/`), split across a pool of
Web Workers. Nothing is computed on a server, so hosting costs are the domain
and nothing else.

## What gets deployed

Publish the `web/` directory as-is. It contains:

| Path | Purpose |
| --- | --- |
| `*.html`, `*.js`, `*.css`, `fonts/`, `*-icons/` | the UI |
| `sim-client.js`, `sim-worker.js` | worker pool that drives the engine |
| `engine/forever_engine.js`, `engine/forever_engine_bg.wasm` | the engine (built from `engine-rs/`) |
| `data/*.json` | item catalog, talents, gear presets, benchmarks (exported from Python) |
| `_headers` | Cloudflare Pages headers (CSP with `wasm-unsafe-eval`, caching) |

Regenerate `web/data` and `web/engine` with `tools/build_engine.sh` whenever the
Python data tables or the Rust engine change. `test_parity.py` fails if the
exported data is stale or the Rust engine drifts from the Python reference.

## Cloudflare Pages (recommended, free)

1. Push this project to a Git repository (GitHub or GitLab).
2. Cloudflare dashboard, Workers & Pages, Create, Pages, Connect to Git.
3. Build settings: framework preset **None**, build command **empty**, build
   output directory **`web`**. No environment variables are needed.
4. After the first deploy, open the project's Custom domains tab and add
   `foreversims.com` and `www.foreversims.com`. Because the domain's DNS is on
   Cloudflare, the CNAME records are created automatically and the certificate
   is issued within minutes.
5. Optional: under Pages, Settings, Builds, set the production branch and
   enable preview deployments for other branches.

Cloudflare serves the `_headers` file, so the same Content-Security-Policy the
Python server sends applies on Pages.

If the domain is registered elsewhere, add the domain to Cloudflare first
(free plan) and point the registrar's nameservers at Cloudflare, then do step 4.

### Alternatives

Netlify (`_headers` works there too), GitHub Pages (needs a separate headers
mechanism; CSP is not enforced there), or any static host or CDN bucket. The
only requirements are that `.wasm` is served with `application/wasm` and that
module Web Workers are allowed (same-origin scripts).

## Keeping the current Docker deployment

`server.py` still serves the site and keeps the JSON API (`/api/*`) for the
Python reference engine, tests and benchmark generation. The UI no longer calls
`/api/simulate*`; it loads `/data/*.json` and runs the WebAssembly engine. The
Docker image on Synner-mini therefore only serves static files. Rebuild with
`docker compose up -d --build` after copying the tree.

## Regenerating benchmarks

Benchmarks are precomputed by the Python reference engine
(`python generate_benchmarks.py`, about ten minutes at 300 iterations), then
exported to `web/data/benchmarks.json` by `tools/export_static_data.py`. A CI
job or a local run before deploying is enough; no server-side compute is needed.
