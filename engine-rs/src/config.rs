//! Static per-request state shared by every iteration (port of `engine.Config`).

use crate::data::{tables, Ability, ItemUse, Racial, Spec, StatMap, Tables};
use crate::items::*;
use indexmap::IndexMap;
use serde::Serialize;
use serde_json::{json, Map, Value};
use std::collections::{BTreeSet, HashMap, HashSet};

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Hand {
    Main,
    Off,
    Ranged,
    None,
}

#[derive(Clone, Debug)]
pub enum Cond {
    True,
    False,
    Or(Vec<Cond>),
    And(Vec<Cond>),
    Not(Box<Cond>),
    Execute,
    Moving,
    DotMissing,
    BuffMissing,
    NoDagger,
    NoShred,
    Targets(String, f64),
    Resource(String, String, f64),
    Keyed(String, String, String, f64),
}

fn parse_cmp(op: &str) -> Option<&'static str> {
    match op { "<" => Some("<"), ">" => Some(">"), "<=" => Some("<="), ">=" => Some(">="), "==" => Some("=="), _ => None }
}

pub fn parse_cond(cond: &str) -> Result<Cond, String> {
    let cond = cond.trim();
    if cond == "true" {
        return Ok(Cond::True);
    }
    if cond == "false" {
        return Ok(Cond::False);
    }
    if cond.contains(" or ") {
        return Ok(Cond::Or(cond.split(" or ").map(parse_cond).collect::<Result<_, _>>()?));
    }
    if cond.contains(" and ") {
        return Ok(Cond::And(cond.split(" and ").map(parse_cond).collect::<Result<_, _>>()?));
    }
    if let Some(rest) = cond.strip_prefix("not ") {
        return Ok(Cond::Not(Box::new(parse_cond(rest)?)));
    }
    match cond {
        "execute" => return Ok(Cond::Execute),
        "moving" => return Ok(Cond::Moving),
        "dot_missing" => return Ok(Cond::DotMissing),
        "buff_missing" => return Ok(Cond::BuffMissing),
        "no_dagger" => return Ok(Cond::NoDagger),
        "no_shred" => return Ok(Cond::NoShred),
        _ => {}
    }
    let re = regex_lite::Regex::new(r"^targets\s*(<=|>=|<|>|==)\s*(\d+)").unwrap();
    if let Some(c) = re.captures(cond) {
        return Ok(Cond::Targets(parse_cmp(&c[1]).unwrap().to_string(), c[2].parse().unwrap()));
    }
    let re = regex_lite::Regex::new(r"^(rage|energy|mana|cp)\s*(<=|>=|<|>|==)\s*(\d+)").unwrap();
    if let Some(c) = re.captures(cond) {
        return Ok(Cond::Resource(c[1].to_string(), parse_cmp(&c[2]).unwrap().to_string(), c[3].parse().unwrap()));
    }
    let re = regex_lite::Regex::new(r"^(dot|debuff|cd|buffstacks|buff|stacks):(.+?)\s*(<=|>=|<|>|==)\s*(\d+)").unwrap();
    if let Some(c) = re.captures(cond) {
        return Ok(Cond::Keyed(c[1].to_string(), c[2].to_string(), parse_cmp(&c[3]).unwrap().to_string(), c[4].parse().unwrap()));
    }
    Err(format!("Unknown rotation condition: {cond}"))
}

pub fn compare(op: &str, val: f64, num: f64) -> bool {
    match op { "<" => val < num, ">" => val > num, "<=" => val <= num, ">=" => val >= num, _ => val == num }
}

#[derive(Clone, Debug, Serialize)]
pub struct ItemProc {
    pub name: String,
    pub trigger: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chance: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ppm: Option<f64>,
    #[serde(default)]
    pub icd: f64,
    pub kind: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub amount: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub school: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stat: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration: Option<f64>,
    /// Identity of the source item (None for procs attached to non-weapon "Equip:" effects).
    #[serde(skip)]
    pub item_id: Option<i64>,
    #[serde(skip)]
    pub item_index: Option<usize>,
}

#[derive(Clone, Debug)]
pub struct HunterPet {
    pub family: String,
    pub damage: f64,
    pub special: Option<String>,
    pub dump: Option<String>,
    pub speed: f64,
    pub uptime: f64,
    pub abilities: BTreeSet<String>,
}

#[derive(Clone, Debug)]
pub struct WarlockPetCfg {
    pub family: String,
    pub cfg: crate::data::WarlockPet,
    pub uptime: f64,
    pub abilities: BTreeSet<String>,
}

#[derive(Clone, Debug)]
pub enum Pet {
    Hunter(HunterPet),
    Warlock(WarlockPetCfg),
}

impl Pet {
    pub fn family(&self) -> &str {
        match self { Pet::Hunter(p) => &p.family, Pet::Warlock(p) => &p.family }
    }
}

#[derive(Serialize, Clone, Debug)]
pub struct AppliedEnchant {
    pub slot: String,
    pub id: String,
    pub name: String,
}

#[derive(Serialize, Clone, Debug)]
pub struct RejectedEnchant {
    pub slot: String,
    pub id: String,
    pub reason: String,
}

pub struct Config {
    pub t: &'static Tables,
    pub request: Value,
    pub spec: Spec,
    pub duration: f64,
    pub variance: f64,
    pub iterations: i64,
    pub seed: i64,
    pub race: String,
    pub boss_type: String,
    pub targets: i64,
    pub racial_enabled: bool,
    pub racial: Racial,
    pub gear: Vec<Item>,
    pub gear_slots: Vec<GearSlot>,
    pub buffs: BTreeSet<String>,
    pub debuffs: BTreeSet<String>,
    pub consumes: BTreeSet<String>,
    pub notes: Vec<String>,
    pub talents: IndexMap<String, i64>,
    pub talent_points: i64,
    pub mods: IndexMap<String, f64>,
    pub mh: Item,
    pub oh: Item,
    pub ranged: Item,
    pub has_shield: bool,
    pub two_hand: bool,
    pub dual_wield: bool,
    pub weapon_skill_bonus: IndexMap<String, i64>,
    pub stats: StatMap,
    pub item_uses: Vec<ItemUse>,
    pub item_procs: Vec<ItemProc>,
    pub item_effects_applied: Vec<Value>,
    pub item_effects_unresolved: Vec<Value>,
    pub set_counts: IndexMap<String, i64>,
    pub active_set_bonuses: Vec<ActiveSetBonus>,
    pub unresolved_set_bonuses: Vec<ActiveSetBonus>,
    pub applied_enchants: Vec<AppliedEnchant>,
    pub rejected_enchants: Vec<RejectedEnchant>,
    pub crusader_hands: HashSet<String>,
    pub windfury_totem: bool,
    pub racial_crit: f64,
    pub threat_reduction: f64,
    pub rotation: Vec<(String, String)>,
    pub rotation_conds: Vec<(String, Cond)>,
    /// Last condition per rotation name (Python `dict(c.rotation)`).
    pub rotation_last: HashMap<String, Cond>,
    pub actions: IndexMap<String, Ability>,
    pub action_names: Vec<String>,
    pub pet: Option<Pet>,
}

