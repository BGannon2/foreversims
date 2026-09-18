// "Changes" button + dialog: a plain-language summary of what World of Warcraft: Forever
// changed from regular Classic, per class. Injected next to the Feedback button.
(function () {
  const SECTIONS = [
    { title: "Character Creation", items: [
      "Undead can now be Paladins — the first Horde-side Paladin combination.",
      "Dwarves can now be Shaman — the first Alliance-side Shaman combination.",
      "Humans can now be Hunters.",
      "Gnomes can now be Priests.",
      "Orcs can now be Mages.",
      "Trolls can now be Warlocks.",
      "New race: Skyborne, playable on both factions and available to Warrior, Hunter, Rogue, and Druid — the first faction-flexible Druid combination. Skyborne Mage is Alliance-only and Skyborne Shaman is Horde-only.",
    ]},
    { title: "Racials", items: [
      "New active: Elune's Light (Night Elf) — grants a burst of critical strike chance.",
      "New active: Eureka! (Gnome) — your next few spells or abilities deal bonus damage.",
      "New passive: Touch of the Grave (Undead) — a chance on spells and attacks to drain health from the target.",
      "Blood Fury (Orc) now also boosts spell power, in addition to attack power.",
      "Endurance (Tauren) now also grants bonus hit chance, in addition to bonus health.",
      "New race: Skyborne — Wind Blessed (haste) and Elemental Insight (bonus damage to Elementals) on both factions, plus a faction-specific racial: Skysight (Horde, bonus run speed) or Read Ley Line (Alliance, greatly increased health/mana regeneration).",
    ]},
    { title: "Gear", items: [
      "Avenger's Battlegear (Paladin tier set): 3-piece now increases Judgement duration by 20%; 5-piece grants spell power.",
      "Lightforge Armor and Soulforge Armor (Paladin dungeon sets): set bonuses reworked, including new proc and resource-return effects.",
    ]},
    { title: "Paladin — Protection", items: [
      "Righteous Fury grants +90% Holy threat (Classic Righteous Fury is a smaller bonus).",
      "New seal: Seal of Fury. Melee swings deal bonus Holy damage, and while a shield is equipped each landed swing also grants a small self-absorb shield.",
      "Judgement of Fury is also a taunt.",
      "Judging no longer consumes your active seal, unlike Classic.",
    ]},
    { title: "Paladin — Retribution", items: [
      "Seal of Righteousness's swing damage and Judgement now scale with spell power instead of Classic's flat values.",
      "Seal of Command's Judgement now scales with spell power instead of Classic's flat value.",
      "Improved Seals boosts both Seal and Judgement damage.",
      "New talent: Sacred Arbiter — increases Holy Strike damage and refreshes Judgement effects on the target.",
    ]},
    { title: "Warrior", items: [
      "Weaponmaster: the mace/staff armor-ignore bonus scales per rank, and now also grants an axe/polearm critical strike chance bonus per rank.",
      "Shield Slam's damage and threat have been retuned.",
      "New talent: Spearing Strike (Arms) — deals bonus damage against Giants and Dragonkin.",
      "Mortal Strike, Bloodthirst and Death Wish have been retuned.",
    ]},
    { title: "Priest", items: [
      "Improved Shadow Word: Pain now grants its bonus DoT tick per rank (+1 at rank 1, +2 at rank 2) instead of all at once.",
    ]},
    { title: "Shaman", items: [
      "Lightning Bolt cast time reduced to 2.5 sec (Classic: 3.0 sec), and its damage has been retuned.",
      "Chain Lightning cast time reduced to 2.0 sec (Classic: 2.5 sec), and its damage has been retuned.",
      "Stormstrike cooldown reduced to 8 sec (Classic: 20 sec).",
      "New talent: Rage of the Farseer (Enhancement) — a personal cooldown granting bonus melee and spell haste.",
      "New ability: Lava Burst — a guaranteed-crit-adjacent nuke that deals bonus damage against a target affected by Flame Shock.",
      "New talent: Maelstrom Weapon — landed melee hits build stacks that reduce Lightning Bolt's cast time and mana cost, making it instant and free at max stacks.",
    ]},
    { title: "Warlock", items: [
      "Shadow and Flame gives Conflagrate a chance to preserve Immolate instead of always consuming it.",
      "New ability: Incinerate replaces Shadow Bolt as Destruction's filler spell, dealing bonus damage against a target affected by Immolate.",
    ]},
    { title: "Hunter", items: [
      "Aimed Shot cast time reduced to 2.0 sec at rank 3 (Classic: 3.0 sec).",
      "Multi-Shot cooldown reduced to 6 sec (Classic: 10 sec), and no longer shares a cooldown with Aimed Shot.",
      "Survival has been rebuilt as a melee specialization, built around Mongoose Bite, Strider Kick, Raptor Strike and Lacerating Strikes.",
      "New talent: Summon Hawk (Beast Mastery) — calls a hawk for an initial strike followed by a continued assault on the target.",
    ]},
    { title: "Rogue", items: [
      "New ability: Mutilate (Assassination) — a dual-weapon builder that becomes the spec's opener, dealing bonus damage while Deadly Poison is ticking on the target.",
      "New talent: Restless Blades (Combat) — damaging finishers reduce the remaining cooldown on Adrenaline Rush and Blade Flurry.",
      "New talent: Thousand Cuts (Subtlety) — Rupture ticks build stacks that discount the Energy cost of your next Hemorrhage or Backstab.",
      "Hemorrhage has been retuned.",
    ]},
    { title: "Druid", items: [
      "New talent: Eclipse (Balance) — Wrath casts reduce the cast time of your next 2 Starfire casts, stacking charges.",
      "New ability: Mangle (Feral) — a strong direct hit usable in Cat or Bear Form.",
      "New talent: Berserk (Feral) — a cooldown that lets Mangle strike multiple targets, removes its cooldown, and boosts combo-point-generator critical chance.",
      "New talent: Primal Fury (Feral) — critical strikes have a chance to grant bonus Rage in Bear Form or an extra combo point in Cat Form.",
      "New talent: King of the Jungle (Feral) — Tiger's Fury also grants instant Energy.",
    ]},
    { title: "Mage", items: [
      "New talent: Arcane Blast (Arcane) — each cast stacks a self-buff that increases the damage of your other spells, at increasing mana cost per stack.",
      "New talent: Missile Barrage (Arcane) — casting Arcane Blast, Fireball or Frostbolt has a chance to make your next Arcane Missiles instant, free, and channel at double speed.",
      "New talent: Hot Streak (Fire) — non-periodic critical strikes build stacks that reduce Pyroblast's cast time.",
      "New ability: Ice Lance (Frost) — deals bonus damage against a Frozen target.",
      "New talent: Fingers of Frost (Frost) — Frostbolt hits have a chance to grant charges that let your next Ice Lance(s) treat the target as Frozen.",
      "Shatter (Frost) now adds a critical strike chance bonus to Ice Lance while a Fingers of Frost charge is available.",
    ]},
  ];

  function build() {
    const button = document.createElement("button");
    button.type = "button"; button.className = "changes-button"; button.textContent = "Changes";
    button.setAttribute("aria-haspopup", "dialog");
    const dialog = document.createElement("dialog");
    dialog.className = "changes-dialog";
    const body = SECTIONS.map(s => `<h3>${s.title}</h3><ul>${s.items.map(i => `<li>${i}</li>`).join("")}</ul>`).join("");
    dialog.innerHTML = `
      <div class="changes-panel">
        <header><h2>What's different from Classic</h2><button type="button" class="changes-close" aria-label="Close">×</button></header>
        <div class="changes-body">${body}</div>
      </div>`;
    let tabs = document.getElementById("bottomTabs");
    if (!tabs) { tabs = document.createElement("div"); tabs.id = "bottomTabs"; tabs.className = "bottom-tabs"; document.body.append(tabs); }
    tabs.append(button); document.body.append(dialog);
    const close = () => dialog.close();
    button.addEventListener("click", () => dialog.showModal());
    dialog.querySelector(".changes-close").addEventListener("click", close);
    dialog.addEventListener("click", e => { if (e.target === dialog) close(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build); else build();
})();
