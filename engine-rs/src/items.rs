//! Item catalog records plus the item/enchant/set helpers from `engine.py`.

use crate::data::{tables, SetBonusDef, StatMap};
use indexmap::IndexMap;
use regex_lite::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

pub const WEAPON_TYPES: [&str; 7] = ["Axe", "Dagger", "Fist Weapon", "Mace", "Polearm", "Staff", "Sword"];
pub const RANGED_TYPES: [&str; 3] = ["Bow", "Gun", "Crossbow"];
pub const SPELL_SCHOOLS: [&str; 6] = ["fire", "frost", "arcane", "nature", "shadow", "holy"];

#[derive(Deserialize, Serialize, Clone, Debug, Default)]
pub struct ItemSet {
    pub name: String,
    #[serde(default)]
    pub bonuses: Vec<SetBonusDef>,
    #[serde(default)]
    pub pieces: Vec<String>,
    #[serde(flatten)]
    pub extra: IndexMap<String, Value>,
}

#[derive(Deserialize, Serialize, Clone, Debug, Default)]
#[allow(non_snake_case)]
pub struct Item {
    #[serde(default)]
    pub id: Option<i64>,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub slot: Option<String>,
    #[serde(default)]
    pub subclass: Option<String>,
    #[serde(default)]
    pub equipSlots: Vec<String>,
    #[serde(default)]
    pub stats: IndexMap<String, Value>,
    #[serde(default)]
    pub effects: Vec<String>,
    #[serde(default)]
    pub weaponDamageMin: Option<f64>,
    #[serde(default)]
    pub weaponDamageMax: Option<f64>,
    #[serde(default)]
    pub weaponSpeed: Option<f64>,
    #[serde(default)]
    pub set: Option<ItemSet>,
    #[serde(flatten)]
    pub extra: IndexMap<String, Value>,
}

impl Item {
    pub fn synthetic(name: &str, lo: f64, hi: f64, speed: f64, subclass: &str) -> Item {
        Item { name: name.to_string(), weaponDamageMin: Some(lo), weaponDamageMax: Some(hi), weaponSpeed: Some(speed), subclass: Some(subclass.to_string()), ..Default::default() }
    }
    pub fn subclass_str(&self) -> &str {
        self.subclass.as_deref().unwrap_or("")
    }
    pub fn slot_str(&self) -> &str {
        self.slot.as_deref().unwrap_or("")
    }
    /// Python truthiness of `item.get("weaponDamageMin")`.
    pub fn has_weapon_damage(&self) -> bool {
        matches!(self.weaponDamageMin, Some(v) if v != 0.0)
    }
    pub fn dmg_min(&self) -> f64 {
        self.weaponDamageMin.unwrap_or(0.0)
    }
    pub fn dmg_max(&self) -> f64 {
        self.weaponDamageMax.unwrap_or(0.0)
    }
    pub fn speed_or(&self, default: f64) -> f64 {
        self.weaponSpeed.unwrap_or(default)
    }
    pub fn is_empty(&self) -> bool {
        self.id.is_none() && self.name.is_empty() && self.weaponDamageMin.is_none()
    }
    /// Numeric stats with nulls treated as 0 (Python `(v or 0)`).
    pub fn stat_map(&self) -> StatMap {
        self.stats.iter().map(|(k, v)| (k.clone(), v.as_f64().unwrap_or(0.0))).collect()
    }
    pub fn has_stat(&self, key: &str) -> bool {
        self.stats.contains_key(key)
    }
    pub fn stat(&self, key: &str) -> f64 {
        self.stats.get(key).and_then(|v| v.as_f64()).unwrap_or(0.0)
    }
}

#[derive(Deserialize, Serialize, Clone, Debug, Default)]
pub struct Enchant {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub stats: IndexMap<String, Value>,
}

#[derive(Default)]
pub struct Catalog {
    pub items: HashMap<i64, Item>,
    pub enchants: IndexMap<String, Vec<Enchant>>,
    pub sets: IndexMap<String, crate::data::ForeverSet>,
}

impl Catalog {
    pub fn get(&self, id: i64) -> Item {
        self.items.get(&id).cloned().unwrap_or_default()
    }
}

