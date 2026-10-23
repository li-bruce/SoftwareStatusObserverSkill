"""Isolated browser fixture for view persistence and recording version changes.

Run with --port 8864. The application and upgrade controls are test-only.
Production viewer, project preferences, and recording modules are used unchanged.
"""

from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import hashlib
import json
import mimetypes
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/business-observer/scripts"))
from recording_session import Recordings
from view_preferences import Preferences


def serve(directory, port):
    directory.mkdir(parents=True, exist_ok=True)
    assets = ROOT / "skills/business-observer/assets/stategraph-viewer"
    preferences = Preferences(directory, "view-continuity-fixture")
    lock = threading.RLock()
    version, events = 1, []

    def model():
        nodes = [
            dict(id="upload", kind="action", layer="business", label="Upload"),
            dict(id="review", kind="action", layer="business", label="Review"),
            dict(
                id="store",
                kind="function",
                parent="upload",
                label="Store file",
                origin="source-ast",
            ),
            dict(
                id="notify",
                kind="effect",
                parent="review",
                label="Notify reviewer",
                analysis_level="advanced",
            ),
            dict(id="guard", kind="decision", parent="review", label="Check permission"),
        ]
        edges = [
            dict(id="flow", **{"from": "upload"}, to="review", type="flow", label="Submitted"),
            dict(
                id="call",
                **{"from": "store"},
                to="notify",
                type="flow",
                origin="source-ast",
                label="Notify",
            ),
            dict(id="call2", **{"from": "store"}, to="guard", type="data", label="File identity"),
            dict(id="guard-edge", **{"from": "guard"}, to="notify", type="guard", label="Allowed"),
        ]
        if version == 2:
            nodes.append(
                dict(
                    id="receipt",
                    kind="function",
                    parent="upload",
                    label="Save receipt",
                    origin="source-ast",
                )
            )
            edges.append(
                dict(
                    id="receipt-edge",
                    **{"from": "store"},
                    to="receipt",
                    type="flow",
                    origin="source-ast",
                    label="Save",
                )
            )
        return dict(
            project_id="view-continuity-fixture",
            revision=str(version),
            nodes=nodes,
            edges=edges,
            graph_roots=["upload", "review"],
            presentation={"subject": f"View continuity · version {version}"},
            machine={
                "values": ["ready", "done"],
                "transitions": [{"trigger": "finish", "source": "ready", "dest": "done"}],
            },
        )

    def view():
        with lock:
            declaration = model()
            digest = hashlib.sha256(json.dumps(declaration, sort_keys=True).encode()).hexdigest()
            return dict(
                stage="runtime",
                layout_id="view-continuity-fixture",
                model=declaration,
                manifest={"build_id": f"fixture-v{version}", "model_hash": digest, "bindings": {}},
                binding_status={"status": "current"},
                events=deepcopy(events),
                machine={"current": "ready", "configurations": [], "journal": []},
                authority={
                    "state": "ready",
                    "basis": {"param_version": 1},
                    "parameters": {"attempt": "demo"},
                    "effects": [],
                },
                health={
                    "run_id": f"run-v{version}",
                    "attempted": len(events),
                    "errors": 0,
                    "dropped": 0,
                    "enabled": True,
                },
                busy=False,
                historical=False,
                available_cases=["live"],
                program_url="/control",
            )

    recordings = Recordings(directory / "recordings", view, {}, interval=0.1)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, value, status=200, mime="application/json"):
            data = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urlsplit(self.path).path
            try:
                if path == "/api/view":
                    return self.reply(view())
                if path == "/api/preferences":
                    return self.reply(preferences.read())
                if path == "/api/design":
                    return self.reply({"available": False})
                if path == "/api/recordings":
                    return self.reply(recordings.list())
                if path.startswith("/api/recordings/"):
                    return self.reply(recordings.get(path.rsplit("/", 1)[1]))
                if path == "/control":
                    return self.reply(
                        b"""<!doctype html><html lang="en"><title>View continuity test controls</title>
                        <h1>View continuity fixture</h1><p>Isolated acceptance data.</p>
                        <button onclick="fetch('/operation',{method:'POST'}).then(()=>document.querySelector('output').textContent='Operation recorded')">Run operation</button>
                        <button onclick="fetch('/upgrade',{method:'POST'}).then(()=>document.querySelector('output').textContent='Graph version 2 loaded')">Upgrade graph</button><output></output></html>""",
                        mime="text/html; charset=utf-8",
                    )
                name = "index.html" if path in ("/", "/graph") else path.lstrip("/")
                file = (assets / name).resolve()
                if not file.is_relative_to(assets.resolve()) or not file.is_file():
                    return self.reply({"error": "not found"}, 404)
                self.reply(
                    file.read_bytes(),
                    mime=mimetypes.guess_type(file)[0] or "application/octet-stream",
                )
            except ValueError as error:
                self.reply({"error": str(error)}, 400)

        def do_POST(self):
            nonlocal version, events
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            data = json.loads(body or b"{}")
            try:
                if self.path == "/api/preferences":
                    return self.reply(preferences.save(data))
                if self.path == "/api/recordings/start":
                    return self.reply(recordings.start(scope=data.get("scope")))
                if self.path == "/api/recordings/stop":
                    return self.reply(recordings.stop())
                with lock:
                    if self.path == "/upgrade":
                        version, events = 2, []
                    elif self.path == "/operation":
                        seq = len(events) + 1
                        events.append(
                            dict(
                                id=f"e{version}-{seq}",
                                seq=seq,
                                node="upload",
                                phase="return",
                                attempt="demo",
                                run_id=f"run-v{version}",
                                build_id=f"fixture-v{version}",
                                basis={"param_version": 1},
                                inputs={},
                                outputs={},
                                depends=[],
                                call_id=f"call-{seq}",
                            )
                        )
                    else:
                        return self.reply({"error": "not found"}, 404)
                self.reply({"ok": True, "version": version})
            except (ValueError, RuntimeError) as error:
                self.reply({"error": str(error)}, 409)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"http://127.0.0.1:{server.server_port}/graph", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        recordings.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8864)
    parser.add_argument(
        "--directory", type=Path, default=ROOT / ".validation/view-continuity-browser"
    )
    args = parser.parse_args()
    serve(args.directory.resolve(), args.port)