fn req_f64(v: Option<&Value>, default: f64) -> Result<f64, String> {
    match v {
        None | Some(Value::Null) => Ok(default),
        Some(Value::Number(n)) => Ok(n.as_f64().unwrap()),
        Some(Value::Bool(b)) => Ok(if *b { 1.0 } else { 0.0 }),
        Some(Value::String(s)) => s.trim().parse::<f64>().map_err(|_| format!("could not convert string to float: '{s}'")),
        Some(other) => Err(format!("float() argument must be a string or a real number, not '{}'", type_name(other))),
    }
}

fn req_i64(v: Option<&Value>, default: i64) -> Result<i64, String> {
    match v {
        None | Some(Value::Null) => Ok(default),
        Some(Value::Number(n)) => n.as_i64().or_else(|| n.as_f64().map(|f| f.trunc() as i64)).ok_or_else(|| "invalid integer".into()),
        Some(Value::Bool(b)) => Ok(*b as i64),
        Some(Value::String(s)) => s.trim().parse::<i64>().map_err(|_| format!("invalid literal for int() with base 10: '{s}'")),
        Some(other) => Err(format!("int() argument must be a string, a bytes-like object or a real number, not '{}'", type_name(other))),
    }
}

fn type_name(v: &Value) -> &'static str {
    match v { Value::Null => "NoneType", Value::Bool(_) => "bool", Value::Number(_) => "float", Value::String(_) => "str", Value::Array(_) => "list", Value::Object(_) => "dict" }
}

fn req_str(v: Option<&Value>, default: &str) -> String {
    match v {
        None | Some(Value::Null) => default.to_string(),
        Some(Value::String(s)) => s.clone(),
        Some(Value::Bool(b)) => if *b { "True".into() } else { "False".into() },
        Some(other) => other.to_string(),
    }
}

fn req_bool(v: Option<&Value>, default: bool) -> bool {
    match v {
        None => default,
        Some(Value::Null) => false,
        Some(Value::Bool(b)) => *b,
        Some(Value::Number(n)) => n.as_f64().unwrap_or(0.0) != 0.0,
        Some(Value::String(s)) => !s.is_empty(),
        Some(Value::Array(a)) => !a.is_empty(),
        Some(Value::Object(o)) => !o.is_empty(),
    }
}

fn str_set(v: Option<&Value>) -> BTreeSet<String> {
    v.and_then(|x| x.as_array()).map(|a| a.iter().map(|x| req_str(Some(x), "")).collect()).unwrap_or_default()
}

fn add(map: &mut StatMap, key: &str, v: f64) {
    *map.entry(key.to_string()).or_insert(0.0) += v;
}

impl Config {
    pub fn new(request: Value, catalog: &Catalog) -> Result<Config, String> {
        let t = tables();
        let spec_id = req_str(request.get("spec"), "");
        let spec = t.SPEC_MAP.get(&spec_id).cloned().ok_or("Choose a supported Forever DPS or tank spec.")?;
        let duration = req_f64(request.get("duration"), 120.0)?;
        let variance = req_f64(request.get("duration_variance"), 0.0)?.clamp(0.0, 60.0);
        let iterations = req_i64(request.get("iterations"), 300)?;
        let seed = req_i64(request.get("seed"), 42)?;
        if !(10.0..=1800.0).contains(&duration) || !(1..=10000).contains(&iterations) {
            return Err("Duration must be 10-1800 seconds and iterations 1-10000.".into());
        }
        if duration * iterations as f64 > 400_000.0 {
            return Err("Run too large; keep duration x iterations at or below 400,000 seconds.".into());
        }
        let races = &t.CLASS_RACES[&spec.class_name];
        let race = req_str(request.get("race"), &races[0]);
        if !races.contains(&race) {
            return Err(format!("{race} cannot be a {} in World of Warcraft: Forever.", spec.class_name));
        }
        let boss_type = req_str(request.get("boss_type"), "none").to_lowercase();
        if !t.CREATURE_TYPES.contains(&boss_type) {
            return Err("Choose a supported boss creature type.".into());
        }
        let targets = req_i64(request.get("targets"), 1)?.clamp(1, 10);
        let racial_enabled = req_bool(request.get("racial_enabled"), true);
        let racial = t.RACIALS.get(&race).cloned().unwrap_or_default();
        let gear: Vec<Item> = request.get("gear").and_then(|g| g.as_array()).map(|a| a.iter().filter_map(value_digits).map(|id| catalog.get(id)).collect()).unwrap_or_default();
        let gear_slots: Vec<GearSlot> = request.get("gear_slots").and_then(|g| g.as_array()).map(|a| a.iter().filter(|x| x.is_object()).filter_map(|x| serde_json::from_value(x.clone()).ok()).collect()).unwrap_or_default();
        let buffs = str_set(request.get("buffs"));
        let debuffs = str_set(request.get("debuffs"));
        let consumes = Self::validate_consumes(t, str_set(request.get("consumables")))?;
        let mut c = Config {
            t, request, spec, duration, variance, iterations, seed, race, boss_type, targets, racial_enabled, racial, gear, gear_slots, buffs, debuffs, consumes,
            notes: vec![], talents: IndexMap::new(), talent_points: 0, mods: IndexMap::new(), mh: Item::default(), oh: Item::default(), ranged: Item::default(), has_shield: false, two_hand: false, dual_wield: false,
            weapon_skill_bonus: IndexMap::new(), stats: StatMap::new(), item_uses: vec![], item_procs: vec![], item_effects_applied: vec![], item_effects_unresolved: vec![], set_counts: IndexMap::new(),
            active_set_bonuses: vec![], unresolved_set_bonuses: vec![], applied_enchants: vec![], rejected_enchants: vec![], crusader_hands: HashSet::new(), windfury_totem: false, racial_crit: 0.0, threat_reduction: 0.0,
            rotation: vec![], rotation_conds: vec![], rotation_last: HashMap::new(), actions: IndexMap::new(), action_names: vec![], pet: None,
        };
        c.init_talents()?;
        c.init_weapons(catalog);
        c.init_stats(catalog);
        c.init_abilities()?;
        c.init_pets()?;
        Ok(c)
    }

