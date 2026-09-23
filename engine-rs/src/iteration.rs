//! One fight iteration (port of `engine.Iteration`).  RNG draws happen in the
//! same order as the Python reference so seeded runs agree.

use crate::config::{compare, Cond, Config, Hand, Pet};
use crate::data::Ability;
use crate::items::{normalized_speed, weapon_type, Item, SPELL_SCHOOLS};
use crate::rng::PyRandom;
use indexmap::IndexMap;
use serde::{Deserialize, Serialize};

pub const EPS: f64 = 1e-7;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Outcome {
    Miss,
    Dodge,
    Parry,
    Glance,
    Block,
    Crit,
    Hit,
    Crush,
}

impl Outcome {
    pub fn as_str(self) -> &'static str {
        match self { Outcome::Miss => "miss", Outcome::Dodge => "dodge", Outcome::Parry => "parry", Outcome::Glance => "glance", Outcome::Block => "block", Outcome::Crit => "crit", Outcome::Hit => "hit", Outcome::Crush => "crush" }
    }
    pub fn avoided(self) -> bool {
        matches!(self, Outcome::Miss | Outcome::Dodge | Outcome::Parry)
    }
}

#[derive(Clone, Debug, Default)]
pub struct Buff {
    pub until: f64,
    pub stacks: i64,
    pub stacks_max: Option<i64>,
    pub stat: Option<String>,
    pub value: f64,
    pub haste: f64,
    pub ap_pct: f64,
    pub sp_pct: f64,
    pub damage_mult: f64,
    pub damage_mult_school: Option<(String, f64)>,
    pub energy_regen_mult: f64,
    pub pet_damage_mult: f64,
    pub flat_damage_bonus: f64,
    pub tick: f64,
    pub next: f64,
}

#[derive(Clone, Debug)]
pub struct Dot {
    pub next: f64,
    pub remaining: i64,
    pub tick: f64,
    pub tick_len: f64,
    pub school: String,
    pub bleed: bool,
    pub stacks: i64,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Row {
    pub casts: f64,
    pub hits: f64,
    pub crits: f64,
    pub misses: f64,
    pub glances: f64,
    pub dodges: f64,
    pub damage: f64,
    pub threat: f64,
}

#[derive(Clone, Debug)]
pub struct Cast {
    pub name: String,
    pub until: f64,
    pub next_tick: f64,
    pub ticks_left: i64,
    pub tick_len: f64,
    pub landed: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LogEntry {
    pub time: f64,
    pub event: String,
    pub outcome: String,
    pub amount: f64,
    pub resource: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
}

#[derive(Clone, Debug, Default)]
pub struct PetState {
    pub focus: f64,
    pub next_swing: f64,
    pub gcd: f64,
    pub ready: IndexMap<String, f64>,
    pub last: f64,
    pub active_until: f64,
    pub frenzy_until: f64,
    pub mana: f64,
    pub next_cast: f64,
    pub cast_until: Option<f64>,
    pub next_mana: f64,
    pub next_utility: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IterResult {
    pub total: f64,
    pub threat: f64,
    pub pet_threat: f64,
    pub taken: f64,
    pub rows: IndexMap<String, Row>,
    pub duration: f64,
    pub starved: f64,
    pub resource_end: f64,
    pub alive: bool,
    pub alive_seconds: f64,
    pub first_oom: Option<f64>,
    pub taken_by: IndexMap<String, f64>,
    pub log: Vec<LogEntry>,
    pub buff_active_seconds: IndexMap<String, f64>,
    pub buff_procs: IndexMap<String, i64>,
}

fn title(s: &str) -> String {
    let mut out = String::new();
    let mut new_word = true;
    for ch in s.chars() {
        if ch.is_alphabetic() {
            if new_word { out.extend(ch.to_uppercase()); } else { out.extend(ch.to_lowercase()); }
            new_word = false;
        } else {
            out.push(ch);
            new_word = true;
        }
    }
    out
}

pub struct Iteration<'a> {
    pub c: &'a Config,
    pub rng: PyRandom,
    pub trace: bool,
    pub log: Vec<LogEntry>,
    pub duration: f64,
    pub execute_at: f64,
    pub t: f64,
    pub rows: IndexMap<String, Row>,
    pub total: f64,
    pub threat: f64,
    pub taken: f64,
    pub st: IndexMap<String, f64>,
    pub max_mana: f64,
    pub max_energy: f64,
    pub max_rage: f64,
    pub mana: f64,
    pub energy: f64,
    pub rage: f64,
    pub cp: i64,
    pub health_max: f64,
    pub health: f64,
    pub alive: bool,
    pub alive_seconds: f64,
    pub buffs: IndexMap<String, Buff>,
    pub debuffs: IndexMap<String, Buff>,
    pub dots: IndexMap<String, Dot>,
    pub dots_extra: Vec<(String, Dot)>,
    pub cooldowns: IndexMap<String, f64>,
    pub gcd_until: f64,
    pub cast: Option<Cast>,
    pub next_mh: f64,
    pub next_oh: f64,
    pub next_ranged: f64,
    pub queued_swing: Option<String>,
    pub last_cast_time: f64,
    pub next_mana_tick: f64,
    pub next_energy_tick: f64,
    pub next_rage_tick: f64,
    pub next_boss: f64,
    pub next_heal: f64,
    pub flurry: i64,
    pub eureka: i64,
    pub dodged_recently: f64,
    pub avoided_recently: f64,
    pub combustion: Option<(i64, i64)>,
    pub clearcast: bool,
    pub next_instant: bool,
    pub next_crit: bool,
    pub eclipse: i64,
    pub busy_until: f64,
    pub starved: f64,
    pub first_oom: Option<f64>,
    pub pet_state: Option<PetState>,
    pub enrage_until: f64,
    pub sacrificed: Option<(String, f64)>,
    pub racial_next: f64,
    pub item_icd: IndexMap<String, f64>,
    pub windfury_lock: f64,
    pub cur_school: String,
    pub cur_cost: f64,
    pub blocked_by_resource: bool,
    pub taken_by: IndexMap<String, f64>,
    pub pet_threat: f64,
    pub wrath_discount: bool,
    pub next_parry: bool,
    pub buff_active_seconds: IndexMap<String, f64>,
    pub buff_covered_until: IndexMap<String, f64>,
    pub buff_procs: IndexMap<String, i64>,
}

impl<'a> Iteration<'a> {
    pub fn new(c: &'a Config, seed: i64, trace: bool) -> Self {
        let mut rng = PyRandom::new(seed.unsigned_abs());
        let duration = if c.variance != 0.0 { rng.uniform(c.duration - c.variance, c.duration + c.variance).max(10.0) } else { c.duration };
        let st = c.stats.clone();
        let g = |k: &str| st.get(k).copied().unwrap_or(0.0);
        let max_mana = g("mana");
        let max_energy = 100.0 + c.flag("max_energy") + g("maxEnergy");
        let max_rage = 100.0 + c.flag("max_rage");
        let health_max = st["health"];
        let mut it = Iteration {
            c, rng, trace, log: vec![], duration, execute_at: duration * 0.8, t: 0.0, rows: IndexMap::new(), total: 0.0, threat: 0.0, taken: 0.0,
            st, max_mana, max_energy, max_rage, mana: max_mana, energy: max_energy, rage: 0.0, cp: 0, health_max, health: health_max, alive: true, alive_seconds: duration,
            buffs: IndexMap::new(), debuffs: IndexMap::new(), dots: IndexMap::new(), dots_extra: Vec::new(), cooldowns: IndexMap::new(), gcd_until: 0.0, cast: None,
            next_mh: 0.0, next_oh: if !c.oh.is_empty() { c.oh.speed_or(2.0) / 2.0 } else { 0.0 }, next_ranged: 0.0, queued_swing: None,
            last_cast_time: -10.0, next_mana_tick: 2.0, next_energy_tick: 2.0, next_rage_tick: 3.0, next_boss: 2.0, next_heal: 2.0,
            flurry: 0, eureka: 0, dodged_recently: -10.0, avoided_recently: -10.0, combustion: None, clearcast: false, next_instant: false, next_crit: false, eclipse: 0,
            busy_until: 0.0, starved: 0.0, first_oom: None, pet_state: None, enrage_until: 0.0, sacrificed: None, racial_next: 0.0, item_icd: IndexMap::new(), windfury_lock: 0.0,
            cur_school: String::new(), cur_cost: 0.0, blocked_by_resource: false, taken_by: IndexMap::new(), pet_threat: 0.0,
            wrath_discount: false, next_parry: false,
            buff_active_seconds: IndexMap::new(), buff_covered_until: IndexMap::new(), buff_procs: IndexMap::new(),
        };
        if c.spec.resource == "Rage" {
            let start = c.request.get("starting_rage").and_then(|v| v.as_f64()).unwrap_or(0.0);
            it.rage = start.min(it.max_rage);
        }
        it
    }

    // ---- utilities -------------------------------------------------------
    fn st(&self, k: &str) -> f64 {
        self.st.get(k).copied().unwrap_or(0.0)
    }

    pub fn row(&mut self, name: &str) -> &mut Row {
        self.rows.entry(name.to_string()).or_default()
    }

    fn record(&mut self, event: &str, outcome: &str, amount: f64) {
        if self.trace && self.log.len() < 400 {
            let res = self.resource();
            self.log.push(LogEntry { time: (self.t * 100.0).round() / 100.0, event: event.to_string(), outcome: outcome.to_string(), amount: (amount * 10.0).round() / 10.0, resource: (res * 10.0).round() / 10.0, note: None });
        }
    }

    fn buff_active(&self, name: &str) -> bool {
        self.buffs.get(name).is_some_and(|b| b.until > self.t + EPS)
    }

    fn debuff_active(&self, name: &str) -> bool {
        self.debuffs.get(name).is_some_and(|b| b.until > self.t + EPS)
    }

    fn add_buff(&mut self, name: &str, duration: f64, mut kw: Buff) {
        let t = self.t;
        let was_active = self.buffs.get(name).is_some_and(|b| b.until > t + EPS);
        if let Some(b) = self.buffs.get_mut(name) {
            if b.until > t {
                if let Some(max) = kw.stacks_max {
                    b.stacks = max.min(b.stacks + 1);
                    b.until = t + duration;
                    self.note_proc(name, duration);
                    self.log_buff(name, was_active);
                    return;
                }
            }
        }
        kw.until = t + duration;
        kw.stacks = 1;
        self.buffs.insert(name.to_string(), kw);
        self.note_proc(name, duration);
        self.log_buff(name, was_active);
    }

    /// Record a buff/proc activation for the Buffs tab: non-overlapping active-seconds (for
    /// duration buffs) plus a proc/activation count (for instant procs like Nightfall, where an
    /// actual timed buff object doesn't make sense).
    fn note_proc(&mut self, name: &str, duration: f64) {
        let t = self.t;
        let end = t + duration;
        let covered = self.buff_covered_until.get(name).copied().unwrap_or(0.0);
        if end > t.max(covered) {
            *self.buff_active_seconds.entry(name.to_string()).or_insert(0.0) += end - t.max(covered);
        }
        self.buff_covered_until.insert(name.to_string(), covered.max(end));
        *self.buff_procs.entry(name.to_string()).or_insert(0) += 1;
    }

    fn log_buff(&mut self, name: &str, was_active: bool) {
        if self.trace && self.log.len() < 400 {
            let res = self.resource();
            self.log.push(LogEntry { time: (self.t * 100.0).round() / 100.0, event: format!("Buff: {name}"), outcome: (if was_active { "refreshed" } else { "gained" }).to_string(), amount: 0.0, resource: (res * 10.0).round() / 10.0, note: None });
        }
    }

    /// Nightfall doesn't grant a stateful buff (it's consumed by the very next cast), so it
    /// can't go through add_buff -- but it should still show up as an activation for the Buffs
    /// tab, same as every other proc.
    fn proc_nightfall(&mut self) {
        self.next_instant = true;
        self.note_proc("Nightfall", 0.0);
        if self.trace && self.log.len() < 400 {
            let res = self.resource();
            self.log.push(LogEntry { time: (self.t * 100.0).round() / 100.0, event: "Buff: Nightfall".to_string(), outcome: "proc".to_string(), amount: 0.0, resource: (res * 10.0).round() / 10.0, note: None });
        }
    }

    fn add_debuff(&mut self, name: &str, duration: f64, stacks_max: Option<i64>) {
        let t = self.t;
        if let Some(b) = self.debuffs.get_mut(name) {
            if b.until > t {
                if let Some(max) = stacks_max {
                    b.stacks = max.min(b.stacks + 1);
                    b.until = t + duration;
                    return;
                }
            }
        }
        self.debuffs.insert(name.to_string(), Buff { until: t + duration, stacks: 1, stacks_max, ..Default::default() });
    }

    fn haste(&self, kind: &str) -> f64 {
        let c = self.c;
        let mut h = 1.0;
        if c.buffs.contains("bloodlust") && self.t < 40.0 { h *= 1.30; }
        h *= 1.0 + c.racial.haste * (c.racial_enabled as i32 as f64);
        if kind == "melee" {
            if self.flurry > 0 {
                h *= 1.0 + c.flag("flurry");
            }
            for name in ["Slice and Dice", "Blade Flurry", "Berserking", "Rage of the Farseer", "Frenzy"] {
                if let Some(b) = self.buffs.get(name) {
                    if b.until > self.t {
                        h *= 1.0 + b.haste;
                    }
                }
            }
            for b in self.buffs.values() {
                if b.stat.as_deref() == Some("haste") && b.until > self.t {
                    h *= 1.0 + b.value;
                }
            }
        } else if kind == "ranged" {
            h *= 1.15;
            for name in ["Rapid Fire", "Berserking", "Quick Shots"] {
                if let Some(b) = self.buffs.get(name) {
                    if b.until > self.t {
                        h *= 1.0 + b.haste;
                    }
                }
            }
        } else {
            for name in ["Berserking", "Rage of the Farseer", "Nature's Grace"] {
                if let Some(b) = self.buffs.get(name) {
                    if b.until > self.t {
                        h *= 1.0 + b.haste;
                    }
                }
            }
        }
        h
    }

    fn pet_delay(&self, speed: f64) -> f64 {
        if !self.c.buffs.contains("bloodlust") || self.t >= 40.0 { return speed; }
        let before = 40.0 - self.t;
        if speed / 1.30 <= before { speed / 1.30 } else { before + speed - before * 1.30 }
    }

