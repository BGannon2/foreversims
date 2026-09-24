"use strict";

const state = { boot:null, items:[], itemsById:new Map(), spec:"protection", profile:null, result:null, baseline:null, pickerSlot:null, resultView:"damage" };
const $ = (id) => document.getElementById(id);
const clone = (value) => JSON.parse(JSON.stringify(value));

const fieldSets = {
  character:[
    ["character.health","Base health","",1],["character.mana","Base mana pool","",1],["character.base_mana","Base mana (Judgement cost basis)","",1],
    ["character.strength","Base Strength","",1],["character.agility","Base Agility","",1],["character.stamina","Base Stamina","",1],["character.intellect","Base Intellect","",1],["character.attack_power","Base Attack Power","",1],
    ["character.spirit","Spirit","",1],["character.mana_per_second","Extra mana regeneration","per second",.1],["character.weapon_min","Weapon damage — minimum","",1],
    ["character.weapon_max","Weapon damage — maximum","",1],["character.weapon_speed","Weapon speed","seconds",.1],
    ["character.hit_chance","Melee hit probability","0–1",.01],["character.crit_chance","Melee crit probability","0–1",.01],
    ["character.spell_hit_chance","Spell hit probability","0–1",.01],["character.spell_crit_chance","Spell crit probability","0–1",.01],
    ["character.physical_mitigation","Physical mitigation","0–1",.01],["character.avoidance","Avoidance","0–1",.01],
    ["character.block_chance","Base block chance","0–1",.01],["character.block_value","Base block value","",1]
  ],
  encounter:[
    ["duration","Fight duration","seconds",1],["duration_variance","Duration variance","seconds",1],["seed","Random seed","",1],
    ["encounter.targets","Outgoing AoE targets","",1],
    ["encounter.enemies","Incoming attackers","",1],["encounter.enemy_damage_min","Raw enemy hit — minimum","",1],["encounter.enemy_damage_max","Raw enemy hit — maximum","",1],
    ["encounter.enemy_swing","Enemy swing interval","seconds",.1],["encounter.enemy_crit_chance","Enemy crit probability","0–1",.01],
    ["encounter.enemy_crit_multiplier","Enemy crit multiplier","",.1],["encounter.target_physical_mitigation","Target mitigation","0–1",.01],
    ["encounter.heal_amount","Healing per pulse","",1],["encounter.heal_interval","Healing interval","seconds",.1]
  ]
};
const gearLabels={head:"Head",neck:"Neck",shoulders:"Shoulders",back:"Back",chest:"Chest",wrist:"Wrist",main_hand:"Main Hand",off_hand:"Off Hand",hands:"Hands",waist:"Waist",legs:"Legs",feet:"Feet",finger1:"Finger 1",finger2:"Finger 2",trinket1:"Trinket 1",trinket2:"Trinket 2",relic:"Relic"};
const statLabels={strength:"Strength",agility:"Agility",stamina:"Stamina",intellect:"Intellect",spirit:"Spirit",armor:"Armor",attackPower:"Attack Power",spellPower:"Spell Power",holyPower:"Holy Power",healingPower:"Healing Power",meleeHit:"Melee Hit %",meleeCrit:"Melee Crit %",spellHit:"Spell Hit %",spellCrit:"Spell Crit %",block:"Block %",blockValue:"Block Value",defense:"Defense",dodge:"Dodge %",parry:"Parry %",mp5:"Mana / 5 sec",health:"Health",mana:"Mana"};

function atPath(obj,path){ return path.split(".").reduce((v,k)=>v[k],obj); }
function setPath(obj,path,value){ const keys=path.split("."); const last=keys.pop(); const target=keys.reduce((v,k)=>v[k],obj); target[last]=value; }
function labelize(key){ return key.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase()); }
function fmt(value,digits=1){ return Number(value).toLocaleString(undefined,{maximumFractionDigits:digits,minimumFractionDigits:digits}); }

function buildFields(){
  for(const [section, fields] of Object.entries(fieldSets)){
    const root=$(section+"Fields"); root.replaceChildren();
    for(const [path,label,hint,step] of fields){
      const wrap=document.createElement("div"); wrap.className="field";
      const lab=document.createElement("label"); lab.htmlFor="f-"+path; lab.textContent=hint?`${label} (${hint})`:label;
      const input=document.createElement("input"); input.type="number"; input.id="f-"+path; input.dataset.path=path; input.step=step; input.min="0";
      wrap.append(lab,input); root.append(wrap);
    }
    if(section==="character"){
      const raceWrap=document.createElement("div"); raceWrap.className="field";
      raceWrap.innerHTML='<label for="race">Available Forever Paladin races</label><select id="race"></select>';
      $("raceField").replaceChildren(raceWrap);
    }
    if(section==="encounter"){
      const typeWrap=document.createElement("div"); typeWrap.className="field";
      typeWrap.innerHTML='<label for="bossType">Boss creature type</label><select id="bossType"><option value="none">Unspecified</option><option value="beast">Beast</option><option value="demon">Demon</option><option value="dragonkin">Dragonkin</option><option value="elemental">Elemental</option><option value="giant">Giant</option><option value="humanoid">Humanoid</option><option value="mechanical">Mechanical</option><option value="undead">Undead</option></select>'; root.append(typeWrap);
      typeWrap.querySelector("select").addEventListener("change",syncCreatureAbilities);
      const wrap=document.createElement("div"); wrap.className="toggle-row field wide";
      wrap.innerHTML='<label for="incoming">Receive enemy attacks</label><input id="incoming" type="checkbox">'; root.append(wrap);
    }
  }
}

function addControls(rootId,items){
  const root=$(rootId); root.replaceChildren();
  for(const [path,label] of items){
    const value=atPath(state.profile,path); const row=document.createElement("div"); row.className=typeof value==="boolean"?"toggle-row":"field";
    const lab=document.createElement("label"); lab.textContent=labelize(label); const id="m-"+path; lab.htmlFor=id;
    const input=document.createElement("input"); input.id=id; input.dataset.path=path;
    if(typeof value==="boolean") input.type="checkbox"; else { input.type="number"; input.min="0"; input.step="0.01"; }
    row.append(lab,input); root.append(row);
  }
}