    fn validate_consumes(t: &Tables, consumes: BTreeSet<String>) -> Result<BTreeSet<String>, String> {
        let mut groups: HashMap<&str, &str> = HashMap::new();
        for key in &consumes {
            if let Some(group) = t.CONSUMABLE_GROUPS.get(key) {
                if let Some(prev) = groups.get(group.as_str()) {
                    return Err(format!("{key} cannot be combined with {prev} ({} group)", group.replace('_', " ")));
                }
                groups.insert(group, key);
            }
        }
        Ok(consumes)
    }

    // ---- talents ---------------------------------------------------------
    fn init_talents(&mut self) -> Result<(), String> {
        let t = self.t;
        let mut talents = IndexMap::new();
        if let Some(Value::Object(map)) = self.request.get("talents") {
            for (k, v) in map {
                let rank = req_i64(Some(v), 0)?;
                if rank > 0 {
                    talents.insert(k.clone(), rank);
                }
            }
        } else {
            talents = t.DEFAULT_BUILDS[&self.spec.id].clone();
        }
        self.talent_points = talents.values().sum();
        let mut mods: IndexMap<String, f64> = IndexMap::new();
        for (tid, rank) in &talents {
            if let Some(effects) = t.TALENT_EFFECTS.get(tid) {
                for (key, per_rank) in effects {
                    *mods.entry(key.clone()).or_insert(0.0) += per_rank * *rank as f64;
                }
            }
        }
        self.talents = talents;
        self.mods = mods;
        Ok(())
    }

    pub fn mod_(&self, key: &str) -> f64 {
        self.mods.get(key).copied().unwrap_or(0.0)
    }

    pub fn flag(&self, name: &str) -> f64 {
        self.mods.get(&format!("flag:{name}")).copied().unwrap_or(0.0)
    }

    // ---- weapons ---------------------------------------------------------
    fn slot_item(&self, catalog: &Catalog, ui_slot: &str, wanted: &[&str], exclude: Option<i64>) -> Item {
        for row in &self.gear_slots {
            if row.slot.as_deref() == Some(ui_slot) {
                if let Some(id) = row.id_digits() {
                    return catalog.get(id);
                }
            }
        }
        let fits = |x: &Item| -> bool {
            if x.equipSlots.iter().any(|s| wanted.contains(&s.as_str())) {
                return true;
            }
            if ui_slot == "Main Hand" {
                return matches!(x.slot.as_deref(), Some("Main Hand") | Some("One-Hand") | Some("Two-Hand")) && x.has_weapon_damage();
            }
            if ui_slot == "Off Hand" {
                return matches!(x.slot.as_deref(), Some("Off Hand") | Some("One-Hand") | Some("Held In Off-hand") | Some("Shield")) || x.subclass_str().contains("Shield");
            }
            false
        };
        for x in &self.gear {
            // Python excludes by object identity; catalog items are shared objects, so same id == same object.
            if exclude.is_some() && x.id.is_some() && x.id == exclude {
                continue;
            }
            if fits(x) {
                return x.clone();
            }
        }
        Item::default()
    }

    fn init_weapons(&mut self, catalog: &Catalog) {
        let mh = self.slot_item(catalog, "Main Hand", &["main_hand"], None);
        let oh = self.slot_item(catalog, "Off Hand", &["off_hand"], mh.id);
        let rw = self.slot_item(catalog, "Ranged / Relic", &["ranged"], None);
        self.has_shield = oh.subclass_str().contains("Shield") || oh.slot.as_deref() == Some("Shield");
        let mut mh = mh;
        if !mh.has_weapon_damage() {
            mh = Item::synthetic("Unarmed", 1.0, 2.0, 2.0, "Fist Weapon");
            if !(self.spec.form_is("cat") || self.spec.form_is("bear")) {
                self.notes.push("No main-hand weapon equipped; unarmed 1-2 damage at 2.0 speed used.".into());
            }
        }
        self.two_hand = mh.slot_str().contains("Two-Hand");
        let mut oh = oh;
        if self.two_hand && oh.has_weapon_damage() {
            oh = Item::default();
        }
        self.mh = mh;
        self.oh = if oh.has_weapon_damage() && matches!(weapon_type(&oh), Some(k) if WEAPON_TYPES.contains(&k)) { oh } else { Item::default() };
        self.ranged = rw.clone();
        if self.spec.form_is("cat") {
            self.mh = Item::synthetic("Cat Form", 43.84, 65.76, 1.0, "Form");
            self.oh = Item::default();
        } else if self.spec.form_is("bear") {
            self.mh = Item::synthetic("Dire Bear Form", 109.0, 165.0, 2.5, "Form");
            self.oh = Item::default();
        }
        if self.spec.style == "ranged" && !rw.has_weapon_damage() {
            self.ranged = Item::synthetic("No ranged weapon", 1.0, 2.0, 2.8, "Bow");
            self.notes.push("No bow, gun or crossbow equipped; a 1-2 damage 2.8 speed placeholder is used.".into());
        }
        self.dual_wield = !self.oh.is_empty();
        let mut skills: IndexMap<String, i64> = IndexMap::new();
        let splitter = regex_lite::Regex::new(r", and |, | and ").unwrap();
        for item in &self.gear {
            for effect in &item.effects {
                if let Some(g) = re_search(r"Increased (.+?) \+(\d+)", effect) {
                    let amount: i64 = g[2].clone().unwrap().parse().unwrap();
                    for kind in splitter.split(g[1].as_deref().unwrap()) {
                        let stripped = kind.trim();
                        let key = stripped.trim_end_matches('s').replace("Two-handed", "Two-Hand");
                        let prev = skills.get(stripped).copied().unwrap_or(0);
                        skills.insert(key, prev + amount);
                    }
                }
            }
        }
        self.weapon_skill_bonus = skills;
    }