    fn attack_delay(&self, speed: f64, kind: &str) -> f64 {
        let haste = self.haste(kind); let delay = speed / haste;
        if self.c.buffs.contains("bloodlust") && self.t < 40.0 && self.t + delay > 40.0 {
            let before = 40.0 - self.t;
            return before + (speed - before * haste) / (haste / 1.30);
        }
        delay
    }

    fn ap(&self, ranged: bool) -> f64 {
        let mut base = if ranged { self.st("rangedAttackPower") } else { self.st("attackPower") };
        for b in self.buffs.values() {
            if b.until > self.t {
                if b.stat.as_deref() == Some("attackPower") || (ranged && b.stat.as_deref() == Some("rangedAttackPower")) {
                    base += b.value;
                }
                if !ranged && b.stat.as_deref() == Some("strength") {
                    base += b.value * self.c.t.AP_PER_STRENGTH[&self.c.spec.class_name];
                }
                if b.ap_pct != 0.0 {
                    base *= 1.0 + b.ap_pct;
                }
            }
        }
        base
    }

    fn sp(&self, school: &str) -> f64 {
        let mut base = self.st("spellPower") + self.st(&format!("{school}Power"));
        let school_power = format!("{school}Power");
        for b in self.buffs.values() {
            if b.until > self.t {
                if b.stat.as_deref() == Some("spellPower") || b.stat.as_deref() == Some(school_power.as_str()) {
                    base += b.value;
                }
                if b.sp_pct != 0.0 {
                    base *= 1.0 + b.sp_pct;
                }
            }
        }
        base
    }

    fn crit_chance(&self, kind: &str, ability: Option<&str>, school: Option<&str>) -> f64 {
        let c = self.c;
        let mut crit;
        if kind == "spell" {
            let school = school.unwrap_or("None");
            crit = self.st("spellCrit") + c.mod_(&format!("crit_school:{school}"));
            if let Some((stacks, _)) = self.combustion {
                if school == "fire" {
                    crit += 10.0 * stacks as f64;
                }
            }
            if school == "frost" && self.debuff_active("Winter's Chill") {
                crit += 2.0 * self.debuffs["Winter's Chill"].stacks as f64;
            }
            if ability == Some("Ice Lance") && c.flag("shatter") != 0.0 && self.buff_active("Fingers of Frost") {
                crit += c.flag("shatter") * 100.0;
            }
            crit -= 2.1;
        } else if kind == "ranged" {
            crit = self.st("rangedCrit") - 4.8;
        } else {
            crit = self.st("meleeCrit") - 4.8;
            if c.flag("weaponmaster") != 0.0 && matches!(weapon_type(&c.mh), Some("Axe") | Some("Polearm")) {
                crit += c.flag("weaponmaster") * 100.0;
            }
        }
        if c.flag("moonkin") != 0.0 {
            crit += c.flag("moonkin") * 100.0;
        }
        if ability == Some("Shadow Word: Death") && c.flag("early_demise") != 0.0 && self.t >= self.execute_at {
            crit += c.flag("early_demise");
        }
        if let Some(a) = ability {
            crit += c.mod_(&format!("crit_ability:{a}"));
        }
        if let Some(b) = self.buffs.get("Elune's Light") {
            if b.until > self.t {
                crit += 10.0;
            }
        }
        if let Some(b) = self.buffs.get("Berserk") {
            if b.until > self.t && matches!(ability, Some("Shred") | Some("Claw") | Some("Mangle")) {
                crit += 100.0;
            }
        }
        crit.clamp(0.0, 100.0) / 100.0
    }

    fn crit_multiplier(&self, kind: &str, ability: &str, school: &str) -> f64 {
        let c = self.c;
        if kind == "spell" {
            let mut bonus = 0.5;
            bonus += c.mod_(&format!("crit_dmg_school:{school}")) * 0.5;
            if c.flag("shadowform") != 0.0 && school == "shadow" {
                bonus += 0.5;
            }
            if c.mod_("crit_dmg_destruction") != 0.0 && ["Shadow Bolt", "Immolate", "Conflagrate", "Shadowburn", "Searing Pain"].contains(&ability) {
                bonus += c.mod_("crit_dmg_destruction") * 0.5;
            }
            return 1.0 + bonus;
        }
        let mut bonus = 1.0;
        let white = ["Melee (Main-Hand)", "Melee (Off-Hand)", "Auto Shot", "Melee (Extra Attack)", "Windfury Attack"].contains(&ability);
        if !white {
            if kind == "ranged" {
                bonus += c.mod_("crit_dmg_school:ranged");
            } else {
                bonus += c.mod_("crit_dmg_school:physical_ability");
            }
            if ["Sinister Strike", "Backstab", "Hemorrhage"].contains(&ability) {
                bonus += c.mod_("crit_dmg_builder");
            }
        }
        1.0 + bonus
    }

    /// Forever lets periodic damage (spell DoTs and bleeds) roll crits, unlike Classic. Sourced
    /// from tooltip language: Nature's Grace and Primal Fury both explicitly say "non-periodic"
    /// crits (a qualifier that's meaningless unless periodic crits are the alternative), and
    /// Pandemic's tooltip is "increases the critical strike damage bonus of [DoTs]" -- only
    /// sensible if those DoTs already have a crit damage bonus to increase. This sim doesn't
    /// roll each tick individually; the flat per-tick damage already stored on dot instances is
    /// scaled by the expected value of crit chance * crit bonus, the same averaging approach
    /// used elsewhere in this engine. Ignite is excluded by construction (it's built directly
    /// from a share of the triggering crit, not through this path).
    fn periodic_crit_mult(&self, ability: &str, school: &str, bleed: bool, extra_bonus: f64) -> f64 {
        let kind = if bleed { "melee" } else { "spell" };
        let crit_chance = self.crit_chance(kind, Some(ability), Some(school));
        let crit_bonus = self.crit_multiplier(kind, ability, school) - 1.0 + extra_bonus;
        1.0 + crit_chance * crit_bonus
    }

    // ---- attack tables ---------------------------------------------------
    fn melee_outcome(&mut self, hand: Hand, white: bool, ability: Option<&str>, no_dodge: bool) -> (Outcome, f64) {
        let c = self.c;
        let level5 = c.t.LEVEL * 5.0;
        let skill = match hand {
            Hand::None => level5,
            h => {
                let item = c.hand_item(h).unwrap();
                if item.is_empty() { level5 } else { c.skill(item) }
            }
        };
        let delta = c.t.TARGET_DEFENSE - skill;
        let base_delta = c.t.TARGET_DEFENSE - level5;
        let (mut miss, suppression) = if delta > 10.0 { (0.05 + delta * 0.002, (delta - 10.0) * 0.002) } else { (0.05 + delta * 0.001, 0.0) };
        let mut hit_pct = self.st("meleeHit") / 100.0;
        if white && c.dual_wield {
            miss += 0.19;
        }
        if hand == Hand::Off && c.spec.class_name == "Warrior" {
            hit_pct += c.mod_("dw_hit") / 100.0;
        }
        if let Some(ab) = ability {
            if !white {
                hit_pct += c.mod_(&format!("hit_ability:{ab}")) / 100.0;
            }
        }
        miss = (miss - (hit_pct - suppression).max(0.0)).max(0.0);
        let dodge = if no_dodge { 0.0 } else { (0.05 + delta * 0.001 - c.flag("expertise") * 0.02).max(0.0) };
        let front = c.spec.role == "tank";
        let parry = if front && !no_dodge { 0.05 + base_delta * 0.006 } else { 0.0 };
        let block = if front && !no_dodge { 0.05 } else { 0.0 };
        let glance = if white { 0.1 + base_delta * 0.02 } else { 0.0 };
        let mut crit = self.crit_chance("melee", if white { None } else { ability }, None);
        let roll = self.rng.random();
        let mut acc = miss;
        if roll < acc {
            return (Outcome::Miss, 0.0);
        }
        acc += dodge;
        if roll < acc {
            return (Outcome::Dodge, 0.0);
        }
        acc += parry;
        if roll < acc {
            return (Outcome::Parry, 0.0);
        }
        acc += glance;
        if roll < acc {
            let lo = (1.3 - 0.05 * delta).clamp(0.01, 0.91);
            let hi = (1.2 - 0.03 * delta).clamp(0.2, 0.99);
            return (Outcome::Glance, self.rng.uniform(lo, hi));
        }
        acc += block;
        if roll < acc {
            return (Outcome::Block, 1.0);
        }
        if self.next_crit && !white {
            crit = 1.0;
        }
        acc += crit;
        if roll < acc {
            return (Outcome::Crit, self.crit_multiplier("melee", ability.unwrap_or("Melee (Main-Hand)"), "physical"));
        }
        (Outcome::Hit, 1.0)
    }

    fn ranged_outcome(&mut self, ability: Option<&str>) -> (Outcome, f64) {
        let c = self.c;
        let skill = c.skill(&c.ranged);
        let delta = c.t.TARGET_DEFENSE - skill;
        let mut miss = if delta > 10.0 { 0.05 + delta * 0.002 } else { 0.05 + delta * 0.001 };
        let suppression = if delta > 10.0 { (delta - 10.0) * 0.002 } else { 0.0 };
        miss = (miss - (self.st("rangedHit") / 100.0 - suppression).max(0.0)).max(0.0);
        let roll = self.rng.random();
        if roll < miss {
            return (Outcome::Miss, 0.0);
        }
        let crit = self.crit_chance("ranged", ability, None);
        if roll < miss + crit {
            return (Outcome::Crit, self.crit_multiplier("ranged", ability.unwrap_or("Auto Shot"), "physical"));
        }
        (Outcome::Hit, 1.0)
    }

    fn spell_outcome(&mut self, ability: &str, school: &str, can_crit: bool) -> (Outcome, f64) {
        let c = self.c;
        let buff_hit: f64 = self.buffs.values().filter(|b| b.stat.as_deref() == Some("spellHit") && b.until > self.t).map(|b| b.value).sum();
        let hit = (0.83 + (self.st("spellHit") + c.mod_(&format!("spell_hit_school:{school}")) + buff_hit) / 100.0).min(0.99);
        let roll = self.rng.random();
        if roll >= hit {
            if c.flag("enigma_hit") != 0.0 {
                self.add_buff("Enigma Vestments", 20.0, Buff { stat: Some("spellHit".into()), value: c.flag("enigma_hit"), ..Default::default() });
            }
            return (Outcome::Miss, 0.0);
        }
        let mut crit = if can_crit { self.crit_chance("spell", Some(ability), Some(school)) } else { 0.0 };
        if self.next_crit && can_crit {
            crit = 1.0;
        }
        if self.rng.random() < crit {
            return (Outcome::Crit, self.crit_multiplier("spell", ability, school));
        }
        (Outcome::Hit, 1.0)
    }

    // ---- damage ---------------------------------------------------------
    fn multiplier(&self, ability: &str, school: &str, kind: &str, periodic: bool, white: bool) -> f64 {
        let c = self.c;
        let mut m = 1.0;
        m *= 1.0 + c.mod_("dmg_all");
        if SPELL_SCHOOLS.contains(&school) {
            m *= 1.0 + c.mod_(&format!("dmg_school:{school}"));
        }
        if kind == "ranged" {
            m *= 1.0 + c.mod_("dmg_school:ranged");
        }
        if kind == "melee" || kind == "pet" || school == "physical" {
            m *= 1.0 + c.mod_("dmg_school:physical");
            if c.flag("two_hand_spec") != 0.0 && c.two_hand {
                m *= 1.0 + c.flag("two_hand_spec");
            }
            if self.t < self.enrage_until {
                m *= 1.10;
            }
        }
        if periodic {
            m *= 1.0 + c.mod_("dmg_periodic");
        }
        if c.mod_("dmg_destruction") != 0.0 && ["Shadow Bolt", "Immolate", "Conflagrate", "Shadowburn", "Searing Pain"].contains(&ability) {
            m *= 1.0 + c.mod_("dmg_destruction");
        }
        let stance = c.t.stance_mod(&c.spec.stance_or_form());
        m *= stance.damage;
        let creature = if c.racial_enabled { c.racial.creature_damage.get(&c.boss_type).copied().unwrap_or(0.0) } else { 0.0 };
        m *= 1.0 + creature;
        m *= 1.0 + c.mod_(&format!("creature_dmg:{}", c.boss_type));
        if c.flag("murder") != 0.0 && ["humanoid", "giant"].contains(&c.boss_type.as_str()) {
            m *= 1.0 + c.flag("murder");
        }
        if c.flag("improved_tracking") != 0.0 && ["beast", "demon", "dragonkin", "elemental", "giant", "humanoid", "undead"].contains(&c.boss_type.as_str()) {
            m *= 1.0 + c.flag("improved_tracking");
        }
        for b in self.buffs.values() {
            if b.until <= self.t {
                continue;
            }
            if b.damage_mult != 0.0 {
                m *= 1.0 + b.damage_mult;
            }
            if let Some((s, v)) = &b.damage_mult_school {
                if s == school {
                    m *= 1.0 + v;
                }
            }
        }
        if let Some((s, v)) = &self.sacrificed {
            if s == school {
                m *= 1.0 + v;
            }
        }
        if c.flag("master_demonologist") != 0.0 && self.sacrificed.is_none() {
            if let Some(pet) = c.pet.as_ref() {
                let fam = pet.family();
                if (fam == "imp" && school == "fire") || (fam == "succubus" && school == "shadow") {
                    m *= 1.0 + c.flag("master_demonologist");
                }
            }
        }
        if c.flag("soul_link") != 0.0 && c.pet.is_some() && self.sacrificed.is_none() {
            m *= 1.0 + c.flag("soul_link");
        }
        if c.flag("shadowform") != 0.0 && school == "shadow" {
            m *= 1.10;
        }
        if school == "shadow" && self.debuff_active("Shadow Weaving") {
            m *= 1.0 + 0.02 * self.debuffs["Shadow Weaving"].stacks as f64;
        }
        if school == "shadow" && self.debuff_active("Improved Shadow Bolt") {
            m *= 1.20;
        }
        if school == "fire" && self.debuff_active("Improved Scorch") {
            m *= 1.0 + 0.03 * self.debuffs["Improved Scorch"].stacks as f64;
        }
        if school == "nature" && self.debuff_active("Stormstrike") {
            m *= 1.20;
        }
        if school == "shadow" && self.debuff_active("Shadow and Flame (shadow)") {
            m *= 1.10;
        }
        if school == "fire" && self.debuff_active("Shadow and Flame (fire)") {
            m *= 1.10;
        }
        if ability == "Rupture" && self.debuff_active("Hemorrhage") {
            m *= 1.15;
        }
        if ability == "Lava Burst" && self.dots.get("Flame Shock").is_some_and(|d| d.remaining > 0) {
            m *= 1.20;
        }
        if ability == "Incinerate" && self.dots.get("Immolate").is_some_and(|d| d.remaining > 0) {
            m *= 1.25;
        }
        if c.flag("arcane_blast") != 0.0 && ability != "Arcane Blast" {
            let stacks = self.buffs.get("Arcane Blast").filter(|b| b.until > self.t).map_or(0, |b| b.stacks);
            if stacks > 0 {
                m *= 1.0 + 0.10 * stacks as f64;
            }
        }
        if c.flag("rend_and_tear") != 0.0 && kind == "melee" && !white && self.dots.iter().any(|(d, dot)| dot.remaining > 0 && c.t.ABILITIES.get(d).is_some_and(|a| a.bleed)) {
            m *= 1.0 + c.flag("rend_and_tear");
        }
        if c.flag("quietus") != 0.0 && ["Sinister Strike", "Hemorrhage"].contains(&ability) && self.t >= self.duration * 0.65 {
            m *= 1.0 + c.flag("quietus");
        }
        if self.eureka > 0 && !white && kind != "pet" && !periodic {
            m *= 1.10;
        }
        if c.flag("lone_wolf") != 0.0 && (c.pet.is_none() || self.pet_state.as_ref().is_some_and(|p| self.t >= p.active_until)) {
            m *= 1.0 + c.flag("lone_wolf");
        }
        m
    }

