import json, subprocess, sys, tempfile, unittest, textwrap
from pathlib import Path
from wired_workbench.native import NativeExecutor
from wired_workbench.core import ModelError

FAKE = textwrap.dedent('''
    import sys, json
    for line in sys.stdin:
        r = json.loads(line)
        out = {"protocol": r["protocol"], "request_id": r["request_id"] + int(MODE == "badid"), "room_id": r["room_id"], "ok": MODE != "reject"}
        if r["action"] == "read_box": out.update(box_id=r.get("box_id"), settings={}, observed_via="reopened_native_editor")
        print(json.dumps(out), flush=True)
''')

class Contract(unittest.TestCase):
    def run_fake(self, mode):
        d = tempfile.mkdtemp(); p = Path(d, "fake.py"); p.write_text(f"MODE={mode!r}\n" + FAKE)
        return NativeExecutor([sys.executable, str(p)], timeout=5)
    def test_ok_round_trip_and_stop(self):
        with self.run_fake("ok") as ex:
            self.assertTrue(ex.call("read_box", 7, box_id=3, role="repeat")["ok"])
        self.assertTrue(ex.close_status["stop_acknowledged"])
    def test_rejected_action_stops(self):
        with self.run_fake("reject") as ex:
            with self.assertRaises(ModelError): ex.call("inspect_room", 7)
    def test_identity_mismatch_stops(self):
        with self.run_fake("badid") as ex:
            with self.assertRaises(ModelError): ex.call("inspect_room", 7)
    def test_executor_must_be_argument_list(self):
        with self.assertRaises(ModelError): NativeExecutor("python fake.py")
if __name__ == "__main__": unittest.main()