    pub fn skill(&self, item: &Item) -> f64 {
        let kind = weapon_type(item).unwrap_or("");
        let base = self.t.LEVEL * 5.0;
        let key = format!("{}{}", if item.slot_str().contains("Two-Hand") { "Two-Hand " } else { "" }, kind);
        let g = |k: &str| self.weapon_skill_bonus.get(k).copied().unwrap_or(0);
        let mut bonus = g(&key);
        if bonus == 0 {
            bonus = g(kind);
        }
        if bonus == 0 {
            bonus = g(&format!("{kind}s"));
        }
        base + bonus as f64 + self.mod_(&format!("skill:{kind}"))
    }

    pub fn hand_item(&self, hand: Hand) -> Option<&Item> {
        match hand { Hand::Main => Some(&self.mh), Hand::Off => Some(&self.oh), Hand::Ranged => Some(&self.ranged), Hand::None => None }
    }

    // ---- stats -----------------------------------------------------------
    fn init_stats(&mut self, catalog: &Catalog) {
        let t = self.t;
        let cls = self.spec.class_name.clone();
        let mut st: StatMap = t.CLASS_BASE[&cls].clone();
        if let Some(rs) = t.RACE_STATS.get(&self.race) {
            for (k, v) in rs {
                add(&mut st, k, *v);
            }
        }
        let mut gear_stats = StatMap::new();
        let gear = self.gear.clone();
        for (idx, item) in gear.iter().enumerate() {
            for (k, v) in permanent_item_stats(item) {
                add(&mut gear_stats, &k, v);
            }
            for effect in &item.effects {
                self.item_effect(item, idx, effect, &mut gear_stats);
            }
        }
        let (counts, mut active, _unresolved) = apply_set_bonuses(&self.gear, &mut gear_stats, &catalog.sets);
        for row in active.iter_mut() {
            let key = format!("{}|{}", row.set, row.required);
            if let Some(effects) = t.SET_EFFECTS.get(&key) {
                for (k, v) in effects {
                    *self.mods.entry(k.clone()).or_insert(0.0) += v;
                }
                row.effects = Some(effects.clone());
            }
            row.modeled = !row.stats.is_empty() || row.effects.is_some() || t.SET_NO_COMBAT_EFFECT.contains(&key);
            if let Some(p) = t.SET_PROVISIONAL.get(&key) {
                row.provisional = Some(p.clone());
                self.notes.push(format!("{} ({}): {}", row.set, row.required, p));
            }
        }
        self.unresolved_set_bonuses = active.iter().filter(|r| !r.modeled).cloned().collect();
        self.set_counts = counts;
        self.active_set_bonuses = active;
        let primary = if self.spec.style == "spell" { "intellect" } else if ["Rogue", "Hunter", "Druid"].contains(&cls.as_str()) { "agility" } else { "strength" };
        if let Some(Value::Array(sels)) = self.request.get("enchants") {
            for sel in sels {
                let Value::Object(sel) = sel else { continue };
                let slot = req_str(sel.get("slot"), "");
                let id = req_str(sel.get("id"), "");
                let Some(e) = catalog.enchants.get(&slot).and_then(|rows| rows.iter().find(|e| e.id == id)) else { continue };
                if !enchant_compatible(&slot, &self.gear, &self.gear_slots, catalog) {
                    self.rejected_enchants.push(RejectedEnchant { slot, id: e.id.clone(), reason: "incompatible item type".into() });
                    continue;
                }
                self.applied_enchants.push(AppliedEnchant { slot: slot.clone(), id: e.id.clone(), name: e.name.clone() });
                for (k, v) in &e.stats {
                    let key = if k == "primary" { primary } else { k.as_str() };
                    add(&mut gear_stats, key, v.as_f64().unwrap_or(0.0));
                }
                if e.id == "crusader" && self.spec.style == "melee" {
                    self.crusader_hands.insert(slot);
                }
            }
        }
        for (k, v) in &gear_stats {
            add(&mut st, k, *v);
        }
        for key in &self.buffs {
            if let Some(b) = t.BUFF_STATS.get(key) {
                for (k, v) in b {
                    add(&mut st, k, *v);
                }
            }
        }
        for key in &self.consumes {
            if let Some(b) = t.CONSUME_STATS.get(key) {
                for (k, v) in b {
                    add(&mut st, k, *v);
                }
            }
        }
        if self.buffs.contains("battle_shout") && self.mod_("buff_ap:battle_shout") != 0.0 {
            add(&mut st, "attackPower", self.mod_("buff_ap:battle_shout"));
        }
        if self.buffs.contains("mana_spring") && self.mod_("buff_pct:mana_spring") != 0.0 {
            let base = t.BUFF_STATS["mana_spring"]["mp5"];
            add(&mut st, "mp5", base * self.mod_("buff_pct:mana_spring"));
        }
        if self.buffs.contains("blessing_of_kings") {
            for stat in ["strength", "agility", "stamina", "intellect", "spirit"] {
                let v = st.get(stat).copied().unwrap_or(0.0) * 1.10;
                st.insert(stat.into(), v);
            }
        }
        self.windfury_totem = self.buffs.contains("windfury_totem") && self.spec.style == "melee" && self.spec.form.is_none() && cls != "Shaman";
        for stat in ["strength", "agility", "stamina", "intellect", "spirit", "armor", "mana"] {
            let pct = self.mod_(&format!("stat_pct:{stat}"));
            if pct != 0.0 {
                let v = st.get(stat).copied().unwrap_or(0.0) * (1.0 + pct);
                st.insert(stat.into(), v);
            }
        }
        if self.spec.form_is("cat") {
            st["strength"] *= 1.0 + self.flag("hotw_cat_str");
        }
        if self.spec.form_is("bear") {
            st["stamina"] *= (1.0 + self.flag("hotw_bear_sta")) * 1.25;
            let v = st.get("armor").copied().unwrap_or(0.0) * 4.6;
            st.insert("armor".into(), v);
        }
        if self.spec.form_is("moonkin") {
            let v = st.get("armor").copied().unwrap_or(0.0) * 4.6;
            st.insert("armor".into(), v);
        }
        if self.flag("thick_hide") != 0.0 {
            let v = st.get("armor").copied().unwrap_or(0.0) + 3.0 * t.LEVEL * (self.flag("thick_hide") / 3.0);
            st.insert("armor".into(), v);
        }
        if self.racial.health_pct != 0.0 {
            st.insert("health_pct".into(), self.racial.health_pct);
        }
        let g = |st: &StatMap, k: &str| st.get(k).copied().unwrap_or(0.0);
        let v = g(&st, "attackPower") + st["strength"] * t.AP_PER_STRENGTH[&cls] + st["agility"] * t.AP_PER_AGILITY[&cls] + st["intellect"] * self.mod_("ap_from_int") + self.flag("predatory_strikes");
        st.insert("attackPower".into(), v);
        let melee_only_ap: f64 = self.buffs.iter().map(|k| t.BUFF_STATS.get(k).and_then(|m| m.get("attackPower")).copied().unwrap_or(0.0)).sum::<f64>()
            + self.consumes.iter().map(|k| t.CONSUME_STATS.get(k).and_then(|m| m.get("attackPower")).copied().unwrap_or(0.0)).sum::<f64>();
        let hunter = cls == "Hunter";
        let v = g(&st, "rangedAttackPower") + (g(&st, "attackPower") - melee_only_ap) + st["agility"] * 2.0 * (hunter as i32 as f64) + if hunter { 120.0 * (1.0 + self.mod_("hawk_pct")) } else { 0.0 };
        st.insert("rangedAttackPower".into(), v);
        let dk = if cls == "Warlock" && req_str(self.request.get("pet_family"), "succubus") != "none" { self.flag("demonic_knowledge") } else { 0.0 };
        let v = g(&st, "spellPower") + st["intellect"] * self.mod_("sp_from_int") + st["spirit"] * self.flag("spiritual_guidance") + dk;
        st.insert("spellPower".into(), v);
        let v = g(&st, "meleeCrit") + st["agility"] * t.MELEE_CRIT_PER_AGI[&cls] + self.mod_("melee_crit");
        st.insert("meleeCrit".into(), v);
        let v = g(&st, "rangedCrit") + st["agility"] * t.MELEE_CRIT_PER_AGI[&cls] + self.mod_("melee_crit") + self.mod_("ranged_crit");
        st.insert("rangedCrit".into(), v);
        let v = g(&st, "spellCrit") + st["intellect"] * t.SPELL_CRIT_PER_INT[&cls] + self.mod_("spell_crit");
        st.insert("spellCrit".into(), v);
        let v = g(&st, "meleeHit") + self.mod_("hit") + self.racial.hit;
        st.insert("meleeHit".into(), v);
        let v = g(&st, "rangedHit") + g(&st, "meleeHit") - (self.mod_("hit") + self.racial.hit) + self.mod_("hit") + self.mod_("ranged_hit") + self.racial.hit;
        st.insert("rangedHit".into(), v);
        let v = g(&st, "spellHit") + self.mod_("spell_hit") + self.racial.hit;
        st.insert("spellHit".into(), v);
        let v = g(&st, "dodge") + st["agility"] * t.DODGE_PER_AGI[&cls] + self.mod_("dodge") + self.racial.dodge;
        st.insert("dodge".into(), v);
        let v = if ["Warrior", "Paladin", "Rogue", "Hunter", "Shaman"].contains(&cls.as_str()) { 5.0 } else { 0.0 } + g(&st, "parry");
        st.insert("parry".into(), v);
        let v = if self.has_shield { 5.0 + g(&st, "block") + self.mod_("block") } else { 0.0 };
        st.insert("block".into(), v);
        let v = 300.0 + g(&st, "defense") + self.mod_("defense");
        st.insert("defense".into(), v);
        let v = (st["health"] + st["stamina"] * 10.0 + g(&st, "health") * 0.0) * (1.0 + g(&st, "health_pct"));
        st.insert("health".into(), v);
        let v = g(&st, "mana") + st["intellect"] * 15.0;
        st.insert("mana".into(), v);
        let equipped_kinds: HashSet<&str> = self.gear.iter().filter_map(weapon_type).collect();
        self.racial_crit = self.racial.weapon_crit.iter().filter(|(k, _)| k.as_str() != "provisional" && equipped_kinds.contains(k.as_str())).map(|(_, v)| v.as_f64().unwrap_or(0.0)).sum();
        st["meleeCrit"] += self.racial_crit;
        st["rangedCrit"] += self.racial_crit;
        st["spellCrit"] += self.racial_crit;
        self.threat_reduction = g(&st, "threatReduction") / 100.0;
        self.stats = st;
    }