    fn armor_mult(&self) -> f64 {
        let c = self.c;
        let mut armor = c.armor_after_debuffs();
        if self.debuff_active("Spider's Kiss") {
            armor = (armor - 100.0).max(0.0);
        }
        let mut pen = c.flag("armor_pen_pct");
        if c.flag("weaponmaster") != 0.0 && matches!(weapon_type(&c.mh), Some("Mace") | Some("Staff")) {
            pen += c.flag("weaponmaster") * 3.0;
        }
        if c.flag("hack_and_slash") != 0.0 && weapon_type(&c.mh) == Some("Mace") {
            pen += 0.15;
        }
        armor *= 1.0 - pen.min(1.0);
        1.0 - armor / (armor + 400.0 + 85.0 * c.t.LEVEL)
    }

    #[allow(clippy::too_many_arguments)]
    fn deal(&mut self, name: &str, amount: f64, school: &str, kind: &str, white: bool, periodic: bool, threat_mult: f64, flat_threat: f64, outcome: Outcome, mult: f64) -> f64 {
        if outcome.avoided() {
            let r = self.row(name);
            if outcome == Outcome::Miss { r.misses += 1.0; } else { r.dodges += 1.0; }
            self.record(name, outcome.as_str(), 0.0);
            return 0.0;
        }
        let mut dmg = amount * mult * self.multiplier(name, school, kind, periodic, white);
        if school == "physical" && !(periodic && (self.dots.get(name).is_some_and(|d| d.bleed) || self.c.t.ABILITIES.get(name).is_some_and(|a| a.bleed))) {
            dmg *= self.armor_mult();
        }
        let th_mult = self.threat_multiplier(Some(school)) * (1.0 + self.c.mod_(&format!("threat_ability:{name}")));
        let r = self.row(name);
        if outcome == Outcome::Glance { r.glances += 1.0; }
        if outcome == Outcome::Crit { r.crits += 1.0; }
        r.hits += 1.0;
        r.damage += dmg;
        let th = (dmg * threat_mult + flat_threat) * th_mult;
        r.threat += th;
        self.total += dmg;
        self.threat += th;
        self.record(name, outcome.as_str(), dmg);
        dmg
    }

    fn threat_multiplier(&self, school: Option<&str>) -> f64 {
        let c = self.c;
        let mut m = c.t.stance_mod(&c.spec.stance_or_form()).threat * c.t.CLASS_THREAT.get(&c.spec.class_name).copied().unwrap_or(1.0);
        if c.spec.stance.as_deref() == Some("defensive") {
            m *= 1.0 + c.flag("defiance");
        }
        m *= 1.0 + c.mod_("threat_mult");
        if let Some(s) = school {
            m *= 1.0 + c.mod_(&format!("threat_school:{s}"));
        }
        m *= 1.0 - c.threat_reduction;
        m
    }

    // ---- resources -------------------------------------------------------
    fn gain_rage(&mut self, amount: f64) {
        let before = self.rage;
        self.rage = self.max_rage.min(self.rage + amount);
        let threat = (self.rage - before) * 5.0;
        self.threat += threat;
        self.row("Rage gains").threat += threat;
    }

    fn white_rage(&mut self, hand: Hand, damage: f64) {
        if self.c.spec.resource == "Rage" {
            let mut gained = damage * 7.5 / self.c.t.RAGE_CONVERSION_60;
            if hand == Hand::Off { gained *= 1.0 + self.c.flag("dw_rage"); }
            self.rage = self.max_rage.min(self.rage + gained);
        }
    }

    fn gain_energy(&mut self, amount: f64) {
        self.energy = self.max_energy.min(self.energy + amount);
    }

    fn gain_mana(&mut self, amount: f64) {
        self.mana = self.max_mana.min(self.mana + amount);
    }

    pub fn resource(&self) -> f64 {
        match self.c.spec.resource.as_str() { "Mana" => self.mana, "Energy" => self.energy, _ => self.rage }
    }

    fn spend(&mut self, amount: f64) {
        match self.c.spec.resource.as_str() {
            "Mana" => {
                if self.clearcast {
                    self.clearcast = false;
                    return;
                }
                self.mana -= amount;
                self.last_cast_time = self.t;
            }
            "Energy" => self.energy -= amount,
            _ => self.rage -= amount,
        }
    }

    // ---- weapon damage ---------------------------------------------------
    fn weapon_damage(&mut self, item: &Item, normalized: bool, ranged: bool, bonus_ap: f64) -> f64 {
        let (lo, hi) = (item.dmg_min(), item.dmg_max());
        let mut speed = if normalized { normalized_speed(item) } else { item.speed_or(2.0) };
        if self.c.spec.form_is("cat") || self.c.spec.form_is("bear") {
            speed = item.speed_or(1.0);
        }
        let ap = self.ap(ranged) + bonus_ap;
        let mut dmg = self.rng.uniform(lo, hi) + ap / 14.0 * speed;
        if ranged {
            dmg += self.st("rangedDamage");
        }
        dmg
    }

    // ---- procs -----------------------------------------------------------
    fn on_weapon_hit(&mut self, hand: Hand, white: bool, ability_name: &str, damage: f64) {
        let c = self.c;
        let hand_item = c.hand_item(hand).filter(|i| !i.is_empty());
        let speed = hand_item.map_or(2.0, |i| i.speed_or(2.0));
        let is_extra = ability_name == "Melee (Extra Attack)" || ability_name == "Windfury Attack";
        if c.spec.resource == "Rage" {
            if white {
                self.white_rage(hand, damage);
            }
            if c.flag("unbridled_wrath") != 0.0 && self.rng.random() < c.flag("unbridled_wrath") {
                self.gain_rage(if c.two_hand { 2.0 } else { 1.0 });
            }
        }
        let hand_slot = if hand == Hand::Off { "off_hand" } else { "main_hand" };
        if c.crusader_hands.contains(hand_slot) && self.rng.random() < speed / 60.0 {
            self.add_buff(&format!("Crusader ({})", hand_slot.replace('_', " ")), 15.0, Buff { stat: Some("strength".into()), value: 100.0, ..Default::default() });
        }
        if white && c.flag("shadowcraft_energy") != 0.0 && self.rng.random() < c.flag("shadowcraft_energy") * speed / 60.0 {
            self.gain_energy(35.0);
            self.row("Shadowcraft Energize").casts += 1.0;
        }
        if c.flag("bloodfang_proc") != 0.0 && self.rng.random() < c.flag("bloodfang_proc") * speed / 60.0 {
            let total = self.rng.uniform(283.0, 317.0);
            self.dots.insert("Bloodfang".into(), Dot { next: self.t + 1.0, remaining: 6, tick: total / 6.0, tick_len: 1.0, school: "physical".into(), bleed: false, stacks: 1 });
        }
        if c.flag("stormshroud_dmg") != 0.0 && self.rng.random() < c.flag("stormshroud_dmg") {
            self.row("Stormshroud").casts += 1.0;
            let amt = self.rng.uniform(15.0, 25.0);
            self.deal("Stormshroud", amt, "nature", "spell", false, false, 1.0, 0.0, Outcome::Hit, 1.0);
        }
        if c.flag("stormshroud_energy") != 0.0 && self.rng.random() < c.flag("stormshroud_energy") {
            self.gain_energy(30.0);
        }
        if c.flag("spiders_kiss") != 0.0 && self.rng.random() < c.flag("spiders_kiss") {
            self.add_debuff("Spider's Kiss", 10.0, None);
        }
        for proc in &c.item_procs {
            if proc.trigger == "weapon" {
                // Python: `item is not hand_item` – the proc's source item must be the swinging weapon.
                let same = match (proc.item_id, hand_item) { (Some(pid), Some(h)) => h.id == Some(pid), _ => false };
                if proc.item_id.is_some() && !same {
                    continue;
                }
            }
            if proc.trigger == "melee" && is_extra {
                continue;
            }
            let key = &proc.name;
            if proc.icd != 0.0 && self.item_icd.get(key).copied().unwrap_or(-1e9) + proc.icd > self.t {
                continue;
            }
            let chance = match proc.chance { Some(ch) => ch, None => proc.ppm.unwrap_or(0.0) * speed / 60.0 };
            if self.rng.random() >= chance {
                continue;
            }
            self.item_icd.insert(key.clone(), self.t);
            let label = format!("Item - {key}");
            if proc.kind == "damage" {
                let school = proc.school.clone().unwrap();
                let (out, m) = if school != "physical" { self.spell_outcome(&label, &school, false) } else { self.melee_outcome(Hand::None, false, Some(&label), true) };
                self.row(&label).casts += 1.0;
                let kind = if school != "physical" { "spell" } else { "melee" };
                self.deal(&label, proc.amount.unwrap(), &school, kind, false, false, 1.0, 0.0, out, m);
            } else if proc.kind == "buff" {
                self.add_buff(&label, proc.duration.unwrap(), Buff { stat: proc.stat.clone(), value: proc.value.unwrap(), ..Default::default() });
            } else if proc.kind == "extra_attack" && !is_extra {
                self.extra_attack("Melee (Extra Attack)", Hand::Main, 0.0);
            }
        }
        if !is_extra {
            let wm = c.flag("weaponmaster");
            let hs = c.flag("hack_and_slash");
            let kind = hand_item.and_then(weapon_type);
            if wm != 0.0 && kind == Some("Sword") && self.rng.random() < wm {
                self.extra_attack("Melee (Extra Attack)", Hand::Main, 0.0);
            }
            if hs != 0.0 && matches!(kind, Some("Sword") | Some("Axe")) && self.rng.random() < hs {
                self.extra_attack("Melee (Extra Attack)", Hand::Main, 0.0);
            }
            if c.windfury_totem && hand == Hand::Main && self.rng.random() < c.t.WINDFURY_TOTEM.chance && self.t >= self.windfury_lock {
                self.windfury_lock = self.t + 0.1;
                self.extra_attack("Windfury Attack", Hand::Main, c.t.WINDFURY_TOTEM.ap);
            }
            if c.spec.class_name == "Shaman" && hand == Hand::Main && self.rng.random() < c.t.WINDFURY.chance && self.t >= self.windfury_lock {
                self.windfury_lock = self.t + 0.1;
                let bonus = c.t.WINDFURY.ap * (1.0 + c.flag("elemental_weapons"));
                for _ in 0..c.t.WINDFURY.extra_attacks {
                    self.extra_attack("Windfury Attack", Hand::Main, bonus);
                }
            }
        }
        if c.spec.class_name == "Rogue" {
            let mh_poison = if c.spec.id == "rogue-assassination" { "deadly" } else { "instant" };
            let poison = if hand == Hand::Main { mh_poison } else { "instant" };
            let venom_active = self.buff_active("Venom");
            let chance = c.t.POISONS[poison].chance + c.flag("poison_chance") + if venom_active { 0.10 } else { 0.0 };
            if self.rng.random() < chance {
                let venom_dmg = if venom_active { 0.30 } else { 0.0 };
                if poison == "instant" {
                    let (out, m) = self.spell_outcome("Instant Poison", "nature", true);
                    self.row("Instant Poison").casts += 1.0;
                    let p = &c.t.POISONS["instant"];
                    let amt = self.rng.uniform(p.min, p.max) * (1.0 + c.flag("poison_damage") + venom_dmg);
                    self.deal("Instant Poison", amt, "nature", "spell", false, false, 1.0, 0.0, out, m);
                } else {
                    let p = &c.t.POISONS["deadly"];
                    let prev = self.dots.get("Deadly Poison").filter(|d| d.remaining > 0).map_or(0, |d| d.stacks);
                    let stacks = p.max_stacks.min(prev + 1);
                    self.dots.insert("Deadly Poison".into(), Dot { next: self.t + 3.0, remaining: 4, tick: p.tick * (1.0 + c.flag("poison_damage") + venom_dmg), tick_len: 3.0, school: "nature".into(), stacks, bleed: false });
                }
            }
        }
        if c.consumes.contains("dragonbreath_chili") && self.rng.random() < 0.05 {
            self.row("Dragonbreath Chili").casts += 1.0;
            let amt = self.rng.uniform(60.0, 90.0);
            self.deal("Dragonbreath Chili", amt, "fire", "spell", false, false, 1.0, 0.0, Outcome::Hit, 1.0);
        }
        if c.flag("expose_prey") != 0.0 && self.rng.random() < c.flag("expose_prey") {
            self.add_buff("Mongoose Bite Ready", 5.0, Buff::default());
        }
        if c.flag("maelstrom_weapon") != 0.0 && !is_extra && self.rng.random() < 0.20 {
            self.add_buff("Maelstrom Weapon", 30.0, Buff { stacks_max: Some(5), ..Default::default() });
        }
        if self.flurry > 0 && white {
            self.flurry -= 1;
        }
    }

