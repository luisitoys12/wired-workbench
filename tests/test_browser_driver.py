import json, shutil, sys, unittest
from pathlib import Path
from wired_workbench.native import NativeExecutor, apply_classic
from wired_workbench.core import ModelError
from tests.test_ui_executor import plan

try:
    import playwright  # noqa
except ImportError:
    playwright = None
CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")
FIX = (Path(__file__).parent / "fixtures" / "sim_client.html").resolve().as_uri()

@unittest.skipUnless(playwright and CHROME, "requiere playwright y un Chrome/Chromium local")
class BrowserDriverTests(unittest.TestCase):
    def ex(self, query, trust=True):
        cmd = [sys.executable, "-m", "wired_workbench.ui_executor", "--browser-url", FIX + query, "--chrome-path", CHROME]
        if trust: cmd += ["--trust-origin", FIX]
        return NativeExecutor(cmd, timeout=30)
    def test_clone_with_identity_hook_configures_through_real_dialogs(self):
        with self.ex("?clone=1") as ex:
            r = apply_classic(plan(), ex)
        self.assertTrue(r["configuration_verified"]); self.assertFalse(r["gameplay_verified"])
    def test_page_without_identity_hook_reads_but_never_writes(self):
        with self.ex("") as ex:
            with self.assertRaises(ModelError): apply_classic(plan(), ex)
            self.assertEqual(ex.call("read_box", 9, box_id=101, role="repeat")["settings"], {"v": -1})
            with self.assertRaises(ModelError): ex.call("configure_box", 9, box_id=101, role="repeat", native={"v": 1})
            self.assertEqual(ex.call("read_box", 9, box_id=101, role="repeat")["settings"], {"v": -1})
    def test_hook_from_untrusted_origin_is_ignored(self):
        with self.ex("?clone=1", trust=False) as ex:
            with self.assertRaises(ModelError): apply_classic(plan(), ex)
            with self.assertRaises(ModelError): ex.call("configure_box", 9, box_id=101, role="repeat", native={"v": 1})
            self.assertEqual(ex.call("read_box", 9, box_id=101, role="repeat")["settings"], {"v": -1})
    def test_other_trusted_origin_does_not_cover_this_page(self):
        cmd = [sys.executable, "-m", "wired_workbench.ui_executor", "--browser-url", FIX + "?clone=1", "--chrome-path", CHROME, "--trust-origin", "http://127.0.0.1:1/"]
        with NativeExecutor(cmd, timeout=30) as ex:
            with self.assertRaises(ModelError): apply_classic(plan(), ex)
    def test_dropped_save_is_detected_by_reopen(self):
        with self.ex("?clone=1&drop=1") as ex:
            with self.assertRaises(ModelError): apply_classic(plan(), ex)
    def test_open_room_state_blocks_writes(self):
        with self.ex("?clone=1&state=open") as ex:
            with self.assertRaises(ModelError): apply_classic(plan(), ex)
            with self.assertRaises(ModelError): ex.call("configure_box", 9, box_id=101, role="repeat", native={"v": 1})
    def test_unknown_field_is_not_silently_ignored(self):
        with self.ex("?clone=1") as ex:
            with self.assertRaises(ModelError): ex.call("configure_box", 9, box_id=101, role="repeat", native={"nope": 1})
if __name__ == "__main__": unittest.main()
