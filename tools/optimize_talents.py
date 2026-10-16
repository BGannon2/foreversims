"""Sim-optimize a spec variant's 51 talent points around its defining core.

Usage: python tools/optimize_talents.py VARIANT [VARIANT ...] [--iterations N] [--workers N] [--write]
       python tools/optimize_talents.py --all [--write]

A variant (forever/engine_data.VARIANTS or forever/sim.PALADIN_VARIANTS) defines a "core": required
talents and/or a minimum number of points in a tree. The optimizer:

1. Greedy fill: adds one point at a time, simulating every legal +1 and keeping the best. While the
   core isn't met, only moves toward it are allowed (points in the core's trees, then the required
   talents as soon as they're legal).
2. Swap pass: tries moving single points between talents (keeping the build legal and the core met)
   and keeps any move that sims better, until none does.
3. Keeps the better of that result and the parent spec's default build, if the default meets the core.

Every candidate is simulated with the same seed (common random numbers), so comparisons between
candidates aren't drowned in sampling noise. The objective is mean DPS (TPS for tanks). Candidate
evaluations run in parallel; this is meant for a many-core pod, not a laptop.

--write stores each result in data/variant_talents.json, which forever/engine_data.py and
forever/sim.py load over the placeholder (parent) builds.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "variant_talents.json"
MAX_POINTS, PER_TIER = 51, 5


# ---- engines ---------------------------------------------------------------------------------
def variant_info(vid):
    from forever.engine_data import SPEC_MAP, VARIANTS
    from forever.sim import PALADIN_VARIANTS
    if vid in VARIANTS:
        v = VARIANTS[vid]; spec = SPEC_MAP[v["parent"]]
        return {"engine": "shared", "variant": v, "class": spec["class_name"].lower(), "tank": spec["role"] == "tank"}
    if vid in PALADIN_VARIANTS:
        v = PALADIN_VARIANTS[vid]
        return {"engine": "paladin", "variant": v, "class": "paladin", "tank": v["parent"] == "protection"}
    raise SystemExit(f"Unknown variant {vid}")


def talent_trees(info):
    """[(tree name, [talent dict])] in the engine's own talent data."""
    if info["engine"] == "paladin":
        from forever.sim import TALENT_DATA
        return [(t["name"], t["talents"]) for t in TALENT_DATA["trees"]]
    data = json.loads((ROOT / "data" / "forever_talents_all.json").read_text(encoding="utf-8"))
    return [(t["name"], t["talents"]) for t in data["classes"][info["class"]]]


_CACHE = {}


def evaluate(args):
    """Mean DPS/TPS of one talent build (runs in a worker process)."""
    vid, build, iterations = args
    info = _CACHE.get(vid) or _CACHE.setdefault(vid, variant_info(vid))
    key = "tps" if info["tank"] else "dps"
    if info["engine"] == "paladin":
        from forever.sim import TALENTS, preset, simulate, validate
        p = preset(info["variant"]["parent"], vid)
        p["talents"] = {t: 0 for t in TALENTS} | build
        p.update(iterations=iterations, seed=1717)
        return simulate(validate(p))["metrics"][key]["mean"]
    from forever.all_specs import public_specs, simulate_spec
    from server import default_request
    spec = next(s for s in public_specs() if s["id"] == info["variant"]["parent"])
    req = default_request(spec, iterations=iterations, seed=1717, variant=vid, talents=build)
    return simulate_spec(req)["metrics"][key]["mean"]


# ---- legality --------------------------------------------------------------------------------
def modeled_talents(info):
    """Talent ids the engine gives an effect (used to break ties between equal-scoring points)."""
    if info["engine"] == "paladin":
        import re
        src = (ROOT / "forever" / "sim.py").read_text(encoding="utf-8")
        return set(re.findall(r"rank\('?(\d{6})'?\)", src)) | {k for k in re.findall(r"'(\d{6})'", src)}
    from forever.engine_data import TALENT_EFFECTS
    return {k for k, v in TALENT_EFFECTS.items() if v}


class Tree:
    def __init__(self, info):
        self.trees = talent_trees(info)
        self.tal = {str(t["id"]): (name, t) for name, ts in self.trees for t in ts}
        self.modeled = modeled_talents(info)

    def legal(self, b):
        if sum(b.values()) > MAX_POINTS: return False
        for tid, r in b.items():
            if not r: continue
            if tid not in self.tal: return False
            tree, t = self.tal[tid]
            if r > len(t["ranks"]): return False
            before = sum(rr for k, rr in b.items() if rr and self.tal.get(k, ("", {}))[0] == tree and self.tal[k][1]["row"] < t["row"])
            if before < t["row"] * PER_TIER: return False
            if any(b.get(str(q["id"]), 0) < q["qty"] for q in t["requires"]): return False
        return True

    def tree_points(self, b, tree):
        return sum(r for k, r in b.items() if self.tal[k][0] == tree)


