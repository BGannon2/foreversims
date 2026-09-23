//! Forever Paladin engine (port of `sim.py` + `gear_data.apply_gear`).

use crate::data::{paladin_tables, tables, PaladinTables};
use crate::items::{Catalog, Item};
use crate::rng::PyRandom;
use crate::spec_sim::{fmean, stdev};
use indexmap::IndexMap;
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};
use std::cmp::{Ordering, Reverse};
use std::collections::BinaryHeap;

fn title(s: &str) -> String {
    let mut c = s.chars();
    match c.next() { Some(f) => f.to_uppercase().collect::<String>() + &c.as_str().to_lowercase(), None => String::new() }
}

// ---------------------------------------------------------------------------
// Preset / validation
// ---------------------------------------------------------------------------

pub fn talent_build(spec: &str) -> IndexMap<String, i64> {
    let pt = paladin_tables();
    let mut build: IndexMap<String, i64> = pt.talents.keys().map(|k| (k.clone(), 0)).collect();
    let chosen = if spec == "protection" { &pt.protection_build } else { &pt.retribution_build };
    for (k, v) in chosen {
        build.insert(k.clone(), *v);
    }
    build
}

pub fn preset(spec: &str) -> Result<Value, String> {
    if spec != "protection" && spec != "retribution" {
        return Err("Spec must be protection or retribution".into());
    }
    let pt = paladin_tables();
    let prot = spec == "protection";
    Ok(json!({
        "spec": spec, "race": "Human", "duration": 120.0, "duration_variance": 0.0, "iterations": 300, "seed": 42,
        "character": {"health": 1381.0, "mana": 1512.0,
            "base_mana": 1512.0, "mana_per_second": 0.0, "spirit": 75.0, "mp5": 0.0,
            "level": 60.0, "strength": 105.0, "agility": 65.0, "stamina": 100.0, "intellect": 70.0,
            "attack_power": 160.0, "spell_power": 0.0, "armor": 0.0, "defense": 300.0,
            "weapon_min": 1.0, "weapon_max": 2.0,
            "weapon_speed": 2.0, "hit_chance": 0.92, "crit_chance": 0.007,
            "spell_hit_chance": 0.83, "spell_crit_chance": 0.035,
            "physical_mitigation": 0.0, "avoidance": 0.057,
            "block_chance": if prot { 0.05 } else { 0.0 }, "block_value": 0.0},
        "encounter": {"preset_name": "Patchwerk (120-second single-target model)",
            "targets": 1.0,
            "enemies": 1, "enemy_swing": 2.0, "enemy_damage_min": 2700.0, "enemy_damage_max": 3300.0,
            "target_level": 63.0, "target_armor": 3731.0, "boss_type": "none",
            "enemy_crit_chance": 0.05, "enemy_crit_multiplier": 2.0,
            "target_physical_mitigation": 0.3, "heal_amount": 2500.0,
            "heal_interval": 2.0, "incoming_enabled": prot},
        "raid_buffs": {"bloodlust": true, "power_word_fortitude": true, "mark_of_the_wild": true,
            "arcane_intellect": true, "battle_shout": true, "blessing_of_might": true,
            "devotion_aura": true, "blessing_of_kings": true, "blessing_of_wisdom": true,
            "strength_of_earth": true, "windfury_totem": true, "grace_of_air": false,
            "mana_spring": true, "leader_of_the_pack": true, "moonkin_aura": false, "trueshot_aura": true},
        "consumables": {"flask_of_the_titans": prot, "elixir_of_the_mongoose": true,
            "elixir_of_superior_defense": prot, "elixir_of_fortitude": prot,
            "greater_stoneshield_potion": prot, "smoked_desert_dumplings": true,
            "rumsey_rum_black_label": prot, "mageblood_potion": true,
            "juju_power": true, "juju_might": true, "brilliant_wizard_oil": true,
            "gift_of_arthas": prot, "major_mana_potion": !prot, "demonic_rune": true,
            "goblin_sapper_charge": true, "dragonbreath_chili": true},
        "debuffs": {"sunder_armor_5": true, "faerie_fire": true, "curse_of_recklessness": true,
            "judgement_of_the_crusader": true, "gift_of_arthas": true,
            "demoralizing_shout": true, "thunder_clap": true,
            "insect_swarm": true, "scorpid_sting": true},
        "model": {"command_proc_chance": 0.25, "righteousness_damage": 50.0,
            "holy_strike_cost": 20.0, "holy_strike_cooldown": 12.0, "holy_strike_weapon_pct": 0.40,
            "holy_strike_holy_min": 81.0, "holy_strike_holy_max": 105.0, "holy_strike_coeff": 0.429,
            "hammer_of_wrath_cost": 425.0, "hammer_of_wrath_cooldown": 6.0, "hammer_of_wrath_min": 474.0, "hammer_of_wrath_max": 522.0, "hammer_of_wrath_coeff": 0.429,
            "melee_crit_multiplier": 2.0, "spell_crit_multiplier": 1.5,
            "base_threat_per_damage": 1.0, "holy_threat_per_damage": 1.0,
            "use_classic_era_conversions": true, "thunderfury_proc_chance": 0.20,
            "thunderfury_damage": 300.0, "thunderfury_threat_multiplier": 1.43},
        "rotation": {"use_judgement": true, "use_consecration": true, "consecration_mana_floor": 0.30, "use_holy_strike": true, "use_exorcism": true, "use_holy_wrath": true, "use_hammer_of_wrath": !prot, "twist_seals": !prot,
            "use_bulwark": prot, "bulwark_health_threshold": 0.5},
        "gear": pt.phase6_gear[spec], "enchants": pt.default_enchants[spec],
        "talents": talent_build(spec)
    }))
}

fn num(v: &Value) -> f64 {
    v.as_f64().unwrap_or(0.0)
}

fn is_int(v: &Value) -> bool {
    matches!(v, Value::Number(n) if n.is_i64() || n.is_u64())
}

fn walk(value: &Value, schema: &Value, path: &str) -> Result<(), String> {
    match schema {
        Value::Object(s) => {
            let Value::Object(v) = value else { return Err(format!("{path}: fields must be {}", s.keys().cloned().collect::<Vec<_>>().join(", "))) };
            let same = v.len() == s.len() && s.keys().all(|k| v.contains_key(k));
            if !same {
                return Err(format!("{path}: fields must be {}", s.keys().cloned().collect::<Vec<_>>().join(", ")));
            }
            for (k, sv) in s {
                walk(&v[k], sv, &format!("{path}.{k}"))?;
            }
            Ok(())
        }
        Value::Bool(_) => {
            if !value.is_boolean() {
                return Err(format!("{path} must be true or false"));
            }
            Ok(())
        }
        Value::Number(_) => {
            let Value::Number(n) = value else { return Err(format!("{path} must be a finite number")) };
            let f = n.as_f64().unwrap_or(f64::NAN);
            if !f.is_finite() {
                return Err(format!("{path} must be a finite number"));
            }
            if f < 0.0 {
                return Err(format!("{path} must be nonnegative"));
            }
            if f > 4294967296.0 {
                return Err(format!("{path} exceeds the prototype numeric limit"));
            }
            Ok(())
        }
        _ => {
            if !value.is_string() {
                return Err(format!("{path} must be text"));
            }
            Ok(())
        }
    }
}

pub fn validate(profile: &Value) -> Result<Value, String> {
    let pt = paladin_tables();
    let t = tables();
    let Value::Object(_) = profile else { return Err("Choose protection or retribution.".into()) };
    let spec = profile.get("spec").and_then(|v| v.as_str()).unwrap_or("");
    if spec != "protection" && spec != "retribution" {
        return Err("Choose protection or retribution.".into());
    }
    let mut p = profile.clone();
    if p.get("race").is_none() {
        p["race"] = json!("Human");
    }
    if p.get("enchants").is_none() { p["enchants"] = Value::Object(pt.gear_slots.iter().map(|slot| (slot.clone(), json!(""))).collect()); }
    if let Some(buffs) = p.get_mut("raid_buffs").and_then(|v| v.as_object_mut()) { buffs.entry("bloodlust").or_insert(json!(true)); }
    let race = p["race"].as_str().unwrap_or("").to_string();
    if !t.CLASS_RACES["Paladin"].contains(&race) {
        return Err(format!("{} cannot be a Paladin in World of Warcraft: Forever.", p["race"].as_str().map(|s| s.to_string()).unwrap_or_else(|| p["race"].to_string())));
    }
    let template = preset(spec)?;
    walk(&p, &template, "profile")?;
    let talents = p["talents"].as_object().unwrap();
    let rank_of = |id: &str| talents.get(id).and_then(|v| v.as_i64()).unwrap_or(0);
    let mut total_points = 0;
    for (tree_name, ids) in &pt.tree_talents {
        for id in ids {
            let t_ = &pt.talents[id];
            let v = &talents[id];
            let rank = v.as_i64().unwrap_or(-1);
            if !is_int(v) || !(0..=t_.ranks).contains(&rank) {
                return Err(format!("{} rank must be 0..{}", t_.name, t_.ranks));
            }
            total_points += rank;
            if rank != 0 {
                let prior: i64 = ids.iter().filter(|o| pt.talents[*o].row < t_.row).map(|o| rank_of(o)).sum();
                let needed = t_.row * pt.points_per_tier;
                if prior < needed {
                    return Err(format!("{} requires {needed} points in prior {tree_name} tiers", t_.name));
                }
                for req in &t_.requires {
                    if rank_of(&req.id) < req.qty {
                        return Err(format!("{} requires {} rank {}", t_.name, pt.talents[&req.id].name, req.qty));
                    }
                }
            }
        }
    }
    if total_points > pt.max_points {
        return Err(format!("Talent build exceeds the {}-point level-60 limit", pt.max_points));
    }
    let mut active: IndexMap<&str, &str> = IndexMap::new();
    for (key, enabled) in p["consumables"].as_object().unwrap() {
        if enabled.as_bool().unwrap_or(false) {
            let group = pt.consumable_groups[key].as_str();
            if let Some(prev) = active.get(group) {
                return Err(format!("{key} cannot be combined with {prev} ({} group)", group.replace('_', " ")));
            }
            active.insert(group, key);
        }
    }
    for (key, low, high) in [("duration", 1.0, 1800.0), ("duration_variance", 0.0, 60.0), ("iterations", 1.0, 10000.0), ("seed", 0.0, 4294967295.0)] {
        let v = num(&p[key]);
        if !(low <= v && v <= high) {
            return Err(format!("{key} must be {}..{}", low as i64, high as i64));
        }
    }
    for key in ["iterations", "seed"] {
        if !is_int(&p[key]) {
            return Err(format!("{key} must be an integer"));
        }
    }
    if num(&p["duration"]) * num(&p["iterations"]) > 400_000.0 {
        return Err("Run too large; keep duration x iterations at or below 400,000 seconds.".into());
    }
    let (c, e, m, r) = (&p["character"], &p["encounter"], &p["model"], &p["rotation"]);
    for (obj, key) in [(c, "health"), (c, "mana"), (c, "weapon_speed"), (e, "enemy_swing"), (e, "heal_interval")] {
        if num(&obj[key]) < 0.1 {
            return Err(format!("{key} must be at least 0.1"));
        }
    }
    if !is_int(&e["enemies"]) || !(1.0..=20.0).contains(&num(&e["enemies"])) {
        return Err("enemies must be an integer from 1 to 20".into());
    }
    if !t.CREATURE_TYPES.iter().any(|x| x == e["boss_type"].as_str().unwrap_or("")) {
        return Err("Choose a supported boss creature type.".into());
    }
    if num(&c["weapon_min"]) > num(&c["weapon_max"]) {
        return Err("weapon_min exceeds weapon_max".into());
    }
    if num(&e["enemy_damage_min"]) > num(&e["enemy_damage_max"]) {
        return Err("enemy_damage_min exceeds enemy_damage_max".into());
    }
    let checks: [(&Value, &[&str]); 4] = [
        (c, &["hit_chance", "crit_chance", "spell_hit_chance", "spell_crit_chance", "physical_mitigation", "avoidance", "block_chance"]),
        (e, &["enemy_crit_chance", "target_physical_mitigation"]),
        (m, &["command_proc_chance", "thunderfury_proc_chance"]),
        (r, &["bulwark_health_threshold", "consecration_mana_floor"]),
    ];
    for (obj, keys) in checks {
        for key in keys {
            let v = num(&obj[*key]);
            if !(0.0..=1.0).contains(&v) {
                return Err(format!("{key} must be between 0 and 1"));
            }
        }
    }
    if num(&p["duration"]) * num(&p["iterations"]) * (1.0 / num(&c["weapon_speed"]) + num(&e["enemies"]) / num(&e["enemy_swing"]) + 10.0 + 1.0 / num(&e["heal_interval"])) > 30_000_000.0 {
        return Err("Run too large; reduce iterations, duration, or enemies.".into());
    }
    Ok(p)
}

