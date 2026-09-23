//! Sourced tables exported from `engine_data.py` / `sim.py` by
//! `tools/export_static_data.py` and embedded at compile time.

use indexmap::IndexMap;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::OnceLock;

pub type StatMap = IndexMap<String, f64>;

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct Spec {
    pub id: String,
    pub class_name: String,
    pub name: String,
    pub role: String,
    pub style: String,
    pub resource: String,
    pub tree: String,
    pub form: Option<String>,
    pub stance: Option<String>,
}

impl Spec {
    pub fn form_is(&self, f: &str) -> bool {
        self.form.as_deref() == Some(f)
    }
    pub fn stance_or_form(&self) -> String {
        self.stance.clone().or_else(|| self.form.clone()).unwrap_or_else(|| "none".to_string())
    }
}

#[derive(Deserialize, Serialize, Clone, Debug, Default)]
pub struct RacialActive {
    pub name: String,
    #[serde(default)]
    pub crit: f64,
    #[serde(default)]
    pub haste: f64,
    #[serde(default)]
    pub ap_pct: f64,
    #[serde(default)]
    pub sp_pct: f64,
    #[serde(default)]
    pub charges: i64,
    #[serde(default)]
    pub damage: f64,
    #[serde(default)]
    pub duration: f64,
    #[serde(default)]
    pub cooldown: f64,
    #[serde(default)]
    pub provisional_cooldown: bool,
}

#[derive(Deserialize, Serialize, Clone, Debug, Default)]
pub struct TouchOfTheGrave {
    pub chance: f64,
    pub health_fraction: f64,
}

#[derive(Deserialize, Serialize, Clone, Debug, Default)]
pub struct Racial {
    #[serde(default)]
    pub weapon_crit: IndexMap<String, Value>,
    #[serde(default)]
    pub creature_damage: HashMap<String, f64>,
    #[serde(default)]
    pub summary: String,
    #[serde(default)]
    pub dodge: f64,
    #[serde(default)]
    pub hit: f64,
    #[serde(default)]
    pub haste: f64,
    #[serde(default)]
    pub health_pct: f64,
    #[serde(default)]
    pub active: Option<RacialActive>,
    #[serde(default)]
    pub touch_of_the_grave: Option<TouchOfTheGrave>,
}

#[derive(Deserialize, Serialize, Clone, Debug, Default)]
pub struct StanceMod {
    #[serde(default = "one")]
    pub threat: f64,
    #[serde(default = "one")]
    pub damage: f64,
    #[serde(default = "one")]
    pub taken: f64,
}
fn one() -> f64 {
    1.0
}

#[derive(Deserialize, Serialize, Clone, Debug, Default)]
pub struct Weapon {
    pub hand: String,
    #[serde(default)]
    pub normalized: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mult: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub flat: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dagger_mult: Option<f64>,
}

#[derive(Deserialize, Serialize, Clone, Debug, Default)]
pub struct ItemUse {
    pub name: String,
    pub stat: String,
    pub value: f64,
    #[serde(default)]
    pub school: Option<String>,
    pub duration: f64,
    pub cooldown: f64,
}

/// One ability record from `engine_data.ABILITIES` (plus runtime fields set by `Config::resolve`).
#[derive(Deserialize, Serialize, Clone, Debug, Default)]
pub struct Ability {
    #[serde(default)]
    pub kind: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub school: Option<String>,
    #[serde(default)]
    pub cost: f64,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub cost_pct: f64,
    #[serde(default)]
    pub cooldown: f64,
    #[serde(default)]
    pub cast: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub gcd: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub base: Option<(f64, f64)>,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub tick: f64,
    #[serde(default, skip_serializing_if = "is_zero_i")]
    pub ticks: i64,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub tick_len: f64,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub coeff: f64,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub dot_coeff: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub weapon: Option<Weapon>,
    #[serde(default, skip_serializing_if = "is_zero_i")]
    pub cp: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub threat_mult: Option<f64>,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub flat_threat: f64,
    #[serde(default, skip_serializing_if = "is_false")]
    pub execute: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub execute_formula: Option<(f64, f64)>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub requires: Option<String>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub no_dodge: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub finisher: Option<String>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub bleed: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    pub forever: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    pub aoe: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    pub spreadable: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provisional: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ap_mult: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub flat: Option<f64>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub add_block_value: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    pub no_damage: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    pub off_gcd: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rage: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rage_over_time: Option<(f64, f64)>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub duration: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub damage_mult_school: Option<(String, f64)>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub damage_mult: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cost_mult: Option<f64>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub combustion: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    pub instant_next: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub no_effect: Option<String>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub ranged_cast: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pet_damage_mult: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ranged_haste: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub melee_haste: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub spell_haste: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub energy_regen_mult: Option<f64>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub next_crit: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub energy: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub shared_cd: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub apply_debuff: Option<(String, f64, HashMap<String, f64>)>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub consumes_dot: Option<String>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub execute_bonus: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub life_tap: Option<f64>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub sacrifice: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    pub always_hit: bool,
    #[serde(default, skip_serializing_if = "is_false")]
    pub no_crit: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mana: Option<(f64, f64)>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub strength: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub creature_mult: Option<HashMap<String, f64>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub flat_damage_bonus: Option<f64>,
    // Runtime fields (set by Config::resolve).
    #[serde(default = "one")]
    pub mult: f64,
    #[serde(default)]
    pub crit_bonus: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub direct_mult: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub item_use: Option<ItemUse>,
}

