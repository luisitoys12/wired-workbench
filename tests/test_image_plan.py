import json, struct, tempfile, unittest, zlib, subprocess, sys
from pathlib import Path
from wired_workbench.core import ModelError
from wired_workbench.image_plan import plan_from_image
from wired_workbench.layout import validate_layout

def png(rows, ctype=6):
    h, w = len(rows), len(rows[0]); ch = {2: 3, 6: 4}[ctype]
    raw = b"".join(b"\x00" + bytes(v for px in r for v in px[:ch]) for r in rows)
    c = lambda t, b: struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b))
    return b"\x89PNG\r\n\x1a\n" + c(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0)) + c(b"IDAT", zlib.compress(raw)) + c(b"IEND", b"")

R, B, T = (255, 0, 0, 255), (0, 0, 255, 255), (0, 0, 0, 0)
SPEC = lambda reds, blues: {"target": "habbogz", "width": 2, "height": 2,
    "kinds": [{"name": "rojo", "color": "#ff0000"}, {"name": "azul", "color": "#0000ff"}],
    "pieces": [{"id": f"r{i}", "name": "Roja", "kind": "rojo"} for i in range(reds)] + [{"id": f"b{i}", "name": "Azul", "kind": "azul"} for i in range(blues)]}

class T_(unittest.TestCase):
    def test_plan_matches_pixels_and_validates(self):
        r = plan_from_image(png([[R, B], [B, T]]), SPEC(1, 2))
        self.assertEqual(validate_layout(r["layout"]), [])
        pos = {(p["x"], p["y"]): p["id"] for p in r["layout"]["placements"]}
        self.assertEqual(pos, {(0, 0): "r0", (1, 0): "b0", (0, 1): "b1"})
        self.assertEqual(r["report"]["emptyCells"], 1); self.assertTrue(r["report"]["complete"])
        self.assertFalse(r["report"]["canApply"])
    def test_shortage_reported_not_invented(self):
        r = plan_from_image(png([[R, R], [R, R]]), SPEC(2, 0))
        self.assertEqual(r["report"]["shortage"], {"rojo": 2}); self.assertFalse(r["report"]["complete"])
        self.assertEqual(len(r["layout"]["placements"]), 2)
    def test_downscale_blocks(self):
        rows = [[R] * 4 + [B] * 4 for _ in range(8)]
        r = plan_from_image(png(rows), {**SPEC(4, 4), "width": 2, "height": 2})
        self.assertEqual(r["report"]["pieceNeeds"], {"rojo": 2, "azul": 2})
    def test_rejects_bad_inputs(self):
        for data in (b"nope", png([[R]])[:40], b"\x89PNG\r\n\x1a\n"):
            with self.assertRaises(ModelError): plan_from_image(data, SPEC(1, 1))
        with self.assertRaises(ModelError): plan_from_image(png([[R]]), {**SPEC(1, 1), "extra": 1})
        with self.assertRaises(ModelError): plan_from_image(png([[R]]), {**SPEC(1, 1), "width": 65})
        s = SPEC(1, 1); s["pieces"].append(dict(s["pieces"][0]))
        with self.assertRaises(ModelError): plan_from_image(png([[R]]), s)
    def test_rgb_png_and_cli(self):
        d = tempfile.mkdtemp(); Path(d, "i.png").write_bytes(png([[R[:3], B[:3]]], 2))
        Path(d, "s.json").write_text(json.dumps({**SPEC(1, 1), "height": 1}))
        o = subprocess.run([sys.executable, "-m", "wired_workbench", "image-plan", d + "/i.png", d + "/s.json", "--layout-out", d + "/l.json"], capture_output=True, text=True)
        self.assertEqual(o.returncode, 0, o.stderr)
        o2 = subprocess.run([sys.executable, "-m", "wired_workbench", "layout-check", d + "/l.json"], capture_output=True, text=True)
        self.assertEqual(o2.returncode, 0, o2.stderr)
if __name__ == "__main__": unittest.main()
