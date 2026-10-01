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
    return tags


def select(only):
    """Spec ids matching any of the given tags; exits with a message on an unknown tag."""
    tags = spec_tags()
    wanted = {t.lower() for t in only}
    unknown = wanted - set().union(*tags.values())
    if unknown:
        sys.exit(f"Unknown tag(s): {', '.join(sorted(unknown))}. Use a spec id, class, role (tank/dps) or style (melee/ranged/spell).")
    return {sid for sid, t in tags.items() if t & wanted}