pub fn weapon_type(item: &Item) -> Option<&'static str> {
    let kind = item.subclass_str();
    WEAPON_TYPES.iter().chain(RANGED_TYPES.iter()).chain(["Wand"].iter()).find(|&t| kind.contains(t)).map(|v| v as _)
}

pub fn normalized_speed(item: &Item) -> f64 {
    let kind = weapon_type(item);
    if kind == Some("Dagger") {
        return 1.7;
    }
    if matches!(kind, Some(k) if RANGED_TYPES.contains(&k)) {
        return 2.8;
    }
    if item.slot_str().contains("Two-Hand") || matches!(kind, Some("Polearm") | Some("Staff")) {
        return 3.3;
    }
    2.4
}

/// `re.search(pattern, text, re.I)` returning the capture groups.
pub fn re_search(pattern: &str, text: &str) -> Option<Vec<Option<String>>> {
    let re = Regex::new(&format!("(?i){pattern}")).expect("regex");
    re.captures(text).map(|c| (0..c.len()).map(|i| c.get(i).map(|m| m.as_str().to_string())).collect())
}

pub fn re_matches(pattern: &str, text: &str) -> bool {
    Regex::new(&format!("(?i){pattern}")).expect("regex").is_match(text)
}

pub fn cooldown_seconds(text: &str) -> f64 {
    match re_search(r"\((?:(\d+) Min(?:, (\d+) Sec)?|(\d+) Sec) Cooldown\)", text) {
        None => 120.0,
        Some(g) => {
            let n = |i: usize| g.get(i).cloned().flatten().and_then(|s| s.parse::<f64>().ok()).unwrap_or(0.0);
            let minutes = n(1);
            let secs = if g.get(2).cloned().flatten().is_some() { n(2) } else { n(3) };
            minutes * 60.0 + secs
        }
    }
}

pub fn proc_icd(text: &str) -> f64 {
    re_search(r"(?:can only|cannot) occur(?: more than)? once every (\d+) sec", text).and_then(|g| g[1].clone()).and_then(|s| s.parse().ok()).unwrap_or(0.0)
}

pub fn permanent_item_stats(item: &Item) -> StatMap {
    let mut stats = item.stat_map();
    for effect in &item.effects {
        if !effect.starts_with("Use:") {
            continue;
        }
        if re_matches(r"damage and healing.*?up to \d+ for \d+ sec", effect) {
            stats.shift_remove("spellPower");
        }
        if re_matches(r"Attack Power by \d+ for \d+ sec", effect) {
            stats.shift_remove("attackPower");
        }
        if re_matches(r"attack speed by \d+% for \d+ sec", effect) {
            for k in ["meleeHaste", "rangedHaste", "spellHaste"] {
                stats.shift_remove(k);
            }
        }
    }
    // The catalog importer copies some on-use values into permanent stats (Earthstrike's 280 AP).
    let uses = item.id.and_then(|id| crate::data::tables().ITEM_EFFECTS.get(&id.to_string())).and_then(|ov| ov.get("Use"));
    for use_ in uses.into_iter().flatten() {
        for key in ["stat", "stat2"] {
            if let Some(k) = use_.get(key).and_then(|v| v.as_str()) {
                stats.shift_remove(k);
            }
        }
    }
    stats
}

pub const SET_PATTERNS: [(&str, &str); 20] = [
    ("spellPower", r"damage and healing.*?up to (\d+)"),
    ("mp5", r"Restores (\d+) mana per 5 sec"),
    ("attackPower", r"\+(\d+) Attack Power"),
    ("attackPower", r"Increases Attack Power by (\d+)"),
    ("spellHit", r"hit with spells by (\d+)%"),
    ("agility", r"\+(\d+) Agility"),
    ("intellect", r"\+(\d+) Intellect"),
    ("strength", r"\+(\d+) Strength"),
    ("spirit", r"\+(\d+) Spirit"),
    ("dodge", r"dodge an attack by (\d+)%"),
    ("block", r"block attacks with a shield by (\d+)%"),
    ("spellCrit", r"critical strike with spells by (\d+)%"),
    ("meleeCrit", r"critical strike by (\d+)%"),
    ("meleeHit", r"chance to hit by (\d+)%"),
    ("blockValue", r"block value of your shield by (\d+)"),
    ("maxEnergy", r"maximum Energy by (\d+)"),
    ("armor", r"\+(\d+) Armor"),
    ("defense", r"Increased Defense \+(\d+)"),
    ("parry", r"parry an attack by (\d+)%"),
    ("stamina", r"\+(\d+) Stamina"),
];

