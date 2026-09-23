"use strict";
const $ = id => document.getElementById(id);
const fmt = (n, d = 1) => Number(n).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
const PM = "±", DOT = " · ";
const specId = new URLSearchParams(location.search).get("spec") || "warrior-arms";
let data, spec, profile, baseProfile, points = {}, trees = [], catalogItems = [], pickerIndex = -1, lastResult = null, wsData = null;

const enchantSlot = s => ({ "Head": "head", "Shoulders": "shoulders", "Back": "back", "Chest": "chest", "Wrist": "wrist", "Hands": "hands", "Legs": "legs", "Feet": "feet", "Main Hand": "main_hand", "Off Hand": "off_hand", "Ranged / Relic": "ranged" })[s] || "";
const petFamilies = { none: { name: "No pet", abilities: [], damage: 0 }, cat: { name: "Cat", abilities: ["Bite", "Claw"], damage: 1.10 }, wind_serpent: { name: "Wind Serpent", abilities: ["Bite", "Lightning Breath"], damage: 1.07 }, bat: { name: "Bat", abilities: ["Bite", "Screech"], damage: 1.07 }, bear: { name: "Bear", abilities: ["Bite", "Claw"], damage: .91 }, boar: { name: "Boar", abilities: ["Bite"], damage: .90 }, carrion_bird: { name: "Carrion Bird", abilities: ["Bite", "Claw"], damage: 1 }, owl: { name: "Owl", abilities: ["Claw"], damage: 1.07 }, crab: { name: "Crab", abilities: ["Claw"], damage: .95 }, crocolisk: { name: "Crocolisk", abilities: ["Bite"], damage: 1 }, gorilla: { name: "Gorilla", abilities: ["Bite"], damage: 1.02 }, hyena: { name: "Hyena", abilities: ["Bite"], damage: 1 }, raptor: { name: "Raptor", abilities: ["Bite", "Claw"], damage: 1.10 }, scorpid: { name: "Scorpid", abilities: ["Scorpid Poison", "Claw"], damage: .94 }, spider: { name: "Spider", abilities: ["Bite"], damage: 1.07 }, tallstrider: { name: "Tallstrider", abilities: ["Bite"], damage: 1 }, turtle: { name: "Turtle", abilities: ["Bite"], damage: .90 }, wolf: { name: "Wolf", abilities: ["Bite"], damage: 1 } };
const warlockPets = { imp: { name: "Imp", abilities: ["Firebolt"], speed: 0, summary: "Ranged Firebolt caster (2.0 s cast, 115 mana, spirit-based mana regeneration). Master Demonologist adds Fire damage." }, succubus: { name: "Succubus / Incubus", abilities: ["Melee", "Lash of Pain"], speed: 2, summary: "2.0 speed melee plus Lash of Pain every 12 s. Master Demonologist adds Shadow damage." }, felhunter: { name: "Felhunter", abilities: ["Melee"], speed: 2, summary: "2.0 speed melee; utility spells have no Patchwerk damage." }, voidwalker: { name: "Voidwalker", abilities: ["Melee", "Torment"], speed: 2, summary: "2.0 speed melee plus Torment threat." }, none: { name: "No demon (sacrificed / dismissed)", abilities: [], speed: 0, summary: "No pet damage; Lone Wolf-style talents apply where the class has them." } };

function tooltip(html, e) { const t = $("tooltip"); const host = document.querySelector("dialog[open]") || document.body; if (t.parentNode !== host) host.append(t); t.innerHTML = html; t.hidden = false; const r = t.getBoundingClientRect(), x = Math.min(innerWidth - r.width - 10, e.clientX + 16), y = Math.min(innerHeight - r.height - 10, e.clientY + 16); t.style.left = Math.max(8, x) + "px"; t.style.top = Math.max(8, y) + "px"; }
function hideTip() { $("tooltip").hidden = true; }
function applyBarWidths(root) { root.querySelectorAll("[data-bar-width]").forEach(el => el.style.width = `${Math.max(0, Math.min(100, +el.dataset.barWidth || 0))}%`); }
function showTab(name) { document.querySelectorAll(".main-tab").forEach(x => x.classList.toggle("active", x.dataset.tab === name)); document.querySelectorAll(".view-panel").forEach(x => x.classList.toggle("active", x.id === `view-${name}`)); }