    fn item_effect(&mut self, item: &Item, idx: usize, effect: &str, gear_stats: &mut StatMap) {
        let t = self.t;
        let applied = &mut self.item_effects_applied;
        let unresolved = &mut self.item_effects_unresolved;
        if effect.starts_with("Equip:") {
            // "+N Attack Power" not followed by " when" / " in" (negative lookahead in the Python source).
            let re = regex_lite::Regex::new(r"(?i)\+(\d+) Attack Power").unwrap();
            for m in re.captures_iter(effect) {
                let end = m.get(0).unwrap().end();
                let rest = &effect[end..];
                if rest.starts_with(" when") || rest.starts_with(" in") {
                    continue;
                }
                if !item.has_stat("attackPower") {
                    add(gear_stats, "attackPower", m[1].parse().unwrap());
                }
                return;
            }
            const PATTERNS: [(&str, &str); 16] = [
                ("meleeHit", r"chance to hit by (\d+)%"), ("meleeCrit", r"critical strike by (\d+)%"), ("spellCrit", r"critical strike with spells by (\d+)%"),
                ("spellHit", r"hit with spells by (\d+)%"), ("spellPower", r"damage and healing done by magical spells and effects by up to (\d+)"),
                ("mp5", r"Restores (\d+) mana per 5"), ("defense", r"Increased Defense \+(\d+)"), ("dodge", r"dodge an attack by (\d+)%"), ("parry", r"parry an attack by (\d+)%"),
                ("block", r"block attacks with a shield by (\d+)%"), ("blockValue", r"block value of your shield by (\d+)"), ("firePower", r"Fire spells and effects by up to (\d+)"),
                ("frostPower", r"Frost spells and effects by up to (\d+)"), ("shadowPower", r"Shadow spells and effects by up to (\d+)"), ("naturePower", r"Nature spells and effects by up to (\d+)"),
                ("arcanePower", r"Arcane spells and effects by up to (\d+)"),
            ];
            for (key, pattern) in PATTERNS {
                if let Some(g) = re_search(pattern, effect) {
                    if !item.has_stat(key) {
                        add(gear_stats, key, g[1].clone().unwrap().parse().unwrap());
                    }
                    return;
                }
            }
            if let Some(g) = re_search(r"(\d+)% chance on melee hit to gain 1 extra attack", effect) {
                let pct: f64 = g[1].clone().unwrap().parse().unwrap();
                self.item_procs.push(ItemProc { name: item.name.clone(), trigger: "melee".into(), chance: Some(pct / 100.0), ppm: None, icd: 0.0, kind: "extra_attack".into(), amount: None, school: None, stat: None, value: None, duration: None, item_id: None, item_index: None });
                applied.push(json!({"item": item.name, "effect": effect, "proc_model": format!("{}% per melee hit", g[1].clone().unwrap())}));
                return;
            }
            if re_matches(r"Increased .+ \+\d+", effect) {
                applied.push(json!({"item": item.name, "effect": effect, "proc_model": "weapon skill"}));
                return;
            }
            if re_matches(r"Multi-Shot by (\d+)%", effect) {
                let pct: f64 = re_search(r"(\d+)%", effect).unwrap()[1].clone().unwrap().parse().unwrap();
                let v = self.mod_("dmg_ability:Multi-Shot") + pct / 100.0;
                self.mods.insert("dmg_ability:Multi-Shot".into(), v);
                return;
            }
            if re_matches(r"Attack Power (?:when fighting|in Cat)", effect) || re_matches(r"health per 5|resist|Run speed|stealth|Disarm|Ghost Wolf|interruption|Mana Shield|Sprint|Hamstring|Judgement|healing done by spells|Deals \d+ Fire damage to anyone", effect) {
                return;
            }
            unresolved.push(json!({"item": item.name, "effect": effect}));
            return;
        }
        if effect.starts_with("Use:") {
            let cd = cooldown_seconds(effect);
            let uses = (self.duration / cd).ceil().max(1.0) as i64;
            const USE_PATTERNS: [(&str, &str); 4] = [
                ("spellPower", r"damage and healing.*?up to (\d+) for (\d+) sec"), ("attackPower", r"Attack Power by (\d+) for (\d+) sec"), ("haste", r"attack speed by (\d+)% for (\d+) sec"),
                ("armorPenetration", r"armor penetration.*?for (\d+) sec.*?by (\d+).*?up to (\d+) times"),
            ];
            for (key, pattern) in USE_PATTERNS {
                if let Some(g) = re_search(pattern, effect) {
                    if key != "armorPenetration" {
                        let value: f64 = g[1].clone().unwrap().parse().unwrap();
                        let dur: f64 = g[2].clone().unwrap().parse().unwrap();
                        self.item_uses.push(ItemUse { name: item.name.clone(), stat: key.into(), value: value / if key == "haste" { 100.0 } else { 1.0 }, school: None, duration: dur, cooldown: cd });
                        applied.push(json!({"item": item.name, "effect": effect, "uses": uses}));
                        return;
                    }
                }
            }
            if let Some(g) = re_search(r"Restores (\d+)(?: to (\d+))? mana", effect) {
                let a: f64 = g[1].clone().unwrap().parse().unwrap();
                let b: f64 = g[2].clone().map(|s| s.parse().unwrap()).unwrap_or(a);
                self.item_uses.push(ItemUse { name: item.name.clone(), stat: "mana".into(), value: (a + b) / 2.0, school: None, duration: 0.0, cooldown: cd });
                applied.push(json!({"item": item.name, "effect": effect, "uses": uses}));
                return;
            }
            if let Some(g) = re_search(r"(?:causes|deals) (\d+)(?: to (\d+))? (\w+ )?damage", effect) {
                let a: f64 = g[1].clone().unwrap().parse().unwrap();
                let b: f64 = g[2].clone().map(|s| s.parse().unwrap()).unwrap_or(a);
                let school = g[3].clone().unwrap_or_else(|| "physical".into()).trim().to_lowercase();
                self.item_uses.push(ItemUse { name: item.name.clone(), stat: "damage".into(), value: (a + b) / 2.0, school: Some(school), duration: 0.0, cooldown: cd });
                applied.push(json!({"item": item.name, "effect": effect, "uses": uses}));
                return;
            }
            unresolved.push(json!({"item": item.name, "effect": effect}));
            return;
        }
        if effect.starts_with("Chance on hit:") {
            let ppm = item.id.and_then(|id| t.ITEM_PROC_PPM.get(&id.to_string())).copied().unwrap_or(1.0);
            let icd = proc_icd(effect);
            if let Some(g) = re_search(r"(?:for|dealing|causing|causes|deals|blasts a target for) (\d+)(?: to (\d+))? (\w+ )?damage", effect) {
                let a: f64 = g[1].clone().unwrap().parse().unwrap();
                let b: f64 = g[2].clone().map(|s| s.parse().unwrap()).unwrap_or(a);
                let mut school = g[3].clone().unwrap_or_else(|| "physical".into()).trim().to_lowercase();
                if !SPELL_SCHOOLS.contains(&school.as_str()) {
                    school = "physical".into();
                }
                self.item_procs.push(ItemProc { name: item.name.clone(), trigger: "weapon".into(), chance: None, ppm: Some(ppm), icd, kind: "damage".into(), amount: Some((a + b) / 2.0), school: Some(school), stat: None, value: None, duration: None, item_id: item.id, item_index: Some(idx) });
                applied.push(json!({"item": item.name, "effect": effect, "proc_model": format!("{} PPM", fmt_g(ppm)), "internal_cooldown": icd}));
                return;
            }
            if let Some(g) = re_search(r"attack speed by (\d+)% for (\d+) sec", effect) {
                let v: f64 = g[1].clone().unwrap().parse().unwrap();
                let d: f64 = g[2].clone().unwrap().parse().unwrap();
                self.item_procs.push(ItemProc { name: item.name.clone(), trigger: "weapon".into(), chance: None, ppm: Some(ppm), icd, kind: "buff".into(), amount: None, school: None, stat: Some("haste".into()), value: Some(v / 100.0), duration: Some(d), item_id: item.id, item_index: Some(idx) });
                applied.push(json!({"item": item.name, "effect": effect, "proc_model": format!("{} PPM", fmt_g(ppm))}));
                return;
            }
            for (key, pattern) in [("strength", r"Strength by (\d+) for (\d+) sec"), ("attackPower", r"Attack Power by (\d+) for (\d+) sec")] {
                if let Some(g) = re_search(pattern, effect) {
                    let v: f64 = g[1].clone().unwrap().parse().unwrap();
                    let d: f64 = g[2].clone().unwrap().parse().unwrap();
                    self.item_procs.push(ItemProc { name: item.name.clone(), trigger: "weapon".into(), chance: None, ppm: Some(ppm), icd, kind: "buff".into(), amount: None, school: None, stat: Some(key.into()), value: Some(v), duration: Some(d), item_id: item.id, item_index: Some(idx) });
                    applied.push(json!({"item": item.name, "effect": effect, "proc_model": format!("{} PPM", fmt_g(ppm))}));
                    return;
                }
            }
            unresolved.push(json!({"item": item.name, "effect": effect}));
        }
    }

