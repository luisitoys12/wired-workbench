import contextlib, io, random, unittest
from wired_workbench.role_selector import plan_roles, select_and_apply, ROLES
from wired_workbench.duck_planner import DUCK_BASES
from wired_workbench.core import ModelError

def room(ids, shift=0, extras=()):
    d = ids; s = shift
    items = [
        {'id': d['duck'], 'base_id': DUCK_BASES['duck'], 'position': [6 + s, 4, 0]},
        {'id': d['start'], 'base_id': DUCK_BASES['start'], 'position': [1 + s, 4, 0]},
        {'id': d['repeat'], 'base_id': DUCK_BASES['repeat'], 'position': [1 + s, 1, 0]},
        {'id': d['chase'], 'base_id': DUCK_BASES['chase'], 'position': [1 + s, 1, 0.7]},
        {'id': d['collision'], 'base_id': DUCK_BASES['collision'], 'position': [6 + s, 1, 0]},
        {'id': d['teleport'], 'base_id': DUCK_BASES['teleport'], 'position': [6 + s, 1, 0.7]},
    ] + [dict(e) for e in extras]
    return {'room_id': 500, 'owner_id': 9, 'room_state': 'hide', 'private_acceptance_room': True, 'items': items}
IDS = dict(zip(ROLES, range(10, 16)))
IDS2 = dict(zip(ROLES, [901, 77, 3050, 12, 4001, 88]))
def plan(ins, **kw):
    a = dict(expected_room_id=500, expected_owner_id=9); a.update(kw)
    return plan_roles(ins, **a)

class Sel(unittest.TestCase):
    def test_happy_and_preview_no_write(self):
        m, p = plan(room(IDS)); self.assertFalse(p['will_write']); self.assertEqual(p['ignored_items'], []); self.assertEqual(m['mobile_item_ids'], [10])
    def test_order_and_ids_independent(self):
        base = room(IDS2); shuffled = dict(base); items = list(base['items']); random.Random(3).shuffle(items); shuffled['items'] = items
        m1, p1 = plan(base); m2, p2 = plan(shuffled)
        self.assertEqual(m1, m2); self.assertEqual(p1['fingerprint'], p2['fingerprint'])
        self.assertEqual(m1['steps'][1]['native']['selected_items'], [IDS2['duck']]); self.assertEqual(m1['steps'][3]['native']['selected_items'], [IDS2['start']])
    def test_extras_ignored_when_off_recipe(self):
        m, p = plan(room(IDS, extras=[{'id': 99, 'base_id': 1, 'position': [3, 3, 0]}])); self.assertEqual(p['ignored_items'], [99])
    def test_duplicate_requires_explicit(self):
        ins = room(IDS, extras=[{'id': 98, 'base_id': DUCK_BASES['duck'], 'position': [9, 9, 0]}])
        with self.assertRaises(ModelError): plan(ins)
        m, p = plan(ins, selection=IDS); self.assertEqual(p['roles']['duck'], 10); self.assertEqual(p['ignored_items'], [98]); self.assertTrue(p['selection_was_explicit'])
        m, p = plan(ins, selection=dict(IDS, duck=98)); self.assertEqual(m['mobile_item_ids'], [98])
    def test_selection_rejections(self):
        ins = room(IDS)
        for sel in [dict(IDS, duck=999), dict(IDS, duck=11), dict(IDS, repeat=10), {k: v for k, v in IDS.items() if k != 'duck'}, dict(IDS, extra=1), dict(IDS, chase=True)]:
            with self.assertRaises(ModelError): plan(ins, selection=sel)
    def test_room_gates(self):
        for mut in [lambda i: i.update(owner_id=1), lambda i: i.update(room_state='open'), lambda i: i.pop('room_state'), lambda i: i.update(private_acceptance_room=False), lambda i: i.update(room_id=1)]:
            ins = room(IDS); mut(ins)
            with self.assertRaises(ModelError): plan(ins)
    def test_topology_rejections(self):
        def pos(role, p): return lambda i: [x.update(position=p) for x in i['items'] if x['id'] == IDS[role]]
        cases = [pos('chase', [2, 1, 0.7]), pos('chase', [1, 1, 0]), pos('chase', [1, 1, -0.1]), pos('teleport', [7, 1, 0.7]), pos('teleport', [6, 1, 0]),
                 pos('collision', [1, 1, 0]), pos('start', [1, 1, 0]), pos('start', [6, 1, 0]), pos('start', [6.5, 4, 0]), pos('duck', [1, 4, 0])]
        for c in cases:
            ins = room(IDS); c(ins)
            with self.assertRaises(ModelError): plan(ins)
    def test_extra_on_recipe_tile_rejected(self):
        for p in ([1, 1, 1.4], [6, 1, 1.4], [1, 4, 0]):
            with self.assertRaises(ModelError): plan(room(IDS, extras=[{'id': 99, 'base_id': 1, 'position': p}]))
    def test_nonfinite_and_bool_positions(self):
        for p in ([float('nan'), 1, 0], [True, 1, 0], [1, 1]):
            ins = room(IDS, extras=[{'id': 99, 'base_id': 1, 'position': p}])
            with self.assertRaises(ModelError): plan(ins)

