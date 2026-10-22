"""Loopback-only developer view and separate local operator API."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlparse, parse_qs
from integrations.bo_app import BOApplication, ROOT

def serve(port=0, database="data/studio.sqlite", demo=False):
    app = BOApplication(ROOT / database)
    if demo:
        app.bo_demo()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            q = parse_qs(parsed.query)
            try:
                if parsed.path == "/api/view":
                    self.reply(app.bo_view())
                elif parsed.path == "/api/stategraph":
                    self.reply(app.graph.bo_export())
                elif parsed.path == "/api/preferences":
                    self.reply(app.bo_preferences())
                elif parsed.path == "/api/recordings":
                    self.reply({"saved": [p.stem for p in app.recordings_dir.glob("*.json")], "active": app.recording["id"] if app.recording else None})
                elif parsed.path.startswith("/api/recordings/"):
                    ident = parsed.path.rsplit("/", 1)[-1]
                    if len(ident) != 12 or any(ch not in "0123456789abcdef" for ch in ident):
                        raise ValueError("invalid recording id")
                    self.reply(json.loads((app.recordings_dir / (ident + ".json")).read_text()))
                elif parsed.path == "/api/source":
                    path = q.get("path", [""])[0]
                    self.reply({"path": path, "build_id": app.manifest["build_id"], "text": app.sources[path]})
                elif parsed.path in ("/", "/index.html", "/viewer.js", "/viewer.css"):
                    name = "index.html" if parsed.path == "/" else parsed.path[1:]
                    body = (ROOT / "static" / name).read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}[Path(name).suffix] + "; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers(); self.wfile.write(body)
                else:
                    self.reply({"error": "not_found"}, 404)
            except (ValueError, KeyError, OSError) as exc:
                self.reply({"error": str(exc)}, 400)

        def do_POST(self):
            try:
                # Local tool only. Reject cross-origin browser writes; no CORS allowance.
                origin = self.headers.get("Origin")
                if origin and origin != "http://" + self.headers.get("Host", ""):
                    self.reply({"error": "cross_origin_denied"}, 403); return
                size = int(self.headers.get("Content-Length", "0"))
                if size > 128000:
                    self.reply({"error": "body_too_large"}, 413); return
                data = json.loads(self.rfile.read(size) or b"{}")
                if self.path == "/api/preferences":
                    self.reply(app.bo_preferences(data))
                elif self.path == "/api/recordings/start":
                    self.reply(app.bo_record("start"))
                elif self.path == "/api/recordings/stop":
                    self.reply(app.bo_record("stop"))
                elif self.path == "/operator/command":
                    self.reply(app.bo_command(data))
                else:
                    self.reply({"error": "not_found"}, 404)
            except RuntimeError as exc:
                self.reply({"error": str(exc)}, 409)
            except (ValueError, KeyError, TypeError, PermissionError, OSError) as exc:
                self.reply({"error": str(exc), "type": type(exc).__name__}, 400)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:" + str(httpd.server_port)
    (ROOT / "data/server.json").write_text(json.dumps({"url": url, "port": httpd.server_port, "database": str(ROOT / database)}))
    stop = threading.Event()
    def timer():
        while not stop.wait(0.25):
            app.bo_tick()
    threading.Thread(target=timer, daemon=True, name="approval-expiry").start()
    print(url, flush=True)
    try:
        httpd.serve_forever()
    finally:
        stop.set()
        httpd.server_close()

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--db", default="data/studio.sqlite")
    p.add_argument("--demo", action="store_true")
    a = p.parse_args()
    serve(a.port, a.db, a.demo)
