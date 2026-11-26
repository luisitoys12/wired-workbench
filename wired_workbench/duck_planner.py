"""Plan the duck recipe from a real room inspection. Fails closed, writes nothing.

Item and room ids are never constants here. They come from the executor's own
inspect_room answer. Only item type (base) ids are catalog data, and the caller can
override them. This is not a room builder: it configures furnis that are already
present. Habbogz only. No claim of habbo.es compatibility.
"""
import math
from .core import ModelError
from .native import PROTOCOL, valid_manifest, apply_classic

# Catalog data: item type -> role. Observed in the Habbogz acceptance run, not portable.
DUCK_BASES = {'duck': 179, 'start': 3666, 'repeat': 3671, 'chase': 5055, 'collision': 5050, 'teleport': 3674}

def _int(v):
    return type(v) is int and v > 0

def plan_duck(inspection, *, expected_room_id, expected_owner_id, bases=None):
    bases = dict(bases or DUCK_BASES)
    if set(bases) != set(DUCK_BASES) or any(not _int(b) for b in bases.values()) or len(set(bases.values())) != 6:
        raise ModelError('Six distinct role bases required')
    if not _int(expected_room_id) or not _int(expected_owner_id):
        raise ModelError('Expected room and owner ids must be given by the operator')
    if not isinstance(inspection, dict):
        raise ModelError('Inspection missing')
    if inspection.get('room_id') != expected_room_id:
        raise ModelError('Inspected room differs from expected room')
    if inspection.get('owner_id') != expected_owner_id:
        raise ModelError('Room owner missing or differs from expected owner')
    if inspection.get('room_state') != 'hide':
        raise ModelError('Real room state must be hide')
    if inspection.get('private_acceptance_room') is not True:
        raise ModelError('Room privacy indicator not confirmed by inspection')
    items = inspection.get('items')
    if not isinstance(items, list):
        raise ModelError('Inventory missing')
    by_base = {}
    ids = set()
    for item in items:
        if not isinstance(item, dict) or not _int(item.get('id')) or not _int(item.get('base_id')):
            raise ModelError('Every item needs exact id and base')
        pos = item.get('position')
        if not isinstance(pos, list) or len(pos) != 3 or any(type(n) not in (int, float) or not math.isfinite(n) for n in pos):
            raise ModelError('Every item needs a finite position')
        if item['id'] in ids:
            raise ModelError('Duplicate item id')
        ids.add(item['id'])
        by_base.setdefault(item['base_id'], []).append(item)
    if len(items) != 6:
        raise ModelError('Room must hold exactly the six recipe items; refusing to guess among extras')
    found = {}
    for role, base in bases.items():
        match = by_base.get(base, [])
        if len(match) != 1:
            raise ModelError('Role %s needs exactly one item of its base, found %d' % (role, len(match)))
        found[role] = match[0]
    duck, start = found['duck']['id'], found['start']['id']
    steps = [
        {'role': 'repeat', 'box_id': found['repeat']['id'], 'native': {'cycles': 1}, 'expected': {'cycles': 1}},
        {'role': 'chase', 'box_id': found['chase']['id'], 'native': {'selected_items': [duck]}, 'expected': {'selected_items': [duck]}},
        {'role': 'collision', 'box_id': found['collision']['id'], 'native': {}, 'expected': {}},
        {'role': 'teleport', 'box_id': found['teleport']['id'], 'native': {'selected_items': [start], 'delay': 0}, 'expected': {'selected_items': [start], 'delay': 0}},
    ]
    manifest = {'protocol': PROTOCOL, 'target': 'habbogz', 'room_id': expected_room_id, 'private_acceptance_room': True,
                'items': [{'id': i['id'], 'base_id': i['base_id'], 'position': list(i['position'])} for i in items],
                'steps': steps, 'mobile_item_ids': [duck], 'discovered_from_inspection': True,
                'room_state': inspection['room_state'], 'owner_id': expected_owner_id}
    return valid_manifest(manifest)

def discover_and_apply(executor, *, expected_room_id, expected_owner_id, bases=None, baseline_must_be=None):
    """Inspect, plan, optionally require an unconfigured baseline, then apply.

    baseline_must_be: optional {role: settings}. If given, every box must read back
    exactly that before any write, otherwise nothing is written.
    """
    inspection = executor.call('inspect_room', expected_room_id)
    manifest = plan_duck(inspection, expected_room_id=expected_room_id, expected_owner_id=expected_owner_id, bases=bases)
    if baseline_must_be is not None:
        for step in manifest['steps']:
            if step['role'] not in baseline_must_be:
                raise ModelError('Baseline expectation missing for ' + step['role'])
            cur = executor.call('read_box', expected_room_id, box_id=step['box_id'], role=step['role'])
            if cur.get('observed_via') != 'reopened_native_editor' or cur.get('settings') != baseline_must_be[step['role']]:
                raise ModelError('Box not in expected unconfigured state; no writes issued')
    report = apply_classic(manifest, executor)
    report['planned_from_inspection'] = True
    report['owner_id_checked'] = expected_owner_id
    report['room_state'] = manifest['room_state']
    return report

def repeat_slider_moves(raw_param, ui_value, target, minimum=1, maximum=2):
    """Moves the executor must perform so the native Repeat editor emits `target`.

    raw_param is what the reopened editor reports as the wire parameter (0 on a box
    never configured). ui_value is what the slider shows (clamped to its minimum, so it
    can show 1 while raw_param is 0). The two are different facts and are never
    normalised into each other. When the slider already shows the target, a plain drag
    toward it emits no change and Done saves the raw 0, so the slider is nudged to the
    other end of the scoped range and back. Result must be proven by a native reopen that
    reports raw_param == target; the readback stays strict.
    """
    if target not in range(minimum, maximum + 1) or ui_value not in range(minimum, maximum + 1):
        raise ModelError('Repeat target or slider value outside the scoped range')
    if type(raw_param) is not int or raw_param < 0:
        raise ModelError('Raw Repeat parameter unreadable; no write')
    if raw_param == target:
        return []
    other = maximum if target == minimum else minimum
    if ui_value == target:
        return [other, target]
    return [target]
