"""Explicit role selection, topology checks and no-write preview for the duck recipe.

Works only on a real inspect_room answer. Extras and duplicates are allowed in the room
but never guessed: with several candidates for a role the operator must name the item.
Nothing here writes. Habbogz only, no habbo.es claim, no room or furni creation.
"""
import hashlib
import json
import math
from .core import ModelError
from .native import PROTOCOL, valid_manifest, apply_classic
from .duck_planner import DUCK_BASES

ROLES = ('duck', 'start', 'repeat', 'chase', 'collision', 'teleport')
STACKS = (('repeat', 'chase'), ('collision', 'teleport'))   # (lower, upper) on one tile
EPS = 1e-6

def _pid(v):
    return type(v) is int and v > 0

def _check_room(ins, room, owner):
    if not _pid(room) or not _pid(owner):
        raise ModelError('Operator must give expected room and owner ids')
    if not isinstance(ins, dict) or ins.get('room_id') != room:
        raise ModelError('Inspected room differs from expected room')
    if ins.get('owner_id') != owner:
        raise ModelError('Room owner missing or differs from expected owner')
    if ins.get('room_state') != 'hide':
        raise ModelError('Real room state must be hide')
    if ins.get('private_acceptance_room') is not True:
        raise ModelError('Room privacy indicator not confirmed')
    items = ins.get('items')
    if not isinstance(items, list) or not items:
        raise ModelError('Inventory missing')
    seen = {}
    for it in items:
        if not isinstance(it, dict) or not _pid(it.get('id')) or not _pid(it.get('base_id')):
            raise ModelError('Every item needs exact id and base')
        pos = it.get('position')
        if not isinstance(pos, list) or len(pos) != 3 or any(type(n) not in (int, float) or isinstance(n, bool) or not math.isfinite(n) for n in pos):
            raise ModelError('Every item needs a finite position')
        if it['id'] in seen:
            raise ModelError('Duplicate item id in inventory')
        seen[it['id']] = it
    return items, seen

def choose_roles(items, by_id, bases, selection):
    chosen = {}
    if selection is not None:
        if not isinstance(selection, dict) or set(selection) != set(ROLES):
            raise ModelError('Selection must name all six roles')
        for role in ROLES:
            iid = selection[role]
            if not _pid(iid) or iid not in by_id:
                raise ModelError('Selected item for %s is not in the room' % role)
            if by_id[iid]['base_id'] != bases[role]:
                raise ModelError('Selected item for %s has the wrong base' % role)
            chosen[role] = by_id[iid]
        if len({x['id'] for x in chosen.values()}) != 6:
            raise ModelError('One item cannot hold two roles')
        return chosen
    for role in ROLES:
        cands = [i for i in items if i['base_id'] == bases[role]]
        if len(cands) != 1:
            raise ModelError('Role %s has %d candidates (%s); name the item explicitly' % (role, len(cands), sorted(c['id'] for c in cands)))
        chosen[role] = cands[0]
    return chosen

def _tile(it):
    x, y, _ = it['position']
    if x != int(x) or y != int(y):
        raise ModelError('Fixed recipe items must sit on whole tiles')
    return (int(x), int(y))

def check_topology(chosen, items):
    tiles = {r: _tile(chosen[r]) for r in ROLES if r != 'duck'}
    for low, up in STACKS:
        if tiles[low] != tiles[up]:
            raise ModelError('%s and %s must be stacked on one tile' % (low, up))
        if chosen[up]['position'][2] - chosen[low]['position'][2] <= EPS:
            raise ModelError('%s must sit above %s' % (up, low))
    if tiles['repeat'] == tiles['collision']:
        raise ModelError('The two stacks must be on different tiles')
    if tiles['start'] in (tiles['repeat'], tiles['collision']):
        raise ModelError('Start tile must differ from both stacks')
    duck = chosen['duck']['position']
    if (int(math.floor(duck[0])), int(math.floor(duck[1]))) == tiles['start']:
        raise ModelError('Duck is on the start tile')
    stack_members = {tiles['repeat']: {'repeat', 'chase'}, tiles['collision']: {'collision', 'teleport'}}
    role_of = {v['id']: r for r, v in chosen.items()}
    for it in items:
        if it['id'] in role_of:
            continue
        try:
            t = _tile(it)
        except ModelError:
            continue    # extras may be off-grid; they only matter on stack or start tiles
        if t in stack_members or t == tiles['start']:
            raise ModelError('Extra item %d shares a tile with the recipe; refusing' % it['id'])
    return tiles