// ---------------------------------------------------------------------------
// Gear bridge (gear_data.apply_gear)
// ---------------------------------------------------------------------------

fn obj_f(v: &Value, key: &str) -> f64 {
    v.get(key).and_then(|x| x.as_f64()).unwrap_or(0.0)
}

fn set_f(v: &mut Value, key: &str, val: f64) {
    v[key] = json!(val);
}

pub fn apply_gear(profile: &Value, catalog: &Catalog) -> Result<(Value, Value), String> {
    let pt = paladin_tables();
    let t = tables();
    let mut effective = profile.clone();
    let mut totals: IndexMap<String, f64> = IndexMap::new();
    let mut equipped = Vec::new();
    let mut main: Option<Item> = None;
    let mut set_counts: IndexMap<String, i64> = IndexMap::new();
    let mut set_definitions: IndexMap<String, crate::items::ItemSet> = IndexMap::new();
    let gear = effective["gear"].clone();
    let mut item_effects = Vec::new();
    let mut unresolved_effects = Vec::new();
    let mut applied_enchants = Vec::new();
    for slot in &pt.gear_slots {
        let item_id = gear.get(slot).and_then(|v| v.as_i64()).unwrap_or(0);
        if item_id == 0 {
            continue;
        }
        let Some(item) = catalog.items.get(&item_id) else { return Err(format!("Unknown Classic Era item id {item_id} in {slot}.")) };
        if !item.equipSlots.iter().any(|s| s == slot) {
            return Err(format!("{} cannot be equipped in {slot}.", item.name));
        }
        equipped.push(json!({"slot": slot, "id": item_id, "name": item.name, "quality": item.extra.get("quality"), "itemLevel": item.extra.get("itemLevel"), "wowhead": item.extra.get("wowhead"), "set": item.set}));
        let modeled = pt.item_models.get(&item_id.to_string());
        let stats = modeled.map(|m| m.0.clone()).unwrap_or_else(|| item.stat_map());
        if let Some((_, effects, unresolved)) = modeled {
            item_effects.extend(effects.clone());
            unresolved_effects.extend(unresolved.clone());
        }
        for (key, value) in stats {
            *totals.entry(key).or_insert(0.0) += value;
        }
        let enchant_id = effective.get("enchants").and_then(|e| e.get(slot)).and_then(|v| v.as_str()).unwrap_or("");
        if !enchant_id.is_empty() {
            let Some(enchant) = catalog.enchants.get(slot).and_then(|rows| rows.iter().find(|e| e.id == enchant_id)) else { return Err(format!("Unknown enchant {enchant_id} in {slot}.")); };
            if ["main_hand", "off_hand"].contains(&slot.as_str()) && !item.has_weapon_damage() { return Err(format!("{} requires a weapon in {slot}.", enchant.name)); }
            for (key, value) in &enchant.stats {
                *totals.entry(if key == "primary" { "strength".into() } else { key.clone() }).or_insert(0.0) += value.as_f64().unwrap_or(0.0);
            }
            if enchant_id == "crusader" { item_effects.push(json!({"name": "Crusader", "kind": "strength", "ppm": 1.0, "value": 100, "duration": 15})); }
            applied_enchants.push(json!({"slot": slot, "id": enchant_id, "name": enchant.name}));
        }
        if let Some(set) = &item.set {
            *set_counts.entry(set.name.clone()).or_insert(0) += 1;
            set_definitions.insert(set.name.clone(), set.clone());
        }
        if slot == "main_hand" {
            main = Some(item.clone());
        }
    }
    let mut bonus_totals: IndexMap<String, f64> = IndexMap::new();
    let mut active_forever_bonuses = Vec::new();
    let mut active_classic_bonuses: Vec<Value> = Vec::new();
    let mut set_flags = Map::new();
    for (name, count) in &set_counts {
        let Some(over) = pt.forever_sets.get(name) else {
            for bonus in &set_definitions[name].bonuses {
                if *count < bonus.required {
                    continue;
                }
                let conditional = crate::items::re_search(r"chance on|chance to (?:gain|increase|grant|restore|trigger)|proc|for \d+ sec|when |whenever |after |stack", &bonus.description).is_some();
                let mut stats: IndexMap<String, f64> = if conditional { IndexMap::new() } else { bonus.stats.clone() };
                if stats.is_empty() && !conditional {
                    for (key, pattern) in crate::items::SET_PATTERNS {
                        if let Some(g) = crate::items::re_search(pattern, &bonus.description) {
                            stats.insert(key.to_string(), g[1].clone().unwrap().parse().unwrap());
                            break;
                        }
                    }
                }
                for (stat, value) in &stats {
                    *totals.entry(stat.clone()).or_insert(0.0) += value;
                }
                let key = format!("{}|{}", name, bonus.required);
                let flag = match key.as_str() { "Judgement Armor|8" => Some("judgement_bonus_damage"), "Battlegear of Eternal Justice|3" => Some("eternal_justice_mana"), _ => None };
                if let Some(f) = flag {
                    set_flags.insert(f.to_string(), json!(true));
                }
                active_classic_bonuses.push(json!({"set": name, "required": bonus.required, "description": bonus.description, "stats": stats, "modeled": !stats.is_empty() || flag.is_some()}));
            }
            continue;
        };
        for bonus in &over.bonuses {
            if *count < bonus.required {
                continue;
            }
            let mut row = Map::new();
            row.insert("set".into(), json!(name));
            row.insert("source".into(), json!(over.source));
            if let Value::Object(b) = serde_json::to_value(bonus).unwrap() {
                for (k, v) in b {
                    if k == "modeled" && v.is_null() {
                        continue;
                    }
                    row.insert(k, v);
                }
            }
            active_forever_bonuses.push(Value::Object(row));
            for (stat, value) in &bonus.stats {
                *totals.entry(stat.clone()).or_insert(0.0) += value;
            }
        }
    }
    let race = effective.get("race").and_then(|v| v.as_str()).unwrap_or("Human").to_string();
    if let Some(rs) = t.RACE_STATS.get(&race) {
        for (stat, value) in rs {
            *totals.entry(stat.clone()).or_insert(0.0) += value;
        }
    }
    let classic = effective.get("model").and_then(|m| m.get("use_classic_era_conversions")).and_then(|v| v.as_bool()).unwrap_or(false);
    if classic {
        if let Some(Value::Object(rb)) = effective.get("raid_buffs") {
            for (key, enabled) in rb {
                if enabled.as_bool().unwrap_or(false) {
                    if let Some(stats) = t.BUFF_STATS.get(key) {
                        for (stat, value) in stats {
                            *bonus_totals.entry(stat.clone()).or_insert(0.0) += value;
                        }
                    }
                }
            }
        }
        if let Some(Value::Object(cs)) = effective.get("consumables") {
            for (key, enabled) in cs {
                if enabled.as_bool().unwrap_or(false) {
                    if let Some(stats) = pt.consumable_stats.get(key) {
                        for (stat, value) in stats {
                            *bonus_totals.entry(stat.clone()).or_insert(0.0) += value;
                        }
                    }
                }
            }
        }
        for (stat, value) in &bonus_totals {
            *totals.entry(stat.clone()).or_insert(0.0) += value;
        }
    }
    effective["set_flags"] = Value::Object(set_flags.clone());
    effective["item_effects"] = json!(item_effects);
    if let Some(m) = &main {
        if m.slot.as_deref() == Some("Two-Hand") && effective["gear"]["off_hand"].as_i64().unwrap_or(0) != 0 {
            return Err("A two-handed weapon cannot be combined with an off-hand item.".into());
        }
    }
    let base = effective["character"].clone();
    let tot = |k: &str| totals.get(k).copied().unwrap_or(0.0);
    for (stat, (field, scale)) in &pt.direct_stats {
        let v = obj_f(&effective["character"], field) + tot(stat) * scale;
        set_f(&mut effective["character"], field, v);
    }
    if classic {
        for (stat, field) in &pt.classic_primary {
            let v = obj_f(&effective["character"], field) + tot(stat);
            set_f(&mut effective["character"], field, v);
        }
        let kings = if effective.get("raid_buffs").and_then(|r| r.get("blessing_of_kings")).and_then(|v| v.as_bool()).unwrap_or(false) { 1.10 } else { 1.0 };
        for field in ["strength", "agility", "stamina", "intellect", "spirit"] {
            let v = obj_f(&effective["character"], field) * kings;
            set_f(&mut effective["character"], field, v);
        }
        if race == "Human" { let v = obj_f(&effective["character"], "spirit") * 1.05; set_f(&mut effective["character"], "spirit", v); }
        let talent = |id: &str| effective.get("talents").and_then(|t| t.get(id)).and_then(|v| v.as_f64()).unwrap_or(0.0);
        let (t639, t332, t632, t630, t882) = (talent("105639"), talent("105332"), talent("105632"), talent("105630"), talent("110882"));
        let target_level = obj_f(&effective["encounter"], "target_level");
        let ch = &mut effective["character"];
        set_f(ch, "strength", obj_f(ch, "strength") * (1.0 + 0.02 * t639));
        set_f(ch, "intellect", obj_f(ch, "intellect") * (1.0 + 0.02 * t332));
        set_f(ch, "stamina", obj_f(ch, "stamina") * (1.0 + 0.02 * t632));
        set_f(ch, "armor", obj_f(ch, "armor") * (1.0 + 0.02 * t630));
        set_f(ch, "attack_power", obj_f(ch, "attack_power") + obj_f(ch, "strength") * 2.0);
        set_f(ch, "health", obj_f(ch, "health") + (obj_f(ch, "stamina") - obj_f(&base, "stamina")) * 10.0 + obj_f(&base, "stamina") * 10.0);
        set_f(ch, "mana", obj_f(ch, "mana") + obj_f(ch, "intellect") * 15.0);
        set_f(ch, "crit_chance", obj_f(ch, "crit_chance") + obj_f(ch, "agility") * 0.0506 / 100.0);
        set_f(ch, "spell_crit_chance", obj_f(ch, "spell_crit_chance") + obj_f(ch, "intellect") * 0.0167 / 100.0);
        set_f(ch, "avoidance", obj_f(ch, "avoidance") + obj_f(ch, "agility") * 0.0506 / 100.0);
        set_f(ch, "spell_power", obj_f(ch, "spell_power") + obj_f(ch, "intellect") * (1.0 / 3.0) * t882);
        let racial = t.RACIALS.get(&race).cloned().unwrap_or_default();
        set_f(ch, "health", obj_f(ch, "health") * (1.0 + racial.health_pct));
        let kinds: Vec<String> = ["main_hand", "off_hand"].iter().filter_map(|slot| gear.get(*slot).and_then(|v| v.as_i64())).filter_map(|id| catalog.items.get(&id)).filter_map(|i| i.subclass.clone()).collect();
        for (kind, bonus) in &racial.weapon_crit {
            if kind != "provisional" && kinds.iter().any(|k| k.contains(kind.as_str())) {
                let b = bonus.as_f64().unwrap_or(0.0);
                set_f(ch, "crit_chance", obj_f(ch, "crit_chance") + b / 100.0);
                set_f(ch, "spell_crit_chance", obj_f(ch, "spell_crit_chance") + b / 100.0);
            }
        }
        set_f(ch, "crit_chance", (obj_f(ch, "crit_chance") - 0.048).max(0.0));
        set_f(ch, "spell_crit_chance", (obj_f(ch, "spell_crit_chance") - 0.021).max(0.0));
        let level = obj_f(ch, "level");
        let armor = obj_f(ch, "armor");
        set_f(ch, "physical_mitigation", (armor / (armor + 400.0 + 85.0 * target_level)).min(0.75));
        let d = &effective["debuffs"];
        let mut reductions = if d["sunder_armor_5"].as_bool().unwrap_or(false) { 2250.0 } else { 0.0 };
        reductions += if d["faerie_fire"].as_bool().unwrap_or(false) { 505.0 } else { 0.0 };
        reductions += if d["curse_of_recklessness"].as_bool().unwrap_or(false) { 640.0 } else { 0.0 };
        let target_armor = (obj_f(&effective["encounter"], "target_armor") - reductions).max(0.0);
        set_f(&mut effective["encounter"], "target_physical_mitigation", target_armor / (target_armor + 400.0 + 85.0 * level));
    }
    for key in ["crit_chance", "spell_hit_chance", "spell_crit_chance", "block_chance", "avoidance"] {
        let v = obj_f(&effective["character"], key).min(1.0);
        set_f(&mut effective["character"], key, v);
    }
    if let Some(m) = &main {
        if m.weaponDamageMin.is_some() {
            set_f(&mut effective["character"], "weapon_min", m.dmg_min());
            set_f(&mut effective["character"], "weapon_max", m.dmg_max());
            set_f(&mut effective["character"], "weapon_speed", m.speed_or(0.0));
            effective["character"]["weapon_hands"] = json!(m.slot);
            set_f(&mut effective["character"], "normalized_speed", crate::items::normalized_speed(m));
        }
    }
    let mut weapon_skill = obj_f(&effective["character"], "level") * 5.0;
    if let Some(m) = &main {
        let kind = m.subclass_str();
        let key = format!("{}{kind}", if m.slot_str() == "Two-Hand" { "Two-Hand " } else { "" });
        for slot in &pt.gear_slots {
            let item = catalog.get(gear.get(slot).and_then(|v| v.as_i64()).unwrap_or(0));
            for text in &item.effects {
                if let Some(g) = crate::items::re_search(r"Increased (.+?) \+(\d+)", text) {
                    let types = g[1].as_deref().unwrap_or("").replace(", and ", ",").replace(", ", ",").replace(" and ", ",");
                    if types.split(',').map(|s| s.trim().trim_end_matches('s').replace("Two-handed", "Two-Hand")).any(|s| s == key || s == kind) {
                        weapon_skill += g[2].as_deref().unwrap_or("0").parse::<f64>().unwrap_or(0.0);
                    }
                }
            }
        }
    }
    let ch = &mut effective["character"];
    set_f(ch, "weapon_skill", weapon_skill);
    set_f(ch, "seal_cost_reduction", tot("sealCostReduction"));
    set_f(ch, "threat_reduction", tot("threatReduction") / 100.0);
    set_f(ch, "spell_power", obj_f(ch, "spell_power") + tot("holyPower"));
    let has_shield = catalog.get(gear["off_hand"].as_i64().unwrap_or(0)).subclass_str() == "Shield";
    ch["has_shield"] = json!(has_shield);
    if !has_shield { set_f(ch, "block_chance", 0.0); }
    let mut sets = Vec::new();
    let mut names: Vec<&String> = set_counts.keys().collect();
    names.sort();
    for name in names {
        let count = set_counts[name];
        let definition = &set_definitions[name];
        let forever = pt.forever_sets.get(name);
        let raw: Vec<Value> = match forever { Some(f) => f.bonuses.iter().map(|b| serde_json::to_value(b).unwrap()).collect(), None => definition.bonuses.iter().map(|b| serde_json::to_value(b).unwrap()).collect() };
        let bonuses: Vec<Value> = raw.into_iter().map(|mut b| {
            let req = b.get("required").and_then(|v| v.as_i64()).unwrap_or(99);
            if let Value::Object(m) = &mut b {
                if m.get("modeled").is_some_and(|v| v.is_null()) {
                    m.remove("modeled");
                }
                m.insert("active".into(), json!(count >= req));
            }
            b
        }).collect();
        sets.push(json!({"name": name, "count": count, "total": definition.pieces.len(), "pieces": definition.pieces, "bonuses": bonuses,
            "ruleset": if forever.is_some() { "Forever" } else { "Classic Era" },
            "source": forever.map(|f| json!(f.source)).unwrap_or_else(|| pt.catalog["source"].clone())}));
    }
    let mut modeled_keys: Vec<String> = pt.direct_stats.keys().cloned().collect();
    if classic {
        modeled_keys.extend(pt.classic_primary.keys().cloned());
    }
    let modeled: Map<String, Value> = modeled_keys.iter().filter(|k| totals.get(*k).is_some_and(|v| *v != 0.0)).map(|k| (k.clone(), json!(totals[k]))).collect();
    let unmodeled: Map<String, Value> = totals.iter().filter(|(k, v)| !modeled_keys.contains(k) && **v != 0.0).map(|(k, v)| (k.clone(), json!(v))).collect();
    let active_list = |group: &str| -> Vec<String> { effective.get(group).and_then(|g| g.as_object()).map(|o| o.iter().filter(|(_, v)| v.as_bool().unwrap_or(false)).map(|(k, _)| k.clone()).collect()).unwrap_or_default() };
    let summary = json!({"data_version": pt.catalog["version"], "source": pt.catalog["source"], "scope": pt.catalog["scope"],
        "equipped": equipped, "totals": totals, "modeled_totals": modeled,
        "unmodeled_totals": unmodeled, "sets": sets, "base_character": base,
        "raid_buff_totals": bonus_totals,
        "active_raid_buffs": active_list("raid_buffs"),
        "active_consumables": active_list("consumables"),
        "active_debuffs": active_list("debuffs"),
        "active_forever_set_bonuses": active_forever_bonuses, "active_classic_set_bonuses": active_classic_bonuses, "set_flags": set_flags,
        "effective_character": effective["character"].clone(),
        "item_effects": {"applied": item_effects, "unresolved": unresolved_effects}, "enchants": applied_enchants,
        "note": "Sourced Forever set bonuses apply at their equipped thresholds. Classic primary-stat, armor and attack-power conversions are applied only when the audit switch is enabled. Item effects are modeled individually when identified."});
    Ok((effective, summary))
}

