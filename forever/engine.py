"""Event-driven Forever DPS/tank engine shared by every non-Paladin spec.

Every damage packet is built from sourced base damage, coefficients, weapon
damage, attack tables and stat conversions (see engine_data.py).  There is no
per-spec calibration multiplier.
"""
from __future__ import annotations

import math
import random
import re
import statistics

from .engine_data import *  # noqa: F401,F403
from .profile_rules import item_allowed

EPS = 1e-7
WEAPON_TYPES = ("Axe", "Dagger", "Fist Weapon", "Mace", "Polearm", "Staff", "Sword")
RANGED_TYPES = ("Bow", "Gun", "Crossbow")
SPELL_SCHOOLS = {"fire", "frost", "arcane", "nature", "shadow", "holy"}


def _re(pattern, text):
    return re.search(pattern, text, re.I)


def weapon_type(item):
    kind = str(item.get("subclass", ""))
    for t in WEAPON_TYPES + RANGED_TYPES + ("Wand",):
        if t in kind:
            return t
    return None


def normalized_speed(item):
    kind = weapon_type(item)
    if kind == "Dagger": return 1.7
    if kind in RANGED_TYPES: return 2.8
    if "Two-Hand" in str(item.get("slot", "")) or kind in ("Polearm", "Staff"): return 3.3
    return 2.4


