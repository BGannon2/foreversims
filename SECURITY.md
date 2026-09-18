# Security Policy

Forever Sims is a static fan site — every simulation runs client-side in the visitor's browser via
WebAssembly, and there is no server-side compute or user accounts in production. The attack
surface is small: the Cloudflare Worker (`worker.js`) that handles the feedback form and preview
auth, and the site's static assets.

## Reporting a vulnerability

If you find a security issue (e.g. a way to bypass the feedback form's validation, an XSS vector
in the UI, or a way to abuse `worker.js`'s endpoints), please report it privately rather than
opening a public issue:

- Use [GitHub's private vulnerability reporting](../../security/advisories/new) for this
  repository, or
- Open an issue titled generically (no exploit details) asking for a private contact method.

Please include enough detail to reproduce the issue. There's no bug bounty — this is an unpaid fan
project — but reports are genuinely appreciated and will be credited in `CHANGELOG.md` unless you
prefer otherwise.

## Scope

In scope: this repository's code (`worker.js`, `server.py`, the Rust engine, the static site).
Out of scope: Cloudflare's own platform, third-party services linked from the site (Wowhead,
WoWSims Classic), and the underlying game or Blizzard's services.