function positionInfoTooltip(event){
  const tip=$("infoTooltip"),pad=14,anchor=event.currentTarget?.getBoundingClientRect(); const cx=Number.isFinite(event.clientX)&&event.clientX?event.clientX:(anchor?.right||pad),cy=Number.isFinite(event.clientY)&&event.clientY?event.clientY:(anchor?.top||pad); let x=cx+16,y=cy+16;
  const box=tip.getBoundingClientRect(); if(x+box.width>innerWidth-pad)x=cx-box.width-16;if(y+box.height>innerHeight-pad)y=innerHeight-box.height-pad;
  tip.style.left=`${Math.max(pad,x)}px`;tip.style.top=`${Math.max(pad,y)}px`;
}
function hostTooltip(tip){const host=document.querySelector("dialog[open]")||document.body;if(tip.parentNode!==host)host.append(tip)}
function showInfoTooltip(html,event){const tip=$("infoTooltip");hostTooltip(tip);tip.innerHTML=html;tip.hidden=false;positionInfoTooltip(event)}
function hideInfoTooltip(){$("infoTooltip").hidden=true}

function buildConsumables(){
  const root=$("consumableFields");root.replaceChildren();
  const relevant=state.spec==="protection"?new Set(['flask_of_the_titans','elixir_of_the_mongoose','elixir_of_superior_defense','elixir_of_fortitude','greater_stoneshield_potion','smoked_desert_dumplings','rumsey_rum_black_label','mageblood_potion','juju_power','juju_might','brilliant_wizard_oil','gift_of_arthas']):new Set(['elixir_of_the_mongoose','smoked_desert_dumplings','mageblood_potion','juju_power','juju_might','brilliant_wizard_oil']);
  for(const item of state.boot.consumable_data.items.filter(item=>Object.hasOwn(state.profile.consumables,item.key)&&relevant.has(item.key))){
    const row=document.createElement("label");row.className="consume-card";row.htmlFor="m-consumables."+item.key;
    const input=document.createElement("input");input.type="checkbox";input.id=row.htmlFor;input.dataset.path="consumables."+item.key;
    input.addEventListener("change",()=>{if(!input.checked)return;root.querySelectorAll('input[type="checkbox"]')?.forEach(other=>{if(other!==input&&other.dataset.group===item.group)other.checked=false})});
    input.dataset.group=item.group;
    const img=document.createElement("img");img.src=`/consumable-icons/${item.icon}.jpg`;img.alt="";
    const copy=document.createElement("span");copy.innerHTML=`<strong>${item.name}</strong><small>${item.kind}</small>`;
    row.append(input,img,copy);
    const html=`<h3>${item.name}</h3><p>${item.description}</p><p class="tooltip-meta">${labelize(item.group)} exclusivity group · Item ${item.id}</p>`;
    row.addEventListener("mouseenter",e=>showInfoTooltip(html,e));row.addEventListener("mousemove",positionInfoTooltip);row.addEventListener("mouseleave",hideInfoTooltip);row.addEventListener("focusin",e=>showInfoTooltip(html,e));row.addEventListener("focusout",hideInfoTooltip);
    root.append(row);
  }
}
function buildSettingCards(rootId,group){
  const root=$(rootId);root.replaceChildren();
  for(const item of state.boot.setting_data[group]){
    const row=document.createElement("label");row.className="setting-option";row.htmlFor=`m-${group}.${item.key}`;
    const input=document.createElement("input");input.type="checkbox";input.id=row.htmlFor;input.dataset.path=`${group}.${item.key}`;
    const img=document.createElement("img");img.src=`/setting-icons/${item.icon}.jpg`;img.alt="";
    const copy=document.createElement("span");copy.innerHTML=`<strong>${item.name}</strong><small>${item.source}</small>`;row.append(input,img,copy);
    const html=`<h3>${item.name}</h3><p>${item.description}</p><p class="tooltip-meta">${item.source} · Spell ${item.spell_id}</p>`;
    row.addEventListener("mouseenter",e=>showInfoTooltip(html,e));row.addEventListener("mousemove",positionInfoTooltip);row.addEventListener("mouseleave",hideInfoTooltip);row.addEventListener("focusin",e=>showInfoTooltip(html,e));row.addEventListener("focusout",hideInfoTooltip);root.append(row);
  }
}

function buildMechanics(){
  const about=state.boot.about?.[state.spec]||{};
  $("aboutDps").textContent=about.dps||"Not documented yet.";
  $("aboutTps").textContent=about.tps||"Not documented yet.";
  addControls("rotationFields",["use_judgement","use_consecration","consecration_mana_floor","use_holy_strike","use_exorcism","use_holy_wrath","twist_seals","use_bulwark","bulwark_health_threshold"].map(k=>["rotation."+k,k]));
  if(state.spec==="protection"){
    const opener=document.createElement("div");opener.className="rotation-opener";
    opener.innerHTML="<strong>1. Taunt</strong><span>Mandatory opening cast on the assigned target; used once before the repeating priority begins.</span>";
    $("rotationFields").prepend(opener);
  }
  addControls("modelFields",[
    ["model.use_classic_era_conversions","Use Classic Era gear conversions"],
    ["model.command_proc_chance","Command proc probability"],["model.righteousness_damage","Righteousness swing damage"],
    ["model.holy_strike_cost","Holy Strike mana cost"],["model.holy_strike_cooldown","Holy Strike cooldown"],
    ["model.holy_strike_weapon_pct","Holy Strike weapon damage %"],["model.holy_strike_holy_min","Holy Strike Holy damage (min)"],["model.holy_strike_holy_max","Holy Strike Holy damage (max)"],["model.holy_strike_coeff","Holy Strike spell-power coefficient"],
    ["model.melee_crit_multiplier","Melee crit multiplier"],["model.spell_crit_multiplier","Spell crit multiplier"],
    ["model.base_threat_per_damage","Physical threat per damage"],["model.holy_threat_per_damage","Holy threat per damage (audit coefficient)"],["model.thunderfury_proc_chance","Thunderfury proc chance"],["model.thunderfury_damage","Thunderfury proc damage"],["model.thunderfury_threat_multiplier","Thunderfury threat multiplier"],["rotation.bulwark_health_threshold","Bulwark health threshold"]
  ]);
  buildSettingCards("raidBuffFields","raid_buffs");
  buildConsumables();
  buildSettingCards("debuffFields","debuffs");
  buildTalents();
}

function syncCreatureAbilities(){
  const bossType=$("bossType")?.value||state.profile?.encounter?.boss_type||"none",allowed=bossType==="undead"||bossType==="demon";
  for(const key of ["use_exorcism","use_holy_wrath"]){
    const input=document.querySelector(`[data-path="rotation.${key}"]`);if(!input)continue;
    input.checked=allowed;input.disabled=!allowed;const row=input.closest('.toggle-row');
    row.title=allowed?`${labelize(key)} was automatically selected for a ${labelize(bossType)} target.`:`${labelize(key)} only deals damage to Undead or Demon targets.`;
    let note=row.querySelector('.creature-lock-note');if(!note){note=document.createElement('small');note.className='creature-lock-note';row.append(note)}
    note.textContent=allowed?`Automatically selected for ${labelize(bossType)}; you may turn it off.`:'Unavailable: requires an Undead or Demon target';
  }
}