fn is_zero(v: &f64) -> bool {
    *v == 0.0
}
fn is_zero_i(v: &i64) -> bool {
    *v == 0
}
fn is_false(v: &bool) -> bool {
    !*v
}

impl Ability {
    pub fn school_str(&self) -> &str {
        self.school.as_deref().unwrap_or("physical")
    }
    pub fn threat_mult(&self) -> f64 {
        self.threat_mult.unwrap_or(1.0)
    }
    /// Python `a.get("weapon", {}).get("hand")`.
    pub fn weapon_hand(&self) -> Option<&str> {
        self.weapon.as_ref().map(|w| w.hand.as_str())
    }
    pub fn weapon_flat(&self) -> f64 {
        self.weapon.as_ref().and_then(|w| w.flat).unwrap_or(0.0)
    }
    pub fn rage_value(&self) -> Option<f64> {
        self.rage.as_ref().and_then(|v| v.as_f64())
    }
    pub fn rage_range(&self) -> Option<(f64, f64)> {
        let arr = self.rage.as_ref()?.as_array()?;
        Some((arr.first()?.as_f64()?, arr.get(1)?.as_f64()?))
    }
}

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct PetFamily {
    pub damage: f64,
    pub special: Option<String>,
    pub dump: Option<String>,
}

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct PetAbility {
    pub cost: f64,
    pub cooldown: f64,
    pub min: f64,
    pub max: f64,
    pub school: String,
}

#[derive(Deserialize, Serialize, Clone, Debug, Default)]
pub struct WarlockPet {
    #[serde(default)]
    pub speed: f64,
    #[serde(default)]
    pub melee: Option<(f64, f64)>,
    #[serde(default)]
    pub spell: Option<String>,
    #[serde(default)]
    pub spell_cost: f64,
    #[serde(default)]
    pub cast: f64,
    #[serde(default)]
    pub cooldown: f64,
    #[serde(default)]
    pub spell_min: f64,
    #[serde(default)]
    pub spell_max: f64,
    #[serde(default)]
    pub school: Option<String>,
    #[serde(default)]
    pub mana: f64,
    #[serde(default)]
    pub intellect: f64,
    #[serde(default)]
    pub spirit: f64,
    #[serde(default)]
    pub strength: f64,
    #[serde(default)]
    pub stamina: f64,
    #[serde(default)]
    pub utility: Option<String>,
}

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct Poison {
    pub chance: f64,
    #[serde(default)]
    pub min: f64,
    #[serde(default)]
    pub max: f64,
    #[serde(default)]
    pub tick: f64,
    #[serde(default)]
    pub ticks: i64,
    #[serde(default)]
    pub tick_len: f64,
    #[serde(default)]
    pub max_stacks: i64,
}

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct Windfury {
    pub chance: f64,
    #[serde(default)]
    pub extra_attacks: i64,
    pub ap: f64,
}

