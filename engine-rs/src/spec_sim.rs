//! Driver for the shared-engine specs (port of `engine.simulate`), split so a
//! worker pool can run iteration ranges in parallel and merge them.

use crate::config::Config;
use crate::items::Catalog;
use crate::iteration::{IterResult, Iteration, Row};
use indexmap::IndexMap;
use serde_json::{json, Map, Value};

pub fn fmean(values: &[f64]) -> f64 {
    values.iter().sum::<f64>() / values.len() as f64
}

pub fn stdev(values: &[f64]) -> f64 {
    let n = values.len() as f64;
    let mean = fmean(values);
    (values.iter().map(|v| (v - mean) * (v - mean)).sum::<f64>() / (n - 1.0)).sqrt()
}

fn metric(values: &[f64]) -> Value {
    let mean = fmean(values);
    let ci = if values.len() < 2 { Value::Null } else { json!(1.96 * stdev(values) / (values.len() as f64).sqrt()) };
    json!({"mean": mean, "mean_95ci_half_width": ci})
}

pub fn run_range(cfg: &Config, start: i64, end: i64) -> Vec<IterResult> {
    (start..end).map(|i| Iteration::new(cfg, cfg.seed + i, i == 0).run()).collect()
}

pub fn simulate(request: Value, catalog: &Catalog) -> Result<Value, String> {
    let cfg = Config::new(request, catalog)?;
    let results = run_range(&cfg, 0, cfg.iterations);
    Ok(finalize(&cfg, &results))
}