function allTalents(){return state.boot.talent_data.trees.flatMap(tree=>tree.talents)}
function talentById(id){return allTalents().find(t=>String(t.id)===String(id))}
function pointsInTree(tree,build=state.profile.talents){return tree.talents.reduce((sum,t)=>sum+build[String(t.id)],0)}
function totalTalentPoints(build=state.profile.talents){return Object.values(build).reduce((sum,rank)=>sum+rank,0)}
function talentAvailable(tree,talent){
  if(totalTalentPoints()>=state.boot.talent_data.max_points)return false;
  if(state.profile.talents[String(talent.id)]>=talent.ranks.length)return false;
  const prior=tree.talents.filter(t=>t.row<talent.row).reduce((sum,t)=>sum+state.profile.talents[String(t.id)],0);
  return prior>=talent.row*state.boot.talent_data.points_per_tier&&talent.requires.every(req=>state.profile.talents[String(req.id)]>=req.qty);
}
function talentBuildLegal(build){
  if(totalTalentPoints(build)>state.boot.talent_data.max_points)return false;
  return state.boot.talent_data.trees.every(tree=>tree.talents.every(t=>{
    const rank=build[String(t.id)]; if(!rank)return true;
    const prior=tree.talents.filter(other=>other.row<t.row).reduce((sum,other)=>sum+build[String(other.id)],0);
    return prior>=t.row*state.boot.talent_data.points_per_tier&&t.requires.every(req=>build[String(req.id)]>=req.qty);
  }));
}
function showTalentInfo(talent){
  const rank=state.profile.talents[String(talent.id)], max=talent.ranks.length;
  const current=rank?talent.descriptions[String(rank)]:"No ranks learned.";
  const next=rank<max?`Next rank: ${talent.descriptions[String(rank+1)]}`:"Maximum rank learned.";
  $("talentInfo").innerHTML=`<strong>${talent.name}</strong><span>Rank ${rank}/${max}</span><p>${current}</p><p class="next-rank">${next}</p>`;
}
function changeTalent(tree,talent,delta){
  const key=String(talent.id), build=clone(state.profile.talents);
  if(delta>0){if(!talentAvailable(tree,talent))return;build[key]++}
  else {if(!build[key])return;build[key]--;if(!talentBuildLegal(build))return}
  state.profile.talents=build;buildTalents();showTalentInfo(talent);
}
function buildTalents(){
  const root=$("talentTrees");root.replaceChildren();
  state.boot.talent_data.trees.forEach(tree=>{
    const panel=document.createElement("section");panel.className=`talent-tree tree-${tree.name.toLowerCase()}`;
    const header=document.createElement("header");header.innerHTML=`<strong>${tree.name}</strong><span>${pointsInTree(tree)} points</span>`;panel.append(header);
    const board=document.createElement("div");board.className="talent-board";
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");svg.setAttribute("viewBox","0 0 240 420");svg.classList.add("talent-links");
    tree.talents.forEach(t=>t.requires.forEach(req=>{const source=talentById(req.id);const line=document.createElementNS("http://www.w3.org/2000/svg","line");line.setAttribute("x1",30+source.col*60);line.setAttribute("y1",30+source.row*60);line.setAttribute("x2",30+t.col*60);line.setAttribute("y2",30+t.row*60);if(state.profile.talents[String(req.id)]>=req.qty)line.classList.add("active");svg.append(line)}));board.append(svg);
    tree.talents.forEach(talent=>{
      const rank=state.profile.talents[String(talent.id)],available=talentAvailable(tree,talent);
      const button=document.createElement("button");button.type="button";button.className=`talent-node${rank?" learned":""}${rank===talent.ranks.length?" maxed":""}${available?" available":" locked"}`;
      button.style.left=`${8+talent.col*60}px`;button.style.top=`${8+talent.row*60}px`;button.setAttribute("aria-label",`${talent.name}, rank ${rank} of ${talent.ranks.length}`);
      button.innerHTML=`<img src="/talent-icons/${talent.icon}.jpg" alt=""><span>${rank}/${talent.ranks.length}</span>`;
      button.addEventListener("click",()=>changeTalent(tree,talent,1));button.addEventListener("contextmenu",event=>{event.preventDefault();changeTalent(tree,talent,-1)});
      const talentTip=()=>{const current=rank?talent.descriptions[String(rank)]:"No ranks learned.";const next=rank<talent.ranks.length?talent.descriptions[String(rank+1)]:"Maximum rank learned.";return `<h3>${talent.name}</h3><p>Rank ${rank}/${talent.ranks.length}</p><p>${current}</p><p class="tooltip-next">${next}</p>`};
      button.addEventListener("mouseenter",e=>{showTalentInfo(talent);showInfoTooltip(talentTip(),e)});button.addEventListener("mousemove",positionInfoTooltip);button.addEventListener("mouseleave",hideInfoTooltip);button.addEventListener("focus",e=>{showTalentInfo(talent);showInfoTooltip(talentTip(),e)});button.addEventListener("blur",hideInfoTooltip);board.append(button);
    });panel.append(board);root.append(panel);
  });
  $("talentPoints").textContent=`${totalTalentPoints()} / ${state.boot.talent_data.max_points} points`;
}

function permanentStats(it) { const out = { ...(it.stats || {}) }; for (const e of it.effects || []) { if (!e.startsWith("Use:")) continue; if (/damage and healing.*?up to \d+ for \d+ sec/i.test(e)) delete out.spellPower; if (/Attack Power by \d+ for \d+ sec/i.test(e)) delete out.attackPower; if (/attack speed by \d+% for \d+ sec/i.test(e)) { delete out.meleeHaste; delete out.rangedHaste; delete out.spellHaste; } } return out; }