// ---------------------------------------------------------------- gear
const armorOrder = ["Cloth", "Leather", "Mail", "Plate"], armorMax = { Warrior: 3, Paladin: 3, Hunter: 2, Shaman: 2, Rogue: 1, Druid: 1, Mage: 0, Priest: 0, Warlock: 0 };
const slotKeys = { "Head": ["head"], "Neck": ["neck"], "Shoulders": ["shoulders"], "Back": ["back"], "Chest": ["chest"], "Wrist": ["wrist"], "Hands": ["hands"], "Waist": ["waist"], "Legs": ["legs"], "Feet": ["feet"], "Finger 1": ["finger1", "finger2"], "Finger 2": ["finger1", "finger2"], "Trinket 1": ["trinket1", "trinket2"], "Trinket 2": ["trinket1", "trinket2"], "Main Hand": ["main_hand"], "Off Hand": ["off_hand"], "Ranged / Relic": ["ranged", "relic"] };
const classWeapons = { Warrior: ["Axe", "Bow", "Crossbow", "Dagger", "Fist Weapon", "Gun", "Mace", "Polearm", "Shield", "Staff", "Sword", "Thrown"], Druid: ["Dagger", "Mace", "Staff", "Fist Weapon", "Idol"], Hunter: ["Axe", "Bow", "Crossbow", "Dagger", "Fist Weapon", "Gun", "Polearm", "Staff", "Sword", "Thrown"], Mage: ["Dagger", "Staff", "Sword", "Wand", "Off Hand"], Priest: ["Dagger", "Mace", "Staff", "Wand", "Off Hand"], Rogue: ["Bow", "Crossbow", "Dagger", "Fist Weapon", "Gun", "Mace", "Sword", "Thrown"], Shaman: ["Axe", "Dagger", "Fist Weapon", "Mace", "Shield", "Staff", "Totem", "Off Hand"], Warlock: ["Dagger", "Staff", "Sword", "Wand", "Off Hand"] };
const weaponKinds = ["Axe", "Bow", "Crossbow", "Dagger", "Fist Weapon", "Gun", "Mace", "Polearm", "Shield", "Staff", "Sword", "Wand", "Thrown", "Idol", "Totem", "Libram", "Off Hand"];
function itemSubclass(it) { return it.subclass || ""; }
const raceFaction = () => data.equipment_rules?.race_factions?.[$("race").value];
function allowedItem(it, slot) {
  if (!it.id || !(it.equipSlots || []).some(x => (slotKeys[slot] || []).includes(x))) return false;
  if (it.faction && it.faction !== raceFaction()) return false;
  if ((it.requiredLevel || 0) > 60 || it.simulationAvailability === "excluded") return false;
  const ai = armorOrder.indexOf(it.subclass); if (ai >= 0 && ai > armorMax[spec.class_name]) return false;
  if (it.allowedClasses && !it.allowedClasses.includes(spec.class_name)) return false;
  const classLine = (it.tooltip || []).find?.(x => String(x.label).startsWith("Classes:")); if (classLine && !classLine.label.split(":")[1].split(",").map(x => x.trim()).includes(spec.class_name)) return false;
  const kind = weaponKinds.find(x => String(it.subclass || "").includes(x));
  if (kind && !(classWeapons[spec.class_name] || []).includes(kind)) return false;
  const melee = ["Axe", "Dagger", "Fist Weapon", "Mace", "Polearm", "Staff", "Sword"];
  if (slot === "Main Hand" && !melee.includes(kind)) return false;
  if (slot === "Off Hand" && melee.includes(kind) && (!["Warrior", "Rogue", "Hunter"].includes(spec.class_name) || it.slot === "Two-Hand")) return false;
  if (spec.form && ["Main Hand", "Off Hand"].includes(slot) && ["Shield", "Off Hand"].includes(kind)) return false;
  return true;
}
function permanentStats(it) { const out = { ...(it.stats || {}) }; for (const e of it.effects || []) { if (!e.startsWith("Use:")) continue; if (/damage and healing.*?up to \d+ for \d+ sec/i.test(e)) delete out.spellPower; if (/Attack Power by \d+ for \d+ sec/i.test(e)) delete out.attackPower; if (/attack speed by \d+% for \d+ sec/i.test(e)) { delete out.meleeHaste; delete out.rangedHaste; delete out.spellHaste; } } return out; }
function itemTip(it) { let set = ""; if (it.set) { const names = new Set(profile.gear.filter(x => x.id).map(x => x.name)), count = it.set.pieces.filter(x => names.has(x)).length; set = `<h4>${it.set.name} (${count}/${it.set.pieces.length})</h4>${it.set.bonuses.map(b => `<p class="set-bonus ${count >= b.required ? "active" : "inactive"}">(${b.required}) Set: ${b.description}${DOT}${count >= b.required ? "active" : "inactive"}</p>`).join("")}`; } return `<h3 class="quality-${it.quality}">${it.name}</h3><p>Item Level ${it.itemLevel || "?"}${DOT}${itemSubclass(it)}${it.weaponSpeed ? `${DOT}${Number(it.weaponSpeed).toFixed(2)} speed${DOT}${it.weaponDamageMin}-${it.weaponDamageMax}` : ""}</p>${Object.entries(permanentStats(it)).map(([k, v]) => `<p>+${v} ${k.replace(/([A-Z])/g, " $1")}</p>`).join("")}<p>${(it.effects || []).join("<br>")}</p>${set}<p class="tooltip-meta">${[it.source,it.availabilityNote,...(it.modelNotes||[])].filter(Boolean).join(DOT)}</p>`; }
function enchantRows(it) { const slot = enchantSlot(it.slot); if (!slot || !it.id) return []; const rows = data.enchants.slots[slot] || []; const kinds = ["Axe", "Dagger", "Fist Weapon", "Mace", "Polearm", "Staff", "Sword"]; if (slot === "ranged") return it.subclass === "Gun" ? rows : []; if (["main_hand", "off_hand"].includes(slot) && !kinds.some(k => String(it.subclass || "").includes(k))) return []; return rows; }
function defaultEnchant(it) {
  const rows = enchantRows(it), prefer = data.enchant_preferences?.[spec.id]?.[enchantSlot(it.slot)] || [];
  for (const id of prefer) { const row = rows.find(x => x.id === id); if (row) return row; }
  return null;
}
function renderPicker() { const slot = profile.gear[pickerIndex].slot, q = $("itemSearch").value.trim().toLowerCase(); const list = catalogItems.filter(it => allowedItem(it, slot) && (!q || `${it.name} ${it.source || ""} ${it.subclass || ""}`.toLowerCase().includes(q))).sort((a, b) => (b.itemLevel || 0) - (a.itemLevel || 0)).slice(0, 250); $("itemCount").textContent = `${list.length}${list.length === 250 ? " shown" : ""}`; $("itemList").innerHTML = list.map(it => `<button type="button" class="item-row quality-${it.quality}" data-id="${it.id}"><span class="slot-icon"><img src="/item-icons/${it.icon}.jpg" alt=""></span><span><h3>${it.name}</h3><p>${it.subclass || ""}${DOT}${it.source || "Classic Era"}</p></span><span class="item-stats">${Object.entries(permanentStats(it)).slice(0, 4).map(([k, v]) => `${k} ${v}`).join(DOT)}</span><span class="ilvl">ilvl ${it.itemLevel || "?"}</span></button>`).join(""); document.querySelectorAll(".item-row").forEach(b => { const it = catalogItems.find(x => x.id === +b.dataset.id); b.onclick = () => { profile.gear[pickerIndex] = { ...it, itemSlot: it.slot, slot, enchant: null }; profile.gear[pickerIndex].enchant = defaultEnchant(profile.gear[pickerIndex]); if (slot === "Main Hand" && it.slot === "Two-Hand") { const oh = profile.gear.findIndex(x => x.slot === "Off Hand"); if (oh >= 0) profile.gear[oh] = { slot: "Off Hand", id: 0, name: "Empty (two-hand equipped)", icon: "inv_misc_questionmark", quality: "Common", itemLevel: 0, stats: {}, effects: [] }; } $("itemDialog").close(); renderGear(); }; b.onmousemove = e => tooltip(itemTip(it), e); b.onmouseleave = hideTip; }); }
function openPicker(index) { hideTip(); pickerIndex = index; const it = profile.gear[index], rows = enchantRows(it); $("pickerSlot").textContent = `Choose ${it.slot}`; $("pickerTitle").textContent = `${spec.class_name} equipment`; $("itemSearch").value = ""; $("enchantPicker").hidden = !rows.length; $("enchantSelect").innerHTML = `<option value="">No enchant</option>` + rows.filter(x => x.id !== "none").map(x => `<option value="${x.id}" ${it.enchant?.id === x.id ? "selected" : ""}>${x.name} - ${x.description}</option>`).join(""); renderPicker(); $("itemDialog").appendChild($("tooltip")); $("itemDialog").showModal(); $("itemSearch").focus(); }
function renderGear() {
  const totals = {}, sources = {}, add = (k, v, src, cat) => { if (!v) return; totals[k] = (totals[k] || 0) + v; (sources[k] ??= []).push({ value: v, source: src, category: cat }); };
  $("gearSlots").innerHTML = profile.gear.map((it, i) => { for (const [k, v] of Object.entries(permanentStats(it))) add(k, v, it.name, "gear"); for (const [k, v] of Object.entries(it.enchant?.stats || {})) add(k === "primary" ? (spec.style === "spell" ? "intellect" : (["Rogue", "Hunter", "Druid"].includes(spec.class_name) ? "agility" : "strength")) : k, v, it.enchant.name, "enchant"); return `<button class="gear-slot ${it.id ? "equipped" : ""} quality-${it.quality || "Common"}" data-index="${i}"><span class="slot-icon"><img src="/item-icons/${it.icon || "inv_misc_questionmark"}.jpg" alt=""></span><span class="slot-copy"><small>${it.slot}</small><strong>${it.name || "Empty"}</strong>${itemSubclass(it) && ["Main Hand", "Off Hand", "Ranged / Relic"].includes(it.slot) ? `<small class="weapon-type">${itemSubclass(it)}${it.weaponSpeed ? `${DOT}${Number(it.weaponSpeed).toFixed(2)} speed` : ""}</small>` : ""}${it.enchant ? `<em>${it.enchant.name}</em>` : ""}</span><span class="slot-level">${it.itemLevel || ""}</span></button>`; }).join("");
  const labels = { attackPower: "Attack Power", rangedAttackPower: "Ranged Attack Power", spellPower: "Spell Power", firePower: "Fire Spell Power", frostPower: "Frost Spell Power", shadowPower: "Shadow Spell Power", naturePower: "Nature Spell Power", arcanePower: "Arcane Spell Power", healingPower: "Healing Power", spellHit: "Spell Hit", spellCrit: "Spell Crit", rangedHit: "Ranged Hit", rangedCrit: "Ranged Crit", mana: "Mana", mp5: "Mana per 5 sec", meleeHit: "Melee Hit", meleeCrit: "Melee Crit", fireResistance: "Fire Resistance", blockValue: "Block Value" };
  const pct = new Set(["meleeHit", "meleeCrit", "spellHit", "spellCrit", "rangedHit", "rangedCrit", "dodge", "parry", "block"]), label = k => labels[k] || k.replace(/([A-Z])/g, " $1").replace(/^./, x => x.toUpperCase()), display = (k, v) => `${fmt(v, 0)}${pct.has(k) ? "%" : ""}`;
  const rows = Object.entries(totals).sort((a, b) => b[1] - a[1]);
  $("gearStats").innerHTML = rows.map(([k, v]) => `<div class="gear-stat"><span>${label(k)}</span><strong>${display(k, v)}</strong></div>`).join("");
  const side = spec.style === "spell" ? ["spellPower", "firePower", "frostPower", "shadowPower", "naturePower", "arcanePower", "spellHit", "spellCrit", "intellect", "spirit", "mp5", "stamina"] : spec.class_name === "Hunter" ? ["rangedAttackPower", "attackPower", "agility", "rangedHit", "meleeHit", "rangedCrit", "meleeCrit", "intellect", "stamina"] : ["armor", "attackPower", "strength", "agility", "meleeCrit", "meleeHit", "dodge", "parry", "block", "blockValue", "defense", "stamina"];
  $("sideGearStats").innerHTML = side.filter(k => totals[k] != null).map(k => `<div class="side-stat" data-stat="${k}"><span>${label(k)}</span><b>${display(k, totals[k])}</b></div>`).join("");
  $("gearStats").querySelectorAll(".gear-stat").forEach((el, i) => { el.dataset.stat = rows[i]?.[0] || ""; });
  renderSetBonuses();
  document.querySelectorAll(".side-stat[data-stat], .gear-stat[data-stat]").forEach(el => { const k = el.dataset.stat; const src = sources[k] || []; if (!src.length) return; el.classList.add("has-tip"); const unit = pct.has(k) ? "%" : ""; const sub = cat => src.filter(x => x.category === cat).reduce((a, x) => a + x.value, 0); el.onmousemove = e => tooltip(`<h3>${label(k)}: ${display(k, totals[k])}</h3><p><strong>Gear:</strong> ${fmt(sub("gear"), 0)}${unit}${sub("enchant") ? `${DOT}<strong>Enchants:</strong> ${fmt(sub("enchant"), 0)}${unit}` : ""}</p><p class="tooltip-meta">${src.map(x => `${x.source}: ${fmt(x.value, 0)}${unit}`).join("<br>")}</p><p class="tooltip-meta">Base attributes, buffs, consumables and talents are added in the simulation result.</p>`, e); el.onmouseleave = hideTip; });
  document.querySelectorAll(".gear-slot").forEach(x => { const it = profile.gear[+x.dataset.index]; x.onclick = () => openPicker(+x.dataset.index); x.onmousemove = e => tooltip(itemTip(it) + (it.enchant ? `<p class='tooltip-enchant'>${it.enchant.name}: ${it.enchant.description}</p>` : ""), e); x.onmouseleave = hideTip; });
  $("gearProvenance").innerHTML = `Preset: <a href="${profile.source}" target="_blank" rel="noreferrer">${profile.source_label || profile.source}</a>. Click any slot to browse compatible gear. Gear totals here exclude base attributes, buffs and talents; the simulation result shows the complete character.`;
}

