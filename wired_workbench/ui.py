"""Opt-in loopback UI. No hotel connector and no outbound networking."""
import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .core import MAX_BYTES, ModelError, unique_keys, validate, explain, plan
from .layout import layout_report, svg_preview

ASSETS = Path(__file__).parent / "web"

def create_server(port=0):
    token = secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, code, body, mime="application/json; charset=utf-8"):
            if not isinstance(body, bytes): body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers(); self.wfile.write(body)
        def valid_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"
        def do_GET(self):
            if not self.valid_host(): return self.reply(403, '{}')
            route = urlsplit(self.path).path
            files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
            if route == "/session": return self.reply(200, json.dumps({"token": token}))
            if route not in files: return self.reply(404, '{}')
            name, mime = files[route]; return self.reply(200, (ASSETS/name).read_bytes(), mime)
        def do_POST(self):
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if not self.valid_host() or self.headers.get("Origin") != origin or self.headers.get("X-Workbench-Token") != token:
                return self.reply(403, '{}')
            if self.headers.get("Content-Type") != "application/json" or self.headers.get("Transfer-Encoding"):
                return self.reply(415, '{}')
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if not 0 < n <= MAX_BYTES: return self.reply(413, '{}')
                self.connection.settimeout(3)
                obj = json.loads(self.rfile.read(n), object_pairs_hook=unique_keys)
                if self.path == "/api/analyze":
                    issues = validate(obj); result = {"issues": issues, "report": None if issues else explain(obj)}
                elif self.path == "/api/layout": result = {"report": layout_report(obj), "svg": svg_preview(obj)}
                elif self.path == "/api/plan":
                    if not isinstance(obj, dict) or set(obj) != {"recipe", "target"}: raise ModelError("Pedido de receta inválido")
                    result = plan(obj["recipe"], obj["target"])
                else: return self.reply(404, '{}')
                return self.reply(200, json.dumps(result, ensure_ascii=False))
            except (ValueError, TypeError, RecursionError, TimeoutError, OSError) as e:
                return self.reply(400, json.dumps({"error": str(e)[:2000]}, ensure_ascii=False))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server

def main():
    p = argparse.ArgumentParser(description="Interfaz local opt-in, sin conexión a hoteles")
    p.add_argument("--port", type=int, default=0)
    a = p.parse_args()
    if not 0 <= a.port <= 65535: p.error("Puerto inválido")
    server = create_server(a.port)
    print(f"Interfaz local: http://127.0.0.1:{server.server_port}/", flush=True)
    print("Sin conexión a hoteles. Ctrl+C para cerrar. No habilitar LAN.", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__ == "__main__": main()