#[derive(Serialize, Clone, Debug)]
pub struct ActiveSetBonus {
    pub set: String,
    pub pieces: i64,
    pub required: i64,
    pub description: String,
    pub stats: StatMap,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub effects: Option<IndexMap<String, f64>>,
    pub modeled: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub provisional: Option<String>,
}

pub fn apply_set_bonuses(gear: &[Item], stats: &mut StatMap, forever_sets: &IndexMap<String, crate::data::ForeverSet>) -> (IndexMap<String, i64>, Vec<ActiveSetBonus>, Vec<ActiveSetBonus>) {
    let mut counts: IndexMap<String, i64> = IndexMap::new();
    let mut definitions: IndexMap<String, Vec<SetBonusDef>> = IndexMap::new();
    for item in gear {
        if let Some(set) = &item.set {
            *counts.entry(set.name.clone()).or_insert(0) += 1;
            definitions.insert(set.name.clone(), set.bonuses.clone());
        }
    }
    let mut active = Vec::new();
    let mut unresolved = Vec::new();
    for (name, count) in &counts {
        let bonuses = forever_sets.get(name).map(|s| s.bonuses.clone()).unwrap_or_else(|| definitions[name].clone());
        for bonus in bonuses {
            if *count < bonus.required {
                continue;
            }
            let mut applied = StatMap::new();
            let conditional = re_search(r"chance on|chance to (?:gain|increase|grant|restore|trigger)|proc|for \d+ sec|when |whenever |after |stack", &bonus.description).is_some();
            if !conditional {
            for (key, value) in &bonus.stats {
                *stats.entry(key.clone()).or_insert(0.0) += value;
                applied.insert(key.clone(), *value);
            }
            }
            if applied.is_empty() && !conditional {
                for (key, pattern) in SET_PATTERNS {
                    if let Some(g) = re_search(pattern, &bonus.description) {
                        let value: f64 = g[1].clone().unwrap().parse().unwrap();
                        *stats.entry(key.to_string()).or_insert(0.0) += value;
                        applied.insert(key.to_string(), value);
                        break;
                    }
                }
            }
            let row = ActiveSetBonus { set: name.clone(), pieces: *count, required: bonus.required, description: bonus.description.clone(), stats: applied.clone(), effects: None, modeled: false, provisional: None };
            active.push(row.clone());
            if applied.is_empty() {
                unresolved.push(row);
            }
        }
    }
    (counts, active, unresolved)
}

/// A `gear_slots` request row.
#[derive(Deserialize, Clone, Debug)]
pub struct GearSlot {
    pub slot: Option<String>,
    pub id: Option<Value>,
}

impl GearSlot {
    pub fn id_digits(&self) -> Option<i64> {
        value_digits(self.id.as_ref()?)
    }
}

/// Python `str(x).isdigit()` followed by `int(x)`.
pub fn value_digits(v: &Value) -> Option<i64> {
    match v {
        Value::Number(n) => {
            let s = n.to_string();
            if s.chars().all(|c| c.is_ascii_digit()) { s.parse().ok() } else { None }
        }
        Value::String(s) => {
            if !s.is_empty() && s.chars().all(|c| c.is_ascii_digit()) { s.parse().ok() } else { None }
        }
        _ => None,
    }
}

pub fn enchant_compatible(slot: &str, gear: &[Item], gear_slots: &[GearSlot], catalog: &Catalog) -> bool {
    if !["main_hand", "off_hand", "ranged"].contains(&slot) {
        return true;
    }
    let ui_slot = match slot { "main_hand" => "Main Hand", "off_hand" => "Off Hand", _ => "Ranged / Relic" };
    let ids: Vec<i64> = gear_slots.iter().filter(|x| x.slot.as_deref() == Some(ui_slot)).filter_map(|x| x.id_digits()).collect();
    let candidates: Vec<Item> = if ids.is_empty() { gear.to_vec() } else { ids.iter().map(|i| catalog.get(*i)).collect() };
    if candidates.is_empty() {
        return true;
    }
    if slot == "ranged" {
        return candidates.iter().any(|x| x.subclass.as_deref() == Some("Gun"));
    }
    candidates.iter().any(|x| matches!(weapon_type(x), Some(k) if WEAPON_TYPES.contains(&k)))
}

