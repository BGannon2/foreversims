// Import a WoWSims Exporter in-game addon dump (https://www.curseforge.com/wow/addons/wowsimsexporter).
// The addon exports JSON: {class, race, professions, talents: "<tree1digits>-<tree2digits>-<tree3digits>",
// gear: {items: [ItemSpec x17, in WoWSims ItemSlot enum order]}}, ItemSpec = {id, enchant, randomSuffix}.
// This module only decodes that payload against data already shipped to the page (Forever talent
// trees, our item catalog, our enchant catalog); no network calls, no server support needed.
window.WowSimsImport = (function () {
  const norm = s => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");

  function parseExport(text) {
    let json;
    try { json = JSON.parse(text); } catch { throw new Error("That doesn't look like JSON. Paste the exact text the WoWSims Exporter addon gave you."); }
    if (!json || typeof json !== "object" || !json.class) throw new Error("Missing a \"class\" field — this doesn't look like a WoWSims Exporter dump.");
    const items = (json.gear && Array.isArray(json.gear.items)) ? json.gear.items : [];
    const gearItems = new Array(17).fill(null);
    for (let i = 0; i < 17 && i < items.length; i++) {
      const it = items[i];
      if (it && it.id) gearItems[i] = { id: it.id, enchant: it.enchant || 0 };
    }
    return { className: String(json.class), raceName: String(json.race || ""), talentsStr: String(json.talents || ""), gearItems };
  }

  // WoWSims ItemSlot enum order, paired with our UI slot labels (shared-engine pages) and
  // lowercase keys (Paladin engine). Must match tools/build_wowsims_import.py SLOT_ORDER.
  const SLOT_ORDER = [
    ["Head", "head"], ["Neck", "neck"], ["Shoulders", "shoulders"], ["Back", "back"], ["Chest", "chest"],
    ["Wrist", "wrist"], ["Hands", "hands"], ["Waist", "waist"], ["Legs", "legs"], ["Feet", "feet"],
    ["Finger 1", "finger1"], ["Finger 2", "finger2"], ["Trinket 1", "trinket1"], ["Trinket 2", "trinket2"],
    ["Main Hand", "main_hand"], ["Off Hand", "off_hand"], ["Ranged / Relic", "relic"],
  ];
  function gearForLabel(gearItems, label) { const i = SLOT_ORDER.findIndex(([l]) => l === label); return i >= 0 ? gearItems[i] : null; }
  function gearForKey(gearItems, key) { const i = SLOT_ORDER.findIndex(([, k]) => k === key); return i >= 0 ? gearItems[i] : null; }

  function decodeTalentPositions(wsData, className, talentsStr) {
    const order = (wsData.tree_order || {})[className];
    if (!order) return { positions: [], error: `No talent tree layout for ${className}.` };
    const parts = talentsStr.split("-");
    const positions = [];
    order.forEach((treeName, i) => {
      const digits = parts[i] || "";
      const layout = (wsData.trees[className] || {})[treeName] || [];
      layout.forEach((slot, idx) => {
        const rank = Number(digits.charAt(idx)) || 0;
        if (rank > 0) positions.push({ tree: treeName, row: slot.row, col: slot.col, rank });
      });
    });
    return { positions };
  }

  /** foreverTrees: [{name, talents:[{id,row,col,ranks:[...]}]}, ...] (Forever talent data for one class). */
  function matchForeverTalents(foreverTrees, positions) {
    const byId = {}, unmatched = [];
    const treesByName = new Map(foreverTrees.map(t => [norm(t.name), t]));
    const treeTotals = {};
    for (const pos of positions) {
      treeTotals[pos.tree] = (treeTotals[pos.tree] || 0) + pos.rank;
      const tree = treesByName.get(norm(pos.tree));
      const talent = tree && tree.talents.find(t => t.row === pos.row && t.col === pos.col);
      if (!talent) { unmatched.push(pos); continue; }
      const maxRank = talent.ranks ? talent.ranks.length : 5;
      byId[String(talent.id)] = Math.min(pos.rank, maxRank);
    }
    const primaryTree = Object.entries(treeTotals).sort((a, b) => b[1] - a[1])[0]?.[0] || null;
    return { byId, unmatched, treeTotals, primaryTree };
  }

  function resolveEnchant(wsData, effectId, ourSlotKey) {
    if (!effectId) return null;
    const candidates = (wsData.enchant_map || {})[String(effectId)];
    if (!candidates || !candidates.length) return null;
    return candidates.find(c => c.slot === ourSlotKey) || candidates[0];
  }

  return { parseExport, SLOT_ORDER, gearForLabel, gearForKey, decodeTalentPositions, matchForeverTalents, resolveEnchant, norm };
})();
