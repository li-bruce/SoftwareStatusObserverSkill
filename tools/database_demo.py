"""Disposable SQLite application with the canonical graph service and real probes.

The /demo endpoints are acceptance controls, not features of the observer server.
Run: python tools/database_demo.py --port 8868
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/vibelens/scripts"
sys.path.insert(0, str(SCRIPTS))

from sqlalchemy import create_engine, text
from bo_observer.adapters.python.bo_probe import BOProbe
from bo_observer.data.runtime import BODataRuntime
from bo_observer.data.sync import synchronize, runtime_errors
from bo_observer.observation.observation_scope import bo_internal
from bo_observer.service import GraphSession, make_server


SOURCE = '''"""A small picture publication service using SQLAlchemy Core metadata."""
from sqlalchemy import Column, Integer, String, Table, MetaData, ForeignKey, select, insert

metadata = MetaData()
pictures = Table("pictures", metadata,
    Column("id", Integer, primary_key=True),
    Column("title", String(80), nullable=False),
    Column("approved", Integer, nullable=False),
    # EXTRA_COLUMN
)
exhibition = Table("exhibition", metadata,
    Column("id", Integer, primary_key=True),
    Column("picture_id", Integer, ForeignKey("pictures.id"), nullable=False),
)

def load_pictures(connection):
    """Read the current candidates; the caller owns normal result consumption."""
    return list(connection.execute(select(pictures.c.id, pictures.c.approved)).mappings())

def select_approved(rows):
    """Keep pictures that the reviewer approved."""
    return [row for row in rows if row["approved"] == 1]

def save_pictures(connection, rows):
    """Write the selected picture identities in the current transaction."""
    return connection.execute(insert(exhibition), [{"picture_id": row["id"]} for row in rows])

def publish(engine, observer, rollback=False, **context):
    """Query, process and save; a deliberate rejection exercises rollback."""
    with observer.transaction("transaction", engine.begin(), **context) as connection:
        with observer.operation("load", parameters={"approved": 1}, **context):
            rows = load_pictures(connection)
        query_event = observer.last_event_id
        selected = observer.transform("select", select_approved, rows,
            before=lambda items: {"count": len(items)},
            after=lambda items: {"count": len(items)},
            depends=[{"event": query_event, "type": "data"}], **context)
        processing_event = observer.last_event_id
        with observer.operation("save", parameters={"count": len(selected)},
                depends=[{"event": processing_event, "type": "data"}], **context):
            save_pictures(connection, selected)
        if rollback:
            raise ValueError("Synthetic publication rejected")
        return len(selected)
'''


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def load_source(root):
    spec = importlib.util.spec_from_file_location(
        "gallery_" + uuid.uuid4().hex, root / "gallery.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def initialize(root):
    """Create a private synthetic application, its model export and graph declarations."""
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("The demo root must be empty; existing projects are never overwritten")
    (root / "gallery.py").write_text(SOURCE, encoding="utf-8")
    (root / "export_model.py").write_text(
        "import json, sys\n"
        + "sys.path.insert(0, "
        + repr(str(SCRIPTS))
        + ")\n"
        + "from gallery import metadata\n"
        + "from bo_observer.data.catalog import export_sqlalchemy_metadata\n"
        + "print(json.dumps(export_sqlalchemy_metadata(metadata, 'gallery')))\n",
        encoding="utf-8",
    )
    os.environ["BO_DEMO_DB_URL"] = "sqlite:///" + (root / "gallery.sqlite").as_posix()
    engine = create_engine(os.environ["BO_DEMO_DB_URL"])
    module = load_source(root)
    module.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            module.pictures.insert(),
            [{"id": i, "title": f"Picture {i}", "approved": int(i <= 7)} for i in range(1, 13)],
        )
    write_json(
        root / "intent.json",
        {
            "project_id": "database-browser-demo",
            "requirements": [
                {
                    "id": "R1",
                    "text": "Publish approved pictures and roll back rejected attempts.",
                    "status": "confirmed",
                    "source": "Synthetic browser acceptance fixture",
                }
            ],
        },
    )
    machine = {
        "engine": "python.explicit",
        "version": "1",
        "state_type": "enum",
        "states": ["ready", "published"],
        "values": ["ready", "published"],
        "initial": "ready",
        "transitions": [{"source": "ready", "dest": "published", "trigger": "publish"}],
        "events": {"publish": {"payload": {}}},
        "context": {},
        "guards": {},
    }
    project = {
        "protocol": "bo-project/v1",
        "project_id": "database-browser-demo",
        "selection": {
            "mode": "observe",
            "source": "user",
            "answer": "Observe this isolated synthetic database test",
            "locator": "tools/database_demo.py",
        },
        "model": {
            "schema_version": 3,
            "revision": "1",
            "project_id": "database-browser-demo",
            "intent": "intent.json",
            "source_files": ["gallery.py", "export_model.py"],
            "nodes": [
                {
                    "id": "publish",
                    "kind": "action",
                    "layer": "business",
                    "label": "Publish approved pictures",
                    "summary": "Read candidates, keep approved pictures and save the exhibition",
                    "source": {"path": "gallery.py", "symbol": "publish"},
                    "capture": {
                        "in": {"rollback": "boolean"},
                        "out": {"published": "number", "status": "string"},
                    },
                    "requirements": ["R1"],
                }
            ],
            "edges": [],
            "overview": [{"node": "publish"}],
            "scope": {"unknowns": []},
            "machine": machine,
            "presentation": {
                "subject": "Picture publication",
                "layout_id": "database-browser-demo",
            },
        },
    }
    project["model"]["nodes"].extend(
        {
            "id": "state." + state,
            "kind": "state",
            "layer": "state",
            "value": state,
            "label": state,
            "summary": "Publication state",
        }
        for state in machine["values"]
    )
    write_json(root / "bo_stategraph/project.json", project)
    operations = []
    selected_fields = {
        "load": {"parameters": {"approved": "number"}},
        "select": {"before": {"count": "number"}, "after": {"count": "number"}},
        "save": {"parameters": {"count": "number"}},
        "transaction": {"failure_cases": ["rollback"]},
    }
    for ident, label, action, symbol, targets, previous in [
        ("load", "Load pictures", "read", "load_pictures", ["table:pictures"], []),
        ("select", "Select approved pictures", "transform", "select_approved", [], ["load"]),
        ("save", "Save exhibition", "write", "save_pictures", ["table:exhibition"], ["select"]),
        ("transaction", "Publication transaction", "transaction", "publish", [], []),
    ]:
        operations.append(
            {
                "id": ident,
                "label": label,
                "parent": "publish",
                "source": {"path": "gallery.py", "symbol": symbol},
                "store": "gallery",
                "action": action,
                "targets": targets,
                "inputs": previous,
                "parameters": {},
                "before": {},
                "after": {},
                "required_cases": ["commit", "rollback"],
                "requirements": ["R1"],
                **selected_fields[ident],
            }
        )
    config = {
        "protocol": "bo-databases/v1",
        "stores": [
            {
                "id": "gallery",
                "label": "Gallery database",
                "engine": "sqlalchemy",
                "url_env": "BO_DEMO_DB_URL",
                "model_layer": "SQLAlchemy Core MetaData",
                "source_files": ["gallery.py", "export_model.py"],
                "declaration": "bo_stategraph/schema.json",
                "selection": {
                    "source": "user",
                    "answer": "SQLite and SQLAlchemy for this synthetic test",
                    "locator": "tools/database_demo.py",
                },
            }
        ],
        "operations": operations,
        "exporters": [
            {
                "store": "gallery",
                "command": ["{python}", "export_model.py"],
                "output": "bo_stategraph/schema.json",
            }
        ],
    }
    write_json(root / "bo_stategraph/databases.json", config)
    result = synchronize(root)
    if not result["valid"]:
        engine.dispose()
        raise ValueError(result)
    return engine, config


class Demo:
    """Keep application controls separate from the canonical observer HTTP routes."""

    def __init__(self, root):
        self.root = root
        self.engine, self.config = initialize(root)
        self.lock = threading.RLock()
        self.version = 1
        self.install()

    def __getattr__(self, name):
        return getattr(self.session, name)

    def install(self):
        self.module = load_source(self.root)
        self.session = GraphSession(self.root)
        self.runs = {}
        self.ingestion_errors = []

        def receive(event, kind):
            try:
                return self.session.event(event)
            except Exception as error:
                self.ingestion_errors.append(str(error))
                raise

        self.probe = BOProbe(self.session.project, self.session.manifest["build_id"], sink=receive)
        self.runtime = BODataRuntime(self.probe, self.config)
        self.runtime.attach_sqlalchemy(self.engine)

    def run(self, rollback=False):
        with self.lock:
            previous_events = {event["id"] for event in self.session.current_events()}
            attempt = uuid.uuid4().hex
            call_id = "publish-" + attempt
            context = {
                "attempt": attempt,
                "entity": "gallery",
                "scope": "application",
                "parent_call_id": call_id,
            }
            self.probe.record(
                "publish",
                "enter",
                lambda: {"inputs": {"rollback": rollback}},
                call_id=call_id,
                attempt=attempt,
            )
            status, count = "committed", 0
            try:
                count = self.module.publish(self.engine, self.runtime, rollback, **context)
            except ValueError:
                if not rollback:
                    raise
                status = "rolled_back"
            self.probe.record(
                "publish",
                "return",
                lambda: {"outputs": {"published": count, "status": status}},
                call_id=call_id,
                attempt=attempt,
            )
            if not self.probe.flush(5):
                raise RuntimeError("Observation queue did not drain")
            before = self.session.sequence
            # Metadata and monitoring queries on the same engine are explicitly
            # suppressed even while a business operation scope is active.
            with self.runtime.operation("load"), bo_internal(), self.engine.connect() as connection:
                stored = connection.execute(text("SELECT COUNT(*) FROM exhibition")).scalar_one()
            self.probe.flush(5)
            if before != self.session.sequence:
                raise RuntimeError("Observer query leaked into the business trace")
            if self.probe.bo_errors or self.runtime.bo_errors:
                raise RuntimeError(
                    {
                        "probe_errors": self.probe.bo_errors,
                        "runtime_errors": self.runtime.bo_errors,
                        "ingestion_errors": self.ingestion_errors,
                    }
                )
            case = "rollback" if rollback else "commit"
            self.runs[case] = {
                "case": case,
                "mode": "on",
                "events": [
                    event
                    for event in self.session.current_events()
                    if event["id"] not in previous_events
                ],
            }
            mapping_status = "pending"
            if {"commit", "rollback"} <= self.runs.keys():
                failures = runtime_errors(
                    self.root, {"runs": list(self.runs.values())}, self.session.project["model"]
                )
                if failures:
                    raise RuntimeError({"database_mapping_errors": failures})
                mapping_status = "passed"
            return {
                "status": status,
                "stored": stored,
                "events": self.session.sequence,
                "observer_events": self.session.sequence - before,
                "version": self.version,
                "mapping_status": mapping_status,
            }

    def upgrade(self):
        with self.lock:
            if self.version != 1:
                return {"version": self.version, "changed": False}
            self.probe.close()
            self.runtime.close()
            self.session.close()
            # This is the application's explicit migration. synchronize() only
            # reads metadata and exports the modified SQLAlchemy declaration.
            with self.engine.begin() as connection:
                connection.execute(text("ALTER TABLE pictures ADD COLUMN caption VARCHAR(120)"))
            (self.root / "gallery.py").write_text(
                SOURCE.replace("# EXTRA_COLUMN", 'Column("caption", String(120), nullable=True),'),
                encoding="utf-8",
            )
            result = synchronize(self.root)
            if not result["valid"]:
                raise ValueError(result)
            self.version = 2
            self.install()
            return {
                "version": 2,
                "changed": result["changed"],
                "build_id": self.session.manifest["build_id"],
            }

    def check_database(self, available=True):
        """Exercise a real collector failure while retaining the accepted graph."""
        with self.lock:
            previous = os.environ.pop("BO_DEMO_DB_URL") if not available else None
            try:
                result = synchronize(self.root)
                self.session.data_status = result
                return result
            finally:
                if previous is not None:
                    os.environ["BO_DEMO_DB_URL"] = previous

    def close(self):
        self.probe.close()
        self.runtime.close()
        self.session.close()
        self.engine.dispose()


def serve(root, port):
    demo = Demo(root)
    server = make_server(
        demo, port, assets=ROOT / "skills/vibelens/assets/stategraph-viewer"
    )
    base = server.RequestHandlerClass

    class Handler(base):
        def do_GET(self):
            if self.path == "/favicon.ico":
                return self.reply(204, b"", "image/x-icon")
            return super().do_GET()

        def do_POST(self):
            if self.path not in {
                "/demo/run",
                "/demo/upgrade",
                "/demo/stop",
                "/demo/database-check",
            }:
                return super().do_POST()
            if not self.permitted():
                return self.reply(403, {"error": "local same-origin only"})
            try:
                value = json.loads(
                    self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}"
                )
                if self.path == "/demo/stop":
                    self.reply(200, {"stopping": True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                if self.path == "/demo/database-check":
                    return self.reply(200, demo.check_database(value.get("available") is not False))
                result = (
                    demo.run(value.get("rollback") is True)
                    if self.path == "/demo/run"
                    else demo.upgrade()
                )
                self.reply(200, result)
            except Exception as error:
                self.reply(500, {"error": str(error)})

    server.RequestHandlerClass = Handler
    print(f"Database demo: http://127.0.0.1:{port}/graph", flush=True)
    print(f"Disposable application: {root}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        demo.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8868)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    if args.root:
        serve(args.root.resolve(), args.port)
    else:
        (ROOT / ".validation").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="bo-database-demo-", dir=ROOT / ".validation"
        ) as folder:
            serve(Path(folder), args.port)
