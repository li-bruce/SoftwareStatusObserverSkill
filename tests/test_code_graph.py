"""Independent source, query and HTTP regressions for optional code structure."""

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "skills/business-observer/scripts"), str(ROOT / "tools")]
from bo_observer.code_graph.service import CodeGraph
from bo_observer.code_graph.query import query
from bo_observer.service import GraphSession, make_server
from observation_scope import observer_route
from test_multilanguage import project_fixture


class CodeGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".validation")
        self.root = Path(self.temp.name)
        self.project = project_fixture(self.root)
        self.service = CodeGraph(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, text):
        (self.root / path).write_text(text, encoding="utf-8")

    def test_independent_new_file_and_deleted_file(self):
        old, _ = self.service.refresh()
        self.write("new_feature.py", "def added(value):\n    return value\n")
        new, _ = self.service.refresh()
        self.assertNotEqual(old["revision"], new["revision"])
        self.assertIn("new_feature.py::added", new["symbols"])
        self.assertIn("worker.py", new["incremental"]["reused"])
        (self.root / "new_feature.py").unlink()
        latest, _ = self.service.refresh()
        self.assertNotIn("new_feature.py::added", latest["symbols"])

    def test_stable_identity_parameters_and_repeated_calls(self):
        source = (
            "def target(v):\n    return v\ndef caller(v):\n    target(v)\n    return target(v)\n"
        )
        self.write("calls.py", source)
        first, _ = self.service.refresh()
        calls = [e for e in first["edges"] if e["code_relation"] == "calls"]
        self.assertEqual(len(calls), 2)
        self.assertEqual(len({e["id"] for e in calls}), 2)
        self.write("calls.py", "# A comment moves source locations\n" + source)
        second, _ = self.service.refresh()
        self.assertEqual(
            [e["id"] for e in calls],
            [e["id"] for e in second["edges"] if e["code_relation"] == "calls"],
        )
        self.assertTrue(any(n["code_role"] == "parameter" for n in second["nodes"]))

    def test_calls_imports_inheritance_and_unknowns(self):
        self.write("base.py", "class Base:\n    pass\ndef helper(x):\n    return x\n")
        self.write(
            "child.py",
            "from base import Base, helper\nclass Child(Base):\n    def run(self, x):\n        unknown(x)\n        return helper(x)\n",
        )
        graph, _ = self.service.refresh()
        self.assertFalse(graph["errors"])
        relations = {e["code_relation"] for e in graph["edges"]}
        self.assertTrue({"calls", "imports", "inherits", "defines", "parameter"} <= relations)
        unknown = next(n for n in graph["nodes"] if n["label"] == "unknown")
        self.assertEqual(unknown["code_role"], "unresolved")
        inherit = next(e for e in graph["edges"] if e["code_relation"] == "inherits")
        self.assertEqual(inherit["to"], graph["symbols"]["base.py::Base"])

    def test_focused_authored_binding_and_relation_endpoints(self):
        graph = self.service.view(focus="advance")
        self.assertTrue(
            any(e["code_relation"] == "maps" and e["from"] == "advance" for e in graph["edges"])
        )
        self.assertEqual(graph["status"], "current")
        ids = {n["id"] for n in graph["nodes"]} | {"advance"}
        self.assertTrue(all(e["from"] in ids and e["to"] in ids for e in graph["edges"]))
        with self.assertRaises(ValueError):
            self.service.view(focus="fabricated")

    def test_limits_are_explicit_and_sources_revision_bound(self):
        graph, _ = self.service.refresh()
        full = deepcopy(graph)
        limited = self.service.view(limit=1)
        self.assertEqual(limited["loaded_nodes"], 1)
        self.assertGreater(limited["omitted_nodes"], 0)
        self.assertEqual(graph, full)
        with self.assertRaises(ValueError):
            self.service.view(limit=5001)
        self.assertIn("advance", self.service.source("worker.py", graph["revision"])["source"])
        for path in ("../private.py", "intent.json"):
            with self.assertRaises(ValueError):
                self.service.source(path, graph["revision"])
        self.write("worker.py", "def advance():\n    return 1\n")
        with self.assertRaises(ValueError):
            self.service.source("worker.py", graph["revision"])

    def test_parse_failure_removes_stale_nodes_and_recovers(self):
        first, _ = self.service.refresh()
        self.write("worker.py", "def broken(:\n")
        partial = self.service.view()
        self.assertEqual(partial["status"], "incomplete")
        self.assertTrue(partial["errors"])
        self.assertFalse(
            any(n.get("code_symbol") == "worker.py::advance" for n in partial["nodes"])
        )
        self.write("worker.py", "def recovered():\n    return True\n")
        recovered, _ = self.service.refresh()
        self.assertIn("worker.py::recovered", recovered["symbols"])
        self.assertFalse(recovered["errors"])

    def test_node_react_vue_share_protocol(self):
        self.write(
            "logic.ts",
            "export class Base {}\nexport function save(value: string) { return value; }\n",
        )
        self.write(
            "Panel.tsx",
            'import {save, Base} from "./logic";\nclass Panel extends Base { run(value: string) { return save(value); } }\nexport function View() { return <button onClick={() => save("x")}>Save</button>; }',
        )
        self.write(
            "Form.vue",
            '<script setup lang="ts">\nimport {save} from "./logic";\nfunction submit() { return save("x"); }\n</script><template><button @click="submit">Save</button></template>',
        )
        graph, _ = self.service.refresh()
        self.assertFalse(graph["errors"], graph["errors"])
        self.assertIn("Panel.tsx::Panel.run", graph["symbols"])
        target = graph["symbols"]["logic.ts::save"]
        self.assertGreaterEqual(
            sum(e["to"] == target and e["code_relation"] == "calls" for e in graph["edges"]), 2
        )
        self.assertIn("Form.vue::submit", graph["symbols"])

    def test_module_initialization_and_commonjs(self):
        self.write("init.py", "def initialize():\n    return 1\nvalue = initialize()\n")
        self.write("library.cjs", "function save(v) { return v; }\nexports.save = save;\n")
        self.write(
            "client.cjs",
            'const {save} = require("./library.cjs");\nfunction run(v) { return save(v); }\nfunction callback(save) { return save(2); }\nfunction destructured({save}) { return save(2); }',
        )
        graph, _ = self.service.refresh()
        self.assertFalse(graph["errors"])
        module = graph["symbols"]["init.py::<module>"]
        target = graph["symbols"]["init.py::initialize"]
        self.assertTrue(any(e["from"] == module and e["to"] == target for e in graph["edges"]))
        save = graph["symbols"]["library.cjs::save"]
        caller = graph["symbols"]["client.cjs::run"]
        callback = graph["symbols"]["client.cjs::callback"]
        self.assertTrue(any(e["from"] == caller and e["to"] == save for e in graph["edges"]))
        self.assertFalse(any(e["from"] == callback and e["to"] == save for e in graph["edges"]))
        destructured = graph["symbols"]["client.cjs::destructured"]
        self.assertFalse(any(e["from"] == destructured and e["to"] == save for e in graph["edges"]))

    def test_http_disabled_web_and_no_observer_events(self):
        session = GraphSession(self.root)
        server = make_server(session, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            self.assertIsNone(session.web.code_graph.graph)
            for _ in range(3):
                with urlopen(url + "/api/code/graph?focus=advance") as response:
                    self.assertEqual(json.load(response)["status"], "current")
            self.assertEqual(session.sequence, 0)
            self.assertTrue(observer_route("/api/code/graph?focus=advance"))
            self.assertEqual(session.model, self.project["model"])
            session.web.set_mode("disabled")
            with self.assertRaises(HTTPError) as error:
                urlopen(url + "/api/code/graph")
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            session.close()

    def test_independent_check_rejects_stale_and_tampered_graph(self):
        graph, _ = self.service.refresh()
        self.assertTrue(self.service.check()["valid"])
        self.write("worker.py", "def changed():\n    return 2\n")
        self.assertFalse(self.service.check()["valid"])
        self.assertEqual(json.loads(self.service.cache.read_text())["revision"], graph["revision"])
        self.service.refresh()
        self.assertTrue(self.service.check()["valid"])
        forged = json.loads(self.service.cache.read_text())
        forged["nodes"] = []
        self.service.cache.write_text(json.dumps(forged), encoding="utf-8")
        self.assertFalse(self.service.check()["valid"])

    def test_empty_or_invalid_saved_index_is_a_failure_without_repair(self):
        self.service.refresh()
        for raw in ("{}", "[]", "null", "false", "{broken"):
            with self.subTest(raw=raw):
                self.service.cache.write_text(raw, encoding="utf-8")
                checked = self.service.check()
                self.assertTrue(checked["enabled"])
                self.assertFalse(checked["valid"])
                self.assertEqual(checked["status"], "failed")
                self.assertEqual(self.service.cache.read_text(encoding="utf-8"), raw)

    def test_default_scope_includes_project_owned_state_module_code(self):
        self.write("bo_stategraph/workflow.py", "def execute_business(value):\n    return value\n")
        graph, _ = self.service.refresh()
        self.assertIn("bo_stategraph/workflow.py::execute_business", graph["symbols"])
        self.assertFalse(graph["errors"])

    def test_default_scope_excludes_only_unchanged_managed_copies(self):
        from bo_observer.graph.behavior_model import digest

        self.write("bo_stategraph/bo_support.py", "def support():\n    return 1\n")
        self.write(
            "bo_stategraph/runtime-version.json",
            json.dumps(
                {
                    "schema": 1,
                    "files": {
                        "bo_stategraph/bo_support.py": digest(
                            (self.root / "bo_stategraph/bo_support.py").read_bytes()
                        )
                    },
                }
            ),
        )
        graph, _ = self.service.refresh()
        self.assertNotIn("bo_stategraph/bo_support.py::support", graph["symbols"])
        self.write("bo_stategraph/bo_support.py", "def support():\n    return 2\n")
        graph, _ = self.service.refresh()
        self.assertIn("bo_stategraph/bo_support.py::support", graph["symbols"])

    def test_slow_code_request_does_not_block_actual_event_ingestion(self):
        from bo_observer.adapters.python.bo_probe import BOProbe

        session = GraphSession(self.root)
        server = make_server(session, port=0, token="code-concurrency-test")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        entered, release, delivered = threading.Event(), threading.Event(), threading.Event()
        original = session.web.code_graph.view

        def slow(**options):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("Test failed to release the source request")
            return original(**options)

        session.web.code_graph.view = slow
        probe = BOProbe(
            self.project,
            session.manifest["build_id"],
            endpoint=url,
            token="code-concurrency-test",
            timeout=10,
        )

        def read_code():
            with urlopen(url + "/api/code/graph", timeout=15) as response:
                return json.load(response)

        def send_event():
            probe.record("advance", "change", lambda: {"outputs": {"state": "waiting"}}, revision=1)
            result = probe.flush(timeout=10)
            delivered.set()
            return result

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                code = pool.submit(read_code)
                self.assertTrue(entered.wait(3))
                event = pool.submit(send_event)
                try:
                    independent = delivered.wait(3)
                finally:
                    release.set()
                self.assertTrue(event.result(timeout=10))
                self.assertEqual(code.result(timeout=10)["status"], "current")
                self.assertTrue(independent, "Source reading serialized the ingestion request")
                self.assertEqual(session.sequence, 1)
                self.assertEqual(probe.bo_errors, 0)
        finally:
            release.set()
            probe.close()
            server.shutdown()
            server.server_close()
            thread.join()
            session.close()

    def test_conditional_declarations_and_maintenance_refresh(self):
        from bo_sync import maintenance_task

        self.write("conditional.py", "if True:\n    def callback(value):\n        return value\n")
        graph, _ = self.service.refresh()
        self.assertIn("conditional.py::callback", graph["symbols"])
        cfg = {
            "model": "bo_stategraph/project.json",
            "source_scope": {"roots": ["worker.py", "conditional.py"]},
            "code_files": ["worker.py", "conditional.py"],
        }
        self.write("sync.json", json.dumps(cfg))
        self.write("conditional.py", "if True:\n    def updated(value):\n        return value\n")
        self.assertFalse(self.service.check()["valid"])
        maintenance_task(self.root, cfg)
        self.assertTrue(self.service.check()["valid"])
        saved = json.loads(self.service.cache.read_text())
        self.assertIn("conditional.py::updated", saved["symbols"])

    def test_conditional_bindings_match_inventory_and_capture(self):
        from bo_observer.graph.behavior_model import symbols, capture
        from bo_observer.graph.code_structure import parse_unit

        source = (
            "if True:\n    def advance(state, event, slots):\n        return 'waiting'\n"
            "def outer():\n    try:\n        def nested(value):\n            return value\n"
            "    finally:\n        pass\n    return nested(1)\n"
            "match 1:\n    case 1:\n        class Conditional:\n            pass\n"
        )
        self.write("worker.py", source)
        self.assertEqual(
            set(symbols(self.root / "worker.py")),
            set(parse_unit("worker.py", source)["symbols"]),
        )
        manifest = capture(self.root, self.project["model"])
        self.assertEqual(manifest["bindings"]["advance"]["symbol"], "advance")
        self.assertIn("def advance", manifest["bindings"]["advance"]["snippet"])

    def test_conditional_redefinitions_remain_ambiguous(self):
        from bo_observer.graph.behavior_model import symbols
        from bo_observer.graph.code_structure import parse_unit

        source = "if True:\n    def action(): pass\nelse:\n    def action(): pass\n"
        self.write("ambiguous.py", source)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            symbols(self.root / "ambiguous.py")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            parse_unit("ambiguous.py", source)

    def test_reload_publishes_new_build_while_old_source_request_finishes(self):
        from bo_observer.adapters.python.bo_probe import BOProbe

        session = GraphSession(self.root)
        server = make_server(session, port=0, token="reload-test")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        original_view, original_close = session.web.code_graph.view, session.close

        def slow(**options):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("Source request was not released")
            return original_view(**options)

        def close():
            original_close()
            closed.set()

        session.web.code_graph.view, session.close = slow, close

        def get(path):
            with urlopen(url + path, timeout=15) as response:
                return json.load(response)

        probes = []
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                request = pool.submit(get, "/api/code/graph")
                self.assertTrue(entered.wait(3))
                self.write(
                    "worker.py",
                    "def advance(state: str, event: str, slots: int):\n    return 'waiting'\n",
                )
                reloading = pool.submit(server.bo_reload)
                try:
                    self.assertTrue(reloading.result(timeout=3))
                    self.assertFalse(closed.is_set())
                    current = server.bo_session
                    self.assertNotEqual(current.manifest["build_id"], session.manifest["build_id"])
                    self.assertEqual(
                        get("/api/bo/health")["build_id"], current.manifest["build_id"]
                    )
                    for build, wanted_errors in [
                        (session.manifest["build_id"], 1),
                        (current.manifest["build_id"], 0),
                    ]:
                        probe = BOProbe(
                            self.project, build, endpoint=url, token="reload-test", timeout=3
                        )
                        probes.append(probe)
                        probe.record(
                            "advance",
                            "change",
                            lambda: {"outputs": {"state": "waiting"}},
                            revision=1,
                        )
                        self.assertTrue(probe.flush(timeout=4))
                        self.assertEqual(probe.bo_errors, wanted_errors)
                    self.assertEqual(current.sequence, 1)
                finally:
                    release.set()
                request.result(timeout=5)
                self.assertTrue(closed.wait(3))
        finally:
            release.set()
            for probe in probes:
                probe.close()
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertTrue(server.bo_session.recordings.closed.is_set())


if __name__ == "__main__":
    unittest.main()