class Fake:
    def __init__(self, ins): self.ins = ins; self.calls = []; self.state = {}
    def call(self, action, r, **d):
        self.calls.append(action)
        if action == 'inspect_room': return self.ins
        if action == 'configure_box': self.state[d['box_id']] = d['native']; return {}
        return {'observed_via': 'reopened_native_editor', 'settings': self.state.get(d['box_id'], {})}
class Apply(unittest.TestCase):
    def run_(self, f, **kw):
        with contextlib.redirect_stdout(io.StringIO()):
            return select_and_apply(f, expected_room_id=500, expected_owner_id=9, **kw)
    def test_apply_with_extras_and_fingerprint(self):
        ins = room(IDS2, shift=1, extras=[{'id': 99, 'base_id': 1, 'position': [3, 3, 0]}])
        fp = plan(ins)[1]['fingerprint']
        r = self.run_(Fake(ins), expected_fingerprint=fp); self.assertTrue(r['configuration_verified']); self.assertFalse(r['gameplay_verified'])
    def test_fingerprint_mismatch_no_write(self):
        f = Fake(room(IDS))
        with self.assertRaises(ModelError): self.run_(f, expected_fingerprint='0' * 16)
        self.assertNotIn('configure_box', f.calls)
    def test_topology_failure_no_write(self):
        ins = room(IDS); ins['items'][3]['position'] = [2, 1, 0.7]; f = Fake(ins)
        with self.assertRaises(ModelError): self.run_(f)
        self.assertNotIn('configure_box', f.calls); self.assertNotIn('read_box', f.calls)
if __name__ == '__main__': unittest.main()

import copy
from wired_workbench.native import apply_classic, valid_manifest

class Drift(Fake):
    """inspect_room answer changes after n inspects."""
    def __init__(self, ins, after, mutate):
        super().__init__(ins); self.n = 0; self.after = after; self.mutate = mutate
    def call(self, action, r, **d):
        if action == 'inspect_room':
            self.n += 1
            if self.n > self.after:
                x = copy.deepcopy(self.ins); self.mutate(x); self.calls.append(action); return x
        return super().call(action, r, **d)

class Contract(unittest.TestCase):
    def manifest(self, ins=None):
        return plan(ins or room(IDS2, extras=[{'id': 99, 'base_id': 1, 'position': [3, 3, 0]}]))[0]
    def apply(self, m, f):
        with contextlib.redirect_stdout(io.StringIO()):
            return apply_classic(m, f, require_roles=True)
    def test_role_items_present_and_consistent(self):
        m = valid_manifest(self.manifest(), require_roles=True); self.assertEqual(m['role_items']['duck'], IDS2['duck'])
    def test_role_items_rejections(self):
        for mut in [lambda m: m.pop('role_items'), lambda m: m['role_items'].pop('duck'), lambda m: m['role_items'].update(duck=99),
                    lambda m: m['role_items'].update(start=IDS2['duck']), lambda m: m['role_items'].update(repeat=IDS2['chase']),
                    lambda m: m['role_items'].update(duck=IDS2['start']), lambda m: m['role_items'].update(teleport=True),
                    lambda m: m.update(mobile_item_ids=[IDS2['start']])]:
            m = self.manifest(); mut(m); f = Fake(room(IDS2))
            with self.assertRaises(ModelError): self.apply(m, f)
            self.assertEqual(f.calls, [])
    def test_strict_requires_owner_and_hide(self):
        for mut in [lambda m: m.pop('owner_id'), lambda m: m.update(room_state='open'), lambda m: m.pop('room_state')]:
            m = self.manifest(); mut(m); f = Fake(room(IDS2))
            with self.assertRaises(ModelError): self.apply(m, f)
            self.assertEqual(f.calls, [])
    def test_drift_before_first_write(self):
        ins = room(IDS2, extras=[{'id': 99, 'base_id': 1, 'position': [3, 3, 0]}])
        for mut in [lambda x: x.update(owner_id=1), lambda x: x.update(room_state='open'), lambda x: x['items'].pop(),
                    lambda x: x['items'][2].update(id=4242), lambda x: x['items'][1].update(position=[2, 4, 0]), lambda x: x['items'][6].update(position=[3, 4, 0])]:
            f = Drift(ins, 0, mut)
            with self.assertRaises(ModelError): self.apply(self.manifest(ins), f)
            self.assertNotIn('configure_box', f.calls)
    def test_drift_between_writes_stops(self):
        ins = room(IDS2)
        f = Drift(ins, 1, lambda x: x.update(owner_id=1))   # first inspect ok (plan check), drift before first write
        with self.assertRaises(ModelError): self.apply(self.manifest(ins), f)
        self.assertEqual(f.calls.count('configure_box'), 0)
        f = Drift(ins, 2, lambda x: x.update(room_state='open'))  # drift before the 2nd write
        with self.assertRaises(ModelError): self.apply(self.manifest(ins), f)
        self.assertEqual(f.calls.count('configure_box'), 1)
    def test_duck_may_move_between_writes(self):
        ins = room(IDS2); f = Drift(ins, 1, lambda x: x['items'][0].update(position=[7.5, 5, 0]))
        r = self.apply(self.manifest(ins), f); self.assertTrue(r['configuration_verified'])
    def test_inspections_before_each_write(self):
        ins = room(IDS2, extras=[{'id': 99, 'base_id': 1, 'position': [3, 3, 0]}]); f = Fake(ins); self.apply(self.manifest(ins), f)
        self.assertEqual(f.calls.count('inspect_room'), 5)