    fn on_crit(&mut self, name: &str, damage: f64, hand: Hand, kind: &str) {
        let c = self.c;
        if kind == "melee" {
            if c.flag("flurry") != 0.0 {
                self.flurry = 3;
            }
            if c.flag("deep_wounds") != 0.0 && hand != Hand::None {
                let hand_item = c.hand_item(hand).unwrap();
                let mut avg = (hand_item.dmg_min() + hand_item.dmg_max()) / 2.0 + self.ap(false) / 14.0 * hand_item.speed_or(2.0);
                if hand == Hand::Off {
                    avg *= 0.5 * (1.0 + c.flag("dw_damage"));
                }
                let tick = avg * c.flag("deep_wounds") / 4.0 * self.periodic_crit_mult("Deep Wounds", "physical", true, 0.0);
                self.dots.insert("Deep Wounds".into(), Dot { next: self.t + 3.0, remaining: 4, tick, tick_len: 3.0, school: "physical".into(), bleed: true, stacks: 1 });
            }
            if c.flag("primal_fury") != 0.0 && c.spec.form_is("bear") {
                self.gain_rage(5.0);
            }
        }
        if kind == "spell" {
            if c.flag("ignite") != 0.0 && self.cur_school == "fire" {
                let amount = damage * c.flag("ignite");
                let t = self.t;
                match self.dots.get_mut("Ignite") {
                    Some(d) if d.remaining > 0 => {
                        d.tick += amount / 2.0;
                        d.remaining = 2;
                        d.next = t + 2.0;
                    }
                    _ => {
                        self.dots.insert("Ignite".into(), Dot { next: t + 2.0, remaining: 2, tick: amount / 2.0, tick_len: 2.0, school: "fire".into(), bleed: false, stacks: 1 });
                    }
                }
            }
            if self.combustion.is_some() && self.cur_school == "fire" {
                let (stacks, crits) = self.combustion.unwrap();
                self.combustion = Some((stacks, crits + 1));
                if crits + 1 >= 4 {
                    self.combustion = None;
                }
            }
            if c.flag("natures_grace") != 0.0 {
                self.add_buff("Nature's Grace", 3.0, Buff { haste: 0.10, ..Default::default() });
            }
            if c.flag("improved_shadow_bolt") != 0.0 && name == "Shadow Bolt" {
                self.add_debuff("Improved Shadow Bolt", 12.0, None);
            }
        }
        if kind == "spell" && c.flag("master_of_elements") != 0.0 {
            let cost = self.cur_cost;
            self.gain_mana(cost * c.flag("master_of_elements"));
        }
    }

    fn extra_attack(&mut self, name: &str, hand: Hand, bonus_ap: f64) -> f64 {
        let (out, m) = self.melee_outcome(hand, true, Some(name), false);
        self.row(name).casts += 1.0;
        let item = self.c.hand_item(hand).unwrap().clone();
        let raw = if out != Outcome::Miss { self.weapon_damage(&item, false, false, bonus_ap) } else { 0.0 };
        if matches!(out, Outcome::Dodge | Outcome::Parry) {
            self.white_rage(hand, raw * self.multiplier(name, "physical", "melee", false, true) * self.armor_mult());
        }
        let dmg = self.deal(name, raw, "physical", "melee", true, false, 1.0, 0.0, out, m);
        if dmg != 0.0 {
            self.on_weapon_hit(hand, true, name, dmg);
            if out == Outcome::Crit {
                self.on_crit(name, dmg, hand, "melee");
            }
        }
        dmg
    }

    fn touch_of_the_grave(&mut self) {
        let c = self.c;
        if c.race == "Undead" && c.racial_enabled {
            let tg = c.racial.touch_of_the_grave.clone().unwrap_or_default();
            if self.rng.random() < tg.chance {
                self.row("Touch of the Grave").casts += 1.0;
                let amt = self.health_max * tg.health_fraction;
                self.deal("Touch of the Grave", amt, "shadow", "spell", false, false, 1.0, 0.0, Outcome::Hit, 1.0);
            }
        }
    }

    // ---- swings ----------------------------------------------------------
    fn swing(&mut self, hand: Hand) {
        let c = self.c;
        let name = if hand == Hand::Main { "Melee (Main-Hand)" } else { "Melee (Off-Hand)" };
        let item = c.hand_item(hand).unwrap().clone();
        let queued = if hand == Hand::Main { self.queued_swing.clone() } else { None };
        if let Some(queued) = queued {
            let a = c.actions[&queued].clone();
            let cost = self.cost(&queued);
            if self.resource() + EPS >= cost {
                self.queued_swing = None;
                self.spend(cost);
                let (out, m) = self.melee_outcome(hand, false, Some(&queued), false);
                self.row(&queued).casts += 1.0;
                let mut dmg = 0.0;
                if !out.avoided() {
                    dmg = self.weapon_damage(&item, false, false, 0.0) + a.weapon_flat();
                }
                let cleave_hits = if queued == "Cleave" { (c.targets as f64).min(2.0) } else { 1.0 };
                dmg = self.deal(&queued, dmg, "physical", "melee", false, false, a.threat_mult(), a.flat_threat * cleave_hits, out, m * a.mult * cleave_hits);
                if out.avoided() && self.c.spec.resource == "Rage" {
                    self.rage += cost * 0.8;
                }
                if dmg != 0.0 {
                    self.on_weapon_hit(hand, false, &queued, dmg);
                    if out == Outcome::Crit {
                        self.on_crit(&queued, dmg, hand, "melee");
                    }
                }
                self.touch_of_the_grave();
                return;
            }
            self.queued_swing = None;
        }
        let (out, m) = self.melee_outcome(hand, true, Some(name), false);
        self.row(name).casts += 1.0;
        if out == Outcome::Dodge {
            self.dodged_recently = self.t;
        }
        let mut dmg = 0.0;
        if out != Outcome::Miss {
            dmg = self.weapon_damage(&item, false, false, 0.0);
            if hand == Hand::Off {
                dmg *= 0.5 * (1.0 + c.flag("dw_damage"));
            }
        }
        if matches!(out, Outcome::Dodge | Outcome::Parry) {
            self.white_rage(hand, dmg * self.multiplier(name, "physical", "melee", false, true) * self.armor_mult());
        }
        dmg = self.deal(name, dmg, "physical", "melee", true, false, 1.0, 0.0, out, m);
        if dmg != 0.0 {
            self.on_weapon_hit(hand, true, name, dmg);
            if out == Outcome::Crit {
                self.on_crit(name, dmg, hand, "melee");
            }
        }
        self.touch_of_the_grave();
    }

    fn auto_shot(&mut self) {
        let c = self.c;
        let (out, m) = self.ranged_outcome(None);
        self.row("Auto Shot").casts += 1.0;
        let ranged = c.ranged.clone();
        let raw = if out != Outcome::Miss { self.weapon_damage(&ranged, false, true, 0.0) } else { 0.0 };
        let dmg = self.deal("Auto Shot", raw, "physical", "ranged", true, false, 1.0, 0.0, out, m);
        self.touch_of_the_grave();
        if dmg != 0.0 {
            self.on_ranged_damage(out);
        }
        if dmg != 0.0 {
            for proc in &c.item_procs {
                if proc.trigger == "weapon" && proc.item_id.is_some() && proc.item_id == c.ranged.id && self.rng.random() < proc.ppm.unwrap_or(1.0) * c.ranged.speed_or(2.8) / 60.0 {
                    let label = format!("Item - {}", proc.name);
                    self.row(&label).casts += 1.0;
                    let school = proc.school.clone().unwrap_or_else(|| "physical".into());
                    self.deal(&label, proc.amount.unwrap_or(0.0), &school, "spell", false, false, 1.0, 0.0, Outcome::Hit, 1.0);
                }
            }
        }
    }

    /// Set procs that trigger on landed ranged damage.
    fn on_ranged_damage(&mut self, out: Outcome) {
        let c = self.c;
        if c.flag("beaststalker_mana") != 0.0 && self.rng.random() < c.flag("beaststalker_mana") {
            self.gain_mana(200.0);
        }
        if out == Outcome::Crit && c.flag("cryptstalker_mana") != 0.0 {
            self.gain_mana(c.flag("cryptstalker_mana"));
        }
        if c.flag("dragonstalker_ew") != 0.0 && self.rng.random() < c.flag("dragonstalker_ew") * c.ranged.speed_or(2.8) / 60.0 {
            self.add_buff("Expose Weakness", 7.0, Buff { stat: Some("rangedAttackPower".into()), value: 450.0, ..Default::default() });
        }
    }

    // ---- abilities -------------------------------------------------------
    fn check(&self, cond: &Cond, name: &str) -> bool {
        match cond {
            Cond::True => true,
            Cond::False => false,
            Cond::Or(xs) => xs.iter().any(|x| self.check(x, name)),
            Cond::And(xs) => xs.iter().all(|x| self.check(x, name)),
            Cond::Not(x) => !self.check(x, name),
            Cond::Execute => self.t >= self.execute_at,
            Cond::Moving => false,
            Cond::DotMissing => {
                let active = self.dots.get(name).is_some_and(|d| d.remaining > 0 && d.next - self.t < 1e9);
                let a = &self.c.actions[name];
                if a.spreadable && self.c.targets > 1 {
                    let extra_active = self.dots_extra.iter().filter(|(n, d)| n == name && d.remaining > 0).count() as i64;
                    (if active { 1 } else { 0 }) + extra_active < self.c.targets
                } else {
                    !active
                }
            }
            Cond::BuffMissing => !self.buff_active(name),
            Cond::NoDagger => weapon_type(&self.c.mh) != Some("Dagger"),
            Cond::NoShred => !self.c.actions.contains_key("Shred"),
            Cond::Targets(op, num) => compare(op, self.c.targets as f64, *num),
            Cond::Resource(res, op, num) => {
                let val = match res.as_str() { "rage" => self.rage, "energy" => self.energy, "mana" => self.mana, _ => self.cp as f64 };
                compare(op, val, *num)
            }
            Cond::Keyed(kind, key, op, num) => {
                let val = match kind.as_str() {
                    "dot" => self.dots.get(key).filter(|d| d.remaining > 0).map_or(0.0, |d| d.remaining as f64 * d.tick_len),
                    "debuff" => self.debuffs.get(key).map_or(0.0, |b| (b.until - self.t).max(0.0)),
                    "cd" => (self.cooldowns.get(key).copied().unwrap_or(0.0) - self.t).max(0.0),
                    "buff" => self.buffs.get(key).map_or(0.0, |b| (b.until - self.t).max(0.0)),
                    "buffstacks" => self.buffs.get(key).filter(|b| b.until > self.t).map_or(0.0, |b| b.stacks as f64),
                    _ => self.debuffs.get(key).filter(|b| b.until > self.t).map_or(0.0, |b| b.stacks as f64),
                };
                compare(op, val, *num)
            }
        }
    }

    fn ready(&self, name: &str, ignore_resource: bool) -> bool {
        let c = self.c;
        let a = &c.actions[name];
        if self.cooldowns.get(name).copied().unwrap_or(0.0) > self.t + EPS {
            return false;
        }
        if let Some(s) = &a.shared_cd {
            if self.cooldowns.get(&format!("shared:{s}")).copied().unwrap_or(0.0) > self.t + EPS {
                return false;
            }
        }
        if a.execute && self.t < self.execute_at {
            return false;
        }
        match a.requires.as_deref() {
            Some("dodge") if self.t - self.dodged_recently > 5.0 => return false,
            Some("block_dodge_parry") if self.t - self.avoided_recently > 5.0 => return false,
            Some("dagger") if weapon_type(&c.mh) != Some("Dagger") => return false,
            Some(r) if r.starts_with("dodge_or_buff:") => {
                let buff_name = &r["dodge_or_buff:".len()..];
                if !(self.t - self.dodged_recently <= 5.0 || self.buff_active(buff_name)) {
                    return false;
                }
            }
            Some(r) if r.starts_with("dot:")
                && !self.dots.get(&r[4..]).is_some_and(|d| d.remaining > 0) => {
                    return false;
                }
            _ => {}
        }
        if a.finisher.is_some() && self.cp <= 0 {
            return false;
        }
        if a.kind == "swing" && self.queued_swing.is_some() {
            return false;
        }
        let castable = c.spec.resource == "Mana" && self.clearcast && ["direct", "dot", "channel", "direct_dot"].contains(&a.kind.as_str());
        if !ignore_resource && self.resource() + EPS < self.cost(name) && !castable {
            return false;
        }
        true
    }

    fn cost(&self, name: &str) -> f64 {
        let mut cost = self.c.actions[name].cost;
        if self.buff_active("Arcane Power") && self.c.spec.resource == "Mana" {
            cost *= 1.3;
        }
        if name == "Arcane Blast" {
            let stacks = self.buffs.get("Arcane Blast").filter(|b| b.until > self.t).map_or(0, |b| b.stacks);
            cost *= 1.0 + 1.75 * stacks as f64;
        }
        if name == "Arcane Missiles" && self.buff_active("Missile Barrage") {
            cost = 0.0;
        }
        if name == "Hemorrhage" || name == "Backstab" {
            let stacks = self.buffs.get("Thousand Cuts").filter(|b| b.until > self.t).map_or(0, |b| b.stacks);
            if stacks > 0 {
                cost = (cost - 3.0 * stacks as f64).max(0.0);
            }
        }
        cost
    }

    fn choose(&mut self) -> Option<String> {
        self.blocked_by_resource = false;
        for (name, cond) in &self.c.rotation_conds {
            let a = &self.c.actions[name];
            if a.kind == "buff" && a.no_effect.is_some() {
                continue;
            }
            if !self.ready(name, true) {
                continue;
            }
            if !self.check(cond, name) {
                continue;
            }
            if self.resource() + EPS < self.cost(name) && !(self.c.spec.resource == "Mana" && self.clearcast) {
                self.blocked_by_resource = true;
                continue;
            }
            return Some(name.clone());
        }
        None
    }

