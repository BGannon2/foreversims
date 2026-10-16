"""Spec selection by tag, shared by the benchmark and BiS tools.

A tag is a spec id (druid-feral-tank), a class (druid, paladin), a role (tank, dps) or a
style (melee, ranged, spell); several tags select the union of the specs they match.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def spec_tags():
    """Every spec id (shared engine + Paladin engine) -> the tags that select it."""
    from forever.all_specs import public_specs
    tags = {s["id"]: {s["id"], s["class_name"].lower(), s["role"], s["style"]} for s in public_specs()}
    tags["paladin-protection"] = {"paladin-protection", "paladin", "tank", "melee"}
    tags["paladin-retribution"] = {"paladin-retribution", "paladin", "dps", "melee"}
    # Spec variants: tagged by their own id ("parent/variant" and the bare variant name), plus their
    # parent's tags and "variant", so e.g. --only variant reruns just the variants.
    from forever.engine_data import VARIANTS
    from forever.sim import PALADIN_VARIANTS
    parents = {f"{v['parent']}/{vid}": v["parent"] for vid, v in VARIANTS.items()}
    parents |= {f"paladin-{v['parent']}/{vid}": f"paladin-{v['parent']}" for vid, v in PALADIN_VARIANTS.items()}
    for key, parent in parents.items():
        tags[key] = (tags[parent] - {parent}) | {key, key.split("/")[1], "variant"}
    return tags


def select(only):
    """Spec ids matching any of the given tags; exits with a message on an unknown tag."""
    tags = spec_tags()
    wanted = {t.lower() for t in only}
    unknown = wanted - set().union(*tags.values())
    if unknown:
        sys.exit(f"Unknown tag(s): {', '.join(sorted(unknown))}. Use a spec id, class, role (tank/dps) or style (melee/ranged/spell).")
    return {sid for sid, t in tags.items() if t & wanted}