// ---------------------------------------------------------------- settings
function renderOptions(target, list, kind) {
  const chosen = new Set(kind === "buffs" ? spec.default_buffs : kind === "consumables" ? spec.default_consumables : list.map(x => x.key));
  const visible = kind === "consumables" ? list.filter(x => spec.default_consumables.includes(x.key)) : list;
  $(target).innerHTML = visible.map(x => `<label class="setting-option" data-tip="<h3>${x.name}</h3><p>${x.description || ""}</p><p class='tooltip-meta'>${x.source || x.kind || ""}</p>"><input type="checkbox" data-kind="${kind}" data-key="${x.key}" data-group="${x.group || ""}" ${chosen.has(x.key) ? "checked" : ""}><img src="/${kind === "consumables" ? "consumable" : "setting"}-icons/${x.icon}.jpg" alt=""><span><strong>${x.name}</strong><small>${x.source || x.kind || ""}</small></span></label>`).join("");
  document.querySelectorAll(`#${target} .setting-option`).forEach(x => { x.onmousemove = e => tooltip(x.dataset.tip, e); x.onmouseleave = hideTip; });
  if (kind === "consumables") document.querySelectorAll("[data-kind=consumables]").forEach(x => x.onchange = () => { if (x.checked && x.dataset.group) document.querySelectorAll(`[data-kind=consumables][data-group="${x.dataset.group}"]`).forEach(y => { if (y !== x) y.checked = false; }); });
  if (kind === "buffs") document.querySelectorAll("[data-kind=buffs]").forEach(x => x.onchange = () => { if (!x.checked) return; for (const group of Object.values(data.buff_groups || {})) if (group.includes(x.dataset.key)) group.forEach(k => { const y = document.querySelector(`[data-kind=buffs][data-key="${k}"]`); if (y && y !== x) y.checked = false; }); });
}
function renderSpecCards() {
  const siblings = data.specs.filter(x => x.class_name === spec.class_name);
  const card = $("specCard"); if (!card) return;
  card.hidden = siblings.length < 2;
  const race = encodeURIComponent($("race")?.value || "");
  $("specCards").innerHTML = siblings.map(s => `<a class="spec ${s.id === spec.id ? "active" : ""}" href="/all-specs.html?spec=${s.id}${race ? "&race=" + race : ""}"><b class="spec-icon"><img src="/spec-icons/${s.id}.jpg" alt=""></b><span><strong>${s.name}</strong><small>${s.role === "tank" ? "Threat & survivability" : s.style === "spell" ? "Spell damage" : s.style === "ranged" ? "Ranged damage" : "Melee damage"}</small></span></a>`).join("");
}
function setBonusState(setName, bonus) {
  const key = `${setName}|${bonus.required}`;
  if (data.set_provisional?.[key]) return { modeled: true, label: "modeled (assumption)", note: data.set_provisional[key] };
  if (data.set_effects?.[key]) return { modeled: true, label: "modeled" };
  if (/chance on|chance to (?:gain|increase|grant|restore|trigger)|proc|for \d+ sec|when |whenever |after |stack/i.test(bonus.description || "")) return { modeled: false, label: "not modeled" };
  if (bonus.stats && Object.keys(bonus.stats).length) return { modeled: true, label: "modeled" };
  if ((data.set_patterns || []).some(p => new RegExp(p, "i").test(bonus.description || ""))) return { modeled: true, label: "modeled" };
  if ((data.set_no_combat_effect || []).includes(key)) return { modeled: true, label: "no effect in this fight" };
  return { modeled: false, label: "not modeled" };
}
function renderSetBonuses() {
  const box = $("setBonuses"); if (!box) return;
  const worn = {};
  for (const it of profile.gear) { if (it.set?.name) { (worn[it.set.name] ??= { count: 0, set: it.set }).count++; } }
  const names = Object.keys(worn);
  if (!names.length) { box.innerHTML = "<h4>Set bonuses</h4><p class=\"set-none\">No set pieces equipped.</p>"; return; }
  box.innerHTML = "<h4>Set bonuses</h4>" + names.map(name => {
    const { count, set } = worn[name]; const total = set.pieces?.length || Math.max(count, ...(set.bonuses || []).map(b => b.required || 0));
    const rows = (set.bonuses || []).map(b => { const st = setBonusState(name, b); const active = count >= (b.required || 99);
      return `<li class="set-bonus ${active ? "active" : "inactive"} ${st.modeled ? "modeled" : "unmodeled"}" ${st.note ? `title="${st.note.replace(/"/g, "&quot;")}"` : ""}><b>(${b.required})</b> ${b.description || ""} <em>${active ? st.label : "needs " + b.required}</em></li>`; }).join("");
    return `<div class="set-block"><p class="set-name"><strong>${name}</strong> <span>${count}/${total}</span></p><ul>${rows}</ul></div>`;
  }).join("");
}
function renderRace() { const race = $("race").value; $("racialSummary").textContent = data.racials[race] || ""; }
function renderRotation() {
  $("aboutDps").textContent = spec.about?.dps || "Not documented yet.";
  $("aboutTps").textContent = spec.about?.tps || "Not documented yet.";
  const race = $("race").value, summary = data.racials[race] || "";
  const rows = [{ name: `Racial: ${race}`, racial: true, note: summary }, ...(spec.opener ? [{ name: spec.opener, opener: true }] : []), ...spec.actions.map(name => ({ name }))];
  $("rotationList").innerHTML = rows.map((row, i) => row.opener ? `<li class="rotation-opener"><strong>${row.name}</strong><span>Opening cast on the assigned target before the priority list begins.</span></li>` : row.racial ? `<li class="rotation-racial"><label class="rotation-toggle"><input type="checkbox" data-racial="1" checked><span><strong>${row.name}</strong><small>${row.note}</small></span></label></li>` : `<li><label class="rotation-toggle"><input type="checkbox" data-rotation="${row.name}" checked><span><strong>${row.name}</strong><small>Priority ${i}${DOT}conditions are evaluated by the engine (execute phase, resource pooling, dot/buff uptime).</small></span></label></li>`).join("");
}
function renderPetSettings() {
  const hunter = spec.class_name === "Hunter", warlock = spec.class_name === "Warlock", hasPet = hunter || warlock; $("petSettings").hidden = !hasPet; $("petRotationCard").hidden = !hasPet; if (!hasPet) return;
  const catalog = hunter ? petFamilies : warlockPets, current = $("petFamily").value;
  if ($("petFamily").dataset.owner !== spec.class_name) { $("petFamily").innerHTML = Object.entries(catalog).map(([key, x]) => `<option value="${key}">${x.name}</option>`).join(""); $("petFamily").dataset.owner = spec.class_name; $("petFamily").value = hunter ? "cat" : "succubus"; } else if (current in catalog) $("petFamily").value = current;
  const family = catalog[$("petFamily").value] || Object.values(catalog)[0];
  $("petSettingsTitle").textContent = hunter ? "Hunter pet" : "Warlock demon"; $("petFamilyLabel").textContent = hunter ? "Pet family" : "Active demon"; $("petSpeedField").hidden = warlock;
  $("petSummary").textContent = hunter ? `${family.name}: ${(family.damage * 100).toFixed(0)}% family damage modifier. Focus regenerates 5 per second; abilities use a 1.6 second pet GCD. Pets use the level-63 attack table.` : `${family.name}: ${family.summary}`;
  $("petRotation").innerHTML = family.abilities.map((name, i) => `<label class="setting-option"><input type="checkbox" data-pet-ability="${name}" checked><span><strong>${i + 1}. ${name}</strong><small>${hunter ? ({ Bite: "35 Focus, 10 sec cooldown", Claw: "25 Focus", "Lightning Breath": "50 Focus, Nature damage", Screech: "20 Focus", "Scorpid Poison": "30 Focus, Nature damage" })[name] : ({ Melee: "Automatic physical attacks", Firebolt: "115 mana, 2.0 sec cast", "Lash of Pain": "160 mana, 12 sec cooldown", Torment: "Threat only" })[name]}</small></span></label>`).join("");
}

