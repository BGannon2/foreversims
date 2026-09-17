#!/usr/bin/env bash
# Rebuild everything the static site needs from the Python sources:
#   1. export data tables + API snapshots (web/data, engine-rs/data)
#   2. compile the Rust engine to WebAssembly and generate the JS bindings (web/engine)
#   3. build the native CLI used by tools/parity_check.py
# Requires: python 3, rustup with the wasm32-unknown-unknown target, wasm-bindgen-cli 0.2.128.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.cargo/bin:$PATH"
python tools/export_static_data.py
( cd engine-rs && cargo build --release --target wasm32-unknown-unknown && cargo build --release )
wasm-bindgen --target web --out-dir web/engine --out-name forever_engine --no-typescript engine-rs/target/wasm32-unknown-unknown/release/forever_engine.wasm
ls -la web/engine
python tools/parity_check.py --iterations 5 --duration 60
