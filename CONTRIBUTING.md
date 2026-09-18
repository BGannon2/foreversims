# Contributing to Forever Sims

Thanks for considering a contribution. This project models a large, still-changing ruleset from
sourced data, so the most valuable contributions are often corrections, not just code.

## Ways to contribute

- **Sourcing corrections** — if a talent, ability, or racial value doesn't match Wowhead's Forever
  pages or WoWSims Classic, open an issue with a link to the source. This is the highest-value
  contribution: every number in the data tables should be traceable.
- **Bug reports** — a rotation stalling, a wrong DPS/TPS number, a UI issue. Include the spec,
  race, and (if it's a simulation bug) enough of your gear/talent/buff config to reproduce it.
- **Bug fixes and features** — see the workflow below.

## Reporting issues

Open a [GitHub issue](../../issues) with:
- What you expected vs. what happened.
- Steps to reproduce (spec/race/gear/talents if simulation-related).
- A source link if you're disputing a modeled value.

## Development workflow

1. Fork the repo and create a branch off `main`.
2. Requires Python 3.10+ (no third-party packages). See `README.md` for local setup.
3. Make your change:
   - Simulation logic lives in `forever/engine.py`/`forever/engine_data.py` (21 shared specs) or
     `forever/sim.py`/`forever/gear_data.py` (Paladin). Data tables are cited inline or marked
     `"provisional"` — keep that convention.
   - If the change affects simulation output, port it to the matching Rust file in
     `engine-rs/src/` — the Python and Rust engines must stay numerically identical.
4. Run the test suite: `python -m unittest discover`.
5. If you touched simulation output: `bash tools/build_engine.sh`, which re-exports data,
   rebuilds the Rust engine, and runs `tools/parity_check.py` (must show 0.000% diff across all
   23 specs). This is required before a PR touching `forever/`, `data/`, or `engine-rs/` will be
   mergeable.
6. If default rotations, talents, or gear changed, regenerate benchmarks:
   `python tools/generate_benchmarks.py`.
7. Commit with a clear message and open a pull request describing what changed and why, with
   source links for any data changes.

## Pull request expectations

- Keep PRs focused — one fix or feature per PR.
- Tests must pass (`python -m unittest discover`) and, for simulation changes, parity must hold
  (`tools/parity_check.py`).
- Cite sources for any new or changed data values, or mark them `"provisional"` with a note on
  what's assumed.
- If you're forking this project to deploy your own instance, update `wrangler.jsonc`'s `routes`
  and D1 `database_id` to your own — don't submit PRs that point deploy config back at
  foreversims.com.

## Code style

No enforced linter yet — match the existing style in the file you're editing (this codebase
favors dense, single-purpose functions over heavy abstraction). CI runs the test suite on every
PR; see `.github/workflows/ci.yml`.

## Questions

Open an issue, or use the in-app feedback form at foreversims.com.
