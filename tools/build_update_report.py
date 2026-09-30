"""Compare a new Forever client build with the pinned one and report what matters to the sim.

Downloads the client tables for both builds from wago.tools (cached per build) and writes a
Markdown report of: changed tables, changed values among the reviewed spells and talent curves
(data/wago_verified.json), changes to every spell the engine data references, talent nodes that
were added, removed or changed (flagging ones used by default builds or modeled), and item
changes affecting catalog items. With --apply (and a changed table) it also re-pins the client data to the new build
(wago_verified.json, item class/faction/limit data, removed-item list); engine code is never
changed automatically, so anything flagged "needs review" has to be handled by hand.
Run: python tools/build_update_report.py NEW_BUILD [--apply] [--out report.md] [--cache DIR]
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPELL_TABLES = ("SpellName", "Spell", "SpellEffect", "SpellMisc", "SpellPower", "SpellCooldowns", "SpellLevels",
                "SpellCastTimes", "SpellDuration", "TraitNodeXTraitNodeEntry", "TraitNodeEntry", "TraitDefinition",
                "TraitDefinitionEffectPoints", "CurvePoint", "TraitNode", "TraitTree")
TABLES = SPELL_TABLES + ("ItemSparse",)
# Item fields with no effect on the sim (display, sheathing, sell price ...).
ITEM_IGNORED = {"ID", "SheatheType", "SellPrice", "BuyPrice", "Flags_0", "Flags_1", "Flags_2", "Flags_3", "Flags_4",
                "Display_lang", "Display1_lang", "Display2_lang", "Display3_lang", "Description_lang", "PageID",
                "DurationInInventory", "InstanceBound", "ZoneBound_0", "ZoneBound_1", "ItemRange"}


def fetch(build, cache):
    folder = cache / build
    folder.mkdir(parents=True, exist_ok=True)

    def one(table):
        path = folder / f"{table}.csv"
        if not path.is_file() or path.stat().st_size < 100:
            url = f"https://wago.tools/db2/{table}/csv?build={build}"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=300) as r:
                path.write_bytes(r.read())
        return table
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(one, TABLES))
    return folder


def rows(folder, table):
    return list(csv.DictReader((folder / f"{table}.csv").read_text(encoding="utf-8-sig").splitlines()))


def grouped(folder, table, key):
    out = collections.defaultdict(list)
    for r in rows(folder, table):
        out[r[key]].append(r)
    return out


def engine_spell_ids():
    from forever.engine_data import ABILITIES
    ids = set()
    for a in ABILITIES.values():
        if a.get("spell_id"):
            ids.add(str(a["spell_id"]))
        ids.update(re.findall(r"spell (\d{3,7})", a.get("provisional", "")))
    for r in json.loads((ROOT / "data/wago_verified.json").read_text(encoding="utf-8"))["spells"].values():
        ids.add(str(r["spell_id"]))
        if r.get("whole_spell_id"):
            ids.add(str(r["whole_spell_id"]))
    return ids


def talent_signatures(folder):
    links = grouped(folder, "TraitNodeXTraitNodeEntry", "TraitNodeID")
    entries = {r["ID"]: r for r in rows(folder, "TraitNodeEntry")}
    defs = {r["ID"]: r for r in rows(folder, "TraitDefinition")}
    points = grouped(folder, "TraitDefinitionEffectPoints", "TraitDefinitionID")
    curves = grouped(folder, "CurvePoint", "CurveID")
    sig = {}
    for node, link_rows in links.items():
        parts = []
        for link in link_rows:
            entry = entries.get(link["TraitNodeEntryID"], {})
            d = defs.get(entry.get("TraitDefinitionID"), {})
            pts = sorted((p["EffectIndex"], p["OperationType"], sorted((c["Pos_0"], c["Pos_1"]) for c in curves.get(p["CurveID"], [])))
                         for p in points.get(d.get("ID"), []))
            parts.append((entry.get("MaxRanks"), d.get("SpellID"), pts))
        sig[node] = parts
    return sig


def talent_usage():
    from forever import sim
    from forever.engine_data import DEFAULT_BUILDS, TALENT_EFFECTS, TALENT_RANK_EFFECTS
    names = {}
    for cls, trees in json.loads((ROOT / "data/forever_talents_all.json").read_text(encoding="utf-8"))["classes"].items():
        for tree in trees:
            for t in tree["talents"]:
                names[str(t["id"])] = f"{cls.title()} {tree['name']}: {t['name']}"
    builds = collections.defaultdict(list)
    for spec, build in DEFAULT_BUILDS.items():
        for tid, rank in build.items():
            if rank: builds[str(tid)].append(spec)
    for spec, build in (("paladin-protection", sim.PROTECTION_BUILD), ("paladin-retribution", sim.RETRIBUTION_BUILD)):
        for tid, rank in build.items():
            if rank: builds[str(tid)].append(spec)
    modeled = {str(k) for k in TALENT_EFFECTS} | {str(k) for k in TALENT_RANK_EFFECTS}
    return names, builds, modeled


def report(old_build, new_build, old, new):
    lines = [f"# Forever client update: {old_build} -> {new_build}", ""]
    review = []
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    changed_tables = [t for t in TABLES if digest(old / f"{t}.csv") != digest(new / f"{t}.csv")]
    lines += ["## Client tables", "", "Changed: " + (", ".join(changed_tables) or "none"), ""]

    from tools.wago_audit import Snapshot, build_evidence
    raw = new.parent / f"{new.name}-audit"
    raw.mkdir(exist_ok=True)
    for t in SPELL_TABLES:
        (raw / f"{t}.csv").write_bytes((new / f"{t}.csv").read_bytes())
    current = json.loads((ROOT / "data/wago_verified.json").read_text(encoding="utf-8"))
    fresh = build_evidence(Snapshot(raw))
    lines += ["## Reviewed spell values (data/wago_verified.json)", ""]
    diffs = 0
    for name, rec in current["spells"].items():
        a, b = rec["fields"], fresh["spells"][name]["fields"]
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                lines.append(f"- **{name}** `{k}`: {a.get(k)} -> {b.get(k)}"); diffs += 1
    for node, rec in current["talents"].items():
        if rec["fields"] != fresh["talents"][node]["fields"]:
            lines.append(f"- talent node {node}: {rec['fields']} -> {fresh['talents'][node]['fields']}"); diffs += 1
    if not diffs:
        lines.append("No changes.")
    lines.append("")

    ids = engine_spell_ids()
    spell_names = {r["ID"]: r["Name_lang"] for r in rows(new, "SpellName")}
    lines += ["## Other engine-referenced spells", ""]
    found = 0
    for table in ("SpellEffect", "SpellPower", "SpellCooldowns", "SpellMisc", "SpellLevels"):
        a, b = grouped(old, table, "SpellID"), grouped(new, table, "SpellID")
        for sid in sorted(ids, key=int):
            ra = sorted((r for r in a.get(sid, [])), key=lambda r: r.get("EffectIndex", ""))
            rb = sorted((r for r in b.get(sid, [])), key=lambda r: r.get("EffectIndex", ""))
            if len(ra) != len(rb):
                lines.append(f"- {spell_names.get(sid, sid)} ({sid}) {table}: {len(ra)} -> {len(rb)} rows"); found += 1
                review.append(f"{spell_names.get(sid, sid)}: {table} row count changed")
                continue
            for x, y in zip(ra, rb):
                d = {k: (x[k], y.get(k)) for k in x if k != "ID" and x[k] != y.get(k)}
                if d:
                    lines.append(f"- {spell_names.get(sid, sid)} ({sid}) {table}: {d}"); found += 1
    if not found:
        lines.append("No changes.")
    lines.append("")

    names, builds, modeled = talent_usage()
    sa, sb = talent_signatures(old), talent_signatures(new)
    old_spell_names = {r["ID"]: r["Name_lang"] for r in rows(old, "SpellName")}
    for node, parts in list(sa.items()) + list(sb.items()):  # fall back to the client's spell name
        if node not in names and parts and parts[0][1] in (spell_names | old_spell_names):
            names[node] = (spell_names | old_spell_names)[parts[0][1]]
    lines += ["## Talent tree", ""]
    for label, nodes in (("Removed", sorted(set(sa) - set(sb))), ("Added", sorted(set(sb) - set(sa))),
                         ("Changed", sorted(k for k in sa if k in sb and sa[k] != sb[k]))):
        for node in nodes:
            used = builds.get(node, [])
            flag = []
            if used: flag.append("in default build: " + ", ".join(used))
            if node in modeled: flag.append("modeled")
            lines.append(f"- {label}: {names.get(node, 'node ' + node)} ({node})" + (f" — **{'; '.join(flag)}**" if flag else ""))
            if flag: review.append(f"{label} talent {names.get(node, node)} ({'; '.join(flag)})")
    if not (set(sa) ^ set(sb)) and all(sa[k] == sb[k] for k in sa if k in sb):
        lines.append("No changes.")
    lines.append("")

    from forever.all_specs import ITEMS
    ia, ib = {r["ID"]: r for r in rows(old, "ItemSparse")}, {r["ID"]: r for r in rows(new, "ItemSparse")}
    lines += ["## Catalog items", ""]
    item_changes = 0
    removed = []
    for iid in sorted(ITEMS):
        a, b = ia.get(str(iid)), ib.get(str(iid))
        if a and not b:
            lines.append(f"- Removed from client: {ITEMS[iid]['name']} ({iid})"); removed.append(iid); item_changes += 1
        elif a and b:
            d = {k: (a[k], b.get(k)) for k in a if k not in ITEM_IGNORED and a[k] != b.get(k)}
            if d:
                lines.append(f"- {ITEMS[iid]['name']} ({iid}): {d}"); item_changes += 1
                review.append(f"Item {ITEMS[iid]['name']} changed in the client (catalog stats not auto-updated)")
    new_items = [r for k, r in ib.items() if k not in ia and r.get("ItemLevel", "0").isdigit()
                 and int(r["ItemLevel"]) >= 55 and int(r.get("OverallQualityID") or 0) >= 2]
    for r in new_items[:50]:
        lines.append(f"- New level-55+ item: {r['Display_lang']} ({r['ID']}, ilvl {r['ItemLevel']})")
    if new_items:
        review.append(f"{len(new_items)} new level-55+ items are not in the catalog yet")
    if not item_changes and not new_items:
        lines.append("No changes.")
    lines += ["", "## Needs review", ""] + ([f"- [ ] {x}" for x in review] or ["Nothing flagged: the automatic refresh covers this build."])
    return "\n".join(lines) + "\n", raw, removed, bool(changed_tables)


def apply(new_build, raw, new, removed):
    for tool in ("tools/wago_audit.py", "tools/build_item_class_restrictions.py"):
        path = ROOT / tool
        path.write_text(re.sub(r'^BUILD = "[^"]+"', f'BUILD = "{new_build}"', path.read_text(encoding="utf-8"), count=1, flags=re.M), encoding="utf-8")
    subprocess.run([sys.executable, "tools/wago_audit.py", "--raw", str(raw), "--output", "data/wago_verified.json"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "tools/build_item_class_restrictions.py", "--raw", str(new / "ItemSparse.csv")], cwd=ROOT, check=True)
    if removed:
        path = ROOT / "data/forever_removed_item_ids.json"
        ids = sorted(set(json.loads(path.read_text(encoding="utf-8"))) | set(removed))
        path.write_text(json.dumps(ids) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("new_build")
    parser.add_argument("--apply", action="store_true", help="re-pin client data to the new build")
    parser.add_argument("--out", type=Path, default=ROOT / "build-update-report.md")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "wago")
    args = parser.parse_args()
    from tools.wago_audit import BUILD as old_build
    if old_build == args.new_build:
        print(f"Already pinned to {old_build}.")
        return
    old, new = fetch(old_build, args.cache), fetch(args.new_build, args.cache)
    text, raw, removed, client_changed = report(old_build, args.new_build, old, new)
    args.out.write_text(text, encoding="utf-8")
    print(text)
    # Only re-pin when a table the sim reads changed; identical builds keep the current pin.
    if args.apply and client_changed:
        apply(args.new_build, raw, new, removed)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"client_changed={'true' if client_changed else 'false'}\n")


if __name__ == "__main__":
    main()