// ---------------------------------------------------------------------------
// Fight
// ---------------------------------------------------------------------------

#[derive(Deserialize, Clone, Debug)]
pub struct Character {
    pub health: f64,
    pub mana: f64,
    pub base_mana: f64,
    pub mana_per_second: f64,
    #[serde(default)]
    pub spirit: f64,
    #[serde(default)]
    pub mp5: f64,
    pub level: f64,
    pub strength: f64,
    pub agility: f64,
    pub stamina: f64,
    pub intellect: f64,
    pub attack_power: f64,
    pub spell_power: f64,
    pub armor: f64,
    pub defense: f64,
    pub weapon_min: f64,
    pub weapon_max: f64,
    pub weapon_speed: f64,
    #[serde(default)]
    pub normalized_speed: f64,
    #[serde(default)]
    pub weapon_skill: f64,
    #[serde(default)]
    pub seal_cost_reduction: f64,
    #[serde(default)]
    pub threat_reduction: f64,
    #[serde(default)]
    pub has_shield: bool,
    pub hit_chance: f64,
    pub crit_chance: f64,
    pub spell_hit_chance: f64,
    pub spell_crit_chance: f64,
    pub physical_mitigation: f64,
    pub avoidance: f64,
    pub block_chance: f64,
    pub block_value: f64,
    #[serde(default)]
    pub weapon_hands: Option<String>,
}