    fn use_offgcd(&mut self) {
        let c = self.c;
        if c.racial_enabled {
            if let Some(r) = &c.racial.active {
                if self.t >= self.racial_next && (r.name != "Stoneform" || (c.spec.role == "tank" && self.t + EPS >= self.gcd_until && self.cast.is_none())) {
                    self.racial_next = self.t + r.cooldown;
                    if r.name == "Stoneform" {
                        self.add_buff("Stoneform", r.duration, Buff::default());
                        self.gcd_until = self.t + c.t.GCD;
                        self.row("Stoneform").casts += 1.0;
                    } else if r.crit != 0.0 {
                        self.add_buff(&r.name, r.duration, Buff::default());
                    } else if r.haste != 0.0 {
                        self.add_buff(&r.name, r.duration, Buff { haste: r.haste, ..Default::default() });
                    } else if r.ap_pct != 0.0 {
                        self.add_buff(&r.name, r.duration, Buff { ap_pct: r.ap_pct, sp_pct: r.sp_pct, ..Default::default() });
                    } else if r.charges != 0 {
                        self.eureka = r.charges;
                    }
                    self.record(&r.name, "activated", 0.0);
                }
            }
        }
        let names: Vec<String> = c.actions.keys().cloned().collect();
        for name in names {
            let a = c.actions[&name].clone();
            if !a.off_gcd && a.kind != "item_use" {
                continue;
            }
            if self.cooldowns.get(&name).copied().unwrap_or(0.0) > self.t + EPS {
                continue;
            }
            if let Some(s) = &a.shared_cd {
                if self.cooldowns.get(&format!("shared:{s}")).copied().unwrap_or(0.0) > self.t + EPS {
                    continue;
                }
            }
            if let Some(cond) = c.rotation_last.get(&name) {
                if !self.check(cond, &name) {
                    continue;
                }
            }
            if a.kind == "item_use" {
                let u = a.item_use.clone().unwrap();
                if u.stat == "mana" && self.max_mana - self.mana < u.value {
                    continue;
                }
                if u.stat == "damage" {
                    let school = u.school.clone().unwrap_or_else(|| "physical".into());
                    let (out, m) = self.spell_outcome(&name, &school, false);
                    self.row(&name).casts += 1.0;
                    self.deal(&name, u.value, &school, "spell", false, false, 1.0, 0.0, out, m);
                } else if u.stat == "mana" {
                    self.gain_mana(u.value);
                    self.row(&name).casts += 1.0;
                } else {
                    self.add_buff(&name, u.duration, Buff { stat: Some(u.stat.clone()), value: u.value, ..Default::default() });
                    self.row(&name).casts += 1.0;
                }
                self.cooldowns.insert(name.clone(), self.t + a.cooldown);
                self.record(&name, "activated", 0.0);
                continue;
            }
            if let Some((lo, hi)) = a.mana {
                if self.max_mana - self.mana < 1500.0 {
                    continue;
                }
                let v = self.rng.uniform(lo, hi);
                self.gain_mana(v);
                self.cooldowns.insert(name.clone(), self.t + a.cooldown);
                if let Some(s) = &a.shared_cd {
                    self.cooldowns.insert(format!("shared:{s}"), self.t + a.cooldown);
                }
                self.row(&name).casts += 1.0;
                self.record(&name, "activated", 0.0);
                continue;
            }
            if a.kind == "buff" && a.rage.is_some() && name == "Mighty Rage Potion" {
                if self.rage > 30.0 {
                    continue;
                }
                let (lo, hi) = a.rage_range().unwrap();
                let v = self.rng.uniform(lo, hi);
                self.gain_rage(v);
                self.add_buff(&name, a.duration.unwrap_or(0.0), Buff { stat: Some("strength".into()), value: a.strength.unwrap_or(0.0), ..Default::default() });
                self.cooldowns.insert(name.clone(), self.t + a.cooldown);
                self.cooldowns.insert("shared:potion".into(), self.t + a.cooldown);
                self.row(&name).casts += 1.0;
                continue;
            }
            if let Some(e) = a.energy {
                if self.energy > 20.0 {
                    continue;
                }
                self.gain_energy(e);
                self.cooldowns.insert(name.clone(), self.t + a.cooldown);
                self.row(&name).casts += 1.0;
                continue;
            }
            if name == "Goblin Sapper Charge" {
                self.row(&name).casts += 1.0;
                let (lo, hi) = a.base.unwrap();
                let v = self.rng.uniform(lo, hi);
                self.deal(&name, v, "fire", "spell", false, false, 1.0, 0.0, Outcome::Hit, 1.0);
                self.cooldowns.insert(name.clone(), self.t + a.cooldown);
                continue;
            }
            if name == "Bloodrage" {
                if self.rage >= 60.0 {
                    continue;
                }
                let mult = 1.0 + c.flag("improved_bloodrage");
                self.gain_rage(a.rage_value().unwrap_or(0.0) * mult);
                self.buffs.insert("Bloodrage".into(), Buff { until: self.t + 10.0, tick: a.rage_over_time.map_or(0.0, |r| r.0) * mult, next: self.t + 1.0, ..Default::default() });
                self.cooldowns.insert(name.clone(), self.t + a.cooldown);
                self.row(&name).casts += 1.0;
                self.record(&name, "activated", 0.0);
                continue;
            }
            if a.kind == "buff" && a.off_gcd {
                self.activate_buff(&name, &a);
            }
        }
    }

    fn queue_swings(&mut self) {
        if self.queued_swing.is_some() || !self.alive {
            return;
        }
        for (name, cond) in &self.c.rotation_conds {
            let a = &self.c.actions[name];
            if a.kind != "swing" {
                continue;
            }
            if self.resource() + EPS < self.cost(name) {
                continue;
            }
            if a.execute && self.t < self.execute_at {
                continue;
            }
            if !self.check(cond, name) {
                continue;
            }
            self.queued_swing = Some(name.clone());
            self.record(name, "queued", 0.0);
            return;
        }
    }

    fn activate_buff(&mut self, name: &str, a: &Ability) {
        let c = self.c;
        self.cooldowns.insert(name.to_string(), self.t + a.cooldown);
        self.row(name).casts += 1.0;
        if let Some(dur) = a.duration {
            let mut kw = Buff::default();
            if let Some(v) = a.damage_mult { kw.damage_mult = v; }
            if let Some(v) = &a.damage_mult_school { kw.damage_mult_school = Some(v.clone()); }
            if let Some(v) = a.melee_haste { kw.haste = v; }
            if let Some(v) = a.spell_haste { kw.haste = v; }
            if let Some(v) = a.ranged_haste { kw.haste = v; }
            if let Some(v) = a.energy_regen_mult { kw.energy_regen_mult = v; }
            if let Some(v) = a.pet_damage_mult { kw.pet_damage_mult = v; }
            if let Some(v) = a.flat_damage_bonus { kw.flat_damage_bonus = v; }
            self.add_buff(name, dur + c.mod_(&format!("duration:{name}")), kw);
        }
        if name == "Tiger's Fury" && c.flag("king_of_the_jungle") != 0.0 {
            self.gain_energy(c.flag("king_of_the_jungle"));
        }
        if a.combustion {
            self.combustion = Some((0, 0));
        }
        if a.instant_next {
            self.next_instant = true;
        }
        if a.next_crit {
            self.next_crit = true;
        }
        if let Some(lt) = a.life_tap {
            let gain = lt * (1.0 + c.mod_("dmg_ability:Life Tap")) + self.sp("shadow") * 0.8;
            self.gain_mana(gain);
            self.health -= lt;
        }
        if a.sacrifice {
            if let Some(p) = &c.pet {
                self.sacrificed = match p.family() { "imp" => Some(("shadow".into(), 0.15)), "succubus" => Some(("fire".into(), 0.15)), _ => None };
                self.pet_state = None;
            }
        }
        self.record(name, "activated", 0.0);
    }

    fn start(&mut self, name: &str) {
        let c = self.c;
        let a = c.actions[name].clone();
        let gcd = a.gcd.unwrap_or(c.t.GCD);
        let spell_style = c.spec.style == "spell";
        let haste = self.haste(if a.cast > 0.0 || (["channel", "direct", "dot", "direct_dot"].contains(&a.kind.as_str()) && spell_style) { "spell" } else { "melee" });
        if a.kind == "swing" {
            self.queued_swing = Some(name.to_string());
            self.record(name, "queued", 0.0);
            return;
        }
        if a.kind == "buff" {
            let cost = self.cost(name);
            self.spend(cost);
            if a.finisher.as_deref() == Some("slice_and_dice") {
                let dur = (6.0 + 3.0 * self.cp as f64) * (1.0 + c.flag("snd_duration"));
                self.add_buff(name, dur, Buff { haste: a.melee_haste.unwrap_or(0.0), ..Default::default() });
                self.finish(name);
                self.row(name).casts += 1.0;
                self.record(name, "applied", 0.0);
            } else if a.finisher.as_deref() == Some("venom_buff") {
                let dur = 6.0 + 3.0 * self.cp as f64;
                self.add_buff(name, dur, Buff::default());
                self.finish(name);
                self.row(name).casts += 1.0;
                self.record(name, "applied", 0.0);
            } else {
                self.activate_buff(name, &a);
            }
            self.gcd_until = self.t + gcd / if spell_style { haste } else { 1.0 };
            return;
        }
        let mut cost = self.cost(name);
        if c.spec.resource == "Rage" && cost > 0.0 && self.wrath_discount {
            cost = (cost - 5.0).max(0.0);
            self.wrath_discount = false;
        }
        if (name == "Hemorrhage" || name == "Backstab") && self.buff_active("Thousand Cuts") {
            self.buffs.shift_remove("Thousand Cuts");
        }
        self.row(name).casts += 1.0;
        let mut cast = a.cast / self.haste(if a.ranged_cast { "ranged" } else { "spell" });
        if self.next_instant && cast > 0.0 {
            cast = 0.0;
            self.next_instant = false;
        }
        if name == "Starfire" && self.eclipse > 0 {
            cast = (cast - 0.5).max(0.0);
            self.eclipse -= 1;
        }
        if name == "Pyroblast" {
            let stacks = self.buffs.get("Hot Streak").filter(|b| b.until > self.t).map_or(0, |b| b.stacks);
            if stacks > 0 {
                cast *= (1.0 - 0.25 * stacks as f64).max(0.25);
                self.buffs.shift_remove("Hot Streak");
            }
        }
        if name == "Lightning Bolt" {
            let stacks = self.buffs.get("Maelstrom Weapon").filter(|b| b.until > self.t).map_or(0, |b| b.stacks);
            if stacks > 0 {
                let reduction = (c.flag("maelstrom_weapon") * stacks as f64).min(1.0);
                cast *= (1.0 - reduction).max(0.0);
                cost *= (1.0 - reduction).max(0.0);
                self.buffs.shift_remove("Maelstrom Weapon");
            }
        }
        if name == "Arcane Missiles" && self.buff_active("Missile Barrage") {
            cast *= 0.5;
            self.buffs.shift_remove("Missile Barrage");
        }
        self.spend(cost);
        self.cur_cost = cost;
        if c.spec.resource == "Rage" && cost > 0.0 && c.flag("wrath_rage_proc") != 0.0 && self.rng.random() < c.flag("wrath_rage_proc") {
            self.wrath_discount = true;
        }
        self.cooldowns.insert(name.to_string(), self.t + a.cooldown);
        if let Some(s) = &a.shared_cd {
            self.cooldowns.insert(format!("shared:{s}"), self.t + a.cooldown);
        }
        self.gcd_until = if gcd == c.t.GCD { self.t + (gcd / if spell_style { self.haste("spell") } else { 1.0 }).max(1.0) } else { self.t + gcd };
        if cast > 0.0 {
            if a.ranged_cast {
                self.next_ranged = self.next_ranged.max(self.t + cast);
            }
            if a.kind == "channel" {
                let ticks = a.ticks;
                self.cast = Some(Cast { name: name.to_string(), until: self.t + cast, next_tick: self.t + cast / ticks as f64, ticks_left: ticks, tick_len: cast / ticks as f64, landed: true });
                self.busy_until = self.t + cast;
                let school = a.school_str().to_string();
                let (out, _m) = self.spell_outcome(name, &school, false);
                self.cast.as_mut().unwrap().landed = out != Outcome::Miss;
                if out == Outcome::Miss {
                    self.row(name).misses += 1.0;
                    self.record(name, "miss", 0.0);
                }
            } else {
                self.cast = Some(Cast { name: name.to_string(), until: self.t + cast, next_tick: 0.0, ticks_left: 0, tick_len: 0.0, landed: true });
                self.busy_until = self.t + cast;
            }
            return;
        }
        self.resolve(name);
    }

    fn finish(&mut self, name: &str) -> i64 {
        let c = self.c;
        let cp = self.cp;
        self.cp = 0;
        if c.flag("ruthlessness") != 0.0 && self.rng.random() < c.flag("ruthlessness") {
            self.cp = 1;
        }
        if c.flag("relentless_strikes") != 0.0 && self.rng.random() < 0.2 * cp as f64 {
            self.gain_energy(25.0);
        }
        if c.flag("restless_blades") != 0.0 && c.actions[name].kind != "buff" {
            let reduction = 2.0 * cp as f64;
            for cd_name in ["Adrenaline Rush", "Blade Flurry"] {
                if let Some(v) = self.cooldowns.get_mut(cd_name) {
                    *v = (*v - reduction).max(self.t);
                }
            }
        }
        cp
    }

