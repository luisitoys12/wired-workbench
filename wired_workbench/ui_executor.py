"""Generic executor skeleton for hgz-classic-editor/1 over a pluggable driver.

A driver is whatever can look at and operate a client (a browser page, a clone).
This file never opens a network connection. The bundled SimDriver works on a JSON
file that stands for a synthetic clone, for tests and for demos. Write actions are
refused unless the driver itself reports owner and room state as verified: an
operator declaration is not accepted as identity evidence.
"""
import json
import sys
from pathlib import Path

PROTOCOL = "hgz-classic-editor/1"

from .driver_base import DriverError

class SimDriver:
    """Synthetic clone backed by a JSON file: {room_id, owner_id, room_state, private_acceptance_room, items, boxes{id:settings}}."""
    identity_verified = True
    def __init__(self, path, drop_writes=False):
        self.path = Path(path); self.drop = drop_writes
        self.state = json.loads(self.path.read_text())
    def inspect(self):
        s = self.state
        return {k: s[k] for k in ("room_id", "owner_id", "room_state", "private_acceptance_room", "items")}
    def read_box(self, box_id, role):
        boxes = self.state["boxes"]
        if str(box_id) not in boxes: raise DriverError("unknown box")
        return json.loads(json.dumps(boxes[str(box_id)]))
    def configure(self, box_id, role, native):
        if str(box_id) not in self.state["boxes"]: raise DriverError("unknown box")
        if not self.drop:
            self.state["boxes"][str(box_id)] = dict(native)
            self.path.write_text(json.dumps(self.state))

class UnverifiedUIDriver:
    """What a plain browser driver offers on a real client: it can read the box editors
    but cannot read the numeric owner or the real room state. Inspection therefore
    omits identity and writes are refused."""
    identity_verified = False
    def __init__(self, inner): self.inner = inner
    def inspect(self):
        data = self.inner.inspect()
        return {"room_id": data.get("room_id"), "items": data.get("items")}
    def read_box(self, box_id, role): return self.inner.read_box(box_id, role)
    def configure(self, box_id, role, native): raise DriverError("identity not verifiable by this driver")

def handle(driver, req, scope_room=None):
    action, room = req.get("action"), req.get("room_id")
    base = {"protocol": PROTOCOL, "request_id": req.get("request_id"), "room_id": room}
    try:
        if req.get("protocol") != PROTOCOL: raise DriverError("protocol")
        if action == "stop": return {**base, "ok": True}
        ins = driver.inspect()
        if ins.get("room_id") != room: raise DriverError("room mismatch")
        if scope_room is not None and room != scope_room: raise DriverError("room out of scope")
        if action == "inspect_room": return {**base, "ok": True, **ins}
        if action == "read_box":
            return {**base, "ok": True, "box_id": req["box_id"], "settings": driver.read_box(req["box_id"], req.get("role")),
                    "observed_via": "reopened_native_editor"}
        if action == "configure_box":
            if not getattr(driver, "identity_verified", False): raise DriverError("write refused: owner/state not verified")
            if ins.get("owner_id") is None or ins.get("room_state") != "hide" or ins.get("private_acceptance_room") is not True:
                raise DriverError("write refused: room not private/hidden")
            driver.configure(req["box_id"], req.get("role"), req["native"])
            return {**base, "ok": True, "box_id": req["box_id"]}
        raise DriverError("unknown action")
    except (DriverError, KeyError, TypeError) as e:
        return {**base, "ok": False, "error": str(e)}

def serve(driver, stdin=None, stdout=None, scope_room=None):
    stdin = stdin or sys.stdin; stdout = stdout or sys.stdout
    for line in stdin:
        if not line.strip(): continue
        stdout.write(json.dumps(handle(driver, json.loads(line), scope_room)) + "\n"); stdout.flush()

def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Executor de pruebas sobre un clon sintético en JSON")
    p.add_argument("--sim"); p.add_argument("--unverified", action="store_true")
    p.add_argument("--browser-url", help="Pagina local o clon a operar con Playwright (sin credenciales)"); p.add_argument("--chrome-path"); p.add_argument("--trust-origin", action="append", default=[], help="Prefijo de URL que el operador declara como clon de prueba; sin esto no hay identidad verificada")
    p.add_argument("--drop-writes", action="store_true"); p.add_argument("--scope-room", type=int)
    a = p.parse_args(argv)
    if bool(a.sim) == bool(a.browser_url): p.error("elija --sim o --browser-url")
    if a.browser_url:
        from .browser_driver import BrowserDriver, launch
        pw, browser, page = launch(a.browser_url, a.chrome_path)
        try: serve(BrowserDriver(page, trusted_origins=a.trust_origin), scope_room=a.scope_room)
        finally: browser.close(); pw.stop()
        return
    d = SimDriver(a.sim, drop_writes=a.drop_writes)
    serve(UnverifiedUIDriver(d) if a.unverified else d, scope_room=a.scope_room)

if __name__ == "__main__":
    main()
