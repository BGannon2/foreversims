//! Forever Sims engine: Rust port of the Python reference (`engine.py`, `sim.py`)
//! compiled to WebAssembly so every simulation runs in the visitor's browser.

pub mod config;
pub mod data;
pub mod items;
pub mod iteration;
pub mod paladin;
pub mod rng;
pub mod spec_sim;

use items::Catalog;
use serde_json::{json, Value};
use std::cell::RefCell;
use wasm_bindgen::prelude::*;

thread_local! {
    static CATALOG: RefCell<Option<Catalog>> = const { RefCell::new(None) };
}

fn with_catalog<T>(f: impl FnOnce(&Catalog) -> Result<T, String>) -> Result<T, String> {
    CATALOG.with(|c| match c.borrow().as_ref() { Some(cat) => f(cat), None => Err("Catalog not loaded; call set_catalog first.".into()) })
}

fn parse(json_text: &str) -> Result<Value, String> {
    serde_json::from_str(json_text).map_err(|e| format!("Invalid JSON: {e}"))
}

fn out(result: Result<Value, String>) -> String {
    match result {
        Ok(v) => v.to_string(),
        Err(e) => json!({"error": e}).to_string(),
    }
}

/// Load the item catalog (same JSON documents the site serves).  Call once per worker.
#[wasm_bindgen]
pub fn set_catalog(items_json: &str, extra_json: &str, enchants_json: &str, sets_json: &str) -> Result<(), JsValue> {
    let cat = items::load_catalog(items_json, extra_json, enchants_json, sets_json).map_err(|e| JsValue::from_str(&e))?;
    CATALOG.with(|c| *c.borrow_mut() = Some(cat));
    Ok(())
}

#[wasm_bindgen]
pub fn engine_version() -> String {
    format!("forever_engine {} (rust)", env!("CARGO_PKG_VERSION"))
}

/// Full shared-engine simulation; returns the same JSON as `POST /api/simulate-spec`.
#[wasm_bindgen]
pub fn simulate_spec(request_json: &str) -> String {
    out(parse(request_json).and_then(|req| with_catalog(|cat| spec_sim::simulate(req, cat))))
}

/// Iterations `[start, end)` of a shared-engine run as a JSON array of per-iteration results.
#[wasm_bindgen]
pub fn run_spec_iterations(request_json: &str, start: u32, end: u32) -> String {
    out(parse(request_json).and_then(|req| with_catalog(|cat| {
        let cfg = config::Config::new(req, cat)?;
        let end = (end as i64).min(cfg.iterations);
        let rows = spec_sim::run_range(&cfg, start as i64, end);
        serde_json::to_value(rows).map_err(|e| e.to_string())
    })))
}

/// Merge per-iteration results (from `run_spec_iterations`, in order) into the final result.
#[wasm_bindgen]
pub fn finalize_spec(request_json: &str, partials_json: &str) -> String {
    out(parse(request_json).and_then(|req| with_catalog(|cat| {
        let cfg = config::Config::new(req, cat)?;
        let parts: Vec<Vec<iteration::IterResult>> = serde_json::from_str(partials_json).map_err(|e| format!("partials: {e}"))?;
        let rows: Vec<iteration::IterResult> = parts.into_iter().flatten().collect();
        if rows.is_empty() {
            return Err("No iterations were simulated.".into());
        }
        Ok(spec_sim::finalize(&cfg, &rows))
    })))
}

/// Full Paladin simulation; returns the same JSON as `POST /api/simulate`.
#[wasm_bindgen]
pub fn simulate_paladin(profile_json: &str) -> String {
    out(parse(profile_json).and_then(|p| with_catalog(|cat| paladin::simulate(&p, cat))))
}

#[wasm_bindgen]
pub fn run_paladin_iterations(profile_json: &str, start: u32, end: u32) -> String {
    out(parse(profile_json).and_then(|p| with_catalog(|cat| {
        let prep = paladin::prepare(&p, cat)?;
        let iterations = prep.effective["iterations"].as_i64().unwrap_or(1);
        let rows = paladin::run_range(&prep, start as i64, (end as i64).min(iterations))?;
        serde_json::to_value(rows).map_err(|e| e.to_string())
    })))
}

#[wasm_bindgen]
pub fn finalize_paladin(profile_json: &str, partials_json: &str) -> String {
    out(parse(profile_json).and_then(|p| with_catalog(|cat| {
        let prep = paladin::prepare(&p, cat)?;
        let parts: Vec<Vec<paladin::FightResult>> = serde_json::from_str(partials_json).map_err(|e| format!("partials: {e}"))?;
        let rows: Vec<paladin::FightResult> = parts.into_iter().flatten().collect();
        if rows.is_empty() {
            return Err("No iterations were simulated.".into());
        }
        Ok(paladin::finalize(&prep, &rows))
    })))
}

/// Validate a Paladin profile without simulating (mirrors `sim.validate`).
#[wasm_bindgen]
pub fn validate_paladin(profile_json: &str) -> String {
    out(parse(profile_json).and_then(|p| paladin::validate(&p)))
}

/// Native helper used by the CLI and tests.
pub fn set_catalog_native(cat: Catalog) {
    CATALOG.with(|c| *c.borrow_mut() = Some(cat));
}