def plan_roles(inspection, *, expected_room_id, expected_owner_id, bases=None, selection=None):
    bases = dict(bases or DUCK_BASES)
    if set(bases) != set(ROLES) or any(not _pid(b) for b in bases.values()) or len(set(bases.values())) != 6:
        raise ModelError('Six distinct role bases required')
    items, by_id = _check_room(inspection, expected_room_id, expected_owner_id)
    chosen = choose_roles(items, by_id, bases, selection)
    tiles = check_topology(chosen, items)
    duck, start = chosen['duck']['id'], chosen['start']['id']
    steps = [
        {'role': 'repeat', 'box_id': chosen['repeat']['id'], 'native': {'cycles': 1}, 'expected': {'cycles': 1}},
        {'role': 'chase', 'box_id': chosen['chase']['id'], 'native': {'selected_items': [duck]}, 'expected': {'selected_items': [duck]}},
        {'role': 'collision', 'box_id': chosen['collision']['id'], 'native': {}, 'expected': {}},
        {'role': 'teleport', 'box_id': chosen['teleport']['id'], 'native': {'selected_items': [start], 'delay': 0}, 'expected': {'selected_items': [start], 'delay': 0}},
    ]
    ordered = sorted(items, key=lambda i: i['id'])
    manifest = valid_manifest({
        'protocol': PROTOCOL, 'target': 'habbogz', 'room_id': expected_room_id, 'private_acceptance_room': True,
        'items': [{'id': i['id'], 'base_id': i['base_id'], 'position': list(i['position'])} for i in ordered],
        'steps': steps, 'mobile_item_ids': [duck], 'room_state': 'hide', 'owner_id': expected_owner_id,
        'role_items': {r: chosen[r]['id'] for r in ROLES}}, require_roles=True)
    ignored = [i['id'] for i in ordered if i['id'] not in {v['id'] for v in chosen.values()}]
    preview = {
        'will_write': False, 'room_id': expected_room_id, 'owner_id': expected_owner_id, 'room_state': 'hide',
        'roles': {r: chosen[r]['id'] for r in ROLES}, 'selection_was_explicit': selection is not None,
        'stack_tiles': {'repeat_chase': list(tiles['repeat']), 'collision_teleport': list(tiles['collision'])},
        'start_tile': list(tiles['start']), 'ignored_items': ignored,
        'planned_settings': {s['role']: s['native'] for s in steps},
    }
    # Anchored to the whole canonical context: every item's id, base and position (only the
    # duck's position is left out, it is the one item allowed to move), room, owner, state,
    # role bases and selection. Any other drift between preview and apply changes it.
    duck_id = chosen['duck']['id']
    canonical = {
        'preview': preview, 'bases': {r: bases[r] for r in ROLES},
        'inventory': [{'id': i['id'], 'base_id': i['base_id'], 'position': None if i['id'] == duck_id else list(i['position'])} for i in ordered],
    }
    preview['fingerprint'] = hashlib.sha256(json.dumps(canonical, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
    return manifest, preview

def select_and_apply(executor, *, expected_room_id, expected_owner_id, bases=None, selection=None, expected_fingerprint=None):
    """Inspect, plan, require the operator-approved preview fingerprint if given, apply."""
    ins = executor.call('inspect_room', expected_room_id)
    manifest, preview = plan_roles(ins, expected_room_id=expected_room_id, expected_owner_id=expected_owner_id, bases=bases, selection=selection)
    if expected_fingerprint is not None and preview['fingerprint'] != expected_fingerprint:
        raise ModelError('Room differs from the previewed plan; no writes issued')
    report = apply_classic(manifest, executor, require_roles=True)
    report['preview'] = preview
    return report