// ---------------------------------------------------------------- talents
function requirementParts(req) { return typeof req === "object" ? { id: req.id, qty: req.qty || 1 } : { id: req, qty: 1 }; }
function treePoints(t) { return t.talents.reduce((a, z) => a + (points[z.id] || 0), 0); }
function pointsBefore(t, row, subtractId = null) { return t.talents.filter(z => z.row < row).reduce((a, z) => a + (points[z.id] || 0) - (String(z.id) === String(subtractId) ? 1 : 0), 0); }
function canAdd(t, talent) { const total = Object.values(points).reduce((a, b) => a + b, 0); if (total >= 51 || pointsBefore(t, talent.row) < talent.row * 5 || (points[talent.id] || 0) >= talent.ranks.length) return false; return (talent.requires || []).every(raw => { const req = requirementParts(raw); return (points[req.id] || 0) >= req.qty; }); }
function canRemove(t, talent) { const current = points[talent.id] || 0; if (!current) return false; const next = current - 1; for (const child of t.talents) { if (!(points[child.id] || 0)) continue; if (pointsBefore(t, child.row, talent.id) < child.row * 5) return false; for (const raw of child.requires || []) { const req = requirementParts(raw); if (String(req.id) === String(talent.id) && next < req.qty) return false; } } return true; }
function autoTalents() { points = {}; for (const [id, rank] of Object.entries(spec.default_talents || {})) points[id] = rank; renderTalents(); }
function treeLinks(t) { const lines = []; for (const child of t.talents) for (const raw of child.requires || []) { const req = requirementParts(raw), parent = t.talents.find(x => String(x.id) === String(req.id)); if (parent) lines.push(`<line x1="${30 + parent.col * 60}" y1="${30 + parent.row * 60}" x2="${30 + child.col * 60}" y2="${30 + child.row * 60}" class="${(points[parent.id] || 0) >= req.qty ? "active" : ""}"/>`); } return `<svg class="generic-links" viewBox="0 0 240 420">${lines.join("")}</svg>`; }
function showTalentInfo(x) { const rank = points[x.id] || 0, max = x.ranks.length, current = rank ? x.descriptions[String(rank)] : "No ranks learned.", next = rank < max ? `Next rank: ${x.descriptions[String(rank + 1)]}` : "Maximum rank learned."; $("talentInfo").innerHTML = `<strong>${x.name}</strong><span>Rank ${rank}/${max}</span><p>${current}</p><p class="next-rank">${next}</p>`; }
function renderTalents() {
  const total = Object.values(points).reduce((a, b) => a + b, 0); $("talentCounter").textContent = `${total} / 51 points`; $("quickTalents").textContent = `${total} / 51`;
  $("talentTrees").innerHTML = trees.map(t => `<article class="generic-tree"><header><strong>${t.name}</strong><span>${treePoints(t)} points</span></header><div class="generic-board">${treeLinks(t)}${t.talents.map(x => { const p = points[x.id] || 0, max = x.ranks.length, ok = canAdd(t, x); return `<button class="generic-talent talent-row-${x.row} talent-col-${x.col} ${p ? "learned" : ""} ${p === max ? "maxed" : ""} ${ok ? "available" : ""}" data-tree="${t.id}" data-id="${x.id}" aria-label="${x.name}, rank ${p} of ${max}" title="${x.name}"><img src="/talent-icons/${x.icon}.jpg" alt=""><span>${p}/${max}</span></button>`; }).join("")}</div></article>`).join("");
  document.querySelectorAll(".generic-talent").forEach(b => { const t = trees.find(x => String(x.id) === b.dataset.tree), x = t.talents.find(x => String(x.id) === b.dataset.id); b.style.left = `${8 + x.col * 60}px`; b.style.top = `${8 + x.row * 60}px`; b.onclick = e => { e.preventDefault(); if (e.shiftKey) { if (canRemove(t, x)) points[x.id]--; renderTalents(); } else if ((points[x.id] || 0) < x.ranks.length && canAdd(t, x)) { points[x.id] = (points[x.id] || 0) + 1; renderTalents(); } }; b.oncontextmenu = e => { e.preventDefault(); if (canRemove(t, x)) { points[x.id]--; renderTalents(); } }; b.onmousemove = e => { showTalentInfo(x); const rank = Math.max(1, points[x.id] || 1); tooltip(`<h3>${x.name}</h3><p>Rank ${points[x.id] || 0}/${x.ranks.length}</p><p>${x.descriptions[String(rank)] || ""}</p><p class="tooltip-meta">Tier ${x.row + 1}${DOT}${x.row * 5} points required</p>`, e); }; b.onmouseleave = hideTip; });
}