#[derive(Deserialize, Clone, Debug)]
#[allow(non_snake_case)]
pub struct Tables {
    pub CLASS_RACES: IndexMap<String, Vec<String>>,
    pub CREATURE_TYPES: Vec<String>,
    pub RACE_STATS: HashMap<String, IndexMap<String, f64>>,
    pub CLASS_BASE: HashMap<String, StatMap>,
    pub AP_PER_STRENGTH: HashMap<String, f64>,
    pub AP_PER_AGILITY: HashMap<String, f64>,
    pub MELEE_CRIT_PER_AGI: HashMap<String, f64>,
    pub SPELL_CRIT_PER_INT: HashMap<String, f64>,
    pub DODGE_PER_AGI: HashMap<String, f64>,
    pub SPIRIT_REGEN: HashMap<String, (f64, f64)>,
    pub RAGE_CONVERSION_60: f64,
    pub LEVEL: f64,
    pub TARGET_LEVEL: f64,
    pub TARGET_DEFENSE: f64,
    pub GCD: f64,
    pub ENERGY_GCD: f64,
    pub RACIALS: IndexMap<String, Racial>,
    pub BUFF_STATS: IndexMap<String, StatMap>,
    pub BUFF_GROUPS: IndexMap<String, Vec<String>>,
    pub WINDFURY_TOTEM: Windfury,
    pub DEBUFF_ARMOR: IndexMap<String, f64>,
    pub CONSUME_STATS: IndexMap<String, StatMap>,
    pub SPEC_MAP: IndexMap<String, Spec>,
    pub STANCE_MODS: HashMap<String, StanceMod>,
    pub CLASS_THREAT: HashMap<String, f64>,
    pub ABILITIES: IndexMap<String, Ability>,
    pub ROTATIONS: HashMap<String, Vec<(String, String)>>,
    pub CONSUMABLE_ACTIONS: IndexMap<String, String>,
    pub TALENT_EFFECTS: HashMap<String, IndexMap<String, f64>>,
    pub TALENT_GATED: HashMap<String, String>,
    pub DEFAULT_BUILDS: HashMap<String, IndexMap<String, i64>>,
    pub PET_FAMILIES: HashMap<String, PetFamily>,
    pub PET_ABILITIES: HashMap<String, PetAbility>,
    pub PET_FOCUS_PER_SEC: f64,
    pub WARLOCK_PETS: HashMap<String, WarlockPet>,
    pub POISONS: HashMap<String, Poison>,
    pub WINDFURY: Windfury,
    pub ITEM_PROC_PPM: HashMap<String, f64>,
    pub CONSUMABLE_GROUPS: HashMap<String, String>,
    #[serde(default)]
    pub SET_EFFECTS: HashMap<String, IndexMap<String, f64>>,
    #[serde(default)]
    pub SET_NO_COMBAT_EFFECT: Vec<String>,
    #[serde(default)]
    pub SET_PROVISIONAL: HashMap<String, String>,
    pub EQUIPMENT_RULES: Value,
}

static TABLES: OnceLock<Tables> = OnceLock::new();

pub fn tables() -> &'static Tables {
    TABLES.get_or_init(|| serde_json::from_str(include_str!("../data/engine_data.json")).expect("engine_data.json"))
}

impl Tables {
    pub fn stance_mod(&self, key: &str) -> StanceMod {
        self.STANCE_MODS.get(key).cloned().unwrap_or_default()
    }
}

// ---------------------------------------------------------------------------
// Paladin tables (sim.py / gear_data.py)
// ---------------------------------------------------------------------------

#[derive(Deserialize, Clone, Debug)]
pub struct PaladinTalent {
    pub name: String,
    pub row: i64,
    pub ranks: i64,
    pub requires: Vec<TalentReq>,
}

#[derive(Deserialize, Clone, Debug)]
pub struct TalentReq {
    pub id: String,
    pub qty: i64,
}

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct SetBonusDef {
    pub required: i64,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub stats: StatMap,
    #[serde(default)]
    pub modeled: Option<bool>,
}

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct ForeverSet {
    pub source: String,
    pub bonuses: Vec<SetBonusDef>,
}

#[derive(Deserialize, Clone, Debug)]
pub struct PaladinTables {
    pub facts: IndexMap<String, IndexMap<String, Value>>,
    pub version: String,
    pub sources: Value,
    pub status: Value,
    pub excluded: Value,
    pub data_sha256: String,
    pub assumptions: Vec<String>,
    pub talents: IndexMap<String, PaladinTalent>,
    pub tree_talents: IndexMap<String, Vec<String>>,
    pub points_per_tier: i64,
    pub max_points: i64,
    pub protection_build: IndexMap<String, i64>,
    pub retribution_build: IndexMap<String, i64>,
    pub consumable_groups: IndexMap<String, String>,
    pub phase6_gear: HashMap<String, IndexMap<String, i64>>,
    pub gear_slots: Vec<String>,
    pub catalog: IndexMap<String, Value>,
    pub forever_sets: IndexMap<String, ForeverSet>,
    pub consumable_stats: IndexMap<String, StatMap>,
    pub direct_stats: IndexMap<String, (String, f64)>,
    pub classic_primary: IndexMap<String, String>,
    pub item_models: IndexMap<String, (StatMap, Vec<Value>, Vec<Value>)>,
    pub default_enchants: IndexMap<String, Value>,
}

impl PaladinTables {
    pub fn fact(&self, group: &str, key: &str) -> f64 {
        self.facts.get(group).and_then(|g| g.get(key)).and_then(|v| v.as_f64()).unwrap_or_else(|| panic!("missing fact {group}.{key}"))
    }

    /// Mirrors Python's `F[group].get(key, default)` for facts that only exist on some groups
    /// (e.g. `judgement_base`, which is sourced for Seal of Fury but not the other two seals).
    pub fn fact_or(&self, group: &str, key: &str, default: f64) -> f64 {
        self.facts.get(group).and_then(|g| g.get(key)).and_then(|v| v.as_f64()).unwrap_or(default)
    }
}

static PALADIN: OnceLock<PaladinTables> = OnceLock::new();

pub fn paladin_tables() -> &'static PaladinTables {
    PALADIN.get_or_init(|| serde_json::from_str(include_str!("../data/paladin_data.json")).expect("paladin_data.json"))
}