def required(tree, core):
    """Core talents plus their prerequisite chains, as {id: rank}."""
    need = dict(core.get("talents", {}))
    stack = list(need)
    while stack:
        t = tree.tal[stack.pop()][1]
        for q in t["requires"]:
            k = str(q["id"])
            if need.get(k, 0) < q["qty"]: need[k] = q["qty"]; stack.append(k)
    return need


def core_met(tree, core, b):
    return all(b.get(k, 0) >= r for k, r in required(tree, core).items()) and \
        all(tree.tree_points(b, t) >= n for t, n in core.get("tree_min", {}).items())


def core_moves(tree, core, b):
    """Talent ids a point may go to while the core is unmet: required talents once legal, else
    any talent in a tree that still needs points for the core."""
    need = required(tree, core)
    ready = [k for k, r in need.items() if b.get(k, 0) < r and tree.legal({**b, k: b.get(k, 0) + 1})]
    if ready: return ready
    trees = {tree.tal[k][0] for k, r in need.items() if b.get(k, 0) < r}
    trees |= {t for t, n in core.get("tree_min", {}).items() if tree.tree_points(b, t) < n}
    return [k for k, (name, _) in tree.tal.items() if name in trees]


# ---- search ----------------------------------------------------------------------------------
def optimize(vid, iterations, pool, log=print):
    info = variant_info(vid); tree = Tree(info); core = info["variant"].get("core", {})
    score = lambda builds: list(pool.map(evaluate, [(vid, b, iterations) for b in builds], chunksize=1))
    build = {}
    while sum(build.values()) < MAX_POINTS:
        pool_ids = core_moves(tree, core, build) if not core_met(tree, core, build) else list(tree.tal)
        cands = [{**build, k: build.get(k, 0) + 1} for k in pool_ids]
        cands = [c for c in cands if tree.legal(c)]
        if not cands:  # nothing legal toward the core: open up every tree
            cands = [c for c in ({**build, k: build.get(k, 0) + 1} for k in tree.tal) if tree.legal(c)]
            if not cands: break
        vals = score(cands)
        top = max(vals)
        # Near-ties (within 0.05%, i.e. noise) are usually filler points that unlock a deeper tier:
        # prefer a talent the engine models, then the tree that already has the most points.
        def tiebreak(i):
            k = next(k for k in cands[i] if cands[i][k] != build.get(k, 0))
            return (vals[i] >= top * 0.9995, k in tree.modeled, tree.tree_points(build, tree.tal[k][0]), vals[i])
        best = max(range(len(cands)), key=tiebreak)
        build = cands[best]
        log(f"{vid}: {sum(build.values()):2d} pts  {vals[best]:9.2f}")
    if not core_met(tree, core, build):
        raise RuntimeError(f"{vid}: greedy fill could not meet the core {core}")
    current = score([build])[0]
    improved = True
    while improved:  # swap pass: move one point between talents
        improved = False
        cands = []
        for src, r in build.items():
            if not r: continue
            for dst in tree.tal:
                if dst == src: continue
                c = {**build, src: r - 1, dst: build.get(dst, 0) + 1}
                c = {k: v for k, v in c.items() if v}
                if tree.legal(c) and core_met(tree, core, c): cands.append(c)
        if not cands: break
        vals = score(cands)
        best = max(range(len(cands)), key=lambda i: vals[i])
        if vals[best] > current * 1.0005:  # ignore sub-0.05% "gains" (rounding-level noise)
            build, current, improved = cands[best], vals[best], True
            log(f"{vid}: swap -> {current:9.2f}")
    parent = {k: v for k, v in info["variant"]["talents"].items() if v}
    if tree.legal(parent) and core_met(tree, core, parent) and sum(parent.values()) == MAX_POINTS:
        pv = score([parent])[0]
        if pv > current: build, current = parent, pv; log(f"{vid}: parent build is better ({pv:.2f})")
    return {k: v for k, v in sorted(build.items()) if v}, current


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("variants", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--iterations", type=int, default=300)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    from forever.engine_data import VARIANTS
    from forever.sim import PALADIN_VARIANTS
    todo = list(VARIANTS) + list(PALADIN_VARIANTS) if args.all else args.variants
    if not todo: ap.error("name variants or pass --all")
    saved = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for vid in todo:
            build, value = optimize(vid, args.iterations, pool)
            print(f"== {vid}: {value:.2f}  {json.dumps(build)}", flush=True)
            saved[vid] = {"talents": build, "value": round(value, 2), "iterations": args.iterations}
            if args.write:
                OUT.write_text(json.dumps(saved, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