pub fn item_allowed(item: &Item, slot: &str, class: &str, rules: &Value) -> bool {
    let contains = |v: &Value, s: &str| v.as_array().is_some_and(|a| a.iter().any(|x| x.as_str() == Some(s)));
    if item.id.is_none() || item.extra.get("simulationAvailability").and_then(|v| v.as_str()) == Some("excluded") { return false; }
    if !item.equipSlots.iter().any(|s| contains(&rules["slots"][slot], s)) { return false; }
    if item.extra.get("requiredLevel").and_then(|v| v.as_f64()).unwrap_or(0.0) > 60.0 { return false; }
    let sub = item.subclass_str();
    if let Some(index) = rules["armor_order"].as_array().and_then(|a| a.iter().position(|x| x.as_str() == Some(sub))) {
        if index as u64 > rules["armor_max"][class].as_u64().unwrap_or(0) { return false; }
    }
    if let Some(allowed) = item.extra.get("allowedClasses") { if allowed.as_array().is_some_and(|a| !a.is_empty()) && !contains(allowed, class) { return false; } }
    if let Some(rows) = item.extra.get("tooltip").and_then(|v| v.as_array()) {
        for row in rows { if let Some(text) = row["label"].as_str().and_then(|s| s.strip_prefix("Classes:")) { if !text.split(',').any(|s| s.trim() == class) { return false; } } }
    }
    let kind = rules["weapon_kinds"].as_array().and_then(|a| a.iter().filter_map(|x| x.as_str()).find(|s| sub.contains(s)));
    if let Some(kind) = kind {
        if !contains(&rules["class_weapons"][class], kind) { return false; }
        if slot == "Main Hand" && !contains(&rules["melee_weapons"], kind) { return false; }
        if slot == "Off Hand" && contains(&rules["melee_weapons"], kind) {
            return contains(&rules["dual_wield_classes"], class) && item.slot_str() != "Two-Hand";
        }
    } else if slot == "Main Hand" { return false; }
    true
}

/// `"%g" % value` for the small numbers used in proc notes.
pub fn fmt_g(v: f64) -> String {
    if v.fract() == 0.0 && v.abs() < 1e15 {
        format!("{}", v as i64)
    } else {
        format!("{v}")
    }
}

pub fn round_to(v: f64, digits: i32) -> f64 {
    let f = 10f64.powi(digits);
    (v * f).round() / f
}

/// Load a catalog from the same JSON documents the site serves.
pub fn load_catalog(items_json: &str, extra_json: &str, enchants_json: &str, sets_json: &str) -> Result<Catalog, String> {
    #[derive(Deserialize)]
    struct Items {
        items: Vec<Item>,
    }
    #[derive(Deserialize)]
    struct Enchants {
        slots: IndexMap<String, Vec<Enchant>>,
    }
    #[derive(Deserialize)]
    struct Sets {
        sets: IndexMap<String, crate::data::ForeverSet>,
    }
    let items: Items = serde_json::from_str(items_json).map_err(|e| format!("items: {e}"))?;
    let extra: Items = if extra_json.trim().is_empty() { Items { items: vec![] } } else { serde_json::from_str(extra_json).map_err(|e| format!("extra items: {e}"))? };
    let enchants: Enchants = serde_json::from_str(enchants_json).map_err(|e| format!("enchants: {e}"))?;
    let sets: Sets = serde_json::from_str(sets_json).map_err(|e| format!("sets: {e}"))?;
    let mut map = HashMap::new();
    for it in items.items.into_iter().chain(extra.items) {
        if let Some(id) = it.id {
            map.insert(id, it);
        }
    }
    let _ = tables();
    Ok(Catalog { items: map, enchants: enchants.slots, sets: sets.sets })
}