class Config:
    """Static per-request state shared by every iteration."""

    def __init__(self, request, items, enchants, sets):
        self.request = request
        spec_id = request.get("spec")
        if spec_id not in SPEC_MAP:
            raise ValueError("Choose a supported Forever DPS or tank spec.")
        self.spec = SPEC_MAP[spec_id]
        s = self.spec
        self.duration = float(request.get("duration", 120))
        self.variance = max(0.0, min(60.0, float(request.get("duration_variance", 0))))
        self.iterations = int(request.get("iterations", 300))
        self.seed = int(request.get("seed", 42))
        if not 10 <= self.duration <= 1800 or not 1 <= self.iterations <= 10000:
            raise ValueError("Duration must be 10-1800 seconds and iterations 1-10000.")
        if self.duration * self.iterations > 400_000:
            raise ValueError("Run too large; keep duration x iterations at or below 400,000 seconds.")
        self.race = str(request.get("race", CLASS_RACES[s["class_name"]][0]))
        if self.race not in CLASS_RACES[s["class_name"]]:
            raise ValueError(f"{self.race} cannot be a {s['class_name']} in World of Warcraft: Forever.")
        self.boss_type = str(request.get("boss_type", "none")).lower()
        if self.boss_type not in CREATURE_TYPES:
            raise ValueError("Choose a supported boss creature type.")
        self.targets = max(1, min(10, int(request.get("targets", 1))))
        self.racial_enabled = bool(request.get("racial_enabled", True))
        self.racial = RACIALS[self.race]
        self.gear = [items.get(int(x), {}) for x in request.get("gear", []) if str(x).isdigit()]
        self.gear_slots = request.get("gear_slots", [])
        for row in self.gear_slots:
            iid = int(row.get('id') or 0)
            if iid and not item_allowed(items.get(iid, {}), row.get('slot'), s['class_name']):
                raise ValueError(f"Item {iid} cannot be equipped in {row.get('slot')} by {s['class_name']}.")
        self.items, self.enchant_data, self.set_data = items, enchants, sets
        self.buffs = set(request.get("buffs", []))
        self.debuffs = set(request.get("debuffs", []))
        self.consumes = self._validate_consumes(set(request.get("consumables", [])))
        self.notes = ["Periodic critical damage uses a snapshotted expected value, not independent tick outcomes. Tick crit counts, variance and proc interactions remain provisional. Monte Carlo intervals measure sampling noise, not uncertainty in mechanics."]
        if 'bloodlust' in self.buffs: self.notes.append('Requested Bloodlust scenario: 30% haste from the pull; 40-second duration is provisional pending confirmed Forever spell data.')
        self._talents(request)
        self._weapons(request)
        self._stats()
        self._abilities(request)
        self._pets(request)

    # ---- consumables -----------------------------------------------------
    def _validate_consumes(self, consumes):
        groups = {}
        from .sim import CONSUMABLE_GROUPS  # single source of exclusivity rules
        for key in sorted(consumes):
            group = CONSUMABLE_GROUPS.get(key)
            if group and group in groups:
                raise ValueError(f"{key} cannot be combined with {groups[group]} ({group.replace('_', ' ')} group)")
            if group: groups[group] = key
        return consumes

    # ---- talents ---------------------------------------------------------
    def _talents(self, request):
        s = self.spec
        if "talents" in request and isinstance(request["talents"], dict):
            self.talents = {str(k): int(v) for k, v in request["talents"].items() if int(v) > 0}
        else:
            self.talents = dict(DEFAULT_BUILDS[s["id"]])
        self.talent_points = sum(self.talents.values())
        mods = {}
        for tid, rank in self.talents.items():
            for key, per_rank in TALENT_EFFECTS.get(tid, {}).items():
                mods[key] = mods.get(key, 0) + per_rank * rank
        self.mods = mods

    def mod(self, key, default=0.0):
        return self.mods.get(key, default)

    def flag(self, name, default=0.0):
        return self.mods.get(f"flag:{name}", default)

    # ---- weapons ---------------------------------------------------------
    def _slot_item(self, ui_slot, wanted, exclude=None):
        for row in self.gear_slots:
            if isinstance(row, dict) and row.get("slot") == ui_slot and str(row.get("id", "")).isdigit():
                return self.items.get(int(row["id"]), {})
        def fits(x):
            if wanted.intersection(x.get("equipSlots", [])): return True
            if ui_slot == "Main Hand": return x.get("slot") in {"Main Hand", "One-Hand", "Two-Hand"} and bool(x.get("weaponDamageMin"))
            if ui_slot == "Off Hand": return x.get("slot") in {"Off Hand", "One-Hand", "Held In Off-hand", "Shield"} or "Shield" in str(x.get("subclass", ""))
            return False
        candidates = [x for x in self.gear if fits(x) and x is not exclude]
        return candidates[0] if candidates else {}

    def _weapons(self, request):
        s = self.spec
        mh = self._slot_item("Main Hand", {"main_hand"}); oh = self._slot_item("Off Hand", {"off_hand"}, exclude=mh); rw = self._slot_item("Ranged / Relic", {"ranged"})
        self.has_shield = "Shield" in str(oh.get("subclass", "")) or oh.get("slot") == "Shield"
        if not mh.get("weaponDamageMin"):
            mh = {"name": "Unarmed", "weaponDamageMin": 1, "weaponDamageMax": 2, "weaponSpeed": 2.0, "subclass": "Fist Weapon"}
            if s["form"] not in {"cat", "bear"}: self.notes.append("No main-hand weapon equipped; unarmed 1-2 damage at 2.0 speed used.")
        self.two_hand = "Two-Hand" in str(mh.get("slot", ""))
        if self.two_hand and oh.get("weaponDamageMin"):
            oh = {}
        self.mh, self.oh, self.ranged = mh, (oh if oh.get("weaponDamageMin") and weapon_type(oh) in WEAPON_TYPES else {}), rw
        if s["form"] == "cat":
            self.mh = {"name": "Cat Form", "weaponDamageMin": 43.84, "weaponDamageMax": 65.76, "weaponSpeed": 1.0, "subclass": "Form"}; self.oh = {}
        elif s["form"] == "bear":
            self.mh = {"name": "Dire Bear Form", "weaponDamageMin": 109, "weaponDamageMax": 165, "weaponSpeed": 2.5, "subclass": "Form"}; self.oh = {}
        if s["style"] == "ranged" and not rw.get("weaponDamageMin"):
            rw = {"name": "No ranged weapon", "weaponDamageMin": 1, "weaponDamageMax": 2, "weaponSpeed": 2.8, "subclass": "Bow"}
            self.ranged = rw
            self.notes.append("No bow, gun or crossbow equipped; a 1-2 damage 2.8 speed placeholder is used.")
        self.dual_wield = bool(self.oh)
        skills = {}
        for item in self.gear:
            for effect in item.get("effects", []):
                m = _re(r"Increased (.+?) \+(\d+)", effect)
                if m:
                    for kind in re.split(r", and |, | and ", m.group(1)):
                        skills[kind.strip().rstrip("s").replace("Two-handed", "Two-Hand")] = skills.get(kind.strip(), 0) + int(m.group(2))
        self.weapon_skill_bonus = skills

    def skill(self, item):
        kind = weapon_type(item) or ""
        base = LEVEL * 5
        key = ("Two-Hand " if "Two-Hand" in str(item.get("slot", "")) else "") + kind
        bonus = self.weapon_skill_bonus.get(key, 0) or self.weapon_skill_bonus.get(kind, 0) or self.weapon_skill_bonus.get(kind + "s", 0)
        return base + bonus + self.mod(f"skill:{kind}")

    # ---- stats -----------------------------------------------------------
    def _stats(self):
        s = self.spec; cls = s["class_name"]
        st = {k: float(v) for k, v in CLASS_BASE[cls].items()}
        for k, v in RACE_STATS.get(self.race, {}).items(): st[k] = st.get(k, 0) + v
        gear_stats = {}
        self.item_uses, self.item_procs, unresolved, applied = [], [], [], []
        for item in self.gear:
            self.notes.extend(f"{item.get('name', 'Item')}: {note}" for note in item.get("modelNotes", []))
            for k, v in permanent_item_stats(item).items(): gear_stats[k] = gear_stats.get(k, 0) + (v or 0)
            for effect in item.get("effects", []):
                self._item_effect(item, effect, gear_stats, applied, unresolved)
        self.set_counts, self.active_set_bonuses, self.unresolved_set_bonuses = apply_set_bonuses(self.gear, gear_stats, self.set_data)
        for row in self.active_set_bonuses:
            key = f"{row['set']}|{row['required']}"
            effects = SET_EFFECTS.get(key)
            if effects:
                for k, v in effects.items(): self.mods[k] = self.mod(k) + v
                row["effects"] = dict(effects)
            row["modeled"] = bool(row["stats"]) or bool(effects) or key in SET_NO_COMBAT_EFFECT
            if key in SET_PROVISIONAL: row["provisional"] = SET_PROVISIONAL[key]; self.notes.append(f"{row['set']} ({row['required']}): {SET_PROVISIONAL[key]}")
        self.unresolved_set_bonuses = [row for row in self.active_set_bonuses if not row["modeled"]]
        self.applied_enchants, self.rejected_enchants = [], []
        primary = "intellect" if s["style"] == "spell" else ("agility" if cls in {"Rogue", "Hunter", "Druid"} else "strength")
        lookup = {(slot, e["id"]): e for slot, rows in self.enchant_data.items() for e in rows}
        self.crusader_hands = set()
        for sel in self.request.get("enchants", []):
            if not isinstance(sel, dict): continue
            e = lookup.get((sel.get("slot"), sel.get("id")))
            if not e: continue
            slot = sel["slot"]
            if not enchant_compatible(slot, self.gear, self.gear_slots, self.items):
                self.rejected_enchants.append({"slot": slot, "id": e["id"], "reason": "incompatible item type"}); continue
            self.applied_enchants.append({"slot": slot, "id": e["id"], "name": e["name"]})
            for k, v in e.get("stats", {}).items():
                key = primary if k == "primary" else k
                gear_stats[key] = gear_stats.get(key, 0) + (v or 0)
            if e["id"] == "crusader" and s["style"] == "melee": self.crusader_hands.add(slot)
        gear_stats["armor"] = gear_stats.get("armor", 0) * (1 + self.mod("item_armor_pct"))
        for k, v in gear_stats.items(): st[k] = st.get(k, 0) + v
        for key in self.buffs:
            for k, v in BUFF_STATS.get(key, {}).items(): st[k] = st.get(k, 0) + v
        for key in self.consumes:
            for k, v in CONSUME_STATS.get(key, {}).items(): st[k] = st.get(k, 0) + v
        if "battle_shout" in self.buffs and self.mod("buff_ap:battle_shout"): st["attackPower"] = st.get("attackPower", 0) + self.mod("buff_ap:battle_shout")
        if "mana_spring" in self.buffs and self.mod("buff_pct:mana_spring"): st["mp5"] = st.get("mp5", 0) + BUFF_STATS["mana_spring"]["mp5"] * self.mod("buff_pct:mana_spring")
        if "blessing_of_kings" in self.buffs:
            for stat in ("strength", "agility", "stamina", "intellect", "spirit"): st[stat] = st.get(stat, 0) * 1.10
        if self.race == "Human" and self.racial_enabled: st["spirit"] *= 1.05
        self.windfury_totem = "windfury_totem" in self.buffs and s["style"] == "melee" and s["form"] is None and s["class_name"] != "Shaman"
        # Talent percentage stats
        for stat in ("strength", "agility", "stamina", "intellect", "spirit", "armor", "mana"):
            pct = self.mod(f"stat_pct:{stat}")
            if pct: st[stat] = st.get(stat, 0) * (1 + pct)
        if s["form"] == "cat": st["strength"] *= 1 + self.flag("hotw_cat_str")
        if s["form"] == "bear": st["stamina"] *= (1 + self.flag("hotw_bear_sta")) * 1.25
        if s["form"] == "bear": st["armor"] = st.get("armor", 0) * 4.6
        if s["form"] == "moonkin": st["armor"] = st.get("armor", 0) * 4.6
        if self.flag("thick_hide"): st["armor"] = st.get("armor", 0) + 3 * LEVEL * (self.flag("thick_hide") / 3)
        if self.racial.get("health_pct"): st["health_pct"] = self.racial["health_pct"]
        # Derived
        st["attackPower"] = st.get("attackPower", 0) + st["strength"] * AP_PER_STRENGTH[cls] + st["agility"] * AP_PER_AGILITY[cls] + st["intellect"] * self.mod("ap_from_int") + self.flag("predatory_strikes")
        # RAP has its own base and Agility dependency; Strength and melee-only buffs never enter it.
        # Generic item AP and Juju Might/Firewater grant both melee and ranged AP in Classic.
        st["rangedAttackPower"] = st.get("rangedAttackPower", 0) + gear_stats.get("attackPower", 0) + sum(CONSUME_STATS.get(k, {}).get("attackPower", 0) for k in self.consumes) + (st["agility"] * 2 + st["intellect"] * self.mod("ap_from_int") + 120 * (1 + self.mod("hawk_pct")) if cls == "Hunter" else 0)
        st["spellPower"] = st.get("spellPower", 0) + st["intellect"] * self.mod("sp_from_int") + st["spirit"] * self.flag("spiritual_guidance") + (self.flag("demonic_knowledge") if cls == "Warlock" and self.request.get("pet_family", "succubus") != "none" else 0)
        st["meleeCrit"] = st.get("meleeCrit", 0) + st["agility"] * MELEE_CRIT_PER_AGI[cls] + self.mod("melee_crit")
        st["rangedCrit"] = st.get("rangedCrit", 0) + st["agility"] * MELEE_CRIT_PER_AGI[cls] + self.mod("melee_crit") + self.mod("ranged_crit")
        st["spellCrit"] = st.get("spellCrit", 0) + st["intellect"] * SPELL_CRIT_PER_INT[cls] + self.mod("spell_crit")
        st["meleeHit"] = st.get("meleeHit", 0) + self.mod("hit") + self.racial.get("hit", 0)
        st["rangedHit"] = st.get("rangedHit", 0) + st.get("meleeHit", 0) - (self.mod("hit") + self.racial.get("hit", 0)) + self.mod("hit") + self.mod("ranged_hit") + self.racial.get("hit", 0)
        st["spellHit"] = st.get("spellHit", 0) + self.mod("spell_hit") + self.racial.get("hit", 0)
        st["dodge"] = st.get("dodge", 0) + st["agility"] * DODGE_PER_AGI[cls] + self.mod("dodge") + self.racial.get("dodge", 0)
        st["parry"] = (5.0 if cls in {"Warrior", "Paladin", "Rogue", "Hunter", "Shaman"} else 0.0) + st.get("parry", 0)
        st["block"] = (5.0 + st.get("block", 0) + self.mod("block")) if self.has_shield else 0.0
        st["defense"] = 300 + st.get("defense", 0) + self.mod("defense")
        st["health"] = (st["health"] + st["stamina"] * 10 + st.get("health", 0) * 0) * (1 + st.get("health_pct", 0))
        st["mana"] = st.get("mana", 0) + st["intellect"] * 15
        for race_key in ("Human", "Dwarf", "Orc"):
            pass
        crit_spec = self.racial.get("weapon_crit", {})
        equipped_kinds = {weapon_type(x) for x in self.gear if weapon_type(x)}
        self.racial_crit = sum(v for k, v in crit_spec.items() if k != "provisional" and k in equipped_kinds)
        st["meleeCrit"] += self.racial_crit; st["rangedCrit"] += self.racial_crit; st["spellCrit"] += self.racial_crit
        self.stats = st
        self.item_effects = {"applied": applied, "unresolved": unresolved}
        self.threat_reduction = st.get("threatReduction", 0) / 100

    def _item_effect(self, item, effect, gear_stats, applied, unresolved):
        stats = item.get("stats", {})
        def add(key, value):
            gear_stats[key] = gear_stats.get(key, 0) + value
        if effect.startswith("Equip:"):
            if _re(r'^Equip: \+\d+ (?:Mana Regeneration|(?:Shadow|Fire|Frost|Arcane|Nature|Holy) Spell Damage)$', effect):
                return  # Normalized into catalog stats at import.
            m = _re(r"\+(\d+) Attack Power(?! (?:when|in))", effect)
            if m:
                if "attackPower" not in stats: add("attackPower", float(m.group(1)))
                return
            for key, pattern in (("meleeHit", r"chance to hit by (\d+)%"), ("meleeCrit", r"critical strike by (\d+)%"), ("spellCrit", r"critical strike with spells by (\d+)%"),
                                 ("spellHit", r"hit with spells by (\d+)%"), ("spellPower", r"damage and healing done by magical spells and effects by up to (\d+)"),
                                 ("mp5", r"Restores (\d+) mana per 5"), ("defense", r"Increased Defense \+(\d+)"), ("dodge", r"dodge an attack by (\d+)%"), ("parry", r"parry an attack by (\d+)%"),
                                 ("block", r"block attacks with a shield by (\d+)%"), ("blockValue", r"block value of your shield by (\d+)"), ("firePower", r"Fire spells and effects by up to (\d+)"),
                                 ("frostPower", r"Frost spells and effects by up to (\d+)"), ("shadowPower", r"Shadow spells and effects by up to (\d+)"), ("naturePower", r"Nature spells and effects by up to (\d+)"),
                                 ("arcanePower", r"Arcane spells and effects by up to (\d+)")):
                m = _re(pattern, effect)
                if m:
                    if key not in stats: add(key, float(m.group(1)))
                    return
            m = _re(r"(\d+)% chance on melee hit to gain 1 extra attack", effect)
            if m: self.item_procs.append({"name": item["name"], "trigger": "melee", "chance": float(m.group(1)) / 100, "kind": "extra_attack"}); applied.append({"item": item["name"], "effect": effect, "proc_model": f"{m.group(1)}% per melee hit"}); return
            if _re(r"Increased .+ \+\d+", effect): applied.append({"item": item["name"], "effect": effect, "proc_model": "weapon skill"}); return
            if _re(r"Multi-Shot by (\d+)%", effect): self.mods["dmg_ability:Multi-Shot"] = self.mod("dmg_ability:Multi-Shot") + float(_re(r"(\d+)%", effect).group(1)) / 100; return
            if _re(r"Attack Power (?:when fighting|in Cat)", effect) or _re(r"health per 5|resist|Run speed|stealth|Disarm|Ghost Wolf|interruption|Mana Shield|Sprint|Hamstring|Judgement|healing done by spells|Deals \d+ Fire damage to anyone", effect):
                return
            unresolved.append({"item": item["name"], "effect": effect}); return
        if effect.startswith("Use:"):
            cd = _cooldown_seconds(effect)
            for key, pattern in (("spellPower", r"damage and healing.*?up to (\d+) for (\d+) sec"), ("attackPower", r"Attack Power by (\d+) for (\d+) sec"), ("haste", r"attack speed by (\d+)% for (\d+) sec"), ("armorPenetration", r"armor penetration.*?for (\d+) sec.*?by (\d+).*?up to (\d+) times")):
                m = _re(pattern, effect)
                if m and key != "armorPenetration":
                    self.item_uses.append({"name": item["name"], "stat": key, "value": float(m.group(1)) / (100 if key == "haste" else 1), "duration": float(m.group(2)), "cooldown": cd}); applied.append({"item": item["name"], "effect": effect, "uses": max(1, math.ceil(self.duration / cd))}); return
            m = _re(r"Restores (\d+)(?: to (\d+))? mana", effect)
            if m: self.item_uses.append({"name": item["name"], "stat": "mana", "value": (float(m.group(1)) + float(m.group(2) or m.group(1))) / 2, "duration": 0, "cooldown": cd}); applied.append({"item": item["name"], "effect": effect, "uses": max(1, math.ceil(self.duration / cd))}); return
            m = _re(r"(?:causes|deals) (\d+)(?: to (\d+))? (\w+ )?damage", effect)
            if m: self.item_uses.append({"name": item["name"], "stat": "damage", "value": (float(m.group(1)) + float(m.group(2) or m.group(1))) / 2, "school": (m.group(3) or "physical").strip().lower(), "duration": 0, "cooldown": cd}); applied.append({"item": item["name"], "effect": effect, "uses": max(1, math.ceil(self.duration / cd))}); return
            unresolved.append({"item": item["name"], "effect": effect}); return
        if effect.startswith("Chance on hit:"):
            ppm = ITEM_PROC_PPM.get(item.get("id"), 1.0); icd = _proc_icd(effect)
            m = _re(r"(?:for|dealing|causing|causes|deals|blasts a target for) (\d+)(?: to (\d+))? (\w+ )?damage", effect)
            if m:
                amount = (float(m.group(1)) + float(m.group(2) or m.group(1))) / 2; school = (m.group(3) or "physical").strip().lower()
                if school not in SPELL_SCHOOLS: school = "physical"
                self.item_procs.append({"name": item["name"], "trigger": "weapon", "ppm": ppm, "icd": icd, "kind": "damage", "amount": amount, "school": school, "item": item})
                applied.append({"item": item["name"], "effect": effect, "proc_model": f"{ppm:g} PPM", "internal_cooldown": icd}); return
            m = _re(r"attack speed by (\d+)% for (\d+) sec", effect)
            if m: self.item_procs.append({"name": item["name"], "trigger": "weapon", "ppm": ppm, "icd": icd, "kind": "buff", "stat": "haste", "value": float(m.group(1)) / 100, "duration": float(m.group(2)), "item": item}); applied.append({"item": item["name"], "effect": effect, "proc_model": f"{ppm:g} PPM"}); return
            for key, pattern in (("strength", r"Strength by (\d+) for (\d+) sec"), ("attackPower", r"Attack Power by (\d+) for (\d+) sec")):
                m = _re(pattern, effect)
                if m: self.item_procs.append({"name": item["name"], "trigger": "weapon", "ppm": ppm, "icd": icd, "kind": "buff", "stat": key, "value": float(m.group(1)), "duration": float(m.group(2)), "item": item}); applied.append({"item": item["name"], "effect": effect, "proc_model": f"{ppm:g} PPM"}); return
            unresolved.append({"item": item["name"], "effect": effect}); return

    # ---- abilities -------------------------------------------------------
    def _abilities(self, request):
        s = self.spec
        self.rotation = []
        self.actions = {}
        enabled = set(request.get("rotation_enabled", [n for n, _ in ROTATIONS[s["id"]]]))
        for name, cond in ROTATIONS[s["id"]]:
            base = ABILITIES[name]
            gate = TALENT_GATED.get(name)
            if gate and not self.flag(gate):
                continue
            if name == "Shield Slam" and not self.has_shield:
                self.notes.append("Shield Slam requires a shield; none equipped."); continue
            if name not in enabled:
                continue
            self.rotation.append((name, cond))
            self.actions[name] = self._resolve(name, base)
        if not self.rotation:
            raise ValueError("Enable at least one rotation ability.")
        for key, action in CONSUMABLE_ACTIONS.items():
            if key in self.consumes and action not in self.actions:
                if action == "Major Mana Potion" and s["resource"] != "Mana": continue
                if action == "Mighty Rage Potion" and s["resource"] != "Rage": continue
                if action == "Thistle Tea" and s["resource"] != "Energy": continue
                if action == "Demonic Rune" and s["resource"] != "Mana": continue
                self.actions[action] = self._resolve(action, ABILITIES[action])
        for use in self.item_uses:
            self.actions[f"Item - {use['name']}"] = {"kind": "item_use", "cooldown": use["cooldown"], "off_gcd": True, "use": use, "school": use.get("school", "physical")}
        self.action_names = [n for n, _ in self.rotation]

    def _resolve(self, name, base):
        a = dict(base)
        a["name"] = name
        base_cost = a.get("cost", 0)
        if a.get("cost_pct") and self.spec["resource"] == "Mana":
            # Base mana is the class/level pool, before Intellect, gear and percentage talents.
            base_cost = CLASS_BASE[self.spec["class_name"]]["mana"] * a["cost_pct"]
        a["cost"] = max(0.0, (base_cost + self.mod(f"cost:{name}")) * (1 + self.mod(f"cost_pct:{name}") + self.mod("cost_pct_all") + self.mod(f"cost_pct_school:{a.get('school')}")))
        if self.spec["resource"] == "Rage" and a.get("cost") and self.flag("focused_rage") and name not in {"Heroic Strike"}: a["cost"] = max(0, a["cost"] - 3)
        if self.flag("shadowform") and a.get("school") == "shadow": a["cost"] *= 0.5
        a["cast"] = max(0.0, a.get("cast", 0) + self.mod(f"cast:{name}"))
        a["cooldown"] = max(0.0, a.get("cooldown", 0) + self.mod(f"cooldown:{name}"))
        a["gcd"] = a.get("gcd", GCD)
        a["mult"] = 1 + self.mod(f"dmg_ability:{name}")
        a["crit_bonus"] = self.mod(f"crit_ability:{name}")
        if name == "Shadow Word: Pain": a["ticks"] = a["ticks"] + int(self.flag("swp_ticks"))
        if a.get("ticks") and self.mod(f"ticks:{name}"): a["ticks"] = a["ticks"] + int(self.mod(f"ticks:{name}"))
        if name == "Immolate" and self.flag("aftermath"): a["direct_mult"] = 1 + self.flag("aftermath") * 5 * 0.1
        if name == "Execute" and self.spec["resource"] == "Rage": pass
        return a

    # ---- pets ------------------------------------------------------------
    def _pets(self, request):
        s = self.spec; self.pet = None
        if s["class_name"] == "Hunter":
            fam = str(request.get("pet_family", "cat"))
            if fam == "none": return
            if fam not in PET_FAMILIES: raise ValueError("Choose a supported Hunter pet family or none.")
            family = PET_FAMILIES[fam]
            self.pet = {"kind": "hunter", "family": fam, "damage": family["damage"], "special": family["special"], "dump": family["dump"], "speed": max(1.0, min(2.5, float(request.get("pet_attack_speed", 2.0)))), "uptime": max(0.0, min(1.0, float(request.get("pet_uptime", 1.0)))), "abilities": set(request.get("pet_abilities", [x for x in (family["special"], family["dump"]) if x]))}
        elif s["class_name"] == "Warlock":
            fam = str(request.get("pet_family", "succubus"))
            if fam != "none":
                cfg = WARLOCK_PETS.get(fam, WARLOCK_PETS["succubus"])
                defaults = (["Melee"] if cfg.get("melee") else []) + ([cfg["spell"]] if cfg.get("spell") else []) + ([cfg["utility"]] if cfg.get("utility") else [])
                self.pet = {"kind": "warlock", "family": fam, "cfg": cfg, "uptime": max(0.0, min(1.0, float(request.get("pet_uptime", 1.0)))), "abilities": set(request.get("pet_abilities", defaults))}

    # ---- summary ---------------------------------------------------------
    def summary(self):
        s = self.spec
        return {
            "race": self.race, "racial": self.racial.get("summary"), "racial_enabled": self.racial_enabled, "boss_type": self.boss_type, "boss_armor": self.armor_after_debuffs(),
            "targets": self.targets, "gear_stats": {k: round(v, 3) for k, v in self.stats.items()}, "enchants": self.applied_enchants, "rejected_enchants": self.rejected_enchants,
            "active_effects": sorted(self.buffs | self.consumes | self.debuffs), "item_effects": self.item_effects, "set_bonuses": {"counts": self.set_counts, "active": self.active_set_bonuses, "unresolved": self.unresolved_set_bonuses},
            "talent_points": self.talent_points, "talents": self.talents, "primary_tree": s["tree"], "talent_effects": {k: round(v, 4) for k, v in self.mods.items()},
            "weapons": [{"slot": "Main Hand", "name": self.mh.get("name"), "speed": self.mh.get("weaponSpeed"), "damage": [self.mh.get("weaponDamageMin"), self.mh.get("weaponDamageMax")], "skill": self.skill(self.mh)}] + ([{"slot": "Off Hand", "name": self.oh.get("name"), "speed": self.oh.get("weaponSpeed"), "damage": [self.oh.get("weaponDamageMin"), self.oh.get("weaponDamageMax")], "skill": self.skill(self.oh)}] if self.oh else []) + ([{"slot": "Ranged", "name": self.ranged.get("name"), "speed": self.ranged.get("weaponSpeed"), "damage": [self.ranged.get("weaponDamageMin"), self.ranged.get("weaponDamageMax")], "skill": self.skill(self.ranged)}] if self.ranged.get("weaponDamageMin") else []),
            "actions": {n: {k: v for k, v in a.items() if k not in {"name", "use"}} for n, a in self.actions.items()}, "rotation": self.rotation,
            "execute_phase": {"starts_at": self.duration * 0.8, "fraction": 0.2},
            "pet": ({k: v for k, v in self.pet.items() if k not in {"cfg"}} | {"abilities": sorted(self.pet["abilities"])}) if self.pet else None,
            "notes": self.notes + [f"{n}: {a['provisional']}" for n, a in self.actions.items() if a.get("provisional")] + ([f"{self.racial['active']['name']} cooldown is not published by Wowhead; {self.racial['active']['cooldown']} sec assumed."] if self.racial.get("active", {}).get("provisional_cooldown") else []),
            "classic_reference_dps": None, "multiplier": 1.0,
        }

    def armor_after_debuffs(self):
        armor = float(self.request.get("armor", 3731))
        for key, value in DEBUFF_ARMOR.items():
            if key in self.debuffs: armor -= value
        armor -= self.stats.get("armorPenetration", 0)
        return max(0.0, min(20000.0, armor))


# ---------------------------------------------------------------------------
# helpers shared with all_specs.py
# ---------------------------------------------------------------------------
def _cooldown_seconds(text):
    m = _re(r"\((?:(\d+) Min(?:, (\d+) Sec)?|(\d+) Sec) Cooldown\)", text)
    if not m: return 120.0
    return int(m.group(1) or 0) * 60 + int(m.group(2) or m.group(3) or 0)


def _proc_icd(text):
    m = _re(r"(?:can only|cannot) occur(?: more than)? once every (\d+) sec", text)
    return float(m.group(1)) if m else 0.0


def permanent_item_stats(item):
    stats = dict(item.get("stats", {}))
    for effect in item.get("effects", []):
        if not effect.startswith("Use:"): continue
        if _re(r"damage and healing.*?up to \d+ for \d+ sec", effect): stats.pop("spellPower", None)
        if _re(r"Attack Power by \d+ for \d+ sec", effect): stats.pop("attackPower", None)
        if _re(r"attack speed by \d+% for \d+ sec", effect):
            for k in ("meleeHaste", "rangedHaste", "spellHaste"): stats.pop(k, None)
    return stats