// ---------------------------------------------------------------- results
function metricCard(label, value, primary = false) { return `<article class="metric ${primary ? "primary-metric" : ""}"><div class="label">${label}</div><div class="value">${value}</div></article>`; }
function renderResultView(view) {
  if (!lastResult) return; document.querySelectorAll(".result-tab").forEach(x => x.classList.toggle("active", x.dataset.result === view)); const x = lastResult, detail = $("resultDetail");
  if (view === "damage") { const max = Math.max(1, ...Object.values(x.ability_dps)); detail.innerHTML = '<h3>Damage</h3><div class="result-table-wrap"><table class="result-breakdown"><thead><tr><th>Ability</th><th>Contribution</th><th>DPS</th><th>Total</th><th>Casts</th><th>Hits</th><th>Crits</th><th>Misses</th><th>Dodged/Parried</th><th>Glances</th></tr></thead><tbody>' + Object.entries(x.ability_dps).sort((a, b) => b[1] - a[1]).map(([n, v]) => { const r = x.ability_stats[n]; return `<tr><td>${n}</td><td><div class="share-track"><div class="share-fill" data-bar-width="${100 * v / max}"></div></div></td><td>${fmt(v)}</td><td>${fmt(x.ability_damage?.[n] ?? r.damage, 0)}</td><td>${fmt(r.casts, 1)}</td><td>${fmt(r.hits, 1)}</td><td>${fmt(r.crits, 1)}</td><td>${fmt(r.misses, 1)}</td><td>${fmt(r.dodges || 0, 1)}</td><td>${fmt(r.glances || 0, 1)}</td></tr>`; }).join("") + "</tbody></table></div>"; applyBarWidths(detail); return; }
  if (view === "threat") { const max = Math.max(1, ...Object.values(x.threat_by_ability)); detail.innerHTML = "<h3>Threat</h3>" + Object.entries(x.threat_by_ability).sort((a, b) => b[1] - a[1]).filter(([, v]) => v > 0).map(([n, v]) => `<div class="result-row"><span>${n}</span><div class="share-track"><div class="share-fill" data-bar-width="${100 * v / max}"></div></div><strong>${fmt(v)} TPS</strong></div>`).join(""); applyBarWidths(detail); return; }
  if (view === "taken") {
    const tank = x.spec.role === "tank", m = x.metrics, e = x.incoming;
    detail.innerHTML = `<h3>Damage Taken & Survival</h3>`;
    if (!tank) { detail.innerHTML += "<p>No incoming attacks are scheduled for a DPS assignment.</p>"; return; }
    detail.innerHTML += `<div class="metrics">${metricCard("DAMAGE / ALIVE SEC", fmt(m.alive_dtps.mean), true)}${metricCard("SURVIVED FIGHT", fmt(m.survival_fraction * 100, 1) + "%")}${metricCard("TIME ALIVE", fmt(m.alive_seconds.mean) + " s")}${metricCard("PEAK 3-SECOND DAMAGE", fmt(m.peak_3s_damage.mean))}${metricCard("TOTAL DAMAGE TAKEN", fmt(m.taken.mean))}${metricCard("EFFECTIVE HEALING", fmt(m.effective_healing.mean))}${metricCard("OVERHEALING", fmt(m.overhealing.mean))}${metricCard("ENDING HEALTH", fmt(m.ending_health.mean))}</div><h4>Incoming damage by outcome</h4>`;
    detail.innerHTML += Object.entries(x.taken_dtps || {}).map(([k, v]) => `<div class="result-row"><span>${k}</span><div class="share-track"><div class="share-fill" data-bar-width="${100 * v / Math.max(1, m.dtps.mean)}"></div></div><strong>${fmt(v)} DTPS</strong></div>`).join("");
    detail.innerHTML += `<p>${e.enemies} level-63 attacker(s), ${fmt(e.enemy_damage_min, 0)}–${fmt(e.enemy_damage_max, 0)} raw physical damage every ${e.enemy_swing} s before attack-speed debuffs. Healing: ${fmt(e.heal_amount, 0)} every ${e.heal_interval} s. Change these in Encounter.</p><p>Survival is the fraction of runs alive at fight end under this healing scenario. Time alive is capped at encounter length. Outcome DTPS divides by full fight duration (${fmt(m.dtps.mean)} total); damage/alive-second divides by time alive. Attacks and healing stop at death. A low full-fight DTPS caused by early death is not better mitigation.</p>`;
    applyBarWidths(detail); return;
  }
  if (view === "buffs" || view === "debuffs") {
    const rows = view === "buffs" ? x.buff_uptimes : x.debuff_uptimes;
    let html = `<h3>${view === "buffs" ? "Buff uptime" : "Debuff uptime"}</h3>` + Object.entries(rows).sort((a, b) => b[1] - a[1]).map(([n, v]) => `<div class="result-row"><span>${n.replaceAll("_", " ")}</span><div class="share-track"><div class="share-fill" data-bar-width="${v * 100}"></div></div><strong>${fmt(v * 100, 0)}%</strong></div>`).join("");
    if (view === "buffs" && x.buff_procs_per_min) {
      const procOnly = Object.entries(x.buff_procs_per_min).filter(([n]) => !(rows[n] > 0));
      if (procOnly.length) {
        const maxRate = Math.max(1, ...procOnly.map(([, v]) => v));
        html += `<h3>Procs (no sustained uptime)</h3><p style="font-size:.75rem;color:var(--muted);margin:0 0 10px">Instant procs consumed by the next cast (e.g. Nightfall) don't hold a timed buff, so they're shown as activations/min instead of uptime %.</p>` +
          procOnly.sort((a, b) => b[1] - a[1]).map(([n, v]) => `<div class="result-row"><span>${n.replaceAll("_", " ")}</span><div class="share-track"><div class="share-fill" data-bar-width="${100 * v / maxRate}"></div></div><strong>${fmt(v, 1)}/min</strong></div>`).join("");
      }
    }
    detail.innerHTML = html; applyBarWidths(detail); return;
  }
  if (view === "resources") { detail.innerHTML = `<h3>${x.resource.name}</h3><div class="metrics">${metricCard("MAXIMUM", fmt(x.resource.maximum, 0))}${metricCard("MEAN AT END", fmt(x.resource.mean_end, 1))}${metricCard("STARVED TIME", fmt(x.resource.starved_fraction * 100, 1) + "%")}${metricCard("FIRST EMPTY", x.resource.first_out_of_mana == null ? "never" : fmt(x.resource.first_out_of_mana, 0) + " s")}</div><p>Mana regenerates in 2 s ticks (mp5 always; Spirit only outside the five-second rule or at the talent fraction). Energy ticks 20 every 2 s. Rage comes from landed white damage (7.5 / 230.6 per point) and damage taken.</p>`; return; }
  detail.innerHTML = '<h3>First-iteration event log</h3><div class="table-wrap"><table><thead><tr><th>Time</th><th>Event</th><th>Outcome</th><th>Amount</th><th>Resource</th></tr></thead><tbody>' + x.log.map(r => `<tr><td>${r.time.toFixed(2)}</td><td>${r.event}</td><td>${r.outcome}</td><td>${fmt(r.amount, 1)}</td><td>${fmt(r.resource, 1)}</td></tr>`).join("") + "</tbody></table></div>";
}
function renderConfiguration(x) {
  const c = x.configuration, g = c.gear_stats || {};
  const stat = (k, d = 0) => g[k] == null ? "?" : fmt(g[k], d);
  const statsLine = spec.style === "spell" ? `Spell power ${stat("spellPower")}${DOT}spell hit ${stat("spellHit")}%${DOT}spell crit ${stat("spellCrit")}%${DOT}mana ${stat("mana")}${DOT}spirit ${stat("spirit")}${DOT}mp5 ${stat("mp5")}` : spec.style === "ranged" ? `Ranged AP ${stat("rangedAttackPower")}${DOT}ranged hit ${stat("rangedHit")}%${DOT}ranged crit ${stat("rangedCrit")}%${DOT}agility ${stat("agility")}${DOT}mana ${stat("mana")}` : `Attack power ${stat("attackPower")}${DOT}hit ${stat("meleeHit")}%${DOT}crit ${stat("meleeCrit")}%${DOT}strength ${stat("strength")}${DOT}agility ${stat("agility")}${spec.role === "tank" ? `${DOT}armor ${stat("armor")}${DOT}dodge ${stat("dodge")}%${DOT}parry ${stat("parry")}%${DOT}block ${stat("block")}%${DOT}defense ${stat("defense")}${DOT}health ${stat("health")}` : ""}`;
  $("configuration").innerHTML = `<p><strong>Race:</strong> ${c.race}${DOT}${c.racial || ""}</p><p><strong>Boss:</strong> level 63${DOT}${fmt(c.boss_armor, 0)} armor after debuffs${DOT}type ${c.boss_type}${DOT}${c.targets} target(s)</p><p><strong>Character:</strong> ${statsLine}</p><p><strong>Weapons:</strong> ${(c.weapons || []).map(w => `${w.slot}: ${w.name} (${w.damage?.[0]}-${w.damage?.[1]}, ${Number(w.speed).toFixed(2)} speed, skill ${w.skill})`).join(DOT)}</p>${c.pet ? `<p><strong>Pet:</strong> ${c.pet.family.replaceAll("_", " ")}${c.pet.attack_speed ? `${DOT}${Number(c.pet.attack_speed).toFixed(1)} speed` : ""}${DOT}${(c.pet.uptime * 100).toFixed(0)}% uptime${DOT}${(c.pet.abilities || []).join(", ")}</p>` : ""}<p><strong>Enchants:</strong> ${c.enchants?.length || 0} applied, ${c.rejected_enchants?.length || 0} rejected. <strong>Item effects:</strong> ${c.item_effects?.applied?.length || 0} modeled, ${c.item_effects?.unresolved?.length || 0} unresolved${c.item_effects?.unresolved?.length ? ` (${c.item_effects.unresolved.map(u => `${u.item}: ${u.effect}`).join("; ")})` : ""}. <strong>Set bonuses:</strong> ${c.set_bonuses?.active?.length ? c.set_bonuses.active.map(b => `${b.set} (${b.required})${b.modeled ? " - modeled" : " - unresolved"}`).join(", ") : "none"}.</p><p><strong>Talents:</strong> ${c.talent_points} points${DOT}${Object.keys(c.talent_effects || {}).length} modeled talent effects active.</p>${c.notes?.length ? `<p><strong>Provisional values:</strong> ${c.notes.join(" ")}</p>` : ""}<p><strong>Model:</strong> ${x.model_status}</p>`;
}