    // ---- abilities -------------------------------------------------------
    fn init_abilities(&mut self) -> Result<(), String> {
        let t = self.t;
        let rotation_src = &t.ROTATIONS[&self.spec.id];
        let enabled: BTreeSet<String> = match self.request.get("rotation_enabled") {
            Some(v) if v.is_array() => str_set(Some(v)),
            _ => rotation_src.iter().map(|(n, _)| n.clone()).collect(),
        };
        let mut rotation = Vec::new();
        let mut actions: IndexMap<String, Ability> = IndexMap::new();
        for (name, cond) in rotation_src {
            let base = &t.ABILITIES[name];
            if let Some(gate) = t.TALENT_GATED.get(name) {
                if self.flag(gate) == 0.0 {
                    continue;
                }
            }
            if name == "Shield Slam" && !self.has_shield {
                self.notes.push("Shield Slam requires a shield; none equipped.".into());
                continue;
            }
            if !enabled.contains(name) {
                continue;
            }
            rotation.push((name.clone(), cond.clone()));
            actions.insert(name.clone(), self.resolve(name, base));
        }
        if rotation.is_empty() {
            return Err("Enable at least one rotation ability.".into());
        }
        for (key, action) in &t.CONSUMABLE_ACTIONS {
            if self.consumes.contains(key) && !actions.contains_key(action) {
                let res = self.spec.resource.as_str();
                if action == "Major Mana Potion" && res != "Mana" { continue; }
                if action == "Mighty Rage Potion" && res != "Rage" { continue; }
                if action == "Thistle Tea" && res != "Energy" { continue; }
                if action == "Demonic Rune" && res != "Mana" { continue; }
                actions.insert(action.clone(), self.resolve(action, &t.ABILITIES[action]));
            }
        }
        for u in &self.item_uses {
            let a = Ability { kind: "item_use".into(), cooldown: u.cooldown, off_gcd: true, item_use: Some(u.clone()), school: Some(u.school.clone().unwrap_or_else(|| "physical".into())), mult: 1.0, ..Default::default() };
            actions.insert(format!("Item - {}", u.name), a);
        }
        self.action_names = rotation.iter().map(|(n, _)| n.clone()).collect();
        self.rotation_conds = rotation.iter().map(|(n, c)| Ok((n.clone(), parse_cond(c)?))).collect::<Result<_, String>>()?;
        for (n, c) in &self.rotation_conds {
            self.rotation_last.insert(n.clone(), c.clone());
        }
        self.rotation = rotation;
        self.actions = actions;
        Ok(())
    }

