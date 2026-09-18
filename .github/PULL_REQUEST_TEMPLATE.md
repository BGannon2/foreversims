## What changed and why

## Checklist

- [ ] `python -m unittest discover` passes
- [ ] `ruff check .` / `npx eslint .` / `cargo clippy --release --all-targets -- -D warnings` pass
      (whichever apply to the files you touched)
- [ ] If this changes simulation output: ported to `engine-rs/src/`, ran `tools/build_engine.sh`,
      and `tools/parity_check.py` shows 0.000% diff
- [ ] If this changes default rotations/talents/gear: regenerated benchmarks
      (`python tools/generate_benchmarks.py`)
- [ ] New or changed data values are cited (source link) or marked `"provisional"`