// ---------------------------------------------------------------- run
async function run() {
  try {
    $("error").textContent = ""; $("progress").className = "running";
    const chosen = kind => [...document.querySelectorAll(`[data-kind=${kind}]:checked`)].map(x => x.dataset.key);
    const payload = { ...tankEncounter(), spec: spec.id, duration: +$("duration").value, duration_variance: +$("durationVariance").value, iterations: +$("iterations").value, seed: data.defaults.seed, race: $("race").value, gear: profile.gear.map(x => x.id), gear_slots: profile.gear.map(x => ({ slot: x.slot, id: x.id })), enchants: profile.gear.filter(x => x.enchant).map(x => ({ slot: enchantSlot(x.slot), id: x.enchant.id })), talents: points, armor: +$("armor").value, targets: +$("targets").value, boss_type: $("bossType").value, buffs: chosen("buffs"), debuffs: chosen("debuffs"), consumables: chosen("consumables"), racial_enabled: !!document.querySelector("[data-racial]:checked"), rotation_enabled: [...document.querySelectorAll("[data-rotation]:checked")].map(x => x.dataset.rotation), pet_family: $("petFamily")?.value || "cat", pet_attack_speed: +($("petAttackSpeed")?.value || 2), pet_uptime: +($("petUptime")?.value || 100) / 100, pet_abilities: [...document.querySelectorAll("[data-pet-ability]:checked")].map(x => x.dataset.petAbility) };
    const bar = $("progress"); bar.style.width = "0%";
    const x = await ForeverSim.simulate("spec", payload, payload.iterations, (done, total) => { bar.style.width = `${Math.round(100 * done / total)}%`; });
    if (x.error) throw new Error(x.error);
    lastResult = x;
    const ci = m => m.mean_95ci_half_width == null ? "" : `<small>95% CI ${PM} ${fmt(m.mean_95ci_half_width, 2)}</small>`;
    $("quickDps").textContent = fmt(x.metrics.dps.mean); $("quickTps").textContent = fmt(x.metrics.tps.mean);
    $("metrics").innerHTML = metricCard("DPS", `${fmt(x.metrics.dps.mean)}${ci(x.metrics.dps)}`, true) + metricCard("TPS", `${fmt(x.metrics.tps.mean)}${ci(x.metrics.tps)}`) + (x.spec.role === "tank" ? metricCard("DAMAGE / ALIVE SEC", `${fmt(x.metrics.alive_dtps.mean)}${ci(x.metrics.alive_dtps)}`) + metricCard("SURVIVAL", `${fmt((x.metrics.survival_fraction ?? 1) * 100, 0)}%`) : metricCard("STARVED", `${fmt(x.resource.starved_fraction * 100, 1)}%`));
    renderResultView("damage"); renderConfiguration(x);
    $("resultLabel").textContent = `${payload.iterations.toLocaleString()} iterations${DOT}${payload.duration}s Patchwerk${DOT}${x.configuration.race}${DOT}${payload.boss_type === "none" ? "unspecified creature type" : payload.boss_type}`;
    showTab("results");
  } catch (e) { $("error").textContent = e.message; } finally { $("progress").className = ""; $("progress").style.width = ""; }
}

