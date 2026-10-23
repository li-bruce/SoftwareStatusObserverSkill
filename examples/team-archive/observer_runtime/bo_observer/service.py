"""Project-local collector process and the existing full graph viewer.

The service accepts observations only. It cannot execute a business command.
"""

from collections import OrderedDict
from copy import deepcopy
from functools import wraps
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit, parse_qs
from .protocol import validate_project, validate_event, validate_snapshot
from .session_lifecycle import SessionHost

try:
    from ..behavior_model import read, capture, check, contained, digest
    from ..bo_stategraph import BOStateGraph
    from ..bo_retention import EventHistory
    from ..view_preferences import Preferences, PreferenceConflict
    from ..recording_session import Recordings
    from ..bo_web import BOWeb, ASSETS
except ImportError:
    from behavior_model import read, capture, check, contained, digest
    from bo_stategraph import BOStateGraph
    from bo_retention import EventHistory
    from view_preferences import Preferences, PreferenceConflict
    from recording_session import Recordings
    from bo_web import BOWeb, ASSETS


class GraphSession:
    def __init__(self, root, project_path="bo_stategraph/project.json"):
        """Load one project/build and prepare its bounded event history and recording service."""
        self.root = Path(root).absolute().resolve()
        self.path = contained(self.root, project_path)
        self.project = validate_project(read(self.path))
        self.project_hash = digest(self.project)
        self.model = self.project["model"]
        self.manifest = capture(self.root, self.model)
        self.graph = BOStateGraph(
            self.model, build_id=self.manifest["build_id"], mode=self.project["selection"]["mode"]
        )
        self.lock = threading.RLock()
        self.sequence = 0
        self.producers = {}
        self.seen = OrderedDict()
        self.owners = {}
        self.identities = {}
        self.current_instance = None
        self.program_url = None
        self.data_status = None
        self.errors = self.gaps = 0
        self.last_error = ""
        self.stream_id = secrets.token_hex(12)
        self.frames = OrderedDict()
        self.frame_bytes = 0
        self.frame_evictions = 0
        self.history = EventHistory(
            project_root=self.root, path=self.root / "bo_stategraph/data/events.jsonl"
        )
        self.preferences = Preferences(self.root, self.project["project_id"])
        self.web = BOWeb(self.root)
        self.recordings = Recordings(
            self.root / "bo_stategraph/data/recordings",
            self.view,
            self.sources(),
            event_source=self.history,
        )

    def sources(self):
        """Read the source files bound to this build for later source lookup and recordings."""
        return {
            name: contained(self.root, name).read_text(encoding="utf-8")
            for name in self.manifest["files"]
        }

    def binding(self):
        """Report whether current source bytes still match the loaded build."""
        status = check(self.root, self.model, self.manifest)
        try:
            if digest(read(self.path)) != self.project_hash:
                status.update(status="stale", project_changed=True)
        except (OSError, ValueError):
            status.update(status="stale", project_changed=True)
        return status

    def event(self, event):
        """Validate and append one producer event, preserving its original identity.

        The collector sequence is a display order. Producer sequences and dependency
        IDs remain the evidence for gaps and causal links.
        """
        value = validate_event(event, self.project, self.manifest["build_id"])
        signature = digest(value)
        producer = (value["run_id"], value["producer_id"])
        with self.lock:
            if self.binding()["status"] != "current":
                raise ValueError("source or declaration changed; reload after verification")
            if value["id"] in self.seen:
                if self.seen[value["id"]]["digest"] != signature:
                    raise ValueError("event identity collision")
                return {"accepted": True, "duplicate": True}
            if producer not in self.producers and len(self.producers) >= 1024:
                raise ValueError("producer limit reached")
            prior = self.producers.get(producer, 0)
            if value["seq"] <= prior:
                raise ValueError("old or reordered producer sequence")
            if value["seq"] != prior + 1:
                self.gaps += value["seq"] - prior - 1
            for ref in value["depends"]:
                previous = self.seen.get(ref["event"])
                if previous is None:
                    self.gaps += 1
                    continue
                if previous["run_id"] != value["run_id"]:
                    raise ValueError("cross-run dependency")
            self.sequence += 1
            # Collector order is a display index, not a causal claim.
            stored = {
                **value,
                "source_seq": value["seq"],
                "seq": self.sequence,
                "stream_id": self.stream_id,
            }
            self.producers[producer] = value["seq"]
            self.seen[value["id"]] = {
                "digest": signature,
                "run_id": value["run_id"],
                "producer_id": value["producer_id"],
                "entity": value["entity"],
                "attempt": value["attempt"],
                "revision": value.get("revision"),
            }
            while len(self.seen) > 10000:
                self.seen.popitem(last=False)
            self.history.append(stored)
            return {"accepted": True, "receipt_seq": self.sequence}

    def snapshot(self, value):
        """Attach an application snapshot to its matching recorded event.

        Reject stale revisions, conflicting instance owners, and cross-run evidence
        before updating the graph; retain bounded before/after frames for replay.
        """
        value = validate_snapshot(value, self.project, self.manifest["build_id"])
        with self.lock:
            if self.binding()["status"] != "current":
                raise ValueError("source or declaration changed")
            evidence = self.seen.get(value["evidence_id"])
            if not evidence or (evidence["run_id"], evidence["producer_id"]) != (
                value["run_id"],
                value["producer_id"],
            ):
                raise ValueError("snapshot lacks a matching recorded event")
            if evidence["revision"] != value["revision"]:
                raise ValueError("snapshot needs the same explicit state revision as its event")
            ident = value["run_id"] + ":" + value["instance_id"]
            owner = value["producer_id"]
            if ident in self.owners and self.owners[ident] != owner:
                raise ValueError("instance already has another authoritative producer")
            if ident not in self.owners and len(self.owners) >= 1024:
                raise ValueError("instance limit reached")
            if evidence.get("snapshot_instance") not in (None, ident):
                raise ValueError("event already belongs to another instance snapshot")
            previous = next(
                (
                    i["observed"]
                    for i in self.graph.bo_instances()
                    if i["observed"]["instance_id"] == ident
                ),
                None,
            )
            result = self.graph.bo_observe(
                ident,
                **{
                    k: value[k]
                    for k in (
                        "state",
                        "context",
                        "revision",
                        "evidence_id",
                        "build_id",
                        "configuration",
                        "event",
                        "guards",
                        "payload",
                    )
                },
            )
            if result["accepted"]:
                self.owners[ident] = owner
                self.identities[ident] = {
                    "entity": evidence["entity"],
                    "attempt": evidence["attempt"],
                }
                self.current_instance = ident
                evidence["snapshot_instance"] = ident
                if not result.get("duplicate"):
                    cfg = deepcopy(
                        value.get("configuration")
                        or {
                            "attempt": evidence["attempt"],
                            "phase": value["state"],
                            "param_version": value["revision"],
                            "activities": {},
                            "resources": {},
                            "journal": [],
                        }
                    )
                    journal = []
                    if previous and value["event"]:
                        transition = {
                            "event": value["event"],
                            "source": previous["state"],
                            "target": value["state"],
                            "attempt": evidence["attempt"],
                            "evidence_id": value["evidence_id"],
                            "revision": value["revision"],
                        }
                        cfg["state_transition"] = transition
                        journal = [transition]
                    frame = {
                        "event_id": value["evidence_id"],
                        "run_id": value["run_id"],
                        "build_id": value["build_id"],
                        "revision": value["revision"],
                        "machine": {
                            "current": value["state"],
                            "state_revision": value["revision"],
                            "configurations": [cfg],
                            "journal": journal,
                        },
                        "authority": {
                            "entity": evidence["entity"],
                            "state": value["state"],
                            "basis": {},
                            "parameters": {
                                **deepcopy(value["context"]),
                                "attempt": evidence["attempt"],
                            },
                        },
                    }
                    size = len(json.dumps(frame, ensure_ascii=False, allow_nan=False).encode())
                    self.frames[value["evidence_id"]] = (frame, size)
                    self.frame_bytes += size
                    while len(self.frames) > 2000 or self.frame_bytes > 16 * 1024 * 1024:
                        _, (_, removed) = self.frames.popitem(last=False)
                        self.frame_bytes -= removed
                        self.frame_evictions += 1
            return result

    def view(self):
        """Assemble one consistent viewer snapshot from the graph and retained runtime evidence."""
        with self.lock:
            instances = self.graph.bo_instances()
            current = next(
                (
                    i["observed"]
                    for i in instances
                    if i["observed"]["instance_id"] == self.current_instance
                ),
                {},
            )
            configurations = []
            for entry in instances:
                o = entry["observed"]
                configurations.append(
                    o.get("configuration")
                    or {
                        "attempt": self.identities[o["instance_id"]]["attempt"],
                        "phase": o["state"],
                        "param_version": o["revision"],
                        "activities": {},
                        "resources": {},
                        "journal": [],
                    }
                )
            model = deepcopy(self.model)
            model.setdefault("presentation", {}).setdefault("subject", self.project["project_id"])
            model["machine"].setdefault("labels", {s: s for s in model["machine"]["values"]})
            health = self.history.health()
            current_frame = self.frames.get(current.get("evidence_id"), (None, 0))[0]
            return {
                "stage": "runtime",
                "program_url": self.program_url,
                "layout_id": self.project["project_id"],
                "model": model,
                "manifest": deepcopy(self.manifest),
                "binding_status": self.binding(),
                "events": self.current_events(),
                "database_status": self.data_status,
                "machine": {
                    "current": current.get("state"),
                    "state_revision": current.get("revision"),
                    "configurations": configurations,
                    "journal": (
                        deepcopy(current_frame["machine"]["journal"]) if current_frame else []
                    ),
                },
                "runtime_frames": {
                    "schema": "stategraph-runtime-frames/v1",
                    "partial": True,
                    "frames": [deepcopy(f) for f, _ in self.frames.values()],
                },
                "authority": {
                    "entity": self.identities.get(current.get("instance_id"), {}).get("entity"),
                    "state": current.get("state"),
                    "basis": {},
                    "parameters": {
                        **current.get("context", {}),
                        "attempt": self.identities.get(current.get("instance_id"), {}).get(
                            "attempt"
                        ),
                    },
                },
                "health": {
                    "errors": self.errors + health["log_errors"],
                    # Live history expiry is reported separately. Recording listeners
                    # already received those events, so expiry is not a capture gap.
                    "dropped": self.gaps,
                    "run_id": self.stream_id,
                    "attempted": self.sequence,
                    "written": self.sequence,
                    "enabled": True,
                    "runtime_frame_evictions": self.frame_evictions,
                    **health,
                },
                "busy": False,
                "historical": False,
                "available_cases": ["live"],
                "instances": instances,
            }

    def export(self):
        """Return the complete declared graph with retained events and matching runtime frames."""
        with self.lock:
            events = self.current_events()
            ids = {e["id"] for e in events}
            return self.graph.bo_export(
                binding=self.binding(),
                runtime={
                    "events": events,
                    "runtime_frames": {
                        "schema": "stategraph-runtime-frames/v1",
                        "partial": True,
                        "frames": [
                            deepcopy(f) for key, (f, _) in self.frames.items() if key in ids
                        ],
                    },
                },
            )

    def current_events(self):
        """Keep prior build evidence out of the live graph after source or schema changes."""
        return [
            e for e in self.history.snapshot() if e.get("build_id") == self.manifest["build_id"]
        ]

    def close(self):
        """Stop the recording worker and its subscriptions during server shutdown."""
        self.recordings.close()