#[derive(Deserialize, Clone, Debug)]
pub struct Encounter {
    pub targets: f64,
    pub enemies: i64,
    pub enemy_swing: f64,
    pub enemy_damage_min: f64,
    pub enemy_damage_max: f64,
    pub target_level: f64,
    pub target_armor: f64,
    pub boss_type: String,
    pub enemy_crit_chance: f64,
    pub enemy_crit_multiplier: f64,
    pub target_physical_mitigation: f64,
    pub heal_amount: f64,
    pub heal_interval: f64,
    pub incoming_enabled: bool,
}

#[derive(Deserialize, Clone, Debug)]
pub struct Model {
    pub command_proc_chance: f64,
    pub righteousness_damage: f64,
    pub holy_strike_cost: f64,
    pub holy_strike_cooldown: f64,
    pub holy_strike_weapon_pct: f64,
    pub holy_strike_holy_min: f64,
    pub holy_strike_holy_max: f64,
    pub holy_strike_coeff: f64,
    pub hammer_of_wrath_cost: f64,
    pub hammer_of_wrath_cooldown: f64,
    pub hammer_of_wrath_min: f64,
    pub hammer_of_wrath_max: f64,
    pub hammer_of_wrath_coeff: f64,
    pub melee_crit_multiplier: f64,
    pub spell_crit_multiplier: f64,
    pub base_threat_per_damage: f64,
    pub holy_threat_per_damage: f64,
    pub use_classic_era_conversions: bool,
    pub thunderfury_proc_chance: f64,
    pub thunderfury_damage: f64,
    pub thunderfury_threat_multiplier: f64,
}