    fn resolve(&self, name: &str, base: &Ability) -> Ability {
        let mut a = base.clone();
        let school = a.school.clone().unwrap_or_else(|| "None".into());
        a.cost = ((a.cost + self.mod_(&format!("cost:{name}"))) * (1.0 + self.mod_(&format!("cost_pct:{name}")) + self.mod_("cost_pct_all") + self.mod_(&format!("cost_pct_school:{school}")))).max(0.0);
        if self.spec.resource == "Rage" && a.cost != 0.0 && self.flag("focused_rage") != 0.0 && name != "Heroic Strike" {
            a.cost = (a.cost - 3.0).max(0.0);
        }
        if self.flag("shadowform") != 0.0 && a.school.as_deref() == Some("shadow") {
            a.cost *= 0.5;
        }
        a.cast = (a.cast + self.mod_(&format!("cast:{name}"))).max(0.0);
        a.cooldown = (a.cooldown + self.mod_(&format!("cooldown:{name}"))).max(0.0);
        if a.gcd.is_none() {
            a.gcd = Some(self.t.GCD);
        }
        a.mult = 1.0 + self.mod_(&format!("dmg_ability:{name}"));
        a.crit_bonus = self.mod_(&format!("crit_ability:{name}"));
        if name == "Shadow Word: Pain" {
            a.ticks += self.flag("swp_ticks") as i64;
        }
        if a.ticks != 0 && self.mod_(&format!("ticks:{name}")) != 0.0 {
            a.ticks += self.mod_(&format!("ticks:{name}")) as i64;
        }
        if name == "Immolate" && self.flag("aftermath") != 0.0 {
            a.direct_mult = Some(1.0 + self.flag("aftermath") * 5.0 * 0.1);
        }
        a
    }