const incomingDefaults = { enemies: 1, enemy_damage_min: 2700, enemy_damage_max: 3300, enemy_swing: 2, heal_amount: 2500, heal_interval: 2 };
function tankEncounter() { return Object.fromEntries(Object.entries(incomingDefaults).map(([key, value]) => [key, document.getElementById(`incoming-${key}`) ? Number(document.getElementById(`incoming-${key}`).value) : value])); }
function renderTankEncounter() {
  if (spec.role !== "tank") return;
  const card = document.createElement("div"); card.className = "settings-card";
  card.innerHTML = '<h3>Incoming damage & healing</h3><p>Physical melee scenario; healing is a fixed pulse, not a healer simulation. Set healing to 0 to measure unhealed survival. Incoming attackers are independent of outgoing targets.</p><div class="form-grid"></div>';
  const labels = { enemies: "Incoming attackers", enemy_damage_min: "Raw hit minimum", enemy_damage_max: "Raw hit maximum", enemy_swing: "Attack interval (seconds)", heal_amount: "Healing per pulse", heal_interval: "Healing interval (seconds)" };
  for (const [key, value] of Object.entries(incomingDefaults)) {
    const interval = key.endsWith("interval") || key === "enemy_swing";
    card.querySelector(".form-grid").insertAdjacentHTML("beforeend", `<div class="field"><label for="incoming-${key}">${labels[key]}</label><input id="incoming-${key}" type="number" min="${interval ? .2 : key === "enemies" ? 1 : 0}" max="${interval ? 60 : key === "enemies" ? 10 : 1000000}" step="${interval ? .1 : 1}" value="${value}"></div>`);
  }
  $("view-encounter").append(card);
}

// ---------------------------------------------------------------- init
async function init() {
  const [bootstrap, itemPayload, wsPayload] = await Promise.all([fetch("/data/spec-bootstrap.json?v=794920e").then(r => r.json()), fetch("/data/items.json?v=794920e").then(r => r.json()), fetch("/data/wowsims-import.json?v=794920e").then(r => r.json()).catch(() => null)]);
  wsData = wsPayload;
  ForeverSim.warm();
  data = bootstrap; catalogItems = itemPayload.items; spec = data.specs.find(x => x.id === specId);
  baseProfile = structuredClone(data.gear.profiles[specId]); if (!spec || !baseProfile) { location.href = "/"; return; }
  baseProfile.gear = baseProfile.gear.map(row => { const full = catalogItems.find(x => x.id === row.id); return full ? { ...row, ...full, slot: row.slot } : row; });
  profile = structuredClone(baseProfile);
  document.body.dataset.class = spec.class_name.toLowerCase(); document.body.dataset.spec = spec.id;
  $("duration").value = data.defaults.duration; $("iterations").value = data.defaults.iterations; $("quickFight").textContent = `${data.defaults.duration}s`; $("armor").value = data.defaults.armor;
  const query = new URLSearchParams(location.search);
  $("targets").value = Math.max(1,Math.min(10,Number(query.get("targets"))||data.defaults.targets));
  if(query.get("benchmark")==="1"){data.defaults.seed=data.defaults.benchmark_seed;$("iterations").value=data.defaults.benchmark_iterations;}
  const raceNames = spec.races || ["Human"]; $("race").innerHTML = raceNames.map(name => `<option>${name}</option>`).join("");
  const requestedRace = new URLSearchParams(location.search).get("race"); $("race").value = raceNames.includes(requestedRace) ? requestedRace : (raceNames.includes("Human") ? "Human" : raceNames[0]);
  $("race").onchange = () => { renderRace(); renderRotation(); renderSpecCards(); swapFactionGear(); }; renderRace(); renderSpecCards(); renderTankEncounter();
  trees = data.talents.classes[spec.class_name.toLowerCase()]; profile.gear.forEach(x => x.enchant = defaultEnchant(x));
  $("sideSpec").textContent = `${spec.class_name}${DOT}${spec.name}`; $("talentHeading").textContent = `${spec.class_name} talents`; $("className").textContent = spec.class_name.toUpperCase(); $("specName").textContent = spec.name; $("gearSource").textContent = profile.source_label || ""; $("serverDot").className = "online";
  renderGear(); renderOptions("buffs", data.settings.raid_buffs, "buffs"); renderOptions("debuffs", data.settings.debuffs, "debuffs"); renderOptions("consumables", data.consumables.items, "consumables"); renderRotation(); renderPetSettings();
  if (["Hunter", "Warlock"].includes(spec.class_name)) $("petFamily").onchange = renderPetSettings;
  autoTalents();
}
document.addEventListener("error", e => { if (e.target && e.target.tagName === "IMG") e.target.style.visibility = "hidden"; }, true);
document.querySelectorAll(".result-tab").forEach(x => x.onclick = () => renderResultView(x.dataset.result));
document.querySelectorAll(".main-tab").forEach(x => x.onclick = () => showTab(x.dataset.tab));
$("run").onclick = run;
$("resetTalents").onclick = () => { points = {}; renderTalents(); $("talentInfo").textContent = "Talents cleared. Choose talents from any tree, or Reset to reload the default build."; };
$("duration").oninput = () => $("quickFight").textContent = $("duration").value + "s";
$("itemSearch").oninput = renderPicker;
$("enchantSelect").onchange = () => { const it = profile.gear[pickerIndex], rows = enchantRows(it); it.enchant = rows.find(x => x.id === $("enchantSelect").value) || null; renderGear(); };
$("clearItem").onclick = () => { const slot = profile.gear[pickerIndex].slot; profile.gear[pickerIndex] = { slot, id: 0, name: "Empty", icon: "inv_misc_questionmark", quality: "Common", itemLevel: 0, stats: {}, effects: [] }; $("itemDialog").close(); renderGear(); };
$("itemDialog").addEventListener("close", () => { hideTip(); document.body.appendChild($("tooltip")); });
$("resetProfile").onclick = () => { profile = structuredClone(baseProfile); profile.gear.forEach(x => x.enchant = defaultEnchant(x)); autoTalents(); renderGear(); renderOptions("buffs", data.settings.raid_buffs, "buffs"); renderOptions("consumables", data.consumables.items, "consumables"); showTab("gear"); };
// Alliance/Horde-only gear: swap to the other faction's identical twin, or clear the slot.
function swapFactionGear() {
  const faction = raceFaction(), cleared = [];
  profile.gear.forEach((row, i) => {
    if (!row.faction || row.faction === faction) return;
    const twin = catalogItems.find(x => x.id === row.factionTwin);
    if (twin) profile.gear[i] = { ...twin, itemSlot: twin.slot, slot: row.slot, enchant: row.enchant };
    else { cleared.push(row.name); profile.gear[i] = { slot: row.slot, id: 0, name: "Empty", icon: "inv_misc_questionmark", quality: "Common", itemLevel: 0, stats: {}, effects: [] }; }
  });
  $("error").textContent = cleared.length ? `Removed ${faction === "Alliance" ? "Horde" : "Alliance"}-only gear with no ${faction} equivalent: ${cleared.join(", ")}.` : "";
  renderGear();
}
$("foreverBisProfile").onclick = () => {
  const bis = data.forever_bis?.profiles?.[specId];
  if (!bis) { $("error").textContent = "No Forever BiS set is available for this spec yet."; return; }
  const hydrated = structuredClone(bis);
  const uiSlot = row => Object.keys(slotKeys).find(label => slotKeys[label][0] === row.gear_slot || (row.gear_slot === "finger2" && label === "Finger 2") || (row.gear_slot === "trinket2" && label === "Trinket 2") || (row.gear_slot === "relic" && label === "Ranged / Relic")) || row.slot;
  hydrated.gear = hydrated.gear.map(row => { const full = catalogItems.find(x => x.id === row.id), slot = uiSlot(row); return full ? { ...row, ...full, itemSlot: full.slot, slot } : { ...row, slot }; });
  profile = hydrated; profile.gear.forEach(x => x.enchant = defaultEnchant(x));
  $("gearSource").textContent = profile.source_label || "Assumed Forever BiS";
  if (bis.race && [...$("race").options].some(o => o.value === bis.race) && $("race").value !== bis.race) { $("race").value = bis.race; renderRace(); renderRotation(); renderSpecCards(); }
  swapFactionGear();
  renderGear(); showTab("gear");
};
$("exportProfile").onclick = () => { const output = { ruleset: "World of Warcraft Forever prototype", spec: spec.id, race: $("race").value, gear: Object.fromEntries(profile.gear.map(x => [x.slot, { item_id: x.id, enchant_id: x.enchant?.id || null }])), talents: points, encounter: { ...tankEncounter(), duration: +$("duration").value, boss_armor: +$("armor").value, targets: +$("targets").value, boss_type: $("bossType").value } }; const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(output, null, 2)], { type: "application/json" })); a.download = `${spec.id}-forever-profile.json`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); };