function aggregateGear(){
  const totals={}, sets={}, sources={}; let equipped=0;
  const add=(k,v,src)=>{if(!v)return;totals[k]=(totals[k]||0)+v;(sources[k]??=[]).push({source:src,value:v})};
  Object.values(state.profile.gear).forEach(id=>{const item=state.itemsById.get(id);if(!item)return;equipped++;Object.entries(permanentStats(item)).forEach(([k,v])=>add(k,v,item.name));if(item.set){sets[item.set.name]??={...item.set,count:0};sets[item.set.name].count++}});
  Object.values(sets).forEach(set=>set.bonuses.filter(b=>set.count>=b.required&&!/chance on|chance to (?:gain|increase|grant|restore|trigger)|proc|for \d+ sec|when |whenever |after |stack/i.test(b.description||"")).forEach(b=>Object.entries(b.stats||{}).forEach(([k,v])=>add(k,v,`${set.name} (${b.required} pieces)`))));
  Object.entries(state.profile.enchants||{}).forEach(([slot,id])=>{if(!state.profile.gear[slot])return;const enchant=state.boot.enchants?.slots?.[slot]?.find(e=>e.id===id);Object.entries(enchant?.stats||{}).forEach(([key,value])=>add(key==="primary"?"strength":key,value,enchant.name));});
  return {totals,equipped,sets,sources};
}

function addItemTooltip(target,item){if(!item)return;target.addEventListener("pointerenter",event=>showItemTooltip(item,event));target.addEventListener("pointermove",positionTooltip);target.addEventListener("pointerleave",hideItemTooltip);target.addEventListener("focus",event=>showItemTooltip(item,event));target.addEventListener("blur",hideItemTooltip)}
function showItemTooltip(item,event){
  const tip=$("gearTooltip"),equippedNames=new Set(Object.values(state.profile.gear).map(id=>state.itemsById.get(id)?.name).filter(Boolean));tip.replaceChildren();
  const title=document.createElement("h3");title.className=`quality-${item.quality}`;title.textContent=item.name;tip.append(title);
  const meta=document.createElement("p");meta.className="tooltip-meta";meta.textContent=`Item Level ${item.itemLevel} · ${item.subclass||item.slot}`;tip.append(meta);
  const stats=itemStatLine(item);if(stats!=="No parsed direct stats"){const p=document.createElement("p");p.textContent=stats;tip.append(p)}
  (item.effects||[]).forEach(text=>{const p=document.createElement("p");p.className="tooltip-effect";p.textContent=text;tip.append(p)});
  if(item.set){const count=item.set.pieces.filter(name=>equippedNames.has(name)).length;const head=document.createElement("h4");head.textContent=`${item.set.name} (${count}/${item.set.pieces.length}) · ${item.set.ruleset||"Classic Era"}`;tip.append(head);const list=document.createElement("ul");item.set.pieces.forEach(name=>{const li=document.createElement("li");li.className=equippedNames.has(name)?"equipped-piece":"";li.textContent=name;list.append(li)});tip.append(list);item.set.bonuses.forEach(bonus=>{const p=document.createElement("p");p.className=`set-bonus ${count>=bonus.required?"active":"inactive"}`;p.textContent=`(${bonus.required}) Set: ${bonus.description}${bonus.modeled===false?" · informational":" · modeled"}`;tip.append(p)})}
  const source=document.createElement("p");source.className="tooltip-source";source.textContent=[item.source,item.availabilityNote,...(item.modelNotes||[])].filter(Boolean).join(" � ");tip.append(source);tip.hidden=false;positionTooltip(event)
}
function positionTooltip(event){const tip=$("gearTooltip");if(tip.hidden)return;const x=Math.min(innerWidth-tip.offsetWidth-12,(event.clientX||20)+18),y=Math.min(innerHeight-tip.offsetHeight-12,(event.clientY||20)+18);tip.style.left=`${Math.max(8,x)}px`;tip.style.top=`${Math.max(8,y)}px`}
function hideItemTooltip(){$("gearTooltip").hidden=true}

function buildGear(){
  const root=$("gearSlots"); root.replaceChildren();
  Object.entries(gearLabels).forEach(([slot,label])=>{
    const item=state.itemsById.get(state.profile.gear[slot]); const button=document.createElement("button"); button.type="button";
    button.className=`gear-slot ${item?`equipped quality-${item.quality}`:""}`; button.dataset.slot=slot;
    const icon=item&&item.icon?`<img src="/item-icons/${item.icon}.jpg" alt="">`:label[0];
    button.innerHTML=`<span class="slot-icon">${icon}</span><span class="slot-copy"><small>${label}</small><strong>${item?item.name:"Empty"}</strong></span><span class="slot-level">${item?`iLvl ${item.itemLevel}`:"Choose"}</span>`;
    button.addEventListener("click",()=>openPicker(slot));addItemTooltip(button,item);
    const wrap=document.createElement("div");wrap.className="gear-entry";wrap.append(button);root.append(wrap);
    const options=state.boot.enchants?.slots?.[slot]||[];
    if(item&&options.length&&(!["main_hand","off_hand"].includes(slot)||item.weaponDamageMin)){
      state.profile.enchants??=Object.fromEntries(Object.keys(gearLabels).map(k=>[k,""]));
      const select=document.createElement("select");select.setAttribute("aria-label",`${label} enchant`);select.add(new Option("No enchant",""));
      options.forEach(e=>{const option=new Option(e.name,e.id);option.title=e.description;select.add(option)});select.value=state.profile.enchants[slot]||"";
      select.addEventListener("change",()=>{state.profile.enchants[slot]=select.value;buildGear()});wrap.append(select);
    }
  });
  const {totals,equipped,sets,sources}=aggregateGear(); const summary=$("gearTotals"); summary.replaceChildren();
  const statTip=(row,k)=>{const src=sources[k]||[];if(!src.length)return;row.classList.add("has-tip");const html=`<h3>${statLabels[k]||labelize(k)}: +${fmt(totals[k],totals[k]%1?1:0)}</h3><p class="tooltip-meta">${src.map(x=>`${x.source}: +${fmt(x.value,x.value%1?1:0)}`).join("<br>")}</p><p class="tooltip-meta">Base attributes, buffs, consumables and talents are added in the simulation result.</p>`;row.addEventListener("mouseenter",e=>showInfoTooltip(html,e));row.addEventListener("mousemove",positionInfoTooltip);row.addEventListener("mouseleave",hideInfoTooltip)};
  const keyByLabel=Object.fromEntries(Object.keys(totals).map(k=>[statLabels[k]||labelize(k),k]));
  const rows=[["Items equipped",equipped],...Object.entries(totals).sort(([a],[b])=>(statLabels[a]||a).localeCompare(statLabels[b]||b)).map(([k,v])=>[statLabels[k]||labelize(k),`+${fmt(v,v%1?1:0)}`])];
  rows.forEach(([name,value])=>{const row=document.createElement("div");row.className="gear-stat";row.innerHTML=`<span>${name}</span><strong>${value}</strong>`;summary.append(row);if(keyByLabel[name])statTip(row,keyByLabel[name])});
  const side=$("sideGearStats"); if(side){side.replaceChildren(); rows.slice(1).forEach(([name,value])=>{const row=document.createElement("div");row.className="side-stat";row.innerHTML=`<span>${name}</span><b>${value}</b>`;side.append(row);if(keyByLabel[name])statTip(row,keyByLabel[name])});}
  const setRoot=$("gearSets");setRoot.replaceChildren();Object.values(sets).forEach(set=>{const card=document.createElement("section");card.className="set-summary";const h=document.createElement("h4");h.textContent=`${set.name} · ${set.count}/${set.pieces.length} · ${set.ruleset||"Classic Era"}`;card.append(h);set.bonuses.forEach(b=>{const p=document.createElement("p");p.className=set.count>=b.required?"active":"inactive";p.textContent=`${b.required} pieces — ${b.description}${b.modeled===false?" · informational":" · modeled"}`;card.append(p)});setRoot.append(card)});
}

