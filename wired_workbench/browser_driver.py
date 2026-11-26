"""Browser driver for ui_executor, built on Playwright (optional dependency).

It operates what a page shows: item elements, the box editor dialog, its fields and
Save/Close. It cannot read a numeric owner or the real room state from a normal
client, so by default `identity_verified` is False and writes are refused. Only a
page that exposes the `window.__wiredIdentity` hook AND whose URL starts with an
origin the operator listed in `trusted_origins` can make identity verified (a page
that merely exposes a JS object proves nothing), and the room id must match. Nothing here logs in, stores credentials or opens any address by itself:
the operator passes the URL of the page.
"""
import json
from .driver_base import DriverError

DEFAULT_PROFILE = {
    "item": ".item[data-item-id]", "item_id_attr": "data-item-id", "base_id_attr": "data-base-id", "position_attr": "data-pos",
    "room": "#room", "room_id_attr": "data-room-id",
    "box": ".item[data-box][data-item-id='{id}']", "editor": "#editor", "field": "#fields input[name='{key}']",
    "fields": "#fields input", "save": "#save", "close": "#close",
}

class BrowserDriver:
    def __init__(self, page, profile=None, trusted_origins=()):
        self.page = page
        self.p = {**DEFAULT_PROFILE, **(profile or {})}
        self.trusted = tuple(trusted_origins)
        if any(not isinstance(t, str) or "://" not in t for t in self.trusted):
            raise DriverError("trusted origins must be URL prefixes such as http://127.0.0.1:8080/")
    def _trusted_page(self):
        """The page itself is not evidence: only a URL prefix the operator listed may supply identity."""
        u = self.page.url.split("?")[0].split("#")[0]
        return any(u == t or (t.endswith("/") and u.startswith(t)) or u.startswith(t + "/") for t in self.trusted)
    @property
    def identity_verified(self):
        if not self.trusted or not self._trusted_page():
            return False
        hook = self._hook()
        return bool(hook) and hook.get("room_id") == self._room_id() and type(hook.get("owner_id")) is int
    def _hook(self):
        h = self.page.evaluate("() => (typeof window.__wiredIdentity === 'object' && window.__wiredIdentity) || null")
        return h if isinstance(h, dict) else None
    def _room_id(self):
        v = self.page.get_attribute(self.p["room"], self.p["room_id_attr"])
        try: return int(v)
        except (TypeError, ValueError): return None
    def inspect(self):
        items = []
        for el in self.page.query_selector_all(self.p["item"]):
            pos = [float(x) if "." in x else int(x) for x in el.get_attribute(self.p["position_attr"]).split(",")]
            items.append({"id": int(el.get_attribute(self.p["item_id_attr"])), "base_id": int(el.get_attribute(self.p["base_id_attr"])), "position": pos})
        out = {"room_id": self._room_id(), "items": items}
        if self.identity_verified:
            h = self._hook()
            out.update(owner_id=h["owner_id"], room_state=h.get("room_state"), private_acceptance_room=h.get("private_acceptance_room"))
        return out
    def _open(self, box_id):
        sel = self.p["box"].format(id=int(box_id))
        if self.page.query_selector(sel) is None: raise DriverError("unknown box")
        self.page.click(sel)
        self.page.wait_for_selector(self.p["editor"], state="visible", timeout=3000)
    def _close(self):
        self.page.click(self.p["close"])
        self.page.wait_for_selector(self.p["editor"], state="hidden", timeout=3000)
    def read_box(self, box_id, role):
        self._open(box_id)
        try:
            out = {}
            for el in self.page.query_selector_all(self.p["fields"]):
                out[el.get_attribute("name")] = json.loads(el.input_value())
            return out
        except ValueError:
            raise DriverError("editor value not readable")
        finally:
            self._close()
    def configure(self, box_id, role, native):
        self._open(box_id)
        try:
            for key, value in native.items():
                sel = self.p["field"].format(key=key)
                if self.page.query_selector(sel) is None: raise DriverError("editor has no field " + key)
                self.page.fill(sel, json.dumps(value))
            self.page.click(self.p["save"])
        finally:
            self._close()

def launch(url, chrome_path=None, headless=True):
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    kw = {"headless": headless, "args": ["--no-sandbox"]}
    if chrome_path: kw["executable_path"] = chrome_path
    browser = pw.chromium.launch(**kw)
    page = browser.new_page(); page.goto(url)
    return pw, browser, page
