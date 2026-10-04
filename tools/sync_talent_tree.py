"""Sync data/forever_talents_all.json's tree layout to a Forever client build.

Usage: python tools/sync_talent_tree.py BUILD [--cache DIR] [--dry-run]

For every talent node already in the file, the client's TraitNode / TraitNodeEntry / TraitEdge
rows decide its row, column, rank count and prerequisites. Nodes the client added to a spec's
tree are appended with the client's spell name and raw tooltip text; nodes the client removed
are dropped. Existing names, icons and tooltip descriptions are kept unless the node now points
at a different spell (a talent replaced in place), in which case they're taken from the client.
Prints every change so it can be reviewed before committing.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TALENTS = ROOT / "data" / "forever_talents_all.json"
TABLES = ("TraitNode", "TraitNodeEntry", "TraitNodeXTraitNodeEntry", "TraitDefinition", "TraitEdge", "SpellName", "Spell")
GRID = 600  # client units between talent rows / columns


def load(build, cache):
    from urllib.request import Request, urlopen
    folder = cache / build
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for table in TABLES:
        path = folder / f"{table}.csv"
        if not path.is_file():
            req = Request(f"https://wago.tools/db2/{table}/csv?build={build}", headers={"User-Agent": "foreversims-talent-sync"})
            path.write_bytes(urlopen(req, timeout=120).read())
        out[table] = list(csv.DictReader(path.open(encoding="utf-8")))
    return out


def tooltip(text, ranks):
    """Client tooltip with $ tokens stripped to something readable (exact values need the curves)."""
    text = re.sub(r"\$\?[^\[]*\[([^\]]*)\]\[[^\]]*\]", r"\1", text or "")
    text = re.sub(r"\$\{[^}]*\}|\$[a-zA-Z]?\d*[a-zA-Z]\d*", "X", text)
    return {str(r): text.strip() for r in range(1, ranks + 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("build")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "wago")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    t = load(args.build, args.cache)
    nodes = {r["ID"]: r for r in t["TraitNode"]}
    entry_of = {r["TraitNodeID"]: r["TraitNodeEntryID"] for r in t["TraitNodeXTraitNodeEntry"]}
    entries = {r["ID"]: r for r in t["TraitNodeEntry"]}
    defs = {r["ID"]: r for r in t["TraitDefinition"]}
    names = {r["ID"]: r["Name_lang"] for r in t["SpellName"]}
    descs = {r["ID"]: r.get("Description_lang", "") for r in t["Spell"]}

    def info(node_id):
        e = entries.get(entry_of.get(node_id, ""))
        d = defs.get(e["TraitDefinitionID"]) if e else None
        return (int(e["MaxRanks"]), d["SpellID"]) if d else (None, None)

    def shown_name(node_id):
        """The name the talent UI shows: the trait's override name, else its spell's name."""
        e = entries.get(entry_of.get(node_id, ""))
        d = defs.get(e["TraitDefinitionID"]) if e else None
        return (d.get("OverrideName_lang") or names.get(d["SpellID"])) if d else None

    # Prerequisite edges are Type 2 (and the odd Type 3), Left -> Right. A few pairs also appear
    # pointing back up the tree; a prerequisite never sits below what it unlocks, so those are skipped.
    parents = {}
    for edge in t["TraitEdge"]:
        up, down = nodes.get(edge["LeftTraitNodeID"]), nodes.get(edge["RightTraitNodeID"])
        if edge["Type"] in ("2", "3") and up and down and int(up["PosY"]) <= int(down["PosY"]):
            parents.setdefault(edge["RightTraitNodeID"], []).append(edge["LeftTraitNodeID"])

    data = json.loads(TALENTS.read_text(encoding="utf-8"))
    changes = []
    for cls, trees in data["classes"].items():
        for tree in trees:
            known = [x for x in tree["talents"] if str(x["id"]) in nodes]
            if not known:
                continue
            tree_id = nodes[str(known[0]["id"])]["TraitTreeID"]
            # This spec's grid origin: the most common offset between client position and stored cell.
            ox = Counter(int(nodes[str(x["id"])]["PosX"]) - GRID * x["col"] for x in known).most_common(1)[0][0]
            oy = Counter(int(nodes[str(x["id"])]["PosY"]) - GRID * x["row"] for x in known).most_common(1)[0][0]
            cell = lambda n: (round((int(n["PosY"]) - oy) / GRID), round((int(n["PosX"]) - ox) / GRID))
            in_spec = {nid for nid, n in nodes.items() if n["TraitTreeID"] == tree_id and 0 <= cell(n)[1] < 4
                       and 0 <= cell(n)[0] < 11 and info(nid)[0]}
            kept = []
            for tal in tree["talents"]:
                nid = str(tal["id"])
                if nid not in in_spec:
                    changes.append(f"{cls}/{tree['name']}: removed {tal['name']} ({nid})")
                    continue
                n = nodes[nid]; ranks, spell = info(nid)
                row, col = cell(n)
                req = [{"id": int(p), "qty": info(p)[0]} for p in sorted(parents.get(nid, [])) if p in in_spec]
                new = dict(tal, row=row, col=col, ranks=[None] * ranks, requires=req)
                if shown_name(nid) and shown_name(nid) != tal["name"]:
                    new.update(name=shown_name(nid), descriptions=tooltip(descs.get(spell), ranks))
                elif ranks != len(tal["ranks"]):
                    new["descriptions"] = {k: v for k, v in tal["descriptions"].items() if int(k) <= ranks} or tooltip(descs.get(spell), ranks)
                diff = [k for k in ("name", "row", "col", "ranks", "requires") if new[k] != tal[k]]
                if diff:
                    changes.append(f"{cls}/{tree['name']}: {tal['name']} ({nid}) " + ", ".join(
                        f"{k} {len(tal[k]) if k == 'ranks' else tal[k]} -> {len(new[k]) if k == 'ranks' else new[k]}" for k in diff))
                kept.append(new)
            for nid in sorted(in_spec - {str(x["id"]) for x in tree["talents"]}):
                n = nodes[nid]; ranks, spell = info(nid)
                tal = {"id": int(nid), "row": cell(n)[0], "col": cell(n)[1],
                       "icon": "inv_misc_questionmark", "name": shown_name(nid) or f"Talent {nid}", "ranks": [None] * ranks,
                       "requires": [{"id": int(p), "qty": info(p)[0]} for p in sorted(parents.get(nid, [])) if p in in_spec],
                       "descriptions": tooltip(descs.get(spell), ranks)}
                changes.append(f"{cls}/{tree['name']}: added {tal['name']} ({nid}) row {tal['row']} col {tal['col']}, {ranks} ranks")
                kept.append(tal)
            tree["talents"] = sorted(kept, key=lambda x: (x["row"], x["col"]))
    print("\n".join(changes) or "No tree changes.")
    if changes and not args.dry_run:
        TALENTS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {TALENTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
