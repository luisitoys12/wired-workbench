import json, sys, tempfile, unittest, copy
from pathlib import Path
from wired_workbench.native import NativeExecutor, apply_classic, PROTOCOL
from wired_workbench.core import ModelError

ITEMS = [{"id": 100 + i, "base_id": 5, "position": [i, 0, 0]} for i in range(5)]
def plan():
    steps = [{"role": r, "box_id": 101 + i, "native": {"v": i}, "expected": {"v": i}} for i, r in enumerate(("repeat", "chase", "collision", "teleport"))]
    steps[1]["native"]["selected_items"] = steps[1]["expected"]["selected_items"] = [100]
    return {"protocol": PROTOCOL, "target": "habbogz", "room_id": 9, "private_acceptance_room": True, "owner_id": 3, "room_state": "hide",
            "items": copy.deepcopy(ITEMS), "mobile_item_ids": [100], "steps": steps}
def state(**kw):
    s = {"room_id": 9, "owner_id": 3, "room_state": "hide", "private_acceptance_room": True, "items": copy.deepcopy(ITEMS),
         "boxes": {str(101 + i): {"v": -1} for i in range(4)}}
    s.update(kw); return s
def run(s, *flags):
    f = Path(tempfile.mkdtemp(), "sim.json"); f.write_text(json.dumps(s))
    ex = NativeExecutor([sys.executable, "-m", "wired_workbench.ui_executor", "--sim", str(f), *flags], timeout=10)
    return f, ex

class UIExecutor(unittest.TestCase):
    def test_verified_clone_configures_and_reads_back(self):
        f, ex = run(state())
        with ex: r = apply_classic(plan(), ex)
        self.assertTrue(r["configuration_verified"]); self.assertFalse(r["gameplay_verified"])
        self.assertEqual(json.loads(f.read_text())["boxes"]["102"]["selected_items"], [100])
    def test_unverified_driver_cannot_write(self):
        f, ex = run(state(), "--unverified")
        with ex:
            with self.assertRaises(ModelError): apply_classic(plan(), ex)
        self.assertEqual(json.loads(f.read_text())["boxes"]["101"], {"v": -1})
    def test_dropped_write_is_caught_by_readback(self):
        f, ex = run(state(), "--drop-writes")
        with ex:
            with self.assertRaises(ModelError): apply_classic(plan(), ex)
    def test_wrong_owner_or_public_room_blocks_every_write(self):
        for bad in (state(owner_id=4), state(room_state="open"), state(private_acceptance_room=False)):
            f, ex = run(bad)
            with ex:
                with self.assertRaises(ModelError): apply_classic(plan(), ex)
            self.assertEqual(json.loads(f.read_text())["boxes"]["101"], {"v": -1})
    def test_scope_room_rejects_other_room(self):
        f, ex = run(state(), "--scope-room", "8")
        with ex:
            with self.assertRaises(ModelError): apply_classic(plan(), ex)
if __name__ == "__main__": unittest.main()