    fn resolve(&mut self, name: &str) {
        let c = self.c;
        let a = c.actions[name].clone();
        let school = a.school_str().to_string();
        self.cur_school = school.clone();
        let kind = a.kind.as_str();
        if kind == "buff" {
            self.activate_buff(name, &a);
            return;
        }
        if name == "Mutilate" {
            if c.oh.is_empty() {
                self.deal(name, 0.0, "physical", "melee", false, false, 1.0, 0.0, Outcome::Miss, 1.0);
                return;
            }
            let poisoned = self.dots.get("Deadly Poison").is_some_and(|d| d.remaining > 0);
            let mut landed_any = false;
            for hand in [Hand::Main, Hand::Off] {
                let item = if hand == Hand::Main { c.mh.clone() } else { c.oh.clone() };
                let (out, m) = self.melee_outcome(hand, false, Some(name), false);
                if out.avoided() {
                    self.deal(name, 0.0, "physical", "melee", false, false, 1.0, 0.0, out, 1.0);
                    continue;
                }
                let mut base = self.weapon_damage(&item, true, false, 0.0) * 0.75 + 13.0;
                if poisoned {
                    base *= 1.20;
                }
                let dmg = self.deal(name, base, "physical", "melee", false, false, 1.0, 0.0, out, m * a.mult);
                if dmg != 0.0 {
                    landed_any = true;
                    self.on_weapon_hit(hand, false, name, dmg);
                    if out == Outcome::Crit {
                        self.on_crit(name, dmg, hand, "melee");
                    }
                }
            }
            if landed_any {
                let mut gained = a.cp;
                if self.rng.random() < c.flag("seal_fate") {
                    gained += 1;
                }
                self.cp = 5.min(self.cp + gained);
            }
            self.touch_of_the_grave();
            return;
        }
        let (threat_mult, flat_threat) = (a.threat_mult(), a.flat_threat);
        if a.no_damage {
            let th_mult = self.threat_multiplier(None);
            let targets_mult = if name == "Demoralizing Shout" { c.targets as f64 } else { 1.0 };
            let r = self.row(name);
            r.hits += 1.0;
            let th = flat_threat * targets_mult * (1.0 + c.mod_(&format!("threat_ability:{name}"))) * th_mult;
            r.threat += th;
            self.threat += th;
            if name == "Sunder Armor" {
                self.add_debuff("Sunder Armor", 30.0, Some(5));
            }
            if name == "Demoralizing Shout" {
                self.add_debuff("Demoralizing Shout", 45.0, None);
            }
            self.record(name, "hit", 0.0);
            return;
        }
        let melee_like = a.weapon.is_some() || a.ap_mult.is_some() || a.execute_formula.is_some() || matches!(a.finisher.as_deref(), Some("eviscerate") | Some("ferocious_bite"))
            || (school == "physical" && c.spec.style != "ranged" && (a.base.is_some() || a.flat.is_some_and(|f| f != 0.0)));
        if melee_like {
            if a.weapon_hand() == Some("ranged") {
                let (out, m) = self.ranged_outcome(Some(name));
                let mut dmg = 0.0;
                if out != Outcome::Miss {
                    let ranged = c.ranged.clone();
                    dmg = self.weapon_damage(&ranged, true, true, 0.0) + a.weapon_flat();
                }
                let targets = if name == "Multi-Shot" { c.targets.min(3) as f64 } else { 1.0 };
                let dealt = self.deal(name, dmg, "physical", "ranged", false, false, 1.0, 0.0, out, m * a.mult * targets);
                if dealt != 0.0 {
                    self.on_ranged_damage(out);
                }
                return;
            }
            let item = c.mh.clone();
            let (out, m) = self.melee_outcome(Hand::Main, false, Some(name), a.no_dodge);
            if out.avoided() {
                self.deal(name, 0.0, "physical", "melee", false, false, 1.0, 0.0, out, 1.0);
                if c.spec.resource == "Rage" {
                    self.rage += self.cur_cost * 0.8;
                }
                if out == Outcome::Dodge {
                    self.dodged_recently = self.t;
                }
                if a.finisher.is_some() && c.flag("finisher_refund") != 0.0 {
                    self.gain_energy(c.flag("finisher_refund"));
                }
                return;
            }
            let mut base;
            if let Some((f0, f1)) = a.execute_formula {
                let extra = self.rage;
                base = f0 + f1 * extra;
                self.rage = 0.0;
            } else if let Some(apm) = a.ap_mult {
                base = apm * self.ap(false) + a.flat.unwrap_or(0.0);
            } else if a.finisher.as_deref() == Some("eviscerate") {
                let cp = self.cp as f64;
                base = self.rng.uniform(48.0 + 151.0 * cp, 48.0 + 151.0 * cp + 96.0) + 0.03 * cp * self.ap(false);
            } else if a.finisher.as_deref() == Some("ferocious_bite") {
                let cp = self.cp as f64;
                let extra = self.energy.max(0.0);
                self.energy = 0.0;
                base = 52.0 + self.rng.uniform(0.0, 60.0) + 128.0 * cp + self.ap(false) * 0.03 * cp + extra * 2.7;
            } else if let Some((lo, hi)) = a.base {
                base = self.rng.uniform(lo, hi) + if a.add_block_value { self.st("blockValue") } else { 0.0 };
            } else if a.weapon.is_none() {
                base = a.flat.unwrap_or(0.0);
            } else {
                // Safe: the `a.weapon.is_none()` branch above was already taken otherwise.
                #[allow(clippy::unnecessary_unwrap)]
                let w = a.weapon.as_ref().unwrap();
                let mut mult = w.mult.unwrap_or(1.0);
                if let Some(dm) = w.dagger_mult {
                    if weapon_type(&item) == Some("Dagger") {
                        mult = dm;
                    }
                }
                base = self.weapon_damage(&item, w.normalized, false, 0.0) * mult + w.flat.unwrap_or(0.0);
                if w.hand == "both" && !c.oh.is_empty() {
                    base += self.weapon_damage(&c.oh, w.normalized, false, 0.0) * mult + w.flat.unwrap_or(0.0);
                }
                if let Some(cm) = &a.creature_mult {
                    if let Some(v) = cm.get(&c.boss_type) {
                        base *= v;
                    }
                }
            }
            let fb: f64 = self.buffs.values().filter(|b| b.until > self.t).map(|b| b.flat_damage_bonus).sum();
            base += fb + c.mod_(&format!("flat_ability:{name}"));
            if self.next_crit {
                self.next_crit = false;
            }
            let targets = if name == "Whirlwind" || name == "Thunder Clap" { c.targets.min(4) as f64 } else if name == "Swipe" { c.targets.min(3) as f64 } else { 1.0 };
            let dmg = self.deal(name, base, "physical", "melee", false, false, threat_mult, flat_threat, out, m * a.mult * targets);
            if self.eureka > 0 {
                self.eureka -= 1;
            }
            if a.cp != 0 {
                let mut gained = a.cp;
                if out == Outcome::Crit && self.rng.random() < c.flag("seal_fate") {
                    gained += 1;
                }
                if out == Outcome::Crit && c.flag("primal_fury") != 0.0 && c.spec.form_is("cat") {
                    gained += 1;
                }
                self.cp = 5.min(self.cp + gained);
            }
            if out == Outcome::Crit && c.flag("bonescythe_energy") != 0.0 && ["Backstab", "Sinister Strike", "Hemorrhage"].contains(&name) {
                self.gain_energy(c.flag("bonescythe_energy"));
            }
            if a.finisher.is_some() {
                self.finish(name);
            }
            if let Some((n, d, _)) = &a.apply_debuff {
                self.add_debuff(n, *d, None);
            }
            if name == "Hemorrhage" {
                self.add_debuff("Hemorrhage", 15.0, None);
            }
            if name == "Mongoose Bite" {
                self.buffs.shift_remove("Mongoose Bite Ready");
                if dmg != 0.0 && c.flag("lacerating_strikes") != 0.0 {
                    let tick = dmg * 0.40 / 7.0 * self.periodic_crit_mult("Lacerating Strikes", "physical", true, 0.0);
                    self.dots.insert("Lacerating Strikes".into(), Dot { next: self.t + 3.0, remaining: 7, tick, tick_len: 3.0, school: "physical".into(), bleed: true, stacks: 1 });
                }
            }
            if dmg != 0.0 {
                if a.weapon.is_some() {
                    self.on_weapon_hit(Hand::Main, false, name, dmg);
                }
                if out == Outcome::Crit {
                    self.on_crit(name, dmg, if a.weapon.is_some() { Hand::Main } else { Hand::None }, "melee");
                }
            }
            self.touch_of_the_grave();
            return;
        }
        if ["direct", "direct_dot", "dot"].contains(&kind) && a.finisher.as_deref() == Some("rip") {
            let cp = self.cp;
            let scaling = if cp == 5 { 4 } else { cp };
            let tick = 17.0 + 28.0 * cp as f64 + 0.01 * scaling as f64 * self.ap(false);
            let (out, _m) = self.melee_outcome(Hand::Main, false, Some(name), false);
            self.row(name);
            if out.avoided() {
                self.deal(name, 0.0, "physical", "melee", false, false, 1.0, 0.0, out, 1.0);
                if c.flag("finisher_refund") != 0.0 {
                    self.gain_energy(c.flag("finisher_refund"));
                }
                return;
            }
            let tick = tick * a.mult * self.periodic_crit_mult(name, "physical", true, 0.0);
            self.dots.insert(name.to_string(), Dot { next: self.t + a.tick_len, remaining: a.ticks, tick, tick_len: a.tick_len, school: "physical".into(), bleed: true, stacks: 1 });
            self.finish(name);
            self.record(name, "applied", 0.0);
            return;
        }
        if a.finisher.as_deref() == Some("rupture") {
            let cp = self.cp;
            let scale = [0.0, 0.04 / 4.0, 0.10 / 5.0, 0.18 / 6.0, 0.21 / 7.0, 0.24 / 8.0][cp as usize];
            // Forever cut Rupture's per-CP totals roughly in half vs Classic (foreverchanges.pro,
            // build 1.60.1.69913); refit flat base in place of the old Classic-fit "60 + 8*cp".
            let tick = 2.9 + 4.4 * cp as f64 + scale * self.ap(false);
            let (out, _m) = self.melee_outcome(Hand::Main, false, Some(name), false);
            if out.avoided() {
                self.deal(name, 0.0, "physical", "melee", false, false, 1.0, 0.0, out, 1.0);
                if c.flag("finisher_refund") != 0.0 {
                    self.gain_energy(c.flag("finisher_refund"));
                }
                return;
            }
            let tick = tick * a.mult * self.periodic_crit_mult(name, "physical", true, 0.0);
            self.dots.insert(name.to_string(), Dot { next: self.t + 2.0, remaining: 3 + cp, tick, tick_len: 2.0, school: "physical".into(), bleed: true, stacks: 1 });
            self.finish(name);
            self.record(name, "applied", 0.0);
            return;
        }
        let sp = self.sp(&school);
        if kind == "direct" || kind == "direct_dot" {
            let can_crit = !a.no_crit;
            if name == "Arcane Blast" && c.flag("arcane_blast") != 0.0 {
                self.add_buff("Arcane Blast", 8.0, Buff { stacks_max: Some(4), ..Default::default() });
            }
            let (out, m) = if !a.always_hit { self.spell_outcome(name, &school, can_crit) } else { (Outcome::Hit, 1.0) };
            if out == Outcome::Miss {
                self.deal(name, 0.0, &school, "spell", false, false, 1.0, 0.0, Outcome::Miss, 1.0);
                return;
            }
            let (lo, hi) = a.base.unwrap_or((0.0, 0.0));
            let mut base = self.rng.uniform(lo, hi) + sp * a.coeff;
            base *= a.direct_mult.unwrap_or(1.0);
            if name == "Chain Lightning" {
                let bounce = 0.7 + c.mod_("chain_lightning_bounce");
                base *= 1.0 + bounce * ((c.targets > 1) as i32 as f64) + bounce * bounce * ((c.targets > 2) as i32 as f64);
            }
            if name == "Conflagrate" {
                let preserve = (c.flag("shadow_and_flame") * 10.0).min(1.0);
                if self.rng.random() >= preserve {
                    if let Some(d) = self.dots.get_mut("Immolate") {
                        d.remaining = 0;
                    }
                }
            }
            let mut fof_used = false;
            if name == "Ice Lance"
                && self.buffs.get("Fingers of Frost").is_some_and(|b| b.until > self.t && b.stacks > 0) {
                    base *= 4.0;
                    fof_used = true;
                }
            if self.next_crit {
                self.next_crit = false;
            }
            let dmg = self.deal(name, base, &school, "spell", false, false, threat_mult, flat_threat, out, m * a.mult * (if a.aoe { c.targets as f64 } else { 1.0 }));
            if self.eureka > 0 {
                self.eureka -= 1;
            }
            if fof_used {
                if let Some(b) = self.buffs.get_mut("Fingers of Frost") {
                    b.stacks -= 1;
                    if b.stacks <= 0 {
                        self.buffs.shift_remove("Fingers of Frost");
                    }
                }
            }
            self.after_spell_hit(name, &school, out, dmg, &a);
            if (name == "Fireball" || name == "Frostbolt") && c.flag("netherwind_instant") != 0.0 && self.rng.random() < c.flag("netherwind_instant") {
                self.next_instant = true;
            }
            if kind == "direct_dot" {
                self.apply_dot(name, &a, sp);
            }
            return;
        }
        if kind == "dot" {
            let (out, _m) = self.spell_outcome(name, &school, false);
            if out == Outcome::Miss {
                self.deal(name, 0.0, &school, "spell", false, false, 1.0, 0.0, Outcome::Miss, 1.0);
                return;
            }
            self.apply_dot(name, &a, sp);
            self.after_spell_hit(name, &school, Outcome::Hit, 0.0, &a);
            self.record(name, "applied", 0.0);
        }
    }

    fn apply_dot(&mut self, name: &str, a: &Ability, sp: f64) {
        let c = self.c;
        let mut tick = (a.tick + sp * a.dot_coeff) * a.mult;
        let pandemic = if ["Corruption", "Curse of Agony", "Siphon Life", "Drain Soul", "Wrack"].contains(&name) { c.mod_("crit_dmg_periodic") } else { 0.0 };
        let school = a.school_str().to_string();
        tick *= self.periodic_crit_mult(name, &school, a.bleed, pandemic);
        let instance = Dot { next: self.t + a.tick_len, remaining: a.ticks, tick, tick_len: a.tick_len, school, bleed: a.bleed, stacks: 1 };
        let primary_active = self.dots.get(name).is_some_and(|d| d.remaining > 0 && d.next - self.t < 1e9);
        if a.spreadable && c.targets > 1 && primary_active {
            if let Some(slot) = self.dots_extra.iter_mut().find(|(n, d)| n == name && d.remaining <= 0) {
                slot.1 = instance;
            } else {
                self.dots_extra.push((name.to_string(), instance));
            }
        } else {
            self.dots.insert(name.to_string(), instance);
        }
    }