// ---------------------------------------------------------------- WoWSims Exporter import
function applyWowSimsImport(text) {
  if (!wsData) throw new Error("Import data failed to load; reload the page and try again.");
  const parsed = WowSimsImport.parseExport(text);
  if (WowSimsImport.norm(parsed.className) !== WowSimsImport.norm(spec.class_name)) {
    throw new Error(`That export is for a ${parsed.className}. Open a ${spec.class_name} spec page to import it.`);
  }
  const notes = [];
  const raceNames = spec.races || ["Human"];
  const raceMatch = raceNames.find(r => WowSimsImport.norm(r) === WowSimsImport.norm(parsed.raceName));
  if (raceMatch) { $("race").value = raceMatch; renderRace(); }
  else notes.push(`Race "${parsed.raceName}" isn't in the Forever roster for ${spec.class_name}; kept ${$("race").value}.`);
  const foreverTrees = data.talents.classes[spec.class_name.toLowerCase()] || [];
  const { positions, error } = WowSimsImport.decodeTalentPositions(wsData, spec.class_name, parsed.talentsStr);
  if (error) throw new Error(error);
  const { byId, unmatched, primaryTree } = WowSimsImport.matchForeverTalents(foreverTrees, positions);
  points = byId;
  if (unmatched.length) notes.push(`${unmatched.length} talent point(s) couldn't be matched to a Forever talent and were skipped.`);
  if (primaryTree && WowSimsImport.norm(primaryTree) !== WowSimsImport.norm(spec.tree)) notes.push(`Most of the imported points are in ${primaryTree}, not ${spec.tree} — you may want the ${primaryTree} spec page instead.`);
  renderTalents();
  let equipped = 0, itemsMissing = 0;
  profile.gear.forEach(row => {
    const imp = WowSimsImport.gearForLabel(parsed.gearItems, row.slot);
    if (!imp) return;
    const full = catalogItems.find(x => x.id === imp.id);
    if (!full) { itemsMissing++; return; }
    Object.assign(row, { ...full, slot: row.slot, enchant: null });
    equipped++;
    if (row.slot === "Main Hand" && full.slot === "Two-Hand") { const oh = profile.gear.find(x => x.slot === "Off Hand"); if (oh) Object.assign(oh, { slot: "Off Hand", id: 0, name: "Empty (two-hand equipped)", icon: "inv_misc_questionmark", quality: "Common", itemLevel: 0, stats: {}, effects: [] }); }
    const rows = enchantRows(row);
    const match = WowSimsImport.resolveEnchant(wsData, imp.enchant, enchantSlot(row.slot));
    row.enchant = (match && rows.find(x => x.id === match.id)) || null;
  });
  if (itemsMissing) notes.push(`${itemsMissing} equipped item(s) aren't in this catalog (wrong phase or not carried) and were left as-is.`);
  renderGear();
  return { equipped, notes };
}
$("importButton").onclick = () => { $("importStatus").textContent = ""; $("importStatus").className = "import-status"; $("importText").value = ""; $("importDialog").showModal(); $("importText").focus(); };
$("importApply").onclick = () => {
  const status = $("importStatus");
  try {
    const { equipped, notes } = applyWowSimsImport($("importText").value);
    status.textContent = `Imported ${equipped} item(s), race and talents.${notes.length ? String.fromCharCode(10) + notes.join(String.fromCharCode(10)) : ""}`;
    status.className = "import-status ok";
    setTimeout(() => $("importDialog").close(), notes.length ? 2600 : 1200);
  } catch (e) { status.textContent = e.message; status.className = "import-status error"; }
};

init().catch(e => { $("error").textContent = e.message; });