def make_server(session, port=8830, *, token=None, origins=(), assets=ASSETS):
    """Create a localhost collector and viewer with explicit origin and ingestion-token checks."""
    token = token or secrets.token_urlsafe(32)
    origins = frozenset(origins)
    if any(
        urlsplit(o).scheme not in ("http", "https")
        or urlsplit(o).hostname not in ("localhost", "127.0.0.1")
        or urlsplit(o).path
        for o in origins
    ):
        raise ValueError("collector origins must be explicit local development origins")
    assets = Path(session.web.assets if assets == ASSETS else assets).resolve()
    session.program_url = next(iter(origins)) if len(origins) == 1 else None
    host = SessionHost(
        session,
        lambda previous: GraphSession(
            previous.root, previous.path.relative_to(previous.root).as_posix()
        ),
    )

    def consistent_request(method):
        """Finish each request against one session while a watcher may replace the build."""

        @wraps(method)
        def handle(handler):
            with host.borrow() as current:
                return method(handler, current)

        return handle

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def permitted(self, ingest=False):
            if self.headers.get("Host") not in {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }:
                return False
            origin = self.headers.get("Origin")
            allowed = (
                not origin
                or origin == "http://" + self.headers["Host"]
                or ingest
                and origin in origins
            )
            return allowed and (
                not ingest or secrets.compare_digest(self.headers.get("X-BO-Token", ""), token)
            )

        def reply(self, code, body, mime="application/json"):
            raw = (
                body
                if isinstance(body, bytes)
                else json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
            )
            self.send_response(code)
            for k, v in [
                ("Content-Type", mime + "; charset=utf-8"),
                ("Content-Length", str(len(raw))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
            ]:
                self.send_header(k, v)
            origin = self.headers.get("Origin")
            if origin in origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self):
            if self.headers.get("Origin") not in origins:
                return self.reply(403, {"error": "origin denied"})
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Access-Control-Allow-Methods", "POST")
            self.send_header("Access-Control-Allow-Headers", "Content-Type,X-BO-Token")
            self.send_header("Vary", "Origin")
            self.end_headers()

        @consistent_request
        def do_GET(self, session):
            if not self.permitted():
                return self.reply(403, {"error": "local same-origin only"})
            path = urlsplit(self.path).path
            try:
                if path == "/api/bo/health":
                    return self.reply(
                        200,
                        {
                            "protocol": "bo-project/v1",
                            "project_id": session.project["project_id"],
                            "build_id": session.manifest["build_id"],
                            "binding": session.binding(),
                        },
                    )
                if not session.web.allowed(path):
                    return self.reply(
                        404, {"error": "Debug Web is disabled", "code": "bo_web_disabled"}
                    )
                if path == "/api/view":
                    return self.reply(200, session.view())
                if path.startswith("/api/code/"):
                    return self.reply(200, session.web.get(self.path))
                if path in ("/api/stategraph", "/api/stategraph/export"):
                    return self.reply(200, session.export())
                if path == "/api/preferences":
                    return self.reply(200, session.preferences.read())
                if path == "/api/design":
                    return self.reply(200, session.web.design.snapshot())
                if path == "/api/versions":
                    return self.reply(200, [])
                if path == "/api/recordings":
                    return self.reply(200, session.recordings.list())
                if path.startswith("/api/recordings/"):
                    return self.reply(200, session.recordings.get(path.rsplit("/", 1)[-1]))
                if path == "/api/source":
                    q = parse_qs(urlsplit(self.path).query)
                    name = q.get("path", [""])[0]
                    sources = (
                        session.recordings.get(q["recording"][0])["sources"]
                        if q.get("recording")
                        else session.recordings.sources
                    )
                    if name not in sources:
                        return self.reply(404, {"error": "Source not in this build"})
                    return self.reply(
                        200, {"source": sources[name], "build_id": session.manifest["build_id"]}
                    )
                name = "index.html" if path in ("/", "/graph", "/graph/") else path[1:]
                if "/" in name or "\\" in name or name.startswith("."):
                    return self.reply(404, {"error": "not found"})
                file = assets / name
                if not file.is_file():
                    return self.reply(404, {"error": "not found"})
                return self.reply(
                    200,
                    file.read_bytes(),
                    mimetypes.guess_type(name)[0] or "application/octet-stream",
                )
            except (OSError, ValueError, KeyError) as exc:
                return self.reply(400, {"error": str(exc)})

        @consistent_request
        def do_POST(self, session):
            path = urlsplit(self.path).path
            ingest = path.startswith("/api/bo/")
            if not self.permitted(ingest):
                return self.reply(403, {"error": "origin or collector token denied"})
            try:
                if not ingest and not session.web.allowed(path):
                    return self.reply(
                        404, {"error": "Debug Web is disabled", "code": "bo_web_disabled"}
                    )
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= (24576 if ingest else 2 * 1024 * 1024):
                    raise ValueError("invalid payload size")
                body = json.loads(self.rfile.read(size))
                if path == "/api/bo/events":
                    return self.reply(200, session.event(body))
                if path == "/api/bo/snapshots":
                    return self.reply(200, session.snapshot(body))
                if path == "/api/preferences":
                    return self.reply(200, session.preferences.save(body))
                if path == "/api/recordings/start":
                    return self.reply(
                        200, session.recordings.start(body.get("label", ""), body.get("scope"))
                    )
                if path == "/api/recordings/stop":
                    return self.reply(200, session.recordings.stop())
                return self.reply(405, {"error": "No business commands are exposed"})
            except PreferenceConflict as exc:
                return self.reply(409, {"error": str(exc)})
            except (OSError, ValueError, KeyError, TypeError) as exc:
                if ingest:
                    with session.lock:
                        session.errors += 1
                        session.last_error = str(exc)
                return self.reply(400, {"error": str(exc)})

    class SessionServer(ThreadingHTTPServer):
        def server_close(self):
            super().server_close()
            host.close()

    server = SessionServer(("127.0.0.1", port), Handler)
    server.bo_token = token
    server.bo_session = session

    def reload_session():
        """Load current declarations without transferring obsolete events or machine instances."""
        changed = host.reload()
        server.bo_session = host.current
        return changed

    server.bo_reload = reload_session
    return server