function openPicker(slot){
  hideInfoTooltip(); state.pickerSlot=slot; $("pickerSlot").textContent=gearLabels[slot]; $("itemSearch").value=""; renderPicker(); $("itemDialog").showModal(); $("itemSearch").focus();
}

function itemStatLine(item){
  const parts=Object.entries(item.stats).slice(0,6).map(([k,v])=>`+${fmt(v,v%1?1:0)} ${statLabels[k]||labelize(k)}`);
  if(item.weaponDamageMin!==null) parts.unshift(`${fmt(item.weaponDamageMin,0)}–${fmt(item.weaponDamageMax,0)} @ ${item.weaponSpeed.toFixed(2)}`);
  return parts.join(" · ")||"No parsed direct stats";
}

function renderPicker(){
  const query=$("itemSearch").value.trim().toLowerCase();
  const faction=(state.boot.race_factions||{})[$("race").value];
  const matches=state.items.filter(item=>item.simulationAvailability!=="excluded"&&(!item.faction||item.faction===faction)&&(item.equipSlots||[]).includes(state.pickerSlot)&&(!query||`${item.name} ${item.source} ${item.subclass||""}`.toLowerCase().includes(query))).slice(0,150);
  const list=$("itemList"); list.replaceChildren();
  matches.forEach(item=>{const row=document.createElement("button");row.type="button";row.className=`item-row quality-${item.quality}`;const icon=item.icon?`<img src="/item-icons/${item.icon}.jpg" alt="">`:item.name[0];row.innerHTML=`<span class="slot-icon">${icon}</span><span><h3>${item.name}</h3><p>${item.subclass||item.slot} · ${item.source}</p></span><span class="item-stats">${itemStatLine(item)}</span><span class="ilvl">iLvl ${item.itemLevel}</span>`;row.addEventListener("click",()=>selectItem(item));addItemTooltip(row,item);list.append(row)});
  $("itemCount").textContent=`${matches.length}${matches.length===150?"+":""} shown`;
}

function selectItem(item){
  state.profile.gear[state.pickerSlot]=item.id;
  if(state.profile.enchants&&["main_hand","off_hand"].includes(state.pickerSlot)&&!item.weaponDamageMin)state.profile.enchants[state.pickerSlot]="";
  if(state.pickerSlot==="main_hand"&&item.slot==="Two-Hand") state.profile.gear.off_hand=0;
  buildGear(); $("itemDialog").close();
}

function hydrateForm(){
  document.querySelectorAll("[data-path]").forEach(input=>{
    const value=atPath(state.profile,input.dataset.path);
    if(input.type==="checkbox") input.checked=value; else input.value=value;
  });
  $("incoming").checked=state.profile.encounter.incoming_enabled;
  $("bossType").value=state.profile.encounter.boss_type;
  $("race").innerHTML=(state.boot.races||["Human"]).map(r=>`<option value="${r}">${r}</option>`).join("");
  $("race").value=state.profile.race||"Human";
  const renderRacial=()=>{$("racialSummary").textContent=(state.boot.racials||{})[$("race").value]||""};renderRacial();$("race").onchange=()=>{renderRacial();swapFactionGear()};
  syncCreatureAbilities();
  $("sideIterations").value=state.profile.iterations;
  $("runTitle").textContent=labelize(state.spec)+" results";
  $("brandSpec").textContent=labelize(state.spec)+" Paladin";
  buildGear();
}

// Alliance/Horde-only gear: swap to the other faction's identical twin, or clear the slot.
function swapFactionGear(){
  const faction=(state.boot.race_factions||{})[$("race").value],cleared=[];
  Object.entries(state.profile.gear).forEach(([slot,id])=>{const item=state.itemsById.get(id);if(!item?.faction||item.faction===faction)return;
    if(item.factionTwin&&state.itemsById.has(item.factionTwin))state.profile.gear[slot]=item.factionTwin;else{cleared.push(item.name);state.profile.gear[slot]=0}});
  $("formError").textContent=cleared.length?`Removed ${faction==="Alliance"?"Horde":"Alliance"}-only gear with no ${faction} equivalent: ${cleared.join(", ")}.`:"";
  buildGear();
}
function readForm(){
  const profile=clone(state.profile);
  document.querySelectorAll("[data-path]").forEach(input=>{
    const old=atPath(profile,input.dataset.path);
    const value=input.type==="checkbox"?input.checked:(Number.isInteger(old)?Number.parseInt(input.value,10):Number.parseFloat(input.value));
    if(typeof value==="number"&&!Number.isFinite(value)) throw new Error(`${input.previousElementSibling.textContent} requires a number.`);
    setPath(profile,input.dataset.path,value);
  });
  profile.encounter.incoming_enabled=$("incoming").checked;
  profile.encounter.boss_type=$("bossType").value;
  profile.race=$("race").value;
  profile.iterations=Number.parseInt($("sideIterations").value,10);
  if(!Number.isInteger(profile.iterations)) throw new Error("Iterations requires a whole number.");
  return profile;
}

function selectSpec(spec){
  state.spec=spec; state.profile=clone(state.boot.presets[spec]);
  document.body.dataset.class="paladin";document.body.dataset.spec=`paladin-${spec}`;
  document.querySelectorAll(".spec").forEach(b=>b.classList.toggle("active",b.dataset.spec===spec));
  buildMechanics(); hydrateForm(); $("formError").textContent="";
  $("talentInfo").textContent=spec==="protection"?"51-point preset optimized for Protection TPS in the implemented model.":"51-point preset maximizes implemented Retribution DPS talents and sourced melee damage talents.";
}