    // ---- pets ------------------------------------------------------------
    fn init_pets(&mut self) -> Result<(), String> {
        let t = self.t;
        let r = &self.request;
        if self.spec.class_name == "Hunter" {
            let fam = req_str(r.get("pet_family"), "cat");
            let family = t.PET_FAMILIES.get(&fam).unwrap_or(&t.PET_FAMILIES["cat"]).clone();
            let abilities = match r.get("pet_abilities") {
                Some(v) if v.is_array() => str_set(Some(v)),
                _ => [family.special.clone(), family.dump.clone()].into_iter().flatten().collect(),
            };
            self.pet = Some(Pet::Hunter(HunterPet {
                family: fam,
                damage: family.damage,
                special: family.special.clone(),
                dump: family.dump.clone(),
                speed: req_f64(r.get("pet_attack_speed"), 2.0)?.clamp(1.0, 2.5),
                uptime: req_f64(r.get("pet_uptime"), 1.0)?.clamp(0.0, 1.0),
                abilities,
            }));
        } else if self.spec.class_name == "Warlock" {
            let fam = req_str(r.get("pet_family"), "succubus");
            if fam != "none" {
                let cfg = t.WARLOCK_PETS.get(&fam).unwrap_or(&t.WARLOCK_PETS["succubus"]).clone();
                let mut defaults: Vec<String> = vec![];
                if cfg.melee.is_some() {
                    defaults.push("Melee".into());
                }
                if let Some(s) = &cfg.spell {
                    defaults.push(s.clone());
                }
                if let Some(u) = &cfg.utility {
                    defaults.push(u.clone());
                }
                let abilities = match r.get("pet_abilities") {
                    Some(v) if v.is_array() => str_set(Some(v)),
                    _ => defaults.into_iter().collect(),
                };
                self.pet = Some(Pet::Warlock(WarlockPetCfg { family: fam, cfg, uptime: req_f64(r.get("pet_uptime"), 1.0)?.clamp(0.0, 1.0), abilities }));
            }
        }
        Ok(())
    }

    pub fn armor_after_debuffs(&self) -> f64 {
        let mut armor = req_f64(self.request.get("armor"), 3731.0).unwrap_or(3731.0);
        for (key, value) in &self.t.DEBUFF_ARMOR {
            if self.debuffs.contains(key) {
                armor -= value;
            }
        }
        armor -= self.stats.get("armorPenetration").copied().unwrap_or(0.0);
        armor.clamp(0.0, 20000.0)
    }

    fn weapon_row(&self, slot: &str, item: &Item) -> Value {
        json!({"slot": slot, "name": item.name, "speed": item.weaponSpeed, "damage": [item.weaponDamageMin, item.weaponDamageMax], "skill": self.skill(item)})
    }

    pub fn summary(&self) -> Value {
        let t = self.t;
        let s = &self.spec;
        let mut weapons = vec![self.weapon_row("Main Hand", &self.mh)];
        if !self.oh.is_empty() {
            weapons.push(self.weapon_row("Off Hand", &self.oh));
        }
        if self.ranged.has_weapon_damage() {
            weapons.push(self.weapon_row("Ranged", &self.ranged));
        }
        let mut actions = Map::new();
        for (n, a) in &self.actions {
            let mut v = serde_json::to_value(a).unwrap();
            if let Value::Object(m) = &mut v {
                m.remove("item_use");
            }
            actions.insert(n.clone(), v);
        }
        let mut effects: BTreeSet<String> = self.buffs.iter().cloned().collect();
        effects.extend(self.consumes.iter().cloned());
        effects.extend(self.debuffs.iter().cloned());
        let pet = self.pet.as_ref().map(|p| match p {
            Pet::Hunter(h) => json!({"kind": "hunter", "family": h.family, "damage": h.damage, "special": h.special, "dump": h.dump, "speed": h.speed, "uptime": h.uptime, "abilities": h.abilities}),
            Pet::Warlock(w) => json!({"kind": "warlock", "family": w.family, "uptime": w.uptime, "abilities": w.abilities}),
        });
        let mut notes = self.notes.clone();
        for (n, a) in &self.actions {
            if let Some(p) = &a.provisional {
                notes.push(format!("{n}: {p}"));
            }
        }
        if let Some(active) = &self.racial.active {
            if active.provisional_cooldown {
                notes.push(format!("{} cooldown is not published by Wowhead; {} sec assumed.", active.name, fmt_g(active.cooldown)));
            }
        }
        let gear_stats: Map<String, Value> = self.stats.iter().map(|(k, v)| (k.clone(), json!(round_to(*v, 3)))).collect();
        let talent_effects: Map<String, Value> = self.mods.iter().map(|(k, v)| (k.clone(), json!(round_to(*v, 4)))).collect();
        json!({
            "race": self.race, "racial": self.racial.summary, "racial_enabled": self.racial_enabled, "boss_type": self.boss_type, "boss_armor": self.armor_after_debuffs(),
            "targets": self.targets, "gear_stats": gear_stats, "enchants": self.applied_enchants, "rejected_enchants": self.rejected_enchants,
            "active_effects": effects, "item_effects": {"applied": self.item_effects_applied, "unresolved": self.item_effects_unresolved},
            "set_bonuses": {"counts": self.set_counts, "active": self.active_set_bonuses, "unresolved": self.unresolved_set_bonuses},
            "talent_points": self.talent_points, "talents": self.talents, "primary_tree": s.tree, "talent_effects": talent_effects,
            "weapons": weapons, "actions": actions, "rotation": self.rotation,
            "bloodlust": {"haste": t.BLOODLUST_HASTE, "starts_at": 0.0, "duration": self.duration.min(t.BLOODLUST_DURATION)},
            "execute_phase": {"starts_at": self.duration * 0.8, "fraction": 0.2},
            "pet": pet, "notes": notes, "classic_reference_dps": null, "multiplier": 1.0,
        })
    }
}
