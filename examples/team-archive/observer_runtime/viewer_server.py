"""Loopback-only read-only viewer for captured models and real JSONL events."""
from __future__ import annotations
import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit
from model_tool import ASSETS, capture, compare, read_json, safe_path


def read_events(path, limit=3000):
    path = Path(path)
    if not path.exists():
        return [], {"malformed": 0, "truncated": False}
    malformed, total = 0, 0
    rows = deque(maxlen=limit)
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            total += 1
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                malformed += 1
    return list(rows), {"malformed": malformed, "truncated": total > limit}


class ViewerHandler(BaseHTTPRequestHandler):
    snapshot = None
    static_files = {"/": (ASSETS / "viewer/index.html", "text/html"),
                    "/viewer.js": (ASSETS / "viewer/viewer.js", "text/javascript"),
                    "/viewer.css": (ASSETS / "viewer/viewer.css", "text/css")}

    def log_message(self, *_):
        pass

    def local_request(self):
        port = self.server.server_address[1]
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def reply(self, value, code=200, content_type="application/json"):
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self.local_request():
            return self.reply({"error": "invalid host"}, 403)
        path = urlsplit(self.path).path
        if path == "/api/view":
            try:
                return self.reply(type(self).snapshot())
            except Exception:
                return self.reply({"error": "observation unavailable"}, 503)
        if path in self.static_files:
            f, mime = self.static_files[path]
            return self.reply(f.read_bytes(), content_type=mime)
        return self.reply({"error": "not found"}, 404)

    def do_POST(self):
        return self.reply({"error": "observer is read-only"}, 405)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--events", required=True)
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    root = args.root.absolute().resolve()
    model = read_json(safe_path(root, args.model))
    manifest = read_json(safe_path(root, args.manifest))
    def snapshot():
        current = capture(root, read_json(safe_path(root, args.model)))
        events, ingestion = read_events(safe_path(root, args.events))
        return {"model": model, "manifest": manifest, "events": events,
                "binding_status": compare(current, manifest)["status"],
                "health": {"enabled": None, "dropped": None, "errors": None, "queued": None},
                "ingestion": ingestion, "authority": None}
    ViewerHandler.snapshot = staticmethod(snapshot)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ViewerHandler)
    print(f"Read-only viewer: http://127.0.0.1:{args.port} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