if __name__ == '__main__': unittest.main()

class Fingerprint(unittest.TestCase):
    EX = [{'id': 99, 'base_id': 1, 'position': [3, 3, 0]}, {'id': 98, 'base_id': 2, 'position': [4, 3, 0]}]
    def fp(self, ins, **kw):
        return plan(ins, **kw)[1]['fingerprint']
    def test_changes_that_used_to_keep_fingerprint(self):
        base = room(IDS2, extras=self.EX); fp0 = self.fp(base)
        def mut_item(iid, **chg):
            def f(x):
                for i in x['items']:
                    if i['id'] == iid: i.update(chg)
            return f
        muts = [mut_item(99, position=[3, 3, 0.4]), mut_item(99, position=[5, 5, 0]), mut_item(99, base_id=77), mut_item(98, position=[4, 3, 1]),
                mut_item(IDS2['chase'], position=[1 + 0, 1, 0.9]), mut_item(IDS2['start'], position=[2, 4, 0]), mut_item(IDS2['collision'], position=[7, 1, 0]),
                lambda x: x['items'].append({'id': 97, 'base_id': 5, 'position': [8, 8, 0]})]
        for m in muts:
            ins = copy.deepcopy(base); m(ins)
            try:
                fp1 = self.fp(ins)
            except ModelError:
                continue   # rejected by topology is also a safe outcome
            self.assertNotEqual(fp0, fp1)
    def test_duck_move_keeps_fingerprint(self):
        base = room(IDS2, extras=self.EX); moved = copy.deepcopy(base)
        for i in moved['items']:
            if i['id'] == IDS2['duck']: i['position'] = [9.25, 7, 0]
        self.assertEqual(self.fp(base), self.fp(moved))
    def test_order_independent(self):
        base = room(IDS2, extras=self.EX); sh = copy.deepcopy(base); random.Random(5).shuffle(sh['items'])
        self.assertEqual(self.fp(base), self.fp(sh))
    def test_bases_and_selection_change_it(self):
        base = room(IDS2, extras=self.EX)
        self.assertNotEqual(self.fp(base), self.fp(base, selection=IDS2))
    def test_apply_rejects_extra_changed_after_preview(self):
        base = room(IDS2, extras=self.EX); fp = self.fp(base)
        for chg in [lambda x: x['items'][6].update(position=[3, 3, 0.4]), lambda x: x['items'][7].update(base_id=3), lambda x: x['items'].append({'id': 97, 'base_id': 5, 'position': [8, 8, 0]})]:
            ins = copy.deepcopy(base); chg(ins); f = Fake(ins)
            with self.assertRaises(ModelError):
                with contextlib.redirect_stdout(io.StringIO()):
                    select_and_apply(f, expected_room_id=500, expected_owner_id=9, expected_fingerprint=fp)
            self.assertNotIn('configure_box', f.calls)
    def test_apply_with_unchanged_room_and_moved_duck_ok(self):
        base = room(IDS2, extras=self.EX); fp = self.fp(base); ins = copy.deepcopy(base)
        ins['items'][0]['position'] = [8.5, 6, 0]
        with contextlib.redirect_stdout(io.StringIO()):
            r = select_and_apply(Fake(ins), expected_room_id=500, expected_owner_id=9, expected_fingerprint=fp)
        self.assertTrue(r['configuration_verified'])
if __name__ == '__main__': unittest.main()
