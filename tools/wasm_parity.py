"""Compare the shipped browser binary and split-worker merges against Python."""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forever.all_specs import public_specs, simulate_spec  # noqa: E402
from forever.sim import preset, simulate  # noqa: E402
from server import default_request  # noqa: E402


def cases():
    for spec in public_specs():
        base = default_request(spec, iterations=3, duration=90, seed=917)
        variants = [base, {**base, 'race': spec['races'][-1], 'targets': 3, 'boss_type': 'beast'},
                    {**base, 'gear': [], 'gear_slots': [], 'enchants': [], 'buffs': [], 'consumables': [], 'talents': {}, 'pet_family': 'none'}]
        for i, request in enumerate(variants):
            yield {'name': f'{spec["id"]}/{i}', 'kind': 'spec', 'request': request, 'python': simulate_spec(request)}
    for spec in ('protection', 'retribution'):
        for race, creature in [('Human', 'none'), ('Dwarf', 'beast'), ('Undead', 'demon')]:
            request = copy.deepcopy(preset(spec))
            request.update(iterations=3, duration=90, seed=917, race=race)
            request['encounter']['boss_type'] = creature
            yield {'name': f'paladin-{spec}/{race}', 'kind': 'paladin', 'request': request, 'python': simulate(request)}
    # Partial ranks specifically exercise the non-linear DB2 curve path. These
    # are engine fixtures, not recommended complete player builds.
    partials = {
        'warrior-fury': {'105932': 1},
        'rogue-combat': {'105741': 1, '105708': 2, '105716': 3},
        'druid-balance': {'104925': 2, '104936': 3},
        'shaman-elemental': {'104765': 2, '104759': 2, '104758': 1},
        'hunter-marksmanship': {'105001': 2, '110870': 1},
        'mage-frost': {'105768': 2, '105803': 1},
        'priest-shadow': {'105843': 2, '105853': 3},
        'warlock-destruction': {'105887': 2, '105879': 2, '105877': 2, '105917': 2},
    }
    specs = {s['id']: s for s in public_specs()}
    for sid, talents in partials.items():
        request = default_request(specs[sid], iterations=3, duration=90, seed=917, talents=talents)
        yield {'name': f'{sid}/partial-ranks', 'kind': 'spec', 'request': request, 'python': simulate_spec(request)}


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='forever-wasm-parity-') as temp:
        path = Path(temp) / 'cases.json'
        path.write_text(json.dumps(list(cases())), encoding='utf-8')
        sys.exit(subprocess.call(['node', str(ROOT / 'tools/wasm_parity.mjs'), str(path)], cwd=ROOT))