#[derive(Deserialize, Clone, Debug)]
pub struct Rotation {
    pub use_judgement: bool,
    pub use_consecration: bool,
    #[serde(default)]
    pub consecration_mana_floor: f64,
    pub use_holy_strike: bool,
    pub use_exorcism: bool,
    pub use_holy_wrath: bool,
    #[serde(default)]
    pub use_hammer_of_wrath: bool,
    pub twist_seals: bool,
    pub use_bulwark: bool,
    pub bulwark_health_threshold: f64,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct PalLog {
    pub time: f64,
    pub event: String,
    pub amount: f64,
    pub health: f64,
    pub mana: f64,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct FightResult {
    pub dps: f64,
    pub tps: f64,
    pub dtps: f64,
    pub alive_dtps: f64,
    pub survived: bool,
    pub alive_seconds: f64,
    pub peak_3s_damage: f64,
    pub damage: IndexMap<String, f64>,
    pub threat_by_source: IndexMap<String, f64>,
    pub taken_by_source: IndexMap<String, f64>,
    pub hits: IndexMap<String, i64>,
    pub casts: IndexMap<String, i64>,
    pub damage_taken: f64,
    pub absorbed: f64,
    pub blocked_damage: f64,
    pub blocks: i64,
    pub avoids: i64,
    pub effective_healing: f64,
    pub overhealing: f64,
    pub mana_spent: f64,
    pub mana_gained: f64,
    pub ending_mana: f64,
    pub first_unaffordable_cast: Option<f64>,
    pub log: Vec<PalLog>,
    pub duration: f64,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Kind {
    Decision,
    Swing,
    Consecration,
    Enemy,
    Heal,
    Mana,
}

#[derive(Clone, Copy, Debug)]
struct Ev {
    time: f64,
    prio: u8,
    serial: u64,
    kind: Kind,
}
impl PartialEq for Ev {
    fn eq(&self, o: &Self) -> bool {
        self.cmp(o) == Ordering::Equal
    }
}
impl Eq for Ev {}
impl PartialOrd for Ev {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}
impl Ord for Ev {
    fn cmp(&self, o: &Self) -> Ordering {
        self.time.total_cmp(&o.time).then(self.prio.cmp(&o.prio)).then(self.serial.cmp(&o.serial))
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Seal {
    Righteousness,
    Command,
    Fury,
}
impl Seal {
    fn key(self) -> &'static str {
        match self { Seal::Righteousness => "righteousness", Seal::Command => "command", Seal::Fury => "fury" }
    }
}

pub struct Fight<'a> {
    pt: &'static PaladinTables,
    c: Character,
    e: Encounter,
    m: Model,
    rot: Rotation,
    tal: IndexMap<String, i64>,
    raid_buffs: IndexMap<String, bool>,
    consumables: IndexMap<String, bool>,
    debuffs: IndexMap<String, bool>,
    gear_main_hand: i64,
    duration: f64,
    prot: bool,
    rng: PyRandom,
    time: f64,
    health: f64,
    mana: f64,
    queue: BinaryHeap<Reverse<Ev>>,
    serial: u64,
    gcd: f64,
    cd: IndexMap<&'static str, f64>,
    seal: Option<Seal>,
    seal_until: f64,
    echo: Option<Seal>,
    iron_until: f64,
    execute_at: f64,
    hs_until: f64,
    hs_charges: i64,
    red_until: f64,
    red_charges: i64,
    absorb: f64,
    absorb_until: f64,
    forbearance: f64,
    vengeance: i64,
    vengeance_until: f64,
    mana_icd: f64,
    damage: IndexMap<String, f64>,
    threat_by_source: IndexMap<String, f64>,
    taken_by_source: IndexMap<String, f64>,
    hits: IndexMap<String, i64>,
    casts: IndexMap<String, i64>,
    threat: f64,
    taken: f64,
    absorbed: f64,
    blocked: f64,
    healed: f64,
    overheal: f64,
    blocks: i64,
    avoids: i64,
    mana_spent: f64,
    mana_gained: f64,
    oom: Option<f64>,
    alive: bool,
    life: f64,
    trace: bool,
    log: Vec<PalLog>,
    damage_window: std::collections::VecDeque<(f64, f64)>,
    window_sum: f64,
    peak_three_seconds: f64,
    racial: crate::data::Racial,
    judgement_bonus_damage: bool,
    eternal_justice_mana: bool,
    last_cast: f64,
    potion_cd: f64,
    rune_cd: f64,
    item_effects: Vec<Value>,
    item_until: IndexMap<String, f64>,
    item_ready: IndexMap<String, f64>,
    _marker: std::marker::PhantomData<&'a ()>,
}

fn bool_map(v: &Value) -> IndexMap<String, bool> {
    v.as_object().map(|o| o.iter().map(|(k, x)| (k.clone(), x.as_bool().unwrap_or(false))).collect()).unwrap_or_default()
}

impl<'a> Fight<'a> {
    pub fn new(profile: &Value, duration: f64, seed: i64, trace: bool) -> Result<Self, String> {
        let pt = paladin_tables();
        let t = tables();
        let c: Character = serde_json::from_value(profile["character"].clone()).map_err(|e| e.to_string())?;
        let e: Encounter = serde_json::from_value(profile["encounter"].clone()).map_err(|e| e.to_string())?;
        let m: Model = serde_json::from_value(profile["model"].clone()).map_err(|e| e.to_string())?;
        let rot: Rotation = serde_json::from_value(profile["rotation"].clone()).map_err(|e| e.to_string())?;
        let tal: IndexMap<String, i64> = profile["talents"].as_object().map(|o| o.iter().map(|(k, v)| (k.clone(), v.as_i64().unwrap_or(0))).collect()).unwrap_or_default();
        let race = profile.get("race").and_then(|v| v.as_str()).unwrap_or("Human");
        Ok(Fight {
            pt,
            health: c.health,
            mana: c.mana,
            c,
            e,
            m,
            rot,
            tal,
            raid_buffs: bool_map(&profile["raid_buffs"]),
            consumables: bool_map(&profile["consumables"]),
            debuffs: bool_map(&profile["debuffs"]),
            gear_main_hand: profile["gear"]["main_hand"].as_i64().unwrap_or(0),
            duration,
            prot: profile["spec"].as_str() == Some("protection"),
            rng: PyRandom::new(seed.unsigned_abs()),
            time: 0.0,
            queue: BinaryHeap::new(),
            serial: 0,
            gcd: 0.0,
            cd: IndexMap::new(),
            seal: None,
            seal_until: 0.0,
            echo: None,
            iron_until: 0.0,
            execute_at: duration * 0.8,
            hs_until: 0.0,
            hs_charges: 0,
            red_until: 0.0,
            red_charges: 0,
            absorb: 0.0,
            absorb_until: 0.0,
            forbearance: 0.0,
            vengeance: 0,
            vengeance_until: 0.0,
            mana_icd: 0.0,
            damage: IndexMap::new(),
            threat_by_source: IndexMap::new(),
            taken_by_source: IndexMap::new(),
            hits: IndexMap::new(),
            casts: IndexMap::new(),
            threat: 0.0,
            taken: 0.0,
            absorbed: 0.0,
            blocked: 0.0,
            healed: 0.0,
            overheal: 0.0,
            blocks: 0,
            avoids: 0,
            mana_spent: 0.0,
            mana_gained: 0.0,
            oom: None,
            alive: true,
            life: duration,
            trace,
            log: vec![],
            damage_window: Default::default(),
            window_sum: 0.0,
            peak_three_seconds: 0.0,
            racial: t.RACIALS.get(race).cloned().unwrap_or_default(),
            judgement_bonus_damage: profile.get("set_flags").and_then(|f| f.get("judgement_bonus_damage")).and_then(|v| v.as_bool()).unwrap_or(false),
            eternal_justice_mana: profile.get("set_flags").and_then(|f| f.get("eternal_justice_mana")).and_then(|v| v.as_bool()).unwrap_or(false),
            last_cast: -10.0,
            potion_cd: 0.0,
            rune_cd: 0.0,
            item_effects: profile.get("item_effects").and_then(|v| v.as_array()).cloned().unwrap_or_default(),
            item_until: IndexMap::new(), item_ready: IndexMap::new(),
            _marker: Default::default(),
        })
    }

    fn rank(&self, id: &str) -> f64 {
        self.tal.get(id).copied().unwrap_or(0) as f64
    }

    fn item_stat(&self, stat: &str) -> f64 {
        let mut value = match stat { "attack_power" => self.c.attack_power, "spell_power" => self.c.spell_power, "defense" => self.c.defense, "armor" => self.c.armor, _ => 0.0 };
        for effect in &self.item_effects {
            let name = effect["name"].as_str().unwrap_or("");
            if self.item_until.get(name).copied().unwrap_or(0.0) > self.time {
                if effect.get("stat").and_then(|v| v.as_str()) == Some(stat) { value += obj_f(effect, "value"); }
                if effect["kind"] == "strength" && stat == "attack_power" { value += obj_f(effect, "value") * 2.0; }
                if effect["kind"] == "weapon_defense" { value += obj_f(effect, stat); }
            }
        }
        value
    }

    fn swing_delay(&self) -> f64 {
        let speed = self.c.weapon_speed;
        if !self.raid_buffs.get("bloodlust").copied().unwrap_or(false) || self.time >= 40.0 { return speed; }
        let before = 40.0 - self.time;
        if speed / 1.30 <= before { speed / 1.30 } else { before + (speed - before * 1.30) }
    }

    fn activate_item(&mut self, effect: &Value) {
        let name = effect["name"].as_str().unwrap_or("");
        self.item_until.insert(name.into(), self.time + obj_f(effect, "duration"));
        *self.casts.entry(name.into()).or_insert(0) += 1;
        self.record(&format!("{name} activated"), 0.0);
    }

    fn f(&self, group: &str, key: &str) -> f64 {
        self.pt.fact(group, key)
    }

    fn cd(&self, key: &str) -> f64 {
        self.cd.get(key).copied().unwrap_or(0.0)
    }

    fn schedule(&mut self, time: f64, kind: Kind) {
        let prio = match kind { Kind::Decision => 0, Kind::Swing => 1, Kind::Consecration => 2, Kind::Enemy => 3, Kind::Heal => 4, Kind::Mana => 5 };
        self.serial += 1;
        self.queue.push(Reverse(Ev { time, prio, serial: self.serial, kind }));
    }

    fn record(&mut self, event: &str, amount: f64) {
        if self.trace {
            let r = |v: f64, d: f64| (v * d).round() / d;
            self.log.push(PalLog { time: r(self.time, 1e4), event: event.to_string(), amount: r(amount, 1e3), health: r(self.health, 1e3), mana: r(self.mana, 1e3) });
        }
    }

    fn gain_mana(&mut self, amount: f64) {
        let gained = amount.min(self.c.mana - self.mana);
        self.mana += gained;
        self.mana_gained += gained;
    }

    fn spend(&mut self, name: &str, amount: f64) -> bool {
        let amount = if name.starts_with("Seal") { (amount - self.c.seal_cost_reduction).max(0.0) } else { amount };
        let discounted = name.starts_with("Seal") || ["Judgement", "Holy Shield", "Holy Strike", "Templar's Bulwark", "Consecration"].contains(&name);
        let amount = amount * if discounted { 1.0 - 0.02 * self.rank("105706") } else { 1.0 };
        if self.mana + 1e-9 < amount {
            if self.oom.is_none() {
                self.oom = Some(self.time);
            }
            return false;
        }
        self.mana = (self.mana - amount).max(0.0);
        self.mana_spent += amount;
        self.last_cast = self.time;
        *self.casts.entry(name.to_string()).or_insert(0) += 1;
        self.record(&format!("Cast {name}"), 0.0);
        true
    }

    fn mana_tick(&mut self) {
        let mut regen = self.c.mp5 / 5.0 * 2.0;
        let spirit = self.c.spirit / 5.0 + 15.0;
        if self.time - self.last_cast >= 5.0 {
            regen += spirit;
        } else {
            regen += spirit * 0.10 * self.rank("110871");
        }
        self.gain_mana(regen);
        if self.consumables.get("major_mana_potion").copied().unwrap_or(false) && self.time >= self.potion_cd && self.c.mana - self.mana >= 1800.0 {
            let v = self.rng.uniform(1350.0, 2250.0);
            self.gain_mana(v);
            self.potion_cd = self.time + 120.0;
            *self.casts.entry("Major Mana Potion".into()).or_insert(0) += 1;
            self.record("Major Mana Potion", 0.0);
        }
        if self.consumables.get("demonic_rune").copied().unwrap_or(false) && self.time >= self.rune_cd && self.c.mana - self.mana >= 1500.0 {
            let v = self.rng.uniform(900.0, 1500.0);
            self.gain_mana(v);
            self.rune_cd = self.time + 120.0;
            *self.casts.entry("Demonic Rune".into()).or_insert(0) += 1;
            self.record("Demonic Rune", 0.0);
        }
    }

    fn touch_of_the_grave(&mut self) {
        if let Some(tg) = self.racial.touch_of_the_grave.clone() {
            if self.rng.random() < tg.chance {
                let amt = self.c.health * tg.health_fraction;
                self.deal("Touch of the Grave", amt, true, false, 1.0, 1.0, false, Some(false), 0.0);
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn deal(&mut self, name: &str, amount: f64, holy: bool, can_crit: bool, hit: f64, extra_threat: f64, melee_crit: bool, physical: Option<bool>, spell_coefficient: f64) -> bool {
        self.deal_inner(name, amount, holy, can_crit, hit, extra_threat, melee_crit, physical, spell_coefficient).is_some()
    }

    // Mirrors sim.py's `deal_inner` parameter list 1:1 for parity auditing; a
    // struct wrapper would obscure the line-by-line comparison with Python.
    #[allow(clippy::too_many_arguments)]
    fn deal_inner(&mut self, name: &str, amount: f64, holy: bool, can_crit: bool, hit: f64, extra_threat: f64, melee_crit: bool, physical: Option<bool>, spell_coefficient: f64) -> Option<f64> {
        let precision = 0.01 * self.rank("105638");
        let mut crit = if melee_crit || !holy { self.c.crit_chance } else { self.c.spell_crit_chance };
        if melee_crit || !holy {
            crit += 0.01 * self.rank("105703");
        }
        let white = ["Melee", "Reckoning", "Windfury Attack", "Hand of Justice"].contains(&name);
        let mut glance = 1.0;
        let critical;
        if self.m.use_classic_era_conversions && (white || melee_crit) {
            let delta = self.e.target_level * 5.0 - self.c.weapon_skill;
            let miss = 0.05 + delta * if delta > 10.0 { 0.002 } else { 0.001 };
            let bonus = (hit - 0.92).max(0.0) + precision;
            let miss = (miss - (bonus - if delta > 10.0 { 0.01 } else { 0.0 }).max(0.0)).max(0.0);
            let dodge = (0.05 + delta * 0.001).max(0.0);
            let parry = if self.prot { 0.14 } else { 0.0 };
            let roll = self.rng.random();
            if roll < miss + dodge + parry {
                self.record(&format!("{name}{}", if roll < miss { " miss" } else if roll < miss + dodge { " dodge" } else { " parry" }), 0.0);
                return None;
            }
            let glancing = if white { 0.40 } else { 0.0 };
            if roll < miss + dodge + parry + glancing {
                glance = self.rng.uniform((1.3 - 0.05 * delta).clamp(0.01, 0.91), (1.2 - 0.03 * delta).clamp(0.2, 0.99));
                critical = false;
            } else { critical = can_crit && roll < miss + dodge + parry + glancing + (crit + (15.0 - delta) * 0.0004).max(0.0); }
        } else {
            if self.rng.random() >= (hit + precision).min(1.0) {
                self.record(&format!("{name} miss"), 0.0); return None;
            }
            critical = can_crit && self.rng.random() < crit.min(1.0);
        }
        if self.time >= self.vengeance_until {
            self.vengeance = 0;
        }
        let mut amount = amount;
        if holy && spell_coefficient != 0.0 {
            let holy_bonus = self.item_stat("spell_power") + if self.debuffs.get("judgement_of_the_crusader").copied().unwrap_or(false) { 140.0 } else { 0.0 };
            amount += holy_bonus * spell_coefficient;
        }
        amount *= 1.0 + self.vengeance as f64 * self.f("vengeance_rank1", "bonus_per_stack") * self.rank("105693");
        let crusade_rank = self.rank("110883");
        let creature_crusade = if self.e.boss_type == "demon" || self.e.boss_type == "undead" { crusade_rank } else { 0.0 };
        amount *= 1.0 + 0.01 * (crusade_rank + creature_crusade);
        amount *= 1.0 + self.racial.creature_damage.get(&self.e.boss_type).copied().unwrap_or(0.0);
        let physical = physical.unwrap_or(!holy);
        if physical && self.debuffs.get("gift_of_arthas").copied().unwrap_or(false) && self.consumables.get("gift_of_arthas").copied().unwrap_or(false) {
            amount += 8.0;
        }
        if physical {
            amount *= 1.0 - self.e.target_physical_mitigation;
        }
        if critical {
            amount *= if melee_crit || !holy { self.m.melee_crit_multiplier } else { self.m.spell_crit_multiplier };
        }
        amount *= glance;
        *self.damage.entry(name.to_string()).or_insert(0.0) += amount;
        *self.hits.entry(name.to_string()).or_insert(0) += 1;
        let base_threat = if holy { self.m.holy_threat_per_damage } else { self.m.base_threat_per_damage };
        let generated = amount * base_threat * extra_threat * if holy && self.prot { self.f("righteous_fury", "holy_threat_multiplier") } else { 1.0 };
        let generated = generated * (1.0 - self.c.threat_reduction);
        self.threat += generated;
        *self.threat_by_source.entry(name.to_string()).or_insert(0.0) += generated;
        self.record(&format!("{name}{}", if critical { " crit" } else { "" }), amount);
        if name != "Touch of the Grave" && !name.starts_with("Consecration") {
            self.touch_of_the_grave();
        }
        if critical && self.rank("105693") != 0.0 {
            self.vengeance = (self.f("vengeance_rank1", "max_stacks") as i64).min(self.vengeance + 1);
            self.vengeance_until = self.time + self.f("vengeance_rank1", "duration");
        }
        Some(amount)
    }

    fn seal_proc(&mut self, seal: Seal, weapon: f64, echo: bool) {
        let suffix = if echo { " echo" } else { "" };
        let seal_bonus = 1.0 + 0.05 * self.rank("105334");
        match seal {
            Seal::Command => {
                if self.rng.random() < self.m.command_proc_chance {
                    let amt = weapon * self.f("command", "weapon_fraction") * seal_bonus;
                    self.deal(&format!("Seal of Command{suffix}"), amt, true, false, 1.0, 1.0, false, None, 0.29 * seal_bonus);
                }
            }
            Seal::Righteousness => {
                let hand_mult = if self.c.weapon_hands.as_deref() == Some("Two-Hand") {
                    self.f("righteousness", "proc_two_hand_mult")
                } else {
                    self.f("righteousness", "proc_one_hand_mult")
                };
                let amt = self.f("righteousness", "proc_base") * hand_mult * self.c.weapon_speed * seal_bonus;
                let coeff = self.f("righteousness", "proc_coeff") * seal_bonus;
                self.deal(&format!("Seal of Righteousness{suffix}"), amt, true, false, 1.0, 1.0, false, None, coeff);
            }
            Seal::Fury => {
                let coeff = self.f("fury", "swing_pct_sp") * seal_bonus;
                let base = self.f("fury", "swing_base") * seal_bonus;
                let dealt = self.deal_inner(&format!("Seal of Fury{suffix}"), base, true, false, 1.0, 1.0, false, None, coeff);
                if let Some(dealt) = dealt {
                    if dealt != 0.0 && self.c.block_chance > 0.0 {
                        self.absorb += dealt * self.f("fury", "absorb_pct");
                        self.absorb_until = self.absorb_until.max(self.time + self.f("fury", "duration"));
                    }
                }
            }
        }
    }

    fn swing(&mut self, extra: bool, bonus_ap: f64, extra_name: &str) {
        let mut weapon = self.rng.uniform(self.c.weapon_min, self.c.weapon_max);
        if self.m.use_classic_era_conversions {
            weapon += (self.item_stat("attack_power") + bonus_ap) / 14.0 * self.c.weapon_speed;
        }
        match self.c.weapon_hands.as_deref() {
            Some("Two-Hand") => weapon *= 1.0 + [0.0, 0.03, 0.06, 0.09][self.rank("105697") as usize],
            Some("One-Hand") | Some("Main Hand") => weapon *= 1.0 + [0.0, 0.03, 0.07, 0.10][self.rank("105629") as usize],
            _ => {}
        }
        let name = if bonus_ap != 0.0 { "Windfury Attack" } else if extra { extra_name } else { "Melee" };
        let landed = self.deal(name, weapon, false, true, self.c.hit_chance, 1.0, false, None, 0.0);
        if landed && !extra && self.raid_buffs.get("windfury_totem").copied().unwrap_or(false) && self.rng.random() < 0.20 {
            self.swing(true, 315.0, "Windfury Attack");
        }
        if landed {
            for effect in self.item_effects.clone() {
                let kind = effect["kind"].as_str().unwrap_or("");
                if ["extra_attack", "strength", "weapon_defense"].contains(&kind) && !(extra && kind == "extra_attack") {
                    let chance = effect.get("chance").and_then(|v| v.as_f64()).unwrap_or_else(|| obj_f(&effect, "ppm") * self.c.weapon_speed / 60.0);
                    if self.rng.random() < chance {
                        if kind == "extra_attack" { *self.casts.entry(effect["name"].as_str().unwrap_or("").into()).or_insert(0) += 1; self.swing(true, 0.0, effect["name"].as_str().unwrap_or("Hand of Justice")); }
                        else { self.activate_item(&effect); }
                    }
                }
            }
            if self.consumables.get("dragonbreath_chili").copied().unwrap_or(false) && self.rng.random() < 0.05 {
                let amt = self.rng.uniform(60.0, 90.0);
                self.deal("Dragonbreath Chili", amt, false, false, 1.0, 1.0, false, Some(false), 0.0);
            }
            if self.gear_main_hand == 19019 && self.rng.random() < self.m.thunderfury_proc_chance {
                self.deal("Thunderfury", self.m.thunderfury_damage, false, false, 1.0, self.m.thunderfury_threat_multiplier, false, Some(false), 0.0);
            }
            if self.time < self.seal_until {
                if let Some(seal) = self.seal {
                    self.seal_proc(seal, weapon, false);
                }
            }
            if let Some(echo) = self.echo {
                self.seal_proc(echo, weapon, true);
            }
        }
        self.echo = None;
        if !extra {
            let next = self.time + self.swing_delay();
            self.schedule(next, Kind::Swing);
        }
    }

    fn cast_seal(&mut self, seal: Seal) -> bool {
        let cost = self.f(seal.key(), "cost");
        if !self.spend(&format!("Seal of {}", title(seal.key())), cost) {
            return false;
        }
        if let Some(cur) = self.seal {
            if self.time < self.seal_until && cur != seal && self.rank("105692") != 0.0 {
                self.echo = Some(cur);
            }
        }
        self.seal = Some(seal);
        self.seal_until = self.time + self.f(seal.key(), "duration");
        self.gcd = self.time + self.f("righteousness", "gcd");
        true
    }

    fn decision(&mut self) {
        for effect in self.item_effects.clone() {
            let name = effect["name"].as_str().unwrap_or("");
            if effect["kind"] == "use" && self.time >= self.item_ready.get(name).copied().unwrap_or(0.0) && (obj_f(&effect, "shared_cooldown") == 0.0 || self.time >= self.item_ready.get("trinkets").copied().unwrap_or(0.0)) {
                self.activate_item(&effect); self.item_ready.insert(name.into(), self.time + obj_f(&effect, "cooldown"));
                if obj_f(&effect, "shared_cooldown") > 0.0 { self.item_ready.insert("trinkets".into(), self.time + obj_f(&effect, "shared_cooldown")); }
            }
        }
        if self.racial.active.as_ref().is_some_and(|r| r.name == "Stoneform") && self.e.incoming_enabled && self.time >= self.item_ready.get("Stoneform").copied().unwrap_or(0.0) && self.time >= self.gcd {
            self.activate_item(&json!({"name": "Stoneform", "duration": 8})); self.item_ready.insert("Stoneform".into(), self.time + 180.0); self.gcd = self.time + 1.5;
        }
        if self.rot.use_judgement && self.time >= self.cd("judgement") && self.time < self.seal_until {
            let cost = self.f("judgement", "base_mana_fraction") * self.c.base_mana;
            if self.spend("Judgement", cost) {
                let seal = self.seal.unwrap();
                let seal_bonus = 1.0 + 0.05 * self.rank("105334");
                let coeff = self.f(seal.key(), "judgement_pct_sp") * seal_bonus;
                let base = self.pt.fact_or(seal.key(), "judgement_base", 0.0) * seal_bonus;
                self.deal(&format!("Judgement of {}", title(seal.key())), base, true, true, self.c.spell_hit_chance, 1.0, false, None, coeff);
                if self.judgement_bonus_damage {
                    let bonus = self.rng.uniform(60.0, 66.0);
                    self.deal("Judgement Armor bonus", bonus, true, false, 1.0, 1.0, false, None, 0.0);
                }
                if self.eternal_justice_mana && self.rng.random() < 0.20 {
                    self.gain_mana(100.0);
                }
                // Judgement does not consume the active seal in Forever (classicwow.gg guide).
                let cd = self.f("judgement", "cooldown") - self.f("improved_judgement_rank1", "cooldown_reduction") * self.rank("105705");
                self.cd.insert("judgement", self.time + cd);
                let sj_rank = self.rank("105701");
                if sj_rank != 0.0 && self.rng.random() < (self.f("sanctified_judgement_rank1", "proc") * sj_rank).min(1.0) {
                    let refund = self.f(seal.key(), "cost") * self.f("sanctified_judgement_rank1", "seal_refund_fraction") * sj_rank;
                    self.gain_mana(refund);
                }
            }
        }
        if self.time + 1e-9 >= self.gcd {
            let mut acted = false;
            if self.prot && self.rank("105625") != 0.0 && self.rot.use_bulwark && self.time >= self.cd("bulwark").max(self.forbearance) && self.health / self.c.health <= self.rot.bulwark_health_threshold {
                let cost = self.f("bulwark", "cost");
                if self.spend("Templar's Bulwark", cost) {
                    self.absorb = self.c.health * self.f("bulwark", "health_fraction");
                    self.absorb_until = self.time + self.f("bulwark", "duration");
                    let v = self.time + self.f("bulwark", "cooldown") - 30.0 * self.rank("105632");
                    self.cd.insert("bulwark", v);
                    self.forbearance = self.time + self.f("bulwark", "forbearance");
                    acted = true;
                }
            }
            if !acted && self.prot && self.rank("105628") != 0.0 && self.time >= self.cd("holy_shield") {
                let cost = self.f("holy_shield", "cost");
                if self.spend("Holy Shield", cost) {
                    self.hs_until = self.time + self.f("holy_shield", "duration");
                    self.hs_charges = self.f("holy_shield", "charges") as i64;
                    let v = self.time + self.f("holy_shield", "cooldown");
                    self.cd.insert("holy_shield", v);
                    acted = true;
                }
            }
            let eligible_holy_target = self.e.boss_type == "demon" || self.e.boss_type == "undead";
            let conduit_discount = 1.0 - 0.20 * self.rank("105704");
            let purifying_cd = [1.0, 0.83, 0.67][self.rank("105327") as usize];
            if !acted && self.rot.use_hammer_of_wrath && self.time >= self.execute_at && self.time >= self.cd("hammer_of_wrath")
                && self.spend("Hammer of Wrath", self.m.hammer_of_wrath_cost) {
                    let amt = self.rng.uniform(self.m.hammer_of_wrath_min, self.m.hammer_of_wrath_max);
                    self.deal("Hammer of Wrath", amt, true, true, self.c.spell_hit_chance, 1.0, false, None, self.m.hammer_of_wrath_coeff);
                    let v = self.time + self.m.hammer_of_wrath_cooldown;
                    self.cd.insert("hammer_of_wrath", v);
                    acted = true;
                }
            if !acted && eligible_holy_target && self.rot.use_exorcism && self.time >= self.cd("exorcism")
                && self.spend("Exorcism", 345.0 * conduit_discount) {
                    let amt = self.rng.uniform(505.0, 563.0);
                    self.deal("Exorcism", amt, true, true, self.c.spell_hit_chance, 1.0, false, None, 0.429);
                    self.cd.insert("exorcism", self.time + 15.0 * purifying_cd);
                    acted = true;
                }
            if !acted && self.rot.use_holy_strike && self.time >= self.cd("holy_strike")
                && self.spend("Holy Strike", self.m.holy_strike_cost) {
                    let iron = self.rank("110879");
                    let arbiter = if self.rank("105700") != 0.0 { 1.1 } else { 1.0 };
                    let mut weapon = self.rng.uniform(self.c.weapon_min, self.c.weapon_max);
                    if self.m.use_classic_era_conversions { weapon += self.item_stat("attack_power") / 14.0 * if self.c.normalized_speed > 0.0 { self.c.normalized_speed } else { 2.4 }; }
                    let amount = (weapon * self.m.holy_strike_weapon_pct + self.rng.uniform(self.m.holy_strike_holy_min, self.m.holy_strike_holy_max)) * arbiter;
                    let landed = self.deal("Holy Strike", amount, true, true, self.c.hit_chance, 1.0 + 0.05 * iron, true, None, self.m.holy_strike_coeff);
                    if landed && iron != 0.0 {
                        self.iron_until = self.time + 6.0;
                    }
                    let v = self.time + (self.m.holy_strike_cooldown - self.rank("105328")).max(0.1);
                    self.cd.insert("holy_strike", v);
                    acted = true;
                }
            if !acted && eligible_holy_target && self.rot.use_holy_wrath && self.time >= self.cd("holy_wrath")
                && self.spend("Holy Wrath", 805.0 * conduit_discount) {
                    let amt = self.rng.uniform(490.0, 576.0);
                    self.deal("Holy Wrath", amt, true, true, self.c.spell_hit_chance, 1.0, false, None, 0.19);
                    self.cd.insert("holy_wrath", self.time + 60.0 * purifying_cd);
                    self.gcd = self.time + 2.0 / if self.raid_buffs.get("bloodlust").copied().unwrap_or(false) && self.time < 40.0 { 1.30 } else { 1.0 };
                    acted = true;
                }
            if !acted && self.rot.use_consecration && self.time >= self.cd("consecration") && self.mana / self.c.mana >= self.rot.consecration_mana_floor {
                let cost = self.f("consecration", "cost");
                if self.spend("Consecration", cost) {
                    let ticks = self.f("consecration", "ticks") as i64;
                    let dur = self.f("consecration", "duration");
                    for tick in 1..=ticks {
                        let at = self.time + tick as f64 * dur / ticks as f64;
                        self.schedule(at, Kind::Consecration);
                    }
                    let v = self.time + self.f("consecration", "cooldown");
                    self.cd.insert("consecration", v);
                    acted = true;
                }
            }
            if acted {
                self.gcd = self.gcd.max(self.time + 1.5);
            } else if self.time >= self.seal_until {
                let seal = if self.prot { Seal::Fury } else if self.rank("105696") == 0.0 { Seal::Righteousness } else { Seal::Command };
                self.cast_seal(seal);
            } else if self.rot.twist_seals && self.rank("105692") != 0.0 && self.echo.is_none() {
                let seal = if self.seal == Some(Seal::Command) { Seal::Righteousness } else { Seal::Command };
                self.cast_seal(seal);
            }
        }
        let next = ((self.time + 0.1) * 1e8).round() / 1e8;
        self.schedule(next, Kind::Decision);
    }

    fn enemy(&mut self) {
        let swing = self.e.enemy_swing / if self.debuffs.get("thunder_clap").copied().unwrap_or(false) { 0.8 } else { 1.0 };
        let next = self.time + swing;
        self.schedule(next, Kind::Enemy);
        let hs = self.hs_charges > 0 && self.time < self.hs_until;
        let red = self.red_charges > 0 && self.time < self.red_until;
        let defense_bonus = if self.m.use_classic_era_conversions { (self.item_stat("defense") - self.e.target_level * 5.0) * 0.0004 } else { 0.0 };
        let block = (self.c.block_chance + defense_bonus).max(0.0) + if hs && self.c.has_shield { self.f("holy_shield", "block_bonus") } else { 0.0 } + if red && self.c.has_shield { self.f("redoubt_rank1", "block_bonus") * self.rank("105626") } else { 0.0 };
        let miss_debuff = if self.debuffs.get("insect_swarm").copied().unwrap_or(false) { 0.02 } else { 0.0 } + if self.debuffs.get("scorpid_sting").copied().unwrap_or(false) { 0.05 } else { 0.0 };
        let roll = self.rng.random();
        let avoid = (self.c.avoidance + 0.01 * self.rank("105707") + miss_debuff + 3.0 * defense_bonus).clamp(0.0, 1.0);
        if roll < avoid {
            self.avoids += 1;
            self.record("Enemy avoided", 0.0);
            return;
        }
        let blocked = roll < (avoid + block).min(1.0);
        let crit_chance = (self.e.enemy_crit_chance - defense_bonus).max(0.0);
        let critical = !blocked && roll < (avoid + block + crit_chance).min(1.0);
        let mut crushing = false;
        if self.m.use_classic_era_conversions && !blocked && !critical && self.e.target_level - self.c.level >= 3.0 {
            crushing = roll < (avoid + block + crit_chance + 0.15).min(1.0);
        }
        let multiplier = if crushing { 1.5 } else if critical { self.e.enemy_crit_multiplier } else { 1.0 };
        let mut raw_damage = self.rng.uniform(self.e.enemy_damage_min, self.e.enemy_damage_max);
        if self.debuffs.get("demoralizing_shout").copied().unwrap_or(false) {
            raw_damage *= 0.90;
        }
        let mut mitigation = self.c.physical_mitigation;
        if self.m.use_classic_era_conversions { let armor = self.item_stat("armor"); mitigation = (armor / (armor + 400.0 + 85.0 * self.e.target_level)).min(0.75); }
        let mut amount = raw_damage * multiplier * (1.0 - mitigation);
        if self.item_until.get("Stoneform").copied().unwrap_or(0.0) > self.time { amount *= 0.90; }
        for effect in self.item_effects.clone() {
            if effect["kind"] == "incoming_flat" {
                if self.item_until.get(effect["name"].as_str().unwrap_or("")).copied().unwrap_or(0.0) > self.time { amount = (amount - obj_f(&effect, "value")).max(0.0); }
                if self.rng.random() < obj_f(&effect, "chance") { self.activate_item(&effect); }
            }
        }
        if blocked {
            self.blocks += 1;
            let ss_rank = self.rank("110874");
            let value = self.c.block_value * (1.0 + self.f("shield_specialization_rank1", "block_value_bonus") * ss_rank);
            let stopped = amount.min(value);
            self.blocked += stopped;
            amount -= stopped;
            if hs {
                self.hs_charges -= 1;
                let dmg = self.f("holy_shield", "damage");
                let tm = self.f("holy_shield", "threat_multiplier");
                self.deal("Holy Shield", dmg, true, false, 1.0, tm, false, None, 0.05);
            }
            if red {
                self.red_charges -= 1;
            }
            if ss_rank != 0.0 && self.time >= self.mana_icd && self.rng.random() < (self.f("shield_specialization_rank1", "mana_proc") * ss_rank).min(1.0) {
                let v = self.c.mana * self.f("shield_specialization_rank1", "mana_fraction");
                self.gain_mana(v);
                self.mana_icd = self.time + self.f("shield_specialization_rank1", "internal_cooldown");
            }
        }
        if self.prot && self.rank("105634") != 0.0 {
            amount *= 1.0 - self.f("improved_righteous_fury_rank1", "damage_reduction") * self.rank("105634");
        }
        if self.prot && self.time < self.iron_until {
            amount *= 1.0 - 0.02 * self.rank("110879");
        }
        let damaging = amount > 0.0;
        if self.time >= self.absorb_until {
            self.absorb = 0.0;
        }
        let pre_absorb = self.absorb;
        let absorbed = amount.min(self.absorb);
        self.absorb -= absorbed;
        self.absorbed += absorbed;
        amount -= absorbed;
        if pre_absorb > 0.0 && self.absorb <= 1e-9 && self.rank("110875") != 0.0 {
            let level_diff = (self.e.target_level - self.c.level).max(0.0);
            let pct = (self.f("improved_seal_of_fury_rank1", "per_level_pct") * level_diff).min(self.f("improved_seal_of_fury_rank1", "max_pct"));
            self.gain_mana(self.f("improved_seal_of_fury_rank1", "base_mana") * (1.0 + pct));
        }
        let source = if blocked { "Boss block" } else if critical { "Boss critical" } else if crushing { "Boss crushing" } else { "Boss melee" };
        self.health = (self.health - amount).max(0.0);
        self.taken += amount;
        *self.taken_by_source.entry(source.to_string()).or_insert(0.0) += amount;
        self.damage_window.push_back((self.time, amount));
        self.window_sum += amount;
        while let Some(&(t0, a0)) = self.damage_window.front() {
            if t0 <= self.time - 3.0 {
                self.window_sum -= a0;
                self.damage_window.pop_front();
            } else {
                break;
            }
        }
        self.peak_three_seconds = self.peak_three_seconds.max(self.window_sum);
        let label = format!("Enemy {}", if blocked { "block" } else if critical { "crit" } else if crushing { "crush" } else { "hit" });
        self.record(&label, amount);
        if self.health <= 0.0 {
            self.alive = false;
            self.life = self.time;
            self.record("Death", 0.0);
            return;
        }
        if damaging && self.rank("105626") != 0.0 && self.rng.random() < self.f("redoubt_rank1", "proc") {
            self.red_until = self.time + self.f("redoubt_rank1", "duration");
            self.red_charges = self.f("redoubt_rank1", "charges") as i64;
        }
        let reck_rank = self.rank("105627");
        if reck_rank != 0.0 {
            let block_hit = blocked && self.rng.random() < (self.f("reckoning_rank1", "block_proc") * reck_rank).min(1.0);
            let crit_hit = !block_hit && critical && self.rng.random() < (self.f("reckoning_rank1", "crit_proc") * reck_rank).min(1.0);
            if block_hit || crit_hit {
                self.swing(true, 0.0, "Reckoning");
            }
        }
    }

    pub fn run(mut self) -> FightResult {
        if self.prot {
            *self.casts.entry("Taunt".into()).or_insert(0) += 1;
            self.record("Cast Taunt", 0.0);
            self.schedule(1.5, Kind::Decision);
        } else {
            self.schedule(0.0, Kind::Decision);
        }
        let first_swing = self.swing_delay();
        self.schedule(first_swing, Kind::Swing);
        self.schedule(2.0, Kind::Mana);
        if self.consumables.get("goblin_sapper_charge").copied().unwrap_or(false) {
            let amt = self.rng.uniform(450.0, 750.0);
            self.deal("Goblin Sapper Charge", amt, false, false, 1.0, 1.0, false, Some(false), 0.0);
        }
        if self.e.incoming_enabled {
            let first = self.e.enemy_swing / if self.debuffs.get("thunder_clap").copied().unwrap_or(false) { 0.8 } else { 1.0 };
            for _ in 0..self.e.enemies {
                self.schedule(first, Kind::Enemy);
            }
            let hi = self.e.heal_interval;
            self.schedule(hi, Kind::Heal);
        }
        let mut previous = 0.0;
        let duration = self.duration;
        while self.alive {
            let Some(Reverse(ev)) = self.queue.pop() else { break };
            if ev.time >= duration {
                break;
            }
            self.time = ev.time;
            let mps = self.c.mana_per_second;
            self.gain_mana((ev.time - previous) * mps);
            previous = ev.time;
            match ev.kind {
                Kind::Decision => self.decision(),
                Kind::Swing => self.swing(false, 0.0, "Melee"),
                Kind::Consecration => {
                    let ticks = self.f("consecration", "ticks");
                    let aoe = self.e.targets;
                    let base_total = self.f("consecration", "total_damage");
                    let first4_total = self.f("consecration", "first4_total_damage");
                    let first4 = aoe.min(4.0);
                    let amt = (base_total * aoe + (first4_total - base_total) * first4) / ticks;
                    self.deal("Consecration", amt, true, false, 1.0, 1.0, false, None, 0.33 / ticks * aoe);
                }
                Kind::Mana => {
                    self.mana_tick();
                    self.schedule(ev.time + 2.0, Kind::Mana);
                }
                Kind::Enemy => self.enemy(),
                Kind::Heal => {
                    let amount = self.e.heal_amount.min(self.c.health - self.health);
                    self.health += amount;
                    self.healed += amount;
                    self.overheal += self.e.heal_amount - amount;
                    self.record("Healing", amount);
                    let hi = self.e.heal_interval;
                    self.schedule(ev.time + hi, Kind::Heal);
                }
            }
        }
        if self.alive {
            let mps = self.c.mana_per_second;
            self.gain_mana((duration - previous) * mps);
        }
        let total: f64 = self.damage.values().sum();
        FightResult {
            dps: total / duration,
            tps: self.threat / duration,
            dtps: self.taken / duration,
            alive_dtps: self.taken / self.life.max(0.001),
            survived: self.alive,
            alive_seconds: self.life,
            peak_3s_damage: self.peak_three_seconds,
            damage: self.damage,
            threat_by_source: self.threat_by_source,
            taken_by_source: self.taken_by_source,
            hits: self.hits,
            casts: self.casts,
            damage_taken: self.taken,
            absorbed: self.absorbed,
            blocked_damage: self.blocked,
            blocks: self.blocks,
            avoids: self.avoids,
            effective_healing: self.healed,
            overhealing: self.overheal,
            mana_spent: self.mana_spent,
            mana_gained: self.mana_gained,
            ending_mana: self.mana,
            first_unaffordable_cast: self.oom,
            log: self.log,
            duration,
        }
    }
}

// ---------------------------------------------------------------------------
// Driver
// ---------------------------------------------------------------------------

fn summarize(values: &[f64]) -> Value {
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.total_cmp(b));
    let n = sorted.len();
    let mean = fmean(&sorted);
    let se = if n > 1 { Some(stdev(&sorted) / (n as f64).sqrt()) } else { None };
    json!({"mean": mean, "p05": sorted[((n - 1) as f64 * 0.05) as usize], "p95": sorted[((n - 1) as f64 * 0.95) as usize],
        "mean_95ci_half_width": se.map(|s| json!(1.96 * s)).unwrap_or(Value::Null)})
}

pub struct Prepared {
    pub original: Value,
    pub effective: Value,
    pub gear_summary: Value,
}

pub fn prepare(profile: &Value, catalog: &Catalog) -> Result<Prepared, String> {
    let original = validate(profile)?;
    let (effective, gear_summary) = apply_gear(&original, catalog)?;
    Ok(Prepared { original, effective, gear_summary })
}

pub fn iteration_duration(p: &Value, i: i64) -> f64 {
    let seed = p["seed"].as_i64().unwrap_or(0) + i + 100000;
    let d = num(&p["duration"]);
    let v = num(&p["duration_variance"]);
    PyRandom::new(seed.unsigned_abs()).uniform(d - v, d + v).max(10.0)
}

pub fn run_range(prep: &Prepared, start: i64, end: i64) -> Result<Vec<FightResult>, String> {
    let p = &prep.effective;
    let seed = p["seed"].as_i64().unwrap_or(0);
    let mut rows = Vec::new();
    for i in start..end {
        let dur = iteration_duration(p, i);
        rows.push(Fight::new(p, dur, seed + i, i == 0)?.run());
    }
    Ok(rows)
}

pub fn finalize(prep: &Prepared, rows: &[FightResult]) -> Value {
    let pt = paladin_tables();
    let n = rows.len() as f64;
    let mut totals: IndexMap<String, f64> = IndexMap::new();
    let mut damage_totals: IndexMap<String, f64> = IndexMap::new();
    let mut threat_totals: IndexMap<String, f64> = IndexMap::new();
    let mut taken_totals: IndexMap<String, f64> = IndexMap::new();
    for row in rows {
        for (name, damage) in &row.damage {
            *totals.entry(name.clone()).or_insert(0.0) += damage / row.duration;
            *damage_totals.entry(name.clone()).or_insert(0.0) += damage;
        }
        for (name, threat) in &row.threat_by_source {
            *threat_totals.entry(name.clone()).or_insert(0.0) += threat / row.duration;
        }
        for (name, damage) in &row.taken_by_source {
            *taken_totals.entry(name.clone()).or_insert(0.0) += damage / row.duration;
        }
    }
    let sorted_avg = |m: &IndexMap<String, f64>| -> Map<String, Value> {
        let mut v: Vec<(&String, &f64)> = m.iter().collect();
        v.sort_by(|a, b| b.1.total_cmp(a.1));
        v.into_iter().map(|(k, x)| (k.clone(), json!(x / n))).collect()
    };
    let mut metrics = Map::new();
    for key in ["dps", "tps", "dtps", "alive_dtps", "alive_seconds", "peak_3s_damage", "ending_mana", "absorbed", "blocked_damage"] {
        let values: Vec<f64> = rows.iter().map(|r| match key {
            "dps" => r.dps, "tps" => r.tps, "dtps" => r.dtps, "alive_dtps" => r.alive_dtps, "alive_seconds" => r.alive_seconds,
            "peak_3s_damage" => r.peak_3s_damage, "ending_mana" => r.ending_mana, "absorbed" => r.absorbed, _ => r.blocked_damage,
        }).collect();
        metrics.insert(key.into(), summarize(&values));
    }
    metrics.insert("survival_fraction".into(), json!(rows.iter().filter(|r| r.survived).count() as f64 / n));
    metrics.insert("unaffordable_cast_fraction".into(), json!(rows.iter().filter(|r| r.first_unaffordable_cast.is_some()).count() as f64 / n));
    let mut assumptions = pt.assumptions.clone();
    assumptions.push("Rotation decisions are evaluated every 0.1 seconds; fixed-duration, single outgoing target.".into());
    let mut first = serde_json::to_value(&rows[0]).unwrap();
    if let Value::Object(m) = &mut first {
        m.remove("duration");
    }
    json!({"data_version": pt.version, "data_sha256": pt.data_sha256,
        "status": "EXPERIMENTAL — incomplete mechanics; not a validated Forever performance prediction",
        "profile": prep.original, "effective_character": prep.effective["character"], "gear_summary": prep.gear_summary, "metrics": metrics,
        "ability_dps": sorted_avg(&totals), "ability_damage": sorted_avg(&damage_totals), "ability_tps": sorted_avg(&threat_totals), "taken_dtps": sorted_avg(&taken_totals),
        "first_iteration": first, "sources": pt.sources,
        "assumptions": assumptions,
        "notes": ["DPS/TPS/DTPS divide by full fight duration, including time after death.",
                  "alive_dtps divides by time alive. Surviving time is censored at fight duration.",
                  "Confidence intervals cover random sampling only, not uncertainty in mechanics.",
                  "Independent seed per iteration; repeat the same profile and seed for identical results."],
        "engine": "rust-wasm"})
}

pub fn simulate(profile: &Value, catalog: &Catalog) -> Result<Value, String> {
    let prep = prepare(profile, catalog)?;
    let iterations = prep.effective["iterations"].as_i64().unwrap_or(1);
    let rows = run_range(&prep, 0, iterations)?;
    Ok(finalize(&prep, &rows))
}
