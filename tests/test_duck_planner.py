import contextlib, copy, io, unittest
from wired_workbench.duck_planner import plan_duck, discover_and_apply, DUCK_BASES
from wired_workbench.core import ModelError

def insp(room=7001, owner=55, ids=None):
    ids = ids or {'duck': 11, 'start': 12, 'repeat': 13, 'chase': 14, 'collision': 15, 'teleport': 16}
    return {'room_id': room, 'owner_id': owner, 'private_acceptance_room': True, 'room_state': 'hide',
            'items': [{'id': ids[r], 'base_id': b, 'position': [i, 1, 0]} for i, (r, b) in enumerate(DUCK_BASES.items())]}

class Fake:
    def __init__(self, ins, baseline=None):
        self.ins = ins; self.calls = []; self.state = {}; self.baseline = baseline or {}
    def call(self, action, room, **d):
        self.calls.append(action)
        if action == 'inspect_room': return self.ins
        if action == 'configure_box': self.state[d['box_id']] = d['native']; return {}
        return {'observed_via': 'reopened_native_editor', 'settings': self.state.get(d['box_id'], self.baseline.get(d['role'], {}))}

class T(unittest.TestCase):
    def plan(self, i=None, **kw):
        a = dict(expected_room_id=7001, expected_owner_id=55); a.update(kw)
        return plan_duck(i or insp(), **a)
    def test_uses_live_ids_not_constants(self):
        p = self.plan(); self.assertEqual(p['steps'][1]['native']['selected_items'], [11]); self.assertEqual(p['steps'][3]['native']['selected_items'], [12]); self.assertEqual(p['mobile_item_ids'], [11])
        other = insp(ids={'duck': 91, 'start': 92, 'repeat': 93, 'chase': 94, 'collision': 95, 'teleport': 96})
        self.assertEqual(self.plan(other)['steps'][1]['native']['selected_items'], [91])
    def test_fail_closed(self):
        for mut in [lambda i: i.pop('owner_id'), lambda i: i.update(owner_id=1), lambda i: i.update(room_id=2),
                    lambda i: i.update(private_acceptance_room=False), lambda i: i.update(room_state='open'), lambda i: i.pop('room_state'), lambda i: i.pop('private_acceptance_room'),
                    lambda i: i['items'].pop(), lambda i: i['items'].append(dict(i['items'][0], id=99)),
                    lambda i: i['items'][0].update(base_id=1), lambda i: i['items'][1].update(id=i['items'][0]['id']),
                    lambda i: i['items'][2].update(position=[float('nan'), 1, 0]), lambda i: i['items'][2].update(position=[1, 1])]:
            i = insp(); mut(i)
            with self.assertRaises(ModelError): self.plan(i)
    def test_operator_must_give_expected(self):
        with self.assertRaises(ModelError): plan_duck(insp(), expected_room_id=0, expected_owner_id=55)
        with self.assertRaises(ModelError): plan_duck(insp(), expected_room_id=7001, expected_owner_id=True)
    def test_bad_bases(self):
        with self.assertRaises(ModelError): self.plan(bases=dict(DUCK_BASES, start=DUCK_BASES['duck']))
    def run_apply(self, f, **kw):
        with contextlib.redirect_stdout(io.StringIO()):
            return discover_and_apply(f, expected_room_id=7001, expected_owner_id=55, **kw)
    def test_apply_ok_not_gameplay(self):
        f = Fake(insp()); r = self.run_apply(f)
        self.assertTrue(r['configuration_verified']); self.assertFalse(r['gameplay_verified']); self.assertTrue(r['planned_from_inspection']); self.assertEqual(r['room_state'],'hide')
    def test_no_write_on_wrong_owner(self):
        f = Fake(insp(owner=9))
        with self.assertRaises(ModelError): self.run_apply(f)
        self.assertNotIn('configure_box', f.calls)
    def test_baseline_gate(self):
        base = {r: {} for r in ('repeat', 'chase', 'collision', 'teleport')}
        f = Fake(insp(), baseline={'repeat': {'cycles': 3}})
        with self.assertRaises(ModelError): self.run_apply(f, baseline_must_be=base)
        self.assertNotIn('configure_box', f.calls)
        f = Fake(insp()); self.run_apply(f, baseline_must_be=base); self.assertIn('configure_box', f.calls)
if __name__ == '__main__': unittest.main()

class RepeatMoves(unittest.TestCase):
    def test_fresh_box_shows_min_but_wire_zero(self):
        from wired_workbench.duck_planner import repeat_slider_moves as m
        self.assertEqual(m(0, 1, 1), [2, 1])
    def test_already_target_wire(self):
        from wired_workbench.duck_planner import repeat_slider_moves as m
        self.assertEqual(m(1, 1, 1), [])
    def test_normal_changes(self):
        from wired_workbench.duck_planner import repeat_slider_moves as m
        self.assertEqual(m(1, 1, 2), [2]); self.assertEqual(m(2, 2, 1), [1]); self.assertEqual(m(0, 1, 2), [2])
    def test_rejects_out_of_scope(self):
        from wired_workbench.duck_planner import repeat_slider_moves as m
        for a in [(0, 1, 3), (0, 5, 1), (-1, 1, 1), (True, 1, 1), ('0', 1, 1)]:
            with self.assertRaises(ModelError): m(*a)