function metricCard(label,key,primary=false,suffix=""){
  const m=state.result.metrics[key]; const el=document.createElement("article"); el.className="metric"+(primary?" primary-metric":"");
  const ci=m.mean_95ci_half_width===null?"one sample":`95% CI ± ${fmt(m.mean_95ci_half_width,2)}`;
  el.innerHTML=`<div class="label">${label}</div><div class="value">${fmt(m.mean,1)}${suffix}</div><div class="range">${ci}</div>`; return el;
}
function contributionTable(values,unit){
  const entries=Object.entries(values),total=entries.reduce((sum,[,v])=>sum+v,0)||1;
  const wrap=document.createElement("div");wrap.className="result-table-wrap";
  wrap.innerHTML=`<table class="result-breakdown"><thead><tr><th>Name</th><th>Contribution</th><th>${unit}</th>${unit==='DPS'?'<th>Total Damage</th>':''}<th>%</th></tr></thead><tbody></tbody></table>`;
  const body=wrap.querySelector("tbody");
  entries.forEach(([name,value])=>{
    const share=100*value/total,tr=document.createElement("tr");
    const nameCell=document.createElement("td"),barCell=document.createElement("td"),valueCell=document.createElement("td"),damageCell=unit==='DPS'?document.createElement("td"):null,shareCell=document.createElement("td");
    const track=document.createElement("div"),fill=document.createElement("div");
    nameCell.textContent=name;track.className="share-track";track.setAttribute("role","img");track.setAttribute("aria-label",`${fmt(share,1)} percent`);
    fill.className="share-fill";fill.style.width=`${Math.max(0,Math.min(100,share))}%`;track.append(fill);barCell.append(track);
    valueCell.textContent=fmt(value,2);if(damageCell)damageCell.textContent=fmt(state.result.ability_damage?.[name]??value*state.result.profile.duration,0);shareCell.textContent=`${fmt(share,1)}%`;tr.append(nameCell,barCell,valueCell,...(damageCell?[damageCell]:[]),shareCell);body.append(tr);
  });
  return wrap;
}
function settingsSummary(group,title){
  const wrap=document.createElement("div");wrap.className="active-settings";const h=document.createElement("h3");h.textContent=title;wrap.append(h);
  const data=group==='consumables'?state.boot.consumable_data.items:state.boot.setting_data[group];
  data.filter(item=>state.result.profile[group][item.key]).forEach(item=>{const row=document.createElement("div");row.className="active-setting-row";const folder=group==='consumables'?'consumable-icons':'setting-icons';row.innerHTML=`<img src="/${folder}/${item.icon}.jpg" alt=""><span><strong>${item.name}</strong><small>${item.description}</small></span>`;wrap.append(row)});return wrap;
}
function renderResultDetail(){
  const root=$("resultDetail");root.replaceChildren();document.querySelectorAll(".result-tab").forEach(b=>b.classList.toggle("active",b.dataset.resultView===state.resultView));
  if(state.resultView==='damage')root.append(contributionTable(state.result.ability_dps,'DPS'));
  else if(state.resultView==='threat')root.append(contributionTable(state.result.ability_tps,'TPS'));
  else if(state.resultView==='taken'){
    const e=state.result.profile.encounter,m=state.result.metrics;
    if(!e.incoming_enabled){const note=document.createElement('p');note.textContent='Incoming damage is disabled. Enable it in Encounter to evaluate survivability.';root.append(note);return}
    const cards=document.createElement('div');cards.className='metrics';
    cards.append(metricCard('Damage / alive second','alive_dtps'),metricCard('Time alive','alive_seconds',false,'s'),metricCard('Peak 3-second damage','peak_3s_damage'),metricCard('Total damage taken','damage_taken'),metricCard('Effective healing','effective_healing'),metricCard('Overhealing','overhealing'));
    const note=document.createElement('p');note.textContent=`${(m.survival_fraction*100).toFixed(1)}% survived. ${e.enemies} level-63 attacker(s), ${e.enemy_damage_min}–${e.enemy_damage_max} raw physical damage every ${e.enemy_swing}s; healing ${e.heal_amount} every ${e.heal_interval}s. Configure these in Encounter; use zero healing for unhealed survival. DTPS divides by full fight duration, while damage/alive second divides by time alive. Early death can lower full-fight DTPS. Survival is conditional on this simplified healing scenario.`;
    root.append(cards,note,contributionTable(state.result.taken_dtps,'DTPS'));
  }
  else if(state.resultView==='buffs'){root.append(settingsSummary('raid_buffs','Active raid buffs'),settingsSummary('consumables','Active consumables'))}
  else if(state.resultView==='debuffs')root.append(settingsSummary('debuffs','Active target debuffs'));
  else if(state.resultView==='resources'){const table=document.createElement('dl');table.className='diagnostics';[['Mana spent',state.result.first_iteration.mana_spent],['Mana gained',state.result.first_iteration.mana_gained],['Ending mana',state.result.metrics.ending_mana.mean],['First unaffordable cast',state.result.first_iteration.first_unaffordable_cast??'Never']].forEach(([a,b])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=a;dd.textContent=typeof b==='number'?fmt(b,1):b;table.append(dt,dd)});root.append(table)}
  else {const wrap=document.createElement('div');wrap.className='table-wrap';wrap.innerHTML='<table><thead><tr><th>Time</th><th>Event</th><th>Amount</th><th>Health</th><th>Mana</th></tr></thead><tbody></tbody></table>';state.result.first_iteration.log.forEach(e=>{const tr=document.createElement('tr');[e.time.toFixed(3),e.event,fmt(e.amount,2),fmt(e.health,2),fmt(e.mana,2)].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td)});wrap.querySelector('tbody').append(tr)});root.append(wrap)}
}