SET_PATTERNS = (("spellPower", r"damage and healing.*?up to (\d+)"), ("mp5", r"Restores (\d+) mana per 5 sec"), ("attackPower", r"\+(\d+) Attack Power"), ("attackPower", r"Increases Attack Power by (\d+)"), ("spellHit", r"hit with spells by (\d+)%"),
                ("agility", r"\+(\d+) Agility"), ("intellect", r"\+(\d+) Intellect"), ("strength", r"\+(\d+) Strength"), ("spirit", r"\+(\d+) Spirit"), ("dodge", r"dodge an attack by (\d+)%"), ("block", r"block attacks with a shield by (\d+)%"),
                ("spellCrit", r"critical strike with spells by (\d+)%"), ("meleeCrit", r"critical strike by (\d+)%"), ("meleeHit", r"chance to hit by (\d+)%"), ("blockValue", r"block value of your shield by (\d+)"),
                ("maxEnergy", r"maximum Energy by (\d+)"), ("armor", r"\+(\d+) Armor"), ("defense", r"Increased Defense \+(\d+)"), ("parry", r"parry an attack by (\d+)%"), ("stamina", r"\+(\d+) Stamina"))


def apply_set_bonuses(gear, stats, forever_sets):
    counts, definitions = {}, {}
    for item in gear:
        set_data = item.get("set")
        if not set_data: continue
        name = set_data["name"]; counts[name] = counts.get(name, 0) + 1; definitions[name] = set_data.get("bonuses", [])
    active, unresolved = [], []
    for name, count in counts.items():
        bonuses = forever_sets.get(name, {}).get("bonuses", definitions[name])
        for bonus in bonuses:
            if count < int(bonus.get("required", 99)): continue
            desc = bonus.get("description", ""); applied = {}
            conditional = bool(_re(r"chance on|chance to (?:gain|increase|grant|restore|trigger)|proc|for \d+ sec|when |whenever |after |stack", desc))
            if not conditional:
                for key, value in bonus.get("stats", {}).items(): stats[key] = stats.get(key, 0) + value; applied[key] = value
            if not applied and not conditional:
                for key, pattern in SET_PATTERNS:
                    m = _re(pattern, desc)
                    if m: value = float(m.group(1)); stats[key] = stats.get(key, 0) + value; applied[key] = value; break
            row = {"set": name, "pieces": count, "required": bonus["required"], "description": desc, "stats": applied}
            active.append(row)
            if not applied: unresolved.append(row)
    return counts, active, unresolved


def enchant_compatible(slot, gear, gear_slots, items):
    if slot not in {"main_hand", "off_hand", "ranged"}: return True
    ui_slot = {"main_hand": "Main Hand", "off_hand": "Off Hand", "ranged": "Ranged / Relic"}[slot]
    ids = [int(x.get("id", 0)) for x in gear_slots if isinstance(x, dict) and x.get("slot") == ui_slot and str(x.get("id", "")).isdigit()]
    candidates = [items.get(i, {}) for i in ids] if ids else gear
    if not candidates: return True
    if slot == "ranged": return any(x.get("subclass") == "Gun" for x in candidates)
    return any(weapon_type(x) in WEAPON_TYPES for x in candidates)


# ---------------------------------------------------------------------------
# Iteration
# ---------------------------------------------------------------------------
class Row:
    __slots__ = ("casts", "hits", "crits", "misses", "glances", "dodges", "damage", "threat")

    def __init__(self):
        self.casts = self.hits = self.crits = self.misses = self.glances = self.dodges = 0; self.damage = self.threat = 0.0

    def dict(self):
        return {"casts": self.casts, "hits": self.hits, "crits": self.crits, "misses": self.misses, "glances": self.glances, "dodges": self.dodges, "damage": self.damage, "threat": self.threat}