pub fn finalize(cfg: &Config, results: &[IterResult]) -> Value {
    let t = cfg.t;
    let n = results.len() as f64;
    let dps: Vec<f64> = results.iter().map(|r| r.total / r.duration).collect();
    let tps: Vec<f64> = results.iter().map(|r| (r.threat + r.pet_threat) / r.duration).collect();
    let dtps: Vec<f64> = results.iter().map(|r| r.taken / r.duration).collect();
    let alive: Vec<f64> = results.iter().map(|r| r.taken / r.alive_seconds.max(0.001)).collect();
    let mut agg: IndexMap<String, Row> = IndexMap::new();
    for r in results {
        for (name, row) in &r.rows {
            let target = agg.entry(name.clone()).or_default();
            target.casts += row.casts;
            target.hits += row.hits;
            target.crits += row.crits;
            target.misses += row.misses;
            target.glances += row.glances;
            target.dodges += row.dodges;
            target.damage += row.damage;
            target.threat += row.threat;
        }
    }
    let duration = cfg.duration;
    let mut ability_stats = Map::new();
    let mut ability_dps = Map::new();
    let mut ability_damage = Map::new();
    let mut threat_by = Map::new();
    for (name, row) in &agg {
        ability_stats.insert(name.clone(), json!({"casts": row.casts / n, "hits": row.hits / n, "crits": row.crits / n, "misses": row.misses / n, "glances": row.glances / n, "dodges": row.dodges / n, "damage": row.damage / n, "threat": row.threat / n}));
        ability_dps.insert(name.clone(), json!(row.damage / n / duration));
        ability_damage.insert(name.clone(), json!(row.damage / n));
        threat_by.insert(name.clone(), json!(row.threat / n / duration));
    }
    let starved = fmean(&results.iter().map(|r| r.starved / r.duration).collect::<Vec<_>>());
    let mut taken_by: IndexMap<String, f64> = IndexMap::new();
    for r in results {
        for (k, v) in &r.taken_by {
            *taken_by.entry(k.clone()).or_insert(0.0) += v / n / duration;
        }
    }
    let cfg_summary = cfg.summary();
    let res_name = cfg.spec.resource.clone();
    let max_res = match res_name.as_str() {
        "Mana" => cfg.stats.get("mana").copied().unwrap_or(0.0),
        "Energy" => 100.0 + cfg.flag("max_energy") + cfg.stats.get("maxEnergy").copied().unwrap_or(0.0),
        _ => 100.0 + cfg.flag("max_rage"),
    };
    let ooms: Vec<f64> = results.iter().filter_map(|r| r.first_oom).collect();
    let first_oom = if ooms.is_empty() { Value::Null } else { json!(fmean(&ooms)) };
    let mut buff_seconds_agg: IndexMap<String, f64> = IndexMap::new();
    let mut buff_proc_agg: IndexMap<String, i64> = IndexMap::new();
    for r in results {
        for (name, secs) in &r.buff_active_seconds {
            *buff_seconds_agg.entry(name.clone()).or_insert(0.0) += secs;
        }
        for (name, procs) in &r.buff_procs {
            *buff_proc_agg.entry(name.clone()).or_insert(0) += procs;
        }
    }
    let mut buff_uptimes = Map::new();
    let mut effects: Vec<&String> = cfg.buffs.iter().chain(cfg.consumes.iter()).collect();
    effects.sort();
    effects.dedup();
    for x in effects {
        buff_uptimes.insert(x.clone(), json!(1.0));
    }
    for (name, secs) in &buff_seconds_agg {
        buff_uptimes.insert(name.clone(), json!((secs / n / duration).min(1.0)));
    }
    let buff_procs_per_min: Map<String, Value> = buff_proc_agg.iter().map(|(name, procs)| (name.clone(), json!(*procs as f64 / n / (duration / 60.0)))).collect();
    let debuff_uptimes: Map<String, Value> = cfg.debuffs.iter().map(|x| (x.clone(), json!(1.0))).collect();
    let mut spec = serde_json::to_value(&cfg.spec).unwrap();
    if let Value::Object(m) = &mut spec {
        m.insert("actions".into(), json!(cfg.action_names));
        m.insert("opener".into(), if cfg.spec.role == "tank" { json!("Taunt") } else { Value::Null });
        m.insert("races".into(), json!(t.CLASS_RACES[&cfg.spec.class_name]));
    }
    let survival = results.iter().filter(|r| r.alive).count() as f64 / n;
    json!({
        "profile": {"spec": cfg.spec.id, "race": cfg.race, "level": t.LEVEL, "target_level": t.TARGET_LEVEL, "duration": duration, "duration_variance": cfg.variance, "iterations": cfg.iterations, "seed": cfg.seed},
        "spec": spec,
        "metrics": {"dps": metric(&dps), "tps": metric(&tps), "dtps": metric(&dtps), "alive_dtps": metric(&alive), "survival_fraction": survival},
        "ability_dps": ability_dps, "ability_damage": ability_damage, "ability_stats": ability_stats, "threat_by_ability": threat_by, "taken_dtps": taken_by,
        "configuration": cfg_summary,
        "resource": {"name": res_name, "maximum": max_res, "mean_end": fmean(&results.iter().map(|r| r.resource_end).collect::<Vec<_>>()), "starved_fraction": starved, "first_out_of_mana": first_oom},
        "buff_uptimes": buff_uptimes, "debuff_uptimes": debuff_uptimes, "buff_procs_per_min": buff_procs_per_min,
        "log": results.first().map(|r| serde_json::to_value(&r.log).unwrap()).unwrap_or(Value::Array(vec![])),
        "model_status": "Event-driven level-60 model: sourced base damage, coefficients, cast times, Classic attack tables (miss, dodge, parry, glancing, block, crit suppression), resource ticks, combo points, DoTs, procs, timed cooldowns, pets and racials. No calibration multiplier. Provisional values are listed under configuration.notes.",
        "source": "https://wago.tools (reviewed client fields and talent curves, build 1.60.1.69913; data/wago_verified.json) + https://www.wowhead.com/forever/ (roster, racials, calculator) + WoWSims Classic (baseline mechanics). Unverified behavior remains provisional.",
        "engine": "rust-wasm",
    })
}