function renderResult(){
  $("emptyState").hidden=true; $("results").hidden=false; $("pinButton").disabled=false; $("exportButton").disabled=false;
  const cards=$("metricCards"); cards.replaceChildren(
    metricCard("Damage / second","dps",true),metricCard("Threat / second","tps"),
    metricCard("Damage taken / alive sec","alive_dtps"),metricCard("Peak 3-second damage","peak_3s_damage"),
    metricCard("Time alive","alive_seconds",false,"s"),metricCard("Ending mana","ending_mana"),
    metricCard("Damage absorbed","absorbed"),metricCard("Damage blocked","blocked_damage")
  );
  renderResultDetail();
  const d=$("diagnostics"); d.replaceChildren();
  const diagnostics=[
    ["Survived",`${(state.result.metrics.survival_fraction*100).toFixed(1)}%`],
    ["Unaffordable cast runs",`${(state.result.metrics.unaffordable_cast_fraction*100).toFixed(1)}%`],
    ["Iterations",state.result.profile.iterations.toLocaleString()], ["Seed",state.result.profile.seed],
    ["Duration",`${state.result.profile.duration}s`],["Items equipped",state.result.gear_summary.equipped.length],
    ["Gear data",state.result.gear_summary.data_version],["Mechanics data",state.result.data_version]
  ];
  diagnostics.forEach(([name,value])=>{ const dt=document.createElement("dt"); const dd=document.createElement("dd"); dt.textContent=name; dd.textContent=value; d.append(dt,dd); });
  const gearAudit=state.result.gear_summary;
  const addNote=(label,text)=>{const dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=label;dd.textContent=text;d.append(dt,dd)};
  (gearAudit.item_effects?.unresolved||[]).forEach(x=>addNote("Unmodeled item effect",`${x.item}: ${x.effect}`));
  (gearAudit.item_effects?.applied||[]).filter(x=>x.provisional).forEach(x=>addNote("Provisional effect",x.provisional));
  (gearAudit.equipped||[]).forEach(x=>(state.itemsById.get(x.id)?.modelNotes||[]).forEach(note=>addNote(x.name,note)));
  (gearAudit.active_classic_set_bonuses||[]).filter(x=>!x.modeled).forEach(x=>addNote("Unmodeled set bonus",`${x.set} (${x.required}): ${x.description}`));
  addNote("Accuracy", "Alpha model. Confidence intervals measure simulation sampling noise, not uncertainty in game mechanics. Defaults are suggested builds, not proven global optima.");
  $("quickDps").textContent=fmt(state.result.metrics.dps.mean,1); $("quickTps").textContent=fmt(state.result.metrics.tps.mean,1);
  $("quickSurvival").textContent=`${(state.result.metrics.survival_fraction*100).toFixed(1)}%`; $("quickDtps").textContent=fmt(state.result.metrics.alive_dtps.mean,1); $("quickMana").textContent=fmt(state.result.metrics.ending_mana.mean,0);
  $("runMeta").textContent=`${state.result.profile.iterations.toLocaleString()} iterations · seed ${state.result.profile.seed} · ${state.result.profile.duration}s`;
  const comp=$("comparison");
  if(state.baseline){ const a=state.result.metrics,b=state.baseline.metrics; comp.hidden=false; comp.textContent=`Against pinned ${labelize(state.baseline.profile.spec)}: DPS ${signed(a.dps.mean-b.dps.mean)}, TPS ${signed(a.tps.mean-b.tps.mean)}, alive-DTPS ${signed(a.alive_dtps.mean-b.alive_dtps.mean)}.`; }
  else comp.hidden=true;
}
function signed(v){return (v>=0?"+":"")+fmt(v,1)}

async function run(){
  try{
    $("formError").textContent=""; state.profile=readForm();
    // A fresh seed each run unless locked; the seed field shows the one used.
    if(!$("lockSeed").checked){state.profile.seed=Math.floor(Math.random()*2147483647);$("f-seed").value=state.profile.seed;}
    $("runButton").disabled=true; $("runButton").textContent="Simulating…"; $("progressBar").classList.add("running");
    const data=await ForeverSim.simulate("paladin",state.profile,state.profile.iterations,(done,total)=>{$("progressBar").style.width=`${Math.round(100*done/total)}%`;});
    if(data.error) throw new Error(data.error); state.result=data; renderResult(); showPanel("results");
    $("runStamp").textContent=`Last run ${new Date().toLocaleTimeString()} · seed ${state.profile.seed}`;
    const cards=$("metricCards");cards.classList.remove("run-flash");void cards.offsetWidth;cards.classList.add("run-flash");
  }catch(error){ $("formError").textContent=error.message; }
  finally{ $("runButton").disabled=false; $("runButton").textContent="Run simulation"; $("progressBar").classList.remove("running"); $("progressBar").style.width="0"; }
}

function exportResult(){
  const blob=new Blob([JSON.stringify(state.result,null,2)],{type:"application/json"}); const a=document.createElement("a");
  a.href=URL.createObjectURL(blob); a.download=`${state.result.profile.spec}-result.json`; a.click(); URL.revokeObjectURL(a.href);
}

async function init(){
  buildFields();
  try{
    const [response,itemResponse,wsResponse]=await Promise.all([fetch("/data/bootstrap.json?v=8fe71e8"),fetch("/data/items.json?v=8fe71e8"),fetch("/data/wowsims-import.json?v=8fe71e8").catch(()=>null)]); if(!response.ok||!itemResponse.ok) throw new Error("Simulator data unavailable."); ForeverSim.warm(); state.wsData=wsResponse&&wsResponse.ok?await wsResponse.json():null; state.boot=await response.json(); const catalog=await itemResponse.json(); state.items=catalog.items; state.itemsById=new Map(state.items.map(item=>[item.id,item]));
    $("serverDot").classList.add("online"); $("serverText").textContent="Browser engine ready";
    $("gearVersion").textContent=`Classic Anniversary Phase 1–2 preset equipped · ${state.items.length.toLocaleString()} items`;
    const sources=$("sources"); Object.entries(state.boot.sources).forEach(([name,url])=>{ const p=document.createElement("p"); const a=document.createElement("a"); a.href=url; a.target="_blank"; a.rel="noopener noreferrer"; a.textContent=labelize(name); p.append(a); sources.append(p); });
    const gp=document.createElement("p"),ga=document.createElement("a");ga.href=state.boot.gear_catalog.source;ga.target="_blank";ga.rel="noopener noreferrer";ga.textContent="Classic Era item catalog (temporary exception)";gp.append(ga);sources.append(gp);
    Object.values(state.boot.phase6_bis).forEach(loadout=>{const p=document.createElement("p"),a=document.createElement("a");a.href=loadout.source;a.target="_blank";a.rel="noopener noreferrer";a.textContent=loadout.name;p.append(a);sources.append(p)});
    const relicSource=state.boot.phase6_bis.protection.relic_source;if(relicSource){const p=document.createElement("p"),a=document.createElement("a");a.href=relicSource;a.target="_blank";a.rel="noopener noreferrer";a.textContent="Protection relic recommendation";p.append(a);sources.append(p)}
    const tp=document.createElement("p"),ta=document.createElement("a");ta.href=state.boot.talent_data.source;ta.target="_blank";ta.rel="noopener noreferrer";ta.textContent="WoW Forever Paladin talent calculator";tp.append(ta);sources.append(tp);
    state.boot.assumptions.forEach(text=>{const li=document.createElement("li");li.textContent=text;$("assumptions").append(li)});
    const requested=new URLSearchParams(location.search).get("spec");
    selectSpec(requested==="retribution"?"retribution":"protection");
    const query=new URLSearchParams(location.search);state.profile.encounter.targets=Math.max(1,Math.min(10,Number(query.get("targets"))||1));
    if(query.get("benchmark")==="1"){state.profile.seed=state.boot.defaults.benchmark_seed;state.profile.iterations=state.boot.defaults.benchmark_iterations;$("lockSeed").checked=true;}hydrateForm();
    const requestedRace=new URLSearchParams(location.search).get("race"); if(requestedRace&&(state.boot.races||[]).includes(requestedRace)){state.profile.race=requestedRace;$("race").value=requestedRace;$("race").dispatchEvent(new Event("change"));}
  }catch(error){ $("serverText").textContent="Server connection failed"; $("formError").textContent=error.message; }
}