    fn after_spell_hit(&mut self, name: &str, school: &str, out: Outcome, dmg: f64, a: &Ability) {
        let c = self.c;
        if c.flag("arcane_blast") != 0.0 && name != "Arcane Blast" {
            self.buffs.shift_remove("Arcane Blast");
        }
        if c.flag("missile_barrage") != 0.0 && ["Arcane Blast", "Fireball", "Frostbolt"].contains(&name) && matches!(out, Outcome::Hit | Outcome::Crit) {
            let chance = if name == "Arcane Blast" { 0.40 } else { 0.20 };
            if self.rng.random() < chance {
                self.add_buff("Missile Barrage", 20.0, Buff::default());
            }
        }
        if c.flag("hot_streak") != 0.0 && ["Fireball", "Fire Blast", "Scorch"].contains(&name) && out == Outcome::Crit {
            self.add_buff("Hot Streak", 15.0, Buff { stacks_max: Some(3), ..Default::default() });
        }
        if c.flag("fingers_of_frost") != 0.0 && name == "Frostbolt" && matches!(out, Outcome::Hit | Outcome::Crit) && self.rng.random() < 0.15 {
            self.add_buff("Fingers of Frost", 15.0, Buff { stacks_max: Some(2), ..Default::default() });
        }
        if c.flag("shadow_weaving") != 0.0 && school == "shadow" {
            self.add_debuff("Shadow Weaving", 15.0, Some(5));
        }
        if c.flag("improved_scorch") != 0.0 && name == "Scorch" {
            self.add_debuff("Improved Scorch", 30.0, Some(5));
        }
        if c.flag("winters_chill") != 0.0 && school == "frost" {
            self.add_debuff("Winter's Chill", 15.0, Some(5));
        }
        let landed = matches!(out, Outcome::Hit | Outcome::Crit);
        if self.combustion.is_some() && school == "fire" && landed {
            let (s, cr) = self.combustion.unwrap();
            self.combustion = Some((s + 1, cr));
        }
        if c.flag("clearcasting") != 0.0 && landed && self.rng.random() < c.flag("clearcasting") {
            self.clearcast = true;
        }
        if c.flag("eclipse") != 0.0 && name == "Wrath" {
            self.eclipse = 4.min(self.eclipse + 2);
        }
        if c.flag("lightning_overload") != 0.0 && (name == "Lightning Bolt" || name == "Chain Lightning") && self.rng.random() < c.flag("lightning_overload") {
            let (o2, m2) = self.spell_outcome(name, school, true);
            if o2 != Outcome::Miss {
                let label = format!("{name} (Overload)");
                self.row(&label).casts += 1.0;
                let (lo, hi) = a.base.unwrap_or((0.0, 0.0));
                let amt = (self.rng.uniform(lo, hi) + self.sp(school) * a.coeff) * 0.5;
                self.deal(&label, amt, school, "spell", false, false, 0.0, 0.0, o2, m2 * a.mult);
            }
        }
        if c.flag("stormcaller") != 0.0 && ["Lightning Bolt", "Chain Lightning", "Earth Shock", "Flame Shock"].contains(&name) && landed && self.rng.random() < c.flag("stormcaller") {
            self.add_buff("Stormcaller's Garb", 8.0, Buff { stat: Some("naturePower".into()), value: 50.0, ..Default::default() });
        }
        if c.flag("shadow_and_flame") != 0.0 {
            if name == "Conflagrate" {
                self.add_debuff("Shadow and Flame (shadow)", 20.0, None);
            }
            if name == "Shadowburn" {
                self.add_debuff("Shadow and Flame (fire)", 20.0, None);
            }
        }
        if out == Outcome::Crit {
            self.on_crit(name, dmg, Hand::None, "spell");
        }
        self.touch_of_the_grave();
    }

    fn complete_cast(&mut self) {
        let cast = self.cast.take().unwrap();
        let a = &self.c.actions[&cast.name];
        if a.kind == "channel" {
            if cast.name == "Arcane Missiles" && self.c.flag("netherwind_instant") != 0.0 && self.rng.random() < self.c.flag("netherwind_instant") {
                self.next_instant = true;
            }
            return;
        }
        self.resolve(&cast.name);
    }

    fn channel_tick(&mut self) {
        let c = self.c;
        let (name, landed) = {
            let cast = self.cast.as_mut().unwrap();
            cast.ticks_left -= 1;
            cast.next_tick += cast.tick_len;
            (cast.name.clone(), cast.landed)
        };
        let a = c.actions[&name].clone();
        if !landed {
            return;
        }
        let school = a.school_str().to_string();
        let mut tick = a.tick + self.sp(&school) * a.coeff;
        if a.execute_bonus && self.t >= self.execute_at {
            let active = ["Corruption", "Curse of Agony", "Siphon Life"].iter().filter(|d| self.dots.get(**d).is_some_and(|x| x.remaining > 0)).count() as f64;
            tick *= 1.0 + (c.flag("improved_drains") * active).min(0.18) * 3.0;
        }
        let (mut out, mut m) = (Outcome::Hit, 1.0);
        if name == "Arcane Missiles" {
            let r = self.spell_outcome(&name, &school, true);
            out = r.0;
            m = r.1;
            if out == Outcome::Miss {
                self.deal(&name, 0.0, &school, "spell", false, false, 1.0, 0.0, Outcome::Miss, 1.0);
                return;
            }
        }
        if name == "Drain Soul" {
            if c.flag("soul_siphon") != 0.0 {
                tick *= 1.0 + c.flag("soul_siphon");
            }
            if c.flag("nightfall") != 0.0 && self.rng.random() < c.flag("nightfall") {
                self.proc_nightfall();
            }
        }
        let dmg = self.deal(&name, tick, &school, "spell", false, name != "Arcane Missiles", 1.0, 0.0, out, m * a.mult * (if a.aoe { c.targets as f64 } else { 1.0 }));
        if name == "Arcane Missiles" {
            self.after_spell_hit(&name, &school, out, dmg, &a);
        }
    }

    fn dot_tick(&mut self, name: &str) {
        let (tick, school) = {
            let d = self.dots.get_mut(name).unwrap();
            d.remaining -= 1;
            d.next += d.tick_len;
            (d.tick * d.stacks as f64, d.school.clone())
        };
        self.row(name);
        let kind = if school != "physical" { "spell" } else { "melee" };
        self.deal(name, tick, &school, kind, false, true, 1.0, 0.0, Outcome::Hit, 1.0);
        if name == "Corruption" && self.c.flag("nightfall") != 0.0 && self.rng.random() < self.c.flag("nightfall") {
            self.proc_nightfall();
        }
        if name == "Rupture" && self.c.flag("thousand_cuts") != 0.0 {
            self.add_buff("Thousand Cuts", 10.0, Buff { stacks_max: Some(5), ..Default::default() });
        }
    }

    fn dot_tick_extra(&mut self, idx: usize) {
        let (name, tick, school) = {
            let (name, d) = &mut self.dots_extra[idx];
            d.remaining -= 1;
            d.next += d.tick_len;
            (name.clone(), d.tick * d.stacks as f64, d.school.clone())
        };
        self.row(&name);
        let kind = if school != "physical" { "spell" } else { "melee" };
        self.deal(&name, tick, &school, kind, false, true, 1.0, 0.0, Outcome::Hit, 1.0);
        if name == "Corruption" && self.c.flag("nightfall") != 0.0 && self.rng.random() < self.c.flag("nightfall") {
            self.proc_nightfall();
        }
    }

    // ---- boss ------------------------------------------------------------
    fn boss_swing(&mut self) {
        let c = self.c;
        let raw = self.rng.uniform(2700.0, 3300.0);
        let defense_bonus = (self.st("defense") - c.t.TARGET_DEFENSE) * 0.0004;
        let miss = (0.05 + defense_bonus).max(0.0);
        let dodge = (self.st("dodge") / 100.0 + defense_bonus).max(0.0);
        let parry = if c.spec.class_name == "Warrior" || c.spec.class_name == "Paladin" { (self.st("parry") / 100.0 + defense_bonus).max(0.0) } else { 0.0 };
        let block = if self.st("block") > 0.0 { (self.st("block") / 100.0 + defense_bonus).max(0.0) } else { 0.0 };
        let crit = (0.05 - defense_bonus).max(0.0);
        let crush = if c.t.TARGET_LEVEL - c.t.LEVEL >= 3.0 { 0.15 } else { 0.0 };
        let roll = self.rng.random();
        let mut acc = 0.0;
        let mut outcome = Outcome::Hit;
        for (o, chance) in [(Outcome::Miss, miss), (Outcome::Dodge, dodge), (Outcome::Parry, parry), (Outcome::Block, block), (Outcome::Crit, crit), (Outcome::Crush, crush)] {
            acc += chance;
            if roll < acc {
                outcome = o;
                break;
            }
        }
        if self.next_parry {
            self.next_parry = false;
            outcome = Outcome::Parry;
        }
        if outcome.avoided() {
            self.avoided_recently = self.t;
            if (outcome == Outcome::Dodge || outcome == Outcome::Parry) && c.flag("master_of_defense") != 0.0 && self.rng.random() < c.flag("master_of_defense").min(1.0) {
                self.gain_rage(5.0);
            }
            if outcome == Outcome::Dodge && c.spec.form_is("bear") && c.mod_("dodge") != 0.0 {
                self.gain_rage(5.0);
            }
            if (outcome == Outcome::Dodge || outcome == Outcome::Parry) && c.flag("improved_stormstrike") != 0.0 && self.rng.random() < c.flag("improved_stormstrike").min(1.0) {
                self.cooldowns.insert("Stormstrike".to_string(), self.t);
            }
            self.row("Boss melee").misses += 1.0;
            self.record("Boss melee", outcome.as_str(), 0.0);
            return;
        }
        let armor = self.st("armor");
        let mult = match outcome { Outcome::Crit => 2.0, Outcome::Crush => 1.5, _ => 1.0 };
        let tl = c.t.TARGET_LEVEL;
        let mut amount = raw * mult * (1.0 - (armor / (armor + 400.0 + 85.0 * tl)).min(0.75));
        amount *= c.t.stance_mod(&c.spec.stance_or_form()).taken;
        if c.debuffs.contains("demoralizing_shout") {
            amount *= 0.90;
        }
        if outcome == Outcome::Block {
            self.avoided_recently = self.t;
            let bv = self.st("blockValue") + self.st("strength") / 20.0;
            amount = (amount - bv).max(0.0);
            if c.flag("shield_spec_rage") != 0.0 && self.rng.random() < c.flag("shield_spec_rage").min(1.0) {
                self.gain_rage(5.0);
            }
            if c.flag("wrath_parry") != 0.0 && self.rng.random() < c.flag("wrath_parry") {
                self.next_parry = true;
            }
        }
        if self.buff_active("Stoneform") { amount *= 0.90; }
        self.taken += amount;
        self.health -= amount;
        let conversion = 0.0091107836 * tl * tl + 3.225598133 * tl + 4.2652911;
        self.rage = self.max_rage.min(self.rage + amount * 2.5 / conversion);
        if c.flag("enrage") != 0.0 && self.rng.random() < c.flag("enrage") * 3.0 {
            self.enrage_until = self.t + 12.0;
        }
        if c.flag("might_rage") != 0.0 && self.rng.random() < c.flag("might_rage") {
            self.gain_rage(1.0);
        }
        if c.flag("wildheart_proc") != 0.0 && self.rng.random() < c.flag("wildheart_proc") {
            match c.spec.resource.as_str() {
                "Mana" => self.gain_mana(300.0),
                "Rage" => self.gain_rage(10.0),
                _ => self.gain_energy(40.0),
            }
        }
        let r = self.row("Boss melee");
        r.casts += 1.0;
        r.hits += 1.0;
        *self.taken_by.entry(outcome.as_str().to_string()).or_insert(0.0) += amount;
        self.record("Boss melee", outcome.as_str(), amount);
        if self.health <= 0.0 && self.alive {
            self.alive = false;
            self.alive_seconds = self.t;
            self.record("Death", "death", 0.0);
        }
    }

    // ---- pets ------------------------------------------------------------
    fn pet_setup(&mut self) {
        let c = self.c;
        match &c.pet {
            None => {}
            Some(Pet::Hunter(p)) => {
                self.pet_state = Some(PetState { focus: 100.0, active_until: self.duration * p.uptime, ..Default::default() });
            }
            Some(Pet::Warlock(p)) => {
                self.pet_state = Some(PetState { mana: p.cfg.mana * (1.0 + c.mod_("stat_pct:mana") * 0.0), active_until: self.duration * p.uptime, next_mana: 2.0, ..Default::default() });
            }
        }
    }

    fn pet_multiplier(&self) -> f64 {
        let c = self.c;
        let mut m = 1.0;
        match c.pet.as_ref().unwrap() {
            Pet::Hunter(p) => {
                m *= 1.25 * p.damage * (1.0 + c.flag("pet_damage"));
                if let Some(b) = self.buffs.get("Bestial Wrath") {
                    if b.until > self.t {
                        m *= 1.5;
                    }
                }
            }
            Pet::Warlock(p) => {
                m *= 1.0 + c.flag("pet_damage");
                if c.flag("soul_link") != 0.0 {
                    m *= 1.0 + c.flag("soul_link");
                }
                if c.flag("master_demonologist") != 0.0 && p.family == "succubus" {
                    m *= 1.0 + c.flag("master_demonologist");
                }
            }
        }
        let creature = if c.racial_enabled { c.racial.creature_damage.get(&c.boss_type).copied().unwrap_or(0.0) } else { 0.0 };
        m * (1.0 + creature)
    }

    fn pet_attack(&mut self, name: &str, base: f64, school: &str, crit_chance: f64, ability: bool) -> f64 {
        // Independent level-60 pet table: never inherit owner combat stats.
        let roll = self.rng.random();
        let (out, m) = if school == "physical" {
            let glance = if ability { 0.0 } else { 0.40 };
            if roll < 0.08 { (Outcome::Miss, 0.0) }
            else if roll < 0.145 { (Outcome::Dodge, 0.0) }
            else if roll < 0.145 + glance { (Outcome::Glance, self.rng.uniform(0.55, 0.75)) }
            else if roll < 0.145 + glance + (crit_chance - 0.048).max(0.0) { (Outcome::Crit, 2.0) }
            else { (Outcome::Hit, 1.0) }
        } else {
            if roll >= 0.83 { (Outcome::Miss, 0.0) }
            else if self.rng.random() < (crit_chance - 0.021).max(0.0) { (Outcome::Crit, 1.5) }
            else { (Outcome::Hit, 1.0) }
        };
        self.row(name).casts += 1.0;
        if out.avoided() {
            self.row(name).misses += 1.0;
            self.record(name, out.as_str(), 0.0);
            return 0.0;
        }
        let mut dmg = base * m * self.pet_multiplier();
        if school == "physical" {
            dmg *= self.armor_mult();
        }
        let r = self.row(name);
        if out == Outcome::Crit {
            r.crits += 1.0;
        }
        if out == Outcome::Glance { r.glances += 1.0; }
        r.hits += 1.0;
        r.damage += dmg;
        r.threat += dmg;
        self.total += dmg;
        self.pet_threat += dmg;
        if out == Outcome::Crit && matches!(self.c.pet, Some(Pet::Hunter(_))) && self.c.flag("pet_frenzy") != 0.0 && self.rng.random() < self.c.flag("pet_frenzy") {
            self.pet_state.as_mut().unwrap().frenzy_until = self.t + 8.0;
        }
        self.record(name, out.as_str(), dmg);
        dmg
    }

