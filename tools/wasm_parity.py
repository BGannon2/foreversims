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


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='forever-wasm-parity-') as temp:
        path = Path(temp) / 'cases.json'
        path.write_text(json.dumps(list(cases())), encoding='utf-8')
        sys.exit(subprocess.call(['node', str(ROOT / 'tools/wasm_parity.mjs'), str(path)], cwd=ROOT))