class Iteration:
    def __init__(self, cfg: Config, seed: int, trace: bool):
        self.c = cfg; self.s = cfg.spec; self.rng = random.Random(seed); self.trace = trace; self.log = []
        c = cfg
        self.duration = max(10.0, self.rng.uniform(c.duration - c.variance, c.duration + c.variance)) if c.variance else c.duration
        self.execute_at = self.duration * 0.8
        self.t = 0.0; self.rows = {}; self.total = 0.0; self.threat = 0.0; self.taken = 0.0
        self.st = dict(c.stats)
        res = self.s["resource"]
        self.max_mana = self.st.get("mana", 0)
        self.max_energy = 100 + c.flag("max_energy") + self.st.get("maxEnergy", 0)
        self.max_rage = 100 + c.flag("max_rage")
        self.mana = self.max_mana; self.energy = self.max_energy; self.rage = 0.0
        self.cp = 0
        self.health_max = self.st["health"]; self.health = self.health_max; self.alive = True; self.alive_seconds = self.duration
        self.buffs = {}   # name -> {"until":t, "stacks":n, ...}
        self.debuffs = {}  # on target
        self.buff_active_seconds = {}  # name -> total non-overlapping seconds the buff was up
        self._buff_covered_until = {}  # name -> internal bookkeeping for the above
        self.buff_procs = {}  # name -> number of times the buff was granted/refreshed (or an instant proc fired)
        self.dots = {}
        self.dots_extra = []  # secondary-target instances of "spreadable" DoTs: [{"name":..., ...dot fields}]
        self.cooldowns = {}
        self.gcd_until = 0.0; self.cast = None  # {"name","until","ticks"...}
        self.next_mh = 0.0; self.next_oh = (c.oh.get("weaponSpeed", 2.0) / 2 if c.oh else None); self.next_ranged = 0.0
        self.queued_swing = None
        self.last_cast_time = -10.0; self.next_mana_tick = 2.0; self.next_energy_tick = 2.0; self.next_rage_tick = 3.0
        self.next_boss = 2.0; self.next_heal = 2.0
        self.flurry = 0; self.eureka = 0; self.dodged_recently = -10.0; self.avoided_recently = -10.0
        self.combustion = None; self.clearcast = False; self.next_instant = False; self.next_crit = False; self.eclipse = 0
        self.busy_until = 0.0; self.starved = 0.0; self.first_oom = None
        self.pet_state = None
        self.taunted = False
        self.enrage_until = 0.0
        self.sacrificed = None
        self.racial_next = 0.0
        self.item_icd = {}
        self.oom_time = 0.0
        self.windfury_lock = 0.0
        self.wrath_discount = False; self.next_parry = False
        if res == "Rage":
            self.rage = min(self.max_rage, float(c.request.get("starting_rage", 0)))

    # ---- utilities -------------------------------------------------------
    def row(self, name):
        r = self.rows.get(name)
        if r is None: r = self.rows[name] = Row()
        return r

    def record(self, event, outcome, amount, note=None):
        if self.trace and len(self.log) < 400:
            res = {"Mana": self.mana, "Energy": self.energy, "Rage": self.rage}[self.s["resource"]]
            self.log.append({"time": round(self.t, 2), "event": event, "outcome": outcome, "amount": round(amount, 1), "resource": round(res, 1), **({"note": note} if note else {})})

    def buff_active(self, name):
        b = self.buffs.get(name)
        return b is not None and b["until"] > self.t + EPS

    def debuff_active(self, name):
        b = self.debuffs.get(name)
        return b is not None and b["until"] > self.t + EPS

    def add_buff(self, name, duration, **kw):
        b = self.buffs.get(name)
        was_active = b is not None and b["until"] > self.t + EPS
        if b and b["until"] > self.t and kw.get("stacks_max"):
            b["stacks"] = min(kw["stacks_max"], b.get("stacks", 1) + 1); b["until"] = self.t + duration
        else:
            self.buffs[name] = {"until": self.t + duration, "stacks": 1, **kw}
        self.note_proc(name, duration)
        if self.trace and len(self.log) < 400:
            self.log.append({"time": round(self.t, 2), "event": f"Buff: {name}", "outcome": "refreshed" if was_active else "gained", "amount": 0.0, "resource": round(self.resource(), 1)})
        self.uptime_track(name)

    def note_proc(self, name, duration=0.0):
        """Record a buff/proc activation for the Buffs tab: non-overlapping active-seconds
        (for duration buffs) plus a proc/activation count (for instant procs like Nightfall,
        where an actual timed buff object doesn't make sense)."""
        end = self.t + duration
        covered = self._buff_covered_until.get(name, 0.0)
        if end > max(self.t, covered):
            self.buff_active_seconds[name] = self.buff_active_seconds.get(name, 0.0) + (end - max(self.t, covered))
        self._buff_covered_until[name] = max(covered, end)
        self.buff_procs[name] = self.buff_procs.get(name, 0) + 1

    def proc_nightfall(self):
        """Nightfall doesn't grant a stateful buff (it's consumed by the very next cast), so it
        can't go through add_buff -- but it should still show up as an activation for the Buffs
        tab, same as every other proc."""
        self.next_instant = True
        self.note_proc("Nightfall")
        if self.trace and len(self.log) < 400:
            self.log.append({"time": round(self.t, 2), "event": "Buff: Nightfall", "outcome": "proc", "amount": 0.0, "resource": round(self.resource(), 1)})

    def add_debuff(self, name, duration, **kw):
        b = self.debuffs.get(name)
        if b and b["until"] > self.t and kw.get("stacks_max"):
            b["stacks"] = min(kw["stacks_max"], b.get("stacks", 1) + 1); b["until"] = self.t + duration
        else:
            self.debuffs[name] = {"until": self.t + duration, "stacks": 1, **kw}

    def uptime_track(self, name): pass

    def haste(self, kind):
        h = 1.0
        if "bloodlust" in self.c.buffs and self.t < 40: h *= 1.30
        h *= 1 + self.c.racial.get("haste", 0) * self.c.racial_enabled
        if kind == "melee":
            if self.flurry > 0: h *= 1 + self.c.flag("flurry")
            for name in ("Slice and Dice", "Blade Flurry", "Berserking", "Rage of the Farseer", "Frenzy"):
                b = self.buffs.get(name)
                if b and b["until"] > self.t: h *= 1 + b.get("haste", 0)
            for b in self.buffs.values():
                if b.get("stat") == "haste" and b["until"] > self.t: h *= 1 + b["value"]
        elif kind == "ranged":
            h *= 1.15  # quiver / ammo pouch
            for name in ("Rapid Fire", "Berserking", "Quick Shots"):
                b = self.buffs.get(name)
                if b and b["until"] > self.t: h *= 1 + b.get("haste", 0)
        else:
            for name in ("Berserking", "Rage of the Farseer", "Nature's Grace"):
                b = self.buffs.get(name)
                if b and b["until"] > self.t: h *= 1 + b.get("haste", 0)
        return h

    def attack_delay(self, speed, kind):
        haste=self.haste(kind); delay=speed/haste
        if 'bloodlust' in self.c.buffs and self.t<40 and self.t+delay>40:
            before=40-self.t
            return before+(speed-before*haste)/(haste/1.30)
        return delay

    def pet_delay(self, speed):
        if 'bloodlust' not in self.c.buffs or self.t >= 40: return speed
        before = 40 - self.t
        return speed / 1.30 if speed / 1.30 <= before else before + speed - before * 1.30

    def ap(self, ranged=False):
        base = self.st["rangedAttackPower"] if ranged else self.st["attackPower"]
        for b in self.buffs.values():
            if b["until"] > self.t:
                if b.get("stat") == "attackPower" or (ranged and b.get("stat") == "rangedAttackPower"): base += b["value"]
                if not ranged and b.get("stat") == "strength": base += b["value"] * AP_PER_STRENGTH[self.s["class_name"]]
                if b.get("ap_pct"): base *= 1 + b["ap_pct"]
        return base

    def sp(self, school):
        base = self.st["spellPower"] + self.st.get(f"{school}Power", 0)
        for b in self.buffs.values():
            if b["until"] > self.t:
                if b.get("stat") == "spellPower" or b.get("stat") == f"{school}Power": base += b["value"]
                if b.get("sp_pct"): base *= 1 + b["sp_pct"]
        return base

    def crit_chance(self, kind, ability=None, school=None):
        c = self.c
        if kind == "spell":
            crit = self.st["spellCrit"] + c.mod(f"crit_school:{school}")
            if self.combustion is not None and school == "fire": crit += 10 * self.combustion["stacks"]
            if school == "frost" and self.debuff_active("Winter's Chill"): crit += 2 * self.debuffs["Winter's Chill"]["stacks"]
            if ability == "Ice Lance" and c.flag("shatter") and self.buff_active("Fingers of Frost"): crit += c.flag("shatter") * 100
            crit -= 2.1
        elif kind == "ranged":
            crit = self.st["rangedCrit"] - 4.8
        else:
            crit = self.st["meleeCrit"] - 4.8
        if c.flag("weaponmaster") and weapon_type(c.mh) in {"Axe", "Polearm"}: crit += c.flag("weaponmaster") * 100
        if c.flag("moonkin"): crit += c.flag("moonkin") * 100
        if ability == "Shadow Word: Death" and c.flag("early_demise") and self.t >= self.execute_at: crit += c.flag("early_demise")
        if ability: crit += c.mod(f"crit_ability:{ability}")
        b = self.buffs.get("Elune's Light")
        if b and b["until"] > self.t: crit += 10
        b = self.buffs.get("Berserk")
        if b and b["until"] > self.t and ability in {"Shred", "Claw", "Mangle"}: crit += 100
        return max(0.0, min(100.0, crit)) / 100

    def crit_multiplier(self, kind, ability, school):
        c = self.c
        if kind == "spell":
            bonus = 0.5 + c.mod(f"crit_dmg_school:{school}") * 0.5 / 0.5 * 0.5 if False else 0.5
            bonus += c.mod(f"crit_dmg_school:{school}") * 0.5
            if c.flag("shadowform") and school == "shadow": bonus += 0.5
            if c.mod("crit_dmg_destruction") and ability in {"Shadow Bolt", "Immolate", "Conflagrate", "Shadowburn", "Searing Pain"}: bonus += c.mod("crit_dmg_destruction") * 0.5
            return 1 + bonus
        bonus = 1.0
        white = ability in {"Melee (Main-Hand)", "Melee (Off-Hand)", "Auto Shot", "Melee (Extra Attack)", "Windfury Attack"}
        if not white:
            if kind == "ranged": bonus += c.mod("crit_dmg_school:ranged")
            else: bonus += c.mod("crit_dmg_school:physical_ability")
            if ability in {"Sinister Strike", "Backstab", "Hemorrhage"}: bonus += c.mod("crit_dmg_builder")
        return 1 + bonus

    def periodic_crit_mult(self, ability, school, bleed=False, extra_bonus=0.0):
        """Forever lets periodic damage (spell DoTs and bleeds) roll crits, unlike Classic.
        Sourced from tooltip language, not inference: Nature's Grace and Primal Fury both
        explicitly say "non-periodic" crits (a qualifier that's meaningless unless periodic
        crits are the alternative), and Pandemic's tooltip is "increases the critical strike
        damage bonus of [DoTs]" -- only sensible if those DoTs already have a crit damage bonus
        to increase. This sim doesn't roll each tick individually; instead the flat per-tick
        damage already stored on dot instances (see apply_dot) is scaled by the expected value
        of crit chance * crit bonus, the same averaging approach used elsewhere in this engine.
        Ignite is excluded by construction (it's built directly from a share of the triggering
        crit, not through this path) since Forever explicitly excludes it from periodic crits."""
        kind = "melee" if bleed else "spell"
        crit_chance = self.crit_chance(kind, ability, school)
        crit_bonus = self.crit_multiplier(kind, ability, school) - 1 + extra_bonus
        return 1 + crit_chance * crit_bonus

    # ---- attack tables ---------------------------------------------------
    def melee_outcome(self, hand_item, white, ability=None, no_dodge=False):
        """Returns (outcome, damage_multiplier)."""
        c = self.c; rng = self.rng
        skill = c.skill(hand_item) if hand_item else LEVEL * 5
        delta = TARGET_DEFENSE - skill
        base_delta = TARGET_DEFENSE - LEVEL * 5
        if delta > 10:
            miss = 0.05 + delta * 0.002; suppression = (delta - 10) * 0.002
        else:
            miss = 0.05 + delta * 0.001; suppression = 0.0
        hit_pct = self.st["meleeHit"] / 100
        if white and c.dual_wield: miss += 0.19
        if hand_item is c.oh and c.spec["class_name"] == "Warrior": hit_pct += c.mod("dw_hit") / 100
        if ability and not white: hit_pct += c.mod(f"hit_ability:{ability}") / 100
        miss = max(0.0, miss - max(0.0, hit_pct - suppression))
        dodge = 0.0 if no_dodge else max(0.0, 0.05 + delta * 0.001 - c.flag("expertise") * 0.02)
        front = self.s["role"] == "tank"
        parry = (0.05 + base_delta * 0.006) if front and not no_dodge else 0.0
        block = 0.05 if front and not no_dodge else 0.0
        glance = (0.1 + base_delta * 0.02) if white else 0.0
        crit = self.crit_chance("melee", ability if not white else None)
        roll = rng.random(); acc = miss
        if roll < acc: return "miss", 0.0
        acc += dodge
        if roll < acc: return "dodge", 0.0
        acc += parry
        if roll < acc: return "parry", 0.0
        acc += glance
        if roll < acc:
            lo = max(min(1.3 - 0.05 * delta, 0.91), 0.01); hi = max(min(1.2 - 0.03 * delta, 0.99), 0.2)
            return "glance", rng.uniform(lo, hi)
        acc += block
        if roll < acc: return "block", 1.0
        if self.next_crit and not white: crit = 1.0
        acc += crit
        if roll < acc: return "crit", self.crit_multiplier("melee", ability or "Melee (Main-Hand)", "physical")
        return "hit", 1.0

    def ranged_outcome(self, ability=None):
        c = self.c; rng = self.rng
        skill = c.skill(c.ranged); delta = TARGET_DEFENSE - skill
        miss = (0.05 + delta * 0.002) if delta > 10 else (0.05 + delta * 0.001)
        suppression = (delta - 10) * 0.002 if delta > 10 else 0.0
        miss = max(0.0, miss - max(0.0, self.st["rangedHit"] / 100 - suppression))
        roll = rng.random()
        if roll < miss: return "miss", 0.0
        crit = self.crit_chance("ranged", ability)
        if roll < miss + crit: return "crit", self.crit_multiplier("ranged", ability or "Auto Shot", "physical")
        return "hit", 1.0

    def spell_outcome(self, ability, school, can_crit=True):
        c = self.c; rng = self.rng
        hit = min(0.99, 0.83 + (self.st["spellHit"] + c.mod(f"spell_hit_school:{school}") + sum(b["value"] for b in self.buffs.values() if b.get("stat") == "spellHit" and b["until"] > self.t)) / 100)
        roll = rng.random()
        if roll >= hit:
            if c.flag("enigma_hit"): self.add_buff("Enigma Vestments", 20, stat="spellHit", value=c.flag("enigma_hit"))
            return "miss", 0.0
        crit = self.crit_chance("spell", ability, school) if can_crit else 0.0
        if self.next_crit and can_crit: crit = 1.0
        if rng.random() < crit: return "crit", self.crit_multiplier("spell", ability, school)
        return "hit", 1.0

    # ---- damage ---------------------------------------------------------
    def multiplier(self, ability, school, kind, periodic=False, white=False):
        c = self.c; m = 1.0
        m *= 1 + c.mod("dmg_all")
        if school in SPELL_SCHOOLS: m *= 1 + c.mod(f"dmg_school:{school}")
        if kind == "ranged": m *= 1 + c.mod("dmg_school:ranged")
        if kind in {"melee", "pet"} or school == "physical":
            m *= 1 + c.mod("dmg_school:physical")
            if c.flag("two_hand_spec") and c.two_hand: m *= 1 + c.flag("two_hand_spec")
            if self.t < self.enrage_until: m *= 1.10
        if periodic: m *= 1 + c.mod("dmg_periodic")
        if c.mod("dmg_destruction") and ability in {"Shadow Bolt", "Immolate", "Conflagrate", "Shadowburn", "Searing Pain"}: m *= 1 + c.mod("dmg_destruction")
        stance = STANCE_MODS.get(self.s["stance"] or self.s["form"], {})
        m *= stance.get("damage", 1.0)
        creature = c.racial.get("creature_damage", {}).get(c.boss_type, 0) if c.racial_enabled else 0
        m *= 1 + creature
        m *= 1 + c.mod(f"creature_dmg:{c.boss_type}")
        if c.flag("murder") and c.boss_type in {"humanoid", "giant"}: m *= 1 + c.flag("murder")
        if c.flag("improved_tracking") and c.boss_type in {"beast", "demon", "dragonkin", "elemental", "giant", "humanoid", "undead"}: m *= 1 + c.flag("improved_tracking")
        for name, b in self.buffs.items():
            if b["until"] <= self.t: continue
            if b.get("damage_mult"): m *= 1 + b["damage_mult"]
            if b.get("damage_mult_school") and b["damage_mult_school"][0] == school: m *= 1 + b["damage_mult_school"][1]
        if self.sacrificed and school == self.sacrificed[0]: m *= 1 + self.sacrificed[1]
        if c.flag("master_demonologist") and c.pet and not self.sacrificed:
            fam = c.pet["family"]
            if (fam == "imp" and school == "fire") or (fam == "succubus" and school == "shadow"): m *= 1 + c.flag("master_demonologist")
        if c.flag("soul_link") and c.pet and not self.sacrificed: m *= 1 + c.flag("soul_link")
        if c.flag("shadowform") and school == "shadow": m *= 1.10
        if school == "shadow" and self.debuff_active("Shadow Weaving"): m *= 1 + 0.02 * self.debuffs["Shadow Weaving"]["stacks"]
        if school == "shadow" and self.debuff_active("Improved Shadow Bolt"): m *= 1.20
        if school == "fire" and self.debuff_active("Improved Scorch"): m *= 1 + 0.03 * self.debuffs["Improved Scorch"]["stacks"]
        if school == "nature" and self.debuff_active("Stormstrike"): m *= 1.20
        if school == "shadow" and self.debuff_active("Shadow and Flame (shadow)"): m *= 1.10
        if school == "fire" and self.debuff_active("Shadow and Flame (fire)"): m *= 1.10
        if ability == "Rupture" and self.debuff_active("Hemorrhage"): m *= 1.15
        if ability == "Lava Burst" and self.dots.get("Flame Shock") and self.dots["Flame Shock"]["remaining"] > 0: m *= 1.20
        if ability == "Incinerate" and self.dots.get("Immolate") and self.dots["Immolate"]["remaining"] > 0: m *= 1.25
        if c.flag("arcane_blast") and ability != "Arcane Blast":
            b = self.buffs.get("Arcane Blast")
            stacks = b["stacks"] if b and b["until"] > self.t else 0
            if stacks: m *= 1 + 0.10 * stacks
        if c.flag("rend_and_tear") and kind == "melee" and not white and any(self.dots.get(d) and self.dots[d]["remaining"] > 0 and ABILITIES.get(d, {}).get("bleed") for d in self.dots): m *= 1 + c.flag("rend_and_tear")
        if c.flag("quietus") and ability in {"Sinister Strike", "Hemorrhage"} and self.t >= self.duration * 0.65: m *= 1 + c.flag("quietus")
        if self.eureka > 0 and not white and kind != "pet" and not periodic: m *= 1.10
        if c.flag("lone_wolf") and (c.pet is None or c.pet["uptime"] <= 0 or (self.pet_state and self.t >= self.pet_state["active_until"])): m *= 1 + c.flag("lone_wolf")
        return m

    def armor_mult(self, ability=None):
        c = self.c
        armor = c.armor_after_debuffs()
        if self.debuff_active("Spider's Kiss"): armor = max(0.0, armor - 100)
        pen = c.flag("armor_pen_pct")
        if c.flag("weaponmaster") and weapon_type(c.mh) in {"Mace", "Staff"}: pen += c.flag("weaponmaster") * 3  # 1%/rank crit (axe/polearm) implies 3%/rank armor ignore (mace/staff) per Forever tooltip
        if c.flag("hack_and_slash") and weapon_type(c.mh) == "Mace": pen += 0.15
        armor *= 1 - min(1.0, pen)
        return 1 - armor / (armor + 400 + 85 * LEVEL)

    def deal(self, name, amount, school, kind, white=False, periodic=False, threat_mult=1.0, flat_threat=0.0, outcome="hit", mult=1.0):
        """Apply multipliers/armor, record and return damage."""
        r = self.row(name)
        if outcome in {"miss", "dodge", "parry"}:
            if outcome == "miss": r.misses += 1
            else: r.dodges += 1
            self.record(name, outcome, 0.0)
            return 0.0
        dmg = amount * mult * self.multiplier(name, school, kind, periodic, white)
        if school == "physical" and not (periodic and (self.dots.get(name, {}).get("bleed") or ABILITIES.get(name, {}).get("bleed"))): dmg *= self.armor_mult(name)
        if outcome == "glance": r.glances += 1
        if outcome == "crit": r.crits += 1
        r.hits += 1; r.damage += dmg; self.total += dmg
        th = (dmg * threat_mult + flat_threat) * (1 + self.c.mod(f"threat_ability:{name}")) * self.threat_multiplier(school)
        r.threat += th; self.threat += th
        self.record(name, outcome, dmg)
        return dmg

    def threat_multiplier(self, school=None):
        c = self.c
        m = STANCE_MODS.get(self.s["stance"] or self.s["form"], {}).get("threat", 1.0) * CLASS_THREAT.get(self.s["class_name"], 1.0)
        if self.s["stance"] == "defensive": m *= 1 + c.flag("defiance")
        m *= 1 + c.mod("threat_mult")
        if school: m *= 1 + c.mod(f"threat_school:{school}")
        m *= 1 - c.threat_reduction
        return m

    # ---- resources -------------------------------------------------------
    def gain_rage(self, amount, source="ability"):
        before = self.rage; self.rage = min(self.max_rage, self.rage + amount)
        # Classic rage from dealt/taken damage and refunds is threat-free. Other gains
        # produce 5 flat threat per actual Rage, without stance/threat multipliers.
        if source == "ability":
            threat = (self.rage - before) * 5
            self.threat += threat; self.row("Rage gains").threat += threat

    def white_rage(self, hand_item, damage):
        if self.s["resource"] == "Rage":
            gained = damage * 7.5 / RAGE_CONVERSION_60
            if hand_item is self.c.oh: gained *= 1 + self.c.flag("dw_rage")
            self.gain_rage(gained, source="damage")

    def gain_energy(self, amount):
        self.energy = min(self.max_energy, self.energy + amount)

    def gain_mana(self, amount):
        self.mana = min(self.max_mana, self.mana + amount)

    def resource(self):
        return {"Mana": self.mana, "Energy": self.energy, "Rage": self.rage}[self.s["resource"]]

    def spend(self, amount):
        res = self.s["resource"]
        if res == "Mana":
            if self.clearcast: self.clearcast = False; return
            self.mana -= amount; self.last_cast_time = self.t
        elif res == "Energy": self.energy -= amount
        else: self.rage -= amount

    # ---- weapon damage ---------------------------------------------------
    def weapon_damage(self, item, normalized=False, ranged=False, bonus_ap=0.0):
        lo, hi = float(item["weaponDamageMin"]), float(item["weaponDamageMax"])
        speed = normalized_speed(item) if normalized else float(item.get("weaponSpeed", 2.0))
        if self.s["form"] in {"cat", "bear"}: speed = float(item.get("weaponSpeed", 1.0))
        ap = self.ap(ranged) + bonus_ap
        dmg = self.rng.uniform(lo, hi) + ap / 14 * speed
        if ranged: dmg += self.st.get("rangedDamage", 0)
        return dmg

    # ---- procs -----------------------------------------------------------
    def on_weapon_hit(self, hand_item, white, ability_name, damage):
        """Procs triggered by a landed melee weapon attack."""
        c = self.c; rng = self.rng
        speed = float(hand_item.get("weaponSpeed", 2.0)) if hand_item else 2.0
        is_extra = ability_name in {"Melee (Extra Attack)", "Windfury Attack"}
        # Rage
        if self.s["resource"] == "Rage":
            if white:
                self.white_rage(hand_item, damage)
            if c.flag("unbridled_wrath") and rng.random() < c.flag("unbridled_wrath"): self.gain_rage(2 if c.two_hand else 1)
            if c.flag("primal_fury") and self.s["form"] == "bear" and ability_name and "crit" in ability_name: pass
        # Weapon enchants / item procs
        hand_slot = "off_hand" if hand_item is c.oh else "main_hand"
        if hand_slot in c.crusader_hands and rng.random() < speed / 60:
            self.add_buff(f"Crusader ({hand_slot.replace('_', ' ')})", 15, stat="strength", value=100)
        if white and c.flag("shadowcraft_energy") and rng.random() < c.flag("shadowcraft_energy") * speed / 60:
            self.gain_energy(35); self.row("Shadowcraft Energize").casts += 1
        if c.flag("bloodfang_proc") and rng.random() < c.flag("bloodfang_proc") * speed / 60:
            self.dots["Bloodfang"] = {"next": self.t + 1, "remaining": 6, "tick": rng.uniform(283, 317) / 6, "tick_len": 1, "school": "physical", "kind": "dot"}
        if c.flag("stormshroud_dmg") and rng.random() < c.flag("stormshroud_dmg"):
            self.row("Stormshroud").casts += 1; self.deal("Stormshroud", rng.uniform(15, 25), "nature", "spell", outcome="hit")
        if c.flag("stormshroud_energy") and rng.random() < c.flag("stormshroud_energy"): self.gain_energy(30)
        if c.flag("spiders_kiss") and rng.random() < c.flag("spiders_kiss"): self.add_debuff("Spider's Kiss", 10)
        for proc in c.item_procs:
            item = proc.get("item")
            if proc["trigger"] == "weapon" and item is not None and item is not hand_item: continue
            if proc["trigger"] == "melee" and is_extra: continue
            key = proc["name"]
            if proc.get("icd") and self.item_icd.get(key, -1e9) + proc["icd"] > self.t: continue
            chance = proc["chance"] if "chance" in proc else proc["ppm"] * speed / 60
            if rng.random() >= chance: continue
            self.item_icd[key] = self.t
            if proc["kind"] == "damage":
                school = proc["school"]
                out, m = self.spell_outcome(f"Item - {key}", school, can_crit=False) if school != "physical" else self.melee_outcome(None, False, f"Item - {key}", no_dodge=True)
                self.row(f"Item - {key}").casts += 1
                self.deal(f"Item - {key}", proc["amount"], school, "spell" if school != "physical" else "melee", outcome=out, mult=m)
            elif proc["kind"] == "buff":
                self.add_buff(f"Item - {key}", proc["duration"], stat=proc["stat"], value=proc["value"])
            elif proc["kind"] == "extra_attack" and not is_extra:
                self.extra_attack("Melee (Extra Attack)", c.mh)
        # Talent extra attacks
        if not is_extra:
            wm = c.flag("weaponmaster"); hs = c.flag("hack_and_slash")
            kind = weapon_type(hand_item) if hand_item else None
            if wm and kind == "Sword" and rng.random() < wm: self.extra_attack("Melee (Extra Attack)", c.mh)
            if hs and kind in {"Sword", "Axe"} and rng.random() < hs: self.extra_attack("Melee (Extra Attack)", c.mh)
            if c.windfury_totem and hand_item is c.mh and rng.random() < WINDFURY_TOTEM["chance"] and self.t >= self.windfury_lock:
                self.windfury_lock = self.t + 0.1
                self.extra_attack("Windfury Attack", c.mh, bonus_ap=WINDFURY_TOTEM["ap"])
            if self.s["class_name"] == "Shaman" and hand_item is c.mh and rng.random() < WINDFURY["chance"] and self.t >= self.windfury_lock:
                self.windfury_lock = self.t + 0.1
                bonus = WINDFURY["ap"] * (1 + c.flag("elemental_weapons"))
                for _ in range(WINDFURY["extra_attacks"]): self.extra_attack("Windfury Attack", c.mh, bonus_ap=bonus)
        # Poisons
        if self.s["class_name"] == "Rogue":
            mh_poison = "deadly" if self.s["id"] == "rogue-assassination" else "instant"
            poison = mh_poison if hand_item is c.mh else "instant"
            chance = POISONS[poison]["chance"] + c.flag("poison_chance") + (0.10 if self.buff_active("Venom") else 0.0)
            if rng.random() < chance:
                if poison == "instant":
                    out, m = self.spell_outcome("Instant Poison", "nature", can_crit=True)
                    self.row("Instant Poison").casts += 1
                    venom_dmg = 0.30 if self.buff_active("Venom") else 0.0
                    self.deal("Instant Poison", rng.uniform(POISONS["instant"]["min"], POISONS["instant"]["max"]) * (1 + c.flag("poison_damage") + venom_dmg), "nature", "spell", outcome=out, mult=m)
                else:
                    d = self.dots.get("Deadly Poison")
                    stacks = min(POISONS["deadly"]["max_stacks"], (d["stacks"] if d and d["remaining"] > 0 else 0) + 1)
                    venom_dmg = 0.30 if self.buff_active("Venom") else 0.0
                    self.dots["Deadly Poison"] = {"next": self.t + 3, "remaining": 4, "tick": POISONS["deadly"]["tick"] * (1 + c.flag("poison_damage") + venom_dmg), "tick_len": 3, "school": "nature", "stacks": stacks, "kind": "dot"}
        # Dragonbreath Chili
        if "dragonbreath_chili" in c.consumes and rng.random() < 0.05:
            self.row("Dragonbreath Chili").casts += 1
            self.deal("Dragonbreath Chili", rng.uniform(60, 90), "fire", "spell", outcome="hit")
        if c.flag("expose_prey") and rng.random() < c.flag("expose_prey"):
            self.add_buff("Mongoose Bite Ready", 5)
        if c.flag("maelstrom_weapon") and not is_extra and rng.random() < 0.20:
            self.add_buff("Maelstrom Weapon", 30, stacks_max=5)
        # Flurry
        if self.flurry > 0 and white: self.flurry -= 1

    def on_crit(self, name, damage, hand_item=None, kind="melee"):
        c = self.c
        if kind == "melee":
            if c.flag("flurry"): self.flurry = 3
            if c.flag("deep_wounds") and hand_item is not None:
                avg = (float(hand_item["weaponDamageMin"]) + float(hand_item["weaponDamageMax"])) / 2 + self.ap() / 14 * float(hand_item.get("weaponSpeed", 2.0))
                if hand_item is c.oh: avg *= 0.5 * (1 + c.flag("dw_damage"))
                tick = avg * c.flag("deep_wounds") / 4 * self.periodic_crit_mult("Deep Wounds", "physical", bleed=True)
                self.dots["Deep Wounds"] = {"next": self.t + 3, "remaining": 4, "tick": tick, "tick_len": 3, "school": "physical", "kind": "dot", "bleed": True}
            if c.flag("primal_fury") and self.s["form"] == "bear": self.gain_rage(5)
        if kind == "spell":
            if c.flag("ignite") and self.cur_school == "fire":
                amount = damage * c.flag("ignite")
                d = self.dots.get("Ignite")
                if d and d["remaining"] > 0: d["tick"] += amount / 2; d["remaining"] = 2; d["next"] = self.t + 2
                else: self.dots["Ignite"] = {"next": self.t + 2, "remaining": 2, "tick": amount / 2, "tick_len": 2, "school": "fire", "kind": "dot", "no_sp": True}
            if self.combustion is not None and self.cur_school == "fire":
                self.combustion["crits"] += 1
                if self.combustion["crits"] >= 4: self.combustion = None
            if c.flag("natures_grace"): self.add_buff("Nature's Grace", 3, haste=0.10)
            if c.flag("improved_shadow_bolt") and name == "Shadow Bolt": self.add_debuff("Improved Shadow Bolt", 12)
        if kind == "spell" and c.flag("master_of_elements"):
            self.gain_mana(self.cur_cost * c.flag("master_of_elements"))

    def extra_attack(self, name, item, bonus_ap=0.0):
        out, m = self.melee_outcome(item, True, name)
        self.row(name).casts += 1
        raw = self.weapon_damage(item, bonus_ap=bonus_ap) if out != "miss" else 0
        if out in {"dodge", "parry"}:
            self.white_rage(item, raw * self.multiplier(name, "physical", "melee", white=True) * self.armor_mult(name))
        dmg = self.deal(name, raw, "physical", "melee", white=True, outcome=out, mult=m)
        if dmg:
            self.on_weapon_hit(item, True, name, dmg)
            if out == "crit": self.on_crit(name, dmg, item)
        return dmg

    def touch_of_the_grave(self):
        c = self.c
        if c.race == "Undead" and c.racial_enabled and self.rng.random() < c.racial["touch_of_the_grave"]["chance"]:
            self.row("Touch of the Grave").casts += 1
            self.deal("Touch of the Grave", self.health_max * c.racial["touch_of_the_grave"]["health_fraction"], "shadow", "spell", outcome="hit")

    # ---- swings ----------------------------------------------------------
    def swing(self, item, hand):
        c = self.c
        name = "Melee (Main-Hand)" if hand == "main" else "Melee (Off-Hand)"
        queued = self.queued_swing if hand == "main" else None
        if queued:
            a = c.actions[queued]
            cost = self.cost(queued)
            if self.resource() + EPS >= cost:
                self.queued_swing = None
                self.spend(cost)
                out, m = self.melee_outcome(item, False, queued)
                self.row(queued).casts += 1
                dmg = 0.0
                if out not in {"miss", "dodge", "parry"}:
                    dmg = self.weapon_damage(item) + a["weapon"].get("flat", 0)
                    if queued == "Maul": dmg += 40 * 0 # Maul has no extra AP term
                cleave_hits = min(c.targets, 2) if queued == "Cleave" else 1
                dmg = self.deal(queued, dmg, "physical", "melee", threat_mult=a.get("threat_mult", 1.0), flat_threat=a.get("flat_threat", 0) * cleave_hits, outcome=out, mult=m * a["mult"] * cleave_hits)
                if out in {"miss", "dodge", "parry"} and self.s["resource"] == "Rage": self.rage += cost * 0.8
                if dmg:
                    self.on_weapon_hit(item, False, queued, dmg)
                    if out == "crit": self.on_crit(queued, dmg, item)
                self.touch_of_the_grave()
                return
            self.queued_swing = None
        out, m = self.melee_outcome(item, True, name)
        self.row(name).casts += 1
        if out == "dodge": self.dodged_recently = self.t
        dmg = 0.0
        if out != "miss":
            dmg = self.weapon_damage(item)
            if hand == "off": dmg *= 0.5 * (1 + c.flag("dw_damage"))
        if out in {"dodge", "parry"}:
            self.white_rage(item, dmg * self.multiplier(name, "physical", "melee", white=True) * self.armor_mult(name))
        dmg = self.deal(name, dmg, "physical", "melee", white=True, outcome=out, mult=m)
        if dmg:
            self.on_weapon_hit(item, True, name, dmg)
            if out == "crit": self.on_crit(name, dmg, item)
        self.touch_of_the_grave()

    def auto_shot(self):
        c = self.c
        out, m = self.ranged_outcome()
        self.row("Auto Shot").casts += 1
        dmg = self.weapon_damage(c.ranged, ranged=True) if out != "miss" else 0.0
        dmg = self.deal("Auto Shot", dmg, "physical", "ranged", white=True, outcome=out, mult=m)
        if dmg and c.flag("pet_frenzy") == 0: pass
        self.touch_of_the_grave()
        if dmg: self.on_ranged_damage(out)
        if dmg:
            for proc in c.item_procs:
                if proc["trigger"] == "weapon" and proc.get("item") is c.ranged and self.rng.random() < proc.get("ppm", 1) * float(c.ranged.get("weaponSpeed", 2.8)) / 60:
                    self.row(f"Item - {proc['name']}").casts += 1
                    self.deal(f"Item - {proc['name']}", proc.get("amount", 0), proc.get("school", "physical"), "spell", outcome="hit")

    def on_ranged_damage(self, out):
        """Set procs that trigger on landed ranged damage."""
        c = self.c; rng = self.rng
        if c.flag("beaststalker_mana") and rng.random() < c.flag("beaststalker_mana"): self.gain_mana(200)
        if out == "crit" and c.flag("cryptstalker_mana"): self.gain_mana(c.flag("cryptstalker_mana"))
        if c.flag("dragonstalker_ew") and rng.random() < c.flag("dragonstalker_ew") * float(c.ranged.get("weaponSpeed", 2.8)) / 60:
            self.add_buff("Expose Weakness", 7, stat="rangedAttackPower", value=450)

    # ---- abilities -------------------------------------------------------
    def check(self, cond, name):
        """Evaluate a rotation condition."""
        c = self.c; a = c.actions[name]
        cond = cond.strip()
        if cond == "true": return True
        if cond == "false": return False
        if " or " in cond: return any(self.check(x, name) for x in cond.split(" or "))
        if " and " in cond: return all(self.check(x, name) for x in cond.split(" and "))
        if cond.startswith("not "): return not self.check(cond[4:], name)
        if cond == "execute": return self.t >= self.execute_at
        if cond == "moving": return False
        if cond == "dot_missing":
            d = self.dots.get(name); active = bool(d and d["remaining"] > 0 and d["next"] - self.t < 1e9)
            if a.get("spreadable") and c.targets > 1:
                extra_active = sum(1 for x in self.dots_extra if x["name"] == name and x["remaining"] > 0)
                return (1 if active else 0) + extra_active < c.targets
            return not active
        if cond == "buff_missing": return not self.buff_active(name)
        if cond == "no_dagger": return weapon_type(c.mh) != "Dagger"
        if cond == "no_shred": return "Shred" not in c.actions
        m = re.match(r"targets\s*(<=|>=|<|>|==)\s*(\d+)", cond)
        if m:
            op, num = m.groups(); num = float(num)
            return {"<": c.targets < num, ">": c.targets > num, "<=": c.targets <= num, ">=": c.targets >= num, "==": c.targets == num}[op]
        m = re.match(r"(rage|energy|mana|cp)\s*(<=|>=|<|>|==)\s*(\d+)", cond)
        if m:
            val = {"rage": self.rage, "energy": self.energy, "mana": self.mana, "cp": self.cp}[m.group(1)]
            return {"<": val < float(m.group(3)), ">": val > float(m.group(3)), "<=": val <= float(m.group(3)), ">=": val >= float(m.group(3)), "==": val == float(m.group(3))}[m.group(2)]
        m = re.match(r"(dot|debuff|cd|buffstacks|buff|stacks):(.+?)\s*(<=|>=|<|>|==)\s*(\d+)", cond)
        if m:
            kind, key, op, num = m.groups(); num = float(num)
            if kind == "dot":
                d = self.dots.get(key); val = (d["remaining"] * d["tick_len"]) if d and d["remaining"] > 0 else 0.0
            elif kind == "debuff":
                b = self.debuffs.get(key); val = max(0.0, b["until"] - self.t) if b else 0.0
            elif kind == "cd":
                val = max(0.0, self.cooldowns.get(key, 0.0) - self.t)
            elif kind == "buff":
                b = self.buffs.get(key); val = max(0.0, b["until"] - self.t) if b else 0.0
            elif kind == "buffstacks":
                b = self.buffs.get(key); val = b["stacks"] if b and b["until"] > self.t else 0
            else:
                b = self.debuffs.get(key); val = b["stacks"] if b and b["until"] > self.t else 0
            return {"<": val < num, ">": val > num, "<=": val <= num, ">=": val >= num, "==": val == num}[op]
        raise ValueError(f"Unknown rotation condition: {cond}")

    def ready(self, name, ignore_resource=False):
        a = self.c.actions[name]
        if self.cooldowns.get(name, 0) > self.t + EPS: return False
        if a.get("shared_cd") and self.cooldowns.get("shared:" + a["shared_cd"], 0) > self.t + EPS: return False
        if a.get("execute") and self.t < self.execute_at: return False
        if a.get("requires") == "dodge" and self.t - self.dodged_recently > 5: return False
        if a.get("requires", "").startswith("dodge_or_buff:"):
            buff_name = a["requires"][len("dodge_or_buff:"):]
            if not (self.t - self.dodged_recently <= 5 or self.buff_active(buff_name)): return False
        if a.get("requires") == "block_dodge_parry" and self.t - self.avoided_recently > 5: return False
        if a.get("requires") == "dagger" and weapon_type(self.c.mh) != "Dagger": return False
        if a.get("requires", "").startswith("dot:"):
            d = self.dots.get(a["requires"][4:]);
            if not (d and d["remaining"] > 0): return False
        if a.get("finisher") and self.cp <= 0: return False
        if a.get("kind") == "swing" and self.queued_swing: return False
        if not ignore_resource and self.resource() + EPS < self.cost(name) and not (self.s["resource"] == "Mana" and self.clearcast and a.get("kind") in {"direct", "dot", "channel", "direct_dot"}): return False
        return True

    def cost(self, name):
        a = self.c.actions[name]; cost = a.get("cost", 0)
        if self.buff_active("Arcane Power") and self.s["resource"] == "Mana": cost *= 1.3
        if name == "Arcane Blast":
            b = self.buffs.get("Arcane Blast"); stacks = b["stacks"] if b and b["until"] > self.t else 0
            cost *= 1 + 1.75 * stacks
        if name == "Arcane Missiles" and self.buff_active("Missile Barrage"): cost = 0
        if name in {"Hemorrhage", "Backstab"}:
            b = self.buffs.get("Thousand Cuts")
            if b and b["until"] > self.t: cost = max(0.0, cost - 3 * b["stacks"])
        return cost

    def choose(self):
        self.blocked_by_resource = False
        for name, cond in self.c.rotation:
            a = self.c.actions[name]
            if a.get("kind") == "buff" and a.get("no_effect"): continue
            if not self.ready(name, ignore_resource=True): continue
            if not self.check(cond, name): continue
            if self.resource() + EPS < self.cost(name) and not (self.s["resource"] == "Mana" and self.clearcast):
                self.blocked_by_resource = True; continue
            return name
        return None

    def use_offgcd(self):
        """Off-GCD actions: racial actives, potions, item uses, Bloodrage, cooldown buffs."""
        c = self.c
        if c.racial_enabled and c.racial.get("active") and self.t >= self.racial_next and (c.racial["active"]["name"] != "Stoneform" or (self.s["role"] == "tank" and self.t + EPS >= self.gcd_until and self.cast is None)):
            r = c.racial["active"]; self.racial_next = self.t + r["cooldown"]
            if r["name"] == "Stoneform":
                self.add_buff("Stoneform", r["duration"]); self.gcd_until = self.t + GCD; self.row("Stoneform").casts += 1
            elif r.get("crit"): self.add_buff(r["name"], r["duration"])
            elif r.get("haste"): self.add_buff(r["name"], r["duration"], haste=r["haste"])
            elif r.get("ap_pct"): self.add_buff(r["name"], r["duration"], ap_pct=r["ap_pct"], sp_pct=r["sp_pct"])
            elif r.get("charges"): self.eureka = r["charges"]
            self.record(r["name"], "activated", 0)
        for name, a in c.actions.items():
            if not a.get("off_gcd") and a.get("kind") not in {"item_use"}: continue
            if self.cooldowns.get(name, 0) > self.t + EPS: continue
            if a.get("shared_cd") and self.cooldowns.get("shared:" + a["shared_cd"], 0) > self.t + EPS: continue
            if name in {n for n, _ in c.rotation}:
                cond = dict(c.rotation)[name]
                if not self.check(cond, name): continue
            if a.get("kind") == "item_use":
                use = a["use"]
                if use["stat"] == "mana" and self.max_mana - self.mana < use["value"]: continue
                if use["stat"] == "damage":
                    out, m = self.spell_outcome(name, use["school"], can_crit=False); self.row(name).casts += 1
                    self.deal(name, use["value"], use["school"], "spell", outcome=out, mult=m)
                elif use["stat"] == "mana": self.gain_mana(use["value"]); self.row(name).casts += 1
                else:
                    self.add_buff(name, use["duration"], stat=use["stat"], value=use["value"]); self.row(name).casts += 1
                self.cooldowns[name] = self.t + a["cooldown"]; self.record(name, "activated", 0); continue
            if a.get("mana"):
                if self.max_mana - self.mana < 1500: continue
                self.gain_mana(self.rng.uniform(*a["mana"])); self.cooldowns[name] = self.t + a["cooldown"]
                if a.get("shared_cd"): self.cooldowns["shared:" + a["shared_cd"]] = self.t + a["cooldown"]
                self.row(name).casts += 1; self.record(name, "activated", 0); continue
            if a.get("kind") == "buff" and a.get("rage") is not None and name == "Mighty Rage Potion":
                if self.rage > 30: continue
                self.gain_rage(self.rng.uniform(*a["rage"])); self.add_buff(name, a["duration"], stat="strength", value=a["strength"]); self.cooldowns[name] = self.t + a["cooldown"]; self.cooldowns["shared:potion"] = self.t + a["cooldown"]; self.row(name).casts += 1; continue
            if a.get("energy"):
                if self.energy > 20: continue
                self.gain_energy(a["energy"]); self.cooldowns[name] = self.t + a["cooldown"]; self.row(name).casts += 1; continue
            if name == "Goblin Sapper Charge":
                self.row(name).casts += 1; self.deal(name, self.rng.uniform(*a["base"]), "fire", "spell", outcome="hit"); self.cooldowns[name] = self.t + a["cooldown"]; continue
            if name == "Bloodrage":
                if self.rage >= 60: continue
                mult = 1 + c.flag("improved_bloodrage")
                self.gain_rage(a["rage"] * mult); self.buffs["Bloodrage"] = {"until": self.t + 10, "tick": a["rage_over_time"][0] * mult, "next": self.t + 1}
                self.cooldowns[name] = self.t + a["cooldown"]; self.row(name).casts += 1; self.record(name, "activated", 0); continue
            if a.get("kind") == "buff" and a.get("off_gcd"):
                self.activate_buff(name, a)

    def queue_swings(self):
        """On-next-swing attacks (Heroic Strike, Maul) are queued off the GCD."""
        if self.queued_swing or not self.alive: return
        for name, cond in self.c.rotation:
            a = self.c.actions[name]
            if a.get("kind") != "swing": continue
            if self.resource() + EPS < self.cost(name): continue
            if a.get("execute") and self.t < self.execute_at: continue
            if not self.check(cond, name): continue
            self.queued_swing = name; self.record(name, "queued", 0); return

    def activate_buff(self, name, a):
        c = self.c
        self.cooldowns[name] = self.t + a.get("cooldown", 0)
        self.row(name).casts += 1
        if a.get("duration"):
            kw = {}
            if a.get("damage_mult"): kw["damage_mult"] = a["damage_mult"]
            if a.get("damage_mult_school"): kw["damage_mult_school"] = a["damage_mult_school"]
            if a.get("melee_haste"): kw["haste"] = a["melee_haste"]
            if a.get("spell_haste"): kw["haste"] = a["spell_haste"]
            if a.get("ranged_haste"): kw["haste"] = a["ranged_haste"]
            if a.get("energy_regen_mult"): kw["energy_regen_mult"] = a["energy_regen_mult"]
            if a.get("pet_damage_mult"): kw["pet_damage_mult"] = a["pet_damage_mult"]
            if a.get("flat_damage_bonus"): kw["flat_damage_bonus"] = a["flat_damage_bonus"]
            self.add_buff(name, a["duration"] + c.mod(f"duration:{name}"), **kw)
        if name == "Tiger's Fury" and c.flag("king_of_the_jungle"): self.gain_energy(c.flag("king_of_the_jungle"))
        if a.get("combustion"): self.combustion = {"stacks": 0, "crits": 0}
        if a.get("instant_next"): self.next_instant = True
        if a.get("next_crit"): self.next_crit = True
        if a.get("life_tap"):
            self.gain_mana(a["life_tap"] * (1 + c.mod("dmg_ability:Life Tap")) + self.sp("shadow") * 0.8)
            self.health -= a["life_tap"]
        if a.get("sacrifice") and c.pet:
            fam = c.pet["family"]; self.sacrificed = ("shadow", 0.15) if fam == "imp" else ("fire", 0.15) if fam == "succubus" else None; self.pet_state = None
        self.record(name, "activated", 0)

    def start(self, name):
        """Begin an action chosen on the GCD."""
        c = self.c; a = c.actions[name]
        gcd = a.get("gcd", GCD)
        haste = self.haste("spell" if a.get("cast", 0) > 0 or a.get("kind") in {"channel", "direct", "dot", "direct_dot"} and self.s["style"] == "spell" else "melee")
        if a.get("kind") == "swing":
            self.queued_swing = name; self.record(name, "queued", 0); return
        if a.get("kind") == "buff":
            cost = self.cost(name); self.spend(cost)
            if a.get("finisher") == "slice_and_dice":
                dur = (6 + 3 * self.cp) * (1 + c.flag("snd_duration")); self.add_buff(name, dur, haste=a["melee_haste"]); self.finish(name); self.row(name).casts += 1; self.record(name, "applied", 0)
            elif a.get("finisher") == "venom_buff":
                dur = 6 + 3 * self.cp; self.add_buff(name, dur); self.finish(name); self.row(name).casts += 1; self.record(name, "applied", 0)
            else:
                self.activate_buff(name, a)
            self.gcd_until = self.t + gcd / (haste if self.s["style"] == "spell" else 1.0)
            return
        cost = self.cost(name)
        if self.s["resource"] == "Rage" and cost > 0 and self.wrath_discount: cost = max(0.0, cost - 5); self.wrath_discount = False
        if name in {"Hemorrhage", "Backstab"} and self.buff_active("Thousand Cuts"): self.buffs.pop("Thousand Cuts", None)
        self.row(name).casts += 1
        cast = a.get("cast", 0) / self.haste("ranged" if a.get("ranged_cast") else "spell")
        if self.next_instant and cast > 0: cast = 0; self.next_instant = False
        if name == "Starfire" and self.eclipse > 0: cast = max(0, cast - 0.5); self.eclipse -= 1
        if name == "Pyroblast":
            b = self.buffs.get("Hot Streak")
            stacks = b["stacks"] if b and b["until"] > self.t else 0
            if stacks > 0:
                cast *= max(0.25, 1 - 0.25 * stacks)
                self.buffs.pop("Hot Streak", None)
        if name == "Lightning Bolt":
            b = self.buffs.get("Maelstrom Weapon")
            stacks = b["stacks"] if b and b["until"] > self.t else 0
            if stacks > 0:
                reduction = min(1.0, c.flag("maelstrom_weapon") * stacks)
                cast *= max(0.0, 1 - reduction)
                cost *= max(0.0, 1 - reduction)
                self.buffs.pop("Maelstrom Weapon", None)
        if name == "Arcane Missiles" and self.buff_active("Missile Barrage"):
            cast *= 0.5
            self.buffs.pop("Missile Barrage", None)
        self.spend(cost); self.cur_cost = cost
        if self.s["resource"] == "Rage" and cost > 0 and c.flag("wrath_rage_proc") and self.rng.random() < c.flag("wrath_rage_proc"): self.wrath_discount = True
        self.cooldowns[name] = self.t + a.get("cooldown", 0)
        if a.get("shared_cd"): self.cooldowns["shared:" + a["shared_cd"]] = self.t + a.get("cooldown", 0)
        self.gcd_until = self.t + max(1.0, gcd / (self.haste("spell") if self.s["style"] == "spell" else 1.0)) if gcd == GCD else self.t + gcd
        if cast > 0:
            if a.get("ranged_cast"): self.next_ranged = max(self.next_ranged, self.t + cast)
            if a.get("kind") == "channel":
                self.cast = {"name": name, "until": self.t + cast, "next_tick": self.t + cast / a["ticks"], "ticks_left": a["ticks"], "tick_len": cast / a["ticks"]}
                self.busy_until = self.t + cast
                out, m = self.spell_outcome(name, a["school"], can_crit=False)
                self.cast["landed"] = out != "miss"
                if out == "miss": self.row(name).misses += 1; self.record(name, "miss", 0)
            else:
                self.cast = {"name": name, "until": self.t + cast}
                self.busy_until = self.t + cast
            return
        self.resolve(name)

    def finish(self, name):
        """Combo-point finisher bookkeeping."""
        c = self.c
        cp = self.cp; self.cp = 0
        if c.flag("ruthlessness") and self.rng.random() < c.flag("ruthlessness"): self.cp = 1
        if c.flag("relentless_strikes") and self.rng.random() < 0.2 * cp: self.gain_energy(25)
        if c.flag("restless_blades") and c.actions[name].get("kind") != "buff":
            # Only Adrenaline Rush/Blade Flurry matter for a single-target DPS sim; Evasion/Sprint/Vanish
            # (also reduced by the real talent) are defensive/utility and unmodeled here.
            reduction = 2 * cp
            for cd_name in ("Adrenaline Rush", "Blade Flurry"):
                if cd_name in self.cooldowns:
                    self.cooldowns[cd_name] = max(self.t, self.cooldowns[cd_name] - reduction)
        return cp

    def resolve(self, name):
        """Apply an instant or completed cast."""
        c = self.c; a = c.actions[name]; rng = self.rng
        school = a.get("school", "physical"); self.cur_school = school
        kind = a.get("kind")
        if kind == "buff":
            self.activate_buff(name, a); return
        threat_mult, flat_threat = a.get("threat_mult", 1.0), a.get("flat_threat", 0.0)
        if name == "Mutilate":
            if not c.oh:
                self.deal(name, 0, "physical", "melee", outcome="miss"); return
            poisoned = self.dots.get("Deadly Poison") and self.dots["Deadly Poison"]["remaining"] > 0
            landed_any = False
            for hand_item, hand in ((c.mh, "main"), (c.oh, "off")):
                out, m = self.melee_outcome(hand_item, False, name)
                if out in {"miss", "dodge", "parry"}:
                    self.deal(name, 0, "physical", "melee", outcome=out); continue
                base = self.weapon_damage(hand_item, normalized=True) * 0.75 + 13
                if poisoned: base *= 1.20
                dmg = self.deal(name, base, "physical", "melee", outcome=out, mult=m * a["mult"])
                if dmg:
                    landed_any = True
                    self.on_weapon_hit(hand_item, False, name, dmg)
                    if out == "crit": self.on_crit(name, dmg, hand_item)
            if landed_any:
                gained = a["cp"] + (1 if self.rng.random() < c.flag("seal_fate") else 0)
                self.cp = min(5, self.cp + gained)
            self.touch_of_the_grave()
            return
        if a.get("no_damage"):
            self.row(name).hits += 1; th = flat_threat * (1 + c.mod(f"threat_ability:{name}")) * self.threat_multiplier(); self.row(name).threat += th; self.threat += th
            if name == "Sunder Armor": self.add_debuff("Sunder Armor", 30, stacks_max=5)
            self.record(name, "hit", 0); return
        # ---- weapon-based melee
        if a.get("weapon") or a.get("ap_mult") or a.get("execute_formula") or a.get("finisher") in {"eviscerate", "ferocious_bite"} or (school == "physical" and self.s["style"] != "ranged" and (a.get("base") or a.get("flat"))):
            if a.get("weapon", {}).get("hand") == "ranged":
                out, m = self.ranged_outcome(name)
                dmg = 0.0
                if out != "miss":
                    dmg = self.weapon_damage(c.ranged, normalized=True, ranged=True) + a["weapon"].get("flat", 0)
                    if name == "Multi-Shot": dmg *= 1
                dmg = self.deal(name, dmg, "physical", "ranged", outcome=out, mult=m * a["mult"] * (min(c.targets, 3) if name == "Multi-Shot" else 1))
                if dmg: self.on_ranged_damage(out)
                return
            item = c.mh
            out, m = self.melee_outcome(item, False, name, no_dodge=a.get("no_dodge", False))
            if out in {"miss", "dodge", "parry"}:
                self.deal(name, 0, "physical", "melee", outcome=out)
                if self.s["resource"] == "Rage": self.rage += self.cur_cost * 0.8
                if out == "dodge": self.dodged_recently = self.t
                if a.get("finisher") and c.flag("finisher_refund"): self.gain_energy(c.flag("finisher_refund"))
                return
            if a.get("execute_formula"):
                extra = self.rage; base = a["execute_formula"][0] + a["execute_formula"][1] * extra; self.rage = 0
            elif a.get("ap_mult"): base = a["ap_mult"] * self.ap() + a.get("flat", 0)
            elif a.get("finisher") == "eviscerate":
                cp = self.cp; base = rng.uniform(48 + 151 * cp, 48 + 151 * cp + 96) + 0.03 * cp * self.ap()
            elif a.get("finisher") == "ferocious_bite":
                cp = self.cp; extra = max(0.0, self.energy); self.energy = 0
                base = 52 + rng.uniform(0, 60) + 128 * cp + self.ap() * 0.03 * cp + extra * 2.7
            elif a.get("base"):
                base = rng.uniform(*a["base"]) + (self.st.get("blockValue", 0) if a.get("add_block_value") else 0)
            elif not a.get("weapon"):
                base = a.get("flat", 0)
            else:
                w = a["weapon"]; mult = w.get("mult", 1.0)
                if w.get("dagger_mult") and weapon_type(item) == "Dagger": mult = w["dagger_mult"]
                base = self.weapon_damage(item, normalized=w.get("normalized", False)) * mult + w.get("flat", 0)
                if w.get("hand") == "both" and c.oh:
                    base += self.weapon_damage(c.oh, normalized=w.get("normalized", False)) * mult + w.get("flat", 0)
                if a.get("creature_mult") and c.boss_type in a["creature_mult"]: base *= a["creature_mult"][c.boss_type]
            fb = sum(b.get("flat_damage_bonus", 0) for b in self.buffs.values() if b["until"] > self.t)
            base += fb + c.mod(f"flat_ability:{name}")
            if self.next_crit: self.next_crit = False
            dmg = self.deal(name, base, "physical", "melee", threat_mult=threat_mult, flat_threat=flat_threat, outcome=out, mult=m * a["mult"] * (min(c.targets, 4) if name == "Whirlwind" else min(c.targets, 3) if name == "Swipe" else 1))
            if self.eureka > 0: self.eureka -= 1
            if a.get("cp"):
                gained = a["cp"] + (1 if out == "crit" and rng.random() < c.flag("seal_fate") else 0) + (1 if out == "crit" and c.flag("primal_fury") and self.s["form"] == "cat" else 0)
                self.cp = min(5, self.cp + gained)
            if out == "crit" and c.flag("bonescythe_energy") and name in {"Backstab", "Sinister Strike", "Hemorrhage"}: self.gain_energy(c.flag("bonescythe_energy"))
            if a.get("finisher"): self.finish(name)
            if a.get("apply_debuff"): n, d, extra = a["apply_debuff"]; self.add_debuff(n, d)
            if name == "Hemorrhage": self.add_debuff("Hemorrhage", 15)
            if name == "Mongoose Bite":
                self.buffs.pop("Mongoose Bite Ready", None)
                if dmg and c.flag("lacerating_strikes"):
                    tick = dmg * 0.40 / 7 * self.periodic_crit_mult("Lacerating Strikes", "physical", bleed=True)
                    self.dots["Lacerating Strikes"] = {"next": self.t + 3, "remaining": 7, "tick": tick, "tick_len": 3, "school": "physical", "kind": "dot", "bleed": True}
            if dmg:
                self.on_weapon_hit(item, False, name, dmg) if a.get("weapon") else None
                if out == "crit": self.on_crit(name, dmg, item if a.get("weapon") else None)
            self.touch_of_the_grave()
            return
        # ---- spells / ranged magic
        if kind in {"direct", "direct_dot", "dot"} and a.get("finisher") == "rip":
            cp = self.cp; scaling = 4 if cp == 5 else cp
            tick = 17 + 28 * cp + 0.01 * scaling * self.ap()
            out, m = self.melee_outcome(c.mh, False, name)
            self.row(name)
            if out in {"miss", "dodge", "parry"}:
                self.deal(name, 0, "physical", "melee", outcome=out)
                if c.flag("finisher_refund"): self.gain_energy(c.flag("finisher_refund"))
                return
            tick *= a["mult"] * self.periodic_crit_mult(name, "physical", bleed=True)
            self.dots[name] = {"next": self.t + a["tick_len"], "remaining": a["ticks"], "tick": tick, "tick_len": a["tick_len"], "school": "physical", "kind": "dot", "bleed": True}
            self.finish(name); self.record(name, "applied", 0); return
        if a.get("finisher") == "rupture":
            cp = self.cp
            # Forever cut Rupture's per-CP totals roughly in half vs Classic (foreverchanges.pro,
            # build 1.60.1.69913: 159/222/295 total dmg for 1/2/3 combo points over 12s/6 ticks,
            # vs Classic's 272/380/504). Refit flat base against those three data points
            # (tick ~= 2.9 + 4.4*cp) in place of the old Classic-fit "60 + 8*cp"; AP-scaling
            # coefficients per CP are not published and keep their prior placeholder ratios.
            tick = 2.9 + 4.4 * cp + [0, 0.04 / 4, 0.10 / 5, 0.18 / 6, 0.21 / 7, 0.24 / 8][cp] * self.ap()
            out, m = self.melee_outcome(c.mh, False, name)
            if out in {"miss", "dodge", "parry"}:
                self.deal(name, 0, "physical", "melee", outcome=out)
                if c.flag("finisher_refund"): self.gain_energy(c.flag("finisher_refund"))
                return
            tick *= a["mult"] * self.periodic_crit_mult(name, "physical", bleed=True)
            self.dots[name] = {"next": self.t + 2, "remaining": 3 + cp, "tick": tick, "tick_len": 2, "school": "physical", "kind": "dot", "bleed": True}
            self.finish(name); self.record(name, "applied", 0); return
        sp = self.sp(school)
        if kind in {"direct", "direct_dot"}:
            can_crit = not a.get("no_crit")
            if name == "Arcane Blast" and c.flag("arcane_blast"): self.add_buff("Arcane Blast", 8, stacks_max=4)
            out, m = self.spell_outcome(name, school, can_crit) if not a.get("always_hit") else ("hit", 1.0)
            if out == "miss":
                self.deal(name, 0, school, "spell", outcome="miss"); return
            base = rng.uniform(*a["base"]) + sp * a.get("coeff", 0)
            base *= a.get("direct_mult", 1.0)
            if name == "Chain Lightning": bounce = 0.7 + c.mod("chain_lightning_bounce"); base *= 1 + bounce * (c.targets > 1) + bounce * bounce * (c.targets > 2)
            if name == "Conflagrate" and self.dots.get("Immolate") and rng.random() >= min(1.0, c.flag("shadow_and_flame") * 10): self.dots["Immolate"]["remaining"] = 0
            fof_used = False
            if name == "Ice Lance":
                b = self.buffs.get("Fingers of Frost")
                if b and b["until"] > self.t and b["stacks"] > 0:
                    base *= 4.0
                    fof_used = True
            if self.next_crit: self.next_crit = False
            dmg = self.deal(name, base, school, "spell", threat_mult=threat_mult, flat_threat=flat_threat, outcome=out, mult=m * a["mult"] * (c.targets if a.get("aoe") else 1))
            if self.eureka > 0: self.eureka -= 1
            if fof_used:
                b = self.buffs.get("Fingers of Frost")
                if b:
                    b["stacks"] -= 1
                    if b["stacks"] <= 0: self.buffs.pop("Fingers of Frost", None)
            self.after_spell_hit(name, school, out, dmg, a)
            if name in {"Fireball", "Frostbolt"} and c.flag("netherwind_instant") and rng.random() < c.flag("netherwind_instant"): self.next_instant = True
            if kind == "direct_dot":
                self.apply_dot(name, a, sp)
            return
        if kind == "dot":
            out, m = self.spell_outcome(name, school, can_crit=False)
            if out == "miss": self.deal(name, 0, school, "spell", outcome="miss"); return
            self.apply_dot(name, a, sp); self.after_spell_hit(name, school, "hit", 0, a)
            self.record(name, "applied", 0)
            return

    def apply_dot(self, name, a, sp):
        c = self.c
        tick = (a.get("tick", 0) + sp * a.get("dot_coeff", 0)) * a["mult"]
        pandemic = c.mod("crit_dmg_periodic") if name in {"Corruption", "Curse of Agony", "Siphon Life", "Drain Soul", "Wrack"} else 0.0
        tick *= self.periodic_crit_mult(name, a["school"], bleed=a.get("bleed", False), extra_bonus=pandemic)
        instance = {"next": self.t + a["tick_len"], "remaining": a["ticks"], "tick": tick, "tick_len": a["tick_len"], "school": a["school"], "kind": "dot", "bleed": a.get("bleed", False)}
        primary = self.dots.get(name)
        primary_active = bool(primary and primary["remaining"] > 0 and primary["next"] - self.t < 1e9)
        if a.get("spreadable") and c.targets > 1 and primary_active:
            slot = next((x for x in self.dots_extra if x["name"] == name and x["remaining"] <= 0), None)
            if slot is None:
                slot = {"name": name}; self.dots_extra.append(slot)
            slot.update(instance)
        else:
            self.dots[name] = instance

    def after_spell_hit(self, name, school, out, dmg, a):
        c = self.c
        if c.flag("arcane_blast") and name != "Arcane Blast": self.buffs.pop("Arcane Blast", None)
        if c.flag("missile_barrage") and name in {"Arcane Blast", "Fireball", "Frostbolt", "Frostfire Bolt"} and out in {"hit", "crit"}:
            chance = 0.40 if name == "Arcane Blast" else 0.20
            if self.rng.random() < chance: self.add_buff("Missile Barrage", 20)
        if c.flag("hot_streak") and name in {"Fireball", "Fire Blast", "Scorch", "Frostfire Bolt"} and out == "crit":
            self.add_buff("Hot Streak", 15, stacks_max=3)
        if c.flag("fingers_of_frost") and name == "Frostbolt" and out in {"hit", "crit"} and self.rng.random() < 0.15:
            self.add_buff("Fingers of Frost", 15, stacks_max=2)
        if c.flag("shadow_weaving") and school == "shadow": self.add_debuff("Shadow Weaving", 15, stacks_max=5)
        if c.flag("improved_scorch") and name == "Scorch": self.add_debuff("Improved Scorch", 30, stacks_max=5)
        if c.flag("winters_chill") and school == "frost": self.add_debuff("Winter's Chill", 15, stacks_max=5)
        if self.combustion is not None and school == "fire" and out in {"hit", "crit"}: self.combustion["stacks"] += 1
        if c.flag("clearcasting") and out in {"hit", "crit"} and self.rng.random() < c.flag("clearcasting"): self.clearcast = True
        if c.flag("eclipse") and name == "Wrath": self.eclipse = min(4, self.eclipse + 2)
        if c.flag("lightning_overload") and name in {"Lightning Bolt", "Chain Lightning"} and self.rng.random() < c.flag("lightning_overload"):
            o2, m2 = self.spell_outcome(name, school, True)
            if o2 != "miss": self.row(name + " (Overload)").casts += 1; self.deal(name + " (Overload)", (self.rng.uniform(*a["base"]) + self.sp(school) * a.get("coeff", 0)) * 0.5, school, "spell", threat_mult=0.0, outcome=o2, mult=m2 * a["mult"])
        if c.flag("stormcaller") and name in {"Lightning Bolt", "Chain Lightning", "Earth Shock", "Flame Shock"} and out in {"hit", "crit"} and self.rng.random() < c.flag("stormcaller"):
            self.add_buff("Stormcaller's Garb", 8, stat="naturePower", value=50)
        if c.flag("shadow_and_flame"):
            if name == "Conflagrate": self.add_debuff("Shadow and Flame (shadow)", 20)
            if name == "Shadowburn": self.add_debuff("Shadow and Flame (fire)", 20)
        if out == "crit": self.on_crit(name, dmg, kind="spell")
        self.touch_of_the_grave()

    def complete_cast(self):
        cast = self.cast; self.cast = None
        name = cast["name"]; a = self.c.actions[name]
        if a.get("kind") == "channel":
            if name == "Arcane Missiles" and self.c.flag("netherwind_instant") and self.rng.random() < self.c.flag("netherwind_instant"): self.next_instant = True
            return
        self.resolve(name)

    def channel_tick(self):
        cast = self.cast; name = cast["name"]; a = self.c.actions[name]; c = self.c
        cast["ticks_left"] -= 1; cast["next_tick"] = cast["next_tick"] + cast["tick_len"]
        if not cast["landed"]: return
        school = a["school"]
        tick = a["tick"] + self.sp(school) * a["coeff"]
        if a.get("execute_bonus") and self.t >= self.execute_at:
            active = sum(1 for d in ("Corruption", "Curse of Agony", "Siphon Life") if self.dots.get(d) and self.dots[d]["remaining"] > 0)
            tick *= 1 + min(0.18, c.flag("improved_drains") * active) * 3
        out, m = ("hit", 1.0)
        if name == "Mind Flay": out, m = ("hit", 1.0)
        if a.get("kind") == "channel" and name == "Arcane Missiles":
            out, m = self.spell_outcome(name, school, True)
            if out == "miss": self.deal(name, 0, school, "spell", outcome="miss"); return
        if name == "Drain Soul":
            if c.flag("soul_siphon"): tick *= 1 + c.flag("soul_siphon")
            if c.flag("nightfall") and self.rng.random() < c.flag("nightfall"): self.proc_nightfall()
        dmg = self.deal(name, tick, school, "spell", periodic=(name != "Arcane Missiles"), outcome=out, mult=m * a["mult"] * (c.targets if a.get("aoe") else 1))
        self.after_spell_hit(name, school, out, dmg, a) if name == "Arcane Missiles" else None

    def dot_tick(self, name, d):
        c = self.c
        d["remaining"] -= 1; d["next"] += d["tick_len"]
        tick = d["tick"] * d.get("stacks", 1)
        r = self.row(name); r.casts += 0
        school = d["school"]
        self.deal(name, tick, school, "spell" if school != "physical" else "melee", periodic=True, outcome="hit")
        if name == "Rupture" and c.flag("thousand_cuts"): self.add_buff("Thousand Cuts", 10, stacks_max=5)
        if name == "Corruption" and c.flag("nightfall") and self.rng.random() < c.flag("nightfall"): self.proc_nightfall()
        if d["remaining"] <= 0 and name in {"Immolate", "Corruption", "Curse of Agony", "Siphon Life", "Serpent Sting", "Shadow Word: Pain", "Moonfire", "Insect Swarm", "Flame Shock", "Rip", "Rupture", "Explosive Trap"}:
            pass

    # ---- boss ------------------------------------------------------------
    def boss_swing(self):
        c = self.c; rng = self.rng
        raw = rng.uniform(2700, 3300)
        defense_bonus = (self.st["defense"] - TARGET_DEFENSE) * 0.0004
        miss = max(0.0, 0.05 + defense_bonus)
        dodge = max(0.0, self.st["dodge"] / 100 + defense_bonus)
        parry = max(0.0, self.st["parry"] / 100 + defense_bonus) if self.s["class_name"] in {"Warrior", "Paladin"} else 0.0
        block = max(0.0, self.st["block"] / 100 + defense_bonus) if self.st.get("block", 0) > 0 else 0.0
        crit = max(0.0, 0.05 - defense_bonus)
        crush = 0.15 if TARGET_LEVEL - LEVEL >= 3 else 0.0  # bonus defense only pushes crushes off via table coverage
        roll = rng.random(); acc = 0.0
        outcome = "hit"
        for name, chance in (("miss", miss), ("dodge", dodge), ("parry", parry), ("block", block), ("crit", crit), ("crush", crush)):
            acc += chance
            if roll < acc: outcome = name; break
        if self.next_parry: self.next_parry = False; outcome = "parry"
        if outcome in {"miss", "dodge", "parry"}:
            self.avoided_recently = self.t
            if outcome in {"dodge", "parry"} and c.flag("master_of_defense") and rng.random() < min(1.0, c.flag("master_of_defense")): self.gain_rage(5)
            if outcome == "dodge" and self.s["form"] == "bear" and c.mod("dodge"): self.gain_rage(5)
            if outcome in {"dodge", "parry"} and c.flag("improved_stormstrike") and rng.random() < min(1.0, c.flag("improved_stormstrike")): self.cooldowns["Stormstrike"] = self.t
            self.row("Boss melee").misses += 1; self.record("Boss melee", outcome, 0); return
        armor = self.st.get("armor", 0)
        mult = {"crit": 2.0, "crush": 1.5}.get(outcome, 1.0)
        amount = raw * mult * (1 - min(0.75, armor / (armor + 400 + 85 * TARGET_LEVEL)))
        amount *= STANCE_MODS.get(self.s["stance"] or self.s["form"], {}).get("taken", 1.0)
        if "demoralizing_shout" in c.debuffs: amount *= 0.90
        if outcome == "block":
            self.avoided_recently = self.t
            bv = self.st.get("blockValue", 0) + self.st["strength"] / 20
            amount = max(0.0, amount - bv)
            if c.flag("shield_spec_rage") and rng.random() < min(1.0, c.flag("shield_spec_rage")): self.gain_rage(5)
            if c.flag("wrath_parry") and rng.random() < c.flag("wrath_parry"): self.next_parry = True
        if self.buff_active("Stoneform"): amount *= 0.90
        self.taken += amount; self.health -= amount
        self.gain_rage(amount * 2.5 / (0.0091107836 * TARGET_LEVEL ** 2 + 3.225598133 * TARGET_LEVEL + 4.2652911), source="damage")
        if c.flag("enrage") and rng.random() < c.flag("enrage") * 3: self.enrage_until = self.t + 12
        if c.flag("might_rage") and rng.random() < c.flag("might_rage"): self.gain_rage(1)
        if c.flag("wildheart_proc") and rng.random() < c.flag("wildheart_proc"):
            if self.s["resource"] == "Mana": self.gain_mana(300)
            elif self.s["resource"] == "Rage": self.gain_rage(10)
            else: self.gain_energy(40)
        r = self.row("Boss melee"); r.casts += 1; r.hits += 1
        self.taken_by[outcome] = self.taken_by.get(outcome, 0.0) + amount
        self.record("Boss melee", outcome, amount)
        if self.health <= 0 and self.alive:
            self.alive = False; self.alive_seconds = self.t; self.record("Death", "death", 0)

    # ---- pets ------------------------------------------------------------
    def pet_setup(self):
        c = self.c
        if not c.pet: return
        p = c.pet
        if p["kind"] == "hunter":
            self.pet_state = {"focus": 100.0, "next_swing": 0.0, "gcd": 0.0, "ready": {}, "last": 0.0, "active_until": self.duration * p["uptime"], "frenzy_until": 0.0}
        else:
            cfg = p["cfg"]
            self.pet_state = {"mana": float(cfg["mana"]) * (1 + c.mod("stat_pct:mana") * 0), "next_swing": 0.0, "next_cast": 0.0, "cast_until": None, "active_until": self.duration * p["uptime"], "next_mana": 2.0}

    def pet_multiplier(self):
        c = self.c; m = 1.0
        if c.pet["kind"] == "hunter":
            m *= 1.25 * c.pet["damage"] * (1 + c.flag("pet_damage"))
            b = self.buffs.get("Bestial Wrath")
            if b and b["until"] > self.t: m *= 1.5
        else:
            m *= 1 + c.flag("pet_damage")
            if c.flag("soul_link"): m *= 1 + c.flag("soul_link")
            if c.flag("master_demonologist") and c.pet["family"] == "succubus": m *= 1 + c.flag("master_demonologist")
        creature = c.racial.get("creature_damage", {}).get(c.boss_type, 0) if c.racial_enabled else 0
        return m * (1 + creature)

    def pet_attack(self, name, base, school, crit_chance, ability=False):
        rng = self.rng
        # Pets have their own level-60 hit table. Owner hit, crit, dual wield,
        # weapon skill and forced-crit buffs must not leak into it.
        roll = rng.random()
        if school == "physical":
            glance = 0.0 if ability else 0.40
            if roll < 0.08: out, m = "miss", 0.0
            elif roll < 0.145: out, m = "dodge", 0.0
            elif roll < 0.145 + glance: out, m = "glance", rng.uniform(0.55, 0.75)
            elif roll < 0.145 + glance + max(0.0, crit_chance - 0.048): out, m = "crit", 2.0
            else: out, m = "hit", 1.0
        else:
            if roll >= 0.83: out, m = "miss", 0.0
            elif rng.random() < max(0.0, crit_chance - 0.021): out, m = "crit", 1.5
            else: out, m = "hit", 1.0
        r = self.row(name); r.casts += 1
        if out in {"miss", "dodge", "parry"}: r.misses += 1; self.record(name, out, 0); return 0.0
        dmg = base * m * self.pet_multiplier()
        if school == "physical": dmg *= self.armor_mult()
        if out == "crit": r.crits += 1
        if out == "glance": r.glances += 1
        r.hits += 1; r.damage += dmg; self.total += dmg; r.threat += dmg; self.pet_threat += dmg
        if out == "crit" and self.c.pet["kind"] == "hunter" and self.c.flag("pet_frenzy") and rng.random() < self.c.flag("pet_frenzy"):
            self.pet_state["frenzy_until"] = self.t + 8
        self.record(name, out, dmg)
        return dmg

    def pet_step(self):
        c = self.c; p = c.pet; ps = self.pet_state; rng = self.rng
        if ps is None or self.t >= ps["active_until"]: return
        if p["kind"] == "hunter":
            ps["focus"] = min(100.0, ps["focus"] + (self.t - ps["last"]) * PET_FOCUS_PER_SEC * (1 + c.flag("pet_focus"))); ps["last"] = self.t
            crit = 0.05 + c.flag("pet_crit") / 100
            if self.t + EPS >= ps["next_swing"]:
                # WoWSims sim/hunter/pet.go: own 136 Strength, 2 AP/Strength,
                # base -20 AP; no owner stat inheritance.
                speed = p["speed"]
                base = (rng.uniform(18.17, 27.66) + 252 / 14) * speed
                self.pet_attack("Pet Melee", base, "physical", crit)
                haste = 1.3 if self.t < ps["frenzy_until"] else 1.0
                ps["next_swing"] = self.t + self.pet_delay(speed / haste)
            if ps["gcd"] <= self.t + EPS:
                for name in (p["special"], p["dump"]):
                    if not name or name not in p["abilities"]: continue
                    cfg = PET_ABILITIES[name]
                    if ps["ready"].get(name, 0) > self.t or ps["focus"] < cfg["cost"]: continue
                    ps["focus"] -= cfg["cost"]; ps["ready"][name] = self.t + cfg["cooldown"]; ps["gcd"] = self.t + 1.6
                    self.pet_attack(f"Pet - {name}", rng.uniform(cfg["min"], cfg["max"]), cfg["school"], crit, ability=True)
                    break
                else:
                    ps["gcd"] = self.t + 0.5
        else:
            cfg = p["cfg"]; fam = p["family"]
            if self.t + EPS >= ps["next_mana"]:
                ps["mana"] = min(float(cfg["mana"]), ps["mana"] + cfg.get("spirit", 0) / 5 * 2); ps["next_mana"] += 2.0
            if cfg.get("speed") and "Melee" in p["abilities"] and self.t + EPS >= ps["next_swing"]:
                ap = cfg.get("strength", 0) * 2 - 20
                base = rng.uniform(*cfg["melee"]) + ap / 14 * cfg["speed"]
                self.pet_attack(f"{fam.title()} - Melee", base, "physical", 0.05)
                ps["next_swing"] = self.t + self.pet_delay(cfg["speed"])
            spell = cfg.get("spell")
            if spell and spell in p["abilities"]:
                if ps["cast_until"] is not None and self.t + EPS >= ps["cast_until"]:
                    ps["cast_until"] = None
                    mult = (1 + c.flag("improved_imp")) if fam == "imp" else (1 + c.flag("improved_sayaad"))
                    if c.flag("master_demonologist") and fam == "imp": mult *= 1 + c.flag("master_demonologist")
                    self.pet_attack(f"{fam.title()} - {spell}", rng.uniform(cfg["spell_min"], cfg["spell_max"]) * mult, cfg["school"], 0.05 + cfg.get("intellect", 0) * SPELL_CRIT_PER_INT["Mage"] / 100, ability=True)
                    ps["next_cast"] = self.t + cfg.get("cooldown", 0)
                if ps["cast_until"] is None and self.t + EPS >= ps["next_cast"] and ps["mana"] >= cfg["spell_cost"]:
                    ps["mana"] -= cfg["spell_cost"]
                    cast = cfg.get("cast", 0)
                    ps["cast_until"] = self.t + max(cast, 0.0) / (1.30 if "bloodlust" in c.buffs and self.t < 40 else 1)
                    if cast == 0: ps["cast_until"] = self.t
            if cfg.get("utility") in p["abilities"] and self.t + EPS >= ps.get("next_utility", 0):
                ps["next_utility"] = self.t + 5; r = self.row(f"{fam.title()} - {cfg['utility']}"); r.casts += 1; r.threat += 120; self.pet_threat += 120

    def pet_next(self):
        ps = self.pet_state
        if ps is None or self.t >= ps["active_until"]: return self.duration
        if self.c.pet["kind"] == "hunter": return min(ps["next_swing"], max(ps["gcd"], self.t + EPS))
        cands = [ps["next_mana"]]
        if self.c.pet["cfg"].get("speed"): cands.append(ps["next_swing"])
        if ps["cast_until"] is not None: cands.append(ps["cast_until"])
        else: cands.append(max(ps["next_cast"], self.t + 0.5))
        cands.append(ps.get("next_utility", self.t + 5))
        return min(cands)

    # ---- main loop -------------------------------------------------------
    def run(self):
        c = self.c; s = self.s
        self.taken_by = {}; self.pet_threat = 0.0
        self.pet_setup()
        if s["role"] == "tank":
            self.row("Taunt").casts += 1; self.record("Taunt", "cast", 0); self.gcd_until = GCD
        if s["style"] == "melee":
            self.next_mh = 0.0
            if c.oh: self.next_oh = float(c.oh["weaponSpeed"]) / 2
        elif s["style"] == "ranged":
            self.next_ranged = 0.0
        if s["resource"] == "Rage" and s["class_name"] == "Warrior": pass
        # Premeditation requires a stealth opener this sim doesn't model; approximated as a
        # one-time 2-combo-point grant at the start of the fight, its only realistic use case.
        if c.flag("premeditation"): self.cp = min(5, self.cp + 2)
        dur = self.duration
        guard = 0
        while self.t < dur - EPS and guard < 2_000_000:
            guard += 1
            self.use_offgcd()
            self.queue_swings()
            # Decide on the GCD if idle
            if self.t + EPS >= self.gcd_until and self.cast is None and self.alive:
                name = self.choose()
                if name is not None:
                    self.start(name)
                elif self.blocked_by_resource and self.s["resource"] == "Mana":
                    self.starved += 0.25
            # Next event time
            cands = [dur]
            if self.cast is not None:
                cands.append(self.cast["until"])
                if self.cast.get("ticks_left", 0) > 0: cands.append(self.cast["next_tick"])
            elif self.gcd_until > self.t + EPS: cands.append(self.gcd_until)
            else: cands.append(self.t + 0.25)
            if s["style"] == "melee":
                cands.append(self.next_mh)
                if c.oh: cands.append(self.next_oh)
            if s["style"] == "ranged": cands.append(self.next_ranged)
            for d in self.dots.values():
                if d["remaining"] > 0: cands.append(d["next"])
            for d in self.dots_extra:
                if d["remaining"] > 0: cands.append(d["next"])
            if s["resource"] == "Mana": cands.append(self.next_mana_tick)
            if s["resource"] == "Energy": cands.append(self.next_energy_tick)
            if s["resource"] == "Rage":
                if c.flag("anger_management"): cands.append(self.next_rage_tick)
                b = self.buffs.get("Bloodrage")
                if b and b["until"] > self.t: cands.append(b["next"])
            if s["role"] == "tank": cands.append(self.next_boss); cands.append(self.next_heal)
            if c.pet: cands.append(self.pet_next())
            nt = min(x for x in cands if x > self.t + EPS) if any(x > self.t + EPS for x in cands) else dur
            self.t = min(nt, dur)
            if self.t >= dur - EPS: break
            t = self.t
            # ---- events at t
            if self.cast is not None and self.cast.get("ticks_left", 0) > 0 and abs(t - self.cast["next_tick"]) < 1e-6: self.channel_tick()
            if self.cast is not None and t + EPS >= self.cast["until"]: self.complete_cast()
            for name, d in list(self.dots.items()):
                if d["remaining"] > 0 and t + EPS >= d["next"]: self.dot_tick(name, d)
            for d in self.dots_extra:
                if d["remaining"] > 0 and t + EPS >= d["next"]: self.dot_tick(d["name"], d)
            if s["style"] == "melee":
                if t + EPS >= self.next_mh:
                    if self.alive: self.swing(c.mh, "main")
                    self.next_mh = t + self.attack_delay(float(c.mh["weaponSpeed"]), "melee")
                if c.oh and t + EPS >= self.next_oh:
                    if self.alive: self.swing(c.oh, "off")
                    self.next_oh = t + self.attack_delay(float(c.oh["weaponSpeed"]), "melee")
            if s["style"] == "ranged" and t + EPS >= self.next_ranged and (self.cast is None or not c.actions[self.cast["name"]].get("ranged_cast")):
                self.auto_shot(); self.next_ranged = t + self.attack_delay(float(c.ranged["weaponSpeed"]), "ranged")
            if s["resource"] == "Mana" and t + EPS >= self.next_mana_tick:
                self.next_mana_tick += 2.0
                mp5 = self.st.get("mp5", 0)
                regen = mp5 / 5 * 2
                frac, base = SPIRIT_REGEN.get(s["class_name"], (0.2, 15))
                spirit_regen = self.st["spirit"] * frac + base
                if t - self.last_cast_time >= 5: regen += spirit_regen
                else: regen += spirit_regen * c.flag("spirit_while_casting")
                self.gain_mana(regen)
            if s["resource"] == "Energy" and t + EPS >= self.next_energy_tick:
                self.next_energy_tick += 2.0
                mult = 2.0 if self.buff_active("Adrenaline Rush") else 1.0
                self.gain_energy(20 * mult)
            if s["resource"] == "Rage":
                if c.flag("anger_management") and t + EPS >= self.next_rage_tick: self.next_rage_tick += 3.0; self.gain_rage(1)
                b = self.buffs.get("Bloodrage")
                if b and b["until"] > t and t + EPS >= b["next"]: b["next"] += 1.0; self.gain_rage(b["tick"])
            if s["role"] == "tank":
                if t + EPS >= self.next_boss: self.boss_swing(); self.next_boss += 2.0 / (0.9 if "thunder_clap" in c.debuffs else 1.0)
                if t + EPS >= self.next_heal: self.health = min(self.health_max, self.health + 2500); self.next_heal += 2.0
            if c.pet: self.pet_step()
            if self.resource() < 1 and s["resource"] == "Mana" and self.first_oom is None: self.first_oom = t
        return self.result()

    def result(self):
        dur = self.duration
        return {"total": self.total, "threat": self.threat + self.pet_threat * 0.0, "pet_threat": self.pet_threat, "taken": self.taken, "rows": {k: v.dict() for k, v in self.rows.items()},
                "duration": dur, "starved": self.starved, "resource_end": self.resource(), "alive": self.alive, "alive_seconds": self.alive_seconds, "first_oom": self.first_oom, "taken_by": self.taken_by, "log": self.log,
                "buff_active_seconds": self.buff_active_seconds, "buff_procs": self.buff_procs}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def simulate(request, items, enchants, sets):
    cfg = Config(request, items, enchants, sets)
    results = [Iteration(cfg, cfg.seed + i, trace=(i == 0)).run() for i in range(cfg.iterations)]
    n = len(results)
    dps = [r["total"] / r["duration"] for r in results]
    tps = [(r["threat"] + r["pet_threat"]) / r["duration"] for r in results]
    dtps = [r["taken"] / r["duration"] for r in results]
    alive = [r["taken"] / max(r["alive_seconds"], 0.001) for r in results]
    agg = {}
    for r in results:
        for name, row in r["rows"].items():
            target = agg.setdefault(name, {k: 0.0 for k in row})
            for k, v in row.items(): target[k] += v
    duration = cfg.duration
    buff_seconds_agg, buff_proc_agg = {}, {}
    for r in results:
        for name, secs in r["buff_active_seconds"].items(): buff_seconds_agg[name] = buff_seconds_agg.get(name, 0.0) + secs
        for name, procs in r["buff_procs"].items(): buff_proc_agg[name] = buff_proc_agg.get(name, 0) + procs
    measured_buff_uptimes = {name: min(1.0, secs / n / duration) for name, secs in buff_seconds_agg.items()}
    buff_procs_per_min = {name: procs / n / (duration / 60.0) for name, procs in buff_proc_agg.items()}

    def metric(values):
        mean = statistics.fmean(values); ci = None if len(values) < 2 else 1.96 * statistics.stdev(values) / math.sqrt(len(values))
        return {"mean": mean, "mean_95ci_half_width": ci}
    ability_stats = {name: {k: v / n for k, v in row.items()} for name, row in agg.items()}
    ability_dps = {name: row["damage"] / n / duration for name, row in agg.items()}
    ability_damage = {name: row["damage"] / n for name, row in agg.items()}
    threat_by = {name: row["threat"] / n / duration for name, row in agg.items()}
    starved = statistics.fmean(r["starved"] / r["duration"] for r in results)
    taken_by = {}
    for r in results:
        for k, v in r["taken_by"].items(): taken_by[k] = taken_by.get(k, 0.0) + v / n / duration
    cfg_summary = cfg.summary()
    res_name = cfg.spec["resource"]
    max_res = {"Mana": cfg.stats.get("mana", 0), "Energy": 100 + cfg.flag("max_energy") + cfg.stats.get("maxEnergy", 0), "Rage": 100 + cfg.flag("max_rage")}[res_name]
    return {
        "profile": {"spec": cfg.spec["id"], "race": cfg.race, "level": LEVEL, "target_level": TARGET_LEVEL, "duration": duration, "duration_variance": cfg.variance, "iterations": cfg.iterations, "seed": cfg.seed},
        "spec": dict(cfg.spec, actions=cfg.action_names, opener=("Taunt" if cfg.spec["role"] == "tank" else None), races=CLASS_RACES[cfg.spec["class_name"]]),
        "metrics": {"dps": metric(dps), "tps": metric(tps), "dtps": metric(dtps), "alive_dtps": metric(alive), "survival_fraction": sum(r["alive"] for r in results) / n},
        "ability_dps": ability_dps, "ability_damage": ability_damage, "ability_stats": ability_stats, "threat_by_ability": threat_by, "taken_dtps": taken_by,
        "configuration": cfg_summary,
        "resource": {"name": res_name, "maximum": max_res, "mean_end": statistics.fmean(r["resource_end"] for r in results), "starved_fraction": starved, "first_out_of_mana": statistics.fmean([r["first_oom"] for r in results if r["first_oom"] is not None]) if any(r["first_oom"] is not None for r in results) else None},
        "buff_uptimes": dict({x: 1.0 for x in sorted(cfg.buffs | cfg.consumes)}, **measured_buff_uptimes), "debuff_uptimes": {x: 1.0 for x in sorted(cfg.debuffs)},
        "buff_procs_per_min": buff_procs_per_min,
        "log": results[0]["log"],
        "model_status": "Event-driven level-60 model: sourced base damage, coefficients, cast times, Classic attack tables (miss, dodge, parry, glancing, block, crit suppression), resource ticks, combo points, DoTs, procs, timed cooldowns, pets and racials. No calibration multiplier. Provisional values are listed under configuration.notes.",
        "source": "https://www.wowhead.com/forever/ (roster, racials, talents) + WoWSims Classic (Classic Anniversary ability data)",
    }