    fn pet_step(&mut self) {
        let c = self.c;
        let Some(pet) = &c.pet else { return };
        let t = self.t;
        {
            let Some(ps) = &self.pet_state else { return };
            if t >= ps.active_until {
                return;
            }
        }
        match pet {
            Pet::Hunter(p) => {
                let crit = 0.05 + c.flag("pet_crit") / 100.0;
                {
                    let ps = self.pet_state.as_mut().unwrap();
                    ps.focus = 100.0f64.min(ps.focus + (t - ps.last) * c.t.PET_FOCUS_PER_SEC * (1.0 + c.flag("pet_focus")));
                    ps.last = t;
                }
                if t + EPS >= self.pet_state.as_ref().unwrap().next_swing {
                    // Own 136 Strength * 2 - 20 = 252 AP; no owner inheritance.
                    let speed = p.speed;
                    let base = (self.rng.uniform(18.17, 27.66) + 252.0 / 14.0) * speed;
                    self.pet_attack("Pet Melee", base, "physical", crit, false);
                    let frenzy = if t < self.pet_state.as_ref().unwrap().frenzy_until { 1.3 } else { 1.0 };
                    self.pet_state.as_mut().unwrap().next_swing = t + self.pet_delay(speed / frenzy);
                }
                if self.pet_state.as_ref().unwrap().gcd <= t + EPS {
                    let mut broke = false;
                    for name in [p.special.clone(), p.dump.clone()].into_iter().flatten() {
                        if !p.abilities.contains(&name) {
                            continue;
                        }
                        let cfg = c.t.PET_ABILITIES[&name].clone();
                        {
                            let ps = self.pet_state.as_ref().unwrap();
                            if ps.ready.get(&name).copied().unwrap_or(0.0) > t || ps.focus < cfg.cost {
                                continue;
                            }
                        }
                        {
                            let ps = self.pet_state.as_mut().unwrap();
                            ps.focus -= cfg.cost;
                            ps.ready.insert(name.clone(), t + cfg.cooldown);
                            ps.gcd = t + 1.6;
                        }
                        let base = self.rng.uniform(cfg.min, cfg.max);
                        let label = format!("Pet - {name}");
                        self.pet_attack(&label, base, &cfg.school, crit, true);
                        broke = true;
                        break;
                    }
                    if !broke {
                        self.pet_state.as_mut().unwrap().gcd = t + 0.5;
                    }
                }
            }
            Pet::Warlock(p) => {
                let cfg = p.cfg.clone();
                let fam = p.family.clone();
                if t + EPS >= self.pet_state.as_ref().unwrap().next_mana {
                    let ps = self.pet_state.as_mut().unwrap();
                    ps.mana = cfg.mana.min(ps.mana + cfg.spirit / 5.0 * 2.0);
                    ps.next_mana += 2.0;
                }
                if cfg.speed != 0.0 && p.abilities.contains("Melee") && t + EPS >= self.pet_state.as_ref().unwrap().next_swing {
                    let ap = cfg.strength * 2.0 - 20.0;
                    let (lo, hi) = cfg.melee.unwrap_or((0.0, 0.0));
                    let base = self.rng.uniform(lo, hi) + ap / 14.0 * cfg.speed;
                    self.pet_attack(&format!("{} - Melee", title(&fam)), base, "physical", 0.05, false);
                    self.pet_state.as_mut().unwrap().next_swing = t + self.pet_delay(cfg.speed);
                }
                if let Some(spell) = &cfg.spell {
                    if p.abilities.contains(spell) {
                        let cast_until = self.pet_state.as_ref().unwrap().cast_until;
                        if let Some(cu) = cast_until {
                            if t + EPS >= cu {
                                self.pet_state.as_mut().unwrap().cast_until = None;
                                let mut mult = if fam == "imp" { 1.0 + c.flag("improved_imp") } else { 1.0 + c.flag("improved_sayaad") };
                                if c.flag("master_demonologist") != 0.0 && fam == "imp" {
                                    mult *= 1.0 + c.flag("master_demonologist");
                                }
                                let base = self.rng.uniform(cfg.spell_min, cfg.spell_max) * mult;
                                let crit = 0.05 + cfg.intellect * c.t.SPELL_CRIT_PER_INT["Mage"] / 100.0;
                                let school = cfg.school.clone().unwrap_or_else(|| "physical".into());
                                self.pet_attack(&format!("{} - {}", title(&fam), spell), base, &school, crit, true);
                                self.pet_state.as_mut().unwrap().next_cast = t + cfg.cooldown;
                            }
                        }
                        let ps = self.pet_state.as_mut().unwrap();
                        if ps.cast_until.is_none() && t + EPS >= ps.next_cast && ps.mana >= cfg.spell_cost {
                            ps.mana -= cfg.spell_cost;
                            let cast = cfg.cast;
                            ps.cast_until = Some(t + cast.max(0.0) / if c.buffs.contains("bloodlust") && t < 40.0 { 1.30 } else { 1.0 });
                            if cast == 0.0 {
                                ps.cast_until = Some(t);
                            }
                        }
                    }
                }
                if let Some(u) = &cfg.utility {
                    if p.abilities.contains(u) && t + EPS >= self.pet_state.as_ref().unwrap().next_utility.unwrap_or(0.0) {
                        self.pet_state.as_mut().unwrap().next_utility = Some(t + 5.0);
                        let label = format!("{} - {}", title(&fam), u);
                        let r = self.row(&label);
                        r.casts += 1.0;
                        r.threat += 120.0;
                        self.pet_threat += 120.0;
                    }
                }
            }
        }
    }

    fn pet_next(&self) -> f64 {
        let Some(ps) = &self.pet_state else { return self.duration };
        if self.t >= ps.active_until {
            return self.duration;
        }
        match self.c.pet.as_ref().unwrap() {
            Pet::Hunter(_) => ps.next_swing.min(ps.gcd.max(self.t + EPS)),
            Pet::Warlock(p) => {
                let mut cands = vec![ps.next_mana];
                if p.cfg.speed != 0.0 {
                    cands.push(ps.next_swing);
                }
                match ps.cast_until {
                    Some(cu) => cands.push(cu),
                    None => cands.push(ps.next_cast.max(self.t + 0.5)),
                }
                cands.push(ps.next_utility.unwrap_or(self.t + 5.0));
                cands.into_iter().fold(f64::INFINITY, f64::min)
            }
        }
    }

    // ---- main loop -------------------------------------------------------
    pub fn run(mut self) -> IterResult {
        let c = self.c;
        let s = &c.spec;
        self.pet_setup();
        if s.role == "tank" {
            self.row("Taunt").casts += 1.0;
            self.record("Taunt", "cast", 0.0);
            self.gcd_until = c.t.GCD;
        }
        if s.style == "melee" {
            self.next_mh = 0.0;
            if !c.oh.is_empty() {
                self.next_oh = c.oh.speed_or(2.0) / 2.0;
            }
        } else if s.style == "ranged" {
            self.next_ranged = 0.0;
        }
        // Premeditation requires a stealth opener this sim doesn't model; approximated as a
        // one-time 2-combo-point grant at the start of the fight, its only realistic use case.
        if c.flag("premeditation") != 0.0 {
            self.cp = 5.min(self.cp + 2);
        }
        let dur = self.duration;
        let mut guard = 0;
        let mut cands: Vec<f64> = Vec::with_capacity(16);
        while self.t < dur - EPS && guard < 2_000_000 {
            guard += 1;
            self.use_offgcd();
            self.queue_swings();
            if self.t + EPS >= self.gcd_until && self.cast.is_none() && self.alive {
                match self.choose() {
                    Some(name) => self.start(&name),
                    None => {
                        if self.blocked_by_resource && s.resource == "Mana" {
                            self.starved += 0.25;
                        }
                    }
                }
            }
            cands.clear();
            cands.push(dur);
            if let Some(cast) = &self.cast {
                cands.push(cast.until);
                if cast.ticks_left > 0 {
                    cands.push(cast.next_tick);
                }
            } else if self.gcd_until > self.t + EPS {
                cands.push(self.gcd_until);
            } else {
                cands.push(self.t + 0.25);
            }
            if s.style == "melee" {
                cands.push(self.next_mh);
                if !c.oh.is_empty() {
                    cands.push(self.next_oh);
                }
            }
            if s.style == "ranged" {
                cands.push(self.next_ranged);
            }
            for d in self.dots.values() {
                if d.remaining > 0 {
                    cands.push(d.next);
                }
            }
            for (_, d) in self.dots_extra.iter() {
                if d.remaining > 0 {
                    cands.push(d.next);
                }
            }
            match s.resource.as_str() {
                "Mana" => cands.push(self.next_mana_tick),
                "Energy" => cands.push(self.next_energy_tick),
                _ => {
                    if c.flag("anger_management") != 0.0 {
                        cands.push(self.next_rage_tick);
                    }
                    if let Some(b) = self.buffs.get("Bloodrage") {
                        if b.until > self.t {
                            cands.push(b.next);
                        }
                    }
                }
            }
            if s.role == "tank" {
                cands.push(self.next_boss);
                cands.push(self.next_heal);
            }
            if c.pet.is_some() {
                cands.push(self.pet_next());
            }
            let mut nt = f64::INFINITY;
            for &x in &cands {
                if x > self.t + EPS && x < nt {
                    nt = x;
                }
            }
            if nt == f64::INFINITY {
                nt = dur;
            }
            self.t = nt.min(dur);
            if self.t >= dur - EPS {
                break;
            }
            let t = self.t;
            if let Some(cast) = &self.cast {
                if cast.ticks_left > 0 && (t - cast.next_tick).abs() < 1e-6 {
                    self.channel_tick();
                }
            }
            if let Some(cast) = &self.cast {
                if t + EPS >= cast.until {
                    self.complete_cast();
                }
            }
            let dot_names: Vec<String> = self.dots.iter().filter(|(_, d)| d.remaining > 0 && t + EPS >= d.next).map(|(n, _)| n.clone()).collect();
            for name in dot_names {
                self.dot_tick(&name);
            }
            let extra_idxs: Vec<usize> = self.dots_extra.iter().enumerate().filter(|(_, (_, d))| d.remaining > 0 && t + EPS >= d.next).map(|(i, _)| i).collect();
            for idx in extra_idxs {
                self.dot_tick_extra(idx);
            }
            if s.style == "melee" {
                if t + EPS >= self.next_mh {
                    if self.alive {
                        self.swing(Hand::Main);
                    }
                    self.next_mh = t + self.attack_delay(c.mh.speed_or(2.0), "melee");
                }
                if !c.oh.is_empty() && t + EPS >= self.next_oh {
                    if self.alive {
                        self.swing(Hand::Off);
                    }
                    self.next_oh = t + self.attack_delay(c.oh.speed_or(2.0), "melee");
                }
            }
            if s.style == "ranged" && t + EPS >= self.next_ranged && self.cast.as_ref().is_none_or(|cst| !c.actions[&cst.name].ranged_cast) {
                self.auto_shot();
                self.next_ranged = t + self.attack_delay(c.ranged.speed_or(2.8), "ranged");
            }
            if s.resource == "Mana" && t + EPS >= self.next_mana_tick {
                self.next_mana_tick += 2.0;
                let mp5 = self.st("mp5");
                let mut regen = mp5 / 5.0 * 2.0;
                let (frac, base) = c.t.SPIRIT_REGEN.get(&s.class_name).copied().unwrap_or((0.2, 15.0));
                let spirit_regen = self.st("spirit") * frac + base;
                if t - self.last_cast_time >= 5.0 {
                    regen += spirit_regen;
                } else {
                    regen += spirit_regen * c.flag("spirit_while_casting");
                }
                self.gain_mana(regen);
            }
            if s.resource == "Energy" && t + EPS >= self.next_energy_tick {
                self.next_energy_tick += 2.0;
                let mult = if self.buff_active("Adrenaline Rush") { 2.0 } else { 1.0 };
                self.gain_energy(20.0 * mult);
            }
            if s.resource == "Rage" {
                if c.flag("anger_management") != 0.0 && t + EPS >= self.next_rage_tick {
                    self.next_rage_tick += 3.0;
                    self.gain_rage(1.0);
                }
                let tick = self.buffs.get("Bloodrage").filter(|b| b.until > t && t + EPS >= b.next).map(|b| b.tick);
                if let Some(tick) = tick {
                    self.buffs.get_mut("Bloodrage").unwrap().next += 1.0;
                    self.gain_rage(tick);
                }
            }
            if s.role == "tank" {
                if t + EPS >= self.next_boss {
                    self.boss_swing();
                    self.next_boss += 2.0 / if c.debuffs.contains("thunder_clap") { 0.9 } else { 1.0 };
                }
                if t + EPS >= self.next_heal {
                    self.health = self.health_max.min(self.health + 2500.0);
                    self.next_heal += 2.0;
                }
            }
            if c.pet.is_some() {
                self.pet_step();
            }
            if self.resource() < 1.0 && s.resource == "Mana" && self.first_oom.is_none() {
                self.first_oom = Some(t);
            }
        }
        IterResult {
            total: self.total,
            threat: self.threat + self.pet_threat * 0.0,
            pet_threat: self.pet_threat,
            taken: self.taken,
            rows: self.rows,
            duration: dur,
            starved: self.starved,
            resource_end: match c.spec.resource.as_str() { "Mana" => self.mana, "Energy" => self.energy, _ => self.rage },
            alive: self.alive,
            alive_seconds: self.alive_seconds,
            first_oom: self.first_oom,
            taken_by: self.taken_by,
            log: self.log,
            buff_active_seconds: self.buff_active_seconds,
            buff_procs: self.buff_procs,
        }
    }
}