// ---------------------------------------------------------------- WoWSims Exporter import
function applyWowSimsImportPaladin(text){
  if(!state.wsData) throw new Error("Import data failed to load; reload the page and try again.");
  const parsed=WowSimsImport.parseExport(text);
  if(WowSimsImport.norm(parsed.className)!=="paladin") throw new Error(`That export is for a ${parsed.className}. This page only imports Paladin exports.`);
  const {positions,error}=WowSimsImport.decodeTalentPositions(state.wsData,"Paladin",parsed.talentsStr);
  if(error) throw new Error(error);
  const totals={};
  positions.forEach(p=>{totals[p.tree]=(totals[p.tree]||0)+p.rank});
  const protPts=totals["Protection"]||0, retPts=totals["Retribution"]||0, holyPts=totals["Holy"]||0;
  if(protPts===0&&retPts===0&&holyPts>0) throw new Error("This looks like a Holy Paladin build; only Protection and Retribution are modeled.");
  const spec=protPts>=retPts?"protection":"retribution";
  selectSpec(spec);
  const notes=[];
  if(holyPts>Math.max(protPts,retPts)) notes.push(`Most points are in Holy (not modeled); imported as ${labelize(spec)} based on the remaining points.`);
  const raceOk=(state.boot.races||[]).some(r=>WowSimsImport.norm(r)===WowSimsImport.norm(parsed.raceName));
  if(raceOk) state.profile.race=(state.boot.races||[]).find(r=>WowSimsImport.norm(r)===WowSimsImport.norm(parsed.raceName));
  else notes.push(`Race "${parsed.raceName}" isn't in the Forever Paladin roster; kept ${state.profile.race}.`);
  const {byId,unmatched}=WowSimsImport.matchForeverTalents(state.boot.talent_data.trees,positions);
  Object.keys(state.profile.talents).forEach(id=>{state.profile.talents[id]=byId[id]||0});
  if(unmatched.length) notes.push(`${unmatched.length} talent point(s) couldn't be matched to a Forever talent and were skipped.`);
  let equipped=0, itemsMissing=0;
  WowSimsImport.SLOT_ORDER.forEach(([,key])=>{
    const imp=WowSimsImport.gearForKey(parsed.gearItems,key);
    if(!imp){ state.profile.gear[key]=0; return; }
    if(!state.itemsById.has(imp.id)){ itemsMissing++; state.profile.gear[key]=0; return; }
    state.profile.gear[key]=imp.id; equipped++;
    const item=state.itemsById.get(imp.id);
    if(key==="main_hand"&&item.slot==="Two-Hand") state.profile.gear.off_hand=0;
  });
  if(itemsMissing) notes.push(`${itemsMissing} equipped item(s) aren't in this catalog (wrong phase or not carried) and were left empty.`);
  hydrateForm(); buildGear(); buildTalents();
  return {equipped,notes};
}
$("importButton").addEventListener("click",()=>{$("importStatus").textContent="";$("importStatus").className="import-status";$("importText").value="";$("importDialog").showModal();$("importText").focus()});
$("importApply").addEventListener("click",()=>{
  const status=$("importStatus");
  try{
    const {equipped,notes}=applyWowSimsImportPaladin($("importText").value);
    status.textContent=`Imported ${equipped} item(s), race and talents.${notes.length?String.fromCharCode(10)+notes.join(String.fromCharCode(10)):""}`;
    status.className="import-status ok";
    setTimeout(()=>$("importDialog").close(),notes.length?2600:1200);
  }catch(e){ status.textContent=e.message; status.className="import-status error"; }
});

document.querySelectorAll(".spec").forEach(b=>b.addEventListener("click",()=>selectSpec(b.dataset.spec)));
function showPanel(name){
  document.querySelectorAll(".main-tab").forEach(x=>x.classList.toggle("active",x.dataset.panel===name));
  document.querySelectorAll(".view-panel").forEach(x=>x.classList.toggle("active",x.dataset.panel===name));
}
document.querySelectorAll(".main-tab").forEach(b=>b.addEventListener("click",()=>showPanel(b.dataset.panel)));
document.querySelectorAll(".result-tab").forEach(b=>b.addEventListener("click",()=>{state.resultView=b.dataset.resultView;if(state.result)renderResultDetail()}));
document.querySelectorAll("[data-panel-jump]").forEach(b=>b.addEventListener("click",()=>showPanel(b.dataset.panelJump)));
$("runButton").addEventListener("click",run); $("resetButton").addEventListener("click",()=>{selectSpec(state.spec);$("gearVersion").textContent=`Classic Anniversary Phase 1–2 preset equipped · ${state.items.length.toLocaleString()} items`});
$("foreverBisButton").addEventListener("click",()=>{const bis=state.boot.forever_bis?.[state.spec];if(!bis)return;Object.keys(state.profile.gear).forEach(slot=>{state.profile.gear[slot]=bis[slot]||0});swapFactionGear();$("gearVersion").textContent=`Assumed Forever BiS (auto-generated) equipped · ${state.items.length.toLocaleString()} items`;buildGear();showPanel("gear")});
$("pinButton").addEventListener("click",()=>{state.baseline=clone(state.result);renderResult();$("pinButton").textContent="Baseline pinned"});
$("exportButton").addEventListener("click",exportResult);
$("itemSearch").addEventListener("input",renderPicker);
$("clearItem").addEventListener("click",()=>{state.profile.gear[state.pickerSlot]=0;buildGear();$("itemDialog").close()});
$("resetTalents").addEventListener("click",()=>{Object.keys(state.profile.talents).forEach(id=>state.profile.talents[id]=0);buildTalents();$("talentInfo").textContent="Talents reset. Choose talents from any tree."});
init();
